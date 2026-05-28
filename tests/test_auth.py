"""Tests for token loading + credential construction.

The network refresh itself is google-auth's job; we only verify we build a
Credentials object with the right fields and read the token file safely.
"""

from __future__ import annotations

import pytest

from gmail_ai_broker.auth import GMAIL_SCOPES, build_credentials, load_refresh_token


def test_load_refresh_token_strips_whitespace(tmp_path):
    f = tmp_path / ".gmail-refresh-token"
    f.write_text("1//the-refresh-token\n")
    assert load_refresh_token(f) == "1//the-refresh-token"


def test_load_refresh_token_missing_raises_helpful_error(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(RuntimeError, match=str(missing)):
        load_refresh_token(missing)


def test_scopes_are_modify_and_settings_basic():
    assert set(GMAIL_SCOPES) == {
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.settings.basic",
    }


def test_build_credentials_carries_refresh_fields():
    creds = build_credentials(
        refresh_token="1//rt",
        client_id="cid.apps.googleusercontent.com",
        client_secret="csecret",
        scopes=GMAIL_SCOPES,
    )
    assert creds.refresh_token == "1//rt"
    assert creds.client_id == "cid.apps.googleusercontent.com"
    assert creds.token_uri == "https://oauth2.googleapis.com/token"
    assert set(creds.scopes) == set(GMAIL_SCOPES)
