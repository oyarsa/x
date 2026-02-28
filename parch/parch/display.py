"""Display formatting — rich tables and pager support."""

from __future__ import annotations

import re
import subprocess
import sys
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

from parch.models import ColourMode

if TYPE_CHECKING:
    from parch.models import ArchivedTask, IndexEntry


def _make_console(colour: ColourMode, **kwargs: Any) -> Console:
    """Create a Console with correct colour handling.

    Rich's force_terminal is a three-way Optional[bool]:
      None = auto-detect, True = force on, False = force off.
    We must pass None for "auto", not False.
    """
    match colour:
        case ColourMode.ALWAYS:
            return Console(force_terminal=True, no_color=False, **kwargs)
        case ColourMode.NEVER:
            return Console(force_terminal=False, no_color=True, **kwargs)
        case ColourMode.AUTO:
            return Console(**kwargs)


def format_task_table(
    entries: list[IndexEntry],
    *,
    colour: ColourMode = ColourMode.AUTO,
) -> None:
    """Print a rich table of index entries to stdout."""
    console = _make_console(colour)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Archive ID", style="dim", no_wrap=True, max_width=14)
    table.add_column("Pueue ID", justify="right", style="bright_cyan", max_width=6)
    table.add_column("Status", max_width=10)
    table.add_column("Group", style="magenta", max_width=12)
    table.add_column("Command", style="white", max_width=50)
    table.add_column("End", style="bright_black", max_width=20)

    for entry in entries:
        status_style = _status_style(entry.status)
        short_id = entry.archive_id[:13]
        cmd_display = _truncate(entry.command, 50)
        end_display = _format_timestamp(entry.end_at or entry.start_at or "")

        table.add_row(
            short_id,
            entry.pueue_task_id,
            f"[{status_style}]{entry.status}[/{status_style}]",
            entry.group,
            cmd_display,
            end_display,
        )

    console.print(table)


def print_task_output(
    task: ArchivedTask,
    *,
    show_meta: bool = False,
    no_ansi: bool = False,
    use_pager: str = "auto",
    colour: ColourMode = ColourMode.AUTO,
) -> None:
    """Print stored task output, optionally with metadata header."""
    strip = no_ansi or colour == ColourMode.NEVER

    output_parts: list[str] = []

    if show_meta:
        output_parts.append(_format_meta_header(task, colour=colour))
        output_parts.append("")

    combined = task.output.combined
    if strip:
        combined = strip_ansi(combined)

    output_parts.append(combined)

    full_output = "\n".join(output_parts)

    if _should_page(full_output, use_pager):
        _page_output(full_output)
    else:
        sys.stdout.write(full_output)
        if not full_output.endswith("\n"):
            sys.stdout.write("\n")


def _format_meta_header(
    task: ArchivedTask, *, colour: ColourMode = ColourMode.AUTO
) -> str:
    """Format a metadata header block for display."""
    console = _make_console(colour, highlight=False)
    status_style = _status_style(task.meta.status)

    with console.capture() as capture:
        console.print(f"[bold]Archive ID:[/bold]  [dim]{task.archive_id}[/dim]")
        console.print(
            f"[bold]Pueue ID:[/bold]   [bright_cyan]{task.source.pueue_task_id}[/bright_cyan]"
        )
        console.print(
            f"[bold]Status:[/bold]     [{status_style}]{task.meta.status}[/{status_style}]"
        )
        console.print(
            f"[bold]Group:[/bold]      [magenta]{task.source.pueue_group}[/magenta]"
        )
        console.print(f"[bold]Command:[/bold]    {task.meta.command}")
        console.print(f"[bold]Directory:[/bold]  {task.meta.cwd}")
        console.print(
            f"[bold]Created:[/bold]    [bright_black]{task.meta.timestamps.created_at}[/bright_black]"
        )
        if task.meta.timestamps.start_at:
            console.print(
                f"[bold]Started:[/bold]    [bright_black]{task.meta.timestamps.start_at}[/bright_black]"
            )
        if task.meta.timestamps.end_at:
            console.print(
                f"[bold]Ended:[/bold]      [bright_black]{task.meta.timestamps.end_at}[/bright_black]"
            )
        console.print("[dim]" + "─" * 60 + "[/dim]")

    return capture.get().rstrip()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _status_style(status: str) -> str:
    """Return a rich style string for a task status."""
    return {
        "success": "green",
        "failed": "red bold",
        "killed": "red",
        "running": "blue",
        "queued": "yellow",
        "paused": "yellow",
        "dependency_failed": "red",
    }.get(status, "white")


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if longer than max_len."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _format_timestamp(ts: str) -> str:
    """Format a timestamp for table display — show date + time, drop timezone."""
    if not ts:
        return ""

    # Remove sub-second precision and timezone for brevity
    # Handle ISO format like "2026-02-28T19:22:11.123456+00:00"
    ts = re.sub(r"\.\d+", "", ts)
    ts = re.sub(r"[+-]\d{2}:\d{2}$", "", ts)
    ts = ts.replace("Z", "")
    return ts.replace("T", " ")


def _should_page(output: str, pager_mode: str) -> bool:
    """Decide whether to use a pager."""
    if pager_mode == "never":
        return False
    if pager_mode == "always":
        return True

    # "auto": page if interactive and output is long
    if not sys.stdout.isatty():
        return False
    return output.count("\n") > 40


def _page_output(text: str) -> None:
    """Pipe output through less with ANSI support."""
    try:
        proc = subprocess.Popen(
            ["less", "-R"],
            stdin=subprocess.PIPE,
        )
        proc.communicate(input=text.encode())
    except FileNotFoundError:
        # less not available, just print
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
