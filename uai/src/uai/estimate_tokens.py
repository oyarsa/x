"""Estimate the number of tokens in the input file (or stdin) using the GPT-4 tokeniser."""

from pathlib import Path
from typing import Annotated

import tiktoken
import typer

from uai.util import read_text

# GPT-4 and later tokeniser.
_GPT_TOKENISER = tiktoken.get_encoding("o200k_base")


def main(
    path: Annotated[
        Path,
        typer.Argument(help="Path to the file. If not provided, use stdin."),
    ] = Path("-"),
):
    text = read_text(path)

    try:
        num_tokens = len(_GPT_TOKENISER.encode(text))
    except Exception:
        num_tokens = len(text.split()) * 1.5

    print(num_tokens)
