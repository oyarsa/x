"""Calculate the number of tokens for items in a datasetm using a Hugging Face model.

By default, the script prints the number of tokens in the longest sequence. It can
also print the longest sequence itself.

It can also save a new JSON file with the added token count for each item.

The input format a JSON file with a list of objects. Each object must have an "input"
key with the text to tokenise.
"""

# pyright: basic
import json
import os
import sys
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from beartype.door import is_bearable

# Disable "None of PyTorch, TensorFlow >= 2.0, or Flax have been found." warning.
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
from transformers import AutoTokenizer


def longest_sequence(
    model_name: str, data: list[dict[str, Any]]
) -> tuple[list[str], list[str]]:
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    longest_seq: list[str] | None = None
    longest_split: list[str] | None = None

    for item in data:
        tokens = tokenizer.tokenize(item["input"].strip())
        if longest_seq is None or len(tokens) > len(longest_seq):
            longest_seq = cast(list[str], tokens)
            longest_split = item["input"].strip().split()

    assert longest_seq is not None and longest_split is not None, "No data provided."
    return longest_seq, longest_split


def main(
    input: Annotated[Path, typer.Argument(help="Input file path")] = Path("-"),
    model: Annotated[
        str, typer.Option("--model", "-m", help="Model name.")
    ] = "google/flan-t5-large",
    print_sequence: Annotated[
        bool, typer.Option("--print-sequence", "-P", help="Print the longest sequence")
    ] = False,
) -> None:
    if input.name == "-":
        data = json.load(sys.stdin)
    else:
        data = json.loads(input.read_text())

    data_keys = {"input"}
    if not is_bearable(data, list[dict[str, Any]]):
        raise SystemExit("Invalid JSON format. Expected a list of objects.")
    if missing := data_keys - data[0].keys():
        raise SystemExit(f"Invalid JSON format. Missing keys: {missing}.")

    longest_seq, longest_split = longest_sequence(model, data)

    if print_sequence:
        print(longest_seq)
    print(f"{len(longest_seq)} tokens.")
    print(f"{len(longest_split)} tokens (split).")
