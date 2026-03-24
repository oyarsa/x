"""Tests for SQLite FTS5 indexer."""

from pathlib import Path

import pytest

from cchs.indexer import SCHEMA_VERSION, DatabaseCorruptError, Indexer

FIXTURES = Path(__file__).parent / "fixtures"


class TestIndexerCreation:
    """Tests for Indexer creation and initialization."""

    def test_creates_db_and_tables(self, tmp_path: Path) -> None:
        """Test that Indexer creates the database file."""
        db_path = tmp_path / "search.db"
        indexer = Indexer(db_path)
        indexer.close()
        assert db_path.exists()

    def test_schema_version_set(self, tmp_path: Path) -> None:
        """Test that schema version is set on creation."""
        db_path = tmp_path / "search.db"
        indexer = Indexer(db_path)
        assert indexer.get_schema_version() == SCHEMA_VERSION
        indexer.close()

    def test_wal_mode(self, tmp_path: Path) -> None:
        """Test that WAL journal mode is enabled."""
        db_path = tmp_path / "search.db"
        indexer = Indexer(db_path)
        assert indexer.get_journal_mode() == "wal"
        indexer.close()


class TestIndexing:
    """Tests for indexing operations."""

    def test_index_jsonl_file(self, tmp_path: Path) -> None:
        """Test indexing a JSONL file produces expected message count."""
        db_path = tmp_path / "search.db"
        indexer = Indexer(db_path)
        indexer.index_file(
            FIXTURES / "simple_conversation.jsonl", session_id="session-1"
        )
        assert indexer.message_count() == 4
        indexer.close()

    def test_incremental_skip_unchanged(self, tmp_path: Path) -> None:
        """Test that unchanged files are skipped on re-index."""
        db_path = tmp_path / "search.db"
        indexer = Indexer(db_path)
        indexer.index_file(FIXTURES / "simple_conversation.jsonl", session_id="s1")
        count_after_first = indexer.message_count()
        indexer.index_file(FIXTURES / "simple_conversation.jsonl", session_id="s1")
        assert indexer.message_count() == count_after_first
        indexer.close()

    def test_reindex_on_change(self, tmp_path: Path) -> None:
        """Test that a modified file is re-indexed with updated content."""
        src = FIXTURES / "simple_conversation.jsonl"
        dst = tmp_path / "conv.jsonl"
        dst.write_text(src.read_text())

        db_path = tmp_path / "search.db"
        indexer = Indexer(db_path)
        indexer.index_file(dst, session_id="s1")
        assert indexer.message_count() == 4

        with dst.open("a") as f:
            f.write(
                '{"type":"user","message":{"role":"user","content":"New message"},'
                '"uuid":"msg-new","timestamp":"2026-03-20T12:00:00.000Z",'
                '"isSidechain":false}\n'
            )

        indexer.index_file(dst, session_id="s1")
        assert indexer.message_count() == 5
        indexer.close()

    def test_fts_search_works(self, tmp_path: Path) -> None:
        """Test that FTS search returns results for a known term."""
        db_path = tmp_path / "search.db"
        indexer = Indexer(db_path)
        indexer.index_file(FIXTURES / "simple_conversation.jsonl", session_id="s1")
        results = indexer.fts_search("PFA")
        assert len(results) > 0
        indexer.close()

    def test_schema_version_mismatch_rebuilds(self, tmp_path: Path) -> None:
        """Test that a schema version mismatch triggers a full rebuild."""
        db_path = tmp_path / "search.db"
        indexer = Indexer(db_path)
        indexer.index_file(FIXTURES / "simple_conversation.jsonl", session_id="s1")
        assert indexer.message_count() == 4
        indexer._conn.execute("PRAGMA user_version = 0")
        indexer._conn.commit()
        indexer.close()

        indexer2 = Indexer(db_path)
        assert indexer2.message_count() == 0
        assert indexer2.get_schema_version() == SCHEMA_VERSION
        indexer2.close()

    def test_corrupt_db_raises(self, tmp_path: Path) -> None:
        """Test that a corrupt database file raises DatabaseCorruptError."""
        db_path = tmp_path / "search.db"
        db_path.write_text("this is not a sqlite database")
        with pytest.raises(DatabaseCorruptError):
            Indexer(db_path)

    def test_cleanup_deleted_files(self, tmp_path: Path) -> None:
        """Test that cleanup removes messages for deleted files."""
        src = FIXTURES / "simple_conversation.jsonl"
        dst = tmp_path / "conv.jsonl"
        dst.write_text(src.read_text())

        db_path = tmp_path / "search.db"
        indexer = Indexer(db_path)
        indexer.index_file(dst, session_id="s1")
        assert indexer.message_count() == 4

        dst.unlink()
        indexer.cleanup_deleted_files(tmp_path)
        assert indexer.message_count() == 0
        indexer.close()
