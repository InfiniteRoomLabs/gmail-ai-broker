"""Network glue: build an authenticated Gmail API service.

Thin wrapper over googleapiclient discovery. Not unit-tested (it is exercised
end-to-end at Gate 1 verification); kept tiny on purpose.
"""

from __future__ import annotations

from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def build_gmail_service(credentials: Credentials) -> Any:
    # cache_discovery=False avoids a noisy oauth2client file-cache warning.
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)
