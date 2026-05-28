# gmail-ai-broker

Small, auditable CLI that fills the four gaps the official claude.ai Gmail
connector leaves open, so Claude can act as a real email assistant:

1. **Attachment download** -- read the PDFs the connector can't.
2. **Raw-MIME send with attachments** -- return completed forms.
3. **Filter CRUD** -- manage standing inbox policy (requires `gmail.settings.basic`).
4. **Raw message fetch** (`format=raw`) -- full MIME when the connector renders incompletely.

Keep the official connector for reads/triage; this tool only adds the missing writes.

**Read-safe by default.** The only path that ever transmits mail is an explicit
`gmail-ai-broker draft send <id>` -- everything else stages drafts. No
delete/archive/bulk verbs in v1.

> Status: in development. Setup runbook (OAuth Desktop client, consent, token
> capture) and the honest threat model are added in a later commit. Design lives
> in the approved plan.

## Quick start (dev)

```bash
uv sync
uv run gmail-ai-broker --help
```
