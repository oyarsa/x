"""Compare dependencies between two pyproject.toml files.

Compatible with Hatch, Rye and PDM. Not compatible with Poetry.
"""

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer


def main(
    file1: Annotated[Path, typer.Argument(help="Path to first pyproject.toml file.")],
    file2: Annotated[Path, typer.Argument(help="Path to second pyproject.toml file.")],
) -> None:
    packages1 = parse_deps(load_deps(file1))
    packages2 = parse_deps(load_deps(file2))

    deps = match_deps(packages1, packages2)
    print(render_deps(file1.name, file2.name, deps))


def load_deps(file: Path) -> list[str]:
    return tomllib.loads(file.read_text())["project"]["dependencies"]


def parse_deps(deps: list[str]) -> dict[str, str]:
    return dict(split(d) for d in deps)


def split(line: str) -> tuple[str, str]:
    name, *versions = re.split(r"(@|,|>|<|=)", line.strip())
    name = name.strip()
    versions = "".join(v for v in versions if v.strip()).strip()
    return name, versions


@dataclass
class Dependency:
    name: str
    version1: str
    version2: str


def match_deps(
    packages1: dict[str, str], packages2: dict[str, str]
) -> list[Dependency]:
    deps = set(packages1) | set(packages2)
    return [
        Dependency(dep, packages1.get(dep, "*"), packages2.get(dep, "*"))
        for dep in sorted(deps)
    ]


def render_deps(file_name1: str, file_name2: str, deps: list[Dependency]) -> str:
    fmt = "{:<25} | {:<20} | {:<20}"
    header = fmt.format(
        "Dependency", os.path.dirname(file_name1), os.path.dirname(file_name2)
    )
    sep = fmt.format("-" * 25, "-" * 20, "-" * 20)
    rows = [
        fmt.format(dep.name, dep.version1[-15:], dep.version2[-15:]) for dep in deps
    ]
    return "\n".join([header, sep, *rows])
