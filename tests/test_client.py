"""Tests for GmailBroker -- the API wrapper.

The Gmail service is an external boundary, so it is faked with MagicMock. We
assert real behavior: payload decoding, correct endpoint parameters, and that
every mutation writes an audit record.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock

from gmail_ai_broker.client import GmailBroker
from gmail_ai_broker.models import FilterSpec


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _audit_lines(log):
    return [json.loads(x) for x in log.read_text().strip().splitlines()] if log.exists() else []


def test_download_attachment_decodes_data(tmp_path):
    svc = MagicMock()
    svc.users.return_value.messages.return_value.attachments.return_value.get.return_value.execute.return_value = {
        "data": _b64(b"PDF-bytes")
    }
    broker = GmailBroker(svc, audit_log=tmp_path / "a.jsonl")
    assert broker.download_attachment("m1", "att1") == b"PDF-bytes"
    svc.users.return_value.messages.return_value.attachments.return_value.get.assert_called_once_with(
        userId="me", messageId="m1", id="att1"
    )


def test_get_raw_message_decodes_raw_field(tmp_path):
    svc = MagicMock()
    svc.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "raw": _b64(b"From: a@b.com\r\n\r\nhi")
    }
    broker = GmailBroker(svc, audit_log=tmp_path / "a.jsonl")
    assert broker.get_raw_message("m9") == b"From: a@b.com\r\n\r\nhi"
    svc.users.return_value.messages.return_value.get.assert_called_once_with(
        userId="me", id="m9", format="raw"
    )


def test_list_filters_returns_list_and_defaults_empty(tmp_path):
    svc = MagicMock()
    svc.users.return_value.settings.return_value.filters.return_value.list.return_value.execute.return_value = {
        "filter": [{"id": "f1"}, {"id": "f2"}]
    }
    broker = GmailBroker(svc, audit_log=tmp_path / "a.jsonl")
    assert broker.list_filters() == [{"id": "f1"}, {"id": "f2"}]

    svc.users.return_value.settings.return_value.filters.return_value.list.return_value.execute.return_value = {}
    assert broker.list_filters() == []


def test_reads_do_not_write_audit(tmp_path):
    log = tmp_path / "a.jsonl"
    svc = MagicMock()
    svc.users.return_value.messages.return_value.get.return_value.execute.return_value = {"raw": _b64(b"x")}
    broker = GmailBroker(svc, audit_log=log)
    broker.get_raw_message("m1")
    assert _audit_lines(log) == []


def test_create_draft_builds_raw_and_audits(tmp_path):
    log = tmp_path / "a.jsonl"
    svc = MagicMock()
    svc.users.return_value.drafts.return_value.create.return_value.execute.return_value = {"id": "d1"}
    broker = GmailBroker(svc, audit_log=log)

    res = broker.create_draft(to="r@example.com", subject="Hi", body="body")
    assert res == {"id": "d1"}

    # The draft body must carry a raw MIME string.
    _, kwargs = svc.users.return_value.drafts.return_value.create.call_args
    assert kwargs["userId"] == "me"
    assert "raw" in kwargs["body"]["message"]
    assert isinstance(kwargs["body"]["message"]["raw"], str)

    lines = _audit_lines(log)
    assert len(lines) == 1
    assert lines[0]["action"] == "draft.create"
    assert lines[0]["result"] == {"draft_id": "d1"}


def test_send_draft_audits(tmp_path):
    log = tmp_path / "a.jsonl"
    svc = MagicMock()
    svc.users.return_value.drafts.return_value.send.return_value.execute.return_value = {
        "id": "sent1",
        "labelIds": ["SENT"],
    }
    broker = GmailBroker(svc, audit_log=log)
    broker.send_draft("d1")
    svc.users.return_value.drafts.return_value.send.assert_called_once_with(
        userId="me", body={"id": "d1"}
    )
    lines = _audit_lines(log)
    assert len(lines) == 1
    assert lines[0]["action"] == "draft.send"
    assert lines[0]["result"]["message_id"] == "sent1"


def test_create_filter_sends_resource_and_audits(tmp_path):
    log = tmp_path / "a.jsonl"
    svc = MagicMock()
    svc.users.return_value.settings.return_value.filters.return_value.create.return_value.execute.return_value = {
        "id": "f99"
    }
    broker = GmailBroker(svc, audit_log=log)
    spec = FilterSpec.model_validate(
        {"criteria": {"from": "billing@example.com"}, "action": {"add_label_ids": ["L1"]}}
    )
    broker.create_filter(spec)
    _, kwargs = svc.users.return_value.settings.return_value.filters.return_value.create.call_args
    assert kwargs["body"] == {"criteria": {"from": "billing@example.com"}, "action": {"addLabelIds": ["L1"]}}
    lines = _audit_lines(log)
    assert lines[0]["action"] == "filter.create"
    assert lines[0]["result"] == {"filter_id": "f99"}


def test_delete_filter_audits(tmp_path):
    log = tmp_path / "a.jsonl"
    svc = MagicMock()
    broker = GmailBroker(svc, audit_log=log)
    broker.delete_filter("f99")
    svc.users.return_value.settings.return_value.filters.return_value.delete.assert_called_once_with(
        userId="me", id="f99"
    )
    lines = _audit_lines(log)
    assert lines[0]["action"] == "filter.delete"
    assert lines[0]["args_hash"]
