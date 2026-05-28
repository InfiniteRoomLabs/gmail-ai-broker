"""Raw MIME construction and attachment decoding for the Gmail API.

Gmail's ``users.messages.send`` (and draft create) take a ``raw`` field: the
RFC 2822 message, urlsafe-base64 encoded. Attachment ``data`` returned by
``users.messages.attachments.get`` is likewise urlsafe-base64 (often unpadded).
This module is pure -- no network, no auth -- so it is fully unit-testable.
"""

from __future__ import annotations

import base64
import mimetypes
from email.message import EmailMessage
from pathlib import Path


def build_raw_message(
    *,
    to: str,
    subject: str,
    body: str,
    attachments: list[str] | None = None,
    in_reply_to: str | None = None,
    sender: str | None = None,
    cc: str | None = None,
) -> str:
    """Build an RFC 2822 message and return it urlsafe-base64 encoded.

    The returned string is ready for the Gmail API ``raw`` field.
    """
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    if sender:
        msg["From"] = sender
    if cc:
        msg["Cc"] = cc
    if in_reply_to:
        # Thread the reply: both headers are needed for Gmail to group it.
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)

    for path_str in attachments or []:
        path = Path(path_str)
        data = path.read_bytes()
        ctype, _ = mimetypes.guess_type(path.name)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        msg.add_attachment(
            data, maintype=maintype, subtype=subtype, filename=path.name
        )

    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def decode_attachment_data(data: str) -> bytes:
    """Decode Gmail's urlsafe-base64 attachment data, tolerating missing padding."""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)
