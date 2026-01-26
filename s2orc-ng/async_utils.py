"""Async utilities for downloads and progress tracking."""

import asyncio
import io
import urllib.parse
from collections.abc import Awaitable, Iterable
from pathlib import Path
from typing import Any, Self

import httpx
import tqdm.asyncio as tqdm_asyncio
from tqdm import tqdm

# === Constants ===

DOWNLOAD_TIMEOUT = 3600  # 1 hour per file
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


# === Progress utilities ===


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


# === Async file I/O ===


class AsyncFile:
    """Async wrapper around writing bytes to a file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.file: io.BufferedWriter | None = None
        self.loop = asyncio.get_event_loop()
        self.bytes_written = 0

    async def __aenter__(self) -> Self:
        """Open file in an executor."""

        def _open() -> io.BufferedWriter:
            return open(self.path, "wb")

        self.file = await self.loop.run_in_executor(None, _open)
        return self

    async def __aexit__(self, *_: object) -> bool | None:
        """Close file in an executor."""
        assert self.file
        await self.loop.run_in_executor(None, self.file.close)

    async def write(self, data: bytes) -> int:
        """Write to file in an executor."""
        assert self.file
        n = await self.loop.run_in_executor(None, self.file.write, data)
        self.bytes_written += n
        return n


# === Download utilities ===


def get_filename_from_url(url: str) -> str:
    """Extract filename from URL."""
    return urllib.parse.urlparse(url).path.split("/")[-1]


async def download_file(url: str, dest: Path, desc: str | None = None) -> int:
    """Download a file with progress tracking and retries. Returns bytes downloaded."""
    part_path = dest.with_suffix(dest.suffix + ".part")

    for attempt in range(MAX_RETRIES):
        try:
            bytes_downloaded = await _try_download_file(url, dest, part_path, desc)
            part_path.rename(dest)
        except Exception as e:
            print(
                f"Error downloading {dest.name}: {e}. Retrying..."
                f" (Attempt {attempt + 1}/{MAX_RETRIES})"
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
        else:
            return bytes_downloaded

    print(f"Failed to download {dest.name} after {MAX_RETRIES} attempts.")
    raise RuntimeError(f"Download failed after {MAX_RETRIES} attempts")


async def _try_download_file(
    url: str, display_path: Path, part_path: Path, desc: str | None
) -> int:
    """Download the file in chunks and update progress bar. Returns bytes downloaded."""
    async with (
        httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client,
        client.stream("GET", url) as response,
    ):
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))

        with tqdm(
            total=total_size,
            unit="B",
            unit_scale=True,
            desc=desc or display_path.name[:30],
            leave=False,
        ) as pbar:
            async with AsyncFile(part_path) as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    await f.write(chunk)
                    pbar.update(len(chunk))
                return f.bytes_written
