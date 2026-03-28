#!/usr/bin/env python3
"""Move a queued/stashed pueue task to a different group."""

import argparse
import json
import subprocess
import sys
from typing import Any


def run(*cmd: str) -> str:
    return subprocess.run(
        cmd, check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("target-group", type=str)
    parser.add_argument("task-id", type=str, nargs="+")
    args = parser.parse_args()

    target_group: str = args.target_group
    task_ids: list[str] = args.task_id

    status_json: dict[str, Any] = json.loads(run("pueue", "status", "--json"))
    moved = 0
    failed = 0
    for task_id in task_ids:
        task = status_json["tasks"].get(task_id)
        if task is None:
            print(f"Task {task_id} not found", file=sys.stderr)
            failed += 1
            continue

        status = task["status"]
        if status not in ("Queued", "Stashed"):
            print(
                f"Task {task_id} is {status} — only Queued/Stashed tasks can be moved",
                file=sys.stderr,
            )
            failed += 1
            continue

        # fmt: off
        add_args = [
            "pueue", "add",
            "--group", target_group,
            "--working-directory", task["path"],
            "--stashed",
        ]
        # fmt: on

        if label := task.get("label"):
            add_args += ["--label", label]
        if task.get("priority", 0) != 0:
            add_args += ["--priority", str(task["priority"])]
        add_args += ["--print-task-id", "--", task["original_command"]]

        new_id = run(*add_args)

        for key, val in task.get("envs", {}).items():
            run("pueue", "env", "set", new_id, key, val)

        run("pueue", "remove", task_id)

        if status == "Queued":
            run("pueue", "enqueue", new_id)

        print(f"Moved task {task_id} → {new_id}")
        moved += 1

    print(f"Moved: {moved}. Failed: {failed}.")


if __name__ == "__main__":
    main()
