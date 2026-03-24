"""Logging configuration with Rich handler."""

import logging
import os

from rich.console import Console
from rich.logging import RichHandler

console = Console(stderr=True)


def setup_logging() -> None:
    """Configure the cchs logger with a RichHandler."""
    level = os.environ.get("LOG_LEVEL", "INFO").upper()

    handler = RichHandler(
        console=console,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )
    handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))

    logger = logging.getLogger("cchs")
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
