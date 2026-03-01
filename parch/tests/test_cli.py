"""Tests for parch.cli — pure helper functions."""

from datetime import UTC, datetime, timedelta

import pytest
import typer

from parch.cli import (
    _apply_time_filters,
    _entry_time,
    _parse_date,
    _parse_duration,
    _parse_iso,
    _sort_entries,
)
from parch.models import IndexEntry


def _make_entry(
    *,
    archive_id: str = "test-id",
    created_at: str = "2026-01-01T00:00:00+00:00",
    start_at: str | None = None,
    end_at: str | None = None,
    status: str = "success",
    group: str = "default",
    command: str = "echo test",
    cwd: str = "/test/workdir",
) -> IndexEntry:
    return IndexEntry(
        archive_id=archive_id,
        fingerprint="fp",
        status=status,
        group=group,
        cwd=cwd,
        command=command,
        created_at=created_at,
        start_at=start_at,
        end_at=end_at,
        pueue_task_id="0",
    )


# ---------------------------------------------------------------------------
# _parse_iso
# ---------------------------------------------------------------------------


class TestParseIso:
    """Parse ISO 8601 timestamps with various formats."""

    def test_standard_iso(self) -> None:
        result = _parse_iso("2026-01-15T10:30:00+00:00")
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_trailing_z(self) -> None:
        result = _parse_iso("2026-01-15T10:30:00Z")
        assert result.year == 2026
        assert result.hour == 10

    def test_with_subseconds(self) -> None:
        result = _parse_iso("2026-01-15T10:30:00.123456+00:00")
        assert result.year == 2026

    def test_empty_string_returns_min(self) -> None:
        result = _parse_iso("")
        assert result == datetime.min.replace(tzinfo=UTC)

    def test_invalid_string_returns_min(self) -> None:
        result = _parse_iso("not-a-date")
        assert result == datetime.min.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------


class TestParseDate:
    """Parse date or datetime strings into timezone-aware datetimes."""

    def test_date_only(self) -> None:
        result = _parse_date("2026-03-15")
        assert result == datetime(2026, 3, 15, tzinfo=UTC)

    def test_datetime(self) -> None:
        result = _parse_date("2026-03-15T10:30:00")
        assert result.hour == 10
        assert result.minute == 30

    def test_invalid_raises_bad_parameter(self) -> None:
        with pytest.raises(typer.BadParameter):
            _parse_date("not-a-date")


# ---------------------------------------------------------------------------
# _parse_duration
# ---------------------------------------------------------------------------


class TestParseDuration:
    """Parse duration strings like '7d', '24h' into timedelta."""

    def test_days(self) -> None:
        assert _parse_duration("7d") == timedelta(days=7)

    def test_hours(self) -> None:
        assert _parse_duration("24h") == timedelta(hours=24)

    def test_minutes(self) -> None:
        assert _parse_duration("30m") == timedelta(minutes=30)

    def test_seconds(self) -> None:
        assert _parse_duration("60s") == timedelta(seconds=60)

    def test_large_value(self) -> None:
        assert _parse_duration("365d") == timedelta(days=365)

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(typer.BadParameter):
            _parse_duration("invalid")

    def test_no_unit_raises(self) -> None:
        with pytest.raises(typer.BadParameter):
            _parse_duration("42")

    def test_unknown_unit_raises(self) -> None:
        with pytest.raises(typer.BadParameter):
            _parse_duration("10w")


# ---------------------------------------------------------------------------
# _entry_time
# ---------------------------------------------------------------------------


class TestEntryTime:
    """Get the best available timestamp for time filtering."""

    def test_prefers_end_at(self) -> None:
        entry = _make_entry(
            created_at="2026-01-01T00:00:00+00:00",
            start_at="2026-01-01T00:00:01+00:00",
            end_at="2026-01-01T00:00:02+00:00",
        )
        assert _entry_time(entry).second == 2

    def test_falls_back_to_start_at(self) -> None:
        entry = _make_entry(
            created_at="2026-01-01T00:00:00+00:00",
            start_at="2026-01-01T00:00:01+00:00",
        )
        assert _entry_time(entry).second == 1

    def test_falls_back_to_created_at(self) -> None:
        entry = _make_entry(created_at="2026-01-01T00:00:05+00:00")
        assert _entry_time(entry).second == 5


# ---------------------------------------------------------------------------
# _sort_entries
# ---------------------------------------------------------------------------


class TestSortEntries:
    """Sort index entries by timestamp fields."""

    def test_default_sort_by_end_newest_first(self) -> None:
        entries = [
            _make_entry(archive_id="old", end_at="2026-01-01T00:00:00"),
            _make_entry(archive_id="new", end_at="2026-01-02T00:00:00"),
        ]
        result = _sort_entries(entries, "end", reverse=False)
        assert result[0].archive_id == "new"
        assert result[1].archive_id == "old"

    def test_reversed_sort_oldest_first(self) -> None:
        entries = [
            _make_entry(archive_id="new", end_at="2026-01-02T00:00:00"),
            _make_entry(archive_id="old", end_at="2026-01-01T00:00:00"),
        ]
        result = _sort_entries(entries, "end", reverse=True)
        assert result[0].archive_id == "old"
        assert result[1].archive_id == "new"

    def test_sort_by_created(self) -> None:
        entries = [
            _make_entry(archive_id="old", created_at="2026-01-01T00:00:00"),
            _make_entry(archive_id="new", created_at="2026-01-02T00:00:00"),
        ]
        result = _sort_entries(entries, "created", reverse=False)
        assert result[0].archive_id == "new"

    def test_sort_by_start(self) -> None:
        entries = [
            _make_entry(archive_id="old", start_at="2026-01-01T00:00:00"),
            _make_entry(archive_id="new", start_at="2026-01-02T00:00:00"),
        ]
        result = _sort_entries(entries, "start", reverse=False)
        assert result[0].archive_id == "new"

    def test_empty_list(self) -> None:
        assert _sort_entries([], "end", reverse=False) == []

    def test_sort_end_falls_back_to_start_and_created(self) -> None:
        entries = [
            _make_entry(
                archive_id="a",
                created_at="2026-01-01T00:00:00",
                start_at="2026-01-01T00:00:01",
            ),
            _make_entry(
                archive_id="b",
                created_at="2026-01-02T00:00:00",
            ),
        ]
        result = _sort_entries(entries, "end", reverse=False)
        assert result[0].archive_id == "b"


# ---------------------------------------------------------------------------
# _apply_time_filters
# ---------------------------------------------------------------------------


class TestApplyTimeFilters:
    """Apply time-based filters to index entries."""

    _NOW = datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC)

    def _entry_at(self, archive_id: str, ts: str) -> IndexEntry:
        return _make_entry(archive_id=archive_id, end_at=ts, created_at=ts)

    def test_no_filters_returns_all(self) -> None:
        entries = [self._entry_at("a", "2026-01-01T00:00:00+00:00")]
        result = _apply_time_filters(
            entries, None, None, None, False, False, False, now=self._NOW
        )
        assert len(result) == 1

    def test_today_filter(self) -> None:
        today = self._entry_at("today", "2026-02-15T10:00:00+00:00")
        yesterday = self._entry_at("yesterday", "2026-02-14T10:00:00+00:00")
        result = _apply_time_filters(
            [today, yesterday], None, None, None, True, False, False, now=self._NOW
        )
        assert [e.archive_id for e in result] == ["today"]

    def test_yesterday_filter(self) -> None:
        today = self._entry_at("today", "2026-02-15T10:00:00+00:00")
        yesterday = self._entry_at("yesterday", "2026-02-14T10:00:00+00:00")
        old = self._entry_at("old", "2026-02-13T10:00:00+00:00")
        result = _apply_time_filters(
            [today, yesterday, old],
            None,
            None,
            None,
            False,
            True,
            False,
            now=self._NOW,
        )
        assert [e.archive_id for e in result] == ["yesterday"]

    def test_last_week_filter(self) -> None:
        recent = self._entry_at("recent", "2026-02-10T10:00:00+00:00")
        old = self._entry_at("old", "2026-01-01T10:00:00+00:00")
        result = _apply_time_filters(
            [recent, old], None, None, None, False, False, True, now=self._NOW
        )
        assert [e.archive_id for e in result] == ["recent"]

    def test_since_filter(self) -> None:
        recent = self._entry_at("recent", "2026-02-14T10:00:00+00:00")
        old = self._entry_at("old", "2026-01-01T10:00:00+00:00")
        result = _apply_time_filters(
            [recent, old], None, None, "3d", False, False, False, now=self._NOW
        )
        assert [e.archive_id for e in result] == ["recent"]

    def test_from_date_filter(self) -> None:
        recent = self._entry_at("recent", "2026-02-10T10:00:00+00:00")
        old = self._entry_at("old", "2026-01-01T10:00:00+00:00")
        result = _apply_time_filters(
            [recent, old], "2026-02-01", None, None, False, False, False, now=self._NOW
        )
        assert [e.archive_id for e in result] == ["recent"]

    def test_to_date_filter(self) -> None:
        recent = self._entry_at("recent", "2026-02-10T10:00:00+00:00")
        old = self._entry_at("old", "2026-01-01T10:00:00+00:00")
        result = _apply_time_filters(
            [recent, old], None, "2026-01-15", None, False, False, False, now=self._NOW
        )
        assert [e.archive_id for e in result] == ["old"]

    def test_from_and_to_date_combined(self) -> None:
        a = self._entry_at("a", "2026-01-01T00:00:00+00:00")
        b = self._entry_at("b", "2026-01-15T00:00:00+00:00")
        c = self._entry_at("c", "2026-02-10T00:00:00+00:00")
        result = _apply_time_filters(
            [a, b, c],
            "2026-01-10",
            "2026-01-20",
            None,
            False,
            False,
            False,
            now=self._NOW,
        )
        assert [e.archive_id for e in result] == ["b"]


# ---------------------------------------------------------------------------
# Functions that need mocks / side effects (future work)
# ---------------------------------------------------------------------------
#
# _auto_sync:
#   Calls sync() which runs pueue and does file I/O.
#
# _resolve_task:
#   Calls load_task() and load_index() which read from disk.
#
# All @app.command functions:
#   Depend on typer context, file I/O, and subprocess calls.
