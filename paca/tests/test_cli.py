"""Tests for paca CLI entrypoint."""

from pathlib import Path

from typer.testing import CliRunner

from paca import app

runner = CliRunner()


class TestCli:
    """Tests for CLI commands."""

    def test_help(self) -> None:
        """Should display help text."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_init_creates_config(self, tmp_path: Path) -> None:
        """Should create a config file."""
        config_file = tmp_path / "config.toml"
        result = runner.invoke(
            app, ["init", "--config-path", str(config_file)], input="\n\n\n"
        )
        assert result.exit_code == 0
        assert config_file.exists()

    def test_init_refuses_existing(self, tmp_path: Path) -> None:
        """Should refuse to overwrite existing config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("existing = true\n")
        result = runner.invoke(app, ["init", "--config-path", str(config_file)])
        assert result.exit_code == 1
