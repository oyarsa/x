"""Success screen displayed after event creation."""

from textual.app import ComposeResult
from textual.containers import Center
from textual.screen import Screen
from textual.widgets import Button, Header, Label, Static


class SuccessScreen(Screen[None]):
    """Shows a summary of the created event."""

    CSS = """
    SuccessScreen {
        align: center middle;
    }

    #success-box {
        width: 60;
        height: auto;
        padding: 2 4;
        border: solid $success;
    }

    #event-link {
        margin-top: 1;
        color: $accent;
    }
    """

    def __init__(self, *, summary: str, link: str = "") -> None:
        """Initialise the success screen.

        Args:
            summary: A short description of the created event.
            link: Optional HTML link to the created event.
        """
        super().__init__()
        self._summary = summary
        self._link = link

    def compose(self) -> ComposeResult:
        """Build the success screen."""
        yield Header()
        with Center(), Center(id="success-box"):
            yield Label("Event created successfully!")
            yield Static(self._summary)
            if self._link:
                yield Static(self._link, id="event-link")
            yield Button("Done", id="done", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle done button.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "done":
            self.dismiss(None)
