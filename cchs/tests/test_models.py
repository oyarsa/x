"""Tests for Pydantic models."""

from datetime import UTC, datetime

import pydantic
import pytest

from cchs.models import ExpandResult, Message, SearchResult


class TestMessage:
    """Test Message model."""

    def test_construction(self) -> None:
        """Test Message construction and field access."""
        msg = Message(
            session_id="abc-123",
            uuid="msg-456",
            role="user",
            content="How did we calculate PFA?",
            timestamp=datetime(2026, 3, 20, tzinfo=UTC),
            message_index=0,
        )
        assert msg.role == "user"
        assert msg.content == "How did we calculate PFA?"

    def test_frozen(self) -> None:
        """Test that Message instances are immutable (frozen)."""
        msg = Message(
            session_id="abc-123",
            uuid="msg-456",
            role="user",
            content="test",
            timestamp=datetime(2026, 3, 20, tzinfo=UTC),
            message_index=0,
        )
        with pytest.raises(pydantic.ValidationError):
            msg.role = "assistant"  # type: ignore[misc]


class TestSearchResult:
    """Test SearchResult model."""

    def test_construction(self) -> None:
        """Test SearchResult construction and field access."""
        match = Message(
            session_id="abc-123",
            uuid="msg-456",
            role="user",
            content="PFA calculation",
            timestamp=datetime(2026, 3, 20, tzinfo=UTC),
            message_index=2,
        )
        result = SearchResult(
            match=match,
            context_before=[],
            context_after=[],
            session_id="abc-123",
            rank=1.5,
        )
        assert result.match.content == "PFA calculation"
        assert result.rank == 1.5


class TestExpandResult:
    """Test ExpandResult model."""

    def test_construction(self) -> None:
        """Test ExpandResult construction and field access."""
        result = ExpandResult(messages=[], session_id="abc-123")
        assert result.messages == []
