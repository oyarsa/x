"""Google Calendar API integration: auth, calendar listing, event creation."""

import datetime
import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel

from paca._shed.google import (
    build_oauth_flow,
    calendar_list,
    exchange_code,
    get_auth_url,
    insert_event,
    load_credentials,
    refresh_credentials,
    save_credentials,
)
from paca.config import config_dir
from paca.oauth_client import load_client_config
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


class AuthError(Exception):
    """Raised when Google Calendar authentication is not available."""


def get_credentials() -> Any:
    """Load existing Google OAuth credentials, refreshing if expired.

    Does NOT run the interactive OAuth flow — use `authenticate()` for that.
    Raises `AuthError` if no valid credentials are available.

    Returns:
        Valid Google OAuth credentials.

    Raises:
        AuthError: If credentials are missing, expired without refresh token,
            or the client secrets file is not found.
    """
    token_path = _token_path()
    creds = load_credentials(token_path, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        refresh_credentials(creds)
        save_credentials(creds, token_path)
        return creds

    msg = "Not authenticated. Run `paca auth` to sign in to Google Calendar."
    raise AuthError(msg)


_REDIRECT_URI = "http://localhost:1"
"""Redirect URI for the manual copy-paste OAuth flow.

Uses an unroutable localhost address so the browser shows the redirect URL
in the address bar for the user to copy.
"""


def _client_config() -> dict[str, object]:
    """Return the OAuth client config from the user's credentials.json.

    Returns:
        OAuth client configuration dict.

    Raises:
        FileNotFoundError: If credentials.json is missing.
    """
    return load_client_config()


def authenticate() -> Any:
    """Run the interactive OAuth flow to obtain Google credentials.

    Prints an authorisation URL for the user to visit, then prompts them
    to paste back the redirect URL containing the auth code.

    Uses the OAuth client config from credentials.json in the
    paca config directory.

    This must be run outside the TUI (e.g. via `paca auth`).

    Returns:
        Valid Google OAuth credentials.
    """
    flow = build_oauth_flow(_client_config(), SCOPES, redirect_uri=_REDIRECT_URI)
    auth_url = get_auth_url(flow)

    print(f"Open this URL in your browser:\n\n  {auth_url}\n")
    print("After authorising, your browser will redirect to a localhost URL")
    print(
        "that won't load. Copy the FULL URL from the address bar and paste it here.\n"
    )

    redirect_url = input("Paste the redirect URL: ").strip()

    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)
    code_values = params.get("code")
    if not code_values:
        msg = "No authorisation code found in the URL. Please try again."
        raise ValueError(msg)

    creds = exchange_code(flow, code_values[0])
    save_credentials(creds, _token_path())
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
