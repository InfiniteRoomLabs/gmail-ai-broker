"""Structural guards for the MCP server surface.

We do not exercise the network here (that is Gate-1, end-to-end). We assert the
exposed tool set: exactly the seven intended wrappers, and -- critically -- no
``send_draft`` / ``send`` wrapper, so the one-deliberate-transmit-path invariant
cannot regress silently.
"""

from __future__ import annotations

import asyncio

from gmail_ai_mcp import server

EXPECTED_TOOLS = {
    "download_attachment",
    "get_raw_message",
    "list_filters",
    "get_filter",
    "create_draft",
    "create_filter",
    "delete_filter",
}


def test_all_expected_tools_are_defined():
    for name in EXPECTED_TOOLS:
        fn = getattr(server, name, None)
        assert callable(fn), f"missing MCP tool wrapper: {name}"


def test_send_is_never_exposed():
    assert not hasattr(server, "send_draft")
    assert not hasattr(server, "send")


def test_main_is_callable():
    assert callable(server.main)


def test_registry_exposes_exactly_expected_tools_and_no_send():
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert names == EXPECTED_TOOLS
    assert "send_draft" not in names and "send" not in names
