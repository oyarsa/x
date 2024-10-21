"""Analyses Python files to extract function/class signatures and docstrings."""

import ast
import shutil
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
    return docstring.split("\n")[0] if docstring else "..."


INDENT = " " * 4


def analyse_file(file_path: Path) -> str:
    """Analyse a Python file and print its structure."""
    with file_path.open("r", encoding="utf-8") as file:
        tree = ast.parse(file.read())

    output: list[str] = []

    module_docstring = get_first_docstring_line(tree)
    output.append(f"{module_docstring}\n")

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if node.name == "main":
                continue

            signature = extract_signature(node)
            output.append(f"{signature}")
            docstring = get_first_docstring_line(node)
            output.append(f"{INDENT}{docstring}\n")

        if isinstance(node, ast.ClassDef):
            for class_node in ast.iter_child_nodes(node):
                if isinstance(class_node, ast.FunctionDef | ast.AsyncFunctionDef):
                    signature = extract_signature(class_node)
                    output.append(f"{INDENT}{signature}")
                    docstring = get_first_docstring_line(class_node)
                    output.append(f"{INDENT*2}{docstring}\n")

    return "\n".join(output)


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
        typer.echo(f"Error: '{file_path}' is not a Python file.", err=True)
        raise typer.Abort()

    echo(analyse_file(path))


def echo(text: str) -> None:
    _, terminal_height = shutil.get_terminal_size()
    text_lines = text.count("\n") + 1

    if text_lines > terminal_height:
        typer.echo_via_pager(text)
    else:
        typer.echo(text)


if __name__ == "__main__":
    app()
