"""Tests for paca.calendar_provider."""

from paca.calendar_provider import (
    CalendarInfo,
    build_event_body,
    compute_end_time,
    pick_default_calendar,
)
from paca.schema import EventDraft, ReminderConfig, ReminderMethod


class TestPickDefaultCalendar:
    """Tests for pick_default_calendar."""

    def test_exact_name_match(self) -> None:
        """Should prefer exact name match."""
        calendars = [
            CalendarInfo(id="1", name="Work", primary=True),
            CalendarInfo(id="2", name="Compromissos", primary=False),
        ]
        result = pick_default_calendar(calendars, preferred_name="Compromissos")
        assert result is not None
        assert result.id == "2"

    def test_fallback_to_primary(self) -> None:
        """Should fall back to primary calendar."""
        calendars = [
            CalendarInfo(id="1", name="Work", primary=True),
            CalendarInfo(id="2", name="Personal", primary=False),
        ]
        result = pick_default_calendar(calendars, preferred_name="Nonexistent")
        assert result is not None
        assert result.id == "1"

    def test_fallback_to_first(self) -> None:
        """Should fall back to first calendar."""
        calendars = [
            CalendarInfo(id="1", name="Work", primary=False),
            CalendarInfo(id="2", name="Personal", primary=False),
        ]
        result = pick_default_calendar(calendars, preferred_name="Nonexistent")
        assert result is not None
        assert result.id == "1"

    def test_empty_list(self) -> None:
        """Should return None for empty list."""
        result = pick_default_calendar([], preferred_name="X")
        assert result is None


class TestComputeEndTime:
    """Tests for compute_end_time."""

    def test_explicit_end(self) -> None:
        """Should return explicit end time."""
        assert compute_end_time("09:00", end_time="10:00") == "10:00"

    def test_duration(self) -> None:
        """Should compute from duration."""
        assert compute_end_time("09:00", duration_minutes=90) == "10:30"

    def test_default_one_hour(self) -> None:
        """Should default to 1 hour."""
        assert compute_end_time("14:00") == "15:00"


class TestBuildEventBody:
    """Tests for build_event_body."""

    def test_basic_event(self) -> None:
        """Should build a valid event body dict."""
        draft = EventDraft(
            title="Dentist",
            date="2026-06-23",
            start_time="14:00",
            end_time="15:00",
            calendar_id="primary",
            calendar_name="Primary",
            location="123 Main St",
        )
        body = build_event_body(draft, timezone="Europe/London")
        assert body["summary"] == "Dentist"
        assert body["location"] == "123 Main St"
        assert "dateTime" in body["start"]

    def test_reminders_override(self) -> None:
        """Should set useDefault=false with explicit reminders."""
        draft = EventDraft(
            title="Test",
            date="2026-06-23",
            start_time="14:00",
            end_time="15:00",
            calendar_id="primary",
            reminders=ReminderConfig(
                method=ReminderMethod.POPUP, selected_minutes=(10, 30)
            ),
        )
        body = build_event_body(draft, timezone="Europe/London")
        assert body["reminders"]["useDefault"] is False
        assert len(body["reminders"]["overrides"]) == 2
