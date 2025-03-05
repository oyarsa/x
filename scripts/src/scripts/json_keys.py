#!/usr/bin/env python3
"Obtain information about the keys of a JSON file containing a list of objects."

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from beartype.door import is_bearable

from scripts.util import HelpOnErrorArgumentParser


@dataclass
class JSONKeyInfo:
    count: int
    type_: set[str]
    nullable: bool


def analyze_json_file(data: list[dict[str, Any]]) -> dict[str, JSONKeyInfo]:
    field_info: dict[str, JSONKeyInfo] = defaultdict(
        lambda: JSONKeyInfo(0, set(), False)
    )

    for obj in data:
        for key, val in field_info.items():
            if obj.get(key) is None:
                val.nullable = True

        for key, value in obj.items():
            if value is not None:
                field_info[key].count += 1
                field_info[key].type_.add(type(value).__name__)

    return field_info


def print_table(
    title: str, headers: list[str], values: list[list[Any]], n_items: int
) -> str:
    # Calculate the maximum length for each column, considering both headers and the
    # data in values
    max_lengths = [
        max(len(str(row[i])) if i < len(row) else 0 for row in [headers, *values])
        for i in range(len(headers))
    ]

    fmt_parts = [f"{{{i}:<{len}}}" for i, len in enumerate(max_lengths)]
    fmt_string = " | ".join(fmt_parts)

    def format_row(row: list[Any]) -> str:
        return fmt_string.format(*(map(str, row)))

    header_line = format_row(headers)
    separator_line = " | ".join("-" * length for length in max_lengths)
    rows = [format_row(row) for row in values]

    title = f"{title}: {n_items} items"
    return "\n".join([title, header_line, separator_line, *rows])


def render_data(
    info: dict[str, JSONKeyInfo], num_objects: int, add_count: bool
) -> list[list[str]]:
    result: list[list[str]] = []
    for k, v in info.items():
        row = [
            k,
            ", ".join(sorted(v.type_)),
            "✓" if v.nullable else "✗",
        ]
        if add_count:
            row.extend([str(v.count), f"{v.count / num_objects:.0%}"])
        result.append(row)
    return result


def get_path(data: dict[str, Any], path: str) -> Any:
    for part in path.split("."):
        if part not in data:
            return None
        data = data[part]
    return data


def main() -> None:
    parser = HelpOnErrorArgumentParser(__doc__)
    parser.add_argument(
        "files",
        type=argparse.FileType("r"),
        nargs="*",
        default=[sys.stdin],
        help="Paths to the JSON files.",
    )
    parser.add_argument(
        "--count",
        "-c",
        action="store_true",
        help="Add the count of objects with the key.",
    )
    parser.add_argument(
        "--path",
        "-p",
        type=str,
        default=None,
        help="Path to the key in the JSON object. Example: 'data.attributes'."
        " Applied to all files.",
    )
    args = parser.parse_args()

    for file in args.files:
        data = json.load(file)
        if args.path:
            data = get_path(data, args.path)

        if not is_bearable(data, list[dict[str, Any]]):
            print(f"{file.name}: Invalid JSON format. Expected a list of objects.")
            if is_bearable(data, dict[str, Any]):
                print("Found object with keys:", ", ".join(repr(k) for k in data))
                print("Use --path/-p with one of these keys.")
            continue

        info = analyze_json_file(data)
        table = render_data(info, len(data), args.count)

        headers = ["Name", "Type", "Nullable"]
        if args.count:
            headers.extend(["Count", "%"])
        print(print_table(file.name, headers, table, len(data)), end="\n\n")


if __name__ == "__main__":
    main()
