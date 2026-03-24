"""Typed wrappers for Google API client libraries."""

# pyright: basic

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request  # type: ignore[import-untyped]
from google.oauth2.credentials import Credentials  # type: ignore[import-untyped]
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]


def load_credentials(path: Path, scopes: Sequence[str]) -> Credentials | None:
    """Load cached OAuth credentials from a JSON file.

    Args:
        path: Path to the token file.
        scopes: Required OAuth scopes.

    Returns:
        Credentials if the file exists, None otherwise.
    """
    if not path.exists():
        return None
    return Credentials.from_authorized_user_file(str(path), list(scopes))


def refresh_credentials(creds: Credentials) -> None:
    """Refresh expired OAuth credentials in place.

    Args:
        creds: Credentials with a valid refresh token.
    """
    creds.refresh(Request())


def run_oauth_flow_local(secrets_path: Path, scopes: Sequence[str]) -> Credentials:
    """Run the installed-app OAuth flow with a local redirect server.

    Suitable when the CLI runs on the same machine as the browser.

    Args:
        secrets_path: Path to the client secrets JSON file.
        scopes: Required OAuth scopes.

    Returns:
        Fresh OAuth credentials.
    """
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), list(scopes))
    return flow.run_local_server(port=0, open_browser=False)


def build_oauth_flow(
    secrets_path: Path,
    scopes: Sequence[str],
    redirect_uri: str,
) -> InstalledAppFlow:
    """Create an OAuth flow with a custom redirect URI.

    Args:
        secrets_path: Path to the client secrets JSON file.
        scopes: Required OAuth scopes.
        redirect_uri: The redirect URI to use.

    Returns:
        Configured OAuth flow.
    """
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), list(scopes))
    flow.redirect_uri = redirect_uri
    return flow


def get_auth_url(flow: InstalledAppFlow) -> str:
    """Generate the OAuth authorisation URL from a flow.

    Args:
        flow: A configured OAuth flow.

    Returns:
        The URL to visit in a browser.
    """
    url, _ = flow.authorization_url(prompt="consent")
    return url


def exchange_code(flow: InstalledAppFlow, code: str) -> Credentials:
    """Exchange an authorisation code for credentials.

    Args:
        flow: The same OAuth flow used to generate the auth URL.
        code: The authorisation code from the redirect.

    Returns:
        Valid OAuth credentials.
    """
    flow.fetch_token(code=code)
    return flow.credentials


def save_credentials(creds: Credentials, path: Path) -> None:
    """Persist OAuth credentials to a JSON file.

    Args:
        creds: Credentials to save.
        path: Target file path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json())


def calendar_list(creds: Credentials) -> list[dict[str, Any]]:
    """Fetch all calendar list entries from the Google Calendar API.

    Args:
        creds: Valid OAuth credentials.

    Returns:
        List of raw calendar resource dicts.
    """
    service = build("calendar", "v3", credentials=creds)
    result: dict[str, Any] = service.calendarList().list().execute()
    items: list[dict[str, Any]] = result.get("items", [])
    return items


def insert_event(
    creds: Credentials,
    *,
    calendar_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Create an event via the Google Calendar API.

    Args:
        creds: Valid OAuth credentials.
        calendar_id: Target calendar ID.
        body: Event resource body.

    Returns:
        Created event resource dict.
    """
    service = build("calendar", "v3", credentials=creds)
    event: dict[str, Any] = (
        service.events().insert(calendarId=calendar_id, body=body).execute()
    )
    return event
