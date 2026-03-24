"""Main Textual application for paca."""

from textual.app import App

from paca.config import PacaConfig
from paca.input_capture import CapturedInput, capture_clipboard
from paca.ui.home_screen import HomeScreen


class PacaApp(App[None]):
    """Paca TUI application."""

    TITLE = "paca"
    SUB_TITLE = "Parse and Create Appointments"

    def __init__(
        self,
        *,
        config: PacaConfig,
        initial_input: CapturedInput | None = None,
    ) -> None:
        """Initialise the application.

        Args:
            config: Loaded paca configuration.
            initial_input: Pre-captured input to skip the home screen capture
                step, or None to show the full home screen flow.
        """
        super().__init__()
        self.config = config
        self.initial_input = initial_input
        self._captured: CapturedInput | None = None

    def on_mount(self) -> None:
        """Show the home screen or skip to review if input was provided."""
        if self.initial_input is not None:
            self._start_extraction(self.initial_input)
        else:
            self.push_screen(HomeScreen(), callback=self._on_home_choice)

    def _on_home_choice(self, choice: str | None) -> None:
        """Handle the user's home screen selection.

        Args:
            choice: The action string returned by HomeScreen, or None if the
                screen was dismissed without a value.
        """
        if choice is None or choice == "quit":
            self.exit()
        elif choice == "clipboard":
            self._capture_from_clipboard()
        elif choice == "file":
            self._load_from_file()
        elif choice == "paste":
            self._paste_text()
        elif choice == "settings":
            self.notify("Settings not yet implemented", severity="warning")
            self.push_screen(HomeScreen(), callback=self._on_home_choice)

    def _capture_from_clipboard(self) -> None:
        """Capture input from clipboard and start extraction."""
        captured = capture_clipboard()
        if captured is None:
            self.notify("No usable clipboard content found", severity="error")
            self.push_screen(HomeScreen(), callback=self._on_home_choice)
            return
        self._start_extraction(captured)

    def _load_from_file(self) -> None:
        """Placeholder for file loading."""
        self.notify("File loading not yet implemented", severity="warning")
        self.push_screen(HomeScreen(), callback=self._on_home_choice)

    def _paste_text(self) -> None:
        """Placeholder for manual text paste."""
        self.notify("Text paste not yet implemented", severity="warning")
        self.push_screen(HomeScreen(), callback=self._on_home_choice)

    def _start_extraction(self, captured: CapturedInput) -> None:
        """Begin LLM extraction from captured input.

        Args:
            captured: The input to extract appointment data from.
        """
        self.notify("Extraction not yet implemented", severity="warning")
        self.push_screen(HomeScreen(), callback=self._on_home_choice)
