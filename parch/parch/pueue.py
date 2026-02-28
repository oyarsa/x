"""Pueue CLI interaction — run commands and parse JSON output."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, cast

from parch.models import TaskStatus
from parch.typing import is_dict_of


@dataclass
class PueueTask:
    """A single task parsed from pueue log --json."""

    task_id: str
    command: str
    cwd: str
    group: str
    status: TaskStatus
    created_at: str
    start_at: str | None
    end_at: str | None
    output: str
    raw_json: dict[str, Any]


def run_pueue_log(
    pueue_bin: str = "pueue",
    timeout: int | None = None,
) -> dict[str, Any]:
    """Run `pueue log --json` and return parsed JSON."""
    cmd = [pueue_bin, "log", "--json"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        print(f"Error: pueue binary not found at '{pueue_bin}'", file=sys.stderr)
        sys.exit(2)
    except subprocess.TimeoutExpired:
        print(f"Error: pueue timed out after {timeout}s", file=sys.stderr)
        sys.exit(2)

    if result.returncode != 0:
        print(
            f"Error: pueue returned exit code {result.returncode}: {result.stderr}",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        data: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON from pueue: {exc}", file=sys.stderr)
        sys.exit(3)

    return data


def parse_pueue_status(status_value: Any) -> TaskStatus:
    """Normalise Pueue's Rust enum-style status JSON into a TaskStatus.

    Pueue serialises its Rust enums in various shapes:
      - Simple variant: "Queued", "Running", "Paused", "Locked"
      - Done variant (modern): {"Done": {"start": ..., "end": ..., "result": "Success"}}
      - Done variant (legacy): {"Done": "Success"} or {"Done": {"Failed": 1}}
    """
    if isinstance(status_value, str):
        return _map_simple_status(status_value)

    if is_dict_of(status_value, k=str, v=Any):
        if "Done" in status_value:
            return _map_done_status(status_value["Done"])
        if "Stashed" in status_value:
            return TaskStatus.STASHED

    return TaskStatus.UNKNOWN


def _map_simple_status(value: str) -> TaskStatus:
    return {
        "Queued": TaskStatus.QUEUED,
        "Running": TaskStatus.RUNNING,
        "Paused": TaskStatus.PAUSED,
        "Locked": TaskStatus.LOCKED,
        "Stashed": TaskStatus.STASHED,
    }.get(value, TaskStatus.UNKNOWN)


def _map_done_status(done: Any) -> TaskStatus:
    # Legacy format: {"Done": "Success"}
    if isinstance(done, str):
        return _map_result_value(done)

    # Modern format: {"Done": {"start": ..., "end": ..., "result": ...}}
    if is_dict_of(done, k=str, v=Any):
        result: Any = done.get("result")
        if result is not None:
            return _map_result_value(result)

        # Fallback: legacy dict format {"Done": {"Failed": 1}}
        if "Success" in done:
            return TaskStatus.SUCCESS
        if "Failed" in done:
            return TaskStatus.FAILED
        if "Killed" in done:
            return TaskStatus.KILLED
        if "DependencyFailed" in done:
            return TaskStatus.DEPENDENCY_FAILED

    return TaskStatus.UNKNOWN


def _map_result_value(result: Any) -> TaskStatus:
    """Map a pueue result value (string or dict) to TaskStatus."""
    if isinstance(result, str):
        return {
            "Success": TaskStatus.SUCCESS,
            "Killed": TaskStatus.KILLED,
            "DependencyFailed": TaskStatus.DEPENDENCY_FAILED,
        }.get(result, TaskStatus.UNKNOWN)

    if is_dict_of(result, k=str, v=Any):
        if "Failed" in result:
            return TaskStatus.FAILED
        if "DependencyFailed" in result:
            return TaskStatus.DEPENDENCY_FAILED

    return TaskStatus.UNKNOWN


def _extract_done_timestamps(status: Any) -> tuple[str | None, str | None]:
    """Extract start/end timestamps from the Done status dict.

    Modern pueue embeds timestamps inside the Done variant:
      {"Done": {"start": "...", "end": "...", "result": ...}}
    """
    if not is_dict_of(status, k=str, v=Any):
        return None, None

    done = status.get("Done")
    if not is_dict_of(done, k=str, v=Any):
        return None, None

    return (_opt_str_field(done, "start"), _opt_str_field(done, "end"))


def _str_field(data: dict[str, Any], key: str, default: str = "") -> str:
    """Extract a string field from a JSON dict, with a default."""
    val = data.get(key, default)
    return str(val) if val is not None else default


def _opt_str_field(data: dict[str, Any], key: str) -> str | None:
    """Extract an optional string field from a JSON dict."""
    val = data.get(key)
    return str(val) if val is not None else None


def parse_pueue_tasks(raw_data: dict[str, Any]) -> list[PueueTask]:
    """Parse the full pueue log JSON into a list of PueueTask objects.

    Pueue log JSON structure:
      {task_id: {"task": {id, command, status, ...}, "output": "..."}, ...}
    """
    tasks: list[PueueTask] = []

    for task_id_str, entry in raw_data.items():
        if not is_dict_of(entry, k=str, v=Any):
            continue

        # Modern pueue wraps each entry as {"task": {...}, "output": "..."}
        if "task" in entry:
            task_data = cast(dict[str, Any], entry["task"])
            output = str(entry.get("output", ""))
        else:
            # Fallback: flat structure (older pueue versions)
            task_data = entry
            output = _str_field(entry, "output")

        status_raw = task_data.get("status")
        status = parse_pueue_status(status_raw)

        command = _str_field(task_data, "original_command") or _str_field(
            task_data, "command"
        )
        cwd = _str_field(task_data, "path") or _str_field(task_data, "cwd")
        group = _str_field(task_data, "group", "default")
        created_at = _str_field(task_data, "created_at")

        # Timestamps: try top-level first, then extract from Done status
        start_at = _opt_str_field(task_data, "start")
        end_at = _opt_str_field(task_data, "end")
        if start_at is None and end_at is None:
            start_at, end_at = _extract_done_timestamps(status_raw)

        tasks.append(
            PueueTask(
                task_id=task_id_str,
                command=command,
                cwd=cwd,
                group=group,
                status=status,
                created_at=created_at,
                start_at=start_at,
                end_at=end_at,
                output=output,
                raw_json=entry,
            ),
        )

    return tasks
