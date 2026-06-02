# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project scaffold: uv package (src layout), typer CLI entrypoint, locked dependencies.
- Hardened `.gitignore` blocking tokens, OAuth client secrets, and audit logs from version control.
- OAuth token loading (`auth.py`) and credential construction for `gmail.modify` + `gmail.settings.basic`.
- Raw MIME building with attachments + attachment decoding (`mime.py`).
- Declarative, validated filter spec -> Gmail filter resource (`models.py`).
- `GmailBroker` (`client.py`): attachment download, raw message fetch, draft create (with attachments), draft send, and filter list/get/create/delete.
- Append-only JSONL audit log for every mutation (`audit.py`).
- TOML config loading with path defaults (`config.py`); `GmailBroker.from_config` wiring.
- Typer CLI exposing `attachment`, `message`, `draft`, and `filter` command groups.
- `auth login` (loopback OAuth consent -> refresh token saved mode-600) and `auth status` commands; `save_refresh_token` + `run_installed_app_flow` in `auth.py`.
- README with the full one-time setup runbook (enable API, consent screen, Production-unverified publish to dodge the 7-day token expiry, Desktop client, `auth login`) and an honest security/threat-model section.
- MCP server (`gmail_ai_mcp`, Phase 2): stdio FastMCP server exposing seven of the eight `GmailBroker` capabilities as native MCP tools, plus a `gmail-ai-mcp` console script. `tools.py` holds the testable broker-mapping helpers; `server.py` holds the FastMCP wrappers + `main()` (glue). `fastmcp` added as a core dependency for an all-in-one install. Lazy thread-safe broker construction; config path overridable via `GMAIL_AI_BROKER_CONFIG`.
- `CLAUDE.md` documenting commands, the pure/glue architecture split, and the project invariants.
- 49 unit tests total (TDD); added MCP tool-helper and server tests.

### Changed
- README "Phase 2 (deferred)" section replaced with built-MCP-server usage + registration instructions.

### Fixed
- `run_installed_app_flow` return type: `flow.run_local_server` is typed as a union (`oauth2 | external_account`); narrow to the oauth2 `Credentials` an installed-app flow actually yields via `cast`.
- Added `pyrightconfig.json` pointing at the uv `.venv` so pyright resolves `google.*`/`typer`/`pydantic` and actually type-checks lib usage (without it, unresolved imports silently disabled type-checking). Guarded a `creds.scopes` Optional in `test_auth.py`. `pyright`: 0 errors, 0 warnings.

### Security
- Read-safe-by-default design: the only mail-transmitting command is an explicit `draft send --yes`; no delete/archive/bulk verbs in v1.
- Audit log hashes call args rather than storing recipient/subject content verbatim.
- MCP server enables zero outbound mail flow: `send_draft` is never exposed (guarded by a registry-level test asserting the exact tool set), and `create_filter` rejects `forward` actions at the MCP layer (the CLI keeps full forward capability). MCP binary reads write bytes to disk and never inline raw email content into the model context.
