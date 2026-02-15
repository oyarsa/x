"""Firefox History Audit Tool.
===========================
Analyzes Firefox browsing history to estimate how many pages are worth
archiving for a local search engine. Deduplicates and filters URLs to
give a realistic count of unique, archivable pages.

Usage:
    python3 audit.py <profile_folder_name>
    python3 audit.py auto --days 14 -v
    python3 audit.py auto -o urls.txt

Requirements:
    - macOS with Firefox installed
    - Firefox must be CLOSED (SQLite will fail on a locked database)
    - Python 3.7+
"""

import argparse
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse, urlunparse

FIREFOX_PROFILES_DIR = Path(
    "~/Library/Application Support/Firefox/Profiles"
).expanduser()

# --- Tracking / junk query parameters to strip ---
TRACKING_PARAMS = {
    # UTM / campaign tracking
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_source_platform",
    "utm_creative_format",
    "utm_marketing_tactic",
    # Facebook / Meta
    "fbclid",
    "fb_action_ids",
    "fb_action_types",
    "fb_ref",
    "fb_source",
    # Google
    "gclid",
    "gclsrc",
    "dclid",
    "gbraid",
    "wbraid",
    "gad_source",
    # Microsoft / Bing
    "msclkid",
    # Twitter / X
    "twclid",
    # HubSpot
    "hsa_cam",
    "hsa_grp",
    "hsa_mt",
    "hsa_src",
    "hsa_ad",
    "hsa_acc",
    "hsa_net",
    "hsa_ver",
    "hsa_la",
    "hsa_ol",
    "hsa_kw",
    # Mailchimp
    "mc_cid",
    "mc_eid",
    # General tracking / analytics
    "ref",
    "_ref",
    "ref_",
    "referrer",
    "source",
    "src",
    "_ga",
    "_gid",
    "_gl",
    "yclid",
    "ymclid",
    "spm",
    "scm",
    "aff_id",
    "aff_sub",
    "zanpid",
    "irclickid",
    # Session / interaction noise
    "_hsenc",
    "_hsmi",
    "_openstat",
    "mkt_tok",
    "trk",
    "trkCampaign",
    "trkInfo",
    "si",
    "feature",
    "app",
    "t",
}

# --- Pagination-like query parameters (used for collapsing) ---
PAGINATION_PARAMS = {
    "page",
    "p",
    "pg",
    "offset",
    "start",
    "from",
    "cursor",
    "after",
    "before",
    "next",
    "skip",
    "limit",
    "per_page",
    "pagesize",
    "page_size",
    "pagenumber",
    "page_number",
}

# --- Non-archivable file extensions ---
NON_HTML_EXTENSIONS = {
    ".json",
    ".xml",
    ".rss",
    ".atom",
    ".yaml",
    ".yml",
    ".js",
    ".mjs",
    ".css",
    ".map",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".bmp",
    ".avif",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".mp3",
    ".mp4",
    ".webm",
    ".ogg",
    ".wav",
    ".flac",
    ".m4a",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".gz",
    ".tar",
    ".bz2",
    ".7z",
    ".rar",
    ".wasm",
}

# --- URL path patterns that are not archivable pages ---
NON_ARCHIVABLE_PATH_PATTERNS = [
    re.compile(r"/api/", re.IGNORECASE),
    re.compile(r"/graphql", re.IGNORECASE),
    re.compile(r"/oauth", re.IGNORECASE),
    re.compile(r"/auth/", re.IGNORECASE),
    re.compile(r"/login", re.IGNORECASE),
    re.compile(r"/logout", re.IGNORECASE),
    re.compile(r"/signin", re.IGNORECASE),
    re.compile(r"/signout", re.IGNORECASE),
    re.compile(r"/callback", re.IGNORECASE),
    re.compile(r"/webhook", re.IGNORECASE),
    re.compile(r"/\.well-known/", re.IGNORECASE),
    re.compile(r"/wp-admin/", re.IGNORECASE),
    re.compile(r"/wp-json/", re.IGNORECASE),
    re.compile(r"/feed/?$", re.IGNORECASE),
    re.compile(r"/rss/?$", re.IGNORECASE),
    re.compile(r"/embed/?", re.IGNORECASE),
    re.compile(r"/amp/?$", re.IGNORECASE),
    re.compile(r"/_next/", re.IGNORECASE),
    re.compile(r"/_nuxt/", re.IGNORECASE),
    re.compile(r"/static/", re.IGNORECASE),
    re.compile(r"/assets/", re.IGNORECASE),
    re.compile(r"/unsubscribe", re.IGNORECASE),
    re.compile(r"/track/click", re.IGNORECASE),
]

# --- Domains that require auth (archiving will just get a login page) ---
AUTH_GATED_DOMAINS = {
    # Email
    "mail.google.com",
    "outlook.live.com",
    "outlook.office.com",
    "outlook.office365.com",
    "mail.yahoo.com",
    "mail.proton.me",
    "mail.protonmail.com",
    "app.fastmail.com",
    # Chat / messaging
    "app.slack.com",
    "teams.microsoft.com",
    "discord.com",
    "web.whatsapp.com",
    "web.telegram.org",
    "messages.google.com",
    # Cloud storage / docs (behind auth)
    "docs.google.com",
    "drive.google.com",
    "sheets.google.com",
    "slides.google.com",
    "onedrive.live.com",
    "dropbox.com",
    "www.dropbox.com",
    # Social media (feeds require auth)
    "www.facebook.com",
    "www.instagram.com",
    "www.messenger.com",
    # Dev tools (dashboards / settings)
    "app.netlify.com",
    "vercel.com",
    "dashboard.heroku.com",
    "console.cloud.google.com",
    "console.aws.amazon.com",
    "console.hetzner.com",
    "portal.azure.com",
    "app.circleci.com",
    "fly.io",
    # Internal tools
    "localhost",
    "127.0.0.1",
    "0.0.0.0",  # noqa: S104
    "kagi.com",
    "duckduckgo.com",
    "www.youtube.com",
    "www.amazon.co.uk",
    "aistudio.google.com",
    "claude.ai",
    "chatgpt.com",
}

# --- Entire domain suffixes to skip ---
AUTH_GATED_DOMAIN_PATTERNS = [
    re.compile(r"^accounts?\."),
    re.compile(r"\.slack\.com$"),
    re.compile(r"\.atlassian\.net$"),
    re.compile(r"\.jira\.com$"),
    re.compile(r"\.zendesk\.com$"),
    re.compile(r"\.salesforce\.com$"),
    re.compile(r"\.service-now\.com$"),
    re.compile(r"\.okta\.com$"),
    re.compile(r"\.auth0\.com$"),
    re.compile(r"\.myworkday\.com$"),
    re.compile(r"\.namely\.com$"),
    re.compile(r"\.bamboohr\.com$"),
]

# --- Domains that are API endpoints, not browsable sites ---
API_DOMAIN_PATTERNS = [
    re.compile(r"^api\."),
    re.compile(r"^api-"),
    re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"),
]

# --- Email tracking/redirect subdomain prefixes ---
EMAIL_TRACKING_DOMAIN_PATTERNS = [
    re.compile(r"^link\."),
    re.compile(r"^links\."),
    re.compile(r"^click\."),
    re.compile(r"^clicks\."),
    re.compile(r"^track\."),
    re.compile(r"^trk\."),
    re.compile(r"^go\."),
    re.compile(r"^e\."),
    re.compile(r"^t\."),
    re.compile(r"^email\."),
    re.compile(r"^enews\."),
    re.compile(r"^mailings\."),
    re.compile(r"^mail\."),
    re.compile(r"^mailer\."),
    re.compile(r"^news\."),
    re.compile(r"^post\."),
    re.compile(r"^em\."),
]

# --- Path-based pagination patterns ---
PATH_PAGINATION_PATTERNS = [
    re.compile(r"/page/\d+/?$", re.IGNORECASE),
    re.compile(r"/p/\d+/?$", re.IGNORECASE),
    re.compile(r"/pages/\d+/?$", re.IGNORECASE),
]

# Minimum length of a single path segment to be considered opaque/tracking junk.
# Real page paths rarely have a single segment this long.
OPAQUE_PATH_SEGMENT_THRESHOLD = 80

# --- Schemes that aren't web pages ---
VALID_SCHEMES = {"http", "https"}


# ============================================================================
# URL cleaning & filtering
# ============================================================================


def classify_url(url: str) -> str | None:
    """Classify a URL and return a filter reason string if it should be excluded,
    or None if it's archivable.
    """
    parsed = urlparse(url)

    # Scheme filter
    if parsed.scheme not in VALID_SCHEMES:
        return "non-http scheme"

    # Empty host
    if not parsed.netloc:
        return "no host"

    # Auth-gated domains
    domain = parsed.netloc.lower().split(":")[0]  # strip port
    if domain in AUTH_GATED_DOMAINS:
        return "auth-gated domain"
    for pat in AUTH_GATED_DOMAIN_PATTERNS:
        if pat.search(domain):
            return "auth-gated domain"

    # API-only domains (not browsable sites)
    for pat in API_DOMAIN_PATTERNS:
        if pat.search(domain):
            return "API domain"

    # Email tracking/redirect domains
    for pat in EMAIL_TRACKING_DOMAIN_PATTERNS:
        if pat.search(domain):
            return "email tracking domain"

    # File extension
    path_lower = parsed.path.lower()
    dot_pos = path_lower.rfind(".")
    if dot_pos != -1:
        ext = path_lower[dot_pos:]
        if ext in NON_HTML_EXTENSIONS and "/" not in ext:
            return f"non-HTML extension ({ext})"

    # Path pattern filters
    for pat in NON_ARCHIVABLE_PATH_PATTERNS:
        if pat.search(parsed.path):
            return f"non-archivable path ({pat.pattern})"

    # Long opaque path segments (email tracking blobs, base64 junk)
    for segment in parsed.path.split("/"):
        if len(segment) >= OPAQUE_PATH_SEGMENT_THRESHOLD:
            return "opaque tracking path"

    return None


def strip_tracking_params(url: str) -> str:
    """Remove tracking/analytics query parameters from a URL."""
    parsed = urlparse(url)
    if not parsed.query:
        return url

    params = parse_qs(parsed.query, keep_blank_values=True)
    cleaned = {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS}

    if not cleaned:
        new_query = ""
    else:
        new_query = urlencode(
            {k: v[0] if len(v) == 1 else v for k, v in cleaned.items()},
            doseq=True,
        )

    return urlunparse(parsed._replace(query=new_query, fragment=""))


def strip_pagination_params(url: str) -> str:
    """Remove pagination parameters to collapse paginated views."""
    parsed = urlparse(url)
    if not parsed.query:
        return url

    params = parse_qs(parsed.query, keep_blank_values=True)
    cleaned = {k: v for k, v in params.items() if k.lower() not in PAGINATION_PARAMS}

    if not cleaned:
        new_query = ""
    else:
        new_query = urlencode(
            {k: v[0] if len(v) == 1 else v for k, v in cleaned.items()},
            doseq=True,
        )

    return urlunparse(parsed._replace(query=new_query, fragment=""))


def normalize_url(url: str) -> str:
    """Full normalization: strip tracking, fragments, trailing slashes,
    canonicalize scheme, host, path encoding, and query param order.
    """
    url = strip_tracking_params(url)
    parsed = urlparse(url)

    # Scheme: normalize to https
    scheme = "https"

    # Host: lowercase + strip www.
    netloc = parsed.netloc.lower()
    host, _, port = netloc.partition(":")
    if host.startswith("www."):
        host = host[4:]
    netloc = f"{host}:{port}" if port else host

    # Path: normalize percent-encoding + strip trailing slash
    path = quote(unquote(parsed.path), safe="/:@!$&'()*+,;=-._~")
    path = path.rstrip("/") or "/"

    # Query: sort parameters for canonical order
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        sorted_query = urlencode(
            {k: v[0] if len(v) == 1 else v for k, v in sorted(params.items())},
            doseq=True,
        )
    else:
        sorted_query = ""

    return urlunparse((scheme, netloc, path, "", sorted_query, ""))


def strip_pagination_path(url: str) -> str:
    """Remove path-based pagination segments like /page/2/."""
    parsed = urlparse(url)
    path = parsed.path
    for pat in PATH_PAGINATION_PATTERNS:
        path = pat.sub("/", path)
    return urlunparse(parsed._replace(path=path))


def deduplicate_pagination(urls: set[str]) -> set[str]:
    """Collapse URLs that differ only by pagination params or path segments.
    Iterates in sorted order for deterministic representative selection.
    """
    seen_bases: dict[str, str] = {}
    for url in sorted(urls):
        base = strip_pagination_params(url)
        base = strip_pagination_path(base)
        if base not in seen_bases:
            seen_bases[base] = url
    return set(seen_bases.values())


# ============================================================================
# Firefox data extraction
# ============================================================================


def resolve_profile(profile_name: str) -> Path:
    if profile_name == "auto":
        candidates = list(FIREFOX_PROFILES_DIR.glob("*.default-release"))
        if not candidates:
            candidates = list(FIREFOX_PROFILES_DIR.glob("*.default"))
        if not candidates:
            print("Error: Could not auto-detect a profile. Available profiles:")
            list_profiles()
            sys.exit(1)
        if len(candidates) > 1:
            print("Warning: Multiple profiles found, using first match.")
        return candidates[0]

    path = FIREFOX_PROFILES_DIR / profile_name
    if not path.is_dir():
        print(f"Error: Profile not found at {path}")
        print("Available profiles:")
        list_profiles()
        sys.exit(1)
    return path


def list_profiles() -> None:
    if not FIREFOX_PROFILES_DIR.is_dir():
        print("  (Firefox profiles directory not found)")
        return
    for entry in sorted(FIREFOX_PROFILES_DIR.iterdir()):
        if entry.is_dir():
            print(f"  {entry.name}")


def extract_history_urls(profile_path: Path, days: int = 30) -> set[str]:
    db_path = profile_path / "places.sqlite"
    if not db_path.is_file():
        print(f"Error: places.sqlite not found in {profile_path}")
        sys.exit(1)

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    shutil.copy2(db_path, tmp_path)
    for ext in ("-wal", "-shm"):
        src = db_path.with_name(db_path.name + ext)
        if src.is_file():
            shutil.copy2(src, tmp_path.with_name(tmp_path.name + ext))

    urls: set[str] = set()
    try:
        conn = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
        cursor = conn.execute(
            """
            SELECT DISTINCT p.url
            FROM moz_places p
            JOIN moz_historyvisits v ON v.place_id = p.id
            WHERE v.visit_date > (strftime('%s', 'now', ? || ' days') * 1000000)
            """,
            (f"-{days}",),
        )
        for (url,) in cursor:
            urls.add(url)
        conn.close()
    finally:
        tmp_path.unlink()
        for ext in ("-wal", "-shm"):
            p = tmp_path.with_name(tmp_path.name + ext)
            if p.is_file():
                p.unlink()
    return urls


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit Firefox history for archivable pages.",
    )
    parser.add_argument(
        "--profile",
        "-P",
        help="Firefox profile folder name (e.g. 'abc123.default-release') or 'auto'",
        default="auto",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of history to consider (default: 30)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show per-filter breakdown and sample URLs",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        default="urls.txt",
        help="Output file for archivable URLs, NUL-separated (default: urls.txt)",
    )
    args = parser.parse_args()

    profile_path = resolve_profile(args.profile)
    print(f"Profile: {profile_path}")
    print(f"Period:  last {args.days} days\n")

    # --- Extract history ---
    print("Extracting history URLs...")
    raw_urls = extract_history_urls(profile_path, args.days)
    print(f"  Found {len(raw_urls):,} unique URLs in history\n")

    if not raw_urls:
        print("No history found for the given period.")
        sys.exit(0)

    # --- Filter pipeline ---
    print("Filtering & deduplicating...")
    filter_reasons: dict[str, list[str]] = {}
    archivable: set[str] = set()

    for url in raw_urls:
        reason = classify_url(url)
        if reason:
            filter_reasons.setdefault(reason, []).append(url)
        else:
            archivable.add(url)

    after_filter = len(archivable)

    # Normalize (strip tracking params + fragments + trailing slashes)
    normalized_map: dict[str, str] = {}
    for url in sorted(archivable):
        norm = normalize_url(url)
        if norm not in normalized_map:
            normalized_map[norm] = url

    tracking_dupes = after_filter - len(normalized_map)
    archivable = set(normalized_map.values())

    # Collapse pagination
    before_pagination = len(archivable)
    archivable = deduplicate_pagination(archivable)
    pagination_dupes = before_pagination - len(archivable)

    # --- Domain breakdown ---
    domain_counts: dict[str, int] = {}
    for url in archivable:
        domain = urlparse(url).netloc
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    top_domains = sorted(domain_counts.items(), key=lambda x: -x[1])[:20]

    # --- Results ---
    filtered_total = sum(len(v) for v in filter_reasons.values())

    print()
    print("=" * 62)
    print("RESULTS")
    print("=" * 62)
    print(f"  Raw history URLs:               {len(raw_urls):>8,}")
    print(f"  Filtered out:                   {filtered_total:>8,}")
    print(f"  Tracking param deduplication:    {tracking_dupes:>8,}")
    print(f"  Pagination deduplication:        {pagination_dupes:>8,}")
    print("                                  --------")
    print(f"  Archivable unique pages:        {len(archivable):>8,}")
    print("=" * 62)

    # Filter breakdown
    print(f"\nFilter breakdown ({filtered_total:,} removed):")
    for reason, urls in sorted(filter_reasons.items(), key=lambda x: -len(x[1])):
        print(f"  {len(urls):>6,}  {reason}")

    # Top domains
    print(f"\nTop 20 domains ({len(domain_counts):,} total):")
    for domain, count in top_domains:
        print(f"  {count:>6,}  {domain}")

    # Verbose output
    if args.verbose:
        print("\n--- Sample filtered URLs (5 per reason) ---")
        for reason, urls in sorted(filter_reasons.items(), key=lambda x: -len(x[1])):
            print(f"\n  [{reason}]")
            for url in sorted(urls)[:5]:
                print(f"    {url}")
            if len(urls) > 5:
                print(f"    ... and {len(urls) - 5} more")

        print("\n--- Sample archivable URLs (first 30) ---")
        for url in sorted(archivable)[:30]:
            print(f"  {url}")
        if len(archivable) > 30:
            print(f"  ... and {len(archivable) - 30} more")

    # Export
    with open(args.output, "w") as f:
        for url in sorted(archivable):
            f.write(url + "\n")

    print(f"\nExported {len(archivable):,} URLs to {args.output}")


if __name__ == "__main__":
    main()
