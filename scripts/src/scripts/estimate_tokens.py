"""Estimate the number of tokens in the input file (or stdin) using the GPT-4 tokeniser."""

import sys
from pathlib import Path
from typing import Annotated

import tiktoken
import typer

# GPT-4 and later tokeniser.
_GPT_TOKENISER = tiktoken.get_encoding("cl100k_base")

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


@app.command(help=__doc__)
def calculate(
    file: Annotated[
        Path | None,
        typer.Argument(help="Path to the file. If not provided, use stdin."),
    ] = None,
):
    if file is None:
        text = sys.stdin.read()
    else:
        text = file.read_text()

    tokens = _GPT_TOKENISER.encode(text)

    print(len(tokens))


if __name__ == "__main__":
    app()
