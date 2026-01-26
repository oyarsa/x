"""Filter s2orc_v2 dataset to extract full-text for NLP conference papers.

Two-phase approach:
1. Build corpus ID index by filtering `papers` dataset for target venues/years
2. Filter `s2orc_v2` dataset to extract only matching papers

Both phases use pipelining: download the next file while processing the current one.
"""

import asyncio
import gzip
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, NoReturn

import httpx
import typer
from tqdm import tqdm

from async_utils import download_file, get_filename_from_url

# === Constants ===

DATASETS_API = "https://api.semanticscholar.org/datasets/v1"

# Venue patterns to match NLP conferences in the papers dataset
# These are matched case-insensitively against the venue field
DEFAULT_VENUE_PATTERNS = [
    r"\bACL\b",
    r"\bEMNLP\b",
    r"\bNAACL\b",
    r"\bCOLING\b",
    r"\bEACL\b",
    r"\bAACL\b",
    r"\bCONLL\b",
    r"\bSemEval\b",
    r"\b\*SEM\b",
    r"\bTACL\b",
    r"\bCL\b",  # Computational Linguistics journal
]

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


def warn(message: str) -> None:
    """Print a warning message to stderr."""
    print(f"WARNING: {message}", file=sys.stderr, flush=True)


def die(message: str) -> NoReturn:
    """Print error message to stderr and exit."""
    err(message)
    sys.exit(1)


# === Data structures ===


@dataclass
class FilterStats:
    """Statistics for the filtering process."""

    files_processed: int = 0
    records_scanned: int = 0
    records_matched: int = 0
    bytes_downloaded: int = 0
    # Match breakdown
    matched_acl_only: int = 0
    matched_venue_only: int = 0
    matched_both: int = 0


@dataclass
class DatasetInfo:
    """Information about a dataset from the API."""

    name: str
    files: list[str] = field(default_factory=list[str])
    release_id: str = ""


# === API helpers ===


async def get_dataset_info(client: httpx.AsyncClient, name: str) -> DatasetInfo:
    """Fetch dataset file URLs from the Semantic Scholar API."""
    # Get latest release ID
    response = await client.get(f"{DATASETS_API}/release/latest")
    response.raise_for_status()
    release_id = response.json()["release_id"]

    # Get dataset files
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    headers = {"x-api-key": api_key} if api_key else {}

    response = await client.get(
        f"{DATASETS_API}/release/{release_id}/dataset/{name}/",
        headers=headers,
    )
    response.raise_for_status()
    data = response.json()

    return DatasetInfo(
        name=name,
        files=data.get("files", []),
        release_id=release_id,
    )


# === Processing helpers ===


@dataclass
class PapersFileResult:
    """Result of processing a papers file."""

    corpus_ids: set[int]
    acl_only: int = 0
    venue_only: int = 0
    both: int = 0


def process_papers_file(
    path: Path,
    year_range: tuple[int, int],
    venue_matcher: Callable[[str], bool],
    desc: str,
) -> PapersFileResult:
    """Process a papers file and return matching corpus IDs with match breakdown."""
    result = PapersFileResult(corpus_ids=set())
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in tqdm(f, desc=desc, leave=False):
            if line.strip():
                record = json.loads(line)
                match = paper_matches(record, year_range, venue_matcher)
                if match.matched:
                    corpus_id = record.get("corpusid")
                    if corpus_id:
                        result.corpus_ids.add(corpus_id)
                        if match.has_acl_id and match.has_venue_match:
                            result.both += 1
                        elif match.has_acl_id:
                            result.acl_only += 1
                        else:
                            result.venue_only += 1
    return result


def process_s2orc_file(
    path: Path,
    corpus_ids: set[int],
    out_file: gzip.GzipFile,
    desc: str,
) -> int:
    """Process an s2orc file and write matching records. Returns match count."""
    matches = 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in tqdm(f, desc=desc, leave=False):
            if line.strip():
                record = json.loads(line)
                corpus_id = record.get("corpusid")
                if corpus_id and corpus_id in corpus_ids:
                    out_file.write((json.dumps(record) + "\n").encode())
                    matches += 1
    return matches


# === Phase 1: Build corpus ID index ===


def make_venue_matcher(patterns: list[str]) -> Callable[[str], bool]:
    """Create a function that matches venue strings against patterns."""
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]

    def matcher(venue: str) -> bool:
        return any(p.search(venue) for p in compiled)

    return matcher


class MatchResult:
    """Result of paper matching, tracking which criteria matched."""

    __slots__ = ("has_acl_id", "has_venue_match", "matched")

    def __init__(
        self, matched: bool, has_acl_id: bool = False, has_venue_match: bool = False
    ) -> None:
        self.matched = matched
        self.has_acl_id = has_acl_id
        self.has_venue_match = has_venue_match


def paper_matches(
    record: dict[str, Any],
    year_range: tuple[int, int],
    venue_matcher: Callable[[str], bool],
) -> MatchResult:
    """Check if a paper matches criteria: has ACL ID OR matches venue pattern, within year range."""
    year = record.get("year")
    if not year or not (year_range[0] <= year <= year_range[1]):
        return MatchResult(False)

    # Check for ACL Anthology ID
    external_ids: dict[str, Any] = record.get("externalids") or {}
    has_acl_id = external_ids.get("ACL") is not None

    # Check venue pattern
    venue = record.get("venue", "") or ""
    has_venue_match = bool(venue and venue_matcher(venue))

    matched = has_acl_id or has_venue_match
    return MatchResult(matched, has_acl_id, has_venue_match)


def save_index(index_path: Path, corpus_ids: set[int]) -> None:
    """Save corpus IDs to file."""
    with open(index_path, "w") as f:
        f.writelines(f"{cid}\n" for cid in sorted(corpus_ids))


def save_metadata(metadata_path: Path, metadata: dict[str, Any]) -> None:
    """Save metadata to JSON file."""
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)


async def build_index(
    output_dir: Path,
    year_range: tuple[int, int],
    venue_patterns: list[str],
    limit_files: int | None = None,
    dry_run: bool = False,
) -> None:
    """Build corpus ID index by filtering papers dataset."""
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "corpus_ids.txt"
    metadata_path = output_dir / "index_metadata.json"

    venue_matcher = make_venue_matcher(venue_patterns)
    stats = FilterStats()
    corpus_ids: set[int] = set()

    async with httpx.AsyncClient() as client:
        log("Fetching papers dataset info...")
        dataset = await get_dataset_info(client, "papers")
        log(f"  Release: {dataset.release_id}")
        log(f"  Files: {len(dataset.files)}")

    files_to_process = dataset.files[:limit_files] if limit_files else dataset.files
    log(f"  Processing: {len(files_to_process)} files")

    if dry_run:
        log("\n[DRY RUN] Would download and process:")
        for i, url in enumerate(files_to_process, 1):
            filename = get_filename_from_url(url)
            log(f"  {i}. {filename}")
        log(f"\nOutput would be saved to: {index_path}")
        return

    log("")

    def process_file(path: Path, idx: int, total: int) -> int:
        """Process a downloaded file and update stats. Returns match count."""
        log(f"[{idx}/{total}] Processing...")
        result = process_papers_file(path, year_range, venue_matcher, "Filtering")
        corpus_ids.update(result.corpus_ids)
        stats.files_processed += 1
        stats.records_matched += len(result.corpus_ids)
        stats.matched_acl_only += result.acl_only
        stats.matched_venue_only += result.venue_only
        stats.matched_both += result.both
        log(
            f"[{idx}/{total}] "
            f"Found {len(result.corpus_ids):,} matches (total: {len(corpus_ids):,})"
        )
        return len(result.corpus_ids)

    # Pipeline: download next file while processing current
    pending_download: asyncio.Task[int] | None = None
    pending_path: Path | None = None
    pending_idx: int = 0

    for i, url in enumerate(files_to_process, 1):
        filename = get_filename_from_url(url)
        temp_path = output_dir / f".temp_{filename}"

        # Start download if not already pending
        if pending_download is None:
            log(f"[{i}/{len(files_to_process)}] Downloading {filename}...")
            pending_download = asyncio.create_task(
                download_file(url, temp_path, "Downloading")
            )
            pending_path = temp_path
            pending_idx = i
            continue

        # Wait for pending download
        try:
            bytes_downloaded = await pending_download
            stats.bytes_downloaded += bytes_downloaded
        except Exception as e:
            err(f"Download failed: {e}")
            if pending_path and pending_path.exists():
                pending_path.unlink()
            pending_download = None
            pending_path = None
            continue

        # Start next download
        log(f"[{i}/{len(files_to_process)}] Downloading {filename}...")
        next_download = asyncio.create_task(
            download_file(url, temp_path, "Downloading")
        )

        # Process completed file
        assert pending_path is not None
        try:
            process_file(pending_path, pending_idx, len(files_to_process))
        finally:
            if pending_path.exists():
                pending_path.unlink()

        pending_download = next_download
        pending_path = temp_path
        pending_idx = i

    # Process last file
    if pending_download is not None:
        try:
            bytes_downloaded = await pending_download
            stats.bytes_downloaded += bytes_downloaded
            assert pending_path is not None
            process_file(pending_path, pending_idx, len(files_to_process))
        finally:
            if pending_path and pending_path.exists():
                pending_path.unlink()

    # Save index
    log(f"\nSaving index with {len(corpus_ids):,} corpus IDs...")
    save_index(index_path, corpus_ids)

    # Save metadata
    metadata = {
        "release_id": dataset.release_id,
        "year_range": list(year_range),
        "venue_patterns": venue_patterns,
        "stats": {
            "files_processed": stats.files_processed,
            "records_scanned": stats.records_scanned,
            "records_matched": stats.records_matched,
            "matched_acl_only": stats.matched_acl_only,
            "matched_venue_only": stats.matched_venue_only,
            "matched_both": stats.matched_both,
            "bytes_downloaded": stats.bytes_downloaded,
        },
    }
    save_metadata(metadata_path, metadata)

    log(f"Index saved to {index_path}")
    log(f"  Files processed: {stats.files_processed}")
    log(f"  Records matched: {stats.records_matched:,}")
    log(f"    ACL ID only: {stats.matched_acl_only:,}")
    log(f"    Venue only: {stats.matched_venue_only:,}")
    log(f"    Both: {stats.matched_both:,}")


# === Phase 2: Filter s2orc_v2 ===


def load_corpus_ids(path: Path) -> set[int]:
    """Load corpus IDs from index file."""
    ids: set[int] = set()
    with open(path) as f:
        for line in f:
            if line.strip():
                ids.add(int(line.strip()))
    return ids


async def filter_s2orc(
    output_dir: Path,
    index_path: Path | None = None,
    limit_files: int | None = None,
    dry_run: bool = False,
) -> None:
    """Filter s2orc_v2 dataset to extract matching papers."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load or find index
    if index_path is None:
        index_path = output_dir / "corpus_ids.txt"

    # In dry-run mode, don't require the index to exist
    if not dry_run:
        if not index_path.exists():
            die(f"Index file not found: {index_path}\nRun 'build-index' first.")

        log(f"Loading corpus ID index from {index_path}...")
        corpus_ids = load_corpus_ids(index_path)
        log(f"  Loaded {len(corpus_ids):,} corpus IDs")

        if not corpus_ids:
            die("Index is empty. No papers to filter.")
    else:
        corpus_ids: set[int] = set()
        log(f"[DRY RUN] Would load index from: {index_path}")

    stats = FilterStats()
    output_path = output_dir / "s2orc_filtered.jsonl.gz"

    async with httpx.AsyncClient() as client:
        log("Fetching s2orc_v2 dataset info...")
        dataset = await get_dataset_info(client, "s2orc_v2")
        log(f"  Release: {dataset.release_id}")
        log(f"  Files: {len(dataset.files)}")

    files_to_process = dataset.files[:limit_files] if limit_files else dataset.files
    log(f"  Processing: {len(files_to_process)} files")

    if dry_run:
        log("\n[DRY RUN] Would download and process:")
        for i, url in enumerate(files_to_process, 1):
            filename = get_filename_from_url(url)
            log(f"  {i}. {filename}")
        log(f"\nOutput would be saved to: {output_path}")
        return

    log("")

    with gzip.open(output_path, "wb") as out_file:
        # Pipeline: download next file while processing current
        pending_download: asyncio.Task[int] | None = None
        pending_path: Path | None = None
        pending_idx: int = 0

        for i, url in enumerate(files_to_process, 1):
            filename = get_filename_from_url(url)
            temp_path = output_dir / f".temp_{filename}"

            # Start download if not already pending
            if pending_download is None:
                log(f"[{i}/{len(files_to_process)}] Downloading {filename}...")
                pending_download = asyncio.create_task(
                    download_file(url, temp_path, "Downloading")
                )
                pending_path = temp_path
                pending_idx = i
                continue

            # Wait for pending download
            try:
                bytes_downloaded = await pending_download
                stats.bytes_downloaded += bytes_downloaded
            except Exception as e:
                err(f"Download failed: {e}")
                if pending_path and pending_path.exists():
                    pending_path.unlink()
                pending_download = None
                pending_path = None
                continue

            # Start next download
            log(f"[{i}/{len(files_to_process)}] Downloading {filename}...")
            next_download = asyncio.create_task(
                download_file(url, temp_path, "Downloading")
            )

            # Process completed file
            assert pending_path is not None
            try:
                log(f"[{pending_idx}/{len(files_to_process)}] Processing...")
                file_matches = process_s2orc_file(
                    pending_path, corpus_ids, out_file, "Filtering"
                )
                stats.files_processed += 1
                stats.records_matched += file_matches
                log(
                    f"[{pending_idx}/{len(files_to_process)}] "
                    f"Found {file_matches:,} matches (total: {stats.records_matched:,})"
                )
            finally:
                if pending_path.exists():
                    pending_path.unlink()

            pending_download = next_download
            pending_path = temp_path
            pending_idx = i

        # Process last file
        if pending_download is not None:
            try:
                bytes_downloaded = await pending_download
                stats.bytes_downloaded += bytes_downloaded
                assert pending_path is not None
                log(f"[{pending_idx}/{len(files_to_process)}] Processing...")
                file_matches = process_s2orc_file(
                    pending_path, corpus_ids, out_file, "Filtering"
                )
                stats.files_processed += 1
                stats.records_matched += file_matches
                log(
                    f"[{pending_idx}/{len(files_to_process)}] "
                    f"Found {file_matches:,} matches (total: {stats.records_matched:,})"
                )
            finally:
                if pending_path and pending_path.exists():
                    pending_path.unlink()

    # Save stats
    stats_path = output_dir / "filter_stats.json"
    save_metadata(
        stats_path,
        {
            "release_id": dataset.release_id,
            "index_path": str(index_path),
            "index_size": len(corpus_ids),
            "stats": {
                "files_processed": stats.files_processed,
                "records_scanned": stats.records_scanned,
                "records_matched": stats.records_matched,
                "bytes_downloaded": stats.bytes_downloaded,
            },
        },
    )

    log("\nFiltering complete!")
    log(f"  Output: {output_path}")
    log(f"  Files processed: {stats.files_processed}")
    log(f"  Records matched: {stats.records_matched:,}")
    coverage = stats.records_matched / len(corpus_ids) * 100 if corpus_ids else 0
    log(f"  Coverage: {coverage:.1f}% of index")


# === CLI Commands ===


@app.command(name="build-index")
def cmd_build_index(
    output_dir: Annotated[
        Path, typer.Argument(help="Directory to save the corpus ID index.")
    ],
    start_year: Annotated[
        int, typer.Option("--start-year", "-s", help="Start year (inclusive).")
    ] = 2010,
    end_year: Annotated[
        int, typer.Option("--end-year", "-e", help="End year (inclusive).")
    ] = 2025,
    venues: Annotated[
        list[str] | None,
        typer.Option(
            "--venue",
            "-v",
            help="Additional venue regex pattern to match. Can be repeated. "
            "Papers are matched if they have an ACL Anthology ID OR match a venue pattern.",
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit", "-n", help="Limit number of files to process (for testing)."
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
) -> None:
    """Build corpus ID index by filtering the papers dataset.

    Scans the Semantic Scholar papers dataset and extracts corpus IDs
    for papers that have an ACL Anthology ID OR match venue patterns,
    within the specified year range.

    Requires SEMANTIC_SCHOLAR_API_KEY environment variable.
    """
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        die("SEMANTIC_SCHOLAR_API_KEY environment variable is required.")

    venue_patterns = list(venues) if venues else DEFAULT_VENUE_PATTERNS
    year_range = (start_year, end_year)

    log("=== Building corpus ID index ===")
    log(f"Year range: {start_year}-{end_year}")
    log(f"Venue patterns: {venue_patterns}")
    log("Filter: ACL Anthology ID OR venue pattern match")
    log("")

    asyncio.run(build_index(output_dir, year_range, venue_patterns, limit, dry_run))


@app.command(name="filter")
def cmd_filter(
    output_dir: Annotated[
        Path,
        typer.Argument(help="Directory for output (should contain corpus_ids.txt)."),
    ],
    index: Annotated[
        Path | None,
        typer.Option(
            "--index",
            "-i",
            help="Path to corpus ID index file. Defaults to output_dir/corpus_ids.txt.",
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit", "-n", help="Limit number of files to process (for testing)."
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
) -> None:
    """Filter s2orc_v2 dataset to extract full-text for indexed papers.

    Uses a pre-built corpus ID index to filter the s2orc_v2 dataset,
    extracting only papers that match the index.

    Requires SEMANTIC_SCHOLAR_API_KEY environment variable.
    """
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        die("SEMANTIC_SCHOLAR_API_KEY environment variable is required.")

    log("=== Filtering s2orc_v2 dataset ===")
    log("")

    asyncio.run(filter_s2orc(output_dir, index, limit, dry_run))


@app.command(name="run")
def cmd_run(
    output_dir: Annotated[Path, typer.Argument(help="Directory for all output files.")],
    start_year: Annotated[
        int, typer.Option("--start-year", "-s", help="Start year (inclusive).")
    ] = 2010,
    end_year: Annotated[
        int, typer.Option("--end-year", "-e", help="End year (inclusive).")
    ] = 2025,
    venues: Annotated[
        list[str] | None,
        typer.Option(
            "--venue",
            "-v",
            help="Additional venue regex pattern to match. Can be repeated. "
            "Papers are matched if they have an ACL Anthology ID OR match a venue pattern.",
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit", "-n", help="Limit number of files per phase (for testing)."
        ),
    ] = None,
    skip_index: Annotated[
        bool,
        typer.Option("--skip-index", help="Skip index building (use existing index)."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
) -> None:
    """Run the full pipeline: build index, then filter s2orc_v2.

    This is a convenience command that runs both phases in sequence.
    Papers are matched if they have an ACL Anthology ID OR match venue patterns.

    Requires SEMANTIC_SCHOLAR_API_KEY environment variable.
    """
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        die("SEMANTIC_SCHOLAR_API_KEY environment variable is required.")

    venue_patterns = list(venues) if venues else DEFAULT_VENUE_PATTERNS
    year_range = (start_year, end_year)

    log("=== Running full pipeline ===")
    log(f"Year range: {start_year}-{end_year}")
    log(f"Venue patterns: {venue_patterns}")
    log("Filter: ACL Anthology ID OR venue pattern match")
    log("")

    if not skip_index:
        log("--- Phase 1: Building corpus ID index ---")
        log("")
        asyncio.run(build_index(output_dir, year_range, venue_patterns, limit, dry_run))
        log("")

    log("--- Phase 2: Filtering s2orc_v2 ---")
    log("")
    asyncio.run(filter_s2orc(output_dir, None, limit, dry_run))


@app.command(name="stats")
def cmd_stats(
    output_dir: Annotated[
        Path, typer.Argument(help="Directory containing filter output.")
    ],
) -> None:
    """Show statistics about the filtered dataset."""
    index_path = output_dir / "corpus_ids.txt"
    output_path = output_dir / "s2orc_filtered.jsonl.gz"
    stats_path = output_dir / "filter_stats.json"

    if index_path.exists():
        corpus_ids = load_corpus_ids(index_path)
        log(f"Index: {len(corpus_ids):,} corpus IDs")

    if stats_path.exists():
        with open(stats_path) as f:
            stats = json.load(f)
        log("Filter stats:")
        log(f"  Release: {stats.get('release_id', 'unknown')}")
        log(f"  Files processed: {stats['stats']['files_processed']}")
        log(f"  Records scanned: {stats['stats']['records_scanned']:,}")
        log(f"  Records matched: {stats['stats']['records_matched']:,}")
        if stats.get("index_size"):
            coverage = stats["stats"]["records_matched"] / stats["index_size"] * 100
            log(f"  Coverage: {coverage:.1f}%")

    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        log(f"Output file: {output_path}")
        log(f"  Size: {size_mb:.1f} MB")

        # Count records
        log("  Counting records...")
        count = 0
        with gzip.open(output_path, "rt") as f:
            for _ in f:
                count += 1
        log(f"  Records: {count:,}")


if __name__ == "__main__":
    app()
