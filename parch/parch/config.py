"""Configuration file loading for parch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import toml

_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "parch" / "config.toml"


@dataclass
class ParchConfig:
    """Resolved configuration values (config file + defaults)."""

    archive_dir: str | None = None
    pueue_bin: str = "pueue"
    include_running: bool = False
    colour: str = "auto"
    pager: str = "auto"


def load_config(config_path: Path | None = None) -> ParchConfig:
    """Load configuration from TOML file.

    Returns defaults if the file doesn't exist.
    """
    path = config_path or _DEFAULT_CONFIG_PATH

    if not path.exists():
        return ParchConfig()

    try:
        data = toml.loads(path.read_text())
    except (toml.TomlDecodeError, OSError):
        return ParchConfig()

    return ParchConfig(
        archive_dir=data.get("archive_dir"),
        pueue_bin=data.get("pueue_bin", "pueue"),
        include_running=data.get("include_running", False),
        colour=data.get("color", data.get("colour", "auto")),
        pager=data.get("pager", "auto"),
    )
