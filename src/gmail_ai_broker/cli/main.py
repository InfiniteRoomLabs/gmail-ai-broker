"""Typer entrypoint for gmail-ai-broker.

Four capability groups -- attachment, message, draft, filter -- each backed by
GmailBroker. Reads print/emit data; the only command that transmits mail is
`draft send`, and it refuses to run without an explicit --yes.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Optional

import typer

from gmail_ai_broker import __version__
from gmail_ai_broker.client import GmailBroker
from gmail_ai_broker.models import FilterSpec

app = typer.Typer(
    name="gmail-ai-broker",
    help=(
        "Auditable Gmail connector gap-filler: attachment download, raw-MIME "
        "send with attachments, filter CRUD, and raw message fetch. "
        "Read-safe by default; the only transmit path is an explicit 'draft send --yes'."
    ),
    no_args_is_help=True,
    add_completion=False,
)

auth_app = typer.Typer(help="One-time OAuth setup (loopback consent).", no_args_is_help=True)
attachment_app = typer.Typer(help="Download message attachments.", no_args_is_help=True)
message_app = typer.Typer(help="Fetch raw message MIME.", no_args_is_help=True)
draft_app = typer.Typer(help="Create drafts and (explicitly) send them.", no_args_is_help=True)
filter_app = typer.Typer(help="Gmail filter CRUD (requires gmail.settings.basic).", no_args_is_help=True)

app.add_typer(auth_app, name="auth")
app.add_typer(attachment_app, name="attachment")
app.add_typer(message_app, name="message")
app.add_typer(draft_app, name="draft")
app.add_typer(filter_app, name="filter")

ConfigOpt = typer.Option(None, "--config", help="Path to config.toml (defaults to XDG location).")


def _broker(config: Optional[Path]) -> GmailBroker:
    return GmailBroker.from_config(config)


def _load_filter_spec(path: Path) -> FilterSpec:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix == ".json" else tomllib.loads(text)
    return FilterSpec.model_validate(data)


@app.callback()
def _main() -> None:
    """gmail-ai-broker -- see the per-command help below."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


# ----- auth (one-time setup) ------------------------------------------------


@auth_app.command("login")
def auth_login(
    client_secrets: Path = typer.Option(
        ..., "--client-secrets", help="Path to the Desktop OAuth client JSON from Google Cloud Console."
    ),
    config: Optional[Path] = ConfigOpt,
) -> None:
    """Run the loopback consent flow and save the refresh token (mode 600)."""
    from gmail_ai_broker.auth import (
        GMAIL_SCOPES,
        run_installed_app_flow,
        save_refresh_token,
    )
    from gmail_ai_broker.config import DEFAULT_CONFIG_PATH, DEFAULT_REFRESH_TOKEN_PATH, Config

    try:
        token_path = Config.load(config or DEFAULT_CONFIG_PATH).refresh_token_path
    except RuntimeError:
        token_path = DEFAULT_REFRESH_TOKEN_PATH

    creds = run_installed_app_flow(client_secrets, GMAIL_SCOPES)
    if not creds.refresh_token:
        typer.echo(
            "no refresh token returned -- revoke prior access and retry "
            "(the flow forces prompt=consent; ensure the app is in Production).",
            err=True,
        )
        raise typer.Exit(code=1)
    save_refresh_token(creds.refresh_token, token_path)
    typer.echo(f"saved refresh token to {token_path} (mode 600). Back it up in Bitwarden.")


@auth_app.command("status")
def auth_status(config: Optional[Path] = ConfigOpt) -> None:
    """Report whether config + refresh token exist (no network)."""
    from gmail_ai_broker.config import DEFAULT_CONFIG_PATH, Config

    cfg_path = config or DEFAULT_CONFIG_PATH
    if not Path(cfg_path).exists():
        typer.echo(f"config: MISSING ({cfg_path})")
        raise typer.Exit(code=1)
    cfg = Config.load(cfg_path)
    typer.echo(f"config: ok ({cfg_path})")
    typer.echo(
        f"refresh token: {'ok' if cfg.refresh_token_path.exists() else 'MISSING'} "
        f"({cfg.refresh_token_path})"
    )
    typer.echo(f"audit log: {cfg.audit_log_path}")


# ----- attachment -----------------------------------------------------------


@attachment_app.command("download")
def attachment_download(
    message_id: str = typer.Argument(..., help="Gmail message id."),
    attachment_id: str = typer.Argument(..., help="Attachment (part) id."),
    out: Path = typer.Option(..., "--out", help="File to write the attachment to."),
    config: Optional[Path] = ConfigOpt,
) -> None:
    """Download an attachment to a file."""
    data = _broker(config).download_attachment(message_id, attachment_id)
    out.write_bytes(data)
    typer.echo(f"wrote {len(data)} bytes to {out}")


# ----- message --------------------------------------------------------------


@message_app.command("get-raw")
def message_get_raw(
    message_id: str = typer.Argument(..., help="Gmail message id."),
    out: Optional[Path] = typer.Option(None, "--out", help="File to write to (default: stdout)."),
    config: Optional[Path] = ConfigOpt,
) -> None:
    """Fetch the full raw RFC822 MIME for a message."""
    data = _broker(config).get_raw_message(message_id)
    if out:
        out.write_bytes(data)
        typer.echo(f"wrote {len(data)} bytes to {out}")
    else:
        sys.stdout.buffer.write(data)


# ----- draft ----------------------------------------------------------------


@draft_app.command("create")
def draft_create(
    to: str = typer.Option(..., "--to"),
    subject: str = typer.Option(..., "--subject"),
    body_file: Path = typer.Option(..., "--body-file", help="File containing the message body."),
    attach: list[Path] = typer.Option(None, "--attach", help="Attachment file(s); repeatable."),
    in_reply_to: Optional[str] = typer.Option(None, "--in-reply-to", help="Message-Id to thread under."),
    cc: Optional[str] = typer.Option(None, "--cc"),
    config: Optional[Path] = ConfigOpt,
) -> None:
    """Create a draft (optionally with attachments). Does NOT send."""
    body = body_file.read_text(encoding="utf-8")
    resp = _broker(config).create_draft(
        to=to,
        subject=subject,
        body=body,
        attachments=[str(a) for a in attach] or None,
        in_reply_to=in_reply_to,
        cc=cc,
    )
    typer.echo(f"created draft {resp.get('id')} (not sent -- review, then 'draft send --yes')")


@draft_app.command("send")
def draft_send(
    draft_id: str = typer.Argument(..., help="Draft id to transmit."),
    yes: bool = typer.Option(False, "--yes", help="Required: confirm you intend to send."),
    config: Optional[Path] = ConfigOpt,
) -> None:
    """Send a draft. This is the ONLY command that transmits mail."""
    if not yes:
        typer.echo("refusing to send without --yes (this is the only transmit path)", err=True)
        raise typer.Exit(code=2)
    resp = _broker(config).send_draft(draft_id)
    typer.echo(f"sent: message {resp.get('id')}")


# ----- filter ---------------------------------------------------------------


@filter_app.command("list")
def filter_list(config: Optional[Path] = ConfigOpt) -> None:
    """List all Gmail filters as JSON."""
    typer.echo(json.dumps(_broker(config).list_filters(), indent=2))


@filter_app.command("get")
def filter_get(
    filter_id: str = typer.Argument(...),
    config: Optional[Path] = ConfigOpt,
) -> None:
    """Show a single filter as JSON."""
    typer.echo(json.dumps(_broker(config).get_filter(filter_id), indent=2))


@filter_app.command("create")
def filter_create(
    spec: Path = typer.Option(..., "--spec", help="Declarative filter spec (.toml or .json) you have reviewed."),
    config: Optional[Path] = ConfigOpt,
) -> None:
    """Create a filter from an approved declarative spec."""
    resp = _broker(config).create_filter(_load_filter_spec(spec))
    typer.echo(f"created filter {resp.get('id')}")


@filter_app.command("delete")
def filter_delete(
    filter_id: str = typer.Argument(...),
    config: Optional[Path] = ConfigOpt,
) -> None:
    """Delete a filter by id."""
    _broker(config).delete_filter(filter_id)
    typer.echo(f"deleted filter {filter_id}")


if __name__ == "__main__":  # pragma: no cover
    app()
