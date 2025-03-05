"""Print project names and languages in a directory."""

# pyright: strict
import argparse
from pathlib import Path
from dataclasses import dataclass


def detect_project_language(dir: Path) -> str:
    """Identify the project's language by configuration file."""
    files = {
        "go.mod": "Go",
        "Cargo.toml": "Rust",
        # Python has quite a few variations
        "pyproject.toml": "Python",
        "requirements.txt": "Python",
        "setup.py": "Python",
        "setup.cfg": "Python",
        "pom.xml": "Java",
        "lua": "Lua",
    }
    return next((lang for file, lang in files.items() if (dir / file).exists()), "-")


@dataclass(frozen=True, kw_only=True)
class Project:
    """Project information."""

    name: str
    language: str


def scan_projects(base_dir: Path) -> list[Project]:
    """For each directory in `base_dir`, determine its language.

    See also `detect_project_language`.
    """
    return [
        Project(name=item.name, language=detect_project_language(item))
        for item in base_dir.iterdir()
        if item.is_dir() and not item.name.startswith(".")
    ]


def print_table(projects: list[Project]) -> None:
    """Print pretty table with project names and languages."""
    # Find the maximum width of project names
    max_project_len = max(len("Project"), max(len(p.name) for p in projects))
    max_lang_len = max(len("Language"), max(len(p.language) for p in projects))
    format_str = f"{{:<{max_project_len}}}  {{:<{max_lang_len}}}"

    # Print header
    print(format_str.format("Project", "Language"))
    print("-" * (max_project_len + max_lang_len + 2))

    # Print rows
    for project in sorted(projects, key=lambda p: p.name):
        print(format_str.format(project.name, project.language))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dir",
        type=Path,
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory)",
    )
    args = parser.parse_args()
    base_dir: Path = args.dir

    projects = scan_projects(base_dir)
    print_table(projects)


if __name__ == "__main__":
    main()
