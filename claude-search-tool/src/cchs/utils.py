"""Shared utility functions."""

import typer


def make_app(help_text: str) -> typer.Typer:
    """Create a Typer app with standard project configuration."""
    return typer.Typer(
        help=help_text,
        context_settings={"help_option_names": ["-h", "--help"]},
        add_completion=False,
        rich_markup_mode="rich",
        pretty_exceptions_show_locals=False,
        no_args_is_help=True,
    )
