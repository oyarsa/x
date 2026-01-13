"""Format a Markdown table with proper padding.

Reads a Markdown table from a file or stdin and formats it with aligned columns.

Examples:
    $ uai tablefmt table.md
    $ cat table.md | uai tablefmt
    $ uai tablefmt - < table.md

Input:
    | Name | Value |
    |---|---|
    | foo | 1 |
    | barbaz | 200 |

Output:
    | Name   | Value |
    |--------|-------|
    | foo    | 1     |
    | barbaz | 200   |
"""

import re
from pathlib import Path
from typing import Annotated

import typer

from uai.util import read_text


def parse_table(text: str) -> list[list[str]]:
    """Parse a Markdown table into a list of rows, each containing cell values."""
    rows: list[list[str]] = []

    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Find the first pipe character and strip everything before it
        pipe_idx = line.find("|")
        if pipe_idx == -1:
            continue
        table_part = line[pipe_idx:].strip("|")

        cells = [cell.strip() for cell in table_part.split("|")]
        rows.append(cells)

    return rows


def is_separator_row(row: list[str]) -> bool:
    """Check if a row is a separator row (contains only dashes and colons)."""
    return all(re.fullmatch(r":?-+:?", cell) for cell in row)


def format_table(rows: list[list[str]]) -> str:
    """Format table rows with proper padding."""
    if not rows:
        return ""

    # Calculate the maximum width for each column
    num_cols = max(len(row) for row in rows)
    col_widths = [0] * num_cols

    for row in rows:
        if is_separator_row(row):
            continue
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    # Build the formatted table
    lines: list[str] = []
    for row in rows:
        if is_separator_row(row):
            # Format separator row with dashes matching column widths (no spaces)
            cells = ["-" * (col_widths[i] + 2) for i in range(num_cols)]
            line = "|" + "|".join(cells) + "|"
        else:
            # Pad cells to match column widths
            cells: list[str] = []
            for i in range(num_cols):
                cell = row[i] if i < len(row) else ""
                cells.append(cell.ljust(col_widths[i]))
            line = "| " + " | ".join(cells) + " |"
        lines.append(line)

    return "\n".join(lines)


def main(
    input_path: Annotated[
        Path,
        typer.Argument(
            help="Input file path. Use '-' for stdin (default).", allow_dash=True
        ),
    ] = Path("-"),
) -> None:
    """Format a Markdown table with proper column padding."""
    text = read_text(input_path)
    rows = parse_table(text)

    if not rows:
        typer.echo("No table found in input.", err=True)
        raise typer.Exit(1)

    print(format_table(rows))
