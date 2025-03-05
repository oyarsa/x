"""Analyse JSON data to count occurrences of values for a specified key."""

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Annotated, Any, cast

import typer

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


@app.command(help=__doc__)
def main(
    input_path: Annotated[
        Path,
        typer.Argument(
            help='Path to JSON file, or "-" for stdin', allow_dash=True, file_okay=True
        ),
    ],
    key: Annotated[str, typer.Argument(help="Key to analyse in each object")],
) -> None:
    """Display occurrence statistics for values of a key in JSON data.

    Reads JSON data from a file or stdin, counts occurrences of values for the specified
    key, and outputs statistics including counts and percentages.
    """
    try:
        show_frequencies(input_path, key)
    except (json.JSONDecodeError, KeyError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)


def show_frequencies(path: Path, key: str) -> None:
    """Show frequency of `key` values in `path` file.

    Raises:
        JSONDecodeError: If the input is not valid JSON
        TypeError: If the data is not a list of objects
    """
    data = json.loads(sys.stdin.read() if path == Path("-") else path.read_bytes())

    if not (isinstance(data, list) and isinstance(data[0], dict)):
        raise TypeError("Error: Input must be a list of objects")

    data = cast(list[dict[str, Any]], data)
    counts = Counter(item.get(key) for item in data)

    typer.echo(display_statistics(counts))


def display_statistics(counts: Counter[Any]) -> str:
    """Build a formatted string of statistics about the counted values."""
    if not counts:
        return "No data to analyse"

    total = sum(counts.values())

    counts_str = [(str(value), count) for value, count in counts.most_common()]
    val_maxlen = max(len(val) for val, _ in counts_str)
    padding = max(val_maxlen, len("Total")) + 1

    lines = [
        f"{value:<{padding}}: {count} ({count / total:.2%})"
        for value, count in counts_str
    ]
    lines.extend(["", f"{"Total":<{padding}}: {total}"])

    return "\n".join(lines)


if __name__ == "__main__":
    app()
