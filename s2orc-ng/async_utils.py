"""Async utilities for downloads and progress tracking."""

import asyncio
import urllib.parse
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path
from typing import Any

import aiofiles
import httpx
import tqdm.asyncio as tqdm_asyncio
from tqdm import tqdm

# === Constants ===

DOWNLOAD_TIMEOUT = 3600  # 1 hour per file
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# HTTP status codes that indicate expired/invalid pre-signed URLs
AUTH_ERROR_CODES = {400, 401, 403}

# Type alias for URL refresher callback
UrlRefresher = Callable[[], Awaitable[str]]


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


# === Download utilities ===


def get_filename_from_url(url: str) -> str:
    """Extract filename from URL."""
    return urllib.parse.urlparse(url).path.split("/")[-1]


async def download_file(
    url: str,
    dest: Path,
    desc: str | None = None,
    url_refresher: UrlRefresher | None = None,
) -> int:
    """Download a file with progress tracking and retries. Returns bytes downloaded.

    Args:
        url: The URL to download from.
        dest: Destination path for the downloaded file.
        desc: Description for the progress bar.
        url_refresher: Optional async callback to get a fresh URL when auth errors occur.
            This is useful for pre-signed S3 URLs that may expire during long runs.
    """
    part_path = dest.with_suffix(dest.suffix + ".part")
    current_url = url

    for attempt in range(MAX_RETRIES):
        try:
            bytes_downloaded = await _try_download_file(
                current_url, dest, part_path, desc
            )
            part_path.rename(dest)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in AUTH_ERROR_CODES and url_refresher:
                print(f"Auth error for {dest.name}, refreshing URL...")
                current_url = await url_refresher()
                # Don't count this as a retry attempt
                continue
            print(
                f"Error downloading {dest.name}: {e}. Retrying..."
                f" (Attempt {attempt + 1}/{MAX_RETRIES})"
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
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
            bytes_written = 0
            async with aiofiles.open(part_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    await f.write(chunk)
                    bytes_written += len(chunk)
                    pbar.update(len(chunk))
            return bytes_written
