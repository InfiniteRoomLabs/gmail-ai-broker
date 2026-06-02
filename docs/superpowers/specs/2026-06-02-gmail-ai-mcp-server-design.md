# gmail-ai-mcp server -- design

**Date:** 2026-06-02
**Status:** approved, pending implementation plan
**Feature:** Phase 2 MCP wrapper over `GmailBroker`

## Goal

Expose seven of `GmailBroker`'s eight methods as MCP tools over stdio, so Claude
can call the connector gap-fillers as native tools alongside the official Gmail
connector. The eighth method, `send_draft`, is deliberately never exposed:
transmission stays a terminal-only, human-typed `draft send --yes` act.

## Non-goals

- No `send_draft` tool, and no other transmit verb. The server has no way to
  send mail, by design -- the same "nothing to auto-act with" defense the CLI
  uses against indirect prompt injection.
- No new mutation logic. The server is glue; all audit/MIME/validation logic
  stays in the existing pure + client modules, unchanged.
- No HTTP/SSE transport. Stdio only.

## Known cost (accepted)

The README and `pyproject.toml` deliberately avoid `fastmcp` because it drags in
uvicorn/starlette/websockets and bloats the audit surface. This design overrides
that decision: `fastmcp` is added as a **core** dependency, so every install --
including plain-CLI users -- pulls that tree. This was chosen with the tradeoff
explicit. If the bloat proves unwelcome, the fallback is to move `fastmcp` to an
optional `mcp` extra (the server package boundary already supports that with no
code change).

## Tools

Seven tools, one per exposed `GmailBroker` method:

| Tool | Broker method | Kind | Audited |
|---|---|---|---|
| `download_attachment` | `download_attachment` | read | no |
| `get_raw_message` | `get_raw_message` | read | no |
| `list_filters` | `list_filters` | read | no |
| `get_filter` | `get_filter` | read | no |
| `create_draft` | `create_draft` | mutation | yes (in client) |
| `create_filter` | `create_filter` | mutation | yes (in client) |
| `delete_filter` | `delete_filter` | mutation | yes (in client) |

`send_draft` is absent.

## Tool I/O

### Binary reads write to disk, never inline bytes

`download_attachment` and `get_raw_message` both take an agent-supplied `out`
file path, write the bytes there, and return `{"path": str, "bytes_written":
int}`. Raw/attachment bytes are never returned into the model's context. This
mirrors the CLI's file-emit model and keeps untrusted email content as data on
disk -- it is never surfaced to the agent as text it might treat as
instructions.

`get_raw_message` uses the same file-write treatment as `download_attachment`
(not a returned text string), for consistency and to keep raw MIME out of the
model context by default.

- `download_attachment(message_id: str, attachment_id: str, out: str) -> {path, bytes_written}`
- `get_raw_message(message_id: str, out: str) -> {path, bytes_written}`

### Filter reads return JSON

- `list_filters() -> list[dict]`
- `get_filter(filter_id: str) -> dict`

Gmail filter resources are small structured JSON; safe and useful to return
directly.

### create_draft: body string, attachment paths

- `create_draft(to: str, subject: str, body: str, attachments: list[str] | None = None, in_reply_to: str | None = None, cc: str | None = None) -> dict`

`body` is a plain string (natural for an agent that composes text).
`attachments` are local file paths the agent has already written. Direct
passthrough to `GmailBroker.create_draft`. Returns the draft resource
(`{"id": ...}`). The draft is staged, not sent.

### create_filter: spec object validated by existing model

- `create_filter(spec: dict) -> dict` -- `spec` is a JSON object passed to the
  existing `FilterSpec.model_validate`, reusing the pydantic model. Returns the
  created filter resource.
- `delete_filter(filter_id: str) -> None`

## Architecture

New package `src/gmail_ai_mcp/` with `server.py`. The server:

1. Builds one `GmailBroker` via `GmailBroker.from_config()`.
2. Registers seven `@mcp.tool` functions, each a thin wrapper that maps tool
   args to a broker call and shapes the return value.
3. Runs over stdio via `main()`.

```
src/gmail_ai_mcp/
  __init__.py
  server.py        # FastMCP instance, 7 tools, main() stdio entrypoint
```

`pyproject.toml` changes:

- Add `fastmcp` to `[project.dependencies]`.
- Add script entry: `gmail-ai-mcp = "gmail_ai_mcp.server:main"`.

The server imports `GmailBroker`, `FilterSpec`, and config helpers from the
existing `gmail_ai_broker` package. It adds no logic those modules don't already
own.

### Config

The server has no CLI flags. It loads config the same way the CLI does
(`GmailBroker.from_config()` -> XDG default path). An optional
`GMAIL_AI_BROKER_CONFIG` environment variable overrides the config path, so the
MCP host launch command can point at a non-default config.

## Tool naming

Plain names (`download_attachment`, `create_draft`, etc.). The official Gmail
connector exposes reads (`search_threads`, `get_thread`, `list_labels`); none
collide with this server's verb set, so no prefix is needed.

## Invariants preserved

- **One transmit path.** No `send_draft` tool; the server cannot send mail.
- **Audit on every mutation.** Audit records still fire inside `client.py`
  (`draft.create`, `filter.create`, `filter.delete`). The server adds none and
  removes none.
- **Email content stays data.** Binary reads land on disk; raw bytes never enter
  the model context.
- **Pure/glue split.** The server is glue. No business logic leaks into it.

## Error handling

Each tool wraps its broker call. Google API errors (`HttpError`) and validation
errors (`pydantic.ValidationError` from `create_filter`) propagate as MCP tool
errors with a readable message. Missing config / refresh token surfaces the same
`RuntimeError` the CLI raises, as a tool error -- the fix is the one-time setup
runbook, identical to the CLI.

## Testing

The tool layer is unit-tested with a mocked `GmailBroker`, mirroring the
existing `tests/test_client.py` mock pattern. Tests lock:

- the `dict -> FilterSpec` mapping in `create_filter`,
- the bytes -> file write behavior and return shape of the two binary reads,
- the argument passthrough of `create_draft`,
- the absence of any `send` tool (assert no tool named `send_draft` is
  registered).

Live wiring (`from_config`, googleapiclient discovery, real OAuth) stays
Gate-1-only, consistent with the repo's "glue is exercised end-to-end, not
mocked" convention.

## MCP host registration (operator step, documented not coded)

After `uv sync`, register the stdio server, e.g.:

```
claude mcp add --scope user gmail-ai-broker \
  uv run --directory /path/to/gmail-ai-broker gmail-ai-mcp
```

This is documented in the README Phase 2 section; it is not part of the code
deliverable.
