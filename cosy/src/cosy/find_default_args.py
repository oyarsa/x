"""Find functions and methods in a Python script whose parameters have default values."""

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer


@dataclass
class ParamInfo:
    name: str
    type_hint: str | None
    default: str


@dataclass
class FuncInfo:
    name: str
    lineno: int
    params: list[ParamInfo]


def process_function(
    function_node: ast.FunctionDef, class_name: str | None
) -> FuncInfo | None:
    """Determine if function has parameters with default values."""
    args_with_defaults = function_node.args.args[-len(function_node.args.defaults) :]
    params_info: list[ParamInfo] = []

    for arg, default in zip(args_with_defaults, function_node.args.defaults):
        default_value = ast.unparse(default)
        type_hint = ast.unparse(arg.annotation) if arg.annotation else None
        params_info.append(ParamInfo(arg.arg, type_hint, default_value))

    if not params_info:
        return None

    full_name = (
        function_node.name
        if class_name is None
        else f"{class_name}.{function_node.name}"
    )
    return FuncInfo(full_name, function_node.lineno, params_info)


def process_class(
    node: ast.ClassDef,
) -> Iterable[FuncInfo]:
    """Find methods in class with parameters having default values."""
    return (
        res
        for method in node.body
        if isinstance(method, ast.FunctionDef)
        and (res := process_function(method, class_name=node.name))
    )


def find_funcs_with_default_values(
    source_code: str,
) -> Iterable[FuncInfo]:
    """Find functions and methods in script with parameters having default values."""
    node = ast.parse(source_code)

    for node in node.body:
        if isinstance(node, ast.FunctionDef) and (
            res := process_function(node, class_name=None)
        ):
            yield res
        elif isinstance(node, ast.ClassDef):
            yield from process_class(node)


def render_result(functions: Iterable[FuncInfo], func_only: bool) -> str:
    """Render the result of the analysis."""
    out: list[str] = []
    for f in functions:
        func_out = [f"{f.name}:{f.lineno}"]
        if not func_only:
            func_out.extend(
                f"    {p.name}: {p.type_hint} = {p.default}" for p in f.params
            )
        out.append("\n".join(func_out))
    return "\n\n".join(out)


def main(
    file: Annotated[Path, typer.Argument(help="Path to the Python script to analyse")],
    func_only: Annotated[
        bool, typer.Option("--func-only", "-f", help="Show only functions")
    ] = False,
) -> None:
    result = find_funcs_with_default_values(file.read_text())
    print(render_result(result, func_only))
