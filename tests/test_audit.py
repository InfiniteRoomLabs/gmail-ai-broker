"""Tests for the append-only JSONL mutation audit log."""

from __future__ import annotations

import json

from gmail_ai_broker.audit import record_mutation


def test_record_mutation_writes_expected_fields(tmp_path):
    log = tmp_path / "audit.jsonl"
    rec = record_mutation(
        action="draft.create",
        args={"to": "r@example.com", "subject": "Hi"},
        result={"draft_id": "d123"},
        log_path=log,
        timestamp="2026-05-28T00:00:00+00:00",
    )
    assert rec["action"] == "draft.create"
    assert rec["result"] == {"draft_id": "d123"}
    assert rec["timestamp"] == "2026-05-28T00:00:00+00:00"
    assert isinstance(rec["args_hash"], str) and len(rec["args_hash"]) > 0

    line = log.read_text().strip()
    assert json.loads(line) == rec


def test_record_mutation_is_append_only(tmp_path):
    log = tmp_path / "audit.jsonl"
    record_mutation(action="filter.create", args={"a": 1}, result={"id": "f1"}, log_path=log)
    record_mutation(action="filter.delete", args={"id": "f1"}, result=None, log_path=log)
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["action"] == "filter.create"
    assert json.loads(lines[1])["action"] == "filter.delete"


def test_args_hash_is_order_independent(tmp_path):
    log = tmp_path / "audit.jsonl"
    a = record_mutation(action="x", args={"a": 1, "b": 2}, result=None, log_path=log)
    b = record_mutation(action="x", args={"b": 2, "a": 1}, result=None, log_path=log)
    assert a["args_hash"] == b["args_hash"]


def test_record_mutation_creates_parent_dir(tmp_path):
    log = tmp_path / "nested" / "dir" / "audit.jsonl"
    record_mutation(action="x", args={}, result=None, log_path=log)
    assert log.exists()
