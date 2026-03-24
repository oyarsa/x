"""Review screen for editing extracted event details before saving."""

from collections.abc import Sequence
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

from paca.calendar_provider import CalendarInfo
from paca.schema import (
    REMINDER_PRESETS,
    Confidence,
    EventDraft,
    ReminderConfig,
    ReminderMethod,
)


class ReviewScreen(Screen[EventDraft | None]):
    """Editable form for reviewing and confirming an event draft.

    Resolves with the finalised EventDraft on save, or None on cancel.
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", "Back"),
        ("s", "save", "Save"),
        ("r", "reextract", "Re-extract"),
        ("e", "toggle_debug", "Debug JSON"),
    ]

    CSS = """
    ReviewScreen {
        layout: horizontal;
    }

    #form-pane {
        width: 1fr;
        padding: 1 2;
    }

    #info-pane {
        width: 1fr;
        padding: 1 2;
        border-left: solid $accent;
    }

    .field-label {
        margin-top: 1;
        text-style: bold;
    }

    Input {
        margin-bottom: 0;
    }

    #actions {
        dock: bottom;
        height: 3;
        padding: 0 2;
    }

    Button {
        margin: 0 1;
    }

    .warning {
        color: $warning;
    }
    """

    def __init__(
        self,
        draft: EventDraft,
        calendars: Sequence[CalendarInfo],
        *,
        source_text: str = "",
    ) -> None:
        """Initialise the review screen.

        Args:
            draft: The event draft to display and edit.
            calendars: Available calendars for the calendar selector.
            source_text: Original source text for the info pane preview.
        """
        super().__init__()
        self._draft = draft
        self._calendars = calendars
        self._source_text = source_text
        self._confirmed_low_confidence = False

    def compose(self) -> ComposeResult:
        """Build the review form layout."""
        yield Header()
        with Horizontal():
            with VerticalScroll(id="form-pane"):
                yield Label("Title", classes="field-label")
                yield Input(self._draft.title, id="title")
                yield Label("Date (YYYY-MM-DD)", classes="field-label")
                yield Input(self._draft.date, id="date")
                yield Label("Start time (HH:MM)", classes="field-label")
                yield Input(self._draft.start_time, id="start_time")
                yield Label("End time (HH:MM)", classes="field-label")
                yield Input(self._draft.end_time, id="end_time")
                yield Label("Location", classes="field-label")
                yield Input(self._draft.location, id="location")
                yield Label("Notes", classes="field-label")
                yield Input(self._draft.notes, id="notes")

                yield Label("Calendar", classes="field-label")
                cal_options = [(cal.name, cal.id) for cal in self._calendars]
                yield Select(
                    cal_options,
                    value=(
                        self._draft.calendar_id
                        or (self._calendars[0].id if self._calendars else Select.BLANK)
                    ),
                    id="calendar",
                )

                yield Label("Reminders", classes="field-label")
                selected = set(self._draft.reminders.selected_minutes)
                for preset in REMINDER_PRESETS:
                    yield Checkbox(
                        preset.label,
                        preset.minutes in selected,
                        id=f"reminder_{preset.minutes}",
                    )

            with Vertical(id="info-pane"):
                yield Label("Source", classes="field-label")
                yield Static(
                    self._source_text or "(no source preview)",
                    id="source-preview",
                )

                if self._draft.warnings:
                    yield Label("Warnings", classes="field-label")
                    for warning in self._draft.warnings:
                        yield Static(f"  {warning}", classes="warning")

                yield Label(
                    f"Confidence: {self._draft.confidence.value}",
                    id="confidence",
                )

        with Horizontal(id="actions"):
            yield Button("Back", id="back", variant="default")
            yield Button("Save", id="save", variant="success")
        yield Footer()

    def _collect_draft(self) -> EventDraft:
        """Gather current form values into an EventDraft.

        Returns:
            A new EventDraft reflecting the current state of the form.
        """
        title = self.query_one("#title", Input).value
        date = self.query_one("#date", Input).value
        start_time = self.query_one("#start_time", Input).value
        end_time = self.query_one("#end_time", Input).value
        location_val = self.query_one("#location", Input).value
        notes_val = self.query_one("#notes", Input).value

        cal_select = self.query_one("#calendar", Select)
        calendar_id = (
            str(cal_select.value) if cal_select.value is not Select.BLANK else ""
        )
        calendar_name = ""
        for cal in self._calendars:
            if cal.id == calendar_id:
                calendar_name = cal.name
                break

        selected_minutes: list[int] = []
        for preset in REMINDER_PRESETS:
            cb = self.query_one(f"#reminder_{preset.minutes}", Checkbox)
            if cb.value:
                selected_minutes.append(preset.minutes)

        return EventDraft(
            title=title,
            date=date,
            start_time=start_time,
            end_time=end_time,
            location=location_val,
            notes=notes_val,
            calendar_id=calendar_id,
            calendar_name=calendar_name,
            reminders=ReminderConfig(
                method=ReminderMethod.POPUP,
                selected_minutes=tuple(selected_minutes),
            ),
            confidence=self._draft.confidence,
            warnings=self._draft.warnings,
            source_summary=self._draft.source_summary,
        )

    def action_save(self) -> None:
        """Validate and save the event.

        Checks required fields, max 5 reminders, and prompts on low confidence.
        """
        draft = self._collect_draft()
        errors: list[str] = []
        if not draft.title:
            errors.append("Title is required")
        if not draft.date:
            errors.append("Date is required")
        if not draft.start_time:
            errors.append("Start time is required")
        if not draft.calendar_id:
            errors.append("Calendar must be selected")
        if len(list(draft.reminders.selected_minutes)) > 5:
            errors.append("Maximum 5 reminders allowed")

        if errors:
            self.notify("\n".join(errors), severity="error")
            return

        if draft.confidence == Confidence.LOW and not self._confirmed_low_confidence:
            self.notify(
                "Low confidence extraction. Press 's' again to confirm.",
                severity="warning",
            )
            self._confirmed_low_confidence = True
            return

        self.dismiss(draft)

    def action_reextract(self) -> None:
        """Request re-extraction from the app.

        Dismisses with a sentinel empty EventDraft (empty title) to signal
        re-extraction. The app distinguishes this from a normal cancel (None).
        """
        self.dismiss(EventDraft())

    def action_toggle_debug(self) -> None:
        """Toggle the raw JSON debug pane."""
        self.notify("Debug JSON toggle not yet implemented", severity="warning")

    def action_cancel(self) -> None:
        """Cancel and return to home."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle action bar buttons.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "save":
            self.action_save()
        elif event.button.id == "back":
            self.action_cancel()
