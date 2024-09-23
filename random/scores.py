"""Extract values from the column of a markdown table.

Takes input from stdin. Requires that the whole input be the markdown table.
"""

import argparse
import contextlib
import sys


def process_markdown_table(column: str) -> None:
    column = column.lower()
    values: list[float] = []
    column_index: int | None = None

    for line in sys.stdin:
        # Skip empty lines
        if not line.strip():
            continue

        # Find the header row and determine the index of the column
        if "|" in line and column in line.lower():
            headers = [
                header.strip().lower() for header in line.split("|") if header.strip()
            ]
            try:
                column_index = headers.index(column)
            except ValueError:
                print("Error: column not found in the table header.")
                return
            continue

        # Process data rows
        if "|" in line and column_index is not None:
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            if len(cells) > column_index:
                # Skip non-numeric values
                with contextlib.suppress(ValueError):
                    values.append(float(cells[column_index]))

    if not values:
        print("No valid values found in the table.")
        return

    min_value = min(values)
    max_value = max(values)
    avg_value = sum(values) / len(values)

    print(f"Minimum: {min_value}")
    print(f"Maximum: {max_value}")
    print(f"Average: {avg_value:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "column",
        type=str,
        help="The name of the column to process.",
    )
    args = parser.parse_args()
    process_markdown_table(args.column)
