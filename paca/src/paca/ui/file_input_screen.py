"""Screen for file path input."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label


class FileInputScreen(Screen[str | None]):
    """Screen for entering a file path to load.

    Resolves with the file path string on submit, or None on cancel.
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
    ]

    CSS = """
    FileInputScreen {
        align: center middle;
    }

    #file-container {
        width: 80%;
        height: auto;
        padding: 2 4;
    }
    """

    def compose(self) -> ComposeResult:
        """Build the file input screen."""
        yield Header()
        with Vertical(id="file-container"):
            yield Label("Enter the path to an image or text file:")
            yield Input(placeholder="/path/to/file.png", id="file-path")
            yield Button("Load", id="load", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle load button.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "load":
            path = self.query_one("#file-path", Input).value
            if path.strip():
                self.dismiss(path.strip())
            else:
                self.notify("Please enter a file path", severity="warning")

    def action_cancel(self) -> None:
        """Cancel and return."""
        self.dismiss(None)
