"""Unified pipeline for acquiring S2ORC NLP dataset.

Five phases, each resumable:
1. index: Build corpus ID index AND extract paper metadata from `papers` dataset
2. fulltext: Extract full paper text from `s2orc_v2` dataset
3. citations: Extract citation relationships from `citations` dataset
4. derive: Compute co-citations and bibliographic coupling from citation graph
5. splits: Create train/dev/test splits by publication year

Run all phases with: uv run pipeline.py all <output_dir>
"""

import asyncio
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, NoReturn

import aiofiles
import httpx
import typer
from tqdm import tqdm

import async_utils
from async_utils import download_file, get_filename_from_url

# === Constants ===

DATASETS_API = "https://api.semanticscholar.org/datasets/v1"

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
    r"\bCL\b",
]

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


# === Utilities ===


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


def backup_files(files: list[Path], backup_suffix: str = ".bak") -> None:
    """Back up files before deleting."""
    for p in files:
        if p.exists():
            backup_path = p.with_suffix(p.suffix + backup_suffix)
            if backup_path.exists():
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                backup_path = p.with_suffix(f"{p.suffix}.{timestamp}{backup_suffix}")
            p.rename(backup_path)
            log(f"  Backed up: {p.name} -> {backup_path.name}")


# === Data structures ===


@dataclass
class Stats:
    """Statistics for processing."""

    files_processed: int = 0
    records_matched: int = 0
    bytes_downloaded: int = 0
    # Match breakdown (for index phase)
    matched_acl_only: int = 0
    matched_venue_only: int = 0
    matched_both: int = 0


@dataclass
class DatasetInfo:
    """Information about a dataset from the API."""

    name: str
    files: list[str] = field(default_factory=list[str])
    release_id: str = ""


@dataclass
class IndexResult:
    """Result of processing a papers file for indexing."""

    corpus_ids: set[int] = field(default_factory=set[int])
    record_count: int = 0
    # Match breakdown
    acl_only: int = 0
    venue_only: int = 0
    both: int = 0


class MatchResult:
    """Result of paper matching, tracking which criteria matched."""

    __slots__ = ("has_acl_id", "has_venue_match", "matched")

    def __init__(
        self, matched: bool, has_acl_id: bool = False, has_venue_match: bool = False
    ) -> None:
        self.matched = matched
        self.has_acl_id = has_acl_id
        self.has_venue_match = has_venue_match


# === Shared helpers ===


async def get_dataset_info(client: httpx.AsyncClient, name: str) -> DatasetInfo:
    """Fetch dataset file URLs from the Semantic Scholar API."""
    response = await client.get(f"{DATASETS_API}/release/latest")
    response.raise_for_status()
    release_id = response.json()["release_id"]

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


def make_url_refresher(
    client: httpx.AsyncClient, dataset_name: str, filename: str
) -> async_utils.UrlRefresher:
    """Create a URL refresher callback for a specific file.

    When called, re-fetches the dataset info and returns the fresh URL
    for the specified filename.
    """

    async def refresh() -> str:
        dataset = await get_dataset_info(client, dataset_name)
        for url in dataset.files:
            if get_filename_from_url(url) == filename:
                return url
        raise RuntimeError(f"File {filename} not found in refreshed dataset")

    return refresh


async def load_processed_files(path: Path) -> set[str]:
    """Load set of processed filenames."""
    if not path.exists():
        return set()
    async with aiofiles.open(path) as f:
        content = await f.read()
        return {line.strip() for line in content.splitlines() if line.strip()}


async def append_processed_file(path: Path, filename: str) -> None:
    """Append a filename to the processed files list."""
    async with aiofiles.open(path, "a") as f:
        await f.write(f"{filename}\n")


def load_corpus_ids(path: Path) -> set[int]:
    """Load corpus IDs from index file."""
    if not path.exists():
        return set()
    ids: set[int] = set()
    with open(path) as f:
        for line in f:
            if line.strip():
                ids.add(int(line.strip()))
    return ids


async def append_corpus_ids(path: Path, ids: set[int]) -> None:
    """Append corpus IDs to file."""
    if not ids:
        return
    async with aiofiles.open(path, "a") as f:
        await f.writelines(f"{cid}\n" for cid in sorted(ids))


def load_matched_ids(path: Path) -> set[int]:
    """Load already-matched corpus IDs from tracking file."""
    if not path.exists():
        return set()
    with open(path) as f:
        return {int(line) for line_ in f if (line := line_.strip())}


async def append_matched_ids(path: Path, ids: set[int]) -> None:
    """Append newly matched corpus IDs to tracking file."""
    if not ids:
        return
    async with aiofiles.open(path, "a") as f:
        await f.writelines(f"{cid}\n" for cid in sorted(ids))


# === Phase 1: Index + Metadata ===


def make_venue_matcher(patterns: list[str]) -> Callable[[str], bool]:
    """Create a function that matches venue strings against patterns."""
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]

    def matcher(venue: str) -> bool:
        return any(p.search(venue) for p in compiled)

    return matcher


def paper_matches(
    record: dict[str, Any],
    year_range: tuple[int, int],
    venue_matcher: Callable[[str], bool],
) -> MatchResult:
    """Check if a paper matches: has ACL ID OR matches venue pattern, within year range."""
    year = record.get("year")
    if not year or not (year_range[0] <= year <= year_range[1]):
        return MatchResult(False)

    external_ids: dict[str, Any] = record.get("externalids") or {}
    has_acl_id = external_ids.get("ACL") is not None

    venue = record.get("venue", "") or ""
    has_venue_match = bool(venue and venue_matcher(venue))

    matched = has_acl_id or has_venue_match
    return MatchResult(matched, has_acl_id, has_venue_match)


def process_papers_file(
    path: Path,
    year_range: tuple[int, int],
    venue_matcher: Callable[[str], bool],
    desc: str,
    output_path: Path,
) -> IndexResult:
    """Process a papers file: extract corpus IDs and write records to output file."""
    result = IndexResult()
    with (
        gzip.open(path, "rt", encoding="utf-8") as f,
        open(output_path, "w", encoding="utf-8") as out,
    ):
        for line in tqdm(f, desc=desc, leave=False):
            if not line.strip():
                continue
            record = json.loads(line)
            match = paper_matches(record, year_range, venue_matcher)
            if match.matched:
                corpus_id = record.get("corpusid")
                if corpus_id:
                    result.corpus_ids.add(corpus_id)
                    result.record_count += 1
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    # Track match breakdown
                    if match.has_acl_id and match.has_venue_match:
                        result.both += 1
                    elif match.has_acl_id:
                        result.acl_only += 1
                    else:
                        result.venue_only += 1
    return result


def _output_name(filename: str) -> str:
    """Convert source filename to output filename (remove .gz extension)."""
    return filename.removesuffix(".gz")


async def download_and_process_index(
    url: str,
    filename: str,
    idx: int,
    total: int,
    output_dir: Path,
    metadata_dir: Path,
    year_range: tuple[int, int],
    venue_matcher: Callable[[str], bool],
    client: httpx.AsyncClient,
) -> tuple[IndexResult, int]:
    """Download a papers file and extract corpus IDs + metadata."""
    temp_path = output_dir / f".temp_{filename}"
    output_path = metadata_dir / _output_name(filename)
    refresher = make_url_refresher(client, "papers", filename)
    try:
        log(f"[{idx}/{total}] Downloading {filename}...")
        bytes_downloaded = await download_file(
            url, temp_path, f"[{idx}/{total}]", url_refresher=refresher
        )

        log(f"[{idx}/{total}] Processing {filename}...")
        result = await asyncio.to_thread(
            process_papers_file,
            temp_path,
            year_range,
            venue_matcher,
            f"[{idx}/{total}]",
            output_path,
        )
        return result, bytes_downloaded
    finally:
        temp_path.unlink(missing_ok=True)


async def run_index(
    output_dir: Path,
    year_range: tuple[int, int],
    venue_patterns: list[str],
    limit_files: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    max_concurrent: int = 10,
) -> None:
    """Phase 1: Build corpus ID index and extract paper metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)

    index_path = output_dir / "corpus_ids.txt"
    metadata_dir = output_dir / "papers"
    processed_path = output_dir / "processed_index.txt"
    stats_path = output_dir / "index_stats.json"

    venue_matcher = make_venue_matcher(venue_patterns)
    stats = Stats()

    if force:
        log("Force mode: backing up previous state...")
        backup_files([index_path, processed_path, stats_path])
        # Note: metadata_dir files are not backed up, they're just overwritten

    processed_files = await load_processed_files(processed_path)
    corpus_ids: set[int]
    if processed_files:
        log(f"Resuming: {len(processed_files)} files already processed")
        corpus_ids = load_corpus_ids(index_path)
        log(f"  Loaded {len(corpus_ids):,} existing corpus IDs")
    else:
        corpus_ids = set()
        if index_path.exists():
            index_path.unlink()

    client = httpx.AsyncClient()
    log("Fetching papers dataset info...")
    dataset = await get_dataset_info(client, "papers")
    log(f"  Release: {dataset.release_id}")
    log(f"  Files: {len(dataset.files)}")

    files_to_process = dataset.files[:limit_files] if limit_files else dataset.files
    files_with_names = [(url, get_filename_from_url(url)) for url in files_to_process]
    remaining_files = [
        (url, name) for url, name in files_with_names if name not in processed_files
    ]

    if len(remaining_files) < len(files_to_process):
        log(f"  Skipping: {len(files_to_process) - len(remaining_files)} already done")
        log(f"  Remaining: {len(remaining_files)} files")

    if dry_run:
        log("\n[DRY RUN] Would download and process:")
        for i, (_, name) in enumerate(remaining_files[:10], 1):
            log(f"  {i}. {name}")
        if len(remaining_files) > 10:
            log(f"  ... and {len(remaining_files) - 10} more")
        return

    if not remaining_files:
        log("\nAll files already processed!")
        log(f"Index contains {len(corpus_ids):,} corpus IDs")
        return

    metadata_dir.mkdir(parents=True, exist_ok=True)
    log(f"  Concurrent downloads: {max_concurrent}")
    log("")

    total = len(remaining_files)
    state_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def worker(url: str, filename: str, idx: int) -> None:
        async with semaphore:
            try:
                result, bytes_dl = await download_and_process_index(
                    url,
                    filename,
                    idx,
                    total,
                    output_dir,
                    metadata_dir,
                    year_range,
                    venue_matcher,
                    client,
                )
                async with state_lock:
                    corpus_ids.update(result.corpus_ids)
                    stats.bytes_downloaded += bytes_dl
                    stats.files_processed += 1
                    stats.records_matched += result.record_count
                    stats.matched_acl_only += result.acl_only
                    stats.matched_venue_only += result.venue_only
                    stats.matched_both += result.both
                    current_total = len(corpus_ids)
                    await append_corpus_ids(index_path, result.corpus_ids)
                    await append_processed_file(processed_path, filename)
                log(
                    f"[{idx}/{total}] Found {len(result.corpus_ids):,} "
                    f"(total: {current_total:,})"
                )
            except Exception as e:
                err(f"[{idx}/{total}] Failed {filename}: {e}")

    tasks = [
        asyncio.create_task(worker(url, filename, i))
        for i, (url, filename) in enumerate(remaining_files, 1)
    ]
    await asyncio.gather(*tasks)

    await client.aclose()

    async with aiofiles.open(stats_path, "w") as f:
        await f.write(
            json.dumps(
                {
                    "release_id": dataset.release_id,
                    "year_range": list(year_range),
                    "venue_patterns": venue_patterns,
                    "stats": {
                        "corpus_ids": len(corpus_ids),
                        "files_processed": stats.files_processed + len(processed_files),
                        "records_matched": stats.records_matched,
                        "matched_acl_only": stats.matched_acl_only,
                        "matched_venue_only": stats.matched_venue_only,
                        "matched_both": stats.matched_both,
                        "bytes_downloaded": stats.bytes_downloaded,
                    },
                },
                indent=2,
            )
        )

    log(f"\nIndex complete: {len(corpus_ids):,} corpus IDs")
    log(f"  Files processed this run: {stats.files_processed}")
    log(f"  Total files processed: {stats.files_processed + len(processed_files)}")
    log(f"  Matches this run: {stats.records_matched:,}")
    log(f"    ACL ID only: {stats.matched_acl_only:,}")
    log(f"    Venue only: {stats.matched_venue_only:,}")
    log(f"    Both: {stats.matched_both:,}")
    log(f"  Index: {index_path}")
    log(f"  Metadata: {metadata_dir}")


# === Phase 2: Full text ===


@dataclass
class FulltextResult:
    """Result of processing an s2orc file for fulltext extraction."""

    matched_ids: set[int]  # Corpus IDs that were matched
    match_count: int


def process_s2orc_file(
    path: Path, corpus_ids: set[int], desc: str, output_path: Path
) -> FulltextResult:
    """Process s2orc file and stream matching records directly to output file."""
    matched_ids: set[int] = set()
    match_count = 0
    with (
        gzip.open(path, "rt", encoding="utf-8") as f,
        gzip.open(output_path, "wt", encoding="utf-8") as out,
    ):
        for line in tqdm(f, desc=desc, leave=False):
            if line.strip():
                record = json.loads(line)
                corpus_id = record.get("corpusid")
                if corpus_id and corpus_id in corpus_ids:
                    out.write(json.dumps(record) + "\n")
                    matched_ids.add(corpus_id)
                    match_count += 1
    return FulltextResult(matched_ids, match_count)


async def download_and_process_fulltext(
    url: str,
    filename: str,
    idx: int,
    total: int,
    output_dir: Path,
    s2orc_dir: Path,
    corpus_ids: set[int],
    client: httpx.AsyncClient,
) -> tuple[FulltextResult, int]:
    """Download s2orc file and extract matching records to output file."""
    temp_input = output_dir / f".temp_{filename}"
    output_path = s2orc_dir / filename  # Keep original .jsonl.gz name
    refresher = make_url_refresher(client, "s2orc_v2", filename)
    try:
        log(f"[{idx}/{total}] Downloading {filename}...")
        bytes_downloaded = await download_file(
            url, temp_input, f"[{idx}/{total}]", url_refresher=refresher
        )

        log(f"[{idx}/{total}] Processing {filename}...")
        result = await asyncio.to_thread(
            process_s2orc_file, temp_input, corpus_ids, f"[{idx}/{total}]", output_path
        )
        return result, bytes_downloaded
    finally:
        temp_input.unlink(missing_ok=True)


async def run_fulltext(
    output_dir: Path,
    limit_files: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    max_concurrent: int = 10,
) -> None:
    """Phase 2: Extract full paper text from s2orc_v2 dataset."""
    index_path = output_dir / "corpus_ids.txt"
    s2orc_dir = output_dir / "s2orc"
    processed_path = output_dir / "processed_fulltext.txt"
    matched_ids_path = output_dir / "matched_corpus_ids.txt"

    if not index_path.exists():
        die(f"Index not found: {index_path}\nRun 'index' phase first.")

    log(f"Loading corpus IDs from {index_path}...")
    corpus_ids = load_corpus_ids(index_path)
    original_index_size = len(corpus_ids)
    log(f"  Loaded {len(corpus_ids):,} corpus IDs")

    if not corpus_ids:
        die("Index is empty.")

    if force:
        log("Force mode: backing up previous state...")
        backup_files([processed_path, matched_ids_path])
        # Note: s2orc_dir files are not backed up, they're just overwritten

    processed_files = await load_processed_files(processed_path)
    matched_ids = load_matched_ids(matched_ids_path)
    prior_matches = len(matched_ids)
    if processed_files:
        log(f"Resuming: {len(processed_files)} files already processed")
        log(f"  Existing matches: {prior_matches:,}")

        # Detect index growth - find IDs that haven't been searched for yet
        new_ids = corpus_ids - matched_ids
        if new_ids:
            log(f"  Index grew: {len(new_ids):,} new IDs to search for")
            # Clear processed files to force re-scan
            processed_files = set[str]()
            # Use new_ids instead of corpus_ids for matching
            corpus_ids = new_ids

    stats = Stats()
    stats.records_matched = prior_matches  # Start from existing count

    client = httpx.AsyncClient()
    log("Fetching s2orc_v2 dataset info...")
    dataset = await get_dataset_info(client, "s2orc_v2")
    log(f"  Release: {dataset.release_id}")
    log(f"  Files: {len(dataset.files)}")

    files_to_process = dataset.files[:limit_files] if limit_files else dataset.files
    files_with_names = [(url, get_filename_from_url(url)) for url in files_to_process]
    remaining_files = [
        (url, name) for url, name in files_with_names if name not in processed_files
    ]

    if len(remaining_files) < len(files_to_process):
        log(f"  Skipping: {len(files_to_process) - len(remaining_files)} already done")
        log(f"  Remaining: {len(remaining_files)} files")

    if dry_run:
        log("\n[DRY RUN] Would download and process:")
        for i, (_, name) in enumerate(remaining_files[:10], 1):
            log(f"  {i}. {name}")
        if len(remaining_files) > 10:
            log(f"  ... and {len(remaining_files) - 10} more")
        return

    if not remaining_files:
        log("\nAll files already processed!")
        log(f"  Total matches: {prior_matches:,}")
        coverage = (
            prior_matches / original_index_size * 100 if original_index_size else 0
        )
        log(f"  Coverage: {coverage:.1f}% of index")
        return

    s2orc_dir.mkdir(parents=True, exist_ok=True)
    log(f"  Concurrent downloads: {max_concurrent}")
    log("")

    total = len(remaining_files)
    state_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def worker(url: str, filename: str, idx: int) -> None:
        async with semaphore:
            try:
                result, bytes_dl = await download_and_process_fulltext(
                    url, filename, idx, total, output_dir, s2orc_dir, corpus_ids, client
                )
                async with state_lock:
                    stats.bytes_downloaded += bytes_dl
                    stats.files_processed += 1
                    stats.records_matched += result.match_count
                    await append_matched_ids(matched_ids_path, result.matched_ids)
                    await append_processed_file(processed_path, filename)
                log(
                    f"[{idx}/{total}] Found {result.match_count:,} "
                    f"(total: {stats.records_matched:,})"
                )
            except Exception as e:
                err(f"[{idx}/{total}] Failed {filename}: {e}")

    tasks = [
        asyncio.create_task(worker(url, filename, i))
        for i, (url, filename) in enumerate(remaining_files, 1)
    ]
    await asyncio.gather(*tasks)

    await client.aclose()

    log(f"\nFull text extraction complete: {stats.records_matched:,} papers")
    log(f"  Files processed this run: {stats.files_processed}")
    log(f"  Output: {s2orc_dir}")
    coverage = (
        stats.records_matched / original_index_size * 100 if original_index_size else 0
    )
    log(f"  Coverage: {coverage:.1f}% of index")


# === Phase 3: Citations ===


def process_citations_file(
    path: Path, corpus_ids: set[int], desc: str, output_path: Path
) -> int:
    """Process citations file and write matching links to output file."""
    match_count = 0
    with (
        gzip.open(path, "rt", encoding="utf-8") as f,
        open(output_path, "w", encoding="utf-8") as out,
    ):
        for line in tqdm(f, desc=desc, leave=False):
            if not line.strip():
                continue
            record = json.loads(line)
            citing = record.get("citingcorpusid")
            cited = record.get("citedcorpusid")
            if citing and cited and citing in corpus_ids and cited in corpus_ids:
                out.write(json.dumps({"citing": citing, "cited": cited}) + "\n")
                match_count += 1
    return match_count


async def download_and_process_citations(
    url: str,
    filename: str,
    idx: int,
    total: int,
    output_dir: Path,
    raw_dir: Path,
    corpus_ids: set[int],
    client: httpx.AsyncClient,
) -> tuple[int, int]:
    """Download citations file and extract matching links to output file."""
    temp_path = output_dir / f".temp_{filename}"
    output_path = raw_dir / _output_name(filename)
    refresher = make_url_refresher(client, "citations", filename)
    try:
        log(f"[{idx}/{total}] Downloading {filename}...")
        bytes_downloaded = await download_file(
            url, temp_path, f"[{idx}/{total}]", url_refresher=refresher
        )

        log(f"[{idx}/{total}] Processing {filename}...")
        match_count = await asyncio.to_thread(
            process_citations_file,
            temp_path,
            corpus_ids,
            f"[{idx}/{total}]",
            output_path,
        )
        return match_count, bytes_downloaded
    finally:
        temp_path.unlink(missing_ok=True)


def aggregate_citations(
    raw_dir: Path,
) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
    """Aggregate raw citation links from all files into references and citations dicts."""
    references: dict[int, set[int]] = defaultdict(set)
    citations: dict[int, set[int]] = defaultdict(set)

    for raw_file in sorted(raw_dir.glob("*.jsonl")):
        with open(raw_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                citing = record["citing"]
                cited = record["cited"]
                references[citing].add(cited)
                citations[cited].add(citing)

    return references, citations


async def run_citations(
    output_dir: Path,
    limit_files: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    max_concurrent: int = 10,
) -> None:
    """Phase 3: Extract citation relationships from citations dataset."""
    index_path = output_dir / "corpus_ids.txt"
    citations_dir = output_dir / "citations"
    raw_dir = citations_dir / "raw"
    processed_path = output_dir / "processed_citations.txt"

    if not index_path.exists():
        die(f"Index not found: {index_path}\nRun 'index' phase first.")

    log(f"Loading corpus IDs from {index_path}...")
    corpus_ids = load_corpus_ids(index_path)
    log(f"  Loaded {len(corpus_ids):,} corpus IDs")

    if not corpus_ids:
        die("Index is empty.")

    if force:
        log("Force mode: backing up previous state...")
        backup_files([processed_path])
        # Note: raw_dir files are not backed up, they're just overwritten

    processed_files = await load_processed_files(processed_path)
    if processed_files:
        log(f"Resuming: {len(processed_files)} files already processed")

    stats = Stats()

    client = httpx.AsyncClient()
    log("Fetching citations dataset info...")
    dataset = await get_dataset_info(client, "citations")
    log(f"  Release: {dataset.release_id}")
    log(f"  Files: {len(dataset.files)}")

    files_to_process = dataset.files[:limit_files] if limit_files else dataset.files
    files_with_names = [(url, get_filename_from_url(url)) for url in files_to_process]
    remaining_files = [
        (url, name) for url, name in files_with_names if name not in processed_files
    ]

    if len(remaining_files) < len(files_to_process):
        log(f"  Skipping: {len(files_to_process) - len(remaining_files)} already done")
        log(f"  Remaining: {len(remaining_files)} files")

    if dry_run:
        log("\n[DRY RUN] Would download and process:")
        for i, (_, name) in enumerate(remaining_files[:10], 1):
            log(f"  {i}. {name}")
        if len(remaining_files) > 10:
            log(f"  ... and {len(remaining_files) - 10} more")
        return

    raw_dir.mkdir(parents=True, exist_ok=True)

    if remaining_files:
        log(f"  Concurrent downloads: {max_concurrent}")
        log("")

        total = len(remaining_files)
        state_lock = asyncio.Lock()
        semaphore = asyncio.Semaphore(max_concurrent)

        async def worker(url: str, filename: str, idx: int) -> None:
            async with semaphore:
                try:
                    match_count, bytes_dl = await download_and_process_citations(
                        url,
                        filename,
                        idx,
                        total,
                        output_dir,
                        raw_dir,
                        corpus_ids,
                        client,
                    )
                    async with state_lock:
                        stats.bytes_downloaded += bytes_dl
                        stats.files_processed += 1
                        stats.records_matched += match_count
                        await append_processed_file(processed_path, filename)
                    log(
                        f"[{idx}/{total}] Found {match_count:,} "
                        f"(total: {stats.records_matched:,})"
                    )
                except Exception as e:
                    err(f"[{idx}/{total}] Failed {filename}: {e}")

        tasks = [
            asyncio.create_task(worker(url, filename, i))
            for i, (url, filename) in enumerate(remaining_files, 1)
        ]
        await asyncio.gather(*tasks)
    else:
        log("\nAll files already processed!")

    await client.aclose()

    log("\nAggregating citation links...")
    references, citations = aggregate_citations(raw_dir)

    refs_path = citations_dir / "references.jsonl"
    async with aiofiles.open(refs_path, "w", encoding="utf-8") as f:
        for paper_id, cited_ids in sorted(references.items()):
            await f.write(
                json.dumps({"paper_id": paper_id, "references": sorted(cited_ids)})
                + "\n"
            )
    log(f"  references.jsonl: {len(references):,} papers")

    cites_path = citations_dir / "citations.jsonl"
    async with aiofiles.open(cites_path, "w", encoding="utf-8") as f:
        for paper_id, citing_ids in sorted(citations.items()):
            await f.write(
                json.dumps({"paper_id": paper_id, "citations": sorted(citing_ids)})
                + "\n"
            )
    log(f"  citations.jsonl: {len(citations):,} papers")

    log(f"\nCitations complete: {stats.records_matched:,} links")


# === Phase 4: Postprocess ===


def load_references(path: Path) -> dict[int, list[int]]:
    """Load references from JSONL file."""
    refs: dict[int, list[int]] = {}
    with open(path, encoding="utf-8") as f:
        for line in tqdm(f, desc="Loading references", leave=False):
            if line.strip():
                record = json.loads(line)
                refs[record["paper_id"]] = record["references"]
    return refs


def load_metadata_years(metadata_dir: Path) -> dict[int, int]:
    """Load paper years from metadata JSONL files in directory."""
    years: dict[int, int] = {}
    files = sorted(metadata_dir.glob("*.jsonl"))
    for file_path in tqdm(files, desc="Loading metadata files", leave=False):
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    corpus_id = record.get("corpusid")
                    year = record.get("year")
                    if corpus_id and year:
                        years[corpus_id] = year
    return years


def run_derive(
    output_dir: Path,
    min_co_citations: int = 2,
    min_shared_refs: int = 3,
) -> None:
    """Phase 4: Compute co-citations and bibliographic coupling from citation graph."""
    refs_path = output_dir / "citations" / "references.jsonl"

    if not refs_path.exists():
        die(f"References not found: {refs_path}\nRun 'citations' phase first.")

    log("Loading references...")
    refs = load_references(refs_path)
    log(f"  {len(refs):,} papers with references")
    log("")

    # === Co-citations ===
    log("Computing co-citations...")
    pair_counts: Counter[tuple[int, int]] = Counter()
    for _paper_id, cited_ids in tqdm(refs.items(), desc="Co-citations", leave=False):
        cited_sorted = sorted(cited_ids)
        n = len(cited_sorted)
        for i in range(n):
            for j in range(i + 1, n):
                pair_counts[(cited_sorted[i], cited_sorted[j])] += 1

    co_cite_pairs = [(p, c) for p, c in pair_counts.items() if c >= min_co_citations]
    co_cite_pairs.sort(key=lambda x: -x[1])

    co_cite_path = output_dir / "citations" / "co_citations.jsonl"
    with open(co_cite_path, "w", encoding="utf-8") as f:
        f.writelines(
            json.dumps({"paper_a": paper_a, "paper_b": paper_b, "count": count}) + "\n"
            for (paper_a, paper_b), count in co_cite_pairs
        )
    log(f"  Wrote {len(co_cite_pairs):,} pairs to co_citations.jsonl")

    # === Bibliographic coupling ===
    log("Computing bibliographic coupling...")
    cited_by: dict[int, set[int]] = defaultdict(set)
    for paper_id, cited_ids in refs.items():
        for cited in cited_ids:
            cited_by[cited].add(paper_id)

    bib_counts: Counter[tuple[int, int]] = Counter()
    for citing_papers in tqdm(cited_by.values(), desc="Bib coupling", leave=False):
        citing_list = sorted(citing_papers)
        n = len(citing_list)
        for i in range(n):
            for j in range(i + 1, n):
                bib_counts[(citing_list[i], citing_list[j])] += 1

    bib_pairs = [(p, c) for p, c in bib_counts.items() if c >= min_shared_refs]
    bib_pairs.sort(key=lambda x: -x[1])

    bib_path = output_dir / "citations" / "bib_coupling.jsonl"
    with open(bib_path, "w", encoding="utf-8") as f:
        f.writelines(
            json.dumps({"paper_a": paper_a, "paper_b": paper_b, "shared_refs": shared})
            + "\n"
            for (paper_a, paper_b), shared in bib_pairs
        )
    log(f"  Wrote {len(bib_pairs):,} pairs to bib_coupling.jsonl")

    log("\nDerived data complete!")


def run_splits(
    output_dir: Path,
    train_years: tuple[int, int] = (2020, 2023),
    dev_year: int = 2024,
    test_year: int = 2025,
) -> None:
    """Phase 5: Create train/dev/test splits by publication year."""
    metadata_dir = output_dir / "papers"

    if not metadata_dir.exists() or not any(metadata_dir.glob("*.jsonl")):
        die(f"Metadata not found: {metadata_dir}\nRun 'index' phase first.")

    log("Loading metadata...")
    years = load_metadata_years(metadata_dir)
    log(f"  {len(years):,} papers with year info")
    log("")

    train_ids: list[int] = []
    dev_ids: list[int] = []
    test_ids: list[int] = []

    for paper_id, year in years.items():
        if train_years[0] <= year <= train_years[1]:
            train_ids.append(paper_id)
        elif year == dev_year:
            dev_ids.append(paper_id)
        elif year == test_year:
            test_ids.append(paper_id)

    splits_dir = output_dir / "splits"
    splits_dir.mkdir(parents=True, exist_ok=True)

    for name, ids in [("train", train_ids), ("dev", dev_ids), ("test", test_ids)]:
        path = splits_dir / f"{name}.txt"
        with open(path, "w") as f:
            for paper_id in sorted(ids):
                f.write(f"{paper_id}\n")

    log(f"  Train ({train_years[0]}-{train_years[1]}): {len(train_ids):,}")
    log(f"  Dev ({dev_year}): {len(dev_ids):,}")
    log(f"  Test ({test_year}): {len(test_ids):,}")

    log("\nSplits complete!")


# === CLI Commands ===


@app.command(name="index")
def cmd_index(
    output_dir: Annotated[Path, typer.Argument(help="Output directory.")],
    start_year: Annotated[
        int, typer.Option("--start-year", "-s", help="Start year (inclusive).")
    ] = 2010,
    end_year: Annotated[
        int, typer.Option("--end-year", "-e", help="End year (inclusive).")
    ] = 2025,
    venues: Annotated[
        list[str] | None,
        typer.Option("--venue", "-v", help="Additional venue pattern (repeatable)."),
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", "-n", help="Limit files (for testing).")
    ] = None,
    concurrent: Annotated[
        int, typer.Option("--concurrent", "-c", help="Concurrent downloads.")
    ] = 10,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be done.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Start fresh, backing up old data.")
    ] = False,
) -> None:
    """Phase 1: Build corpus ID index and extract paper metadata.

    Filters papers by ACL Anthology ID OR venue pattern match.
    """
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        die("SEMANTIC_SCHOLAR_API_KEY required.")

    venue_patterns = list(venues) if venues else DEFAULT_VENUE_PATTERNS

    log("=== Phase 1: Index + Metadata ===")
    log(f"Years: {start_year}-{end_year}")
    log(f"Venues: {venue_patterns}")
    log("")

    asyncio.run(
        run_index(
            output_dir,
            (start_year, end_year),
            venue_patterns,
            limit,
            dry_run,
            force,
            concurrent,
        )
    )


@app.command(name="fulltext")
def cmd_fulltext(
    output_dir: Annotated[Path, typer.Argument(help="Output directory.")],
    limit: Annotated[
        int | None, typer.Option("--limit", "-n", help="Limit files (for testing).")
    ] = None,
    concurrent: Annotated[
        int, typer.Option("--concurrent", "-c", help="Concurrent downloads.")
    ] = 10,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be done.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Start fresh, backing up old data.")
    ] = False,
) -> None:
    """Phase 2: Extract full paper text from s2orc_v2 dataset."""
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        die("SEMANTIC_SCHOLAR_API_KEY required.")

    log("=== Phase 2: Full Text ===")
    log("")

    asyncio.run(run_fulltext(output_dir, limit, dry_run, force, concurrent))


@app.command(name="citations")
def cmd_citations(
    output_dir: Annotated[Path, typer.Argument(help="Output directory.")],
    limit: Annotated[
        int | None, typer.Option("--limit", "-n", help="Limit files (for testing).")
    ] = None,
    concurrent: Annotated[
        int, typer.Option("--concurrent", "-c", help="Concurrent downloads.")
    ] = 10,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be done.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Start fresh, backing up old data.")
    ] = False,
) -> None:
    """Phase 3: Extract citation relationships from citations dataset."""
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        die("SEMANTIC_SCHOLAR_API_KEY required.")

    log("=== Phase 3: Citations ===")
    log("")

    asyncio.run(run_citations(output_dir, limit, dry_run, force, concurrent))


@app.command(name="derive")
def cmd_derive(
    output_dir: Annotated[Path, typer.Argument(help="Output directory.")],
    min_co_citations: Annotated[
        int, typer.Option("--min-co-citations", help="Min co-citation count.")
    ] = 2,
    min_shared_refs: Annotated[
        int, typer.Option("--min-shared-refs", help="Min shared references.")
    ] = 3,
) -> None:
    """Phase 4: Compute co-citations and bibliographic coupling."""
    log("=== Phase 4: Derive ===")
    log("")

    run_derive(output_dir, min_co_citations, min_shared_refs)


@app.command(name="splits")
def cmd_splits(
    output_dir: Annotated[Path, typer.Argument(help="Output directory.")],
    train_start: Annotated[
        int, typer.Option("--train-start", help="First year for training set.")
    ] = 2020,
    train_end: Annotated[
        int, typer.Option("--train-end", help="Last year for training set.")
    ] = 2023,
    dev_year: Annotated[
        int, typer.Option("--dev-year", help="Year for dev set.")
    ] = 2024,
    test_year: Annotated[
        int, typer.Option("--test-year", help="Year for test set.")
    ] = 2025,
) -> None:
    """Phase 5: Create train/dev/test splits by publication year."""
    log("=== Phase 5: Splits ===")
    log("")

    run_splits(output_dir, (train_start, train_end), dev_year, test_year)


@app.command(name="all")
def cmd_all(
    output_dir: Annotated[Path, typer.Argument(help="Output directory.")],
    start_year: Annotated[
        int, typer.Option("--start-year", "-s", help="Start year (inclusive).")
    ] = 2010,
    end_year: Annotated[
        int, typer.Option("--end-year", "-e", help="End year (inclusive).")
    ] = 2025,
    venues: Annotated[
        list[str] | None,
        typer.Option("--venue", "-v", help="Additional venue pattern (repeatable)."),
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", "-n", help="Limit files (for testing).")
    ] = None,
    concurrent: Annotated[
        int, typer.Option("--concurrent", "-c", help="Concurrent downloads.")
    ] = 10,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be done.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Start fresh, backing up old data.")
    ] = False,
    min_co_citations: Annotated[
        int, typer.Option("--min-co-citations", help="Min co-citation count.")
    ] = 2,
    min_shared_refs: Annotated[
        int, typer.Option("--min-shared-refs", help="Min shared references.")
    ] = 3,
    train_start: Annotated[
        int, typer.Option("--train-start", help="First year for training set.")
    ] = 2020,
    train_end: Annotated[
        int, typer.Option("--train-end", help="Last year for training set.")
    ] = 2023,
    dev_year: Annotated[
        int, typer.Option("--dev-year", help="Year for dev set.")
    ] = 2024,
    test_year: Annotated[
        int, typer.Option("--test-year", help="Year for test set.")
    ] = 2025,
) -> None:
    """Run all five phases: index, fulltext, citations, derive, splits.

    Each phase is resumable. If interrupted, just run again.
    """
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        die("SEMANTIC_SCHOLAR_API_KEY required.")

    venue_patterns = list(venues) if venues else DEFAULT_VENUE_PATTERNS

    log("=== Full Pipeline ===")
    log(f"Years: {start_year}-{end_year}")
    log(f"Venues: {venue_patterns}")
    log("")

    log("--- Phase 1: Index + Metadata ---")
    log("")
    asyncio.run(
        run_index(
            output_dir,
            (start_year, end_year),
            venue_patterns,
            limit,
            dry_run,
            force,
            concurrent,
        )
    )

    log("")
    log("--- Phase 2: Full Text ---")
    log("")
    asyncio.run(run_fulltext(output_dir, limit, dry_run, force, concurrent))

    log("")
    log("--- Phase 3: Citations ---")
    log("")
    asyncio.run(run_citations(output_dir, limit, dry_run, force, concurrent))

    if not dry_run:
        log("")
        log("--- Phase 4: Derive ---")
        log("")
        run_derive(output_dir, min_co_citations, min_shared_refs)

        log("")
        log("--- Phase 5: Splits ---")
        log("")
        run_splits(output_dir, (train_start, train_end), dev_year, test_year)

    log("")
    log("=== Pipeline Complete ===")


@app.command(name="stats")
def cmd_stats(
    output_dir: Annotated[Path, typer.Argument(help="Output directory.")],
) -> None:
    """Show statistics about the filtered dataset."""
    index_path = output_dir / "corpus_ids.txt"
    index_stats_path = output_dir / "index_stats.json"
    metadata_dir = output_dir / "papers"
    s2orc_dir = output_dir / "s2orc"
    citations_dir = output_dir / "citations"

    log("=== Dataset Statistics ===")
    log("")

    # Index stats
    if index_path.exists():
        corpus_ids = load_corpus_ids(index_path)
        log(f"Index: {len(corpus_ids):,} corpus IDs")

    if index_stats_path.exists():
        with open(index_stats_path) as f:
            index_stats = json.load(f)
        log(f"  Release: {index_stats.get('release_id', 'unknown')}")
        log(f"  Year range: {index_stats.get('year_range', 'unknown')}")
        if "stats" in index_stats:
            s = index_stats["stats"]
            log(f"  Files processed: {s.get('files_processed', 'unknown')}")
            log("  Match breakdown:")
            log(f"    ACL ID only: {s.get('matched_acl_only', 0):,}")
            log(f"    Venue only: {s.get('matched_venue_only', 0):,}")
            log(f"    Both: {s.get('matched_both', 0):,}")
        log("")

    # Metadata stats
    if metadata_dir.exists():
        files = list(metadata_dir.glob("*.jsonl"))
        if files:
            total_size = sum(f.stat().st_size for f in files)
            size_mb = total_size / (1024 * 1024)
            log(f"Metadata: {metadata_dir}/")
            log(f"  Files: {len(files)}")
            log(f"  Total size: {size_mb:.1f} MB")
            log("")

    # Fulltext stats
    if s2orc_dir.exists():
        files = list(s2orc_dir.glob("*.jsonl.gz"))
        if files:
            total_size = sum(f.stat().st_size for f in files)
            size_mb = total_size / (1024 * 1024)
            log(f"Full text: {s2orc_dir}/")
            log(f"  Files: {len(files)}")
            log(f"  Total size: {size_mb:.1f} MB")
            # Count records from matched_corpus_ids.txt (faster than reading all gzip files)
            matched_ids_path = output_dir / "matched_corpus_ids.txt"
            if matched_ids_path.exists():
                matched_ids = load_matched_ids(matched_ids_path)
                log(f"  Records: {len(matched_ids):,}")
                if index_path.exists():
                    corpus_ids = load_corpus_ids(index_path)
                    coverage = (
                        len(matched_ids) / len(corpus_ids) * 100 if corpus_ids else 0
                    )
                    log(f"  Coverage: {coverage:.1f}% of index")
            log("")

    # Citations stats
    refs_path = citations_dir / "references.jsonl"
    cites_path = citations_dir / "citations.jsonl"
    raw_dir = citations_dir / "raw"

    if refs_path.exists() or cites_path.exists():
        log("Citations:")
        if refs_path.exists():
            with open(refs_path) as f:
                count = sum(1 for _ in f)
            log(f"  Papers with references: {count:,}")
        if cites_path.exists():
            with open(cites_path) as f:
                count = sum(1 for _ in f)
            log(f"  Papers with citations: {count:,}")
        if raw_dir.exists():
            files = list(raw_dir.glob("*.jsonl"))
            if files:
                total_links = 0
                for raw_file in files:
                    with open(raw_file) as f:
                        total_links += sum(1 for _ in f)
                log(f"  Total citation links: {total_links:,}")


if __name__ == "__main__":
    app()
