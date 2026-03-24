"""Home screen with main menu options."""

from textual.app import ComposeResult
from textual.containers import Center, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Header, Label


class HomeScreen(Screen[str]):
    """Main menu screen shown on app launch.

    The screen resolves with a string action:
    "clipboard", "file", "paste", "settings", or "quit".
    """

    CSS = """
    HomeScreen {
        align: center middle;
    }

    #menu {
        width: 50;
        height: auto;
        padding: 2 4;
    }

    Button {
        width: 100%;
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        """Build the home screen layout."""
        yield Header()
        with Center(), VerticalScroll(id="menu"):
            yield Label("What would you like to do?", id="title")
            yield Button("Capture from clipboard", id="clipboard", variant="primary")
            yield Button("Load image from file", id="file")
            yield Button("Paste text manually", id="paste")
            yield Button("Settings", id="settings")
            yield Button("Quit", id="quit", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle menu button presses."""
        self.dismiss(event.button.id or "quit")
