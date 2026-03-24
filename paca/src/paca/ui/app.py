"""Main Textual application for paca."""

from textual.app import App

from paca.calendar_provider import (
    build_event_body,
    create_event,
    get_credentials,
    list_calendars,
    pick_default_calendar,
)
from paca.config import PacaConfig, detect_timezone
from paca.extractor import extract
from paca.input_capture import CapturedInput, capture_clipboard
from paca.schema import (
    EventDraft,
    ReminderConfig,
    ReminderMethod,
)
from paca.ui.home_screen import HomeScreen
from paca.ui.review_screen import ReviewScreen


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
        self.notify("Extracting appointment details...")

        try:
            result = extract(captured, model=self.config.model)
        except Exception as exc:
            self.notify(f"Extraction failed: {exc}", severity="error")
            self.push_screen(HomeScreen(), callback=self._on_home_choice)
            return

        draft = EventDraft(
            title=result.title,
            date=result.date or "",
            start_time=result.start_time or "",
            end_time=result.end_time or "",
            duration_minutes=result.duration_minutes,
            location=result.location or "",
            notes=result.notes or "",
            confidence=result.confidence,
            warnings=tuple(result.warnings),
            source_summary=result.source_summary or "",
            reminders=ReminderConfig(
                method=ReminderMethod.POPUP,
                selected_minutes=tuple(self.config.default_reminder_minutes),
            ),
        )

        self._captured = captured
        self._show_review(draft)

    def _show_review(self, draft: EventDraft) -> None:
        """Fetch calendars and show the review screen.

        Args:
            draft: The event draft to present for review.
        """
        try:
            creds = get_credentials()
            calendars = list_calendars(creds)
        except Exception as exc:
            self.notify(f"Calendar access failed: {exc}", severity="error")
            calendars = []

        default = pick_default_calendar(
            calendars,
            preferred_name=self.config.default_calendar_name,
        )
        if default:
            draft = draft.model_copy(
                update={"calendar_id": default.id, "calendar_name": default.name},
            )

        source_text = ""
        if self._captured and self._captured.text:
            source_text = self._captured.text

        self.push_screen(
            ReviewScreen(draft, calendars, source_text=source_text),
            callback=self._on_review_result,
        )

    def _on_review_result(self, draft: EventDraft | None) -> None:
        """Handle review screen result.

        Args:
            draft: The finalised EventDraft to save, or None if the user
                cancelled or requested re-extraction.
        """
        if draft is None:
            self.push_screen(HomeScreen(), callback=self._on_home_choice)
            return
        self._save_event(draft)

    def _save_event(self, draft: EventDraft) -> None:
        """Create the event in Google Calendar.

        Args:
            draft: The finalised event draft to persist.
        """
        timezone = self.config.timezone or detect_timezone()
        body = build_event_body(draft, timezone=timezone)

        try:
            creds = get_credentials()
            result = create_event(creds, calendar_id=draft.calendar_id, body=body)
            link = result.get("htmlLink", "")
            self.notify(f"Event created! {link}", severity="information")
        except Exception as exc:
            self.notify(f"Failed to create event: {exc}", severity="error")

        self.push_screen(HomeScreen(), callback=self._on_home_choice)
