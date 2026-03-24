"""Tests for project directory resolution."""

from pathlib import Path

from cchs.project import path_to_project_dir, resolve_project_dir


class TestPathToProjectDir:
    def test_simple_path(self) -> None:
        assert path_to_project_dir(Path("/home/dev/work/foo")) == "-home-dev-work-foo"

    def test_dot_in_path(self) -> None:
        assert (
            path_to_project_dir(Path("/home/dev/.config/fish"))
            == "-home-dev--config-fish"
        )

    def test_root(self) -> None:
        assert path_to_project_dir(Path("/")) == "-"


class TestResolveProjectDir:
    def test_existing_project(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude" / "projects" / "-home-dev-work-foo"
        claude_dir.mkdir(parents=True)
        result = resolve_project_dir(
            cwd=Path("/home/dev/work/foo"),
            claude_base=tmp_path / ".claude",
        )
        assert result == claude_dir

    def test_missing_project(self, tmp_path: Path) -> None:
        claude_base = tmp_path / ".claude"
        claude_base.mkdir(parents=True)
        (claude_base / "projects").mkdir()
        result = resolve_project_dir(
            cwd=Path("/home/dev/work/missing"),
            claude_base=claude_base,
        )
        assert result is None
