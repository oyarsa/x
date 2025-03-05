#!/usr/bin/env python3

"""Rename keys in each object in a JSON file.

Input must be a JSON file with a list of objects. The keys to rename must exist in
all objects. The output file will also be a list of objects with keys specified.

The mini-language for renaming keys is:
- old:new - rename the key 'old' to 'new'
- just_key - keep the key the same

Only the specified keys will be in the output.
"""

import argparse
import json
from dataclasses import dataclass
from typing import TextIO

from scripts.util import HelpOnErrorArgumentParser


@dataclass(frozen=True)
class Args:
    input_file: TextIO
    output_file: TextIO
    rename: list[str]


def main() -> None:
    parser = HelpOnErrorArgumentParser(__doc__)
    parser.add_argument(
        "input_file",
        type=argparse.FileType("r"),
        help="The input JSON file to rename keys in",
    )
    parser.add_argument(
        "output_file",
        type=argparse.FileType("w"),
        help="The output JSON file to write the renamed keys to",
    )
    parser.add_argument(
        "rename",
        type=str,
        nargs="+",
        help="A list of key:value pairs to rename, separated by a colon",
    )
    args = Args(**vars(parser.parse_args()))

    renames: dict[str, str] = {}
    for r in args.rename:
        if ":" not in r:
            renames[r] = r
        else:
            old, new = r.split(":")
            renames[old] = new

    data = json.load(args.input_file)
    new_data = [{new: d[old] for old, new in renames.items()} for d in data]

    json.dump(new_data, args.output_file, indent=2)


if __name__ == "__main__":
    main()
