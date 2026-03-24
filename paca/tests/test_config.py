"""Tests for paca.config."""

from pathlib import Path

import pytest

from paca.config import PacaConfig, config_dir, load_config


class TestPacaConfig:
    """Tests for PacaConfig model."""

    def test_defaults(self) -> None:
        """Should have sensible defaults per spec section 15."""
        config = PacaConfig()
        assert config.default_duration_minutes == 60
        assert config.default_reminder_method == "popup"
        assert list(config.default_reminder_minutes) == [10, 30]
        assert config.show_debug_json is False

    def test_frozen(self) -> None:
        """Should be immutable."""
        from pydantic import ValidationError  # noqa: PLC0415

        config = PacaConfig()
        with pytest.raises(ValidationError):
            config.default_duration_minutes = 999  # type: ignore[misc]


class TestConfigDir:
    """Tests for config_dir."""

    def test_xdg_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should use XDG_CONFIG_HOME when set."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg")  # noqa: S108
        assert config_dir() == Path("/tmp/xdg/paca")  # noqa: S108

    def test_default_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should fall back to ~/.config/paca."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = config_dir()
        assert result == Path.home() / ".config" / "paca"


class TestLoadConfig:
    """Tests for load_config."""

    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        """Should return defaults when no config file exists."""
        config = load_config(tmp_path / "nonexistent.toml")
        assert config == PacaConfig()

    def test_loads_partial_override(self, tmp_path: Path) -> None:
        """Should merge partial TOML with defaults."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            'default_calendar_name = "Work"\ndefault_duration_minutes = 30\n'
        )
        config = load_config(config_file)
        assert config.default_calendar_name == "Work"
        assert config.default_duration_minutes == 30
        assert config.default_reminder_method == "popup"
