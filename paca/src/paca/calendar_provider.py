"""Google Calendar API integration: auth, calendar listing, event creation."""

import datetime
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from paca._shed.google import (
    calendar_list,
    insert_event,
    load_credentials,
    refresh_credentials,
    run_oauth_flow,
    save_credentials,
)
from paca.config import config_dir
from paca.schema import (
    DEFAULT_DURATION_MINUTES,
    EventDraft,
    ReminderMethod,
)

logger = logging.getLogger(__name__)

SCOPES: Sequence[str] = (
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
)
"""OAuth scopes required for calendar listing and event creation."""


class CalendarInfo(BaseModel, frozen=True):
    """Summary of a Google Calendar."""

    id: str
    name: str
    primary: bool = False


def _token_path() -> Path:
    """Return the path to the stored OAuth token."""
    return config_dir() / "token.json"


def _credentials_path() -> Path:
    """Return the path to the OAuth client credentials file."""
    return config_dir() / "credentials.json"


def get_credentials() -> Any:
    """Load or create Google OAuth credentials.

    Reads cached token from the config directory. If missing or expired,
    launches the installed-app OAuth flow.

    Returns:
        Valid Google OAuth credentials.

    Raises:
        FileNotFoundError: If credentials.json is not found.
    """
    token_path = _token_path()
    creds = load_credentials(token_path, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        refresh_credentials(creds)
    else:
        creds_path = _credentials_path()
        if not creds_path.exists():
            msg = (
                f"Google OAuth credentials not found at {creds_path}. "
                "Download credentials.json from Google Cloud Console."
            )
            raise FileNotFoundError(msg)
        creds = run_oauth_flow(creds_path, SCOPES)

    save_credentials(creds, token_path)
    return creds


def list_calendars(creds: Any) -> list[CalendarInfo]:
    """Fetch the user's writable calendars.

    Args:
        creds: Valid Google OAuth credentials.

    Returns:
        List of CalendarInfo for writable calendars.
    """
    items = calendar_list(creds)

    calendars: list[CalendarInfo] = []
    for item in items:
        access: str = item.get("accessRole", "")
        if access in ("owner", "writer"):
            calendars.append(
                CalendarInfo(
                    id=item["id"],
                    name=item.get("summary", item["id"]),
                    primary=item.get("primary", False),
                ),
            )
    return calendars


def pick_default_calendar(
    calendars: Sequence[CalendarInfo],
    *,
    preferred_name: str = "",
) -> CalendarInfo | None:
    """Select the best default calendar from a list.

    Selection order per spec section 8:
    1. Exact name match on preferred_name.
    2. Primary calendar.
    3. First available calendar.

    Args:
        calendars: Available calendars.
        preferred_name: Preferred calendar name from config.

    Returns:
        Selected CalendarInfo, or None if the list is empty.
    """
    if not calendars:
        return None

    if preferred_name:
        for cal in calendars:
            if cal.name == preferred_name:
                return cal

    for cal in calendars:
        if cal.primary:
            return cal

    return calendars[0]


def compute_end_time(
    start_time: str,
    *,
    end_time: str | None = None,
    duration_minutes: int | None = None,
) -> str:
    """Compute event end time from start, optional end, or duration.

    Args:
        start_time: Start time in HH:MM format.
        end_time: Explicit end time if known.
        duration_minutes: Duration in minutes if known.

    Returns:
        End time in HH:MM format.
    """
    if end_time:
        return end_time

    minutes = duration_minutes or DEFAULT_DURATION_MINUTES
    start = datetime.datetime.strptime(start_time, "%H:%M")  # noqa: DTZ007
    end = start + datetime.timedelta(minutes=minutes)
    return end.strftime("%H:%M")


def build_event_body(draft: EventDraft, *, timezone: str) -> dict[str, Any]:
    """Build the Google Calendar event body from an EventDraft.

    Args:
        draft: The finalised event draft.
        timezone: IANA timezone string for the event.

    Returns:
        Dict suitable for events.insert API call.
    """
    end_time = compute_end_time(
        draft.start_time,
        end_time=draft.end_time or None,
        duration_minutes=draft.duration_minutes,
    )

    body: dict[str, Any] = {
        "summary": draft.title,
        "start": {
            "dateTime": f"{draft.date}T{draft.start_time}:00",
            "timeZone": timezone,
        },
        "end": {
            "dateTime": f"{draft.date}T{end_time}:00",
            "timeZone": timezone,
        },
    }

    if draft.location:
        body["location"] = draft.location
    if draft.notes:
        body["description"] = draft.notes

    reminders = draft.reminders
    if reminders.method == ReminderMethod.DEFAULT:
        body["reminders"] = {"useDefault": True}
    else:
        overrides = [
            {"method": reminders.method.value, "minutes": m}
            for m in reminders.selected_minutes
        ]
        body["reminders"] = {"useDefault": False, "overrides": overrides}

    return body


def create_event(
    creds: Any,
    *,
    calendar_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Create a Google Calendar event.

    Args:
        creds: Valid Google OAuth credentials.
        calendar_id: Target calendar ID.
        body: Event body dict from build_event_body.

    Returns:
        The created event resource dict.
    """
    event = insert_event(creds, calendar_id=calendar_id, body=body)
    logger.info("Created event: %s", event.get("htmlLink", ""))
    return event
