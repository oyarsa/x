"""Like `head`, but for JSON files with arrays.

Example:

    $ jhead file.json     # first 10 items of the file
    $ jhead file.json 5   # first 5 items of the file
    $ echo ... | jhead    # first 10 items from stdin
    $ echo ... | jhead 5  # first 5 items from stdin
"""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)


@app.command(help=__doc__)
def main(
    path: Annotated[
        Path,
        typer.Argument(
            help='Path to JSON file, or "-" for stdin', allow_dash=True, file_okay=True
        ),
    ] = Path("-"),
    count: Annotated[int, typer.Argument(help="Number of items to show")] = 5,
) -> None:
    """Display first `count` items in a JSON array from a file or stdin."""
    data = json.loads(sys.stdin.read() if path == Path("-") else path.read_bytes())
    print(json.dumps(data[:count], indent=4))


if __name__ == "__main__":
    app()
