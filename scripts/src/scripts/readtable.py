import argparse
import json
from typing import Any, TextIO

from scripts.util import HelpOnErrorArgumentParser


def fit_length(
    data: list[dict[str, Any]], n: int, fill_value: Any = None
) -> list[dict[str, Any]]:
    """Ensures that data has the correct length by either truncating or padding."""
    if len(data) == n:
        return data
    if len(data) > n:
        return data[:n]
    return data + [fill_value] * (n - len(data))


def bool_(value: str) -> bool:
    value = value.lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"could not convert string to bool: {value}")


def clean_value(value: str) -> Any:
    v = value.strip()
    if (v.startswith('"') and v.endswith('"')) or (
        v.startswith("'") and v.endswith("'")
    ):
        return v[1:-1]

    conversion_funcs = [int, float, bool_]
    for func in conversion_funcs:
        try:
            return func(v)
        except ValueError:
            pass

    return v


def parse_data(input: TextIO, separator: str) -> list[dict[str, Any]]:
    lines = input.readlines()
    header = [item.strip() for item in lines[0].strip().split(separator)]

    data: list[dict[str, Any]] = []
    for line_ in lines[1:]:
        line = line_.strip()
        if not line:
            continue

        row = [clean_value(item) for item in line.split(separator)]
        row = fit_length(row, len(header))
        row_data = dict(zip(header, row))
        data.append(row_data)

    return data


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
        "-s",
        "--separator",
        type=str,
        default="\t",
        help="Separator character (default: tab)",
    )
    args = parser.parse_args()

    parsed_data = parse_data(args.input, args.separator)
    print(json.dumps(parsed_data, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
