"""Extract titles and links from an arXiv newsletter using the raw email URL.

For long outputs, you can pipe the output to a pager like `less`:

    $ uv run arxiv-news <URL> | less -Rg
"""

import argparse
import re
from dataclasses import dataclass

import requests
from rich.console import Console
from rich.markdown import Markdown


@dataclass(frozen=True)
class Paper:
    title: str
    link: str


BLOCKLIST_TOPICS = ("audio", "speech", "video", "modal", "memo", "visual")
BLOCKLIST_LANGUGES = ("portuguese", "spanish", "french")
BLOCKLIST_WORDS = BLOCKLIST_TOPICS + BLOCKLIST_LANGUGES


def valid_title(title: str) -> bool:
    return all(block_word not in title.lower() for block_word in BLOCKLIST_WORDS)


def fetch_content(url: str) -> str:
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def extract_papers(text: str) -> list[Paper]:
    paper_parts = re.split(r"\n\\\\", text)
    papers: list[Paper] = []

    for part in paper_parts:
        arxiv_match = re.search(r"arXiv:(\d+\.\d+)", part)
        if not arxiv_match:
            continue
        arxiv_id = arxiv_match[1]

        if title_match := re.search(r"Title: (.*?)(?:\nAuthors:|$)", part, re.DOTALL):
            title = " ".join(title_match[1].strip().split())
            link = f"https://arxiv.org/abs/{arxiv_id}"
            papers.append(Paper(title, link))

    return papers


def generate_markdown(papers: list[Paper]) -> str:
    papers_valid = [p for p in papers if valid_title(p.title)]

    markdown_content = "# arXiv Papers\n\n"
    markdown_content += f"Total papers found: {len(papers)}\n\n"
    markdown_content += f"Papers after filtering: {len(papers_valid)}\n\n"

    for i, p in enumerate(papers_valid, 1):
        markdown_content += f"{i}. [{p.title}]({p.link})\n"
        if i % 10 == 0:
            markdown_content += "\n---\n\n"

    return markdown_content


def display_markdown(markdown_content: str) -> None:
    console = Console(force_terminal=True)
    md = Markdown(markdown_content)
    console.print(md)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url", help="URL of the arXiv newsletter")
    args = parser.parse_args()

    content = fetch_content(args.url)
    papers = extract_papers(content)
    markdown_content = generate_markdown(papers)
    display_markdown(markdown_content)


if __name__ == "__main__":
    main()
