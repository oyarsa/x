"""Extract unique venues from json.gz files."""

import argparse
import gzip
import json
from pathlib import Path

from tqdm import tqdm


def extract_venues(files: list[Path]) -> list[str]:
    venues: set[str] = set()

    for file in tqdm(files):
        with gzip.open(file, "rt") as f:
            data: list[dict[str, str]] = json.load(f)
            for item in data:
                if venue := item.get("venue"):
                    venues.add(venue.casefold().strip())

    return sorted(venues)


def main(files: list[Path], output_path: Path) -> None:
    unique_venues = extract_venues(files)
    output_path.write_text("\n".join(unique_venues) + "\n")
    print(f"Extracted {len(unique_venues)} unique venues to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "files", type=Path, nargs="+", help="List of .json.gz files to process"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="venues.txt",
        type=Path,
        help="Output file with the venues, one per line (default: %(default)s).",
    )
    args = parser.parse_args()
    main(args.files, args.output)
