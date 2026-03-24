"""PArse and create CAlendar appointments."""

import sys
from pathlib import Path

import typer

from paca.calendar_provider import authenticate
from paca.config import (
    PacaConfig,
    config_path,
    detect_timezone,
    load_config,
    save_config,
)
from paca.input_capture import CapturedInput, make_text_input, read_file_input
from paca.ui.app import PacaApp

app = typer.Typer(
    help="Parse and create calendar appointments.",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


@app.command()
def init(
    config_file: Path = typer.Option(  # noqa: B008
        None,
        "--config-path",
        help="Path to write config file. Defaults to ~/.config/paca/config.toml.",
    ),
) -> None:
    """Create the default configuration file."""
    target = config_file or config_path()
    if target.exists():
        typer.echo(f"Config already exists at {target}")
        raise typer.Exit(code=1)

    tz = detect_timezone()

    calendar_name = typer.prompt("Default calendar name", default="Compromissos")
    timezone = typer.prompt("Timezone", default=tz)
    model = typer.prompt("OpenAI model", default="gpt-4o")

    config = PacaConfig(
        default_calendar_name=calendar_name,
        timezone=timezone,
        model=model,
    )
    save_config(config, target)
    typer.echo(f"Created config at {target}")


@app.command()
def auth() -> None:
    """Authenticate with Google Calendar via OAuth.

    Opens a browser for the Google consent flow. Run this before using the TUI
    for the first time, or if your token has expired and cannot be refreshed.
    """
    try:
        authenticate()
        typer.echo("Authenticated successfully.")
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"Authentication failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def run(
    file: Path | None = typer.Argument(  # noqa: B008
        None, help="Image or text file to extract from. Use - for stdin."
    ),
) -> None:
    """Launch the TUI to extract and create a calendar event."""
    captured: CapturedInput | None = None

    if file is not None:
        if str(file) == "-":
            text = sys.stdin.read()
            captured = make_text_input(text, source="stdin")
        else:
            captured = read_file_input(file)

    config = load_config()
    tui = PacaApp(config=config, initial_input=captured)
    tui.run()


def main() -> None:
    """Entrypoint."""
    app()
