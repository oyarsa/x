"""Rich formatting for human-readable search and expand output."""

import json

from rich.console import Console
from rich.text import Text

from cchs.models import ExpandResult, Message, SearchResult

console = Console()


def _format_role(role: str) -> str:
    """Shorten role for display."""
    return "user" if role == "user" else "asst"


def _render_message(msg: Message, *, is_match: bool = False) -> Text:
    """Render a single message as a rich Text."""
    prefix = "\u00bb " if is_match else "  "
    role_tag = f"[{_format_role(msg.role)}]"
    line = Text()
    line.append(prefix, style="bold yellow" if is_match else "")
    line.append(
        f"{role_tag}  ", style="bold cyan" if msg.role == "user" else "bold green"
    )
    line.append(msg.content)
    return line


def display_search_results(results: list[SearchResult]) -> None:
    """Display search results with rich formatting."""
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    for result in results:
        session_short = result.session_id[:8]
        timestamp = result.match.timestamp.strftime("%Y-%m-%d")
        console.rule(f"Session {timestamp} ({session_short})")

        for msg in result.context_before:
            console.print(_render_message(msg))
        console.print(_render_message(result.match, is_match=True))
        for msg in result.context_after:
            console.print(_render_message(msg))

        console.print()


def display_expand_result(result: ExpandResult) -> None:
    """Display expanded context with rich formatting."""
    session_short = result.session_id[:8]
    console.rule(f"Session ({session_short})")

    for msg in result.messages:
        console.print(_render_message(msg))


def print_json_results(results: list[SearchResult]) -> None:
    """Print search results as JSON."""
    data = [r.model_dump(mode="json") for r in results]
    console.print_json(json.dumps(data))


def print_json_expand(result: ExpandResult) -> None:
    """Print expand result as JSON."""
    console.print_json(json.dumps(result.model_dump(mode="json")))
