"""Process emails from getmail output, with enhanced text cleaning."""

import argparse
import html
import json
import re
from dataclasses import asdict, dataclass
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from email.utils import parseaddr
from pathlib import Path
from typing import cast

import urlextract  # type: ignore
from tqdm import tqdm


@dataclass(frozen=True, kw_only=True)
class Contact:
    """Representation of a name and email address pair."""

    name: str
    email: str


@dataclass(frozen=True, kw_only=True)
class Email:
    """Representation of a cleaned email message."""

    from_: Contact
    to: Contact
    subject: str
    text: str


def remove_repeated_chars(text: str) -> str:
    """Remove or consolidate repeated special characters.

    Handles:
    - Repeated punctuation (*, -, =, etc.)
    - Quote marks (>)
    - Whitespace
    - Common email separators
    """
    # Handle repeated special characters
    patterns = [
        (r"\*{3,}", ""),  # Remove repeated asterisks
        (r"-{3,}", ""),  # Remove repeated dashes
        (r"={3,}", ""),  # Remove repeated equals
        (r"_{3,}", ""),  # Remove repeated underscores
        (r"\.{3,}", "..."),  # Consolidate repeated dots to ellipsis
        (r">{3,}", ""),  # Remove repeated quote marks
        (r"#{3,}", ""),  # Remove repeated hash marks
        (r"~{3,}", ""),  # Remove repeated tildes
        (r"\^{3,}", ""),  # Remove repeated carets
        (r"\+{3,}", ""),  # Remove repeated plus signs
    ]

    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)

    # Clean up whitespace around the removed patterns
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)  # Normalize multiple newlines
    text = re.sub(r"[ \t]+", " ", text)  # Normalize horizontal whitespace

    return text.strip()


def decode_header_string(header: str) -> str:
    """Decode an email header that might contain encoded parts."""
    parts: list[str] = []
    for content, charset in decode_header(header):
        if isinstance(content, bytes):
            try:
                parts.append(content.decode(charset or "utf-8", errors="replace"))
            except (LookupError, TypeError, UnicodeError):
                parts.append(content.decode("utf-8", errors="replace"))
        else:
            parts.append(str(content))
    return " ".join(parts)


def extract_name_and_email(addr: str) -> Contact:
    """Extract name and email from an address string, handling encoded headers."""
    decoded_addr = decode_header_string(addr)
    name, email = parseaddr(decoded_addr)
    return Contact(name=name or "<no name>", email=email)


class URLExtractor:
    """Extract URLs from text using urlextract library."""

    def __init__(self) -> None:
        self._extractor = urlextract.URLExtract()

    def find_urls(self, text: str) -> list[str]:
        """Find all URLs in the given text."""
        return cast(list[str], self._extractor.find_urls(text))


_URL_EXTRACTOR = URLExtractor()


def remove_urls(text: str) -> str:
    """Remove URLs while preserving text readability."""
    for url in _URL_EXTRACTOR.find_urls(text):
        text = text.replace(url, " ")
    return text.strip()


def remove_email_artifacts(text: str) -> str:
    """Remove common email formatting artifacts."""
    # Remove email client signatures
    text = re.sub(
        r"Sent from (?:my )?(?:iPhone|Android|mobile device|BlackBerry|iPad).*",
        "",
        text,
    )

    # Remove image placeholders
    text = re.sub(r"(?:Image|Inline image|Attachment) removed by sender\.?", "", text)

    # Remove quoted text markers and email thread markers
    text = re.sub(r"^\s*>+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"On.*wrote:$", "", text, flags=re.MULTILINE)
    text = re.sub(
        r"From:.*Sent:.*To:.*Subject:", "", text, flags=re.MULTILINE | re.DOTALL
    )

    # Remove common headers/footers
    text = re.sub(r"Original Message.*", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(
        r"Begin forwarded message:.*", "", text, flags=re.IGNORECASE | re.MULTILINE
    )

    # Remove social media and contact info
    text = re.sub(
        r"(?:Follow|Connect with|Find) us on:?.*",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(
        r"(?:Facebook|Twitter|LinkedIn|Instagram):.*",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    # Remove common signatures and footers
    text = re.sub(
        r"(?:Best|Kind|Warm|Regards|Sincerely|Thanks|Thank you|Cheers),?\s*\n.*",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(
        r"(?:Tel|Phone|Mobile|Email|Web):.*",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    # Remove legal disclaimers
    text = re.sub(r"Disclaimer:.*", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(
        r"Confidentiality Notice:.*", "", text, flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(
        r"This email (?:and any attachments )?(?:is|are) confidential.*",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Remove remaining artifacts
    text = re.sub(r"\(\s*\)", "", text)  # Empty parentheses
    text = re.sub(r"\[\s*\]", "", text)  # Empty brackets

    return text.strip()


def clean_unicode(text: str) -> str:
    """Clean problematic Unicode characters and normalize text."""
    # Replace common Unicode punctuation with ASCII equivalents
    replacements = {
        # Quotes and apostrophes
        "\u2018": "'",  # Left single quote
        "\u2019": "'",  # Right single quote
        "\u201a": "'",  # Single low quote
        "\u201b": "'",  # Single high reversed quote
        "\u201c": '"',  # Left double quote
        "\u201d": '"',  # Right double quote
        "\u201e": '"',  # Double low quote
        "\u201f": '"',  # Double high reversed quote
        # Dashes and hyphens
        "\u2010": "-",  # Hyphen
        "\u2011": "-",  # Non-breaking hyphen
        "\u2012": "-",  # Figure dash
        "\u2013": "-",  # En dash
        "\u2014": "-",  # Em dash
        "\u2015": "-",  # Horizontal bar
        # Other punctuation
        "\u2026": "...",  # Horizontal ellipsis
        "\u2022": "*",  # Bullet
        "\u2023": "*",  # Triangular bullet
        "\u2043": "-",  # Hyphen bullet
        # Spaces and invisible characters
        "\u00a0": " ",  # Non-breaking space
        "\u200b": "",  # Zero width space
        "\u200c": "",  # Zero width non-joiner
        "\u200d": "",  # Zero width joiner
        "\u2028": "\n",  # Line separator
        "\u2029": "\n\n",  # Paragraph separator
        "\ufeff": "",  # Zero width no-break space (BOM)
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove any remaining control characters
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # Remove any remaining non-ASCII characters except newlines
    text = re.sub(r"[^\x20-\x7E\n]", "", text)

    return text.strip()


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace and line endings."""
    # Convert Windows line endings to Unix
    text = text.replace("\r\n", "\n")

    # Normalize spaces and tabs
    text = re.sub(r"[ \t]+", " ", text)

    # Normalize multiple empty lines
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    # Remove spaces around newlines
    text = re.sub(r"\s*\n\s*", "\n", text)

    # Fix spacing around punctuation
    text = re.sub(r"\s*([.,!?])\s*", r"\1 ", text)

    return text.strip()


def clean_text(text: str) -> str:
    """Clean raw email text content for analysis."""
    # Handle quoted-printable encoding
    text = re.sub(r"=\r?\n", "", text)
    text = re.sub(
        r"=[0-9A-F]{2}",
        lambda m: bytes.fromhex(m.group(0)[1:]).decode("utf-8", errors="replace"),
        text,
    )

    # Remove HTML
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)

    # Apply cleaning steps in order
    text = remove_urls(text)
    text = remove_email_artifacts(text)
    text = remove_repeated_chars(text)
    text = clean_unicode(text)
    text = normalize_whitespace(text)

    return text.strip()


def get_text_parts(message: Message) -> list[str]:
    """Extract all text/plain parts from an email message."""
    texts: list[str] = []

    if message.get_content_type() == "text/plain":
        payload = message.get_payload(decode=True)
        if isinstance(payload, bytes):
            try:
                text = payload.decode(
                    message.get_content_charset() or "utf-8", errors="replace"
                )
                texts.append(text)
            except (LookupError, TypeError, UnicodeError):
                text = payload.decode("utf-8", errors="replace")
                texts.append(text)
    elif message.is_multipart():
        for part in message.get_payload():
            if isinstance(part, Message):
                texts.extend(get_text_parts(part))

    return texts


def get_email_text(message: Message) -> str:
    """Extract and clean the text content from an email message."""
    texts = get_text_parts(message)

    if not texts:
        return "<empty>"

    combined = "\n\n".join(text for text in texts if text.strip())
    return clean_text(combined)


def process_email_file(message: Message) -> Email:
    """Process a single email file into a simplified representation."""
    from_addr = message.get("From", "")
    to_addr = message.get("To", "")
    subject = clean_text(decode_header_string(message.get("Subject", "")))
    text = get_email_text(message)

    return Email(
        from_=extract_name_and_email(from_addr),
        to=extract_name_and_email(to_addr),
        subject=subject,
        text=text,
    )


def main(input_path: Path, output_path: Path, limit: int | None) -> None:
    """Process getmail files and save results to JSON file."""
    files = [file for file in input_path.rglob("*") if file.is_file()]

    emails: list[Email] = []
    for file in tqdm(files[:limit]):
        try:
            message = message_from_bytes(file.read_bytes())
            emails.append(process_email_file(message))
        except Exception as e:
            tqdm.write(f"Error processing {file}: {e}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([asdict(e) for e in emails], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert email files to JSON")
    parser.add_argument(
        "input_path", type=Path, help="Path to folder containing email files"
    )
    parser.add_argument("output_path", type=Path, help="Path for output JSON file")
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Maximum number of emails to process. If absent, process all.",
    )

    args = parser.parse_args()
    main(args.input_path, args.output_path, args.limit)
