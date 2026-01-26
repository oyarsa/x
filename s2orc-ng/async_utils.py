"""Async utilities for progress tracking."""

from collections.abc import Awaitable, Iterable
from typing import Any

import tqdm.asyncio as tqdm_asyncio


def as_completed[T](
    tasks: Iterable[Awaitable[T]], *, desc: str | None = None, **kwargs: Any
) -> Iterable[Awaitable[T]]:
    """Return iterator over `tasks` as they are completed, showing a progress bar.

    Tasks returned by the iterator still need to be `await`ed.
    Type-safe wrapper around `tqdm.asyncio.as_completed`. `kwargs` are forwarded to it.

    See also `asyncio.as_completed`.
    """
    return tqdm_asyncio.as_completed(tasks, desc=desc, **kwargs)  # type: ignore[reportUnknownMemberType]


async def gather[T](
    tasks: Iterable[Awaitable[T]], *, desc: str | None = None, **kwargs: Any
) -> Iterable[T]:
    """Wait for tasks to complete with a progress bar. Returns an iterator over the results.

    Type-safe wrapper around `tqdm.asyncio.gather`. `kwargs` are forwarded to it.

    See also `asyncio.gather`.
    """
    return await tqdm_asyncio.gather(*tasks, desc=desc, **kwargs)  # type: ignore
