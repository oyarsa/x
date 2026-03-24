"""Tests for paca.schema."""

import pytest
from pydantic import ValidationError

from paca.schema import (
    DEFAULT_DURATION_MINUTES,
    Confidence,
    EventDraft,
    ExtractionResult,
    ReminderConfig,
    ReminderMethod,
)


class TestExtractionResult:
    """Tests for the ExtractionResult model."""

    def test_minimal_valid(self) -> None:
        """Should accept minimal fields."""
        result = ExtractionResult(
            title="Dentist",
            confidence=Confidence.HIGH,
        )
        assert result.title == "Dentist"
        assert result.date is None
        assert result.warnings == ()

    def test_full_fields(self) -> None:
        """Should accept all fields."""
        result = ExtractionResult(
            title="Nephrology",
            date="2026-06-23",
            start_time="14:00",
            end_time="15:00",
            duration_minutes=60,
            location="Croydon Hospital",
            notes="Bring referral letter",
            source_summary="Hospital appointment card",
            confidence=Confidence.MEDIUM,
            warnings=("date inferred from weekday",),
            detected_timezone="Europe/London",
        )
        assert result.duration_minutes == 60
        assert len(result.warnings) == 1

    def test_frozen(self) -> None:
        """Should be immutable."""
        result = ExtractionResult(title="Test", confidence=Confidence.LOW)
        with pytest.raises(ValidationError):
            result.title = "Changed"  # type: ignore[misc]


class TestReminderConfig:
    """Tests for ReminderConfig."""

    def test_defaults(self) -> None:
        """Should have popup method with 10min + 30min per spec section 18."""
        config = ReminderConfig()
        assert config.method == ReminderMethod.POPUP
        assert list(config.selected_minutes) == [10, 30]


class TestEventDraft:
    """Tests for EventDraft."""

    def test_empty_defaults(self) -> None:
        """Should default to empty strings."""
        draft = EventDraft()
        assert draft.title == ""
        assert draft.calendar_id == ""

    def test_model_copy_update(self) -> None:
        """Should support immutable updates via model_copy."""
        draft = EventDraft(title="Original")
        updated = draft.model_copy(update={"title": "Changed"})
        assert updated.title == "Changed"
        assert draft.title == "Original"


class TestConstants:
    """Tests for module-level constants."""

    def test_default_duration(self) -> None:
        """Should be 60 minutes per spec."""
        assert DEFAULT_DURATION_MINUTES == 60
