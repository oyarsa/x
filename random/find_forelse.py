#!/usr/bin/env python3
"""Count occurences of for-else in Python files.

Turns out it's really rare, at least for me.
"""

import argparse
import ast
import contextlib
from pathlib import Path


class ForElseFinder(ast.NodeVisitor):
    def __init__(self, filename: str) -> None:
        self.filename = filename

    def visit_For(self, node) -> None:
        if node.orelse:
            print(f"{self.filename}:{node.lineno}")
        self.generic_visit(node)


def find_for_else_in_file(file: Path) -> None:
    with contextlib.suppress(SyntaxError):
        tree = ast.parse(file.read_text(), filename=file.name)
        finder = ForElseFinder(str(file.resolve()))
        finder.visit(tree)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find for-else in Python files")
    parser.add_argument(
        "path",
        type=Path,
        default=".",
        nargs="?",
        help="Directory to search for Python files. Default is the current directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path: Path = args.path

    for file in path.rglob("*.py"):
        # Ignore venv and non-files
        if "env" in str(file.resolve()) or not file.is_file():
            continue
        find_for_else_in_file(file)


if __name__ == "__main__":
    main()
