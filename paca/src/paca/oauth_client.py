"""Google OAuth client configuration loader for paca.

Reads OAuth client credentials from a user-provided credentials.json
file in the paca config directory.
"""

from __future__ import annotations

import json
from pathlib import Path

from paca.config import config_dir


def credentials_path() -> Path:
    """Return the path where the OAuth credentials.json should be placed."""
    return config_dir() / "credentials.json"


def load_client_config() -> dict[str, object]:
    """Load OAuth client config from the user's credentials.json.

    Raises:
        FileNotFoundError: If credentials.json does not exist, with
            instructions for the user.
    """
    path = credentials_path()
    if not path.exists():
        msg = (
            f"OAuth client credentials not found at {path}\n"
            "\n"
            "To set up Google Calendar access:\n"
            "  1. Go to https://console.cloud.google.com/apis/credentials\n"
            "  2. Create an OAuth 2.0 Client ID (type: Desktop app)\n"
            "  3. Download the JSON and save it as:\n"
            f"     {path}\n"
        )
        raise FileNotFoundError(msg)
    return json.loads(path.read_text())
