#!/usr/bin/env python3
"""Print a confusion table from a JSON file and two fields.

Dependencies:
- pandas
"""

import argparse
import json
from collections import defaultdict
from typing import Any

import pandas as pd  # type: ignore
from beartype.door import is_bearable

from scripts.util import HelpOnErrorArgumentParser


def create_confusion_table(
    data: list[dict[str, Any]], field1: str, field2: str
) -> pd.DataFrame:
    confusion_matrix: dict[tuple[Any, Any], int] = defaultdict(int)

    for item in data:
        value1 = item.get(field1, "N/A")
        value2 = item.get(field2, "N/A")
        confusion_matrix[value1, value2] += 1

    field1_values = sorted(set(f1 for f1, _ in confusion_matrix))
    field2_values = sorted(set(f2 for _, f2 in confusion_matrix))

    table_data = [
        [confusion_matrix[(value1, value2)] for value2 in field2_values]
        for value1 in field1_values
    ]

    df = pd.DataFrame(table_data, index=field1_values, columns=field2_values)  # type: ignore
    df.index.name = field1
    df.columns.name = field2

    return df


def main():
    parser = HelpOnErrorArgumentParser(__doc__)
    parser.add_argument("file", type=argparse.FileType(), help="Path to the JSON file")
    parser.add_argument("field1", type=str, help="Name of the first field")
    parser.add_argument("field2", type=str, help="Name of the second field")
    args = parser.parse_args()

    data = json.load(args.file)
    if not is_bearable(data, list[dict[str, Any]]):
        raise ValueError("Invalid JSON format. Expected a list of objects.")

    table = create_confusion_table(data, args.field1, args.field2)
    print(table)


if __name__ == "__main__":
    main()
