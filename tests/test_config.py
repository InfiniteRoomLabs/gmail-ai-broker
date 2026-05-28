"""Tests for config loading + path defaults."""

from __future__ import annotations

import pytest

from gmail_ai_broker.config import Config


def test_load_minimal_applies_path_defaults(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        'client_id = "cid.apps.googleusercontent.com"\n'
        'client_secret = "secret"\n'
    )
    cfg = Config.load(cfg_file)
    assert cfg.client_id == "cid.apps.googleusercontent.com"
    assert cfg.client_secret == "secret"
    # Defaults are absolute and land in the expected locations.
    assert cfg.refresh_token_path.is_absolute()
    assert cfg.refresh_token_path.name == ".gmail-refresh-token"
    assert cfg.audit_log_path.name == "audit.jsonl"


def test_load_respects_overrides(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        'client_id = "c"\n'
        'client_secret = "s"\n'
        f'refresh_token_path = "{tmp_path / "tok"}"\n'
        f'audit_log_path = "{tmp_path / "audit.jsonl"}"\n'
    )
    cfg = Config.load(cfg_file)
    assert cfg.refresh_token_path == tmp_path / "tok"
    assert cfg.audit_log_path == tmp_path / "audit.jsonl"


def test_missing_required_field_raises(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('client_secret = "s"\n')  # no client_id
    with pytest.raises(Exception):
        Config.load(cfg_file)


def test_missing_config_file_raises_helpful_error(tmp_path):
    missing = tmp_path / "nope.toml"
    with pytest.raises(RuntimeError, match=str(missing)):
        Config.load(missing)
