"""FastMCP stdio server over GmailBroker.

Seven typed tool wrappers, one per exposed broker capability. There is no send
wrapper: this server cannot transmit mail, by design. The broker is built lazily
on first tool call so importing this module (and FastMCP schema generation) needs
no config or network. Config path comes from GMAIL_AI_BROKER_CONFIG if set, else
the XDG default.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from gmail_ai_mcp import tools

mcp = FastMCP("gmail-ai-broker")

_broker: Any = None


def _get_broker() -> Any:
    global _broker
    if _broker is None:
        from gmail_ai_broker.client import GmailBroker

        cfg = os.environ.get("GMAIL_AI_BROKER_CONFIG")
        _broker = GmailBroker.from_config(Path(cfg) if cfg else None)
    return _broker


@mcp.tool
def download_attachment(message_id: str, attachment_id: str, out: str) -> dict:
    """Download a message attachment to a local file path.

    Writes the attachment bytes to ``out`` and returns {path, bytes_written}.
    Bytes are never returned inline.
    """
    return tools.tool_download_attachment(_get_broker(), message_id, attachment_id, out)


@mcp.tool
def get_raw_message(message_id: str, out: str) -> dict:
    """Fetch a message's full raw RFC822 MIME to a local file path.

    Writes the raw bytes to ``out`` and returns {path, bytes_written}.
    """
    return tools.tool_get_raw_message(_get_broker(), message_id, out)


@mcp.tool
def list_filters() -> list[dict]:
    """List all Gmail filters as JSON resources."""
    return tools.tool_list_filters(_get_broker())


@mcp.tool
def get_filter(filter_id: str) -> dict:
    """Get a single Gmail filter resource by id."""
    return tools.tool_get_filter(_get_broker(), filter_id)


@mcp.tool
def create_draft(
    to: str,
    subject: str,
    body: str,
    attachments: list[str] | None = None,
    in_reply_to: str | None = None,
    cc: str | None = None,
) -> dict:
    """Stage a draft (optionally with local-file attachments). Does NOT send.

    ``attachments`` are local file paths. Returns the draft resource. Sending is
    intentionally unavailable here; review and send the draft from the CLI.
    """
    return tools.tool_create_draft(
        _get_broker(),
        to=to,
        subject=subject,
        body=body,
        attachments=attachments,
        in_reply_to=in_reply_to,
        cc=cc,
    )


@mcp.tool
def create_filter(spec: dict) -> dict:
    """Create a Gmail filter from a declarative spec object.

    ``spec`` is {criteria: {...}, action: {...}} (snake_case keys, e.g.
    add_label_ids). Validated before submission.
    """
    return tools.tool_create_filter(_get_broker(), spec)


@mcp.tool
def delete_filter(filter_id: str) -> dict:
    """Delete a Gmail filter by id. Returns {deleted: <id>}."""
    return tools.tool_delete_filter(_get_broker(), filter_id)


def main() -> None:
    """Run the server over stdio."""
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()
