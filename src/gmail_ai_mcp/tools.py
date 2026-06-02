"""MCP tool helpers: map tool arguments to GmailBroker calls.

This is the only logic-bearing module in the MCP package, so it is the only one
unit-tested. Each helper takes the broker explicitly (so tests can mock it).
Byte-producing reads write to an agent-supplied path and return a summary --
raw email bytes are never returned into the model context. No audit logic lives
here; the broker mutations audit themselves.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gmail_ai_broker.models import FilterSpec


def tool_download_attachment(
    broker: Any, message_id: str, attachment_id: str, out: str
) -> dict:
    data = broker.download_attachment(message_id, attachment_id)
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": out, "bytes_written": len(data)}


def tool_get_raw_message(broker: Any, message_id: str, out: str) -> dict:
    data = broker.get_raw_message(message_id)
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": out, "bytes_written": len(data)}


def tool_list_filters(broker: Any) -> list[dict]:
    return broker.list_filters()


def tool_get_filter(broker: Any, filter_id: str) -> dict:
    return broker.get_filter(filter_id)


def tool_create_draft(
    broker: Any,
    *,
    to: str,
    subject: str,
    body: str,
    attachments: list[str] | None = None,
    in_reply_to: str | None = None,
    cc: str | None = None,
) -> dict:
    return broker.create_draft(
        to=to,
        subject=subject,
        body=body,
        attachments=attachments,
        in_reply_to=in_reply_to,
        cc=cc,
    )


def tool_create_filter(broker: Any, spec: dict) -> dict:
    return broker.create_filter(FilterSpec.model_validate(spec))


def tool_delete_filter(broker: Any, filter_id: str) -> dict:
    broker.delete_filter(filter_id)
    return {"deleted": filter_id}
