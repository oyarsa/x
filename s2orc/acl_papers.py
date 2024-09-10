import argparse
import gzip
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

from tqdm import tqdm

normalise_re = re.compile(r"[^a-z0-9\s]")


def normalise_text(text: str) -> str:
    """Remove non-alphanumeric characters and convert to lowercase."""
    return normalise_re.sub("", text.lower()).strip()


def match_papers(
    venues: list[str], papers: list[dict[str, str]]
) -> Iterator[dict[str, str]]:
    for paper in papers:
        paper_venue = normalise_text(paper["venue"])
        for candidate_venue in venues:
            if candidate_venue in paper_venue:
                yield paper
                break


def main(venues_file: TextIO, papers: list[Path], output_file: TextIO) -> None:
    venues = [normalise_text(venue) for venue in venues_file]
    print(f"Loaded {len(venues)} venues.")
    output: list[dict[str, str]] = []

    with tqdm(papers) as pbar:
        for paper_file in pbar:
            with gzip.open(paper_file, "rt") as file:
                data = json.load(file)
                output.extend(match_papers(venues, data))
                pbar.set_postfix(matched=len(output))

    Path(output_file.name).parent.mkdir(parents=True, exist_ok=True)
    json.dump(output, output_file, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "venues_file",
        type=argparse.FileType("r"),
        help="Input file containing venue names",
    )
    parser.add_argument(
        "output_file",
        type=argparse.FileType("w"),
        help="Output JSON file where matches will be written",
    )
    parser.add_argument(
        "papers",
        nargs="+",
        type=Path,
        help="JSON.GZ files containing papers to be matched against venues",
    )
    args = parser.parse_args()
    main(args.venues_file, args.papers, args.output_file)
