"""Analyse Python source files to find functions missing return type annotations."""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer


def main(
    directory: Annotated[
        Path, typer.Argument(help="Directory to recursively search for Python files")
    ],
) -> None:
    """Find and report all functions missing return type annotations.

    Recursively searches through Python files in the given directory and prints
    information about functions that should have return type annotations but don't.
    Skips files containing `venv` in the path.
    """
    missing: list[MissingAnnotation] = []
    for file in directory.rglob("*.py"):
        if "venv" not in str(file):
            missing.extend(find_missing_return_funcs(file))

    if not missing:
        print("No functions missing return type annotations found.")
        return

    print("\nFunctions missing return type annotations:")
    for issue in sorted(missing, key=lambda x: (x.filename, x.line_number)):
        print(f"{issue.filename}:{issue.line_number} - {issue.function_name}")


@dataclass(frozen=True, kw_only=True)
class MissingAnnotation:
    """Represents a function missing a return type annotation.

    This dataclass captures the location and details of functions that should have
    return type annotations but don't.
    """

    filename: str
    line_number: int
    function_name: str


def find_missing_return_funcs(path: Path) -> list[MissingAnnotation]:
    """Analyse a Python file for functions missing return type annotations.

    The file is parsed into an AST and traversed to find all function definitions
    that should have return type annotations but don't.
    """
    try:
        tree = ast.parse(path.read_text())
        checker = ReturnAnnotationChecker()
        checker.visit(tree)

        # Update filename in results
        return [
            MissingAnnotation(
                filename=str(path),
                line_number=ma.line_number,
                function_name=ma.function_name,
            )
            for ma in checker.missing_annotations
        ]
    except Exception as e:
        print(f"Error processing {path}: {e}")
        return []


class ReturnAnnotationChecker(ast.NodeVisitor):
    """AST visitor that finds functions missing return type annotations.

    This visitor traverses the AST and identifies function definitions that don't
    specify their return type. It handles both regular functions and async
    functions.
    """

    def __init__(self) -> None:
        self.missing_annotations: list[MissingAnnotation] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Checks a function definition for missing return type annotation."""
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        """Checks an async function definition for missing return type annotation."""
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Analyses a function node and records if it's missing a return annotation."""
        if node.returns:
            return

        self.missing_annotations.append(
            MissingAnnotation(
                filename="<todo>",  # Will be updated later
                line_number=node.lineno,
                function_name=node.name,
            )
        )
