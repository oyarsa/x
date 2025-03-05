#!/usr/bin/env python3
"""Notify a message or send a document to a Telegram chat using a bot.

Example configuration (~/.config/telegram-notify/config.json):
{
    "token": "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "chatid": "1234567890"
}

To get the token, create a bot with https://telegram.me/botfather.
To get the chatid, send a message to the bot and open the URL:
https://api.telegram.org/bot<token>/getUpdates
"""

import argparse
import json
import sys
from pathlib import Path
from typing import BinaryIO, NoReturn

import requests

from scripts.util import HelpOnErrorArgumentParser

level_emojis = {
    "info": "ℹ️",  # noqa: RUF001
    "warning": "⚠️",
    "error": "❌",
}


def log_error(source: str, response: requests.Response) -> NoReturn:
    """Log an error message with the code and description, then terminates."""
    try:
        desc = response.json()["description"]
    except json.JSONDecodeError:
        desc = response.text

    print(f"ERROR | {source} | {response.status_code} | {desc}")
    sys.exit(1)


def send_message(
    token: str, chat_id: str, message: str, level: str, title: str | None
) -> None:
    """Send text message.

    Args:
        token: The Telegram bot token.
        chat_id: The chat id.
        message: The message content to send.
        level: The log level of the message.
        title: The title of the message. If not provided, the level is used.
    """
    emoji = level_emojis[level]
    header = f"{emoji} {title or level.upper()} {emoji}"
    message = f"{header}\n\n{message}"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}

    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        log_error("send_message", e.response)


def send_document(
    token: str, chat_id: str, document_file: BinaryIO, level: str, caption: str | None
) -> None:
    """Send document.

    Args:
        token: The Telegram bot token.
        chat_id: The chat id.
        document_file: The file-like object of the document to send.
        level: The log level of the document.
        caption: The caption of the document. If not provided, the level is used.
    """

    emoji = level_emojis[level]
    caption = f"{emoji} {caption or level.upper()} {emoji}"

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    params = {"chat_id": chat_id, "caption": caption}
    files = {"document": document_file}

    try:
        response = requests.post(url, data=params, files=files)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        log_error("send_document", e.response)


def main() -> None:
    parser = HelpOnErrorArgumentParser(__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("~/.config/telegram-notify/config.json").expanduser(),
        help="The configuration file (default: %(default)s).",
    )
    parser.add_argument(
        "--level",
        type=str,
        choices=["info", "warning", "error"],
        default="info",
        help="The level of the message (default: %(default)s).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    message_parser = subparsers.add_parser("message", help="Send a message")
    message_parser.add_argument(
        "message",
        type=str,
        nargs="?",
        help="The message to send. If not provided or empty, read from stdin.",
    )
    message_parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="The title of message. If not provided, the level is used.",
    )

    document_parser = subparsers.add_parser("document", help="Send a document")
    document_parser.add_argument(
        "document_file",
        type=argparse.FileType("rb"),
        nargs="?",
        default=sys.stdin,
        help="The document to send, or stdin if not provided.",
    )
    document_parser.add_argument(
        "--caption",
        type=str,
        default=None,
        help="The caption of the document.",
    )

    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    token = config["token"]
    chat_id = config["chatid"]

    if args.command == "message":
        message = args.message or sys.stdin.read().strip()
        send_message(token, chat_id, message, args.level, args.title)
    elif args.command == "document":
        send_document(token, chat_id, args.document_file, args.level, args.caption)


if __name__ == "__main__":
    main()
