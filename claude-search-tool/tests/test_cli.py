"""Tests for CLI commands."""

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cchs.cli import app

FIXTURES = Path(__file__).parent / "fixtures"

runner = CliRunner()


class TestSearchCommand:
    def test_search_with_results(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "projects" / "-test-project"
        project_dir.mkdir(parents=True)

        src = FIXTURES / "simple_conversation.jsonl"
        dst = project_dir / "session-1.jsonl"
        dst.write_text(src.read_text())

        with patch("cchs.cli.resolve_project_dir", return_value=project_dir):
            result = runner.invoke(app, ["search", "PFA", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert len(data) > 0

    def test_search_no_results(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "projects" / "-test-project"
        project_dir.mkdir(parents=True)

        src = FIXTURES / "simple_conversation.jsonl"
        dst = project_dir / "session-1.jsonl"
        dst.write_text(src.read_text())

        with patch("cchs.cli.resolve_project_dir", return_value=project_dir):
            result = runner.invoke(app, ["search", "xyznonexistent", "--json"])
            assert result.exit_code == 0

    def test_search_no_project(self) -> None:
        with patch("cchs.cli.resolve_project_dir", return_value=None):
            result = runner.invoke(app, ["search", "test"])
            assert result.exit_code != 0
            assert (
                "not found" in result.stdout.lower()
                or "not found" in (result.stderr or "").lower()
            )


class TestExpandCommand:
    def test_expand_valid_uuid(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "projects" / "-test-project"
        project_dir.mkdir(parents=True)

        src = FIXTURES / "simple_conversation.jsonl"
        dst = project_dir / "session-1.jsonl"
        dst.write_text(src.read_text())

        with patch("cchs.cli.resolve_project_dir", return_value=project_dir):
            runner.invoke(app, ["index"])
            result = runner.invoke(app, ["expand", "msg-002", "--json"])
            assert result.exit_code == 0

    def test_expand_invalid_uuid(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "projects" / "-test-project"
        project_dir.mkdir(parents=True)

        src = FIXTURES / "simple_conversation.jsonl"
        dst = project_dir / "session-1.jsonl"
        dst.write_text(src.read_text())

        with patch("cchs.cli.resolve_project_dir", return_value=project_dir):
            runner.invoke(app, ["index"])
            result = runner.invoke(app, ["expand", "nonexistent"])
            assert result.exit_code != 0


class TestIndexCommand:
    def test_index_runs(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "projects" / "-test-project"
        project_dir.mkdir(parents=True)

        src = FIXTURES / "simple_conversation.jsonl"
        dst = project_dir / "session-1.jsonl"
        dst.write_text(src.read_text())

        with patch("cchs.cli.resolve_project_dir", return_value=project_dir):
            result = runner.invoke(app, ["index"])
            assert result.exit_code == 0


class TestSkillCommand:
    def test_skill_prints_to_stdout(self) -> None:
        result = runner.invoke(app, ["skill"])
        assert result.exit_code == 0
        assert "search-history" in result.stdout

    def test_skill_install(self, tmp_path: Path) -> None:
        skill_path = tmp_path / "search-history" / "SKILL.md"
        with patch("cchs.skill.SKILL_PATH", skill_path):
            result = runner.invoke(app, ["skill", "--install"])
            assert result.exit_code == 0
            assert skill_path.exists()
