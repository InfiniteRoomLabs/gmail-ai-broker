"""GmailBroker: the thin, auditable wrapper over the Gmail API.

Exposes exactly the four capabilities the official connector lacks. Reads are
side-effect-free; the three mutations (draft create, draft send, filter
create/delete) each append an audit record. Sending mail is split out as its
own ``send_draft`` call so transmission is always an explicit, separate act.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gmail_ai_broker.audit import record_mutation
from gmail_ai_broker.mime import build_raw_message, decode_attachment_data
from gmail_ai_broker.models import FilterSpec

USER = "me"


class GmailBroker:
    def __init__(self, service: Any, *, audit_log: Path) -> None:
        self._svc = service
        self._audit_log = Path(audit_log)

    @classmethod
    def from_config(cls, config_path: Path | None = None) -> "GmailBroker":
        """Wire config -> refresh token -> credentials -> service -> broker.

        Network glue; exercised at Gate 1 rather than in unit tests.
        """
        from gmail_ai_broker.auth import (
            GMAIL_SCOPES,
            build_credentials,
            load_refresh_token,
        )
        from gmail_ai_broker.config import DEFAULT_CONFIG_PATH, Config
        from gmail_ai_broker.service import build_gmail_service

        cfg = Config.load(config_path or DEFAULT_CONFIG_PATH)
        creds = build_credentials(
            refresh_token=load_refresh_token(cfg.refresh_token_path),
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
            scopes=GMAIL_SCOPES,
        )
        return cls(build_gmail_service(creds), audit_log=cfg.audit_log_path)

    # ----- reads (no audit) -------------------------------------------------

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        resp = (
            self._svc.users()
            .messages()
            .attachments()
            .get(userId=USER, messageId=message_id, id=attachment_id)
            .execute()
        )
        return decode_attachment_data(resp["data"])

    def get_raw_message(self, message_id: str) -> bytes:
        resp = (
            self._svc.users()
            .messages()
            .get(userId=USER, id=message_id, format="raw")
            .execute()
        )
        return decode_attachment_data(resp["raw"])

    def list_filters(self) -> list[dict]:
        resp = self._svc.users().settings().filters().list(userId=USER).execute()
        return resp.get("filter", [])

    def get_filter(self, filter_id: str) -> dict:
        return (
            self._svc.users()
            .settings()
            .filters()
            .get(userId=USER, id=filter_id)
            .execute()
        )

    # ----- mutations (audited) ---------------------------------------------

    def create_draft(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        attachments: list[str] | None = None,
        in_reply_to: str | None = None,
        cc: str | None = None,
    ) -> dict:
        raw = build_raw_message(
            to=to,
            subject=subject,
            body=body,
            attachments=attachments,
            in_reply_to=in_reply_to,
            cc=cc,
        )
        resp = (
            self._svc.users()
            .drafts()
            .create(userId=USER, body={"message": {"raw": raw}})
            .execute()
        )
        record_mutation(
            action="draft.create",
            args={
                "to": to,
                "subject": subject,
                "cc": cc,
                "in_reply_to": in_reply_to,
                "attachment_count": len(attachments or []),
            },
            result={"draft_id": resp.get("id")},
            log_path=self._audit_log,
        )
        return resp

    def send_draft(self, draft_id: str) -> dict:
        resp = (
            self._svc.users()
            .drafts()
            .send(userId=USER, body={"id": draft_id})
            .execute()
        )
        record_mutation(
            action="draft.send",
            args={"draft_id": draft_id},
            result={"message_id": resp.get("id"), "label_ids": resp.get("labelIds")},
            log_path=self._audit_log,
        )
        return resp

    def create_filter(self, spec: FilterSpec) -> dict:
        resource = spec.to_gmail_resource()
        resp = (
            self._svc.users()
            .settings()
            .filters()
            .create(userId=USER, body=resource)
            .execute()
        )
        record_mutation(
            action="filter.create",
            args=resource,
            result={"filter_id": resp.get("id")},
            log_path=self._audit_log,
        )
        return resp

    def delete_filter(self, filter_id: str) -> None:
        self._svc.users().settings().filters().delete(
            userId=USER, id=filter_id
        ).execute()
        record_mutation(
            action="filter.delete",
            args={"id": filter_id},
            result=None,
            log_path=self._audit_log,
        )
