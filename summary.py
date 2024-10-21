"""Analyzes Python files to extract function/class signatures and docstrings."""

import ast
import sys
from pathlib import Path
from typing import Annotated

import typer


def extract_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> str:
    """Extract the signature of a function or class definition."""
    if isinstance(node, ast.ClassDef):
        return f"class {node.name}"

    args: list[str] = []
    for arg in node.args.args:
        arg_str = arg.arg
        if arg.annotation:
            arg_str += f": {ast.unparse(arg.annotation)}"
        args.append(arg_str)

    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")

    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")

    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""

    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(args)}){returns}"


def get_first_docstring_line(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Module,
) -> str:
    """Get the first line of a node's docstring, if it exists."""
    docstring = ast.get_docstring(node)
    return docstring.split("\n")[0] if docstring else "No docstring"


def analyse_file(file_path: Path) -> None:
    """Analyse a Python file and print its structure."""
    with file_path.open("r", encoding="utf-8") as file:
        tree = ast.parse(file.read())

    module_docstring = get_first_docstring_line(tree)
    print(f"Module docstring: {module_docstring}\n")

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            signature = extract_signature(node)
            docstring = get_first_docstring_line(node)
            print(f"{signature}")
            print(f"    {docstring}\n")

        if isinstance(node, ast.ClassDef):
            for class_node in ast.iter_child_nodes(node):
                if isinstance(class_node, ast.FunctionDef | ast.AsyncFunctionDef):
                    signature = extract_signature(class_node)
                    docstring = get_first_docstring_line(class_node)
                    print(f"    {signature}")
                    print(f"        {docstring}\n")


app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
)


@app.command(help=__doc__)
def main(
    file_path: Annotated[
        Path,
        typer.Argument(
            help="Path to Python file to be analysed", exists=True, file_okay=True
        ),
    ],
) -> None:
    path = Path(file_path)

    if path.suffix != ".py":
        print(f"Error: '{file_path}' is not a Python file.")
        sys.exit(1)

    analyse_file(path)


if __name__ == "__main__":
    app()
