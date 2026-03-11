"""Sync logic — merge Pueue tasks into the archive."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, cast

from parch.archive import (
    archive_lock,
    ensure_archive_dirs,
    load_fingerprints,
    load_index,
    load_task,
    rewrite_index,
    save_fingerprints,
    save_task,
)
from parch.models import (
    ArchivedTask,
    IndexEntry,
    SyncResult,
    TaskMeta,
    TaskOutput,
    TaskSource,
    TaskTimestamps,
    compute_fingerprint,
    compute_output_hash,
    generate_archive_id,
    now_iso,
)
from parch.pueue import parse_pueue_tasks, run_pueue_log, run_pueue_status

if TYPE_CHECKING:
    from parch.archive import ArchivePaths
    from parch.pueue import PueueTask


def sync(
    paths: ArchivePaths,
    *,
    pueue_bin: str = "pueue",
    include_running: bool = False,
    timeout: int | None = None,
    verbose: bool = False,
    quiet: bool = False,
) -> SyncResult:
    """Perform a full sync from Pueue into the archive.

    1. Run `pueue log --json`
    2. Parse tasks and compute fingerprints
    3. For each task: create new or update existing archive entry
    4. Rewrite index and fingerprints
    """
    # Use pueue status for task discovery (includes Done tasks not yet
    # cleaned), then overlay output from pueue log where available.
    status_data = run_pueue_status(pueue_bin=pueue_bin, timeout=timeout)
    log_data = run_pueue_log(pueue_bin=pueue_bin, timeout=timeout)
    for tid, log_entry in log_data.items():
        if not isinstance(log_entry, dict):
            continue
        entry = cast(dict[str, Any], log_entry)
        if tid in status_data:
            # Merge output into the status entry
            status_data[tid]["_log_output"] = entry.get("output", "")
        else:
            # Task only in log (already cleaned from status) — keep it
            status_data[tid] = log_entry

    pueue_tasks = parse_pueue_tasks(status_data)

    result = SyncResult()
    ensure_archive_dirs(paths)

    with archive_lock(paths):
        fingerprints = load_fingerprints(paths)
        index_entries = {e.archive_id: e for e in load_index(paths)}

        for ptask in pueue_tasks:
            if not include_running and not ptask.status.is_terminal():
                result.skipped_running += 1
                continue

            fp = compute_fingerprint(
                ptask.command,
                ptask.cwd,
                ptask.group,
                ptask.created_at,
            )

            if fp in fingerprints:
                _handle_existing(
                    paths,
                    fingerprints,
                    index_entries,
                    fp,
                    ptask,
                    result,
                )
            else:
                _handle_new(
                    paths,
                    fingerprints,
                    index_entries,
                    fp,
                    ptask,
                    result,
                )

        save_fingerprints(paths, fingerprints)
        rewrite_index(paths, list(index_entries.values()))

    if verbose and not quiet:
        print(
            f"Sync complete: {result.new_tasks} new, "
            f"{result.updated_tasks} updated, "
            f"{result.unchanged_tasks} unchanged",
            file=sys.stderr,
        )

    return result


def _handle_existing(
    paths: ArchivePaths,
    fingerprints: dict[str, str],
    index_entries: dict[str, IndexEntry],
    fp: str,
    ptask: PueueTask,
    result: SyncResult,
) -> None:
    """Update an existing archived task if it has changed."""
    archive_id = fingerprints[fp]
    existing = load_task(paths, archive_id)

    if existing is None:
        # Task file missing but fingerprint exists — recreate
        _create_task(paths, fingerprints, index_entries, fp, ptask, archive_id)
        result.new_tasks += 1
        return

    output_hash = compute_output_hash(ptask.output)
    status_str = ptask.status.value

    # Check if anything changed
    if (
        existing.meta.status == status_str
        and existing.output.combined_sha256 == output_hash
        and existing.meta.timestamps.start_at == ptask.start_at
        and existing.meta.timestamps.end_at == ptask.end_at
    ):
        result.unchanged_tasks += 1
        return

    # Update the task
    existing.meta.status = status_str
    existing.meta.timestamps.start_at = ptask.start_at
    existing.meta.timestamps.end_at = ptask.end_at
    existing.output.combined = ptask.output
    existing.output.combined_sha256 = output_hash
    existing.source.pueue_task_id = ptask.task_id
    existing.raw = {"pueue_log_json": ptask.raw_json}

    save_task(paths, existing)
    index_entries[archive_id] = _make_index_entry(existing)
    result.updated_tasks += 1


def _handle_new(
    paths: ArchivePaths,
    fingerprints: dict[str, str],
    index_entries: dict[str, IndexEntry],
    fp: str,
    ptask: PueueTask,
    result: SyncResult,
) -> None:
    """Archive a newly observed task."""
    archive_id = generate_archive_id()
    _create_task(paths, fingerprints, index_entries, fp, ptask, archive_id)
    result.new_tasks += 1


def _create_task(
    paths: ArchivePaths,
    fingerprints: dict[str, str],
    index_entries: dict[str, IndexEntry],
    fp: str,
    ptask: PueueTask,
    archive_id: str,
) -> None:
    """Create and persist a new archived task."""
    output_hash = compute_output_hash(ptask.output)

    task = ArchivedTask(
        archive_id=archive_id,
        fingerprint=fp,
        archived_at=now_iso(),
        source=TaskSource(
            pueue_task_id=ptask.task_id,
            pueue_group=ptask.group,
        ),
        meta=TaskMeta(
            command=ptask.command,
            cwd=ptask.cwd,
            status=ptask.status.value,
            timestamps=TaskTimestamps(
                created_at=ptask.created_at,
                start_at=ptask.start_at,
                end_at=ptask.end_at,
            ),
        ),
        output=TaskOutput(
            combined=ptask.output,
            combined_sha256=output_hash,
        ),
        raw={"pueue_log_json": ptask.raw_json},
    )

    save_task(paths, task)
    fingerprints[fp] = archive_id
    index_entries[archive_id] = _make_index_entry(task)


def _make_index_entry(task: ArchivedTask) -> IndexEntry:
    """Build an IndexEntry from an ArchivedTask."""
    return IndexEntry(
        archive_id=task.archive_id,
        fingerprint=task.fingerprint,
        status=task.meta.status,
        group=task.source.pueue_group,
        cwd=task.meta.cwd,
        command=task.meta.command,
        created_at=task.meta.timestamps.created_at,
        start_at=task.meta.timestamps.start_at,
        end_at=task.meta.timestamps.end_at,
        pueue_task_id=task.source.pueue_task_id,
    )
