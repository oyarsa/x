"""Count number of functions, methods, classes and  in project files."""

import ast
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer


@dataclass(frozen=True, kw_only=True)
class FileStats:
    """Statistics for a single Python file."""

    file: Path
    functions: int
    methods: int
    classes: int


@dataclass(frozen=True, kw_only=True)
class Summary:
    """Summary of all analysed files."""

    total_files: int
    total_functions: int
    total_methods: int
    total_classes: int


@dataclass(frozen=True, kw_only=True)
class AnalysisResults:
    """Complete analysis results."""

    summary: Summary
    file_stats: list[FileStats]
    classes: dict[str, list[str]]
    functions: list[str]
    errors: list[str]


class FunctionCounter(ast.NodeVisitor):
    def __init__(self) -> None:
        self.function_count = 0
        self.method_count = 0
        self.class_methods: defaultdict[str, list[str]] = defaultdict(list)
        self.functions: list[str] = []
        self._current_class: str | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        previous_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = previous_class

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:  # noqa: N802
        if self._current_class:
            self.method_count += 1
            self.class_methods[self._current_class].append(node.name)
        else:
            self.function_count += 1
            self.functions.append(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        # Count async functions/methods the same way
        self.visit_FunctionDef(node)


def analyse_file(file_path: Path) -> FunctionCounter:
    """Analyse a single Python file and return its statistics.

    Args:
        file_path: Path to a Python file.

    Returns:
        A counter with code statistics about the file.

    Raises:
        ValueError: if any error happens during analysis.
    """
    try:
        tree = ast.parse(file_path.read_text())

        counter = FunctionCounter()
        counter.visit(tree)
    except Exception as e:
        raise ValueError(f"Error analysing {file_path}: {e}") from e
    else:
        return counter


def analyse_project(project_paths: Iterable[Path]) -> AnalysisResults:
    """Recursively analyse a Python project directory and count functions/methods.

    Skips files with `venv` in their real path.

    Args:
        project_paths: Paths to project directories.

    Returns:
        Data class containing analysis results.
    """
    total_files = 0
    total_functions = 0
    total_methods = 0
    errors: list[str] = []
    file_stats: list[FileStats] = []
    all_classes: dict[str, list[str]] = defaultdict(list)
    all_functions: list[str] = []

    for project_path in project_paths:
        for file_path in project_path.rglob("*.py"):
            if "venv" in str(file_path.resolve()):
                continue

            total_files += 1

            try:
                counter = analyse_file(file_path)
            except Exception as e:
                errors.append(str(e))
                continue

            total_functions += counter.function_count
            total_methods += counter.method_count

            file_stats.append(
                FileStats(
                    file=file_path,
                    functions=counter.function_count,
                    methods=counter.method_count,
                    classes=len(counter.class_methods),
                )
            )

            # Collect all class methods and functions
            for class_name, methods in counter.class_methods.items():
                all_classes[class_name].extend(methods)
            all_functions.extend(counter.functions)

    return AnalysisResults(
        summary=Summary(
            total_files=total_files,
            total_functions=total_functions,
            total_methods=total_methods,
            total_classes=len(all_classes),
        ),
        file_stats=file_stats,
        classes=all_classes,
        functions=all_functions,
        errors=errors,
    )


def print_analysis(results: AnalysisResults) -> None:
    """Print the analysis results in a formatted way."""
    print("\n=== Python Project Analysis ===")

    print("\nDetailed File Statistics:")
    for stat in results.file_stats:
        print(f"\n{stat.file}:")
        print(f"  Functions: {stat.functions}")
        print(f"  Methods: {stat.methods}")
        print(f"  Classes: {stat.classes}")

    if results.errors:
        print("\nErrors encountered:")
        for error in results.errors:
            print(f"  - {error}")

    print("\nSummary:")
    print(f"Total Python files: {results.summary.total_files}")
    print(f"Total functions: {results.summary.total_functions}")
    print(f"Total methods: {results.summary.total_methods}")
    print(f"Total classes: {results.summary.total_classes}")


app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


@app.command(help=__doc__)
def main(
    *,
    project_paths: Annotated[
        list[Path] | None, typer.Argument(help="Path to the Python project directory.")
    ] = None,
) -> None:
    results = analyse_project(project_paths or [Path(".")])
    print_analysis(results)


if __name__ == "__main__":
    app()
