"""Tests for raw MIME building + attachment decoding (pure logic, no Gmail API)."""

from __future__ import annotations

import base64
from email import message_from_bytes
from email.policy import default as default_policy

from gmail_ai_broker.mime import build_raw_message, decode_attachment_data


def _decode_raw(raw_b64: str):
    """Reverse build_raw_message: urlsafe-b64 -> EmailMessage (modern policy)."""
    padded = raw_b64 + "=" * (-len(raw_b64) % 4)
    return message_from_bytes(
        base64.urlsafe_b64decode(padded), policy=default_policy
    )


def test_build_raw_message_sets_headers_and_body():
    raw = build_raw_message(
        to="recipient@example.com",
        subject="Hello",
        body="This is the body.",
    )
    msg = _decode_raw(raw)
    assert msg["To"] == "recipient@example.com"
    assert msg["Subject"] == "Hello"
    assert "This is the body." in msg.get_content()


def test_build_raw_message_with_attachment_is_multipart_and_carries_file(tmp_path):
    pdf = tmp_path / "form.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake bytes")
    raw = build_raw_message(
        to="r@example.com",
        subject="Completed form",
        body="See attached.",
        attachments=[str(pdf)],
    )
    msg = _decode_raw(raw)
    assert msg.is_multipart()
    attachments = [
        p for p in msg.walk() if p.get_content_disposition() == "attachment"
    ]
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "form.pdf"
    assert attachments[0].get_payload(decode=True) == b"%PDF-1.4 fake bytes"


def test_build_raw_message_threads_reply_headers():
    raw = build_raw_message(
        to="r@example.com",
        subject="Re: thread",
        body="reply",
        in_reply_to="<orig-message-id@mail.gmail.com>",
    )
    msg = _decode_raw(raw)
    assert msg["In-Reply-To"] == "<orig-message-id@mail.gmail.com>"
    assert "<orig-message-id@mail.gmail.com>" in msg["References"]


def test_decode_attachment_data_roundtrips_without_padding():
    payload = b"arbitrary \x00\x01 binary bytes for a disability form"
    # Gmail returns urlsafe base64, often without padding.
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    assert decode_attachment_data(encoded) == payload
