"""Screen for manual text input."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, TextArea


class PasteScreen(Screen[str | None]):
    """Screen for pasting or typing appointment text manually.

    Resolves with the entered text on submit, or None on cancel.
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
    ]

    CSS = """
    PasteScreen {
        align: center middle;
    }

    #paste-container {
        width: 80%;
        height: 80%;
        padding: 1 2;
    }

    TextArea {
        height: 1fr;
    }

    #paste-actions {
        height: 3;
        dock: bottom;
    }
    """

    def compose(self) -> ComposeResult:
        """Build the paste screen layout."""
        yield Header()
        with Vertical(id="paste-container"):
            yield TextArea(id="paste-input")
            with Vertical(id="paste-actions"):
                yield Button("Submit", id="submit", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "submit":
            text = self.query_one("#paste-input", TextArea).text
            if text.strip():
                self.dismiss(text.strip())
            else:
                self.notify("Please enter some text", severity="warning")

    def action_cancel(self) -> None:
        """Cancel and return."""
        self.dismiss(None)
