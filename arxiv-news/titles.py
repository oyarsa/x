"""Extract titles and links from arXiv newsletter text.

The input text should come from the raw text from the newsletter email.
"""

import re
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Paper:
    title: str
    link: str


BLOCKLIST_TOPICS = ("audio", "speech", "video", "modal", "memo", "visual")
BLOCKLIST_LANGUGES = ("portuguese", "spanish", "french")
BLOCKLIST_WORDS = BLOCKLIST_TOPICS + BLOCKLIST_LANGUGES


def valid_title(title: str) -> bool:
    return all(block_word not in title.lower() for block_word in BLOCKLIST_WORDS)


def main() -> None:
    text = sys.stdin.read()

    # Split the text into individual paper entries
    paper_parts = re.split(r"\n\\\\", text)
    papers: list[Paper] = []

    for part in paper_parts:
        arxiv_match = re.search(r"arXiv:(\d+\.\d+)", part)
        if not arxiv_match:
            continue
        arxiv_id = arxiv_match[1]

        # Extract title (may be multi-line)
        if title_match := re.search(r"Title: (.*?)(?:\nAuthors:|$)", part, re.DOTALL):
            title = " ".join(title_match[1].strip().split())
            link = f"https://arxiv.org/abs/{arxiv_id}"
            papers.append(Paper(title, link))

    papers_filtered = [p for p in papers if valid_title(p.title)]
    print(len(papers), "papers found.")
    print(len(papers_filtered), "papers after filtering.")

    for i, p in enumerate(papers_filtered, 1):
        print(f"{i}. [{p.title}]({p.link})")
        if i % 10 == 0:
            print("\n---\n")


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        print("Usage: python titles.py < arxiv_newsletter.txt > titles.md\n")
        print(__doc__)
        sys.exit()
    main()
