"""Extract paper metadata and citations from Semantic Scholar bulk datasets.

Uses an existing corpus_ids.txt index to extract:
- Paper metadata from the `papers` dataset
- Citation relationships from the `citations` dataset

This avoids API calls by using bulk dataset downloads.
"""

import asyncio
import gzip
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, NoReturn

import aiofiles
import httpx
import typer
from tqdm import tqdm

from async_utils import download_file, get_filename_from_url

DATASETS_API = "https://api.semanticscholar.org/datasets/v1"

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


# === Data structures ===


@dataclass
class ExtractStats:
    """Statistics for extraction process."""

    files_processed: int = 0
    records_scanned: int = 0
    records_matched: int = 0
    bytes_downloaded: int = 0


@dataclass
class DatasetInfo:
    """Information about a dataset from the API."""

    name: str
    files: list[str] = field(default_factory=list[str])
    release_id: str = ""


# === Shared helpers ===


async def load_corpus_ids(path: Path) -> set[int]:
    """Load corpus IDs from index file."""
    ids: set[int] = set()
    async with aiofiles.open(path) as f:
        async for line in f:
            if line.strip():
                ids.add(int(line.strip()))
    return ids


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


# === Metadata extraction ===


def process_metadata_file(
    path: Path,
    corpus_ids: set[int],
    desc: str,
) -> list[str]:
    """Process a gzipped papers file and return matching records as JSON lines.

    Runs in a thread pool since gzip doesn't support async.
    """
    matched: list[str] = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in tqdm(f, desc=desc, leave=False):
            if not line.strip():
                continue
            record = json.loads(line)
            corpus_id = record.get("corpusid")
            if corpus_id and corpus_id in corpus_ids:
                matched.append(json.dumps(record, ensure_ascii=False) + "\n")
    return matched


async def download_and_extract_metadata(
    url: str,
    filename: str,
    idx: int,
    total: int,
    output_dir: Path,
    corpus_ids: set[int],
) -> tuple[list[str], int]:
    """Download a papers file and extract matching records.

    Returns (matched_records, bytes_downloaded). Caller handles writing results.
    """
    temp_path = output_dir / f".temp_meta_{filename}"
    try:
        log(f"[{idx}/{total}] Downloading {filename}...")
        bytes_downloaded = await download_file(url, temp_path, f"[{idx}/{total}]")

        log(f"[{idx}/{total}] Processing {filename}...")
        matched = await asyncio.to_thread(
            process_metadata_file, temp_path, corpus_ids, f"[{idx}/{total}]"
        )
        return matched, bytes_downloaded
    finally:
        if temp_path.exists():
            temp_path.unlink()


async def extract_metadata(
    output_dir: Path,
    index_path: Path | None = None,
    limit_files: int | None = None,
    dry_run: bool = False,
    max_concurrent: int = 1,
) -> None:
    """Extract paper metadata from papers dataset for indexed corpus IDs."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if index_path is None:
        index_path = output_dir / "corpus_ids.txt"

    processed_path = output_dir / "processed_papers_metadata.txt"
    output_path = output_dir / "papers" / "metadata.jsonl"

    if not index_path.exists():
        die(f"Index file not found: {index_path}\nRun 'build-index' first.")

    log(f"Loading corpus ID index from {index_path}...")
    corpus_ids = await load_corpus_ids(index_path)
    log(f"  Loaded {len(corpus_ids):,} corpus IDs")

    if not corpus_ids:
        die("Index is empty. No papers to extract.")

    processed_files = await load_processed_files(processed_path)
    if processed_files:
        log(f"Resuming: {len(processed_files)} files already processed")

    stats = ExtractStats()

    async with httpx.AsyncClient() as client:
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
        log(
            f"  Skipping: {len(files_to_process) - len(remaining_files)} already processed"
        )
        log(f"  Remaining: {len(remaining_files)} files")

    if dry_run:
        log("\n[DRY RUN] Would download and process:")
        for i, (_, name) in enumerate(remaining_files[:10], 1):
            log(f"  {i}. {name}")
        if len(remaining_files) > 10:
            log(f"  ... and {len(remaining_files) - 10} more")
        log(f"\nOutput would be saved to: {output_path}")
        return

    if not remaining_files:
        log("\nAll files already processed!")
        return

    log(f"  Concurrent downloads: {max_concurrent}")
    log("")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = len(remaining_files)
    state_lock = asyncio.Lock()
    open_mode = "a" if processed_files else "w"

    async with aiofiles.open(output_path, open_mode, encoding="utf-8") as out_file:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def worker(url: str, filename: str, idx: int) -> None:
            async with semaphore:
                try:
                    records, bytes_dl = await download_and_extract_metadata(
                        url, filename, idx, total, output_dir, corpus_ids
                    )
                    async with state_lock:
                        await out_file.writelines(records)
                        await out_file.flush()
                        stats.bytes_downloaded += bytes_dl
                        stats.files_processed += 1
                        stats.records_matched += len(records)
                        await append_processed_file(processed_path, filename)
                    log(
                        f"[{idx}/{total}] Found {len(records):,} matches "
                        f"(total: {stats.records_matched:,})"
                    )
                except Exception as e:
                    err(f"[{idx}/{total}] Failed {filename}: {e}")

        tasks = [
            asyncio.create_task(worker(url, filename, i))
            for i, (url, filename) in enumerate(remaining_files, 1)
        ]
        await asyncio.gather(*tasks)

    log("\nMetadata extraction complete!")
    log(f"  Output: {output_path}")
    log(f"  Files processed: {stats.files_processed}")
    log(f"  Records matched: {stats.records_matched:,}")


# === Citations extraction ===


def process_citations_file(
    path: Path,
    corpus_ids: set[int],
    desc: str,
) -> list[str]:
    """Process a gzipped citations file and return matching links as JSON lines.

    Runs in a thread pool since gzip doesn't support async.
    """
    matched: list[str] = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in tqdm(f, desc=desc, leave=False):
            if not line.strip():
                continue
            record = json.loads(line)
            citing = record.get("citingcorpusid")
            cited = record.get("citedcorpusid")

            if not citing or not cited:
                continue

            # Include if BOTH papers are in our corpus
            if citing in corpus_ids and cited in corpus_ids:
                matched.append(json.dumps({"citing": citing, "cited": cited}) + "\n")
    return matched


async def download_and_extract_citations(
    url: str,
    filename: str,
    idx: int,
    total: int,
    output_dir: Path,
    corpus_ids: set[int],
) -> tuple[list[str], int]:
    """Download a citations file and extract matching links.

    Returns (matched_links, bytes_downloaded). Caller handles writing results.
    """
    temp_path = output_dir / f".temp_cite_{filename}"
    try:
        log(f"[{idx}/{total}] Downloading {filename}...")
        bytes_downloaded = await download_file(url, temp_path, f"[{idx}/{total}]")

        log(f"[{idx}/{total}] Processing {filename}...")
        matched = await asyncio.to_thread(
            process_citations_file, temp_path, corpus_ids, f"[{idx}/{total}]"
        )
        return matched, bytes_downloaded
    finally:
        if temp_path.exists():
            temp_path.unlink()


async def aggregate_citations(
    raw_path: Path,
) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
    """Aggregate raw citation links into references and incoming citations dicts."""
    references: dict[int, set[int]] = defaultdict(set)
    incoming: dict[int, set[int]] = defaultdict(set)

    async with aiofiles.open(raw_path, encoding="utf-8") as f:
        async for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            citing = record["citing"]
            cited = record["cited"]
            references[citing].add(cited)
            incoming[cited].add(citing)

    return references, incoming


async def extract_citations(
    output_dir: Path,
    index_path: Path | None = None,
    limit_files: int | None = None,
    dry_run: bool = False,
    max_concurrent: int = 1,
) -> None:
    """Extract citations from citations dataset for indexed corpus IDs.

    Outputs two files:
    - references.jsonl: paper_id -> [cited_paper_ids] (outgoing citations)
    - citations.jsonl: paper_id -> [citing_paper_ids] (incoming citations)

    Uses an intermediate file (citations_raw.jsonl) to enable resume after crash.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if index_path is None:
        index_path = output_dir / "corpus_ids.txt"

    processed_path = output_dir / "processed_citations.txt"
    citations_dir = output_dir / "citations"
    raw_path = citations_dir / "citations_raw.jsonl"

    if not index_path.exists():
        die(f"Index file not found: {index_path}\nRun 'build-index' first.")

    log(f"Loading corpus ID index from {index_path}...")
    corpus_ids = await load_corpus_ids(index_path)
    log(f"  Loaded {len(corpus_ids):,} corpus IDs")

    if not corpus_ids:
        die("Index is empty. No citations to extract.")

    processed_files = await load_processed_files(processed_path)
    prior_links = 0
    if processed_files:
        log(f"Resuming: {len(processed_files)} files already processed")
        if raw_path.exists():
            async with aiofiles.open(raw_path, encoding="utf-8") as f:
                async for _ in f:
                    prior_links += 1
            log(f"  Existing citation links: {prior_links:,}")

    stats = ExtractStats()
    stats.records_matched = prior_links

    async with httpx.AsyncClient() as client:
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
        log(
            f"  Skipping: {len(files_to_process) - len(remaining_files)} already processed"
        )
        log(f"  Remaining: {len(remaining_files)} files")

    if dry_run:
        log("\n[DRY RUN] Would download and process:")
        for i, (_, name) in enumerate(remaining_files[:10], 1):
            log(f"  {i}. {name}")
        if len(remaining_files) > 10:
            log(f"  ... and {len(remaining_files) - 10} more")
        return

    citations_dir.mkdir(parents=True, exist_ok=True)

    if remaining_files:
        log(f"  Concurrent downloads: {max_concurrent}")
        log("")

        total = len(remaining_files)
        state_lock = asyncio.Lock()
        open_mode = "a" if processed_files else "w"

        async with aiofiles.open(raw_path, open_mode, encoding="utf-8") as raw_file:
            semaphore = asyncio.Semaphore(max_concurrent)

            async def worker(url: str, filename: str, idx: int) -> None:
                async with semaphore:
                    try:
                        links, bytes_dl = await download_and_extract_citations(
                            url, filename, idx, total, output_dir, corpus_ids
                        )
                        async with state_lock:
                            await raw_file.writelines(links)
                            await raw_file.flush()
                            stats.bytes_downloaded += bytes_dl
                            stats.files_processed += 1
                            stats.records_matched += len(links)
                            await append_processed_file(processed_path, filename)
                        log(
                            f"[{idx}/{total}] Found {len(links):,} citation links "
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

    log("\nAggregating citation links...")
    references, incoming = await aggregate_citations(raw_path)

    log("Writing output files...")

    refs_path = citations_dir / "references.jsonl"
    async with aiofiles.open(refs_path, "w", encoding="utf-8") as f:
        for paper_id, cited_ids in sorted(references.items()):
            record = {"paper_id": paper_id, "references": sorted(cited_ids)}
            await f.write(json.dumps(record) + "\n")
    log(f"  references.jsonl: {len(references):,} papers with references")

    cite_path = citations_dir / "citations.jsonl"
    async with aiofiles.open(cite_path, "w", encoding="utf-8") as f:
        for paper_id, citing_ids in sorted(incoming.items()):
            record = {"paper_id": paper_id, "citations": sorted(citing_ids)}
            await f.write(json.dumps(record) + "\n")
    log(f"  citations.jsonl: {len(incoming):,} papers with citations")

    log("\nCitations extraction complete!")
    log(f"  Total citation links: {stats.records_matched:,}")


# === CLI Commands ===


@app.command(name="metadata")
def cmd_metadata(
    output_dir: Annotated[
        Path, typer.Argument(help="Directory containing corpus_ids.txt")
    ],
    index: Annotated[
        Path | None,
        typer.Option("--index", "-i", help="Path to corpus ID index file."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-n", help="Limit number of files (for testing)."),
    ] = None,
    concurrent: Annotated[
        int,
        typer.Option("--concurrent", "-c", help="Number of concurrent downloads."),
    ] = 10,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
) -> None:
    """Extract paper metadata from the papers dataset.

    Reads corpus IDs from the index and extracts matching paper records
    from the Semantic Scholar papers dataset.

    Output: output_dir/papers/metadata.jsonl
    """
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        die("SEMANTIC_SCHOLAR_API_KEY environment variable is required.")

    log("=== Extracting paper metadata ===")
    log("")

    asyncio.run(extract_metadata(output_dir, index, limit, dry_run, concurrent))


@app.command(name="citations")
def cmd_citations(
    output_dir: Annotated[
        Path, typer.Argument(help="Directory containing corpus_ids.txt")
    ],
    index: Annotated[
        Path | None,
        typer.Option("--index", "-i", help="Path to corpus ID index file."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-n", help="Limit number of files (for testing)."),
    ] = None,
    concurrent: Annotated[
        int,
        typer.Option("--concurrent", "-c", help="Number of concurrent downloads."),
    ] = 10,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
) -> None:
    """Extract citations from the citations dataset.

    Reads corpus IDs from the index and extracts citation relationships
    where BOTH citing and cited papers are in our corpus.

    Output:
    - output_dir/citations/references.jsonl (paper -> papers it cites)
    - output_dir/citations/citations.jsonl (paper -> papers citing it)
    """
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        die("SEMANTIC_SCHOLAR_API_KEY environment variable is required.")

    log("=== Extracting citations ===")
    log("")

    asyncio.run(extract_citations(output_dir, index, limit, dry_run, concurrent))


@app.command(name="all")
def cmd_all(
    output_dir: Annotated[
        Path, typer.Argument(help="Directory containing corpus_ids.txt")
    ],
    index: Annotated[
        Path | None,
        typer.Option("--index", "-i", help="Path to corpus ID index file."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-n", help="Limit number of files (for testing)."),
    ] = None,
    concurrent: Annotated[
        int,
        typer.Option("--concurrent", "-c", help="Number of concurrent downloads."),
    ] = 10,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without downloading."),
    ] = False,
) -> None:
    """Extract both metadata and citations.

    Convenience command that runs both extraction steps.
    """
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        die("SEMANTIC_SCHOLAR_API_KEY environment variable is required.")

    log("=== Extracting metadata and citations ===")
    log("")

    log("--- Phase 1: Paper metadata ---")
    log("")
    asyncio.run(extract_metadata(output_dir, index, limit, dry_run, concurrent))

    log("")
    log("--- Phase 2: Citations ---")
    log("")
    asyncio.run(extract_citations(output_dir, index, limit, dry_run, concurrent))


if __name__ == "__main__":
    app()
