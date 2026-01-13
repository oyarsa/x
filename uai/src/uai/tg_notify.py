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
from collections.abc import Sequence
from pathlib import Path
from typing import Any, BinaryIO, NoReturn, override

import requests


class ArgumentDefaultsRawDescriptionFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    """`formater_class` that shows the raw description text and adds default to help.

    The raw description text is useful when printing pre-formatted text (e.g. bullet
    lists, hard-wrapped text), such as when using a docstring for the `description`.

    The defaults are only added to options that define a `help` text. It's added as
    `(default: x)` at the end.
    """

    pass


class HelpOnErrorArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that prints the full help text on error."""

    @override
    def error(self, message: str) -> NoReturn:
        self.print_help(sys.stderr)
        self.exit(2, f"\nError: {message}\n")

    def __init__(
        self,
        description: str | None = None,
        prog: str | None = None,
        usage: str | None = None,
        epilog: str | None = None,
        parents: Sequence[argparse.ArgumentParser] = (),
        formatter_class: type[
            argparse.HelpFormatter
        ] = ArgumentDefaultsRawDescriptionFormatter,
        prefix_chars: str = "-",
        fromfile_prefix_chars: str | None = None,
        argument_default: Any = None,
        conflict_handler: str = "error",
        add_help: bool = True,
        allow_abbrev: bool = False,
        exit_on_error: bool = True,
    ) -> None:
        """Override `ArgumentParser.__init__` to make `description` the first parameter.

        Sets default `formatter_class` to be `ArgumentDefaultsRawDescriptionFormatter`
        since we're using the full module docstring as usage text, and includes the
        default value for all flags with defined help text. Also sets `allow_abbrev` to
        `False`, so that only real flags are accepted.

        The goal is to allow the most common case (use the module docstring as the
        description) to be just:

        Example:
            >>> parser = HelpOnErrorArgumentParser(__doc__)

        If the docstring contains a line with `---`, the text after that is not included
        in the help text.
        """
        if description:
            description = description.split("\n---", maxsplit=1)[0]
        super().__init__(
            prog=prog,
            usage=usage,
            description=description,
            epilog=epilog,
            parents=parents,
            formatter_class=formatter_class,
            prefix_chars=prefix_chars,
            fromfile_prefix_chars=fromfile_prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
            add_help=add_help,
            allow_abbrev=allow_abbrev,
            exit_on_error=exit_on_error,
        )


LEVEL_EMOJIS = {
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
    emoji = LEVEL_EMOJIS[level]
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

    emoji = LEVEL_EMOJIS[level]
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
