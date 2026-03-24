"""CLI entry point for cchs — Claude Code History Search."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console
from tqdm import tqdm

from cchs.display import (
    display_expand_result,
    display_search_results,
    print_json_expand,
    print_json_results,
)
from cchs.indexer import DatabaseCorruptError, Indexer
from cchs.log_config import setup_logging
from cchs.project import list_available_projects, resolve_project_dir
from cchs.searcher import Searcher
from cchs.skill import get_skill_content, install_skill
from cchs.utils import make_app

app = make_app("cchs — Claude Code History Search")
console = Console(stderr=True)


def _get_project_dir(project: str | None) -> Path:
    """Resolve the project directory, exiting with actionable error if not found."""
    cwd = Path(project) if project else Path.cwd()

    project_dir = resolve_project_dir(cwd)
    if project_dir is None:
        available = list_available_projects()
        projects_list = ", ".join(available[:10]) if available else "(none)"
        console.print(
            f"[red]Error:[/red] Project directory not found for '{cwd}'. "
            f"Available projects: {projects_list}. "
            "Use --project to specify the correct project path."
        )
        raise typer.Exit(code=1)

    return project_dir


def _ensure_index(project_dir: Path) -> None:
    """Run incremental indexing, creating DB if needed."""
    db_path = project_dir / "search.db"
    is_new = not db_path.exists()

    if is_new:
        console.print("[dim]Indexing conversations for first search...[/dim]")

    try:
        with Indexer.new(db_path) as indexer:
            jsonl_files = sorted(project_dir.glob("*.jsonl"))
            if not jsonl_files:
                console.print(
                    f"[yellow]No conversations found in project "
                    f"'{project_dir.name}'. Verify you are in the correct project "
                    f"directory, or use --project to specify one.[/yellow]"
                )
                raise typer.Exit(code=1)

            for f in tqdm(
                jsonl_files, desc="Indexing", disable=not is_new, file=sys.stderr
            ):
                session_id = f.stem
                indexer.index_file(f, session_id=session_id)

            indexer.cleanup_deleted_files(project_dir)
    except DatabaseCorruptError as exc:
        console.print(
            f"[red]Error:[/red] Database is corrupt at {db_path}. "
            "Run [bold]cchs index --force[/bold] to rebuild."
        )
        raise typer.Exit(code=1) from exc


@app.command()
def search(
    query: str,
    context: Annotated[
        int, typer.Option("--context", "-c", help="Messages before/after each match")
    ] = 3,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 10,
    session: Annotated[
        str | None, typer.Option(help="Restrict to a session ID")
    ] = None,
    since: Annotated[
        datetime | None,
        typer.Option(help="Only search on or after this date (YYYY-MM-DD, inclusive)"),
    ] = None,
    until: Annotated[
        datetime | None,
        typer.Option(help="Only search on or before this date (YYYY-MM-DD, inclusive)"),
    ] = None,
    project: Annotated[
        str | None, typer.Option(help="Project path instead of cwd")
    ] = None,
    output_json: Annotated[bool, typer.Option("--json", help="Output JSON")] = False,
) -> None:
    """Full-text search across project conversations."""
    project_dir = _get_project_dir(project)
    _ensure_index(project_dir)

    db_path = project_dir / "search.db"
    with Searcher.new(db_path) as searcher:
        results = searcher.search(
            query,
            context=context,
            limit=limit,
            session_id=session,
            since=since,
            until=until,
        )

    if output_json:
        print_json_results(results)
    elif not results:
        console.print(
            f"[yellow]No matches for '{query}'. Try broader search terms "
            f"or check --since/--until date range.[/yellow]"
        )
    else:
        display_search_results(results)


@app.command()
def expand(
    uuid: str,
    before: Annotated[int, typer.Option("--before", "-B", help="Messages before")] = 10,
    after: Annotated[int, typer.Option("--after", "-A", help="Messages after")] = 10,
    full: Annotated[bool, typer.Option(help="Return entire session")] = False,
    project: Annotated[
        str | None, typer.Option(help="Project path instead of cwd")
    ] = None,
    output_json: Annotated[bool, typer.Option("--json", help="Output JSON")] = False,
) -> None:
    """Expand context around a specific message."""
    project_dir = _get_project_dir(project)
    _ensure_index(project_dir)

    db_path = project_dir / "search.db"
    with Searcher.new(db_path) as searcher:
        result = searcher.expand(uuid, before=before, after=after, full=full)

    if result is None:
        console.print(
            f"[red]Error:[/red] Message '{uuid}' not found. "
            f"Run [bold]cchs search <query>[/bold] first to find valid message UUIDs."
        )
        raise typer.Exit(code=1)

    if output_json:
        print_json_expand(result)
    else:
        display_expand_result(result)


@app.command()
def index(
    force: Annotated[bool, typer.Option(help="Drop and rebuild DB")] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip confirmation for --force")
    ] = False,
    project: Annotated[
        str | None, typer.Option(help="Project path instead of cwd")
    ] = None,
) -> None:
    """Index project conversations. Incremental by default."""
    project_dir = _get_project_dir(project)
    db_path = project_dir / "search.db"

    if force:
        if not yes:
            confirm = typer.confirm(
                f"This will delete and rebuild {db_path}. Continue?"
            )
            if not confirm:
                raise typer.Abort
        if db_path.exists():
            db_path.unlink()
        console.print("[dim]Rebuilding index from scratch...[/dim]")

    with Indexer.new(db_path) as indexer:
        jsonl_files = sorted(project_dir.glob("*.jsonl"))

        if not jsonl_files:
            console.print(
                f"[yellow]No conversations found in project '{project_dir.name}'.[/yellow]"
            )
            raise typer.Exit(code=1)

        for f in tqdm(jsonl_files, desc="Indexing", file=sys.stderr):
            session_id = f.stem
            indexer.index_file(f, session_id=session_id)

        indexer.cleanup_deleted_files(project_dir)
        count = indexer.message_count()

    console.print(
        f"[green]Indexed {count} messages from {len(jsonl_files)} sessions.[/green]"
    )


@app.command()
def skill(
    install: Annotated[
        bool, typer.Option("--install", help="Install skill to ~/.claude/skills/")
    ] = False,
) -> None:
    """Show or install the Claude Code skill."""
    if install:
        if install_skill():
            console.print(
                "[green]Skill installed to ~/.claude/skills/search-history/SKILL.md[/green]"
            )
        else:
            raise typer.Exit(code=1)
    else:
        print(get_skill_content())


def main() -> None:
    """Entry point for the cchs CLI."""
    load_dotenv()
    setup_logging()
    app()
