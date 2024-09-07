"""Download Coppermind HTML and convert to Markdown.

Example:
# Rhythm of War chapter-by-chapter summary
$ python summary.py https://coppermind.net/wiki/Summary:Rhythm_of_War mw-content-text
"""

import argparse
from pathlib import Path

import html2text
import requests
from bs4 import BeautifulSoup


def main(url: str, element_id: str, output: Path) -> None:
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    target_element = soup.find(id=element_id)

    if not target_element:
        raise ValueError(f"Element with id '{element_id}' not found")

    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True

    markdown_content = h.handle(str(target_element))
    output.write_text(markdown_content)

    print(f"Markdown content saved to {output}")

    words_per_page = 250
    num_words = len(markdown_content.split())
    num_pages = num_words // words_per_page
    print(f"{num_words} words ({num_pages} pages at {words_per_page} words per page)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url", help="URL of the webpage to download")
    parser.add_argument("element_id", help="ID of the HTML element to convert")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default="summary.md",
        help="Output file name (optional)",
    )
    args = parser.parse_args()
    main(args.url, args.element_id, args.output)
