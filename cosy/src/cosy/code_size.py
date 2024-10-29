"""Analyses a Python file and prints line count information for its elements.

Analyses functions, classes and methods.
"""

import ast
import contextlib
import functools
import tokenize
from collections.abc import Sequence
from enum import StrEnum
from io import StringIO
from pathlib import Path
from typing import Annotated, Any, Self

import typer
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from rich.console import Console
from rich.table import Table


class CodeItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    type_: str = Field(serialization_alias="type")
    name: str
    line: int
    lines_total: int
    lines_code: int
    params_kw: int | None = None
    params_all: int | None = None

    @classmethod
    def from_elements(
        cls,
        source_lines: Sequence[str],
        docstring_line_indices: set[int],
        comment_line_indices: set[int],
        type_: str,
        name: str,
        node: ast.ClassDef | ast.FunctionDef,
    ) -> Self:
        lineno_start = node.lineno
        lineno_end = node.end_lineno or node.lineno
        lines = source_lines[lineno_start - 1 : lineno_end]

        params_all, params_kw = None, None
        if isinstance(node, ast.FunctionDef):
            params_kw = len(node.args.kwonlyargs)
            params_all = len(node.args.args) + len(node.args.posonlyargs) + params_kw

        return cls(
            type_=type_,
            name=name,
            line=lineno_start,
            lines_total=len(lines),
            lines_code=sum(
                bool(
                    line.strip()
                    and idx not in docstring_line_indices
                    and idx not in comment_line_indices
                )
                for idx, line in enumerate(lines, lineno_start)
            ),
            params_kw=params_kw,
            params_all=params_all,
        )


class SortItem(StrEnum):
    TYPE = "type"
    LINE = "line"
    NAME = "name"
    TOTAL = "total"
    CODE = "code"

    def get(self, item: CodeItem) -> Any:
        return {
            self.TYPE: item.type_,
            self.LINE: item.line,
            self.NAME: item.name,
            self.TOTAL: item.lines_total,
            self.CODE: item.lines_code,
        }[self]


def main(
    file: Annotated[Path, typer.Argument(help="Path to the Python file to analyse")],
    is_json: Annotated[
        bool,
        typer.Option("--json", help="Output information as JSON instead of a table"),
    ] = False,
    sort_item: Annotated[
        SortItem, typer.Option("--sort", "-s", help="Column to sort by")
    ] = SortItem.LINE,
    sort_desc: Annotated[bool, typer.Option("--desc", help="Sort descending")] = False,
) -> None:  # sourcery skip: low-code-quality
    source = file.read_text()
    tree = ast.parse(source)

    # Get docstring lines
    docstring_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef
        ) and ast.get_docstring(node):
            doc_node = node.body[0]
            start, end = doc_node.lineno, doc_node.end_lineno or doc_node.lineno
            docstring_lines.update(range(start, end + 1))

    # Get comment lines
    comment_lines: set[int] = set()
    with contextlib.suppress(tokenize.TokenError, IndentationError):
        tokens = tokenize.generate_tokens(StringIO(source).readline)
        comment_lines = {
            token.start[0] for token in tokens if token.type == tokenize.COMMENT
        }

    source_lines = source.splitlines()
    code_item = functools.partial(
        CodeItem.from_elements, source_lines, docstring_lines, comment_lines
    )

    # Track elements and their lines
    items: list[CodeItem] = []
    parent: dict[ast.AST, ast.AST] = {}

    for node in ast.walk(tree):
        # Add parent references for filtering top-level elements
        for child in ast.iter_child_nodes(node):
            parent[child] = node

        if isinstance(node, ast.FunctionDef) and isinstance(parent[node], ast.Module):
            items.append(code_item("function", node.name, node))
        elif isinstance(node, ast.ClassDef) and isinstance(parent[node], ast.Module):
            items.append(code_item("class", node.name, node))
            # Add methods
            items.extend(
                code_item("method", f"{node.name}.{item.name}", item)
                for item in node.body
                if isinstance(item, ast.FunctionDef)
            )

    items = sorted(items, key=sort_item.get, reverse=sort_desc)
    if is_json:
        print(
            TypeAdapter(list[CodeItem])
            .dump_json(items, indent=2, by_alias=True)
            .decode()
        )
    else:
        _items_to_table(str(file), items)


def _items_to_table(name: str, items: Sequence[CodeItem]) -> None:
    table = Table("Type", "Line", "Name", "Total", "Code", "Params", "KW-only")
    for item in items:
        table.add_row(
            item.type_,
            str(item.line),
            item.name,
            str(item.lines_total),
            str(item.lines_code),
            str(item.params_all or ""),
            str(item.params_kw or ""),
        )

    console = Console()
    console.print(name)
    console.print(table)
