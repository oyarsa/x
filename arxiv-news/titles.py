import re
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Paper:
    title: str
    link: str


def main() -> None:
    text = sys.stdin.read()

    # Split the text into individual paper entries
    paper_parts = re.split(r"\n\\\\", text)
    papers: list[Paper] = []

    for part in paper_parts:
        arxiv_match = re.search(r"arXiv:(\d+\.\d+)", part)
        if not arxiv_match:
            continue
        arxiv_id = arxiv_match.group(1)

        # Extract title (may be multi-line)
        if title_match := re.search(r"Title: (.*?)(?:\nAuthors:|$)", part, re.DOTALL):
            title = " ".join(title_match[1].strip().split())
            link = f"https://arxiv.org/abs/{arxiv_id}"
            papers.append(Paper(title, link))

    print(len(papers), "papers found.")
    for p in papers:
        print(f"1. [{p.title}]({p.link})")


if __name__ == "__main__":
    main()
