"""Dataset download script for S2ORC generative retrieval pipeline.

Downloads papers from Semantic Scholar with full metadata, references, and citations.
Builds citation graphs and creates train/dev/test splits.
"""

import asyncio
import json
import os
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Annotated, Any, NewType

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from api import SemanticScholarAPI, extract_pdf_url
from config import CONFERENCE_PATTERNS, ConferencePattern

# Semantic type aliases for IDs
PaperId = NewType("PaperId", str)
AuthorId = NewType("AuthorId", str)

app = typer.Typer(
    help="Download S2ORC dataset for generative retrieval pipeline",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


@dataclass(frozen=True, kw_only=True)
class Author:
    """Author information."""

    author_id: AuthorId | None
    name: str


@dataclass(frozen=True, kw_only=True)
class PaperMetadata:
    """Extended paper metadata for the retrieval pipeline."""

    paper_id: PaperId
    title: str
    abstract: str | None
    year: int | None
    venue: str | None
    authors: list[Author]
    citation_count: int | None
    fields_of_study: list[str]
    url: str
    open_access_pdf: str | None
    pdf_source: str | None = None


@dataclass(frozen=True, kw_only=True)
class PaperPairScore:
    """A scored pair of papers (for co-citation or bibliographic coupling)."""

    paper_1: PaperId
    paper_2: PaperId
    score: int


@dataclass(frozen=True, kw_only=True)
class CitationData:
    """References and citations for a set of papers."""

    references: dict[PaperId, list[PaperId]]
    citations: dict[PaperId, list[PaperId]]


@dataclass(frozen=True, kw_only=True)
class DatasetSplits:
    """Train/dev/test paper ID splits."""

    train: list[PaperId]
    dev: list[PaperId]
    test: list[PaperId]


@dataclass(frozen=True, kw_only=True)
class DownloadResult:
    """Complete result of dataset download."""

    papers: dict[PaperId, PaperMetadata]
    citation_data: CitationData
    co_citations: list[PaperPairScore]
    bib_coupling: list[PaperPairScore]
    splits: DatasetSplits


@dataclass
class DatasetStats:
    """Statistics about the downloaded dataset."""

    total_papers: int = 0
    papers_with_abstract: int = 0
    papers_with_pdf: int = 0
    papers_with_references: int = 0
    total_references: int = 0
    total_citations: int = 0
    by_year: dict[int, int] = field(default_factory=dict[int, int])
    by_venue: dict[str, int] = field(default_factory=dict[str, int])


# Extended fields for paper metadata (includes abstract and authors)
EXTENDED_PAPER_FIELDS = [
    "paperId",
    "title",
    "abstract",
    "year",
    "venue",
    "authors",
    "citationCount",
    "fieldsOfStudy",
    "url",
    "openAccessPdf",
    "externalIds",
]


def parse_paper_metadata(item: dict[str, Any]) -> PaperMetadata:
    """Parse API response into PaperMetadata."""
    pdf_url, pdf_source = extract_pdf_url(item)

    # Parse authors
    authors: list[Author] = []
    author_list: list[dict[str, Any]] = item.get("authors") or []
    for author_data in author_list:
        author_id_raw = author_data.get("authorId")
        authors.append(
            Author(
                author_id=AuthorId(author_id_raw) if author_id_raw else None,
                name=author_data.get("name", ""),
            )
        )

    return PaperMetadata(
        paper_id=PaperId(item.get("paperId", "")),
        title=item.get("title", ""),
        abstract=item.get("abstract"),
        year=item.get("year"),
        venue=item.get("venue"),
        authors=authors,
        citation_count=item.get("citationCount"),
        fields_of_study=item.get("fieldsOfStudy") or [],
        url=item.get("url", ""),
        open_access_pdf=pdf_url,
        pdf_source=pdf_source,
    )


async def get_papers_by_venues(
    api: SemanticScholarAPI,
    venues: list[str],
    year_range: tuple[int, int] | None = None,
    progress: Progress | None = None,
    task_id: TaskID | None = None,
) -> list[PaperMetadata]:
    """Get all papers from multiple venues with extended metadata."""
    papers: list[PaperMetadata] = []
    token: str | None = None

    year_query: str | None = None
    if year_range:
        start, end = year_range
        year_query = f"{start}-{end}"

    venue_query = ",".join(venues)

    while True:
        try:
            result = await api.search_papers_bulk(
                venue=venue_query,
                year=year_query,
                token=token,
                fields=EXTENDED_PAPER_FIELDS,
            )

            data: list[dict[str, Any]] = result.get("data", [])
            for item in data:
                paper = parse_paper_metadata(item)
                papers.append(paper)

            if progress and task_id:
                progress.update(task_id, advance=len(data))

            token = result.get("token")
            if not token:
                break

        except Exception as e:
            err_console.print(f"[red]Error fetching venues '{venue_query}': {e}[/red]")
            break

    return papers


async def fetch_papers_for_conferences(
    api: SemanticScholarAPI,
    conferences: list[ConferencePattern],
    year_range: tuple[int, int] | None,
) -> dict[PaperId, PaperMetadata]:
    """Fetch papers for all conferences."""
    all_papers: dict[PaperId, PaperMetadata] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        for conference in conferences:
            task_id = progress.add_task(
                f"[cyan]Fetching {conference.name}...", total=None
            )

            papers = await get_papers_by_venues(
                api,
                venues=conference.venue_patterns,
                year_range=year_range,
                progress=progress,
                task_id=task_id,
            )

            # Deduplicate
            new_count = 0
            for paper in papers:
                if paper.paper_id not in all_papers:
                    all_papers[paper.paper_id] = paper
                    new_count += 1

            progress.update(
                task_id,
                description=f"[green]{conference.name}: {new_count} papers[/green]",
                completed=new_count,
                total=new_count,
            )

    return all_papers


async def fetch_citations_for_papers(
    api: SemanticScholarAPI,
    paper_ids: list[PaperId],
    fetch_incoming: bool = True,
) -> CitationData:
    """Fetch references and citations for all papers.

    Args:
        api: Semantic Scholar API client
        paper_ids: List of paper IDs to fetch citations for
        fetch_incoming: Whether to also fetch incoming citations

    Returns:
        CitationData containing references and citations dicts
    """
    references: dict[PaperId, list[PaperId]] = {}
    citations: dict[PaperId, list[PaperId]] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task(
            "[cyan]Fetching references...", total=len(paper_ids)
        )

        for paper_id in paper_ids:
            refs = await api.get_paper_references(paper_id)
            references[paper_id] = [PaperId(r) for r in refs]
            progress.advance(task_id)

        if fetch_incoming:
            progress.update(task_id, description="[cyan]Fetching citations...")
            progress.reset(task_id, total=len(paper_ids))

            for paper_id in paper_ids:
                cites = await api.get_paper_citations(paper_id)
                citations[paper_id] = [PaperId(c) for c in cites]
                progress.advance(task_id)

    return CitationData(references=references, citations=citations)


def compute_co_citations(
    citations: dict[PaperId, list[PaperId]],
    min_overlap: int = 2,
) -> list[PaperPairScore]:
    """Compute co-citation pairs (papers frequently cited together).

    Two papers are co-cited if they appear together in the reference lists
    of other papers.
    """
    # Build inverted index: paper -> papers that cite it
    cited_by: dict[PaperId, set[PaperId]] = defaultdict(set)
    for paper_id, citing_papers in citations.items():
        for citing in citing_papers:
            cited_by[paper_id].add(citing)

    # Find co-citation pairs
    paper_ids = list(cited_by.keys())
    co_citations: list[PaperPairScore] = []

    console.print("[cyan]Computing co-citations...[/cyan]")
    for i, p1 in enumerate(paper_ids):
        for p2 in paper_ids[i + 1 :]:
            overlap = len(cited_by[p1] & cited_by[p2])
            if overlap >= min_overlap:
                co_citations.append(
                    PaperPairScore(paper_1=p1, paper_2=p2, score=overlap)
                )

    return co_citations


def compute_bibliographic_coupling(
    references: dict[PaperId, list[PaperId]],
    min_overlap: int = 2,
) -> list[PaperPairScore]:
    """Compute bibliographic coupling pairs (papers sharing common references).

    Two papers are bibliographically coupled if they cite the same papers.
    """
    # Convert to sets for faster intersection
    ref_sets: dict[PaperId, set[PaperId]] = {
        pid: set(refs) for pid, refs in references.items() if refs
    }

    paper_ids = list(ref_sets.keys())
    coupling: list[PaperPairScore] = []

    console.print("[cyan]Computing bibliographic coupling...[/cyan]")
    for i, p1 in enumerate(paper_ids):
        for p2 in paper_ids[i + 1 :]:
            overlap = len(ref_sets[p1] & ref_sets[p2])
            if overlap >= min_overlap:
                coupling.append(PaperPairScore(paper_1=p1, paper_2=p2, score=overlap))

    return coupling


def create_splits(
    papers: dict[PaperId, PaperMetadata],
    train_years: tuple[int, int],
    dev_year: int,
    test_year: int,
) -> DatasetSplits:
    """Create train/dev/test splits based on year."""
    train_ids: list[PaperId] = []
    dev_ids: list[PaperId] = []
    test_ids: list[PaperId] = []

    for paper_id, paper in papers.items():
        if paper.year is None:
            continue
        if train_years[0] <= paper.year <= train_years[1]:
            train_ids.append(paper_id)
        elif paper.year == dev_year:
            dev_ids.append(paper_id)
        elif paper.year == test_year:
            test_ids.append(paper_id)

    return DatasetSplits(train=train_ids, dev=dev_ids, test=test_ids)


def save_dataset(
    output_dir: Path,
    papers: dict[PaperId, PaperMetadata],
    citation_data: CitationData,
    co_citations: list[PaperPairScore],
    bib_coupling: list[PaperPairScore],
    splits: DatasetSplits,
) -> None:
    """Save all dataset artifacts to disk."""
    # Create directories
    papers_dir = output_dir / "papers"
    citations_dir = output_dir / "citations"
    splits_dir = output_dir / "splits"

    for d in [papers_dir, citations_dir, splits_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Save paper metadata
    console.print("[cyan]Saving paper metadata...[/cyan]")
    with open(papers_dir / "metadata.jsonl", "w", encoding="utf-8") as f:
        for paper in papers.values():
            # Convert to dict, excluding full_text (not available from API)
            data = {
                "paper_id": paper.paper_id,
                "title": paper.title,
                "abstract": paper.abstract,
                "year": paper.year,
                "venue": paper.venue,
                "authors": [asdict(a) for a in paper.authors],
                "citation_count": paper.citation_count,
                "fields_of_study": paper.fields_of_study,
                "url": paper.url,
                "open_access_pdf": paper.open_access_pdf,
                "pdf_source": paper.pdf_source,
            }
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    # Save references
    console.print("[cyan]Saving references...[/cyan]")
    with open(citations_dir / "references.jsonl", "w", encoding="utf-8") as f:
        for paper_id, refs in citation_data.references.items():
            data = {"paper_id": paper_id, "references": list(refs)}
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    # Save citations
    console.print("[cyan]Saving citations...[/cyan]")
    with open(citations_dir / "citations.jsonl", "w", encoding="utf-8") as f:
        for paper_id, cites in citation_data.citations.items():
            data = {"paper_id": paper_id, "citations": list(cites)}
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    # Save co-citations
    console.print("[cyan]Saving co-citations...[/cyan]")
    with open(citations_dir / "co_citations.jsonl", "w", encoding="utf-8") as f:
        for pair in co_citations:
            data = {
                "paper_1": pair.paper_1,
                "paper_2": pair.paper_2,
                "count": pair.score,
            }
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    # Save bibliographic coupling
    console.print("[cyan]Saving bibliographic coupling...[/cyan]")
    with open(citations_dir / "bib_coupling.jsonl", "w", encoding="utf-8") as f:
        for pair in bib_coupling:
            data = {
                "paper_1": pair.paper_1,
                "paper_2": pair.paper_2,
                "count": pair.score,
            }
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    # Save splits
    console.print("[cyan]Saving splits...[/cyan]")
    with open(splits_dir / "train.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(splits.train) + "\n")
    with open(splits_dir / "dev.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(splits.dev) + "\n")
    with open(splits_dir / "test.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(splits.test) + "\n")


def compute_stats(
    papers: dict[PaperId, PaperMetadata],
    citation_data: CitationData,
) -> DatasetStats:
    """Compute dataset statistics."""
    stats = DatasetStats()
    stats.total_papers = len(papers)

    by_year: dict[int, int] = defaultdict(int)
    by_venue: dict[str, int] = defaultdict(int)

    for paper in papers.values():
        if paper.abstract:
            stats.papers_with_abstract += 1
        if paper.open_access_pdf:
            stats.papers_with_pdf += 1
        if paper.year:
            by_year[paper.year] += 1
        if paper.venue:
            by_venue[paper.venue] += 1

    stats.by_year = dict(sorted(by_year.items()))
    stats.by_venue = dict(sorted(by_venue.items(), key=lambda x: -x[1]))

    for refs in citation_data.references.values():
        if refs:
            stats.papers_with_references += 1
            stats.total_references += len(refs)

    for cites in citation_data.citations.values():
        stats.total_citations += len(cites)

    return stats


async def _step_fetch_papers(
    api: SemanticScholarAPI,
    conferences: list[ConferencePattern],
    year_range: tuple[int, int],
) -> dict[PaperId, PaperMetadata]:
    """Step 1: Fetch papers from conferences."""
    console.print("[bold]Step 1: Fetching papers...[/bold]")
    papers = await fetch_papers_for_conferences(api, conferences, year_range)
    console.print(f"[green]Found {len(papers)} unique papers[/green]\n")
    return papers


async def _step_fetch_citations(
    api: SemanticScholarAPI,
    paper_ids: list[PaperId],
    skip: bool,
) -> CitationData:
    """Step 2: Fetch citation data for papers."""
    if skip:
        return CitationData(references={}, citations={})

    console.print("[bold]Step 2: Fetching citation data...[/bold]")
    citation_data = await fetch_citations_for_papers(
        api, paper_ids, fetch_incoming=True
    )
    console.print(
        f"[green]Fetched references for {len(citation_data.references)} papers[/green]\n"
    )
    return citation_data


def _step_compute_graph(
    citation_data: CitationData,
    skip: bool,
    min_overlap: int,
) -> tuple[list[PaperPairScore], list[PaperPairScore]]:
    """Step 3: Compute co-citation and bibliographic coupling graphs."""
    if skip or not citation_data.references or not citation_data.citations:
        return [], []

    console.print("[bold]Step 3: Computing citation graph...[/bold]")
    co_citations = compute_co_citations(
        citation_data.citations, min_overlap=min_overlap
    )
    console.print(f"[green]Found {len(co_citations)} co-citation pairs[/green]")

    bib_coupling = compute_bibliographic_coupling(
        citation_data.references, min_overlap=min_overlap
    )
    console.print(
        f"[green]Found {len(bib_coupling)} bibliographic coupling pairs[/green]\n"
    )
    return co_citations, bib_coupling


def _step_create_splits(
    papers: dict[PaperId, PaperMetadata],
    train_years: tuple[int, int],
    dev_year: int,
    test_year: int,
) -> DatasetSplits:
    """Step 4: Create train/dev/test splits based on year."""
    console.print("[bold]Step 4: Creating train/dev/test splits...[/bold]")
    splits = create_splits(papers, train_years, dev_year, test_year)
    console.print(
        f"  Train: {len(splits.train)} papers ({train_years[0]}-{train_years[1]})"
    )
    console.print(f"  Dev: {len(splits.dev)} papers ({dev_year})")
    console.print(f"  Test: {len(splits.test)} papers ({test_year})\n")
    return splits


@app.command()
def download(
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output directory for dataset",
        ),
    ] = Path("data"),
    start_year: Annotated[
        int,
        typer.Option(
            "--start-year",
            help="Start year for papers (inclusive)",
        ),
    ] = 2020,
    end_year: Annotated[
        int,
        typer.Option(
            "--end-year",
            help="End year for papers (inclusive)",
        ),
    ] = 2025,
    train_end_year: Annotated[
        int,
        typer.Option(
            "--train-end",
            help="Last year for training set",
        ),
    ] = 2023,
    dev_year: Annotated[
        int,
        typer.Option(
            "--dev-year",
            help="Year for dev set",
        ),
    ] = 2024,
    test_year: Annotated[
        int,
        typer.Option(
            "--test-year",
            help="Year for test set",
        ),
    ] = 2025,
    conferences: Annotated[
        list[str] | None,
        typer.Option(
            "--conference",
            "-c",
            help="Specific conferences to include (can be repeated)",
        ),
    ] = None,
    skip_citations: Annotated[
        bool,
        typer.Option(
            "--skip-citations",
            help="Skip fetching citation data (faster)",
        ),
    ] = False,
    skip_graph: Annotated[
        bool,
        typer.Option(
            "--skip-graph",
            help="Skip computing co-citations and bibliographic coupling",
        ),
    ] = False,
    min_overlap: Annotated[
        int,
        typer.Option(
            "--min-overlap",
            help="Minimum overlap for co-citation/coupling pairs",
        ),
    ] = 2,
) -> None:
    """Download S2ORC dataset for generative retrieval pipeline.

    Downloads papers from specified conferences, fetches citation relationships,
    and creates train/dev/test splits.

    Requires SEMANTIC_SCHOLAR_API_KEY environment variable.
    """
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        err_console.print("[red]Error: SEMANTIC_SCHOLAR_API_KEY not set.[/red]")
        err_console.print(
            "Get an API key from https://www.semanticscholar.org/product/api"
        )
        sys.exit(1)

    # Select conferences
    selected_conferences: list[ConferencePattern] = list(CONFERENCE_PATTERNS)
    if conferences:
        conference_map = {c.name.upper(): c for c in CONFERENCE_PATTERNS}
        selected_conferences = []
        for conf_name in conferences:
            conf_upper = conf_name.upper()
            if conf_upper in conference_map:
                selected_conferences.append(conference_map[conf_upper])
            else:
                err_console.print(
                    f"[yellow]Warning: Unknown conference '{conf_name}'[/yellow]"
                )

        if not selected_conferences:
            err_console.print("[red]Error: No valid conferences specified[/red]")
            raise typer.Exit(1)

    console.print("[bold cyan]S2ORC Dataset Download[/bold cyan]")
    console.print(f"  Conferences: {len(selected_conferences)}")
    console.print(f"  Years: {start_year}-{end_year}")
    console.print(f"  Train: {start_year}-{train_end_year}")
    console.print(f"  Dev: {dev_year}, Test: {test_year}")
    console.print()

    async def run() -> DownloadResult:
        async with SemanticScholarAPI(api_key=api_key) as api:
            papers = await _step_fetch_papers(
                api, selected_conferences, (start_year, end_year)
            )
            citation_data = await _step_fetch_citations(
                api, list(papers.keys()), skip=skip_citations
            )
            co_citations, bib_coupling = _step_compute_graph(
                citation_data, skip=skip_graph, min_overlap=min_overlap
            )
            splits = _step_create_splits(
                papers, (start_year, train_end_year), dev_year, test_year
            )
            return DownloadResult(
                papers=papers,
                citation_data=citation_data,
                co_citations=co_citations,
                bib_coupling=bib_coupling,
                splits=splits,
            )

    # Run async portion
    result = asyncio.run(run())

    # Step 5: Save everything (sync I/O)
    console.print("[bold]Step 5: Saving dataset...[/bold]")
    save_dataset(
        output_dir,
        result.papers,
        result.citation_data,
        result.co_citations,
        result.bib_coupling,
        result.splits,
    )

    # Print statistics
    stats = compute_stats(result.papers, result.citation_data)
    console.print("\n[bold cyan]Dataset Statistics:[/bold cyan]")
    console.print(f"  Total papers: {stats.total_papers}")
    console.print(f"  With abstract: {stats.papers_with_abstract}")
    console.print(f"  With PDF: {stats.papers_with_pdf}")
    console.print(f"  With references: {stats.papers_with_references}")
    console.print(f"  Total references: {stats.total_references}")
    console.print(f"  Total citations: {stats.total_citations}")

    console.print("\n[bold cyan]Papers by Year:[/bold cyan]")
    for year, count in stats.by_year.items():
        console.print(f"  {year}: {count}")

    # Save stats
    stats_file = output_dir / "stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(asdict(stats), f, indent=2)
    console.print(f"\n[green]Dataset saved to {output_dir}[/green]")


@app.command()
def resume(
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output directory containing partial dataset",
        ),
    ] = Path("data"),
    skip_graph: Annotated[
        bool,
        typer.Option(
            "--skip-graph",
            help="Skip computing co-citations and bibliographic coupling",
        ),
    ] = False,
    min_overlap: Annotated[
        int,
        typer.Option(
            "--min-overlap",
            help="Minimum overlap for co-citation/coupling pairs",
        ),
    ] = 2,
) -> None:
    """Resume citation fetching for papers that don't have references yet.

    Useful if the initial download was interrupted or run with --skip-citations.
    """
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        err_console.print("[red]Error: SEMANTIC_SCHOLAR_API_KEY not set.[/red]")
        sys.exit(1)

    # Load existing data
    papers_file = output_dir / "papers" / "metadata.jsonl"
    refs_file = output_dir / "citations" / "references.jsonl"

    if not papers_file.exists():
        err_console.print(f"[red]Error: {papers_file} not found[/red]")
        sys.exit(1)

    # Load paper IDs
    paper_ids: list[PaperId] = []
    with open(papers_file, encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            paper_ids.append(PaperId(data["paper_id"]))

    console.print(f"[cyan]Found {len(paper_ids)} papers[/cyan]")

    # Load existing references
    existing_refs: set[PaperId] = set()
    if refs_file.exists():
        with open(refs_file, encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                existing_refs.add(PaperId(data["paper_id"]))

    # Find papers without references
    missing = [pid for pid in paper_ids if pid not in existing_refs]
    console.print(f"[cyan]Papers needing citation fetch: {len(missing)}[/cyan]")

    if not missing:
        console.print("[green]All papers already have citation data[/green]")
        return

    async def run() -> CitationData:
        api = SemanticScholarAPI(api_key=api_key)
        async with api:
            return await fetch_citations_for_papers(api, missing, fetch_incoming=True)

    citation_data = asyncio.run(run())

    # Append to existing files (sync I/O)
    citations_dir = output_dir / "citations"
    with open(citations_dir / "references.jsonl", "a", encoding="utf-8") as f:
        for paper_id, refs in citation_data.references.items():
            data = {"paper_id": paper_id, "references": list(refs)}
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    with open(citations_dir / "citations.jsonl", "a", encoding="utf-8") as f:
        for paper_id, cites in citation_data.citations.items():
            data = {"paper_id": paper_id, "citations": list(cites)}
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    console.print(
        f"[green]Added citations for {len(citation_data.references)} papers[/green]"
    )


if __name__ == "__main__":
    app()
