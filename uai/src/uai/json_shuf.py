"""Given a JSON file containing a list, shuffles the contents of the list.

The input JSON file can be provided as an argument or piped in through stdin.
The output JSON file can be provided as an argument or piped out through stdout.

A random seed can be provided to ensure reproducibility.
"""

import json
import random
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from beartype.door import is_bearable


def main(
    input: Annotated[Path, typer.Argument(help="Input JSON file")] = Path("-"),
    output: Annotated[Path, typer.Argument(help="Output JSON file")] = Path("-"),
    seed: Annotated[int, typer.Option(help="Random seed")] = 0,
    k: Annotated[
        int | None, typer.Option(help="Size of the sample to draw from the dataset")
    ] = None,
) -> None:
    if input.name == "-":
        data = json.load(sys.stdin)
    else:
        data = json.loads(input.read_text())

    if not is_bearable(data, list[Any]):
        raise ValueError("Invalid JSON format. Expected a list.")

    random.seed(seed)
    if k:
        data = random.sample(data, k=k)
    else:
        random.shuffle(data)

    if output.name == "-":
        json.dump(data, sys.stdout, indent=2)
    else:
        output.write_text(json.dumps(data, indent=2))
