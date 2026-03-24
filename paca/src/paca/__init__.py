"""PArse and create CAlendar appointments."""

import sys
from pathlib import Path

import typer

from paca.config import (
    PacaConfig,
    config_path,
    detect_timezone,
    load_config,
    save_config,
)
from paca.input_capture import CapturedInput, make_text_input, read_file_input
from paca.ui.app import PacaApp

app = typer.Typer(help="Parse and create calendar appointments.")


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
