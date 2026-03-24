"""Pydantic models for conversation messages and search results."""

from datetime import datetime

from pydantic import BaseModel


class Message(BaseModel, frozen=True):
    """A cleaned conversation message extracted from JSONL."""

    session_id: str
    uuid: str
    role: str
    content: str
    timestamp: datetime
    message_index: int


class SearchResult(BaseModel, frozen=True):
    """A search match with surrounding context messages."""

    match: Message
    context_before: list[Message]
    context_after: list[Message]
    session_id: str
    rank: float


class ExpandResult(BaseModel, frozen=True):
    """An expanded view of messages around a target."""

    messages: list[Message]
    session_id: str
