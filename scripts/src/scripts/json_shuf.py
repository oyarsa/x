"""Given a JSON file containing a list, shuffles the contents of the list.

The input JSON file can be provided as an argument or piped in through stdin.
The output JSON file can be provided as an argument or piped out through stdout.

A random seed can be provided to ensure reproducibility.
"""

import json
import random
import sys
from pathlib import Path
from typing import Any

from beartype.door import is_bearable

from scripts.util import HelpOnErrorArgumentParser


def main() -> None:
    parser = HelpOnErrorArgumentParser(__doc__)
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="Path to input JSON file. If not provided, reads from stdin.",
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Path to output JSON file. If not provided, prints to stdout.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed used for shuffling.",
    )
    parser.add_argument(
        "-k", type=int, help="Size of the sample to draw from the dataset."
    )
    args = parser.parse_args()

    if args.input is None:
        data = json.load(sys.stdin)
    else:
        data = json.loads(args.input.read_text())

    if not is_bearable(data, list[Any]):
        raise ValueError("Invalid JSON format. Expected a list.")

    random.seed(args.seed)
    if args.k:
        data = random.sample(data, k=args.k)
    else:
        random.shuffle(data)

    if args.output is None:
        json.dump(data, sys.stdout, indent=2)
    else:
        args.output.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
