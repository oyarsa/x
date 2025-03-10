"""Estimate the number of tokens in the input file (or stdin) using the GPT-4 tokeniser."""

import sys
from pathlib import Path
from typing import Annotated

import tiktoken
import typer

# GPT-4 and later tokeniser.
_GPT_TOKENISER = tiktoken.get_encoding("cl100k_base")


def main(
    file: Annotated[
        Path | None,
        typer.Argument(help="Path to the file. If not provided, use stdin."),
    ] = None,
):
    if file is None:
        text = sys.stdin.read()
    else:
        text = file.read_text()

    try:
        num_tokens = len(_GPT_TOKENISER.encode(text))
    except Exception:
        num_tokens = len(text.split()) * 1.5

    print(num_tokens)
