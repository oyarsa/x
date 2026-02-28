"""Data models for parch archive storage."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Normalised task status values."""

    SUCCESS = "success"
    FAILED = "failed"
    KILLED = "killed"
    QUEUED = "queued"
    STASHED = "stashed"
    RUNNING = "running"
    PAUSED = "paused"
    LOCKED = "locked"
    DEPENDENCY_FAILED = "dependency_failed"
    UNKNOWN = "unknown"

    def is_terminal(self) -> bool:
        """Whether this status represents a finished task."""
        return self in {
            TaskStatus.SUCCESS,
            TaskStatus.FAILED,
            TaskStatus.KILLED,
            TaskStatus.DEPENDENCY_FAILED,
        }


class TaskTimestamps(BaseModel):
    """Timestamps extracted from a Pueue task."""

    created_at: str
    start_at: str | None = None
    end_at: str | None = None


class TaskMeta(BaseModel):
    """Core task metadata."""

    command: str
    cwd: str
    status: str
    timestamps: TaskTimestamps


class TaskSource(BaseModel):
    """Provenance information linking back to Pueue."""

    pueue_task_id: str
    pueue_group: str
    pueue_version: str | None = None


class TaskOutput(BaseModel):
    """Stored task output."""

    combined: str = ""
    combined_sha256: str = ""


class ArchivedTask(BaseModel):
    """Full archived task file schema (tasks/<archive_id>.json)."""

    archive_id: str
    fingerprint: str
    archived_at: str

    source: TaskSource
    meta: TaskMeta
    output: TaskOutput
    raw: dict[str, Any] = Field(default_factory=dict)

    def to_index_entry(self) -> IndexEntry:
        """Convert an ArchivedTask to an IndexEntry."""
        return IndexEntry(
            archive_id=self.archive_id,
            fingerprint=self.fingerprint,
            status=self.meta.status,
            group=self.source.pueue_group,
            cwd=self.meta.cwd,
            command=self.meta.command,
            created_at=self.meta.timestamps.created_at,
            start_at=self.meta.timestamps.start_at,
            end_at=self.meta.timestamps.end_at,
            pueue_task_id=self.source.pueue_task_id,
        )


class IndexEntry(BaseModel):
    """One line of index.jsonl — fields used for sorting/filtering."""

    archive_id: str
    fingerprint: str
    status: str
    group: str
    cwd: str
    command: str
    created_at: str
    start_at: str | None = None
    end_at: str | None = None
    pueue_task_id: str


@dataclass
class SyncResult:
    """Summary of a sync operation."""

    new_tasks: int = 0
    updated_tasks: int = 0
    unchanged_tasks: int = 0
    skipped_running: int = 0
    errors: list[str] = field(default_factory=lambda: list[str]())


def generate_archive_id() -> str:
    """Generate a unique archive ID (UUID v4)."""
    return str(uuid.uuid4())


def compute_fingerprint(
    command: str,
    cwd: str,
    group: str,
    created_at: str,
) -> str:
    """Compute a deterministic SHA-256 fingerprint for deduplication.

    Uses command + cwd + group + created_at, separated by null bytes.
    Pueue task ID is deliberately excluded.
    """
    payload = f"{command}\0{cwd}\0{group}\0{created_at}"
    return hashlib.sha256(payload.encode()).hexdigest()


def compute_output_hash(output: str) -> str:
    """Compute SHA-256 of combined output for change detection."""
    return hashlib.sha256(output.encode()).hexdigest()


def now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(tz=UTC).isoformat()
