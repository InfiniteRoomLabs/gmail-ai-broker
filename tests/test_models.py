"""Tests for the declarative filter spec model (pure validation/serialization)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gmail_ai_broker.models import FilterSpec


def test_filter_spec_to_gmail_resource_maps_to_camelcase_and_omits_empty():
    spec = FilterSpec.model_validate(
        {
            "criteria": {"from": "billing@example.com", "subject": "disability"},
            "action": {"add_label_ids": ["Label_42"]},
        }
    )
    resource = spec.to_gmail_resource()
    assert resource == {
        "criteria": {"from": "billing@example.com", "subject": "disability"},
        "action": {"addLabelIds": ["Label_42"]},
    }


def test_has_attachment_serializes_as_camelcase_bool():
    spec = FilterSpec.model_validate(
        {
            "criteria": {"query": "has:attachment", "has_attachment": True},
            "action": {"add_label_ids": ["L1"]},
        }
    )
    resource = spec.to_gmail_resource()
    assert resource["criteria"]["hasAttachment"] is True
    assert resource["criteria"]["query"] == "has:attachment"


def test_empty_criteria_is_rejected():
    with pytest.raises(ValidationError):
        FilterSpec.model_validate(
            {"criteria": {}, "action": {"add_label_ids": ["L1"]}}
        )


def test_empty_action_is_rejected():
    with pytest.raises(ValidationError):
        FilterSpec.model_validate(
            {"criteria": {"from": "a@b.com"}, "action": {}}
        )
