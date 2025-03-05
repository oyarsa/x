"""Calculate the number of tokens for items in a datasetm using a Hugging Face model.

By default, the script prints the number of tokens in the longest sequence. It can
also print the longest sequence itself.

It can also save a new JSON file with the added token count for each item.

The input format a JSON file with a list of objects. Each object must have an "input"
key with the text to tokenise.
"""

# pyright: basic
import argparse
import json
import os
from typing import Any, cast

from beartype.door import is_bearable

from scripts.util import HelpOnErrorArgumentParser

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


def main() -> None:
    parser = HelpOnErrorArgumentParser(__doc__)
    parser.add_argument(
        "input",
        type=argparse.FileType("r"),
        help="Input file path",
        nargs="?",
        default="-",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="google/flan-t5-large",
        help="Model name. Default: %(default)s.",
    )
    parser.add_argument(
        "--print-sequence",
        "-P",
        help="Print the longest sequence",
        action="store_true",
    )
    args = parser.parse_args()

    data = json.load(args.input)

    data_keys = {"input"}
    if not is_bearable(data, list[dict[str, Any]]):
        raise SystemExit("Invalid JSON format. Expected a list of objects.")
    if missing := data_keys - data[0].keys():
        raise SystemExit(f"Invalid JSON format. Missing keys: {missing}.")

    longest_seq, longest_split = longest_sequence(args.model, data)

    if args.print_sequence:
        print(longest_seq)
    print(f"{len(longest_seq)} tokens.")
    print(f"{len(longest_split)} tokens (split).")


if __name__ == "__main__":
    main()
