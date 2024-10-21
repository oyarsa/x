"""Summarises functions and classes signatures in a Python file, including docstrings.

The output is syntax-highlighted with pygments (through rich).
"""

import ast
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console, RenderableType
from rich.syntax import Syntax

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
    theme: Annotated[
        str, typer.Option(help="Syntax highlight theme (see Pygments.)")
    ] = "one-dark",
) -> None:
    if file_path.suffix != ".py":
        typer.echo(f"Error: '{file_path}' is not a Python file.", err=True)
        raise typer.Abort()

    echo(process_file(file_path, theme))


INDENT = " " * 4


def process_file(file_path: Path, syntax_theme: str) -> list[RenderableType]:
    """Process a Python file and return its structure as rich renderables."""
    module = ast.parse(file_path.read_text())

    output: list[RenderableType | str] = []

    module_docstring = get_docstring_summary(module)
    output.append(module_docstring)
    output.append("\n")

    for node in ast.iter_child_nodes(module):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            signature = extract_signature(node)
            docstring = get_docstring_summary(node)

            output.append(syntax(signature, syntax_theme))
            output.append(f"{INDENT}{docstring}")
            output.append("\n")

        if isinstance(node, ast.ClassDef):
            for class_node in ast.iter_child_nodes(node):
                if isinstance(class_node, ast.FunctionDef | ast.AsyncFunctionDef):
                    signature = extract_signature(class_node)
                    docstring = get_docstring_summary(class_node)

                    output.append(syntax(f"{INDENT}{signature}", syntax_theme))
                    output.append(f"{INDENT*2}{docstring}")
                    output.append("\n")

    return output


def get_docstring_summary(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Module,
) -> str:
    """Get the first line of a node's docstring, if it exists."""
    docstring = ast.get_docstring(node)
    return docstring.split("\n")[0] if docstring else "..."


def extract_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> str:
    """Extract the signature of a function or class definition."""
    if isinstance(node, ast.ClassDef):
        return f"class {node.name}:"

    args: list[str] = []

    for arg in node.args.args:
        args.append(f"{arg.arg}: {get_annotation(arg)}")

    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}: {get_annotation(node.args.vararg)}")

    if node.args.kwarg:
        args.append(f"*{node.args.kwarg.arg}: {get_annotation(node.args.kwarg)}")

    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""

    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(args)}){returns}:"


def get_annotation(arg: ast.arg) -> str:
    return ast.unparse(arg.annotation) if arg.annotation else "Unknown"


def syntax(text: str, theme: str) -> Syntax:
    return Syntax(text, "python", theme=theme)


def echo(renderables: Sequence[RenderableType]) -> None:
    console = Console(color_system="truecolor")
    console.print(*renderables)


if __name__ == "__main__":
    app()
