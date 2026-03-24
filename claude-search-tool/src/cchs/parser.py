"""JSONL parsing and content cleaning for Claude Code conversations."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from cchs.models import Message

logger = logging.getLogger("cchs")

SKIP_TYPES = frozenset(
    {
        "file-history-snapshot",
        "progress",
        "system",
        "last-prompt",
        "queue-operation",
    }
)

TOOL_RESULT_MAX_LEN = 200


def _summarize_tool_use(block: dict[str, Any]) -> str:
    """Summarize a tool_use block as [Tool: Name(brief input)]."""
    name = block.get("name", "Unknown")
    inp = block.get("input", {})
    if isinstance(inp, dict):
        parts = [f"{v}" for v in list(inp.values())[:1]]
        brief = ", ".join(parts)[:100]
    else:
        brief = str(inp)[:100]
    return f"[Tool: {name}({brief})]"


def _summarize_tool_result(block: dict[str, Any]) -> str:
    """Summarize a tool_result block as [Result: truncated content]."""
    content = block.get("content", "")
    if isinstance(content, list):
        parts = [item.get("text", "") for item in content if isinstance(item, dict)]
        content = "\n".join(parts)
    content = str(content)[:TOOL_RESULT_MAX_LEN]
    return f"[Result: {content}]"


def _clean_list_content(blocks: list[dict[str, Any]], role: str) -> str:
    """Clean a list of content blocks into readable text."""
    parts: list[str] = []
    for block in blocks:
        block_type = block.get("type", "")
        if block_type == "text":
            parts.append(block.get("text", ""))
        elif block_type == "tool_use" and role == "assistant":
            parts.append(_summarize_tool_use(block))
        elif block_type == "tool_result" and role == "user":
            parts.append(_summarize_tool_result(block))
        elif block_type == "thinking":
            continue
    return "\n".join(parts)


def clean_content(raw: dict[str, Any]) -> str | None:
    """Extract and clean message content from a raw JSONL object.

    Returns None if the message should be skipped.
    """
    msg_type = raw.get("type", "")

    if msg_type in SKIP_TYPES:
        return None

    if raw.get("isSidechain", False):
        return None

    if msg_type not in ("user", "assistant"):
        return None

    message = raw.get("message", {})
    content = message.get("content")

    if content is None:
        return None

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return _clean_list_content(content, msg_type)

    return None


def parse_jsonl_file(path: Path, *, session_id: str) -> list[Message]:
    """Parse a JSONL conversation file into cleaned Message objects."""
    messages: list[Message] = []
    index = 0

    with path.open() as f:
        for line_num, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed JSON at %s:%d", path.name, line_num)
                continue

            content = clean_content(raw)
            if content is None:
                continue

            uuid = raw.get("uuid", f"{session_id}-line-{line_num}")
            timestamp_str = raw.get("timestamp", "1970-01-01T00:00:00.000Z")
            timestamp = datetime.fromisoformat(timestamp_str)

            messages.append(
                Message(
                    session_id=session_id,
                    uuid=uuid,
                    role=raw.get("type", "user"),
                    content=content,
                    timestamp=timestamp,
                    message_index=index,
                )
            )
            index += 1

    return messages
