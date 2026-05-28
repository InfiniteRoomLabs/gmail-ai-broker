"""Declarative, user-approved filter spec -> Gmail filter resource.

Filters are the one mutation that defines standing inbox policy, so they are
expressed as a declarative spec (a file the user reviews) rather than imperative
API calls. ``FilterSpec.to_gmail_resource()`` produces the exact dict the Gmail
API ``users.settings.filters.create`` endpoint expects.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FilterCriteria(BaseModel):
    """Matching criteria. Snake_case in the spec; camelCase to the API."""

    model_config = ConfigDict(populate_by_name=True)

    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    subject: str | None = None
    query: str | None = None
    has_attachment: bool | None = None

    def to_gmail(self) -> dict:
        out: dict = {}
        if self.from_ is not None:
            out["from"] = self.from_
        if self.to is not None:
            out["to"] = self.to
        if self.subject is not None:
            out["subject"] = self.subject
        if self.query is not None:
            out["query"] = self.query
        if self.has_attachment is not None:
            out["hasAttachment"] = self.has_attachment
        return out


class FilterAction(BaseModel):
    """Actions to apply. v1 stays non-destructive (label/forward only)."""

    add_label_ids: list[str] | None = None
    remove_label_ids: list[str] | None = None
    forward: str | None = None

    def to_gmail(self) -> dict:
        out: dict = {}
        if self.add_label_ids:
            out["addLabelIds"] = self.add_label_ids
        if self.remove_label_ids:
            out["removeLabelIds"] = self.remove_label_ids
        if self.forward is not None:
            out["forward"] = self.forward
        return out


class FilterSpec(BaseModel):
    criteria: FilterCriteria
    action: FilterAction

    @model_validator(mode="after")
    def _require_non_empty(self) -> "FilterSpec":
        if not self.criteria.to_gmail():
            raise ValueError("filter criteria must specify at least one condition")
        if not self.action.to_gmail():
            raise ValueError("filter action must specify at least one effect")
        return self

    def to_gmail_resource(self) -> dict:
        return {"criteria": self.criteria.to_gmail(), "action": self.action.to_gmail()}
