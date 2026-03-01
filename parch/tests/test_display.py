"""Tests for parch.display — pure formatting helpers."""

from parch.display import (
    _format_timestamp,
    _should_page,
    _status_style,
    _truncate,
    strip_ansi,
)

# ---------------------------------------------------------------------------
# strip_ansi
# ---------------------------------------------------------------------------


class TestStripAnsi:
    """Remove ANSI escape sequences from text."""

    def test_plain_text_unchanged(self) -> None:
        assert strip_ansi("hello") == "hello"

    def test_removes_colour_codes(self) -> None:
        assert strip_ansi("\x1b[31mred\x1b[0m") == "red"

    def test_removes_bold(self) -> None:
        assert strip_ansi("\x1b[1mbold\x1b[0m") == "bold"

    def test_empty_string(self) -> None:
        assert strip_ansi("") == ""

    def test_multiple_codes(self) -> None:
        assert strip_ansi("\x1b[1;31mbold red\x1b[0m normal") == "bold red normal"

    def test_nested_codes(self) -> None:
        text = "\x1b[32m\x1b[1mgreen bold\x1b[0m\x1b[0m"
        assert strip_ansi(text) == "green bold"


# ---------------------------------------------------------------------------
# _status_style
# ---------------------------------------------------------------------------


class TestStatusStyle:
    """Map task status to a rich style string."""

    def test_success(self) -> None:
        assert _status_style("success") == "green"

    def test_failed(self) -> None:
        assert _status_style("failed") == "red bold"

    def test_killed(self) -> None:
        assert _status_style("killed") == "red"

    def test_running(self) -> None:
        assert _status_style("running") == "blue"

    def test_queued(self) -> None:
        assert _status_style("queued") == "yellow"

    def test_paused(self) -> None:
        assert _status_style("paused") == "yellow"

    def test_dependency_failed(self) -> None:
        assert _status_style("dependency_failed") == "red"

    def test_unknown_defaults_to_white(self) -> None:
        assert _status_style("bogus") == "white"


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------


class TestTruncate:
    """Truncate text with ellipsis if over max_len."""

    def test_short_text_unchanged(self) -> None:
        assert _truncate("hello", 10) == "hello"

    def test_exact_length_unchanged(self) -> None:
        assert _truncate("hello", 5) == "hello"

    def test_long_text_truncated(self) -> None:
        result = _truncate("hello world", 6)
        assert result == "hello…"
        assert len(result) == 6

    def test_single_char_max(self) -> None:
        assert _truncate("hello", 1) == "…"

    def test_empty_string(self) -> None:
        assert _truncate("", 5) == ""


# ---------------------------------------------------------------------------
# _format_timestamp
# ---------------------------------------------------------------------------


class TestFormatTimestamp:
    """Format ISO timestamps for table display."""

    def test_empty_string(self) -> None:
        assert _format_timestamp("") == ""

    def test_iso_with_timezone(self) -> None:
        assert (
            _format_timestamp("2026-01-01T12:30:45.123456+00:00")
            == "2026-01-01 12:30:45"
        )

    def test_iso_with_z(self) -> None:
        assert _format_timestamp("2026-01-01T12:30:45Z") == "2026-01-01 12:30:45"

    def test_iso_no_subseconds(self) -> None:
        assert _format_timestamp("2026-01-01T12:30:45+00:00") == "2026-01-01 12:30:45"

    def test_bare_datetime(self) -> None:
        assert _format_timestamp("2026-01-01T12:30:45") == "2026-01-01 12:30:45"

    def test_negative_utc_offset(self) -> None:
        assert _format_timestamp("2026-01-01T12:30:45-05:00") == "2026-01-01 12:30:45"


# ---------------------------------------------------------------------------
# _should_page
# ---------------------------------------------------------------------------


class TestShouldPage:
    """Decide whether to pipe output through a pager."""

    def test_never_mode_always_false(self) -> None:
        assert not _should_page("x" * 1000, "never", is_tty=True)

    def test_always_mode_always_true(self) -> None:
        assert _should_page("short", "always", is_tty=False)

    def test_auto_not_tty(self) -> None:
        assert not _should_page("line\n" * 100, "auto", is_tty=False)

    def test_auto_tty_short_output(self) -> None:
        assert not _should_page("short output", "auto", is_tty=True)

    def test_auto_tty_long_output(self) -> None:
        assert _should_page("line\n" * 50, "auto", is_tty=True)

    def test_auto_tty_exactly_40_lines(self) -> None:
        assert not _should_page("line\n" * 40, "auto", is_tty=True)

    def test_auto_tty_41_lines(self) -> None:
        assert _should_page("line\n" * 41, "auto", is_tty=True)


# ---------------------------------------------------------------------------
# Functions that need mocks / side effects (future work)
# ---------------------------------------------------------------------------
#
# format_task_table:
#   Prints a rich Table to stdout.  Would need stdout capture or console
#   capture to verify output.
#
# print_task_output:
#   Writes to stdout or spawns a pager subprocess.  Would need stdout
#   capture and subprocess mocking.
#
# _format_meta_header:
#   Uses rich Console.capture() internally — could be tested with a
#   snapshot approach but requires rich rendering.
#
# _page_output:
#   Spawns `less -R` subprocess.  Needs subprocess mocking.
