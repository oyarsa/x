"""Tests for paca.extractor."""

from paca.extractor import EXTRACTION_SYSTEM_PROMPT, build_extraction_input
from paca.input_capture import CapturedInput, InputKind


class TestBuildExtractionInput:
    """Tests for Responses API input construction."""

    def test_text_input(self) -> None:
        """Should build a user message with text content."""
        captured = CapturedInput(kind=InputKind.TEXT, text="Dentist Tuesday 2pm")
        items = build_extraction_input(captured)
        assert len(items) == 1
        assert items[0]["role"] == "user"
        assert items[0]["type"] == "message"
        assert items[0]["content"] == "Dentist Tuesday 2pm"

    def test_image_input(self) -> None:
        """Should build a user message with image content parts."""
        captured = CapturedInput(
            kind=InputKind.IMAGE,
            image_base64="abc123",
            image_media_type="image/png",
        )
        items = build_extraction_input(captured)
        assert len(items) == 1
        assert items[0]["role"] == "user"
        assert items[0]["type"] == "message"
        content = items[0]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "input_image"
        assert "data:image/png;base64,abc123" in content[0]["image_url"]


class TestSystemPrompt:
    """Tests for the extraction system prompt."""

    def test_prompt_mentions_json(self) -> None:
        """Should instruct the model to return JSON."""
        assert "JSON" in EXTRACTION_SYSTEM_PROMPT

    def test_prompt_mentions_single_event(self) -> None:
        """Should instruct extraction of exactly one event."""
        assert "one" in EXTRACTION_SYSTEM_PROMPT.lower()
