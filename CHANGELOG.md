# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project scaffold: uv package (src layout), typer CLI entrypoint, locked dependencies.
- Hardened `.gitignore` blocking tokens, OAuth client secrets, and audit logs from version control.

### Security
- Read-safe-by-default design: the only mail-transmitting command is an explicit `draft send`; no delete/archive/bulk verbs in v1.
