"""CLI interface — typer app with sync, list, show, clean commands."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from parch.archive import ArchivePaths
    from parch.models import ArchivedTask, IndexEntry

import typer

from parch.archive import (
    ArchiveLockError,
    load_index,
    load_task,
    rebuild_index,
    resolve_archive_dir,
)
from parch.config import load_config
from parch.display import format_task_table, print_task_output
from parch.pueue import PueueError, PueueParseError
from parch.sync import sync

app = typer.Typer(
    name="parch",
    help="Pueue archive tool — persist task metadata and logs.",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


@dataclass
class AppState:
    """Global options resolved from CLI flags and config file."""

    archive_dir: str | None = None
    pueue_bin: str = "pueue"
    do_sync: bool = True
    colour: str = "auto"
    pager: str = "auto"
    verbose: bool = False
    quiet: bool = False


def _get_state(ctx: typer.Context) -> AppState:
    """Extract AppState from the typer context."""
    state: AppState = ctx.obj
    return state


def _auto_sync(state: AppState) -> None:
    """Run implicit sync if enabled."""
    if not state.do_sync:
        return

    sync(
        paths=resolve_archive_dir(state.archive_dir),
        pueue_bin=state.pueue_bin,
        verbose=state.verbose,
        quiet=state.quiet,
    )


@app.callback()
def app_callback(
    ctx: typer.Context,
    archive_dir: Annotated[
        str | None,
        typer.Option("--archive-dir", help="Override archive root directory."),
    ] = None,
    pueue_bin: Annotated[
        str | None,
        typer.Option("--pueue-bin", help="Path to pueue binary."),
    ] = None,
    sync_flag: Annotated[
        bool,
        typer.Option("--sync/--no-sync", help="Enable/disable implicit sync."),
    ] = True,
    color: Annotated[
        str,
        typer.Option("--color", help="Colour output: auto|always|never."),
    ] = "",
    pager: Annotated[
        str,
        typer.Option("--pager", help="Pager: auto|always|never."),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Verbose output."),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress informational output."),
    ] = False,
) -> None:
    """Global options applied before every command."""
    config = load_config()

    ctx.obj = AppState(
        archive_dir=archive_dir or config.archive_dir,
        pueue_bin=pueue_bin or config.pueue_bin,
        do_sync=sync_flag,
        colour=color or config.colour,
        pager=pager or config.pager,
        verbose=verbose,
        quiet=quiet,
    )


@app.command("sync")
def sync_cmd(
    ctx: typer.Context,
    include_running: Annotated[
        bool,
        typer.Option("--include-running", help="Include non-terminal tasks."),
    ] = False,
    timeout: Annotated[
        int | None,
        typer.Option("--timeout", help="Pueue invocation timeout in seconds."),
    ] = None,
) -> None:
    """Fetch current pueue log and merge into archive."""
    state = _get_state(ctx)
    result = sync(
        paths=resolve_archive_dir(state.archive_dir),
        pueue_bin=state.pueue_bin,
        include_running=include_running,
        timeout=timeout,
        verbose=True,
        quiet=state.quiet,
    )

    if not state.quiet:
        print(
            f"Synced: {result.new_tasks} new, "
            f"{result.updated_tasks} updated, "
            f"{result.unchanged_tasks} unchanged"
            + (
                f", {result.skipped_running} running (skipped)"
                if result.skipped_running
                else ""
            ),
        )
    sys.exit(0)


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    from_date: Annotated[
        str | None,
        typer.Option("--from", help="Filter: start date (YYYY-MM-DD or datetime)."),
    ] = None,
    to_date: Annotated[
        str | None,
        typer.Option("--to", help="Filter: end date (YYYY-MM-DD or datetime)."),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option("--since", help="Filter: relative window (e.g. 7d, 24h)."),
    ] = None,
    today: Annotated[
        bool,
        typer.Option("--today", help="Filter: today's tasks only."),
    ] = False,
    yesterday: Annotated[
        bool,
        typer.Option("--yesterday", help="Filter: yesterday's tasks only."),
    ] = False,
    last_week: Annotated[
        bool,
        typer.Option("--last-week", help="Filter: last 7 days."),
    ] = False,
    status: Annotated[
        list[str] | None,
        typer.Option("--status", help="Filter by status (repeatable)."),
    ] = None,
    group: Annotated[
        list[str] | None,
        typer.Option("--group", help="Filter by group (repeatable)."),
    ] = None,
    cmd: Annotated[
        str | None,
        typer.Option("--cmd", help="Filter: command substring."),
    ] = None,
    cwd: Annotated[
        str | None,
        typer.Option("--cwd", help="Filter: cwd substring."),
    ] = None,
    format_: Annotated[
        str,
        typer.Option("--format", help="Output format: table|json."),
    ] = "table",
    sort: Annotated[
        str,
        typer.Option("--sort", help="Sort by: created|start|end."),
    ] = "end",
    reverse: Annotated[
        bool,
        typer.Option("--reverse", help="Reverse sort order."),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Limit number of results."),
    ] = None,
) -> None:
    """List archived tasks."""
    state = _get_state(ctx)
    _auto_sync(state)
    paths = resolve_archive_dir(state.archive_dir)
    entries = load_index(paths)

    # Apply filters
    entries = _apply_time_filters(
        entries, from_date, to_date, since, today, yesterday, last_week
    )

    if status:
        status_set = {s.lower() for s in status}
        entries = [e for e in entries if e.status in status_set]

    if group:
        group_set = set(group)
        entries = [e for e in entries if e.group in group_set]

    if cmd:
        entries = [e for e in entries if cmd in e.command]

    if cwd:
        entries = [e for e in entries if cwd in e.cwd]

    # Sort
    entries = _sort_entries(entries, sort, reverse)

    # Limit
    entries = entries[:limit]

    # Output
    if format_ == "json":
        print(json.dumps([e.model_dump() for e in entries], indent=2))
    elif not entries:
        if not state.quiet:
            print("No archived tasks found.")
    else:
        format_task_table(entries, colour=state.colour)


@app.command()
def show(
    ctx: typer.Context,
    archive_id: Annotated[str, typer.Argument(help="Archive ID (or prefix).")],
    meta: Annotated[
        bool,
        typer.Option("--meta", help="Prepend metadata header."),
    ] = False,
    raw_json: Annotated[
        bool,
        typer.Option("--json", help="Dump full stored task JSON."),
    ] = False,
    no_ansi: Annotated[
        bool,
        typer.Option("--no-ansi", help="Strip ANSI escape codes from output."),
    ] = False,
    no_pager: Annotated[
        bool,
        typer.Option("--no-pager", help="Force no pager."),
    ] = False,
) -> None:
    """Show stored output for a specific archived task."""
    state = _get_state(ctx)
    _auto_sync(state)
    paths = resolve_archive_dir(state.archive_dir)

    task = _resolve_task(paths, archive_id)
    if task is None:
        print(f"Error: no task found matching '{archive_id}'", file=sys.stderr)
        sys.exit(1)

    if raw_json:
        print(json.dumps(task.model_dump(), indent=2))
        return

    pager_mode = "never" if no_pager else state.pager
    print_task_output(
        task,
        show_meta=meta,
        no_ansi=no_ansi,
        use_pager=pager_mode,
        colour=state.colour,
    )


@app.command()
def clean(
    ctx: typer.Context,
    args: Annotated[
        list[str] | None,
        typer.Argument(help="Arguments forwarded to pueue clean."),
    ] = None,
) -> None:
    """Sync then run pueue clean with forwarded arguments."""
    state = _get_state(ctx)
    _auto_sync(state)

    cmd = [state.pueue_bin, "clean"]
    if args:
        cmd.extend(args)

    if not state.quiet:
        print(f"Running: {' '.join(cmd)}", file=sys.stderr)

    result = subprocess.run(cmd, check=False)
    sys.exit(result.returncode)


@app.command("rebuild-index")
def rebuild_index_cmd(ctx: typer.Context) -> None:
    """Rebuild index.jsonl from task files."""
    state = _get_state(ctx)
    paths = resolve_archive_dir(state.archive_dir)
    entries = rebuild_index(paths)
    if not state.quiet:
        print(f"Rebuilt index with {len(entries)} entries.")


def _resolve_task(
    paths: ArchivePaths,
    archive_id: str,
) -> ArchivedTask | None:
    """Resolve a task by exact ID or prefix match."""
    # Try exact match first
    task = load_task(paths, archive_id)
    if task is not None:
        return task

    # Try prefix match against index
    entries = load_index(paths)
    matches = [e for e in entries if e.archive_id.startswith(archive_id)]

    if len(matches) == 1:
        return load_task(paths, matches[0].archive_id)

    if len(matches) > 1:
        msg = (
            f"Ambiguous prefix '{archive_id}' matches "
            f"{len(matches)} tasks. Be more specific."
        )
        raise typer.BadParameter(msg)

    return None


def _apply_time_filters(
    entries: list[IndexEntry],
    from_date: str | None,
    to_date: str | None,
    since: str | None,
    today: bool,
    yesterday: bool,
    last_week: bool,
) -> list[IndexEntry]:
    """Apply time-based filters to entries."""
    now = datetime.now(tz=UTC)

    if today:
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return [e for e in entries if _entry_time(e) >= start_of_day]

    if yesterday:
        start_of_yesterday = (now - timedelta(days=1)).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            e for e in entries if start_of_yesterday <= _entry_time(e) < start_of_today
        ]

    if last_week:
        week_ago = now - timedelta(days=7)
        return [e for e in entries if _entry_time(e) >= week_ago]

    if since:
        delta = _parse_duration(since)
        cutoff = now - delta
        return [e for e in entries if _entry_time(e) >= cutoff]

    if from_date or to_date:
        result = entries
        if from_date:
            from_dt = _parse_date(from_date)
            result = [e for e in result if _entry_time(e) >= from_dt]
        if to_date:
            to_dt = _parse_date(to_date)
            result = [e for e in result if _entry_time(e) <= to_dt]
        return result

    return entries


def _entry_time(entry: IndexEntry) -> datetime:
    """Get the best available timestamp for time filtering.

    Prefers end_at, then start_at, then created_at.
    """
    ts = entry.end_at or entry.start_at or entry.created_at
    return _parse_iso(ts)


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp, handling various formats."""
    if not ts:
        return datetime.min.replace(tzinfo=UTC)

    # Handle trailing Z
    ts = ts.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


def _parse_date(date_str: str) -> datetime:
    """Parse a date or datetime string into a timezone-aware datetime."""
    # Try datetime first
    try:
        return datetime.fromisoformat(date_str).replace(tzinfo=UTC)
    except ValueError:
        pass

    # Try date-only
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")  # noqa: DTZ007
        return dt.replace(tzinfo=UTC)
    except ValueError:
        raise typer.BadParameter(f"Cannot parse date '{date_str}'") from None


def _parse_duration(duration_str: str) -> timedelta:
    """Parse a duration string like '7d', '24h', '30m' into a timedelta."""
    match = re.match(r"^(\d+)([dhms])$", duration_str)
    if not match:
        msg = f"Invalid duration '{duration_str}'. Use format like 7d, 24h, 30m, 60s."
        raise typer.BadParameter(msg)

    value = int(match.group(1))
    unit = match.group(2)

    unit_map = {
        "d": "days",
        "h": "hours",
        "m": "minutes",
        "s": "seconds",
    }
    return timedelta(**{unit_map[unit]: value})


def _sort_entries(
    entries: list[IndexEntry],
    sort_by: str,
    reverse: bool,
) -> list[IndexEntry]:
    """Sort entries by the specified field."""

    def sort_key(entry: IndexEntry) -> str:
        if sort_by == "created":
            return entry.created_at or ""
        if sort_by == "start":
            return entry.start_at or ""
        return entry.end_at or entry.start_at or entry.created_at or ""

    return sorted(entries, key=sort_key, reverse=not reverse)


_EXIT_CODES = {
    PueueError: 2,
    PueueParseError: 3,
    ArchiveLockError: 4,
}


def main() -> None:
    """Entry point that wraps the typer app with error handling."""
    try:
        app()
    except (PueueError, PueueParseError, ArchiveLockError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(_EXIT_CODES.get(type(exc), 1))
