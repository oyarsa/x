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
from datetime import UTC, datetime
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


def backup_files(files: list[Path], backup_suffix: str = ".bak") -> list[Path]:
    """Back up files before deleting. Returns list of backed up files."""
    backed_up: list[Path] = []
    for p in files:
        if p.exists():
            backup_path = p.with_suffix(p.suffix + backup_suffix)
            # If backup already exists, add timestamp
            if backup_path.exists():
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                backup_path = p.with_suffix(f"{p.suffix}.{timestamp}{backup_suffix}")
            p.rename(backup_path)
            log(f"  Backed up: {p.name} -> {backup_path.name}")
            backed_up.append(backup_path)
    return backed_up


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


async def save_index(index_path: Path, corpus_ids: set[int]) -> None:
    """Save corpus IDs to file (overwrites)."""
    await asyncio.to_thread(
        _write_lines, index_path, [f"{cid}\n" for cid in sorted(corpus_ids)]
    )


async def append_corpus_ids(index_path: Path, corpus_ids: set[int]) -> None:
    """Append corpus IDs to file."""
    await asyncio.to_thread(
        _append_lines, index_path, [f"{cid}\n" for cid in sorted(corpus_ids)]
    )


async def load_processed_files(path: Path) -> set[str]:
    """Load set of processed filenames."""
    if not path.exists():
        return set()
    return await asyncio.to_thread(_read_lines_as_set, path)


async def append_processed_file(path: Path, filename: str) -> None:
    """Append a filename to the processed files list."""
    await asyncio.to_thread(_append_lines, path, [f"{filename}\n"])


def _write_lines(path: Path, lines: list[str]) -> None:
    with open(path, "w") as f:
        f.writelines(lines)


def _append_lines(path: Path, lines: list[str]) -> None:
    with open(path, "a") as f:
        f.writelines(lines)


def _read_lines_as_set(path: Path) -> set[str]:
    with open(path) as f:
        return {line for line_ in f if (line := line_.strip())}


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
    force: bool = False,
    max_concurrent: int = 1,
) -> None:
    """Build corpus ID index by filtering papers dataset. Supports resume."""
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "corpus_ids.txt"
    metadata_path = output_dir / "index_metadata.json"
    processed_path = output_dir / "processed_papers.txt"

    venue_matcher = make_venue_matcher(venue_patterns)
    stats = FilterStats()

    # Clear previous state if force flag is set
    if force:
        log("Force mode: backing up previous state...")
        backup_files([index_path, metadata_path, processed_path])

    # Load existing state for resume
    processed_files = await load_processed_files(processed_path)
    corpus_ids: set[int]
    if processed_files:
        log(f"Resuming: {len(processed_files)} files already processed")
        corpus_ids = load_corpus_ids(index_path) if index_path.exists() else set()
        log(f"  Loaded {len(corpus_ids):,} existing corpus IDs")
    else:
        corpus_ids = set()
        # Clear index file if starting fresh
        if index_path.exists():
            index_path.unlink()

    async with httpx.AsyncClient() as client:
        log("Fetching papers dataset info...")
        dataset = await get_dataset_info(client, "papers")
        log(f"  Release: {dataset.release_id}")
        log(f"  Files: {len(dataset.files)}")

    files_to_process = dataset.files[:limit_files] if limit_files else dataset.files
    log(f"  Processing: {len(files_to_process)} files")

    # Filter out already processed files
    files_with_names = [(url, get_filename_from_url(url)) for url in files_to_process]
    remaining_files = [
        (url, name) for url, name in files_with_names if name not in processed_files
    ]
    if len(remaining_files) < len(files_to_process):
        log(
            f"  Skipping: {len(files_to_process) - len(remaining_files)} already processed"
        )
        log(f"  Remaining: {len(remaining_files)} files")

    if dry_run:
        log("\n[DRY RUN] Would download and process:")
        for i, (_url, name) in enumerate(remaining_files, 1):
            log(f"  {i}. {name}")
        log(f"\nOutput would be saved to: {index_path}")
        return

    if not remaining_files:
        log("\nAll files already processed!")
        log(f"Index contains {len(corpus_ids):,} corpus IDs")
        return

    log(f"  Concurrent downloads: {max_concurrent}")
    log("")

    total = len(remaining_files)
    # Lock for thread-safe updates to shared state
    state_lock = asyncio.Lock()

    async def process_file_async(
        path: Path, filename: str, idx: int
    ) -> PapersFileResult:
        """Process a downloaded file in a thread pool. Returns result."""
        result = await asyncio.to_thread(
            process_papers_file, path, year_range, venue_matcher, f"[{idx}/{total}]"
        )
        async with state_lock:
            corpus_ids.update(result.corpus_ids)
            stats.files_processed += 1
            stats.records_matched += len(result.corpus_ids)
            stats.matched_acl_only += result.acl_only
            stats.matched_venue_only += result.venue_only
            stats.matched_both += result.both
            current_total = len(corpus_ids)
        log(
            f"[{idx}/{total}] "
            f"Found {len(result.corpus_ids):,} matches (total: {current_total:,})"
        )
        return result

    async def download_and_process(url: str, filename: str, idx: int) -> None:
        """Download a file, process it, and save results."""
        temp_path = output_dir / f".temp_{filename}"
        try:
            log(f"[{idx}/{total}] Downloading {filename}...")
            bytes_downloaded = await download_file(url, temp_path, f"[{idx}/{total}]")
            async with state_lock:
                stats.bytes_downloaded += bytes_downloaded

            log(f"[{idx}/{total}] Processing {filename}...")
            result = await process_file_async(temp_path, filename, idx)

            # Save incrementally (with lock to prevent interleaved writes)
            async with state_lock:
                await append_corpus_ids(index_path, result.corpus_ids)
                await append_processed_file(processed_path, filename)
        except Exception as e:
            err(f"[{idx}/{total}] Failed {filename}: {e}")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    # Process files with limited concurrency
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_download_and_process(url: str, filename: str, idx: int) -> None:
        async with semaphore:
            await download_and_process(url, filename, idx)

    # Launch all tasks (semaphore limits actual concurrency)
    tasks = [
        asyncio.create_task(bounded_download_and_process(url, filename, i))
        for i, (url, filename) in enumerate(remaining_files, 1)
    ]
    await asyncio.gather(*tasks)

    # Save metadata (overwrites with final stats)
    metadata = {
        "release_id": dataset.release_id,
        "year_range": list(year_range),
        "venue_patterns": venue_patterns,
        "stats": {
            "files_processed": stats.files_processed + len(processed_files),
            "records_scanned": stats.records_scanned,
            "records_matched": len(corpus_ids),
            "matched_acl_only": stats.matched_acl_only,
            "matched_venue_only": stats.matched_venue_only,
            "matched_both": stats.matched_both,
            "bytes_downloaded": stats.bytes_downloaded,
        },
    }
    save_metadata(metadata_path, metadata)

    log(f"\nIndex complete: {len(corpus_ids):,} corpus IDs")
    log(f"  Files processed this run: {stats.files_processed}")
    log(f"  Total files processed: {stats.files_processed + len(processed_files)}")
    log(f"  Matches this run: {stats.records_matched:,}")
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
    force: bool = False,
    max_concurrent: int = 1,
) -> None:
    """Filter s2orc_v2 dataset to extract matching papers. Supports resume."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load or find index
    if index_path is None:
        index_path = output_dir / "corpus_ids.txt"

    processed_path = output_dir / "processed_s2orc.txt"
    output_path = output_dir / "s2orc_filtered.jsonl.gz"
    stats_path = output_dir / "filter_stats.json"

    # Clear previous state if force flag is set
    if force:
        log("Force mode: backing up previous state...")
        backup_files([processed_path, output_path, stats_path])

    # In dry-run mode, don't require the index to exist
    corpus_ids: set[int]
    if not dry_run:
        if not index_path.exists():
            die(f"Index file not found: {index_path}\nRun 'build-index' first.")

        log(f"Loading corpus ID index from {index_path}...")
        corpus_ids = load_corpus_ids(index_path)
        log(f"  Loaded {len(corpus_ids):,} corpus IDs")

        if not corpus_ids:
            die("Index is empty. No papers to filter.")
    else:
        corpus_ids = set()
        log(f"[DRY RUN] Would load index from: {index_path}")

    # Load existing state for resume
    processed_files = await load_processed_files(processed_path)
    prior_matches = 0
    if processed_files:
        log(f"Resuming: {len(processed_files)} files already processed")
        # Count existing matches
        if output_path.exists():
            with gzip.open(output_path, "rt") as f:
                prior_matches = sum(1 for _ in f)
            log(f"  Existing matches: {prior_matches:,}")

    stats = FilterStats()
    stats.records_matched = prior_matches  # Start from existing count

    async with httpx.AsyncClient() as client:
        log("Fetching s2orc_v2 dataset info...")
        dataset = await get_dataset_info(client, "s2orc_v2")
        log(f"  Release: {dataset.release_id}")
        log(f"  Files: {len(dataset.files)}")

    files_to_process = dataset.files[:limit_files] if limit_files else dataset.files
    log(f"  Processing: {len(files_to_process)} files")

    # Filter out already processed files
    files_with_names = [(url, get_filename_from_url(url)) for url in files_to_process]
    remaining_files = [
        (url, name) for url, name in files_with_names if name not in processed_files
    ]
    if len(remaining_files) < len(files_to_process):
        log(
            f"  Skipping: {len(files_to_process) - len(remaining_files)} already processed"
        )
        log(f"  Remaining: {len(remaining_files)} files")

    if dry_run:
        log("\n[DRY RUN] Would download and process:")
        for i, (_url, name) in enumerate(remaining_files, 1):
            log(f"  {i}. {name}")
        log(f"\nOutput would be saved to: {output_path}")
        return

    if not remaining_files:
        log("\nAll files already processed!")
        log(f"  Total matches: {prior_matches:,}")
        coverage = prior_matches / len(corpus_ids) * 100 if corpus_ids else 0
        log(f"  Coverage: {coverage:.1f}% of index")
        return

    log(f"  Concurrent downloads: {max_concurrent}")
    log("")

    total = len(remaining_files)
    # Lock for thread-safe updates to shared state and output file
    state_lock = asyncio.Lock()

    # Open in append mode if resuming, write mode if starting fresh
    open_mode = "ab" if processed_files else "wb"

    with gzip.open(output_path, open_mode) as out_file:

        async def download_and_process(url: str, filename: str, idx: int) -> None:
            """Download a file, process it, and save results."""
            nonlocal stats
            temp_path = output_dir / f".temp_{filename}"
            try:
                log(f"[{idx}/{total}] Downloading {filename}...")
                bytes_downloaded = await download_file(
                    url, temp_path, f"[{idx}/{total}]"
                )

                log(f"[{idx}/{total}] Processing {filename}...")
                # Process in thread pool, but write to output with lock
                file_matches = 0
                matched_records: list[str] = []

                def process_and_collect() -> int:
                    nonlocal matched_records
                    matches = 0
                    with gzip.open(temp_path, "rt", encoding="utf-8") as f:
                        for line in tqdm(f, desc=f"[{idx}/{total}]", leave=False):
                            if line.strip():
                                record = json.loads(line)
                                corpus_id = record.get("corpusid")
                                if corpus_id and corpus_id in corpus_ids:
                                    matched_records.append(json.dumps(record) + "\n")
                                    matches += 1
                    return matches

                file_matches = await asyncio.to_thread(process_and_collect)

                # Write results with lock to prevent interleaved output
                async with state_lock:
                    for record_line in matched_records:
                        out_file.write(record_line.encode())
                    stats.bytes_downloaded += bytes_downloaded
                    stats.files_processed += 1
                    stats.records_matched += file_matches
                    current_total = stats.records_matched
                    await append_processed_file(processed_path, filename)

                log(
                    f"[{idx}/{total}] "
                    f"Found {file_matches:,} matches (total: {current_total:,})"
                )
            except Exception as e:
                err(f"[{idx}/{total}] Failed {filename}: {e}")
            finally:
                if temp_path.exists():
                    temp_path.unlink()

        # Process files with limited concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_download_and_process(
            url: str, filename: str, idx: int
        ) -> None:
            async with semaphore:
                await download_and_process(url, filename, idx)

        # Launch all tasks (semaphore limits actual concurrency)
        tasks = [
            asyncio.create_task(bounded_download_and_process(url, filename, i))
            for i, (url, filename) in enumerate(remaining_files, 1)
        ]
        await asyncio.gather(*tasks)

    # Save stats
    stats_path = output_dir / "filter_stats.json"
    save_metadata(
        stats_path,
        {
            "release_id": dataset.release_id,
            "index_path": str(index_path),
            "index_size": len(corpus_ids),
            "stats": {
                "files_processed": stats.files_processed + len(processed_files),
                "records_scanned": stats.records_scanned,
                "records_matched": stats.records_matched,
                "bytes_downloaded": stats.bytes_downloaded,
            },
        },
    )

    log("\nFiltering complete!")
    log(f"  Output: {output_path}")
    log(f"  Files processed this run: {stats.files_processed}")
    log(f"  Total files processed: {stats.files_processed + len(processed_files)}")
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
    concurrent: Annotated[
        int,
        typer.Option("--concurrent", "-c", help="Number of concurrent downloads."),
    ] = 10,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Ignore previous state and start fresh."),
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

    asyncio.run(
        build_index(
            output_dir, year_range, venue_patterns, limit, dry_run, force, concurrent
        )
    )


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
    concurrent: Annotated[
        int,
        typer.Option("--concurrent", "-c", help="Number of concurrent downloads."),
    ] = 10,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Ignore previous state and start fresh."),
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

    asyncio.run(filter_s2orc(output_dir, index, limit, dry_run, force, concurrent))


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
            "Papers are matched if they have an ACL Anthology ID OR match venue patterns.",
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit", "-n", help="Limit number of files per phase (for testing)."
        ),
    ] = None,
    concurrent: Annotated[
        int,
        typer.Option("--concurrent", "-c", help="Number of concurrent downloads."),
    ] = 10,
    skip_index: Annotated[
        bool,
        typer.Option("--skip-index", help="Skip index building (use existing index)."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Ignore previous state and start fresh."),
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
        asyncio.run(
            build_index(
                output_dir,
                year_range,
                venue_patterns,
                limit,
                dry_run,
                force,
                concurrent,
            )
        )
        log("")

    log("--- Phase 2: Filtering s2orc_v2 ---")
    log("")
    asyncio.run(filter_s2orc(output_dir, None, limit, dry_run, force, concurrent))


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
