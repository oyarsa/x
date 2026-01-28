"""Download PDFs from ACL Anthology and ArXiv.

Reads paper metadata and downloads PDFs using external IDs.
Supports concurrent downloads with rate limiting and resume.
"""

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, NoReturn

import aiofiles
import httpx
import typer
from tqdm import tqdm

# Rate limits (requests per second)
# ArXiv: 4 req/s with 1s sleep between bursts - we'll use 3 req/s to be safe
# ACL Anthology: No explicit limit, be conservative at 2 req/s
RATE_LIMIT_ARXIV = 3.0
RATE_LIMIT_ACL = 2.0

# URL patterns
ACL_PDF_URL = "https://aclanthology.org/{acl_id}.pdf"
ARXIV_PDF_URL = "https://export.arxiv.org/pdf/{arxiv_id}.pdf"

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


def log(message: str) -> None:
    """Print a log message."""
    print(message, flush=True)


def err(message: str) -> None:
    """Print an error message to stderr."""
    print(f"ERROR: {message}", file=sys.stderr, flush=True)


def die(message: str) -> NoReturn:
    """Print error message to stderr and exit."""
    err(message)
    sys.exit(1)


@dataclass
class DownloadStats:
    """Statistics for download process."""

    total: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""

    def __init__(self, rate: float) -> None:
        self.rate = rate
        self.interval = 1.0 / rate
        self.lock = asyncio.Lock()
        self.last_request = 0.0

    async def acquire(self) -> None:
        """Wait until a request can be made within rate limit."""
        async with self.lock:
            now = asyncio.get_event_loop().time()
            wait_time = self.last_request + self.interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_request = asyncio.get_event_loop().time()


async def load_downloaded(path: Path) -> set[str]:
    """Load set of downloaded paper IDs."""
    if not path.exists():
        return set()
    async with aiofiles.open(path) as f:
        content = await f.read()
        return {line.strip() for line in content.splitlines() if line.strip()}


async def append_downloaded(path: Path, paper_id: str) -> None:
    """Append a paper ID to the downloaded list."""
    async with aiofiles.open(path, "a") as f:
        await f.write(f"{paper_id}\n")


async def download_pdf(
    client: httpx.AsyncClient,
    url: str,
    output_path: Path,
    rate_limiter: RateLimiter,
) -> bool:
    """Download a PDF file. Returns True on success.

    Uses atomic write (temp file + rename) to avoid partial downloads.
    Validates PDF magic bytes before accepting.
    """
    await rate_limiter.acquire()

    temp_path = output_path.with_suffix(".pdf.part")
    try:
        response = await client.get(url, follow_redirects=True)
        if response.status_code == 200:
            content = response.content
            # Validate PDF magic bytes (%PDF)
            if len(content) < 4 or content[:4] != b"%PDF":
                return False
            # Write to temp file first
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(content)
            # Atomic rename
            temp_path.rename(output_path)
            return True
        else:
            return False
    except Exception:
        # Clean up partial file on error
        if temp_path.exists():
            temp_path.unlink()
        return False


def get_pdf_url(record: dict[str, Any], source: str) -> tuple[str | None, str | None]:
    """Get PDF URL and identifier for a paper from specified source.

    Returns (url, identifier) or (None, None) if not available.
    """
    external_ids: dict[str, Any] = record.get("externalids", {}) or {}

    if source == "acl":
        acl_id: str | None = external_ids.get("ACL")
        if acl_id:
            return ACL_PDF_URL.format(acl_id=acl_id), f"acl:{acl_id}"
    elif source == "arxiv":
        arxiv_id: str | None = external_ids.get("ArXiv")
        if arxiv_id:
            return ARXIV_PDF_URL.format(arxiv_id=arxiv_id), f"arxiv:{arxiv_id}"

    return None, None


async def download_from_source(
    metadata_path: Path,
    output_dir: Path,
    source: str,
    rate_limit: float,
    max_concurrent: int,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """Download PDFs from a specific source."""
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded_path = output_dir / f"downloaded_{source}.txt"

    # Load metadata and filter to papers with this source
    log(f"Loading metadata from {metadata_path}...")
    papers: list[tuple[str, str, int]] = []  # (url, identifier, corpus_id)

    async with aiofiles.open(metadata_path, encoding="utf-8") as f:
        async for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            url, identifier = get_pdf_url(record, source)
            if url and identifier:
                corpus_id = record.get("corpusid")
                papers.append((url, identifier, corpus_id))

    log(f"  Found {len(papers):,} papers with {source.upper()} IDs")

    # Load already downloaded
    downloaded = await load_downloaded(downloaded_path)
    if downloaded:
        log(f"  Already downloaded: {len(downloaded):,}")

    # Filter out already downloaded
    remaining = [
        (url, ident, cid) for url, ident, cid in papers if ident not in downloaded
    ]
    log(f"  Remaining: {len(remaining):,}")

    if limit:
        remaining = remaining[:limit]
        log(f"  Limited to: {len(remaining):,}")

    if dry_run:
        log(f"\n[DRY RUN] Would download {len(remaining):,} PDFs to {output_dir}")
        for url, ident, _ in remaining[:10]:
            log(f"  {ident}: {url}")
        if len(remaining) > 10:
            log(f"  ... and {len(remaining) - 10} more")
        return

    if not remaining:
        log("\nAll PDFs already downloaded!")
        return

    log(f"\nDownloading {len(remaining):,} PDFs...")
    log(f"  Rate limit: {rate_limit} req/s")
    log(f"  Concurrent: {max_concurrent}")
    log("")

    stats = DownloadStats(total=len(remaining))
    rate_limiter = RateLimiter(rate_limit)
    semaphore = asyncio.Semaphore(max_concurrent)
    progress = tqdm(total=len(remaining), desc=f"Downloading ({source})")

    async def worker(url: str, identifier: str, corpus_id: int) -> None:
        async with semaphore:
            # Determine output filename
            # Use corpus_id as filename for consistency
            pdf_path = output_dir / f"{corpus_id}.pdf"

            if pdf_path.exists():
                stats.skipped += 1
                await append_downloaded(downloaded_path, identifier)
            else:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=30, read=60, write=30, pool=30)
                ) as client:
                    success = await download_pdf(client, url, pdf_path, rate_limiter)
                    if success:
                        stats.downloaded += 1
                        await append_downloaded(downloaded_path, identifier)
                    else:
                        stats.failed += 1

            progress.update(1)

    # Process in batches to manage memory
    batch_size = 1000
    for i in range(0, len(remaining), batch_size):
        batch = remaining[i : i + batch_size]
        tasks = [
            asyncio.create_task(worker(url, ident, cid)) for url, ident, cid in batch
        ]
        await asyncio.gather(*tasks)

    progress.close()

    log("\nDownload complete!")
    log(f"  Downloaded: {stats.downloaded:,}")
    log(f"  Skipped (exists): {stats.skipped:,}")
    log(f"  Failed: {stats.failed:,}")


@app.command(name="acl")
def cmd_acl(
    data_dir: Annotated[
        Path, typer.Argument(help="Directory containing papers/metadata.jsonl")
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for PDFs."),
    ] = None,
    concurrent: Annotated[
        int,
        typer.Option("--concurrent", "-c", help="Number of concurrent downloads."),
    ] = 5,
    rate: Annotated[
        float,
        typer.Option("--rate", "-r", help="Requests per second."),
    ] = RATE_LIMIT_ACL,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-n", help="Limit number of downloads (for testing)."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
) -> None:
    """Download PDFs from ACL Anthology.

    Downloads papers that have an ACL Anthology ID in their metadata.
    PDFs are saved as {corpus_id}.pdf in the output directory.
    """
    metadata_path = data_dir / "papers" / "metadata.jsonl"
    if not metadata_path.exists():
        die(f"Metadata not found: {metadata_path}")

    output_dir = output or data_dir / "pdfs" / "acl"

    log("=== Downloading PDFs from ACL Anthology ===")
    log("Source: https://aclanthology.org/")
    log("")

    asyncio.run(
        download_from_source(
            metadata_path, output_dir, "acl", rate, concurrent, limit, dry_run
        )
    )


@app.command(name="arxiv")
def cmd_arxiv(
    data_dir: Annotated[
        Path, typer.Argument(help="Directory containing papers/metadata.jsonl")
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for PDFs."),
    ] = None,
    concurrent: Annotated[
        int,
        typer.Option("--concurrent", "-c", help="Number of concurrent downloads."),
    ] = 5,
    rate: Annotated[
        float,
        typer.Option("--rate", "-r", help="Requests per second."),
    ] = RATE_LIMIT_ARXIV,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-n", help="Limit number of downloads (for testing)."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
) -> None:
    """Download PDFs from ArXiv.

    Downloads papers that have an ArXiv ID in their metadata.
    Uses export.arxiv.org as recommended for programmatic access.
    PDFs are saved as {corpus_id}.pdf in the output directory.
    """
    metadata_path = data_dir / "papers" / "metadata.jsonl"
    if not metadata_path.exists():
        die(f"Metadata not found: {metadata_path}")

    output_dir = output or data_dir / "pdfs" / "arxiv"

    log("=== Downloading PDFs from ArXiv ===")
    log("Source: https://export.arxiv.org/")
    log("")

    asyncio.run(
        download_from_source(
            metadata_path, output_dir, "arxiv", rate, concurrent, limit, dry_run
        )
    )


@app.command(name="all")
def cmd_all(
    data_dir: Annotated[
        Path, typer.Argument(help="Directory containing papers/metadata.jsonl")
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Base output directory for PDFs."),
    ] = None,
    concurrent: Annotated[
        int,
        typer.Option("--concurrent", "-c", help="Number of concurrent downloads."),
    ] = 5,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-n", help="Limit number of downloads per source."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
) -> None:
    """Download PDFs from all sources (ACL Anthology + ArXiv) in parallel.

    Downloads from both sources simultaneously since they have
    independent rate limits.
    """
    metadata_path = data_dir / "papers" / "metadata.jsonl"
    if not metadata_path.exists():
        die(f"Metadata not found: {metadata_path}")

    base_output = output or data_dir / "pdfs"

    log("=== Downloading PDFs from all sources (parallel) ===")
    log("")

    async def download_all() -> None:
        await asyncio.gather(
            download_from_source(
                metadata_path,
                base_output / "acl",
                "acl",
                RATE_LIMIT_ACL,
                concurrent,
                limit,
                dry_run,
            ),
            download_from_source(
                metadata_path,
                base_output / "arxiv",
                "arxiv",
                RATE_LIMIT_ARXIV,
                concurrent,
                limit,
                dry_run,
            ),
        )

    asyncio.run(download_all())


@app.command(name="stats")
def cmd_stats(
    data_dir: Annotated[
        Path, typer.Argument(help="Directory containing papers/metadata.jsonl")
    ],
) -> None:
    """Show PDF download statistics."""
    metadata_path = data_dir / "papers" / "metadata.jsonl"
    if not metadata_path.exists():
        die(f"Metadata not found: {metadata_path}")

    acl_count = 0
    arxiv_count = 0
    both_count = 0
    neither_count = 0

    with open(metadata_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record: dict[str, Any] = json.loads(line)
            external_ids: dict[str, Any] = record.get("externalids", {}) or {}
            has_acl = external_ids.get("ACL") is not None
            has_arxiv = external_ids.get("ArXiv") is not None

            if has_acl and has_arxiv:
                both_count += 1
            elif has_acl:
                acl_count += 1
            elif has_arxiv:
                arxiv_count += 1
            else:
                neither_count += 1

    total = acl_count + arxiv_count + both_count + neither_count
    total_downloadable = acl_count + arxiv_count + both_count

    log("=== PDF availability ===")
    log(f"Total papers: {total:,}")
    log("")
    log(f"ACL Anthology only: {acl_count:,}")
    log(f"ArXiv only: {arxiv_count:,}")
    log(f"Both ACL + ArXiv: {both_count:,}")
    log(f"Neither (no PDF source): {neither_count:,}")
    log("")
    log(
        f"Total downloadable: {total_downloadable:,} ({total_downloadable / total * 100:.1f}%)"
    )

    # Check download progress
    pdfs_dir = data_dir / "pdfs"
    for source in ["acl", "arxiv"]:
        downloaded_path = pdfs_dir / source / f"downloaded_{source}.txt"
        if downloaded_path.exists():
            with open(downloaded_path) as f:
                count = sum(1 for _ in f)
            log(f"  Downloaded from {source}: {count:,}")


if __name__ == "__main__":
    app()
