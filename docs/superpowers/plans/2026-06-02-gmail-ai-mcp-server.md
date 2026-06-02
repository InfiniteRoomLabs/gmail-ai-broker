# gmail-ai-mcp Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stdio FastMCP server exposing seven of `GmailBroker`'s eight methods as MCP tools, so Claude can call the Gmail connector gap-fillers natively -- while `send_draft` stays terminal-only.

**Architecture:** A new `src/gmail_ai_mcp/` package. `tools.py` holds testable helper functions that take a `GmailBroker` and map tool args to broker calls (these carry the only logic and are unit-tested with a mocked broker). `server.py` holds the FastMCP instance, one thin typed tool wrapper per helper, lazy broker construction, and the stdio `main()` entrypoint (glue, exercised live, not unit-tested -- matching the repo convention that network glue is verified end-to-end). There is deliberately no `send_draft` wrapper.

**Tech Stack:** Python 3.12+, `fastmcp` (new core dependency), `pydantic` (existing `FilterSpec`), `pytest` + `unittest.mock` (existing test pattern), `uv`.

---

## Background the engineer needs

- `GmailBroker` lives in `src/gmail_ai_broker/client.py`. Construct it for real with `GmailBroker.from_config(config_path: Path | None)`. Its methods:
  - reads: `download_attachment(message_id, attachment_id) -> bytes`, `get_raw_message(message_id) -> bytes`, `list_filters() -> list[dict]`, `get_filter(filter_id) -> dict`
  - mutations (each writes its own audit line -- do NOT add audit logic in the MCP layer): `create_draft(*, to, subject, body, attachments=None, in_reply_to=None, cc=None) -> dict`, `create_filter(spec: FilterSpec) -> dict`, `delete_filter(filter_id) -> None`
  - `send_draft` EXISTS on the broker but MUST NOT be exposed as a tool.
- `FilterSpec` is in `src/gmail_ai_broker/models.py`. Build it from a plain dict with `FilterSpec.model_validate(data)`. It raises `pydantic.ValidationError` (or `ValueError` via validator) on empty criteria/action.
- Existing tests mock the Gmail service with `MagicMock` (see `tests/test_client.py`). Our tests instead mock the whole `GmailBroker` with `MagicMock`, since we sit one layer above it.
- The repo uses `uv`. Run tests with `uv run --extra dev pytest`.

## File structure

- Create: `src/gmail_ai_mcp/__init__.py` -- package marker + docstring.
- Create: `src/gmail_ai_mcp/tools.py` -- seven `tool_*(broker, ...)` helpers. The only logic-bearing file. Unit-tested.
- Create: `src/gmail_ai_mcp/server.py` -- FastMCP instance, seven typed `@mcp.tool` wrappers (no send), lazy `_get_broker()`, `main()`. Glue.
- Create: `tests/test_mcp_tools.py` -- unit tests for `tools.py` helpers with a mocked broker.
- Create: `tests/test_mcp_server.py` -- structural tests: the seven wrappers exist; no send wrapper exists.
- Modify: `pyproject.toml` -- add `fastmcp` dep + `gmail-ai-mcp` script.
- Modify: `README.md` -- replace the "Phase 2 (deferred)" section with built-server usage.
- Modify: `CLAUDE.md` -- mark Phase 2 built; keep the invariant note.

---

## Task 1: Package scaffold + dependency + script entry

**Files:**
- Create: `src/gmail_ai_mcp/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create the package marker**

Create `src/gmail_ai_mcp/__init__.py`:

```python
"""gmail-ai-mcp: a stdio MCP server over GmailBroker.

Exposes seven of GmailBroker's eight capabilities as MCP tools (attachment
download, raw message fetch, filter list/get/create/delete, draft create).
``send_draft`` is deliberately NOT exposed -- transmitting mail stays a
terminal-only ``gmail-ai-broker draft send --yes`` act, preserving the
one-deliberate-transmit-path invariant against indirect prompt injection.
"""
```

- [ ] **Step 2: Add the fastmcp dependency**

Run: `uv add fastmcp`

Expected: `pyproject.toml` `[project].dependencies` gains a `fastmcp>=...` line and `uv.lock` updates. (If the 7-day release-age gate blocks the newest fastmcp, this is expected per the global uv hardening -- pin to the newest allowed version, e.g. `uv add 'fastmcp<=<allowed>'`, and note it.)

- [ ] **Step 3: Add the script entry**

In `pyproject.toml`, under the existing `[project.scripts]` table, add the second line:

```toml
[project.scripts]
gmail-ai-broker = "gmail_ai_broker.cli.main:app"
gmail-ai-mcp = "gmail_ai_mcp.server:main"
```

- [ ] **Step 4: Sync and verify the package imports**

Run: `uv sync && uv run python -c "import gmail_ai_mcp; print('ok')"`
Expected: prints `ok` (no ImportError).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/gmail_ai_mcp/__init__.py
git commit -m "Scaffold gmail_ai_mcp package + fastmcp dep"
```

---

## Task 2: Tool helper functions (TDD)

These take a broker and return JSON-serializable results. Reads that produce bytes write to an agent-supplied `out` path and return a summary -- raw bytes never enter the result.

**Files:**
- Create: `tests/test_mcp_tools.py`
- Create: `src/gmail_ai_mcp/tools.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mcp_tools.py`:

```python
"""Unit tests for the MCP tool helpers.

The helpers sit one layer above GmailBroker, so the broker is mocked. We assert
the real behavior the MCP layer owns: byte reads land on disk (never returned
inline), dict specs become FilterSpec, and draft args pass through verbatim.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gmail_ai_broker.models import FilterSpec
from gmail_ai_mcp import tools


def test_download_attachment_writes_file_and_returns_summary(tmp_path):
    broker = MagicMock()
    broker.download_attachment.return_value = b"PDF-bytes"
    out = tmp_path / "form.pdf"

    result = tools.tool_download_attachment(broker, "m1", "att1", str(out))

    assert out.read_bytes() == b"PDF-bytes"
    assert result == {"path": str(out), "bytes_written": 9}
    broker.download_attachment.assert_called_once_with("m1", "att1")


def test_get_raw_message_writes_file_and_returns_summary(tmp_path):
    broker = MagicMock()
    broker.get_raw_message.return_value = b"From: a@b.com\r\n\r\nhi"
    out = tmp_path / "msg.eml"

    result = tools.tool_get_raw_message(broker, "m9", str(out))

    assert out.read_bytes() == b"From: a@b.com\r\n\r\nhi"
    assert result == {"path": str(out), "bytes_written": 19}
    broker.get_raw_message.assert_called_once_with("m9")


def test_list_filters_passes_through(tmp_path):
    broker = MagicMock()
    broker.list_filters.return_value = [{"id": "f1"}, {"id": "f2"}]
    assert tools.tool_list_filters(broker) == [{"id": "f1"}, {"id": "f2"}]


def test_get_filter_passes_through(tmp_path):
    broker = MagicMock()
    broker.get_filter.return_value = {"id": "f1"}
    assert tools.tool_get_filter(broker, "f1") == {"id": "f1"}
    broker.get_filter.assert_called_once_with("f1")


def test_create_draft_passes_all_args(tmp_path):
    broker = MagicMock()
    broker.create_draft.return_value = {"id": "d1"}

    result = tools.tool_create_draft(
        broker,
        to="r@example.com",
        subject="Hi",
        body="hello",
        attachments=["/tmp/a.pdf"],
        in_reply_to="<x@mail>",
        cc="c@example.com",
    )

    assert result == {"id": "d1"}
    broker.create_draft.assert_called_once_with(
        to="r@example.com",
        subject="Hi",
        body="hello",
        attachments=["/tmp/a.pdf"],
        in_reply_to="<x@mail>",
        cc="c@example.com",
    )


def test_create_filter_validates_dict_into_filterspec(tmp_path):
    broker = MagicMock()
    broker.create_filter.return_value = {"id": "f99"}

    result = tools.tool_create_filter(
        broker, {"criteria": {"from": "billing@example.com"}, "action": {"add_label_ids": ["L1"]}}
    )

    assert result == {"id": "f99"}
    (spec,), _ = broker.create_filter.call_args
    assert isinstance(spec, FilterSpec)
    assert spec.to_gmail_resource() == {
        "criteria": {"from": "billing@example.com"},
        "action": {"addLabelIds": ["L1"]},
    }


def test_create_filter_rejects_empty_spec(tmp_path):
    broker = MagicMock()
    with pytest.raises(Exception):
        tools.tool_create_filter(broker, {"criteria": {}, "action": {}})
    broker.create_filter.assert_not_called()


def test_delete_filter_returns_confirmation(tmp_path):
    broker = MagicMock()
    broker.delete_filter.return_value = None
    assert tools.tool_delete_filter(broker, "f99") == {"deleted": "f99"}
    broker.delete_filter.assert_called_once_with("f99")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_mcp_tools.py -q`
Expected: FAIL -- `ModuleNotFoundError: No module named 'gmail_ai_mcp.tools'`.

- [ ] **Step 3: Write the helpers**

Create `src/gmail_ai_mcp/tools.py`:

```python
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
    Path(out).write_bytes(data)
    return {"path": out, "bytes_written": len(data)}


def tool_get_raw_message(broker: Any, message_id: str, out: str) -> dict:
    data = broker.get_raw_message(message_id)
    Path(out).write_bytes(data)
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_mcp_tools.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add src/gmail_ai_mcp/tools.py tests/test_mcp_tools.py
git commit -m "Add MCP tool helpers (file-write reads, FilterSpec mapping)"
```

---

## Task 3: FastMCP server wrappers + main (with no-send guard test)

The wrappers are the actual MCP surface; FastMCP reads their type hints and docstrings to build tool schemas. They are glue (call the real broker), so we do NOT unit-test their network behavior. We DO test, structurally, that exactly the seven intended wrappers exist and that no send wrapper exists -- that is the regression guard for the core invariant.

**Files:**
- Create: `tests/test_mcp_server.py`
- Create: `src/gmail_ai_mcp/server.py`

- [ ] **Step 1: Write the failing structural tests**

Create `tests/test_mcp_server.py`:

```python
"""Structural guards for the MCP server surface.

We do not exercise the network here (that is Gate-1, end-to-end). We assert the
exposed tool set: exactly the seven intended wrappers, and -- critically -- no
``send_draft`` / ``send`` wrapper, so the one-deliberate-transmit-path invariant
cannot regress silently.
"""

from __future__ import annotations

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_mcp_server.py -q`
Expected: FAIL -- `ModuleNotFoundError: No module named 'gmail_ai_mcp.server'`.

- [ ] **Step 3: Write the server**

Create `src/gmail_ai_mcp/server.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_mcp_server.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full suite**

Run: `uv run --extra dev pytest -q`
Expected: PASS (all existing tests + 11 new ones).

- [ ] **Step 6: Smoke-test the server boots**

Run: `uv run python -c "from gmail_ai_mcp.server import mcp, main; print(type(mcp).__name__, callable(main))"`
Expected: prints `FastMCP True` (confirms FastMCP instance built and tools registered at import with no config/network).

- [ ] **Step 7: Commit**

```bash
git add src/gmail_ai_mcp/server.py tests/test_mcp_server.py
git commit -m "Add FastMCP server wrappers + no-send structural guard"
```

---

## Task 4: Docs -- mark Phase 2 built

**Files:**
- Modify: `README.md` (the "## Phase 2 (deferred)" section, currently the last section)
- Modify: `CLAUDE.md` (the "## Phase 2 (deferred)" section)

- [ ] **Step 1: Replace the README Phase 2 section**

In `README.md`, replace the entire `## Phase 2 (deferred)` section with:

```markdown
## MCP server

A stdio FastMCP server (`gmail-ai-mcp`) exposes the four capabilities as native
MCP tools alongside the official connector. It exposes seven tools --
`download_attachment`, `get_raw_message`, `list_filters`, `get_filter`,
`create_draft`, `create_filter`, `delete_filter` -- and **deliberately omits
`send_draft`**: transmitting mail stays a terminal-only `draft send --yes` act.

Binary reads (`download_attachment`, `get_raw_message`) write bytes to an
agent-supplied `out` path and return `{path, bytes_written}`; raw email bytes
never enter the model context.

Register it with your MCP host, e.g.:

```bash
claude mcp add --scope user gmail-ai-broker \
  uv run --directory /abs/path/to/gmail-ai-broker gmail-ai-mcp
```

Config is loaded exactly like the CLI (XDG default), or point at a specific
config with the `GMAIL_AI_BROKER_CONFIG` environment variable in the launch
command. Complete the one-time setup runbook above before registering.
```

- [ ] **Step 2: Update the CLAUDE.md Phase 2 section**

In `CLAUDE.md`, replace the `## Phase 2 (deferred)` section with:

```markdown
## MCP server (Phase 2, built)

`src/gmail_ai_mcp/` is a stdio FastMCP server over `client.py`. `tools.py` holds
the testable broker-mapping helpers (unit-tested in `tests/test_mcp_tools.py`);
`server.py` holds the FastMCP wrappers + `main()` (glue). `fastmcp` is a core
dependency (chosen for an all-in-one install, despite the audit-surface cost).

It exposes seven tools and **never** `send_draft` -- the same one-transmit-path
invariant as the CLI, guarded structurally by `tests/test_mcp_server.py`. Any
new broker capability that should be reachable over MCP needs: a `tool_*` helper
in `tools.py` (with a test), a typed `@mcp.tool` wrapper in `server.py`, and an
entry in `EXPECTED_TOOLS`. Never add a send/transmit wrapper.
```

- [ ] **Step 3: Verify no stale "deferred" claims remain**

Run: `grep -rn "deferred\|not built\|NOT added yet\|Phase 2" README.md CLAUDE.md pyproject.toml`
Expected: the only remaining hits are the historical note in `pyproject.toml` comments (leave those, or update the comment to say fastmcp is now a core dep). No remaining claim that the MCP server is unbuilt in README.md/CLAUDE.md.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "Document the built MCP server; retire Phase 2 deferral"
```

---

## Done criteria

- `uv run --extra dev pytest -q` passes (existing suite + `test_mcp_tools.py` + `test_mcp_server.py`).
- `uv run gmail-ai-mcp` starts a stdio server (will block waiting for an MCP client -- Ctrl-C to exit; real verification is registering it with a host and calling `list_filters`, the read-only Gate-1 equivalent).
- No `send_draft`/`send` tool is exposed (`test_mcp_server.py::test_send_is_never_exposed`).
- README and CLAUDE.md describe the server as built; no "deferred" claim remains.
```
