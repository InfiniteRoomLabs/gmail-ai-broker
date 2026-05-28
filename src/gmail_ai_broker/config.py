"""Configuration loading.

Non-secret settings (OAuth client id/secret, file locations) live in a TOML
config under XDG config dir. The refresh token itself is NOT here -- it lives in
its own mode-600 file (default ~/.secrets/.gmail-refresh-token).

Note: for a Desktop/installed OAuth app, the "client_secret" is not truly
secret (installed apps cannot keep secrets); Google still requires it to refresh.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path("~/.config/gmail-ai-broker/config.toml").expanduser()
DEFAULT_REFRESH_TOKEN_PATH = Path("~/.secrets/.gmail-refresh-token").expanduser()
DEFAULT_AUDIT_LOG_PATH = Path(
    "~/.local/state/gmail-ai-broker/audit.jsonl"
).expanduser()


class Config(BaseModel):
    client_id: str
    client_secret: str
    refresh_token_path: Path = Field(default=DEFAULT_REFRESH_TOKEN_PATH)
    audit_log_path: Path = Field(default=DEFAULT_AUDIT_LOG_PATH)

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "Config":
        path = Path(path)
        try:
            raw = path.read_bytes()
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Config not found at {path}. Create it with at least client_id "
                "and client_secret (see README setup runbook)."
            ) from exc
        data = tomllib.loads(raw.decode("utf-8"))
        cfg = cls.model_validate(data)
        # Expand ~ in any user-supplied paths.
        cfg.refresh_token_path = cfg.refresh_token_path.expanduser()
        cfg.audit_log_path = cfg.audit_log_path.expanduser()
        return cfg
