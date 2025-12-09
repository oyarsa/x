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

import httpx
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn

app = typer.Typer(help="Count papers from conferences using Semantic Scholar API")
console = Console()


@dataclass
class Paper:
    """Represents a paper with relevant metadata."""

    paper_id: str
    title: str
    year: int | None
    venue: str | None
    citation_count: int | None
    fields_of_study: list[str]
    url: str


@dataclass
class ConferencePattern:
    """Pattern for identifying a conference across different naming conventions."""

    name: str  # Canonical name for grouping
    venue_patterns: list[str]  # Substrings to match in venue names


# Comprehensive list of conferences to search for
# Each conference may have multiple name variations across years
CONFERENCE_PATTERNS: list[ConferencePattern] = [
    # *ACL Conferences
    ConferencePattern(
        name="ACL",
        venue_patterns=[
            "Annual Meeting of the Association for Computational Linguistics",
            "ACL",
        ],
    ),
    ConferencePattern(
        name="EMNLP",
        venue_patterns=[
            "Conference on Empirical Methods in Natural Language Processing",
            "Empirical Methods in Natural Language Processing",
            "EMNLP",
        ],
    ),
    ConferencePattern(
        name="NAACL",
        venue_patterns=[
            "North American Chapter of the Association for Computational Linguistics",
            "NAACL",
        ],
    ),
    ConferencePattern(
        name="EACL",
        venue_patterns=[
            "Conference of the European Chapter of the Association for Computational Linguistics",
            "European Chapter of the Association for Computational Linguistics",
            "EACL",
        ],
    ),
    ConferencePattern(
        name="AACL-IJCNLP",
        venue_patterns=[
            "AACL",
            "International Joint Conference on Natural Language Processing",
            "IJCNLP",
            "AACL-IJCNLP",
        ],
    ),
    ConferencePattern(
        name="COLING",
        venue_patterns=[
            "International Conference on Computational Linguistics",
            "COLING",
        ],
    ),
    ConferencePattern(
        name="CoNLL",
        venue_patterns=[
            "Conference on Computational Natural Language Learning",
            "CoNLL",
        ],
    ),
    ConferencePattern(
        name="SEM",
        venue_patterns=[
            "Joint Conference on Lexical and Computational Semantics",
            "SEM",
            "StarSEM",
        ],
    ),
    # Major ML/AI Conferences
    ConferencePattern(
        name="NeurIPS",
        venue_patterns=[
            "Neural Information Processing Systems",
            "NeurIPS",
            "NIPS",
        ],
    ),
    ConferencePattern(
        name="ICML",
        venue_patterns=[
            "International Conference on Machine Learning",
            "ICML",
        ],
    ),
    ConferencePattern(
        name="ICLR",
        venue_patterns=[
            "International Conference on Learning Representations",
            "ICLR",
        ],
    ),
    ConferencePattern(
        name="AAAI",
        venue_patterns=[
            "AAAI Conference on Artificial Intelligence",
            "AAAI",
        ],
    ),
    ConferencePattern(
        name="IJCAI",
        venue_patterns=[
            "International Joint Conference on Artificial Intelligence",
            "IJCAI",
        ],
    ),
    ConferencePattern(
        name="KDD",
        venue_patterns=[
            "Knowledge Discovery and Data Mining",
            "KDD",
            "ACM SIGKDD",
        ],
    ),
    ConferencePattern(
        name="WWW",
        venue_patterns=[
            "The Web Conference",
            "WWW",
            "World Wide Web Conference",
        ],
    ),
    ConferencePattern(
        name="SIGIR",
        venue_patterns=[
            "Annual International ACM SIGIR Conference on Research and Development in Information Retrieval",
            "SIGIR",
        ],
    ),
]


class SemanticScholarAPI:
    """Async client for Semantic Scholar API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.headers = {"x-api-key": api_key}
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0

    async def __aenter__(self) -> "SemanticScholarAPI":
        """Initialise the HTTP client."""
        self._client = httpx.AsyncClient(timeout=30.0, headers=self.headers)
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _rate_limit(self) -> None:
        """Ensure at least 3 seconds between requests."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < 3.0:
                await asyncio.sleep(3.0 - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def search_papers_bulk(
        self,
        venue: str,
        year: str | None = None,
        token: str | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search for papers using the Semantic Scholar bulk API.

        Args:
            venue: Venue name to filter by
            year: Year or year range (e.g., "2024" or "2020-2025")
            token: Continuation token for pagination
            fields: List of fields to return

        Returns:
            API response dictionary with total, data, and optional token
        """
        if self._client is None:
            raise RuntimeError("API client not initialised. Use 'async with' context.")

        await self._rate_limit()

        if fields is None:
            fields = [
                "paperId",
                "title",
                "year",
                "venue",
                "citationCount",
                "fieldsOfStudy",
                "url",
            ]

        params: dict[str, str] = {
            "venue": venue,
            "fields": ",".join(fields),
        }

        if year:
            params["year"] = year

        if token:
            params["token"] = token

        response = await self._client.get(
            f"{self.BASE_URL}/paper/search/bulk",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_papers_by_venues(
        self,
        venues: list[str],
        year_range: tuple[int, int] | None = None,
    ) -> list[Paper]:
        """Get all papers from multiple venues using bulk API.

        Args:
            venues: List of venue names to search for (comma-separated in API)
            year_range: Optional (start_year, end_year) tuple

        Returns:
            List of Paper objects
        """
        papers: list[Paper] = []
        token: str | None = None

        # Build year query if specified
        year_query: str | None = None
        if year_range:
            start, end = year_range
            year_query = f"{start}-{end}"

        # Join venues with comma for API
        venue_query = ",".join(venues)

        while True:
            try:
                result = await self.search_papers_bulk(
                    venue=venue_query,
                    year=year_query,
                    token=token,
                )

                data = result.get("data", [])
                for item in data:
                    paper = Paper(
                        paper_id=item.get("paperId", ""),
                        title=item.get("title", ""),
                        year=item.get("year"),
                        venue=item.get("venue"),
                        citation_count=item.get("citationCount"),
                        fields_of_study=item.get("fieldsOfStudy") or [],
                        url=item.get("url", ""),
                    )
                    papers.append(paper)

                # Check for continuation token
                token = result.get("token")
                if not token:
                    break

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    console.print(
                        "[yellow]Rate limited, waiting 60 seconds...[/yellow]"
                    )
                    await asyncio.sleep(60)
                    continue
                console.print(f"[red]HTTP error for venues '{venue_query}': {e}[/red]")
                break
            except Exception as e:
                console.print(f"[red]Error for venues '{venue_query}': {e}[/red]")
                break

        return papers


async def fetch_conference_papers(
    api: SemanticScholarAPI,
    conference: ConferencePattern,
    year_range: tuple[int, int] | None,
    progress: Progress,
    task_id: TaskID,
) -> list[Paper]:
    """Fetch papers for a specific conference pattern.

    Args:
        api: SemanticScholarAPI instance
        conference: Conference pattern to search for
        year_range: Optional year range to filter
        progress: Rich progress bar
        task_id: Task ID for progress updates

    Returns:
        List of papers matching the conference
    """
    progress.update(task_id, description=f"[cyan]Fetching {conference.name}...[/cyan]")

    # Fetch all venue patterns in a single batched request
    papers = await api.get_papers_by_venues(
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

    return unique_papers


async def fetch_all_conferences(
    api: SemanticScholarAPI,
    conferences: list[ConferencePattern],
    year_range: tuple[int, int] | None,
) -> list[Paper]:
    """Fetch papers for all conferences concurrently with rate limiting.

    Args:
        api: SemanticScholarAPI instance
        conferences: List of conference patterns to search
        year_range: Optional year range to filter

    Returns:
        List of all papers from all conferences
    """
    async with api:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            tasks: list[asyncio.Task[list[Paper]]] = []
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

    all_papers: list[Paper] = []
    for papers in results:
        all_papers.extend(papers)

    return all_papers


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
        int | None,
        typer.Option(
            "--start-year",
            help="Start year for filtering (inclusive)",
        ),
    ] = None,
    end_year: Annotated[
        int | None,
        typer.Option(
            "--end-year",
            help="End year for filtering (inclusive)",
        ),
    ] = None,
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
    all_papers = asyncio.run(
        fetch_all_conferences(api, selected_conferences, year_range)
    )

    # Remove duplicates across conferences
    unique_papers: dict[str, Paper] = {}
    for paper in all_papers:
        if paper.paper_id not in unique_papers:
            unique_papers[paper.paper_id] = paper

    console.print(f"\n[green]Total unique papers found: {len(unique_papers)}[/green]")

    # Save individual paper records
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

    for paper in unique_papers.values():
        if paper.year:
            by_year[paper.year] += 1
        if paper.venue:
            by_venue[paper.venue] += 1
            if paper.year:
                by_year_venue[(paper.year, paper.venue)] += 1

    # Prepare aggregated output
    aggregated = {
        "total_papers": len(unique_papers),
        "by_year": dict(sorted(by_year.items())),
        "by_venue": dict(sorted(by_venue.items(), key=lambda x: x[1], reverse=True)),
        "by_year_venue": {
            f"{year}|{venue}": count
            for (year, venue), count in sorted(by_year_venue.items())
        },
    }

    # Save aggregated counts
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
