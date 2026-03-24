"""Project directory resolution.

Maps the current working directory to Claude Code's project storage path
using the same path-mangling convention.
"""

from pathlib import Path

CLAUDE_BASE = Path.home() / ".claude"


def path_to_project_dir(cwd: Path) -> str:
    """Convert a working directory path to Claude Code's project dir name.

    Example: /home/dev/work/foo → -home-dev-work-foo
    """
    return "-" + str(cwd).strip("/").replace("/", "-").replace(".", "-")


def list_available_projects(*, claude_base: Path = CLAUDE_BASE) -> list[str]:
    """List available project directory names."""
    projects_dir = claude_base / "projects"
    if not projects_dir.is_dir():
        return []
    return sorted(p.name for p in projects_dir.iterdir() if p.is_dir())


def resolve_project_dir(
    cwd: Path,
    *,
    claude_base: Path = CLAUDE_BASE,
) -> Path | None:
    """Resolve the project directory for a given cwd.

    Returns None if the project directory does not exist.
    """
    project_name = path_to_project_dir(cwd)
    project_dir = claude_base / "projects" / project_name
    if project_dir.is_dir():
        return project_dir
    return None
