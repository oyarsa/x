"""List imported packages in Python files."""

import ast
import os
from pathlib import Path
from typing import Annotated

import typer


def is_stdlib_module(module_name: str) -> bool:
    # fmt: off
    stdlib_modules = {
        'argparse', 'ast', 'asyncio', 'base64', 'binascii', 'bisect', 'calendar',
        'codecs', 'collections', 'configparser', 'contextlib', 'copy', 'csv',
        'datetime', 'decimal', 'difflib', 'enum', 'functools', 'glob', 'gzip',
        'hashlib', 'heapq', 'hmac', 'http', 'importlib', 'inspect', 'io', 'itertools',
        'json', 'logging', 'math', 'multiprocessing', 'os', 'pathlib', 'pickle',
        'pkgutil', 'platform', 'pprint', 'queue', 'random', 're', 'secrets',
        'shutil', 'signal', 'socket', 'socketserver', 'ssl', 'string', 'subprocess',
        'sys', 'tempfile', 'threading', 'time', 'timeit', 'traceback', 'typing',
        'unittest', 'urllib', 'uuid', 'warnings', 'weakref', 'xml', 'zlib'
    }
    # fmt: on
    return any(module_name.startswith(std) for std in stdlib_modules)


def get_imported_packages(file_path: Path) -> set[str]:
    tree = ast.parse(file_path.read_text())

    imported_packages: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not is_stdlib_module(alias.name):
                    imported_packages.add(alias.name)
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and not is_stdlib_module(node.module)
        ):
            imported_packages.add(node.module)

    return imported_packages


def main(
    directory: Annotated[Path, typer.Argument(help="Directory to analyse")] = Path("."),
    print_files: Annotated[
        bool,
        typer.Option("--files", "-f", help="Display files that import each package."),
    ] = False,
) -> None:
    python_files = directory.rglob("*.py")
    package_files: dict[str, list[Path]] = {}

    for file_path in python_files:
        imported_packages = get_imported_packages(file_path)
        for package in imported_packages:
            if package not in package_files:
                package_files[package] = []
            package_files[package].append(file_path)

    for package, files in sorted(package_files.items()):
        print(package)
        if not print_files:
            continue

        for file in files:
            print(f"  - {os.path.basename(file)}")
