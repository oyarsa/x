"""Demonstrate reading a JSON file that may be gzipped."""

import gzip
import json
from pathlib import Path


def read_json[T](file_path: Path, _: type[T]) -> T:
    """Read a JSON file from the given path, handling both regular and gzipped files.

    This function checks the file's content to determine whether it's gzipped,
    regardless of the file extension.
    """
    with file_path.open("rb") as f:
        is_gzipped = f.read(2) == b"\x1f\x8b"
        f.seek(0)  # Reset file pointer to the beginning so we can read it again

        if is_gzipped:
            with gzip.open(f, "rt") as gz_file:
                return json.load(gz_file)
        else:
            return json.load(f)


test = read_json(Path("data.json.gz"), dict[str, str])
