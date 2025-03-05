#!/usr/bin/env python3

"""Rename keys in each object in a JSON file.

Input must be a JSON file with a list of objects. The keys to rename must exist in
all objects. The output file will also be a list of objects with keys specified.

The mini-language for renaming keys is:
- old:new - rename the key 'old' to 'new'
- just_key - keep the key the same

Only the specified keys will be in the output.
"""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer


def main(
    input_file: Annotated[
        Path, typer.Argument(help="The input JSON file to rename keys in")
    ] = Path("-"),
    output_file: Annotated[
        Path, typer.Argument(help="The output JSON file to write the renamed keys to")
    ] = Path("-"),
    rename: Annotated[
        list[str] | None,
        typer.Argument(
            help="A list of key:value pairs to rename, separated by a colon"
        ),
    ] = None,
) -> None:
    if input_file.name == "-":
        data = json.load(sys.stdin)
    else:
        data = json.loads(input_file.read_bytes())

    rename = rename or []

    renames: dict[str, str] = {}
    for r in rename:
        if ":" not in r:
            renames[r] = r
        else:
            old, new = r.split(":")
            renames[old] = new

    new_data = [{new: d[old] for old, new in renames.items()} for d in data]

    if output_file.name == "-":
        json.dump(new_data, sys.stdout, indent=2)
    else:
        output_file.write_text(json.dumps(new_data, indent=2))
