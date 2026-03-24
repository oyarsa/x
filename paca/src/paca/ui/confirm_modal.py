"""Confirmation modal dialog."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmModal(ModalScreen[bool]):
    """A modal dialog that asks for yes/no confirmation.

    Resolves with True if confirmed, False if cancelled.
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
        ("y", "confirm", "Yes"),
        ("n", "cancel", "No"),
    ]

    CSS = """
    ConfirmModal {
        align: center middle;
    }

    #confirm-box {
        width: 50;
        height: auto;
        padding: 2 4;
        border: solid $warning;
        background: $surface;
    }

    #confirm-message {
        margin-bottom: 1;
    }

    #confirm-buttons {
        height: 3;
        align: center middle;
    }

    #confirm-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, message: str) -> None:
        """Initialise the confirmation modal.

        Args:
            message: The question to display.
        """
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        """Build the modal layout."""
        with Vertical(id="confirm-box"):
            yield Label(self._message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes", id="yes", variant="warning")
                yield Button("No", id="no", variant="default")

    def action_confirm(self) -> None:
        """Confirm the action."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Cancel the action."""
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "yes":
            self.dismiss(True)
        else:
            self.dismiss(False)
