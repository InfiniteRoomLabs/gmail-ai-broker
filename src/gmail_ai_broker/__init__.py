"""gmail-ai-broker: auditable CLI filling the official Gmail connector's gaps.

Capabilities the official connector lacks: attachment download, raw-MIME send
with attachments, Gmail filter CRUD (requires gmail.settings.basic), and raw
message fetch. Read-safe by default; the only transmit path is an explicit
`draft send`.
"""

__version__ = "0.1.0"
