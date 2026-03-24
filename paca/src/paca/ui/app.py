"""Main Textual application for paca."""

from pathlib import Path

from textual.app import App
from textual.worker import Worker, WorkerState

from paca.calendar_provider import (
    AuthError,
    CalendarInfo,
    build_event_body,
    create_event,
    get_credentials,
    list_calendars,
    pick_default_calendar,
)
from paca.config import PacaConfig, detect_timezone
from paca.extractor import extract
from paca.input_capture import (
    CapturedInput,
    capture_clipboard,
    make_text_input,
    read_file_input,
)
from paca.schema import (
    EventDraft,
    ExtractionResult,
    ReminderConfig,
    ReminderMethod,
)
from paca.ui.file_input_screen import FileInputScreen
from paca.ui.home_screen import HomeScreen
from paca.ui.paste_screen import PasteScreen
from paca.ui.review_screen import ReviewScreen
from paca.ui.success_screen import SuccessScreen


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
        """Show a path input screen for loading a file."""
        self.push_screen(FileInputScreen(), callback=self._on_file_result)

    def _on_file_result(self, path_str: str | None) -> None:
        """Handle file input screen result.

        Args:
            path_str: The file path entered by the user, or None if cancelled.
        """
        if path_str is None:
            self.push_screen(HomeScreen(), callback=self._on_home_choice)
            return
        path = Path(path_str)
        try:
            captured = read_file_input(path)
        except FileNotFoundError:
            self.notify(f"File not found: {path}", severity="error")
            self.push_screen(HomeScreen(), callback=self._on_home_choice)
            return
        self._start_extraction(captured)

    def _paste_text(self) -> None:
        """Show the paste screen for manual text entry."""
        self.push_screen(PasteScreen(), callback=self._on_paste_result)

    def _on_paste_result(self, text: str | None) -> None:
        """Handle paste screen result.

        Args:
            text: The text entered by the user, or None if cancelled.
        """
        if text is None:
            self.push_screen(HomeScreen(), callback=self._on_home_choice)
            return
        captured = make_text_input(text, source="manual paste")
        self._start_extraction(captured)

    def _start_extraction(self, captured: CapturedInput) -> None:
        """Begin LLM extraction in a background worker.

        Args:
            captured: The input to extract appointment data from.
        """
        self._captured = captured
        self.notify("Extracting appointment details...")

        def _do_extract() -> ExtractionResult:
            """Run the extraction in a thread."""
            return extract(captured, model=self.config.model)

        self.run_worker(_do_extract, name="extract", thread=True)

    def _show_review(self, draft: EventDraft) -> None:
        """Fetch calendars in a background worker, then show review screen.

        Args:
            draft: The event draft to present for review.
        """
        self._pending_draft = draft

        def _do_fetch_calendars() -> list[CalendarInfo]:
            """Fetch calendars in a thread."""
            creds = get_credentials()
            return list_calendars(creds)

        self.run_worker(_do_fetch_calendars, name="fetch_calendars", thread=True)

    def _on_review_result(self, draft: EventDraft | None) -> None:
        """Handle review screen result.

        Args:
            draft: The finalised EventDraft to save, None if cancelled,
                or an empty-title sentinel requesting re-extraction.
        """
        if draft is None:
            self.push_screen(HomeScreen(), callback=self._on_home_choice)
            return
        if not draft.title and self._captured:
            # Empty title = re-extract sentinel from action_reextract
            self._start_extraction(self._captured)
            return
        self._save_event(draft)

    def _save_event(self, draft: EventDraft) -> None:
        """Create the event in Google Calendar via a background worker.

        Args:
            draft: The finalised event draft to persist.
        """
        self._saving_draft = draft
        timezone = self.config.timezone or detect_timezone()
        body = build_event_body(draft, timezone=timezone)

        def _do_create() -> dict[str, str]:
            """Create the event in a thread."""
            creds = get_credentials()
            result = create_event(creds, calendar_id=draft.calendar_id, body=body)
            return {"link": result.get("htmlLink", ""), "title": draft.title}

        self.run_worker(_do_create, name="create_event", thread=True)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker completion for extraction, calendar fetch, and event creation.

        Args:
            event: The worker state change event.
        """
        if event.state != WorkerState.SUCCESS:
            if event.state == WorkerState.ERROR:
                error = event.worker.error
                if isinstance(error, AuthError):
                    self.notify(
                        "Not authenticated. Run `paca auth` first.",
                        severity="error",
                    )
                    self.exit()
                else:
                    self.notify(
                        f"Operation failed: {error}",
                        severity="error",
                    )
                    self.push_screen(HomeScreen(), callback=self._on_home_choice)
            return

        if event.worker.name == "extract":
            result: ExtractionResult = event.worker.result  # type: ignore[assignment]
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
            self._show_review(draft)

        elif event.worker.name == "fetch_calendars":
            calendars: list[CalendarInfo] = event.worker.result  # type: ignore[assignment]
            draft = self._pending_draft
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

        elif event.worker.name == "create_event":
            info: dict[str, str] = event.worker.result  # type: ignore[assignment]
            self.push_screen(
                SuccessScreen(summary=info["title"], link=info["link"]),
                callback=self._on_success_dismissed,
            )

    def _on_success_dismissed(self, _result: None) -> None:
        """Return to home after success screen."""
        self.push_screen(HomeScreen(), callback=self._on_home_choice)
