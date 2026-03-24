"""Tests for search and expand query logic."""

from datetime import UTC, datetime
from pathlib import Path

from cchs.indexer import Indexer
from cchs.searcher import Searcher, preprocess_query

FIXTURES = Path(__file__).parent / "fixtures"


def _make_indexed_db(tmp_path: Path) -> Path:
    """Create and populate a test database."""
    db_path = tmp_path / "search.db"
    with Indexer.new(db_path) as indexer:
        indexer.index_file(
            FIXTURES / "simple_conversation.jsonl", session_id="session-1"
        )
        indexer.index_file(FIXTURES / "mixed_types.jsonl", session_id="session-2")
    return db_path


class TestPreprocessQuery:
    """Tests for query preprocessing."""

    def test_single_keyword(self) -> None:
        assert preprocess_query("PFA") == "PFA"

    def test_natural_language_becomes_or(self) -> None:
        result = preprocess_query("How was PFA calculated for the overall")
        assert "OR" in result
        assert "PFA" in result
        assert "calculated" in result
        assert "overall" in result
        # Stop words stripped
        assert "How" not in result.split(" OR ")
        assert "was" not in result.split(" OR ")
        assert "for" not in result.split(" OR ")
        assert "the" not in result.split(" OR ")

    def test_preserves_fts5_operators(self) -> None:
        assert preprocess_query("PFA AND calculation") == "PFA AND calculation"
        assert preprocess_query("PFA OR pooled") == "PFA OR pooled"
        assert preprocess_query('"exact phrase"') == '"exact phrase"'

    def test_all_stop_words_uses_original(self) -> None:
        result = preprocess_query("how was the")
        # Falls back to using all words
        assert "how" in result
        assert "was" in result

    def test_empty_query(self) -> None:
        assert preprocess_query("") == ""


class TestSearch:
    """Tests for the Searcher.search() method."""

    def test_basic_search(self, tmp_path: Path) -> None:
        """Search returns results containing the query term."""
        db_path = _make_indexed_db(tmp_path)
        with Searcher.new(db_path) as searcher:
            results = searcher.search("PFA", context=1)
            assert len(results) > 0
            assert any("PFA" in r.match.content for r in results)

    def test_context_window(self, tmp_path: Path) -> None:
        """Context before/after is bounded by the context parameter."""
        db_path = _make_indexed_db(tmp_path)
        with Searcher.new(db_path) as searcher:
            results = searcher.search("PFA", context=2)
            for result in results:
                assert len(result.context_before) <= 2
                assert len(result.context_after) <= 2

    def test_limit(self, tmp_path: Path) -> None:
        """Limit parameter caps the number of returned results."""
        db_path = _make_indexed_db(tmp_path)
        with Searcher.new(db_path) as searcher:
            results = searcher.search("PFA", context=1, limit=1)
            assert len(results) <= 1

    def test_session_filter(self, tmp_path: Path) -> None:
        """Session filter restricts results to a specific session."""
        db_path = _make_indexed_db(tmp_path)
        with Searcher.new(db_path) as searcher:
            results = searcher.search("Hello", context=1, session_id="session-2")
            assert all(r.session_id == "session-2" for r in results)

    def test_since_filter(self, tmp_path: Path) -> None:
        """Since filter excludes messages before the given timestamp."""
        db_path = _make_indexed_db(tmp_path)
        with Searcher.new(db_path) as searcher:
            results = searcher.search(
                "PFA",
                context=1,
                since=datetime(2026, 3, 21, tzinfo=UTC),
            )
            assert len(results) == 0

    def test_until_filter(self, tmp_path: Path) -> None:
        """Until filter excludes messages after the given timestamp."""
        db_path = _make_indexed_db(tmp_path)
        with Searcher.new(db_path) as searcher:
            results = searcher.search(
                "PFA",
                context=1,
                until=datetime(2026, 3, 19, tzinfo=UTC),
            )
            assert len(results) == 0

    def test_natural_language_query(self, tmp_path: Path) -> None:
        """Natural language queries find results via OR preprocessing."""
        db_path = _make_indexed_db(tmp_path)
        with Searcher.new(db_path) as searcher:
            results = searcher.search(
                "How was PFA calculated for the overall", context=1
            )
            assert len(results) > 0

    def test_no_results(self, tmp_path: Path) -> None:
        """Search returns empty list when no matches found."""
        db_path = _make_indexed_db(tmp_path)
        with Searcher.new(db_path) as searcher:
            results = searcher.search("xyznonexistent", context=1)
            assert len(results) == 0


class TestExpand:
    """Tests for the Searcher.expand() method."""

    def test_expand_by_uuid(self, tmp_path: Path) -> None:
        """Expand returns context around a known UUID."""
        db_path = _make_indexed_db(tmp_path)
        with Searcher.new(db_path) as searcher:
            result = searcher.expand("msg-002", before=2, after=2)
            assert result is not None
            assert result.session_id == "session-1"
            assert len(result.messages) > 0

    def test_expand_full_session(self, tmp_path: Path) -> None:
        """Expand with full=True returns all messages in the session."""
        db_path = _make_indexed_db(tmp_path)
        with Searcher.new(db_path) as searcher:
            result = searcher.expand("msg-001", full=True)
            assert result is not None
            assert len(result.messages) == 4

    def test_expand_invalid_uuid(self, tmp_path: Path) -> None:
        """Expand returns None for an unknown UUID."""
        db_path = _make_indexed_db(tmp_path)
        with Searcher.new(db_path) as searcher:
            result = searcher.expand("nonexistent-uuid", before=2, after=2)
            assert result is None
