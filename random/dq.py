#!/usr/bin/env python3
"""Run a DuckDB query with named path bindings.

Examples:
  dq x=data/sales.csv 'SELECT count(*) FROM $x'
  dq x=orders.parquet y=customers.csv 'SELECT * FROM $x JOIN $y ON $x.cid = $y.id'
"""

import argparse
import re
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "args",
        nargs="+",
        metavar="ARG",
        help="name=path bindings and/or SQL query (use $name to reference bindings)",
    )
    parsed = parser.parse_args()

    bindings: dict[str, str] = {}
    query_parts: list[str] = []

    for arg in parsed.args:
        m = re.match(r"^([a-zA-Z_]\w*)=(.+)$", arg)
        if m:
            bindings[m.group(1)] = m.group(2)
        else:
            query_parts.append(arg)

    query = " ".join(query_parts)

    for name, val in bindings.items():
        query = query.replace(f"${name}", f"'{val}'")

    subprocess.run(["duckdb", "-c", query], check=False)


if __name__ == "__main__":
    main()
