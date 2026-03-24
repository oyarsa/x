"""Input capture from clipboard, files, and stdin."""

import base64
import logging
from enum import StrEnum
from pathlib import Path

import pyperclip
from pydantic import BaseModel

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
)
"""File extensions recognised as images."""


class InputKind(StrEnum):
    """Type of captured input."""

    TEXT = "text"
    IMAGE = "image"


class CapturedInput(BaseModel, frozen=True):
    """Content captured from clipboard, file, or manual entry."""

    kind: InputKind
    text: str | None = None
    image_base64: str | None = None
    image_media_type: str | None = None
    source_description: str = ""


def make_text_input(text: str, *, source: str = "manual") -> CapturedInput:
    """Wrap raw text as a CapturedInput.

    Args:
        text: The text content.
        source: Description of where the text came from.

    Returns:
        A text CapturedInput.
    """
    return CapturedInput(kind=InputKind.TEXT, text=text, source_description=source)


def _media_type_for(suffix: str) -> str:
    """Return the MIME type for an image file extension.

    Args:
        suffix: File extension including the dot (e.g. ".png").

    Returns:
        MIME type string.
    """
    mapping: dict[str, str] = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mapping.get(suffix.lower(), "image/png")


def read_file_input(path: Path) -> CapturedInput:
    """Read input from a file path.

    Args:
        path: Path to a text or image file.

    Returns:
        CapturedInput with the file content.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not path.exists():
        msg = f"File not found: {path}"
        raise FileNotFoundError(msg)

    if path.suffix.lower() in IMAGE_EXTENSIONS:
        data = path.read_bytes()
        return CapturedInput(
            kind=InputKind.IMAGE,
            image_base64=base64.b64encode(data).decode("ascii"),
            image_media_type=_media_type_for(path.suffix),
            source_description=str(path),
        )

    return CapturedInput(
        kind=InputKind.TEXT,
        text=path.read_text(),
        source_description=str(path),
    )


def capture_clipboard() -> CapturedInput | None:
    """Attempt to capture content from the system clipboard.

    Tries text clipboard via pyperclip. Image clipboard is not supported
    by pyperclip; users should use file input for images.

    Returns:
        CapturedInput if clipboard has text, None otherwise.
    """
    try:
        text = pyperclip.paste()
    except pyperclip.PyperclipException:
        logger.warning("Clipboard not available")
        return None

    if not text or not text.strip():
        return None

    return CapturedInput(
        kind=InputKind.TEXT,
        text=text.strip(),
        source_description="clipboard",
    )
