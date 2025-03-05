#!/usr/bin/env python3
"""Get blame on file with special colourful format."""

import re
import subprocess
import sys
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer


class Colour(Enum):
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    RESET = "\033[0m"


def prettify(text: str, width: int, color_code: Colour) -> str:
    """Pad the text to a fixed width and apply colour."""
    padded_text = text.ljust(width)
    return f"{color_code.value}{padded_text}{Colour.RESET.value}"


app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


@app.command(help=__doc__)
def main(
    file: Annotated[Path, typer.Argument(help="File to get blame", exists=True)],
) -> None:
    try:
        output = subprocess.check_output(
            ["git", "blame", "--line-porcelain", str(file)],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        sys.exit(f"Error running git blame:\n{e.output.strip()}")
    except FileNotFoundError:
        sys.exit("Git is not installed or not found in PATH.")

    entries: list[dict[str, str]] = []

    lines = output.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^[0-9a-f]{40}", line):
            # Start of a new entry
            parts = line.split()
            commit_hash = parts[0]
            final_lineno = parts[2]

            # Initialize variables
            author = ""
            summary = ""
            fname = ""
            code_line = ""

            i += 1
            # Read the key-value pairs until we get to the code line
            while (
                i < len(lines)
                and not lines[i].startswith("\t")
                and not re.match(r"^[0-9a-f]{40}", lines[i])
            ):
                line = lines[i]
                if line.startswith("author "):
                    author = line[len("author ") :]
                elif line.startswith("summary "):
                    summary = line[len("summary ") :]
                elif line.startswith("filename "):
                    fname = line[len("filename ") :]
                i += 1

            # Now, the code line starts with '\t'
            if i < len(lines) and lines[i].startswith("\t"):
                code_line = lines[i][1:]  # Skip the '\t'
            else:
                # Handle case where code line is missing
                code_line = ""

            # Collect the entry without truncating yet
            entries.append(
                {
                    "short_hash": commit_hash[:8],
                    "author": author,
                    "summary": summary,
                    "filename": fname,
                    "lineno": final_lineno,
                    "code_line": code_line,
                }
            )
            i += 1
        else:
            i += 1  # Skip lines that don't match

    # Define maximum allowed widths for each field
    max_widths = {
        "short_hash": 10,
        "filename": 30,
        "author": 20,
        "summary": 50,
        "lineno": 6,
    }

    # Compute the maximum length for each field, up to the maximum allowed width
    field_lengths = {
        field: min(
            max(len(entry[field]) for entry in entries),
            max_widths[field],
        )
        for field in ["short_hash", "filename", "author", "summary", "lineno"]
    }

    # Truncate the fields in entries according to the maximum allowed widths
    for entry in entries:
        for field in ["author", "summary", "filename"]:
            if len(entry[field]) > max_widths[field]:
                entry[field] = entry[field][: max_widths[field] - 1] + "…"

    typer.echo_via_pager(display(entries, field_lengths))


def display(
    entries: Iterable[dict[str, str]], field_lengths: dict[str, int]
) -> Iterable[str]:
    """Display entries with calculated column widths. Yields one line at a time."""
    colours = {
        "short_hash": Colour.RED,
        "filename": Colour.BLUE,
        "author": Colour.GREEN,
        "summary": Colour.YELLOW,
        "lineno": Colour.MAGENTA,
    }
    for entry in entries:
        line = " ".join(
            prettify(entry[col], field_lengths[col], colours[col]) for col in colours
        )
        yield f"{line} {entry["code_line"]}\n"


if __name__ == "__main__":
    app()
