"""Home screen with main menu options."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Header, Label, OptionList
from textual.widgets.option_list import Option

MENU_OPTIONS: list[tuple[str, str]] = [
    ("Capture from clipboard", "clipboard"),
    ("Load image from file", "file"),
    ("Paste text manually", "paste"),
    ("Settings", "settings"),
    ("Quit", "quit"),
]
"""Menu items as (label, action) pairs."""


class HomeScreen(Screen[str]):
    """Main menu screen shown on app launch.

    The screen resolves with a string action:
    "clipboard", "file", "paste", "settings", or "quit".
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
    ]

    CSS = """
    HomeScreen {
        align: center middle;
    }

    #menu-container {
        width: 50;
        height: auto;
        padding: 2 4;
    }

    OptionList {
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        """Build the home screen layout."""
        yield Header()
        with Center(), Vertical(id="menu-container"):
            yield Label("What would you like to do?", id="title")
            yield OptionList(
                *[Option(label, id=action) for label, action in MENU_OPTIONS],
                id="menu",
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle menu option selection."""
        option_id = event.option.id
        self.dismiss(option_id or "quit")

    def action_cursor_down(self) -> None:
        """Move the menu cursor down."""
        self.query_one("#menu", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move the menu cursor up."""
        self.query_one("#menu", OptionList).action_cursor_up()
