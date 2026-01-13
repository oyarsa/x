#!/usr/bin/env python3
"""Print a confusion table from a JSON file and two fields.

Dependencies:
- pandas
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any

import pandas as pd  # type: ignore
import typer
from beartype.door import is_bearable


def create_confusion_table(
    data: list[dict[str, Any]], field1: str, field2: str
) -> pd.DataFrame:
    confusion_matrix: dict[tuple[Any, Any], int] = defaultdict(int)

    for item in data:
        value1 = item.get(field1, "N/A")
        value2 = item.get(field2, "N/A")
        confusion_matrix[value1, value2] += 1

    field1_values = sorted(set(confusion_matrix))
    field2_values = sorted({f2 for _, f2 in confusion_matrix.items()})

    table_data = [
        [confusion_matrix[(value1, value2)] for value2 in field2_values]
        for value1 in field1_values
    ]

    df = pd.DataFrame(table_data, index=field1_values, columns=field2_values)  # type: ignore
    df.index.name = field1
    df.columns.name = field2

    return df


def main(
    file: Annotated[Path, typer.Argument(help="Path to JSON file")],
    field1: Annotated[str, typer.Argument(help="Name of the first field.")],
    field2: Annotated[str, typer.Argument(help="Name of the second field.")],
):
    data = json.loads(file.read_bytes())
    if not is_bearable(data, list[dict[str, Any]]):
        raise ValueError("Invalid JSON format. Expected a list of objects.")

    table = create_confusion_table(data, field1, field2)
    print(table)
