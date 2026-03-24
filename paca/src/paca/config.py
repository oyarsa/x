"""Configuration loading and defaults for paca."""

import datetime
import os
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def config_dir() -> Path:
    """Return the paca configuration directory.

    Uses XDG_CONFIG_HOME if set, otherwise ~/.config/paca.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "paca"
    return Path.home() / ".config" / "paca"


def config_path() -> Path:
    """Return the default path to the paca config file."""
    return config_dir() / "config.toml"


class PacaConfig(BaseModel, frozen=True):
    """Application configuration, loaded from TOML."""

    default_calendar_name: str = "Compromissos"
    default_duration_minutes: int = 60
    default_reminder_method: str = "popup"
    default_reminder_minutes: Sequence[int] = (10, 30)
    timezone: str = ""
    model: str = "gpt-4o"
    store_tokens_securely: bool = True
    show_debug_json: bool = False
    save_last_extraction: bool = False


def load_config(path: Path | None = None) -> PacaConfig:
    """Load configuration from a TOML file, falling back to defaults.

    Args:
        path: Path to TOML config file. Uses default location if None.

    Returns:
        Merged configuration.
    """
    if path is None:
        path = config_path()
    if not path.exists():
        return PacaConfig()

    with path.open("rb") as f:
        raw: dict[str, Any] = tomllib.load(f)

    return PacaConfig(**raw)


def save_config(config: PacaConfig, path: Path | None = None) -> None:
    """Write configuration to a TOML file.

    Args:
        config: Configuration to save.
        path: Target path. Uses default location if None.
    """
    if path is None:
        path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for key, value in config.model_dump().items():
        if isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, int):
            lines.append(f"{key} = {value}")
        elif isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        elif isinstance(value, list):
            items = ", ".join(str(v) for v in value)
            lines.append(f"{key} = [{items}]")

    path.write_text("\n".join(lines) + "\n")


def detect_timezone() -> str:
    """Detect the system timezone.

    Returns:
        IANA timezone string, or UTC as fallback.
    """
    try:
        tz = datetime.datetime.now(datetime.UTC).astimezone().tzinfo
        if tz and hasattr(tz, "key"):
            return tz.key  # type: ignore[union-attr]
    except Exception:  # noqa: S110
        pass
    return "UTC"
