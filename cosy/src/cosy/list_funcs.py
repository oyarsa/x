"""List all functions in a file, with parameters and types."""

import ast
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, cast

import typer


@dataclass
class Parameter:
    """Function parameter with type."""

    name: str
    type_hint: str | None


@dataclass
class Function:
    """Function with parameters and types."""

    name: str
    parameters: list[Parameter]
    return_type: str | None


class FunctionVisitor(ast.NodeVisitor):
    """Visit nodes in file and gather information from functions."""

    def __init__(self) -> None:
        self.functions: list[Function] = []

    def get_type_annotation(self, node: ast.AST) -> str | None:
        # @FIX: Some types (e.g. T | None, some imports) are getting `None` as the type.
        """Get type annotation for node."""
        match node:
            case ast.Name(id):
                return id
            case ast.Constant(value):
                return str(value)
            case ast.Subscript(
                value=ast.Name(id="Annotated"), slice=ast.Tuple(elts=elts)
            ):
                return self.get_type_annotation(elts[0])
            case ast.Subscript(value=ast.Name(id="Annotated"), slice=slice):
                return self.get_type_annotation(slice)
            case ast.Subscript():
                return ast.unparse(node)
            case _:
                return None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        params = [
            Parameter(arg.arg, fmap(arg.annotation, self.get_type_annotation))
            for arg in node.args.args
        ]
        self.functions.append(
            Function(node.name, params, fmap(node.returns, self.get_type_annotation))
        )

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self.visit_FunctionDef(cast(ast.FunctionDef, node))


def fmap[T, U](val: T | None, fn: Callable[[T], U]) -> U | None:
    """Apply function to `val` if it's None, else returns None."""
    return None if val is None else fn(val)


def parse_file(source: str) -> list[Function]:
    """Parse Python source code and return parsed functions."""
    tree = ast.parse(source)
    visitor = FunctionVisitor()
    visitor.visit(tree)
    return visitor.functions


def main(
    input_file: Annotated[Path, typer.Argument(help="Path to Python file.")],
) -> None:
    """Parse Python file AST and extraction function information."""
    functions = parse_file(input_file.read_text())

    for func in functions:
        print(f"{func.name} -> {func.return_type}")
        for param in func.parameters:
            hint = f": {param.type_hint}" if param.type_hint else ""
            print(f"    {param.name}{hint}")
        print()
