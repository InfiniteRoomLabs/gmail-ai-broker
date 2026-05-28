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
- 33 unit tests (TDD) across MIME, audit, models, auth, config, client, and CLI.

### Security
- Read-safe-by-default design: the only mail-transmitting command is an explicit `draft send --yes`; no delete/archive/bulk verbs in v1.
- Audit log hashes call args rather than storing recipient/subject content verbatim.
