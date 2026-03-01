"""Archive storage — read/write tasks, index, fingerprints, and locking."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from parch.models import ArchivedTask, IndexEntry
from parch.typing import is_dict_of

if TYPE_CHECKING:
    from collections.abc import Iterator

_DEFAULT_ARCHIVE_DIR = Path.home() / ".local" / "share" / "parch"


@dataclass(frozen=True)
class ArchivePaths:
    """Resolved filesystem paths for the archive."""

    root: Path

    @property
    def tasks_dir(self) -> Path:
        """Directory containing individual task JSON files."""
        return self.root / "tasks"

    @property
    def index_path(self) -> Path:
        """Path to the JSONL index file."""
        return self.root / "index.jsonl"

    @property
    def fingerprints_path(self) -> Path:
        """Path to the fingerprint-to-archive-id mapping."""
        return self.root / "fingerprints.json"

    @property
    def lock_path(self) -> Path:
        """Path to the advisory lock file."""
        return self.root / "lock"


def resolve_archive_dir(override: str | None = None) -> ArchivePaths:
    """Resolve archive directory from override or default."""
    if override:
        root = Path(override).expanduser().resolve()
    else:
        root = _DEFAULT_ARCHIVE_DIR
    return ArchivePaths(root=root)


def ensure_archive_dirs(paths: ArchivePaths) -> None:
    """Create archive directories if they don't exist."""
    paths.tasks_dir.mkdir(parents=True, exist_ok=True)


@contextmanager
def archive_lock(paths: ArchivePaths, timeout: float = 5.0) -> Iterator[None]:
    """Acquire an advisory lock on the archive directory.

    Tries non-blocking first, then retries with short sleeps until timeout.

    Args:
        paths: Archive paths.
        timeout: Seconds to wait before failing.

    Raises:
        ArchiveLockError: If the lock cannot be acquired within the timeout.
    """
    ensure_archive_dirs(paths)
    lock_file = open(paths.lock_path, "w")  # noqa: SIM115
    try:
        _acquire_flock(lock_file.fileno(), timeout)
        yield
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


class ArchiveLockError(OSError):
    """Raised when the archive lock cannot be acquired within the timeout."""


def _acquire_flock(fd: int, timeout: float) -> None:
    """Try to acquire LOCK_EX, retrying until timeout."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if time.monotonic() >= deadline:
                raise ArchiveLockError(
                    "Could not acquire archive lock. "
                    "Another parch instance may be running."
                ) from None
            time.sleep(0.05)
        else:
            return


# --- Fingerprints ---


def load_fingerprints(paths: ArchivePaths) -> dict[str, str]:
    """Load fingerprint -> archive_id mapping.

    Returns an empty dict if the file doesn't exist.
    """
    if not paths.fingerprints_path.exists():
        return {}
    try:
        raw = json.loads(paths.fingerprints_path.read_text())
        if not is_dict_of(raw, k=str, v=str):
            return {}
    except (json.JSONDecodeError, OSError):
        return {}
    else:
        return raw


def save_fingerprints(
    paths: ArchivePaths,
    fingerprints: dict[str, str],
) -> None:
    """Atomically write fingerprints.json."""
    _atomic_write_json(paths.fingerprints_path, fingerprints)


# --- Tasks ---


def load_task(paths: ArchivePaths, archive_id: str) -> ArchivedTask | None:
    """Load a single archived task by ID. Returns None if not found."""
    task_path = paths.tasks_dir / f"{archive_id}.json"
    if not task_path.exists():
        return None

    try:
        return ArchivedTask.model_validate_json(task_path.read_text())
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def save_task(paths: ArchivePaths, task: ArchivedTask) -> None:
    """Atomically write a task file."""
    task_path = paths.tasks_dir / f"{task.archive_id}.json"
    _atomic_write_json(task_path, task.model_dump())


# --- Index ---


def load_index(paths: ArchivePaths) -> list[IndexEntry]:
    """Load all index entries from index.jsonl.

    Uses latest-wins semantics: if multiple lines share the same
    archive_id, only the last one is kept.
    """
    if not paths.index_path.exists():
        return []

    seen: dict[str, IndexEntry] = {}
    try:
        for raw_line in paths.index_path.read_text().splitlines():
            line = raw_line.strip()
            if not line:
                continue

            try:
                entry = IndexEntry.model_validate_json(line)
                seen[entry.archive_id] = entry
            except (json.JSONDecodeError, ValueError):
                continue
    except OSError:
        return []

    return list(seen.values())


def rewrite_index(paths: ArchivePaths, entries: list[IndexEntry]) -> None:
    """Atomically rewrite the entire index file."""
    lines = [entry.model_dump_json() for entry in entries]
    content = "\n".join(lines) + "\n" if lines else ""
    _atomic_write_text(paths.index_path, content)


def rebuild_index(paths: ArchivePaths) -> list[IndexEntry]:
    """Rebuild index.jsonl by scanning all task files."""
    entries: list[IndexEntry] = []

    if not paths.tasks_dir.exists():
        return entries

    for task_file in sorted(paths.tasks_dir.glob("*.json")):
        try:
            entries.append(
                ArchivedTask.model_validate_json(task_file.read_text()).to_index_entry()
            )
        except (json.JSONDecodeError, OSError, ValueError):
            continue

    rewrite_index(paths, entries)
    return entries


def _atomic_write_json(path: Path, data: object) -> None:
    """Write JSON data atomically via temp file + rename."""
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    _atomic_write_text(path, content)


def _atomic_write_text(path: Path, content: str) -> None:
    """Write text atomically via temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    tmp_path = Path(tmp_path_str)
    closed = False

    try:
        os.write(fd, content.encode())
        os.close(fd)
        closed = True
        tmp_path.rename(path)
    except BaseException:
        if not closed:
            os.close(fd)
        if tmp_path.exists():
            tmp_path.unlink()
        raise
