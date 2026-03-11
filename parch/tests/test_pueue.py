"""Tests for parch.pueue — Pueue JSON parsing functions."""

from typing import Any

from parch.models import TaskStatus
from parch.pueue import (
    _extract_done_timestamps,
    _map_done_status,
    _map_result_value,
    _map_simple_status,
    _opt_str_field,
    _str_field,
    parse_pueue_status,
    parse_pueue_tasks,
)

# ---------------------------------------------------------------------------
# parse_pueue_status  (top-level dispatcher)
# ---------------------------------------------------------------------------


class TestParsePueueStatus:
    """Normalise Pueue's Rust enum-style status JSON."""

    def test_simple_queued(self) -> None:
        assert parse_pueue_status("Queued") == TaskStatus.QUEUED

    def test_simple_running(self) -> None:
        assert parse_pueue_status("Running") == TaskStatus.RUNNING

    def test_simple_paused(self) -> None:
        assert parse_pueue_status("Paused") == TaskStatus.PAUSED

    def test_simple_locked(self) -> None:
        assert parse_pueue_status("Locked") == TaskStatus.LOCKED

    def test_simple_stashed(self) -> None:
        assert parse_pueue_status("Stashed") == TaskStatus.STASHED

    def test_done_modern_success(self) -> None:
        status = {
            "Done": {
                "start": "2026-01-01",
                "end": "2026-01-02",
                "result": "Success",
            },
        }
        assert parse_pueue_status(status) == TaskStatus.SUCCESS

    def test_done_modern_failed(self) -> None:
        status = {
            "Done": {
                "start": "2026-01-01",
                "end": "2026-01-02",
                "result": {"Failed": 1},
            },
        }
        assert parse_pueue_status(status) == TaskStatus.FAILED

    def test_done_legacy_string(self) -> None:
        assert parse_pueue_status({"Done": "Success"}) == TaskStatus.SUCCESS

    def test_stashed_dict(self) -> None:
        assert (
            parse_pueue_status({"Stashed": {"enqueue_at": None}}) == TaskStatus.STASHED
        )

    def test_unknown_string(self) -> None:
        assert parse_pueue_status("Bogus") == TaskStatus.UNKNOWN

    def test_unknown_non_dict_non_str(self) -> None:
        assert parse_pueue_status(42) == TaskStatus.UNKNOWN

    def test_unknown_dict_key(self) -> None:
        assert parse_pueue_status({"Bogus": "value"}) == TaskStatus.UNKNOWN


# ---------------------------------------------------------------------------
# _map_simple_status
# ---------------------------------------------------------------------------


class TestMapSimpleStatus:
    """Map plain status strings to TaskStatus."""

    def test_all_known(self) -> None:
        assert _map_simple_status("Queued") == TaskStatus.QUEUED
        assert _map_simple_status("Running") == TaskStatus.RUNNING
        assert _map_simple_status("Paused") == TaskStatus.PAUSED
        assert _map_simple_status("Locked") == TaskStatus.LOCKED
        assert _map_simple_status("Stashed") == TaskStatus.STASHED

    def test_unknown(self) -> None:
        assert _map_simple_status("Bogus") == TaskStatus.UNKNOWN


# ---------------------------------------------------------------------------
# _map_done_status
# ---------------------------------------------------------------------------


class TestMapDoneStatus:
    """Map the Done variant's inner value to TaskStatus."""

    def test_legacy_string_success(self) -> None:
        assert _map_done_status("Success") == TaskStatus.SUCCESS

    def test_legacy_string_killed(self) -> None:
        assert _map_done_status("Killed") == TaskStatus.KILLED

    def test_modern_with_result_string(self) -> None:
        assert _map_done_status({"result": "Success"}) == TaskStatus.SUCCESS

    def test_modern_with_result_dict(self) -> None:
        assert _map_done_status({"result": {"Failed": 1}}) == TaskStatus.FAILED

    def test_legacy_dict_success(self) -> None:
        assert _map_done_status({"Success": None}) == TaskStatus.SUCCESS

    def test_legacy_dict_failed(self) -> None:
        assert _map_done_status({"Failed": 1}) == TaskStatus.FAILED

    def test_legacy_dict_killed(self) -> None:
        assert _map_done_status({"Killed": None}) == TaskStatus.KILLED

    def test_legacy_dict_dependency_failed(self) -> None:
        assert (
            _map_done_status({"DependencyFailed": None}) == TaskStatus.DEPENDENCY_FAILED
        )

    def test_unknown_non_dict(self) -> None:
        assert _map_done_status(42) == TaskStatus.UNKNOWN

    def test_unknown_dict(self) -> None:
        assert _map_done_status({"SomethingElse": None}) == TaskStatus.UNKNOWN


# ---------------------------------------------------------------------------
# _map_result_value
# ---------------------------------------------------------------------------


class TestMapResultValue:
    """Map pueue result value (string or dict) to TaskStatus."""

    def test_success_string(self) -> None:
        assert _map_result_value("Success") == TaskStatus.SUCCESS

    def test_killed_string(self) -> None:
        assert _map_result_value("Killed") == TaskStatus.KILLED

    def test_dependency_failed_string(self) -> None:
        assert _map_result_value("DependencyFailed") == TaskStatus.DEPENDENCY_FAILED

    def test_failed_dict(self) -> None:
        assert _map_result_value({"Failed": 1}) == TaskStatus.FAILED

    def test_dependency_failed_dict(self) -> None:
        assert (
            _map_result_value({"DependencyFailed": None})
            == TaskStatus.DEPENDENCY_FAILED
        )

    def test_unknown_string(self) -> None:
        assert _map_result_value("Bogus") == TaskStatus.UNKNOWN

    def test_unknown_type(self) -> None:
        assert _map_result_value(42) == TaskStatus.UNKNOWN


# ---------------------------------------------------------------------------
# _extract_done_timestamps
# ---------------------------------------------------------------------------


class TestExtractDoneTimestamps:
    """Extract start/end from the Done variant's dict."""

    def test_modern_with_timestamps(self) -> None:
        status: dict[str, Any] = {
            "Done": {
                "start": "2026-01-01T00:00:00",
                "end": "2026-01-01T00:01:00",
                "result": "Success",
            },
        }
        start, end = _extract_done_timestamps(status)
        assert start == "2026-01-01T00:00:00"
        assert end == "2026-01-01T00:01:00"

    def test_legacy_done_string(self) -> None:
        start, end = _extract_done_timestamps({"Done": "Success"})
        assert start is None
        assert end is None

    def test_not_a_dict(self) -> None:
        start, end = _extract_done_timestamps("Running")
        assert start is None
        assert end is None

    def test_no_done_key(self) -> None:
        status: dict[str, str] = {"Running": "active"}
        start, end = _extract_done_timestamps(status)
        assert start is None
        assert end is None


# ---------------------------------------------------------------------------
# _str_field / _opt_str_field
# ---------------------------------------------------------------------------


class TestStrField:
    """Safe string extraction from a JSON dict."""

    def test_existing_key(self) -> None:
        assert _str_field({"name": "alice"}, "name") == "alice"

    def test_missing_key_default(self) -> None:
        assert _str_field({"name": "alice"}, "age") == ""

    def test_missing_key_custom_default(self) -> None:
        assert _str_field({"name": "alice"}, "age", "unknown") == "unknown"

    def test_none_value_returns_default(self) -> None:
        assert _str_field({"name": None}, "name") == ""

    def test_int_value_coerced(self) -> None:
        assert _str_field({"id": 42}, "id") == "42"


class TestOptStrField:
    """Safe optional string extraction from a JSON dict."""

    def test_existing_key(self) -> None:
        assert _opt_str_field({"name": "alice"}, "name") == "alice"

    def test_missing_key(self) -> None:
        assert _opt_str_field({"name": "alice"}, "age") is None

    def test_none_value(self) -> None:
        assert _opt_str_field({"name": None}, "name") is None

    def test_int_value_coerced(self) -> None:
        assert _opt_str_field({"id": 42}, "id") == "42"


# ---------------------------------------------------------------------------
# parse_pueue_tasks  (full JSON → PueueTask list)
# ---------------------------------------------------------------------------


class TestParsePueueTasks:
    """Parse pueue log JSON into PueueTask objects."""

    def test_modern_format(self) -> None:
        raw: dict[str, Any] = {
            "0": {
                "task": {
                    "id": 0,
                    "original_command": "echo hello",
                    "path": "/test/workdir",
                    "group": "default",
                    "status": {
                        "Done": {
                            "start": "2026-01-01T00:00:01",
                            "end": "2026-01-01T00:00:02",
                            "result": "Success",
                        },
                    },
                    "created_at": "2026-01-01T00:00:00",
                    "start": "2026-01-01T00:00:01",
                    "end": "2026-01-01T00:00:02",
                },
                "output": "hello\n",
            },
        }
        tasks = parse_pueue_tasks(raw)

        assert len(tasks) == 1
        task = tasks[0]
        assert task.task_id == "0"
        assert task.command == "echo hello"
        assert task.cwd == "/test/workdir"
        assert task.group == "default"
        assert task.status == TaskStatus.SUCCESS
        assert task.output == "hello\n"
        assert task.start_at == "2026-01-01T00:00:01"
        assert task.end_at == "2026-01-01T00:00:02"

    def test_flat_format(self) -> None:
        raw: dict[str, Any] = {
            "1": {
                "id": 1,
                "command": "ls",
                "cwd": "/home",
                "group": "batch",
                "status": "Running",
                "created_at": "2026-02-01T10:00:00",
                "output": "",
            },
        }
        tasks = parse_pueue_tasks(raw)

        assert len(tasks) == 1
        assert tasks[0].command == "ls"
        assert tasks[0].cwd == "/home"
        assert tasks[0].group == "batch"
        assert tasks[0].status == TaskStatus.RUNNING

    def test_skips_non_dict_entries(self) -> None:
        raw: dict[str, Any] = {
            "0": "not a dict",
            "1": {
                "task": {
                    "original_command": "echo hi",
                    "path": "/test/workdir",
                    "group": "default",
                    "status": "Queued",
                    "created_at": "2026-01-01T00:00:00",
                },
                "output": "",
            },
        }
        tasks = parse_pueue_tasks(raw)
        assert len(tasks) == 1

    def test_empty_input(self) -> None:
        assert parse_pueue_tasks({}) == []

    def test_timestamps_extracted_from_done_status(self) -> None:
        """When top-level start/end are absent, extract from Done status."""
        raw: dict[str, Any] = {
            "0": {
                "task": {
                    "original_command": "echo hi",
                    "path": "/test/workdir",
                    "group": "default",
                    "status": {
                        "Done": {
                            "start": "2026-01-01T00:00:01",
                            "end": "2026-01-01T00:00:02",
                            "result": "Success",
                        },
                    },
                    "created_at": "2026-01-01T00:00:00",
                },
                "output": "",
            },
        }
        tasks = parse_pueue_tasks(raw)
        assert tasks[0].start_at == "2026-01-01T00:00:01"
        assert tasks[0].end_at == "2026-01-01T00:00:02"

    def test_multiple_tasks(self) -> None:
        raw: dict[str, Any] = {
            "0": {
                "task": {
                    "original_command": "echo 1",
                    "path": "/test/workdir",
                    "group": "default",
                    "status": "Queued",
                    "created_at": "2026-01-01T00:00:00",
                },
                "output": "",
            },
            "1": {
                "task": {
                    "original_command": "echo 2",
                    "path": "/test/workdir",
                    "group": "default",
                    "status": "Running",
                    "created_at": "2026-01-01T00:00:01",
                },
                "output": "",
            },
        }
        tasks = parse_pueue_tasks(raw)
        assert len(tasks) == 2

    def test_command_fallback_to_command_field(self) -> None:
        """Uses 'command' when 'original_command' is absent."""
        raw: dict[str, Any] = {
            "0": {
                "task": {
                    "command": "ls -la",
                    "path": "/test/workdir",
                    "group": "default",
                    "status": "Queued",
                    "created_at": "2026-01-01T00:00:00",
                },
                "output": "",
            },
        }
        tasks = parse_pueue_tasks(raw)
        assert tasks[0].command == "ls -la"

    def test_cwd_fallback_to_cwd_field(self) -> None:
        """Uses 'cwd' when 'path' is absent."""
        raw: dict[str, Any] = {
            "0": {
                "task": {
                    "original_command": "echo hi",
                    "cwd": "/home/user",
                    "group": "default",
                    "status": "Queued",
                    "created_at": "2026-01-01T00:00:00",
                },
                "output": "",
            },
        }
        tasks = parse_pueue_tasks(raw)
        assert tasks[0].cwd == "/home/user"

    def test_pueue_status_flat_format(self) -> None:
        """Flat entries from ``pueue status --json`` are parsed correctly."""
        raw: dict[str, Any] = {
            "23": {
                "id": 23,
                "created_at": "2026-03-10T12:49:57Z",
                "original_command": "echo done",
                "command": "echo done",
                "path": "/home/user",
                "group": "default",
                "status": {
                    "Done": {
                        "enqueued_at": "2026-03-10T12:49:57Z",
                        "start": "2026-03-10T12:49:58Z",
                        "end": "2026-03-10T12:50:00Z",
                        "result": "Success",
                    },
                },
            },
        }
        tasks = parse_pueue_tasks(raw)
        assert len(tasks) == 1
        assert tasks[0].task_id == "23"
        assert tasks[0].command == "echo done"
        assert tasks[0].status == TaskStatus.SUCCESS
        assert tasks[0].output == ""

    def test_pueue_status_with_log_output(self) -> None:
        """``_log_output`` injected by sync is picked up as output."""
        raw: dict[str, Any] = {
            "5": {
                "id": 5,
                "created_at": "2026-01-01T00:00:00",
                "original_command": "echo hi",
                "path": "/test",
                "group": "default",
                "status": {"Done": {"result": "Success"}},
                "_log_output": "hi\n",
            },
        }
        tasks = parse_pueue_tasks(raw)
        assert tasks[0].output == "hi\n"


# ---------------------------------------------------------------------------
# Functions that need mocks / side effects (future work)
# ---------------------------------------------------------------------------
#
# run_pueue_log:
#   Runs `pueue log --json` via subprocess.  Would need a subprocess mock or
#   a real pueue fixture to test.
