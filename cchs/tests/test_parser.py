"""Tests for JSONL parser and content cleaning."""

from pathlib import Path

from cchs.parser import clean_content, parse_jsonl_file

FIXTURES = Path(__file__).parent / "fixtures"


class TestCleanContent:
    """Tests for the clean_content function."""

    def test_user_string_content(self) -> None:
        """Test that plain string user content is returned as-is."""
        raw = {
            "type": "user",
            "message": {"role": "user", "content": "How do we calculate PFA?"},
            "uuid": "msg-001",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "isSidechain": False,
        }
        result = clean_content(raw)
        assert result is not None
        assert result == "How do we calculate PFA?"

    def test_user_list_with_tool_result(self) -> None:
        """Test that tool_result blocks are summarized with [Result: ...]."""
        raw = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": "PFA@40=0.823\nPFA@100=0.791",
                    }
                ],
            },
            "uuid": "msg-002",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "isSidechain": False,
        }
        result = clean_content(raw)
        assert result is not None
        assert "[Result: PFA@40=0.823" in result

    def test_assistant_text_blocks(self) -> None:
        """Test that multiple text blocks are joined with newlines."""
        raw = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "First paragraph."},
                    {"type": "text", "text": "Second paragraph."},
                ],
            },
            "uuid": "msg-003",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "isSidechain": False,
        }
        result = clean_content(raw)
        assert result == "First paragraph.\nSecond paragraph."

    def test_assistant_tool_use_summarized(self) -> None:
        """Test that tool_use blocks are summarized with [Tool: Name(...)]."""
        raw = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Bash",
                        "input": {"command": "python calc.py"},
                    },
                    {"type": "text", "text": "Done."},
                ],
            },
            "uuid": "msg-004",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "isSidechain": False,
        }
        result = clean_content(raw)
        assert result is not None
        assert "[Tool: Bash(" in result
        assert "Done." in result

    def test_thinking_blocks_skipped(self) -> None:
        """Test that thinking blocks are excluded from output."""
        raw = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "secret thoughts"},
                    {"type": "text", "text": "Visible answer."},
                ],
            },
            "uuid": "msg-005",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "isSidechain": False,
        }
        result = clean_content(raw)
        assert result == "Visible answer."
        assert "secret" not in result

    def test_skipped_types_return_none(self) -> None:
        """Test that non-conversation message types return None."""
        for msg_type in [
            "file-history-snapshot",
            "progress",
            "system",
            "last-prompt",
            "queue-operation",
        ]:
            raw = {
                "type": msg_type,
                "uuid": "x",
                "timestamp": "2026-03-20T10:00:00.000Z",
            }
            assert clean_content(raw) is None

    def test_sidechain_returns_none(self) -> None:
        """Test that sidechain messages are filtered out."""
        raw = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "hi"}],
            },
            "uuid": "msg-006",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "isSidechain": True,
        }
        assert clean_content(raw) is None

    def test_tool_result_truncation(self) -> None:
        """Test that long tool results are truncated to stay under limit."""
        long_result = "x" * 500
        raw = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": long_result}
                ],
            },
            "uuid": "msg-007",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "isSidechain": False,
        }
        result = clean_content(raw)
        assert result is not None
        assert len(result) < 300


class TestParseJsonlFile:
    """Tests for the parse_jsonl_file function."""

    def test_simple_conversation(self) -> None:
        """Test parsing a simple 4-message conversation fixture."""
        messages = parse_jsonl_file(
            FIXTURES / "simple_conversation.jsonl", session_id="session-1"
        )
        assert len(messages) == 4
        assert messages[0].role == "user"
        assert messages[0].content == "How should we calculate PFA?"
        assert messages[0].message_index == 0
        assert messages[1].role == "assistant"
        assert messages[1].message_index == 1
        assert messages[3].message_index == 3

    def test_mixed_types_filters_correctly(self) -> None:
        """Test that non-conversation and sidechain entries are filtered."""
        messages = parse_jsonl_file(
            FIXTURES / "mixed_types.jsonl", session_id="session-2"
        )
        # Should have: user "Hello" + assistant "Main response"
        # Should skip: file-history-snapshot, progress, system, last-prompt, sidechain
        assert len(messages) == 2
        assert messages[0].content == "Hello"
        assert messages[1].content == "Main response"

    def test_malformed_line_skipped(self, tmp_path: Path) -> None:
        """Test that invalid JSON lines are skipped without raising."""
        f = tmp_path / "bad.jsonl"
        f.write_text(
            "not valid json\n"
            '{"type":"user","message":{"role":"user","content":"ok"},'
            '"uuid":"msg-1","timestamp":"2026-03-20T10:00:00.000Z","isSidechain":false}\n'
        )
        messages = parse_jsonl_file(f, session_id="s1")
        assert len(messages) == 1
        assert messages[0].content == "ok"
