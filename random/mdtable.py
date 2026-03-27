#!/usr/bin/env python3
"""Format stdin tabular data as a markdown table."""

import argparse
import re
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Format tabular input as a markdown table.",
    )
    parser.add_argument(
        "--separator",
        "-s",
        default=r"\s+",
        help=r"column separator regex (default: '\s+').",
    )
    parser.add_argument(
        "-H",
        "--header",
        help="comma-separated header names (first input row becomes data).",
    )
    args = parser.parse_args()

    lines = [line for line in sys.stdin if line.strip()]
    if not lines:
        return

    rows = [re.split(args.separator, line.strip()) for line in lines]

    if args.header:
        header = [h.strip() for h in args.header.split(",")]
    else:
        header = rows.pop(0)
        if not rows:
            return

    ncols = max(len(header), *(len(r) for r in rows))
    header.extend([""] * (ncols - len(header)))
    for r in rows:
        r.extend([""] * (ncols - len(r)))

    widths = [max(len(header[c]), *(len(r[c]) for r in rows)) for c in range(ncols)]

    def fmt_row(row: str) -> str:
        cells = " | ".join(v.ljust(w) for v, w in zip(row, widths))
        return f"| {cells} |"

    print(fmt_row(header))
    print("|" + "|".join("-" * (w + 2) for w in widths) + "|")
    for row in rows:
        print(fmt_row(row))


if __name__ == "__main__":
    main()
