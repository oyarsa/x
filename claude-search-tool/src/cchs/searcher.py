"""Search and expand query logic against the FTS5 index."""

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from cchs.models import ExpandResult, Message, SearchResult

# Words too common to be useful in OR queries
# fmt: off
_STOP_WORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "have",
        "has", "had", "do", "does", "did", "will", "would", "could", "should", "may",
        "might", "shall", "can", "need", "dare", "ought", "used", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "out", "off", "over", "under",
        "again", "further", "then", "once", "here", "there", "when", "where", "why",
        "how", "all", "each", "every", "both", "few", "more", "most", "other", "some",
        "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
        "just", "because", "but", "and", "or", "if", "while", "about", "what", "which",
        "who", "whom", "this", "that", "these", "those", "i", "me", "my", "myself",
        "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself",
        "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself",
        "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    }
)
# fmt: on


def preprocess_query(query: str) -> str:
    """Convert a natural language query into an OR-based FTS5 query.

    - Strips stop words
    - Joins remaining terms with OR
    - Falls back to the original query if all words are stop words
    """
    # If the query already contains FTS5 operators, pass it through as-is
    if re.search(r"\b(AND|OR|NOT|NEAR)\b", query) or '"' in query:
        return query

    words = re.findall(r"[a-zA-Z0-9_]+", query)
    meaningful = [w for w in words if w.lower() not in _STOP_WORDS]

    if not meaningful:
        # All stop words — use original words to avoid empty query
        meaningful = words

    if not meaningful:
        return query

    return " OR ".join(meaningful)


def _row_to_message(row: sqlite3.Row) -> Message:
    """Convert a database row to a Message."""
    return Message(
        session_id=row["session_id"],
        uuid=row["uuid"],
        role=row["role"],
        content=row["content"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        message_index=row["message_index"],
    )


class Searcher:
    """Executes search and expand queries against the FTS5 index."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @classmethod
    @contextmanager
    def new(cls, db_path: Path) -> Iterator[Searcher]:
        """Open a database connection and yield a Searcher, closing on exit."""
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        try:
            yield cls(conn)
        finally:
            conn.close()

    def _get_context(
        self,
        session_id: str,
        message_index: int,
        before: int,
        after: int,
    ) -> tuple[list[Message], list[Message]]:
        """Get context messages before and after a given index."""
        cursor = self._conn.execute(
            "SELECT * FROM messages WHERE session_id = ? AND message_index < ? "
            "ORDER BY message_index DESC LIMIT ?",
            (session_id, message_index, before),
        )
        context_before = [_row_to_message(r) for r in cursor.fetchall()]
        context_before.reverse()

        cursor = self._conn.execute(
            "SELECT * FROM messages WHERE session_id = ? AND message_index > ? "
            "ORDER BY message_index ASC LIMIT ?",
            (session_id, message_index, after),
        )
        context_after = [_row_to_message(r) for r in cursor.fetchall()]

        return context_before, context_after

    def search(
        self,
        query: str,
        *,
        context: int = 3,
        limit: int = 10,
        session_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[SearchResult]:
        """Full-text search with context windows."""
        fts_query = preprocess_query(query)

        sql = (
            "SELECT m.*, messages_fts.rank "
            "FROM messages_fts "
            "JOIN messages m ON m.id = messages_fts.rowid "
            "WHERE messages_fts MATCH ?"
        )
        params: list[str | int] = [fts_query]

        if session_id is not None:
            sql += " AND m.session_id = ?"
            params.append(session_id)

        if since is not None:
            sql += " AND m.timestamp >= ?"
            params.append(since.isoformat())

        if until is not None:
            sql += " AND m.timestamp <= ?"
            params.append(until.isoformat())

        sql += " ORDER BY messages_fts.rank LIMIT ?"
        params.append(limit)

        cursor = self._conn.execute(sql, params)
        rows = cursor.fetchall()

        results: list[SearchResult] = []
        for row in rows:
            match = _row_to_message(row)
            before_msgs, after_msgs = self._get_context(
                match.session_id,
                match.message_index,
                context,
                context,
            )
            results.append(
                SearchResult(
                    match=match,
                    context_before=before_msgs,
                    context_after=after_msgs,
                    session_id=match.session_id,
                    rank=-row["rank"],
                )
            )

        return results

    def expand(
        self,
        uuid: str,
        *,
        before: int = 10,
        after: int = 10,
        full: bool = False,
    ) -> ExpandResult | None:
        """Expand context around a specific message UUID."""
        cursor = self._conn.execute("SELECT * FROM messages WHERE uuid = ?", (uuid,))
        row = cursor.fetchone()
        if row is None:
            return None

        target = _row_to_message(row)

        if full:
            cursor = self._conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY message_index",
                (target.session_id,),
            )
            messages = [_row_to_message(r) for r in cursor.fetchall()]
        else:
            before_msgs, after_msgs = self._get_context(
                target.session_id,
                target.message_index,
                before,
                after,
            )
            messages = [*before_msgs, target, *after_msgs]

        return ExpandResult(messages=messages, session_id=target.session_id)
