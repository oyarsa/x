"""Tests for paca.input_capture."""

from pathlib import Path

import pytest

from paca.input_capture import (
    InputKind,
    make_text_input,
    read_file_input,
)


class TestReadFileInput:
    """Tests for read_file_input."""

    def test_text_file(self, tmp_path: Path) -> None:
        """Should read a text file as text input."""
        f = tmp_path / "appt.txt"
        f.write_text("Dentist Tuesday 2pm")
        result = read_file_input(f)
        assert result.kind == InputKind.TEXT
        assert result.text == "Dentist Tuesday 2pm"
        assert result.image_base64 is None

    def test_image_file(self, tmp_path: Path) -> None:
        """Should read an image file as base64."""
        f = tmp_path / "screenshot.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        result = read_file_input(f)
        assert result.kind == InputKind.IMAGE
        assert result.image_base64 is not None
        assert result.text is None

    def test_missing_file(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            read_file_input(tmp_path / "nope.txt")

    def test_stdin_input(self) -> None:
        """Should wrap raw text as text input."""
        result = make_text_input("Appointment at 3pm")
        assert result.kind == InputKind.TEXT
        assert result.text == "Appointment at 3pm"
