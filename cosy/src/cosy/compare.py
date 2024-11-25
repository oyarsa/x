"""Compare two scripts to show what they have in common."""
# pyright: basic

import ast
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer


@dataclass
class Location:
    file: str
    line: int


@dataclass
class Match:
    name: str
    type_: str
    locations: tuple[Location, Location]


class Collector(ast.NodeVisitor):
    def __init__(self, parents: dict[ast.AST, ast.AST]) -> None:
        self.constants: dict[str, tuple[ast.AST, int]] = {}
        self.functions: dict[str, tuple[ast.AST, int]] = {}
        self.classes: dict[str, tuple[ast.AST, int]] = {}
        self.parents = parents

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        # Only collect module-level constants (uppercase names)
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                self.constants[target.id] = (node, node.lineno)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        # Only collect module-level functions
        if isinstance(self.parents[node], ast.Module):
            self.functions[node.name] = (node, node.lineno)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        if isinstance(self.parents[node], ast.Module):
            self.classes[node.name] = (node, node.lineno)
        self.generic_visit(node)


def parse_file(path: Path) -> tuple[ast.Module, dict[ast.AST, ast.AST]]:
    with open(path) as f:
        content = f.read()
    tree = ast.parse(content)
    parents: dict[ast.AST, ast.AST] = {}
    # Add parent references to make it easier to check context
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return tree, parents


def compare_ast_nodes(node1: ast.AST, node2: ast.AST) -> bool:
    # sourcery skip: merge-duplicate-blocks
    """Compare two AST nodes for exact equality."""
    if type(node1) is not type(node2):
        return False

    for name, value1 in ast.iter_fields(node1):
        value2 = getattr(node2, name, None)

        # Skip parent field we added and other internal attributes
        if name in {
            "parent",
            "lineno",
            "col_offset",
            "end_lineno",
            "end_col_offset",
            "ctx",
        }:
            continue

        if isinstance(value1, list):
            assert isinstance(value2, list)
            if len(value1) != len(value2):
                return False
            for item1, item2 in zip(value1, value2):
                if isinstance(item1, ast.AST):
                    if not compare_ast_nodes(item1, item2):
                        return False
                elif item1 != item2:
                    return False
        elif isinstance(value1, ast.AST):
            assert isinstance(value2, ast.AST)
            if not compare_ast_nodes(value1, value2):
                return False
        elif value1 != value2:
            return False

    return True


def find_identical_units(file1: Path, file2: Path) -> list[Match]:
    collector1 = collect(file1)
    collector2 = collect(file2)
    matches: list[Match] = []

    # Compare constants
    for name, (node1, line1) in collector1.constants.items():
        if name in collector2.constants:
            node2, line2 = collector2.constants[name]
            if compare_ast_nodes(node1, node2):
                matches.append(
                    Match(
                        name=name,
                        type_="constant",
                        locations=(
                            Location(file1.name, line1),
                            Location(file2.name, line2),
                        ),
                    )
                )

    # Compare functions
    for name, (node1, line1) in collector1.functions.items():
        if name in collector2.functions:
            node2, line2 = collector2.functions[name]
            if compare_ast_nodes(node1, node2):
                matches.append(
                    Match(
                        name=name,
                        type_="function",
                        locations=(
                            Location(file1.name, line1),
                            Location(file2.name, line2),
                        ),
                    )
                )

    # Compare classes
    for name, (node1, line1) in collector1.classes.items():
        if name in collector2.classes:
            node2, line2 = collector2.classes[name]
            if compare_ast_nodes(node1, node2):
                matches.append(
                    Match(
                        name=name,
                        type_="class",
                        locations=(
                            Location(file1.name, line1),
                            Location(file2.name, line2),
                        ),
                    )
                )

    return matches


def collect(path: Path) -> Collector:
    tree, parents = parse_file(path)
    result = Collector(parents)
    result.visit(tree)
    return result


def main(
    file1: Annotated[
        Path, typer.Argument(help="First Python file to compare.", exists=True)
    ],
    file2: Annotated[
        Path, typer.Argument(help="Second Python file to compare.", exists=True)
    ],
) -> None:
    matches = find_identical_units(file1, file2)
    if not matches:
        print("No identical units found")
        return

    matches_by_type: defaultdict[str, list[Match]] = defaultdict(list)
    for match in matches:
        matches_by_type[match.type_].append(match)

    for type_, matches in matches_by_type.items():
        print(f"\n{type_.upper()}:")
        for match in matches:
            print(f"  {match.name}")
            for loc in match.locations:
                print(f"    - {loc.file}:{loc.line}")
