# gmail-ai-broker

Small, auditable CLI that fills the four gaps the official claude.ai Gmail
connector leaves open, so Claude can act as a real email assistant:

| Capability | Why the official connector can't | Command |
|---|---|---|
| Download attachments | connector exposes no attachment bytes | `attachment download` |
| Send raw MIME w/ attachments | connector can't attach files / send raw | `draft create --attach` then `draft send` |
| Filter CRUD | needs `gmail.settings.basic` scope | `filter list/get/create/delete` |
| Raw message fetch | connector renders, doesn't expose `raw` | `message get-raw` |

Keep the official connector for reads/triage; this tool adds **only** the
missing writes. It is intentionally small enough to read end-to-end -- that
auditability is the trust model.

## Security model (read this)

- **Read-safe by default.** The only command that transmits mail is
  `draft send <id> --yes`. Everything outbound is staged as a draft you review.
  There are no delete/archive/bulk verbs in v1.
- **The token is the crown jewel.** Auth is OAuth; the agent never holds a
  durable credential. A refresh token lives in a mode-600 file
  (`~/.secrets/.gmail-refresh-token`), and google-auth exchanges it for a
  short-lived access token per call. Back the token up in your password
  manager.
- **Scopes are mailbox-wide.** This tool requests `gmail.modify` +
  `gmail.settings.basic`. **There is no per-label OAuth scoping in Gmail** --
  `gmail.modify` legally grants whole-mailbox read/write. Any "only touch label
  X" behavior would be enforced by *our code*, not by Google. Treat the token
  accordingly.
- **Every mutation is audited.** Draft create, draft send, and filter
  create/delete each append a line to an append-only JSONL log
  (`~/.local/state/gmail-ai-broker/audit.jsonl`). Call args are *hashed*, not
  stored verbatim, so recipient/subject content is not persisted.
- **Untrusted content stays data.** The CLI emits attachment/raw bytes to files
  or stdout and never acts on email content as instructions. (Indirect prompt
  injection -- e.g. EchoLeak / CVE-2025-32711 -- is a real, in-the-wild threat
  for email agents. The defense lives at the agent layer; this CLI simply never
  auto-acts.)

## Install (dev)

```bash
uv sync                      # runtime deps
uv sync --extra dev          # + pytest
uv run gmail-ai-broker --help
uv run --extra dev pytest -q # full suite
```

## One-time setup runbook

You only do this once. Steps 2-3 are **Console-manual** -- Google exposes no API
(and no Terraform resource) for creating a Gmail user-consent Desktop OAuth
client.

### 1. Enable the Gmail API ($0)

In any Google Cloud project you own (create one free if needed):

```bash
gcloud services enable gmail.googleapis.com --project <your-project-id>
```

### 2. Configure the OAuth consent screen

Google Cloud Console -> **APIs & Services -> OAuth consent screen**:

- User type: **External** (required for a personal @gmail.com account).
- Fill app name, your support email, developer email.
- Add scopes: `https://www.googleapis.com/auth/gmail.modify` and
  `https://www.googleapis.com/auth/gmail.settings.basic`.
- **Publishing status: click "Publish app" -> move to "In production".** Accept
  the "unverified app" warning. As the sole user you can run it unverified
  indefinitely. **This step matters:** an app left in "Testing" expires its
  refresh token every 7 days; "In production" makes the token persist.

### 3. Create a Desktop OAuth client

Console -> **APIs & Services -> Credentials -> Create credentials -> OAuth
client ID**:

- Application type: **Desktop app**. Name it (e.g. `gmail-ai-broker`).
- Create, then **Download JSON** (contains `client_id` + `client_secret`).
  For a Desktop app the "secret" is not truly secret, but Google still needs it
  to refresh.

### 4. Write the config

`~/.config/gmail-ai-broker/config.toml`:

```toml
client_id = "XXXX.apps.googleusercontent.com"
client_secret = "YYYY"
# Optional overrides (defaults shown):
# refresh_token_path = "~/.secrets/.gmail-refresh-token"
# audit_log_path = "~/.local/state/gmail-ai-broker/audit.jsonl"
```

### 5. Authorize and capture the refresh token

```bash
uv run gmail-ai-broker auth login --client-secrets ~/Downloads/client_secret_XXXX.json
```

A browser opens; approve the two scopes. The refresh token is written to
`~/.secrets/.gmail-refresh-token` (mode 600). **Back it up** in your password
manager.

Verify:

```bash
uv run gmail-ai-broker auth status
uv run gmail-ai-broker filter list      # Gate 1: proves the token + scopes work
```

## Usage

```bash
# Read a message's full raw MIME (to a file or stdout)
gmail-ai-broker message get-raw <message-id> --out msg.eml

# Download an attachment
gmail-ai-broker attachment download <message-id> <attachment-id> --out form.pdf

# Stage a reply with an attachment (does NOT send)
gmail-ai-broker draft create \
  --to someone@example.com --subject "Re: your request" \
  --body-file reply.txt --attach completed-form.pdf \
  --in-reply-to "<original-message-id@mail.gmail.com>"

# Review the draft in Gmail, then -- and only then -- send it:
gmail-ai-broker draft send <draft-id> --yes

# Filters
gmail-ai-broker filter list
gmail-ai-broker filter create --spec my-filter.toml
gmail-ai-broker filter delete <filter-id>
```

### Filter spec file

A reviewed declarative spec (`.toml` or `.json`). Example `my-filter.toml`:

```toml
[criteria]
from = "billing@example.com"
# to, subject, query, has_attachment also supported

[action]
add_label_ids = ["Label_42"]
# remove_label_ids, forward also supported
```

Label *IDs* (not names) -- list them with `filter list` or the official
connector's `list_labels`.

## Audit log

Append-only JSONL, one record per mutation:

```json
{"timestamp":"2026-05-28T...","action":"draft.send","args_hash":"...","result":{"message_id":"...","label_ids":["SENT"]}}
```

## Architecture

```
auth.py     token load/save (mode 600), credential build, loopback flow
config.py   TOML config + path defaults
mime.py     raw MIME build (attachments) + attachment decode  [pure]
models.py   declarative FilterSpec -> Gmail filter resource    [pure]
audit.py    append-only JSONL mutation log                     [pure]
client.py   GmailBroker: the four capabilities, wired together
service.py  googleapiclient discovery build                    [glue]
cli/main.py typer entrypoint
```

## MCP server

A stdio FastMCP server (`gmail-ai-mcp`) exposes the broker's capabilities as
native MCP tools alongside the official connector. It exposes seven tools --
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
