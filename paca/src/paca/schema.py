"""Pydantic models for extracted appointment data and event drafts."""

from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel


class Confidence(StrEnum):
    """Extraction confidence level."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExtractionResult(BaseModel, frozen=True):
    """Structured data extracted from appointment text or image by the LLM."""

    title: str
    date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration_minutes: int | None = None
    location: str | None = None
    notes: str | None = None
    source_summary: str | None = None
    confidence: Confidence = Confidence.MEDIUM
    warnings: Sequence[str] = ()
    detected_timezone: str | None = None


class ReminderPreset(BaseModel, frozen=True):
    """A single reminder preset with label and minutes."""

    label: str
    minutes: int


REMINDER_PRESETS: Sequence[ReminderPreset] = (
    ReminderPreset(label="10 min", minutes=10),
    ReminderPreset(label="30 min", minutes=30),
    ReminderPreset(label="1 hour", minutes=60),
    ReminderPreset(label="4 hours", minutes=240),
    ReminderPreset(label="1 day", minutes=1440),
)
"""Available reminder presets per spec section 9.2."""


class ReminderMethod(StrEnum):
    """Reminder delivery method."""

    DEFAULT = "default"
    POPUP = "popup"
    EMAIL = "email"


class ReminderConfig(BaseModel, frozen=True):
    """User's reminder selections for an event."""

    method: ReminderMethod = ReminderMethod.POPUP
    selected_minutes: Sequence[int] = (10, 30)


class EventDraft(BaseModel, frozen=True):
    """Immutable draft of a calendar event, built from ExtractionResult + user edits.

    Use `model_copy(update=...)` to produce new instances when editing fields.
    """

    title: str = ""
    date: str = ""
    start_time: str = ""
    end_time: str = ""
    duration_minutes: int | None = None
    location: str = ""
    notes: str = ""
    calendar_id: str = ""
    calendar_name: str = ""
    reminders: ReminderConfig = ReminderConfig()
    confidence: Confidence = Confidence.MEDIUM
    warnings: Sequence[str] = ()
    source_summary: str = ""


DEFAULT_DURATION_MINUTES: int = 60
"""Fallback event duration when no end time or duration is extracted."""
