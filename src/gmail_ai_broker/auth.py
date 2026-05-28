"""OAuth token loading and credential construction.

The agent never holds a durable credential: a refresh token sits in a mode-600
file under ~/.secrets (origin: Bitwarden), and google-auth exchanges it for a
short-lived access token at call time. We only request two scopes -- gmail.modify
(read/write messages, drafts, labels) and gmail.settings.basic (filters).

THREAT MODEL: gmail.modify is mailbox-wide. There is no per-label OAuth scoping;
any "only touch label X" behavior is enforced by this code, not by Google. The
refresh token is the crown jewel.
"""

from __future__ import annotations

import os
from pathlib import Path

from google.oauth2.credentials import Credentials

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.settings.basic",
]

TOKEN_URI = "https://oauth2.googleapis.com/token"


def load_refresh_token(path: Path) -> str:
    """Read the refresh token from a file, stripping whitespace.

    Raises a clear RuntimeError (naming the path) if it is missing, so setup
    problems are obvious rather than surfacing as opaque auth failures.
    """
    path = Path(path)
    try:
        token = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Gmail refresh token not found at {path}. "
            "Complete the OAuth setup runbook (see README) and store the token there."
        ) from exc
    if not token:
        raise RuntimeError(f"Gmail refresh token file {path} is empty.")
    return token


def save_refresh_token(token: str, path: Path) -> None:
    """Write the refresh token to a mode-600 file, creating parents as needed.

    Mode 600 (owner read/write only) is the file-level containment for the
    crown-jewel credential.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Create with restrictive perms from the start (avoid a brief world-readable window).
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(token)
    os.chmod(path, 0o600)


def run_installed_app_flow(client_secrets_file: Path, scopes: list[str]) -> Credentials:
    """Drive the Desktop/installed-app loopback consent flow (interactive).

    Network + browser glue, exercised during setup (Gate 1), not unit-tested.
    Forces offline access + a consent prompt so Google returns a refresh token.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_file), scopes)
    return flow.run_local_server(
        port=0, access_type="offline", prompt="consent"
    )


def build_credentials(
    *,
    refresh_token: str,
    client_id: str,
    client_secret: str,
    scopes: list[str],
) -> Credentials:
    """Construct google-auth Credentials that can self-refresh on use."""
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
    )
