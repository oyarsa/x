"""Script to count papers from *ACL and ML/AI/NLP conferences using Semantic Scholar API.

This script searches for papers from major conferences and saves both individual
paper metadata and aggregated counts by year and venue.
"""

import asyncio
import json
import os
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn

from api import SemanticScholarAPI, extract_pdf_url
from config import CONFERENCE_PATTERNS, ConferencePattern, Paper

app = typer.Typer(
    help="Count papers from conferences using Semantic Scholar API",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)
console = Console()


async def get_papers_by_venues(
    api: SemanticScholarAPI,
    venues: list[str],
    year_range: tuple[int, int] | None = None,
) -> list[Paper]:
    """Get all papers from multiple venues using bulk API.

    Args:
        api: SemanticScholarAPI instance
        venues: List of venue names to search for
        year_range: Optional (start_year, end_year) tuple

    Returns:
        List of Paper objects
    """
    papers: list[Paper] = []
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
            )

            data: list[dict[str, Any]] = result.get("data", [])
            for item in data:
                pdf_url, pdf_source = extract_pdf_url(item)

                paper = Paper(
                    paper_id=item.get("paperId", ""),
                    title=item.get("title", ""),
                    year=item.get("year"),
                    venue=item.get("venue"),
                    citation_count=item.get("citationCount"),
                    fields_of_study=item.get("fieldsOfStudy") or [],
                    url=item.get("url", ""),
                    open_access_pdf=pdf_url,
                    pdf_source=pdf_source,
                )
                papers.append(paper)

            token = result.get("token")
            if not token:
                break

        except Exception as e:
            console.print(f"[red]Error for venues '{venue_query}': {e}[/red]")
            break

    return papers


@dataclass
class ConferencePapers:
    """Papers fetched for a specific conference."""

    conference_name: str
    papers: list[Paper]


async def fetch_conference_papers(
    api: SemanticScholarAPI,
    conference: ConferencePattern,
    year_range: tuple[int, int] | None,
    progress: Progress,
    task_id: TaskID,
) -> ConferencePapers:
    """Fetch papers for a specific conference pattern.

    Args:
        api: SemanticScholarAPI instance
        conference: Conference pattern to search for
        year_range: Optional year range to filter
        progress: Rich progress bar
        task_id: Task ID for progress updates

    Returns:
        ConferencePapers with conference name and matching papers
    """
    progress.update(task_id, description=f"[cyan]Fetching {conference.name}...[/cyan]")

    # Fetch all venue patterns in a single batched request
    papers = await get_papers_by_venues(
        api,
        venues=conference.venue_patterns,
        year_range=year_range,
    )

    # Deduplicate by paper_id
    seen_ids: set[str] = set()
    unique_papers: list[Paper] = []
    for paper in papers:
        if paper.paper_id not in seen_ids:
            seen_ids.add(paper.paper_id)
            unique_papers.append(paper)

    progress.update(
        task_id,
        description=f"[green]✓ {conference.name}: {len(unique_papers)} papers[/green]",
    )

    return ConferencePapers(conference_name=conference.name, papers=unique_papers)


async def fetch_all_conferences(
    api: SemanticScholarAPI,
    conferences: list[ConferencePattern],
    year_range: tuple[int, int] | None,
) -> list[ConferencePapers]:
    """Fetch papers for all conferences concurrently with rate limiting.

    Args:
        api: SemanticScholarAPI instance
        conferences: List of conference patterns to search
        year_range: Optional year range to filter

    Returns:
        List of ConferencePapers for each conference
    """
    async with api:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            tasks: list[asyncio.Task[ConferencePapers]] = []
            for conference in conferences:
                task_id = progress.add_task(f"[cyan]{conference.name}[/cyan]")
                tasks.append(
                    asyncio.create_task(
                        fetch_conference_papers(
                            api, conference, year_range, progress, task_id
                        )
                    )
                )

            results = await asyncio.gather(*tasks)

    return list(results)


@app.command()
def main(
    output_file: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output JSON file for individual paper records",
        ),
    ] = Path("output/papers.json"),
    aggregated_file: Annotated[
        Path,
        typer.Option(
            "--aggregated",
            "-a",
            help="Output JSON file for aggregated counts",
        ),
    ] = Path("output/aggregated_counts.json"),
    start_year: Annotated[
        int,
        typer.Option(
            "--start-year",
            help="Start year for filtering (inclusive). Set to 0 for no filter.",
        ),
    ] = 2020,
    end_year: Annotated[
        int,
        typer.Option(
            "--end-year",
            help="End year for filtering (inclusive). Set to 0 for no filter.",
        ),
    ] = 2025,
    conferences: Annotated[
        list[str] | None,
        typer.Option(
            "--conference",
            "-c",
            help="Specific conferences to search (can be repeated). If not specified, searches all.",
        ),
    ] = None,
) -> None:
    """Count papers from *ACL and ML/AI/NLP conferences using Semantic Scholar API.

    Requires SEMANTIC_SCHOLAR_API_KEY environment variable for API access (optional but recommended
    for higher rate limits).
    """
    # Get API key from environment
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        console.print("[red]Error: SEMANTIC_SCHOLAR_API_KEY not set.[/red]")
        sys.exit(1)

    # Create API client
    api = SemanticScholarAPI(api_key=api_key)

    # Determine year range
    year_range: tuple[int, int] | None = None
    if start_year or end_year:
        start = start_year or 1900
        end = end_year or 2030
        year_range = (start, end)
        console.print(f"[cyan]Filtering papers from {start} to {end}[/cyan]")

    # Filter conferences if specified
    selected_conferences = CONFERENCE_PATTERNS
    if conferences:
        conference_map = {c.name.upper(): c for c in CONFERENCE_PATTERNS}
        selected_conferences: list[ConferencePattern] = []
        for conf_name in conferences:
            conf_upper = conf_name.upper()
            if conf_upper in conference_map:
                selected_conferences.append(conference_map[conf_upper])
            else:
                console.print(
                    f"[yellow]Warning: Unknown conference '{conf_name}'[/yellow]"
                )

        if not selected_conferences:
            console.print("[red]Error: No valid conferences specified[/red]")
            raise typer.Exit(1)

    console.print(f"[cyan]Searching {len(selected_conferences)} conferences...[/cyan]")

    # Fetch papers for all conferences
    conference_results = asyncio.run(
        fetch_all_conferences(api, selected_conferences, year_range)
    )

    # Collect all papers and remove duplicates
    unique_papers: dict[str, Paper] = {}
    for conf_papers in conference_results:
        for paper in conf_papers.papers:
            if paper.paper_id not in unique_papers:
                unique_papers[paper.paper_id] = paper

    papers_with_pdf_count = sum(1 for p in unique_papers.values() if p.open_access_pdf)
    console.print(f"\n[green]Total unique papers found: {len(unique_papers)}[/green]")
    console.print(
        f"[green]Papers with open access PDF: {papers_with_pdf_count}[/green]"
    )

    # Save individual paper records
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            [asdict(p) for p in unique_papers.values()],
            f,
            indent=2,
            ensure_ascii=False,
        )
    console.print(f"[green]Saved paper records to {output_file}[/green]")

    # Aggregate by year and venue
    by_year: dict[int, int] = defaultdict(int)
    by_venue: dict[str, int] = defaultdict(int)
    by_year_venue: dict[tuple[int, str], int] = defaultdict(int)
    by_year_venue_with_pdf: dict[tuple[int, str], int] = defaultdict(int)
    papers_with_pdf = 0

    for paper in unique_papers.values():
        has_pdf = bool(paper.open_access_pdf)
        if has_pdf:
            papers_with_pdf += 1

        if paper.year:
            by_year[paper.year] += 1
        if paper.venue:
            by_venue[paper.venue] += 1
            if paper.year:
                by_year_venue[(paper.year, paper.venue)] += 1
                if has_pdf:
                    by_year_venue_with_pdf[(paper.year, paper.venue)] += 1

    # Prepare aggregated output
    aggregated = {
        "total_papers": len(unique_papers),
        "papers_with_pdf": papers_with_pdf,
        "by_year": dict(sorted(by_year.items())),
        "by_venue": dict(sorted(by_venue.items(), key=lambda x: x[1], reverse=True)),
        "by_year_venue": {
            f"{year}|{venue}": count
            for (year, venue), count in sorted(by_year_venue.items())
        },
        "by_year_venue_with_pdf": {
            f"{year}|{venue}": count
            for (year, venue), count in sorted(by_year_venue_with_pdf.items())
        },
    }

    # Save aggregated counts
    aggregated_file.parent.mkdir(parents=True, exist_ok=True)
    with open(aggregated_file, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)
    console.print(f"[green]Saved aggregated counts to {aggregated_file}[/green]")

    # Display summary
    console.print("\n[bold cyan]Summary by Year:[/bold cyan]")
    for year in sorted(by_year.keys()):
        console.print(f"  {year}: {by_year[year]} papers")

    console.print("\n[bold cyan]Summary by Venue (Top 20):[/bold cyan]")
    for venue, count in sorted(by_venue.items(), key=lambda x: x[1], reverse=True)[:20]:
        console.print(f"  {venue}: {count} papers")


if __name__ == "__main__":
    app()
