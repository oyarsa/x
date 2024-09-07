"""Download files from the S2ORC from the Semantic Scholar API."""

import asyncio
import json
import os
import sys
import urllib.parse
from collections.abc import Coroutine
from pathlib import Path

import aiohttp
from tqdm.asyncio import tqdm

MAX_FILES = None
API_KEY = os.environ["SEMANTIC_SCHOLAR_API_KEY"]
DATASET_NAME = "s2orc"
LOCAL_PATH = Path("./data")

MAX_CONCURRENT_DOWNLOADS = 10
DOWNLOAD_TIMEOUT = 3600  # 1 hour timeout for each file
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


async def _download_file(
    url: str, session: aiohttp.ClientSession, display_path: Path, part_path: Path
) -> None:
    """Actually download the file in chunks and handle progress bar."""
    async with session.get(
        url, timeout=aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT)
    ) as response:
        total_size = int(response.headers.get("content-length", 0))

        with (
            open(part_path, "wb") as file,
            tqdm(
                desc=str(display_path),
                total=total_size,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as progress_bar,
        ):
            async for chunk in response.content.iter_chunked(1024):
                size = file.write(chunk)
                progress_bar.update(size)


async def download_file(
    url: str, path: Path, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore
) -> None:
    """Download a file from the given URL with a human-readable progress bar.
    The file is first downloaded to a .part file and then renamed.

    This function is a wrapper around _download_file that handles retries and errors.
    """
    async with semaphore:
        part_path = path.with_suffix(path.suffix + ".part")

        for attempt in range(MAX_RETRIES):
            try:
                await _download_file(url, session, path, part_path)
            except Exception as e:
                print(
                    f"Error downloading {path}: {e}. Retrying..."
                    f" (Attempt {attempt + 1}/{MAX_RETRIES})"
                )
            else:
                # If download completes successfully, rename the file
                part_path.rename(path)
                return

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)

        print(f"Failed to download {path} after {MAX_RETRIES} attempts.")


async def _main() -> None:
    async with aiohttp.ClientSession() as session:
        # Get latest release's ID
        async with session.get(
            "https://api.semanticscholar.org/datasets/v1/release/latest"
        ) as response:
            release_id = (await response.json())["release_id"]
        print(f"Latest release ID: {release_id}")

        # Get the download links for the s2orc dataset
        async with session.get(
            f"https://api.semanticscholar.org/datasets/v1/release/{release_id}/dataset/{DATASET_NAME}/",
            headers={"x-api-key": API_KEY},
        ) as response:
            dataset = await response.json()
        Path("dataset.json").write_text(json.dumps(dataset, indent=2))

        if "files" not in dataset or not dataset["files"]:
            print("No files found.")
            sys.exit(1)

        LOCAL_PATH.mkdir(exist_ok=True)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        tasks: list[Coroutine[None, None, None]] = []

        for url in dataset["files"][:MAX_FILES]:
            file_name = urllib.parse.urlparse(url).path.split("/")[-1]
            file_path = LOCAL_PATH / file_name

            tasks.append(download_file(url, file_path, session, semaphore))

        await tqdm.gather(*tasks, desc="Overall progress")


def main() -> None:
    while True:
        try:
            asyncio.run(_main())
            break  # If _main() completes without interruption, exit the loop
        except KeyboardInterrupt:
            choice = input("\n\nCtrl+C detected. Do you really want to exit? (y/n): ")
            if choice.lower() == "y":
                sys.exit()
            else:
                print("Continuing...\n")  # The loop will continue, restarting _main()


if __name__ == "__main__":
    main()
