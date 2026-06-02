"""Unit tests for the MCP tool helpers.

The helpers sit one layer above GmailBroker, so the broker is mocked. We assert
the real behavior the MCP layer owns: byte reads land on disk (never returned
inline), dict specs become FilterSpec, and draft args pass through verbatim.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from gmail_ai_broker.models import FilterSpec
from gmail_ai_mcp import tools


def test_download_attachment_writes_file_and_returns_summary(tmp_path):
    broker = MagicMock()
    broker.download_attachment.return_value = b"PDF-bytes"
    out = tmp_path / "form.pdf"

    result = tools.tool_download_attachment(broker, "m1", "att1", str(out))

    assert out.read_bytes() == b"PDF-bytes"
    assert result == {"path": str(out), "bytes_written": 9}
    broker.download_attachment.assert_called_once_with("m1", "att1")


def test_download_attachment_creates_missing_parent_dirs(tmp_path):
    broker = MagicMock()
    broker.download_attachment.return_value = b"PDF-bytes"
    out = tmp_path / "sub" / "form.pdf"

    result = tools.tool_download_attachment(broker, "m1", "att1", str(out))

    assert out.exists()
    assert out.read_bytes() == b"PDF-bytes"
    assert result == {"path": str(out), "bytes_written": 9}


def test_get_raw_message_writes_file_and_returns_summary(tmp_path):
    broker = MagicMock()
    broker.get_raw_message.return_value = b"From: a@b.com\r\n\r\nhi"
    out = tmp_path / "msg.eml"

    result = tools.tool_get_raw_message(broker, "m9", str(out))

    assert out.read_bytes() == b"From: a@b.com\r\n\r\nhi"
    assert result == {"path": str(out), "bytes_written": 19}
    broker.get_raw_message.assert_called_once_with("m9")


def test_get_raw_message_creates_missing_parent_dirs(tmp_path):
    broker = MagicMock()
    broker.get_raw_message.return_value = b"data"
    out = tmp_path / "sub" / "msg.eml"
    result = tools.tool_get_raw_message(broker, "m1", str(out))
    assert out.exists()
    assert result == {"path": str(out), "bytes_written": 4}


def test_list_filters_passes_through():
    broker = MagicMock()
    broker.list_filters.return_value = [{"id": "f1"}, {"id": "f2"}]
    assert tools.tool_list_filters(broker) == [{"id": "f1"}, {"id": "f2"}]
    broker.list_filters.assert_called_once_with()


def test_get_filter_passes_through():
    broker = MagicMock()
    broker.get_filter.return_value = {"id": "f1"}
    assert tools.tool_get_filter(broker, "f1") == {"id": "f1"}
    broker.get_filter.assert_called_once_with("f1")


def test_create_draft_passes_all_args():
    broker = MagicMock()
    broker.create_draft.return_value = {"id": "d1"}

    result = tools.tool_create_draft(
        broker,
        to="r@example.com",
        subject="Hi",
        body="hello",
        attachments=["/tmp/a.pdf"],
        in_reply_to="<x@mail>",
        cc="c@example.com",
    )

    assert result == {"id": "d1"}
    broker.create_draft.assert_called_once_with(
        to="r@example.com",
        subject="Hi",
        body="hello",
        attachments=["/tmp/a.pdf"],
        in_reply_to="<x@mail>",
        cc="c@example.com",
    )


def test_create_filter_validates_dict_into_filterspec():
    broker = MagicMock()
    broker.create_filter.return_value = {"id": "f99"}

    result = tools.tool_create_filter(
        broker, {"criteria": {"from": "billing@example.com"}, "action": {"add_label_ids": ["L1"]}}
    )

    assert result == {"id": "f99"}
    (spec,), _ = broker.create_filter.call_args
    assert isinstance(spec, FilterSpec)
    assert spec.to_gmail_resource() == {
        "criteria": {"from": "billing@example.com"},
        "action": {"addLabelIds": ["L1"]},
    }


def test_create_filter_rejects_empty_spec():
    broker = MagicMock()
    with pytest.raises(ValidationError):
        tools.tool_create_filter(broker, {"criteria": {}, "action": {}})
    broker.create_filter.assert_not_called()


def test_delete_filter_returns_confirmation():
    broker = MagicMock()
    broker.delete_filter.return_value = None
    assert tools.tool_delete_filter(broker, "f99") == {"deleted": "f99"}
    broker.delete_filter.assert_called_once_with("f99")
