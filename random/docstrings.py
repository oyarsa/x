"""Generate a list of files and descriptions from Python and Go module docstrings."""

import argparse
import ast
import re
import textwrap
from pathlib import Path
from typing import TextIO


def extract_py_docstring(file_path: Path) -> str | None:
    module = ast.parse(file_path.read_text())

    if docstring := ast.get_docstring(module):
        return docstring.splitlines()[0].strip()
    return None


def extract_go_docstring(file_path: Path) -> str | None:
    content = file_path.read_text()

    # Match `//` comments before the package declaration, skipping `//go:` lines.
    if match := re.search(r"(//(?!go:).*?\n\s*)+package\s+\w+", content, re.DOTALL):
        comments = match[0].strip()

        # Remove `//` symbols and extra whitespace
        docstring = re.sub(r"(^|\n)\s*//", "\n", comments).strip()
        return docstring.splitlines()[0].strip()

    return None


EXTRACT_FN = {".py": extract_py_docstring, ".go": extract_go_docstring}


def main(input_path: Path, output_file: TextIO) -> None:
    docstrings: dict[Path, str] = {}

    for file_path in input_path.rglob("*"):
        if ".venv" in file_path.parts:
            continue
        if file_path.suffix not in EXTRACT_FN:
            continue
        if docstring := EXTRACT_FN[file_path.suffix](file_path):
            docstrings[file_path] = docstring

    output_file.write("## Files\n\n")
    for file_name, docstring in docstrings.items():
        initial_line = f"- [`{file_name}`]({file_name}): "
        remaining_width = 88 - len(initial_line)

        wrapped_docstring = textwrap.fill(docstring, width=remaining_width)
        wrapped_lines = wrapped_docstring.split("\n")

        output_file.write(f"{initial_line}{wrapped_lines[0]}\n")

        for line in wrapped_lines[1:]:
            output_file.write(f"  {line}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default=".",
        type=Path,
        help="The path to the directory containing the source files",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        default="-",
        type=argparse.FileType("w"),
        help="The path to the output file where the docstrings will be written",
    )
    args = parser.parse_args()
    main(args.input_path, args.output_file)
