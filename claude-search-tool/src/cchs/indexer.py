"""SQLite FTS5 database management for conversation indexing."""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Self

from cchs.models import Message
from cchs.parser import parse_jsonl_file

logger = logging.getLogger("cchs")

SCHEMA_VERSION = 1


class DatabaseCorruptError(Exception):
    """Raised when the SQLite database is corrupt."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        super().__init__(
            f"Database is corrupt at {db_path}. Run `cchs index --force` to rebuild."
        )


CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    uuid TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    message_index INTEGER NOT NULL
)
"""

CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 2'
)
"""

CREATE_INDEX_METADATA = """
CREATE TABLE IF NOT EXISTS index_metadata (
    file_path TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    last_modified REAL NOT NULL,
    last_size INTEGER NOT NULL
)
"""


class Indexer:
    """Manages the SQLite FTS5 search index for a project."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        try:
            self._conn = sqlite3.connect(str(db_path))
            self._conn.row_factory = sqlite3.Row
            self._init_db()
        except sqlite3.DatabaseError as e:
            raise DatabaseCorruptError(db_path) from e

    def __enter__(self) -> Self:
        """Enter context manager."""
        return self

    def __exit__(self, *_: object) -> None:
        """Exit context manager and close the database."""
        self.close()

    def _init_db(self) -> None:
        """Create tables and set pragmas."""
        self._conn.execute("PRAGMA journal_mode=WAL")

        current_version = self.get_schema_version()
        if current_version != SCHEMA_VERSION:
            logger.info(
                "Schema version mismatch (%d != %d), rebuilding",
                current_version,
                SCHEMA_VERSION,
            )
            self._drop_all()

        self._conn.execute(CREATE_MESSAGES)
        self._conn.execute(CREATE_FTS)
        self._conn.execute(CREATE_INDEX_METADATA)
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._conn.commit()

    def _drop_all(self) -> None:
        """Drop all tables for rebuild."""
        self._conn.execute("DROP TABLE IF EXISTS messages_fts")
        self._conn.execute("DROP TABLE IF EXISTS messages")
        self._conn.execute("DROP TABLE IF EXISTS index_metadata")
        self._conn.commit()

    def get_schema_version(self) -> int:
        """Get current schema version."""
        cursor = self._conn.execute("PRAGMA user_version")
        return cursor.fetchone()[0]

    def get_journal_mode(self) -> str:
        """Get current journal mode."""
        cursor = self._conn.execute("PRAGMA journal_mode")
        return cursor.fetchone()[0]

    def message_count(self) -> int:
        """Return total number of indexed messages."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM messages")
        return cursor.fetchone()[0]

    def _is_file_changed(self, file_path: Path) -> bool:
        """Check if a file has changed since last index."""
        relative = file_path.name
        stat = file_path.stat()

        cursor = self._conn.execute(
            "SELECT last_modified, last_size FROM index_metadata WHERE file_path = ?",
            (relative,),
        )
        row = cursor.fetchone()
        if row is None:
            return True
        return row["last_modified"] != stat.st_mtime or row["last_size"] != stat.st_size

    def _update_metadata(self, file_path: Path, session_id: str) -> None:
        """Update index metadata for a file."""
        relative = file_path.name
        stat = file_path.stat()
        self._conn.execute(
            "INSERT OR REPLACE INTO index_metadata (file_path, session_id, last_modified, last_size) "
            "VALUES (?, ?, ?, ?)",
            (relative, session_id, stat.st_mtime, stat.st_size),
        )

    def _delete_session(self, session_id: str) -> None:
        """Delete all messages for a session from both tables."""
        cursor = self._conn.execute(
            "SELECT id, content FROM messages WHERE session_id = ?", (session_id,)
        )
        rows = cursor.fetchall()

        for row in rows:
            self._conn.execute(
                "INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', ?, ?)",
                (row["id"], row["content"]),
            )

        self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))

    def _insert_messages(self, messages: list[Message]) -> None:
        """Insert messages into both messages and FTS tables."""
        for msg in messages:
            cursor = self._conn.execute(
                "INSERT INTO messages (session_id, uuid, role, content, timestamp, message_index) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    msg.session_id,
                    msg.uuid,
                    msg.role,
                    msg.content,
                    msg.timestamp.isoformat(),
                    msg.message_index,
                ),
            )
            rowid = cursor.lastrowid
            self._conn.execute(
                "INSERT INTO messages_fts(rowid, content) VALUES(?, ?)",
                (rowid, msg.content),
            )

    def index_file(self, file_path: Path, *, session_id: str) -> None:
        """Index a single JSONL file. Skips if file hasn't changed."""
        if not self._is_file_changed(file_path):
            return

        logger.debug("Indexing %s", file_path.name)
        self._delete_session(session_id)
        messages = parse_jsonl_file(file_path, session_id=session_id)
        self._insert_messages(messages)
        self._update_metadata(file_path, session_id)
        self._conn.commit()

    def fts_search(self, query: str) -> list[dict[str, Any]]:
        """Run a raw FTS5 search."""
        cursor = self._conn.execute(
            "SELECT m.*, messages_fts.rank "
            "FROM messages_fts "
            "JOIN messages m ON m.id = messages_fts.rowid "
            "WHERE messages_fts MATCH ? "
            "ORDER BY messages_fts.rank",
            (query,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def cleanup_deleted_files(self, project_dir: Path) -> None:
        """Remove index entries for JSONL files that no longer exist on disk."""
        cursor = self._conn.execute("SELECT file_path, session_id FROM index_metadata")
        for row in cursor.fetchall():
            full_path = project_dir / row["file_path"]
            if not full_path.exists():
                session_id = row["session_id"]
                logger.debug("Cleaning up deleted file: %s", row["file_path"])
                self._delete_session(session_id)
                self._conn.execute(
                    "DELETE FROM index_metadata WHERE file_path = ?",
                    (row["file_path"],),
                )
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
