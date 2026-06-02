"""gmail-ai-mcp: a stdio MCP server over GmailBroker.

Exposes seven of GmailBroker's eight capabilities as MCP tools (attachment
download, raw message fetch, filter list/get/create/delete, draft create).
``send_draft`` is deliberately NOT exposed -- transmitting mail stays a
terminal-only ``gmail-ai-broker draft send --yes`` act, preserving the
one-deliberate-transmit-path invariant against indirect prompt injection.
"""
