"""Tests for parch.models — pure functions and data conversions."""

from parch.models import (
    ArchivedTask,
    IndexEntry,
    TaskMeta,
    TaskOutput,
    TaskSource,
    TaskStatus,
    TaskTimestamps,
    compute_fingerprint,
    compute_output_hash,
)

# ---------------------------------------------------------------------------
# TaskStatus.is_terminal
# ---------------------------------------------------------------------------


class TestTaskStatusIsTerminal:
    """Terminal statuses indicate a finished task."""

    def test_success(self) -> None:
        assert TaskStatus.SUCCESS.is_terminal()

    def test_failed(self) -> None:
        assert TaskStatus.FAILED.is_terminal()

    def test_killed(self) -> None:
        assert TaskStatus.KILLED.is_terminal()

    def test_dependency_failed(self) -> None:
        assert TaskStatus.DEPENDENCY_FAILED.is_terminal()

    def test_running_not_terminal(self) -> None:
        assert not TaskStatus.RUNNING.is_terminal()

    def test_queued_not_terminal(self) -> None:
        assert not TaskStatus.QUEUED.is_terminal()

    def test_paused_not_terminal(self) -> None:
        assert not TaskStatus.PAUSED.is_terminal()

    def test_stashed_not_terminal(self) -> None:
        assert not TaskStatus.STASHED.is_terminal()

    def test_locked_not_terminal(self) -> None:
        assert not TaskStatus.LOCKED.is_terminal()

    def test_unknown_not_terminal(self) -> None:
        assert not TaskStatus.UNKNOWN.is_terminal()


# ---------------------------------------------------------------------------
# compute_fingerprint
# ---------------------------------------------------------------------------


class TestComputeFingerprint:
    """Fingerprint is a deterministic SHA-256 over command+cwd+group+created_at."""

    def test_deterministic(self) -> None:
        fp1 = compute_fingerprint(
            "echo hi", "/test/workdir", "default", "2026-01-01T00:00:00"
        )
        fp2 = compute_fingerprint(
            "echo hi", "/test/workdir", "default", "2026-01-01T00:00:00"
        )
        assert fp1 == fp2

    def test_different_command(self) -> None:
        fp1 = compute_fingerprint(
            "echo hi", "/test/workdir", "default", "2026-01-01T00:00:00"
        )
        fp2 = compute_fingerprint(
            "echo bye", "/test/workdir", "default", "2026-01-01T00:00:00"
        )
        assert fp1 != fp2

    def test_different_cwd(self) -> None:
        fp1 = compute_fingerprint(
            "echo hi", "/test/workdir", "default", "2026-01-01T00:00:00"
        )
        fp2 = compute_fingerprint("echo hi", "/home", "default", "2026-01-01T00:00:00")
        assert fp1 != fp2

    def test_different_group(self) -> None:
        fp1 = compute_fingerprint(
            "echo hi", "/test/workdir", "default", "2026-01-01T00:00:00"
        )
        fp2 = compute_fingerprint(
            "echo hi", "/test/workdir", "other", "2026-01-01T00:00:00"
        )
        assert fp1 != fp2

    def test_different_created_at(self) -> None:
        fp1 = compute_fingerprint(
            "echo hi", "/test/workdir", "default", "2026-01-01T00:00:00"
        )
        fp2 = compute_fingerprint(
            "echo hi", "/test/workdir", "default", "2026-01-02T00:00:00"
        )
        assert fp1 != fp2

    def test_returns_64_char_hex(self) -> None:
        fp = compute_fingerprint(
            "echo hi", "/test/workdir", "default", "2026-01-01T00:00:00"
        )
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


# ---------------------------------------------------------------------------
# compute_output_hash
# ---------------------------------------------------------------------------


class TestComputeOutputHash:
    """Output hash is a SHA-256 of the combined output string."""

    def test_deterministic(self) -> None:
        h1 = compute_output_hash("hello world")
        h2 = compute_output_hash("hello world")
        assert h1 == h2

    def test_different_output(self) -> None:
        h1 = compute_output_hash("hello")
        h2 = compute_output_hash("world")
        assert h1 != h2

    def test_empty_string(self) -> None:
        h = compute_output_hash("")
        assert len(h) == 64

    def test_returns_64_char_hex(self) -> None:
        h = compute_output_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# ArchivedTask.to_index_entry
# ---------------------------------------------------------------------------


def _make_task(
    *,
    archive_id: str = "abc-123",
    fingerprint: str = "fp-456",
    status: str = "success",
    start_at: str | None = "2026-01-01T00:00:01",
    end_at: str | None = "2026-01-01T00:00:02",
) -> ArchivedTask:
    return ArchivedTask(
        archive_id=archive_id,
        fingerprint=fingerprint,
        archived_at="2026-01-01T00:00:00",
        source=TaskSource(pueue_task_id="42", pueue_group="default"),
        meta=TaskMeta(
            command="echo hi",
            cwd="/test/workdir",
            status=status,
            timestamps=TaskTimestamps(
                created_at="2026-01-01T00:00:00",
                start_at=start_at,
                end_at=end_at,
            ),
        ),
        output=TaskOutput(combined="output", combined_sha256="hash"),
    )


class TestArchivedTaskToIndexEntry:
    """to_index_entry maps all relevant fields into an IndexEntry."""

    def test_all_fields(self) -> None:
        task = _make_task()
        entry = task.to_index_entry()

        assert isinstance(entry, IndexEntry)
        assert entry.archive_id == "abc-123"
        assert entry.fingerprint == "fp-456"
        assert entry.status == "success"
        assert entry.group == "default"
        assert entry.cwd == "/test/workdir"
        assert entry.command == "echo hi"
        assert entry.created_at == "2026-01-01T00:00:00"
        assert entry.start_at == "2026-01-01T00:00:01"
        assert entry.end_at == "2026-01-01T00:00:02"
        assert entry.pueue_task_id == "42"

    def test_optional_timestamps_none(self) -> None:
        task = _make_task(start_at=None, end_at=None)
        entry = task.to_index_entry()

        assert entry.start_at is None
        assert entry.end_at is None
