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
