"""Extract titles and links from an arXiv newsletter using the raw email URL.

For long outputs, you can pipe the output to a pager like `less`:

    $ uv run arxiv-news <URL> | less -Rg
"""

import argparse
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

import requests
import typer
from rich.console import Console
from rich.markdown import Markdown


@dataclass(frozen=True)
class Paper:
    title: str
    link: str


BLOCKLIST_TOPICS = (
    "audio",
    "bio",
    "biology",
    "chemical",
    "chemistry",
    "drug",
    "memo",
    "modal",
    "molecule",
    "mri",
    "protein",
    "speech",
    "video",
    "vision",
    "visual",
    "x-ray",
)
BLOCKLIST_LANGUGES = (
    "basque",
    "chinese",
    "french",
    "greek",
    "hindi",
    "indian",
    "japanese",
    "portuguese",
    "romanian",
    "spanish",
)
BLOCKLIST_WORDS = BLOCKLIST_TOPICS + BLOCKLIST_LANGUGES
HIGHLIGHT_TOPICS = [
    "know",
    "graph",
    "sci",
]


def _valid_title(title: str) -> bool:
    return all(block_word not in title.lower() for block_word in BLOCKLIST_WORDS)


def _fetch_content(url: str) -> str:
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def _extract_papers(text: str) -> list[Paper]:
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


def _has_highlight(title: str) -> bool:
    return any(topic in title.casefold() for topic in HIGHLIGHT_TOPICS)


def _display_papers(papers: Sequence[Paper]) -> str:
    content: list[str] = []

    for i, p in enumerate(papers, 1):
        content.append(f"{i}. [{p.title}]({p.link})")
        if i % 10 == 0:
            content.append("\n---\n")

    return "\n".join(content)


def _generate_markdown(papers: Sequence[Paper]) -> str:
    papers_valid = [p for p in papers if _valid_title(p.title)]
    papers_highlighted = [p for p in papers_valid if _has_highlight(p.title)]
    papers_regular = [p for p in papers_valid if not _has_highlight(p.title)]

    markdown_content = [
        "# arXiv Papers",
        f"Total papers found: {len(papers)}\n",
        f"Papers after filtering: {len(papers_valid)}\n",
        f"Papers with highlights: {len(papers_highlighted)}",
        "## Highlighted papers",
        _display_papers(papers_highlighted),
        "## Other papers",
        _display_papers(papers_regular),
    ]

    return "\n".join(markdown_content)


def _display_markdown(markdown_content: str) -> None:
    console = Console(force_terminal=True)
    md = Markdown(markdown_content)
    console.print(md)


app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


@app.command(help=__doc__)
def main(
    url: Annotated[str, typer.Argument(help="URL to the raw arXiv newsletter email")],
) -> None:
    content = _fetch_content(url)
    papers = _extract_papers(content)
    markdown_content = _generate_markdown(papers)
    _display_markdown(markdown_content)


if __name__ == "__main__":
    app()
