"""List and download Semantic Scholar datasets (standalone version)."""

import asyncio
import io
import json
import os
import sys
import urllib.parse
from collections.abc import Awaitable
from pathlib import Path
from typing import Annotated, NoReturn, Self

import httpx
import typer
from tqdm import tqdm

from async_utils import gather

MAX_CONCURRENT_DOWNLOADS = 10
DOWNLOAD_TIMEOUT = 3600  # 1 hour timeout for each file
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


def die(message: str) -> NoReturn:
    """Print error message and exit."""
    print(message, file=sys.stderr)
    sys.exit(1)


@app.command(name="list")
def list_datasets(
    show_json: Annotated[
        bool,
        typer.Option(
            "--json", help="Output data in JSON format instead of plain text."
        ),
    ] = False,
) -> None:
    """List available datasets."""
    asyncio.run(_list_datasets(show_json))


async def _list_datasets(show_json: bool) -> None:
    """List available datasets from the Semantic Scholar API."""
    async with httpx.AsyncClient() as client:
        # Get latest release ID
        response = await client.get(
            "https://api.semanticscholar.org/datasets/v1/release/latest"
        )
        response.raise_for_status()
        releases = response.json()

        release_id = releases["release_id"]
        print(f"Latest release ID: {release_id}")

        # Get datasets for the latest release
        response = await client.get(
            f"https://api.semanticscholar.org/datasets/v1/release/{release_id}"
        )
        response.raise_for_status()
        data = response.json()

    if show_json:
        print(json.dumps(data["datasets"], indent=2))
    else:
        for dataset in data["datasets"]:
            print(dataset["name"], dataset["description"].strip(), sep="\n", end="\n\n")


@app.command(name="download", help="Download a dataset.", no_args_is_help=True)
def download_dataset(
    dataset_name: Annotated[
        str, typer.Argument(help="Name of the dataset to download.")
    ],
    output_path: Annotated[
        Path, typer.Argument(help="Directory to save the downloaded files.")
    ],
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            "-n",
            help="Limit the number of files to download. Useful for testing.",
        ),
    ] = None,
) -> None:
    """Download dataset files from the Semantic Scholar API to the output path."""
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        die("SEMANTIC_SCHOLAR_API_KEY environment variable is required.")

    output_path.mkdir(parents=True, exist_ok=True)
    asyncio.run(_download(dataset_name, output_path, api_key, limit))


async def _download(
    dataset_name: str, output_path: Path, api_key: str, limit: int | None
) -> None:
    """Download dataset files from the Semantic Scholar API to the output path."""
    async with httpx.AsyncClient() as client:
        # Get latest release's ID
        response = await client.get(
            "https://api.semanticscholar.org/datasets/v1/release/latest"
        )
        response.raise_for_status()
        release_id = response.json()["release_id"]
        print(f"Latest release ID: {release_id}")

        # Get the download links for the dataset
        response = await client.get(
            f"https://api.semanticscholar.org/datasets/v1/release/{release_id}/dataset/{dataset_name}/",
            headers={"x-api-key": api_key},
        )
        response.raise_for_status()
        dataset = response.json()

        # Save dataset metadata
        (output_path / "dataset.json").write_text(json.dumps(dataset, indent=2))

        if "files" not in dataset or not dataset["files"]:
            die("No files found.")

        urls = dataset["files"][:limit]
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        print(f"Files to download: {len(urls)}")

        tasks: list[Awaitable[None]] = []
        for url in urls:
            file_name = urllib.parse.urlparse(str(url)).path.split("/")[-1]
            file_path = output_path / file_name
            tasks.append(_download_file(url, file_path, semaphore))

        await gather(tasks, desc="Overall")
        print("Download complete!")


async def _download_file(
    url: str,
    path: Path,
    semaphore: asyncio.Semaphore,
) -> None:
    """Download a file from the given URL with a progress bar.

    The file is first downloaded to a .part file and then renamed.
    """
    async with semaphore:
        part_path = path.with_suffix(path.suffix + ".part")

        for attempt in range(MAX_RETRIES):
            try:
                await _try_download_file(url, path, part_path)
                part_path.rename(path)
            except Exception as e:
                print(
                    f"Error downloading {path.name}: {e}. Retrying..."
                    f" (Attempt {attempt + 1}/{MAX_RETRIES})"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
            else:
                return

        print(f"Failed to download {path.name} after {MAX_RETRIES} attempts.")


async def _try_download_file(url: str, display_path: Path, part_path: Path) -> None:
    """Download the file in chunks and update progress bar.

    Raises on HTTP errors or timeouts.
    """
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
            desc=display_path.name[:30],
            leave=False,
        ) as pbar:
            async with AsyncFile(part_path) as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    await f.write(chunk)
                    pbar.update(len(chunk))


class AsyncFile:
    """Async wrapper around writing bytes to a file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.file = None
        self.loop = asyncio.get_event_loop()

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
        return await self.loop.run_in_executor(None, self.file.write, data)


if __name__ == "__main__":
    app()
