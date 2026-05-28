"""Typer entrypoint for gmail-ai-broker.

Subcommand groups (attachment / message / draft / filter) are registered here.
Real command implementations are wired in during the build (task #5); this
module stays a thin dispatch layer over `gmail_ai_broker.client`.
"""

from __future__ import annotations

import typer

from gmail_ai_broker import __version__

app = typer.Typer(
    name="gmail-ai-broker",
    help=(
        "Auditable Gmail connector gap-filler: attachment download, raw-MIME "
        "send with attachments, filter CRUD, and raw message fetch. "
        "Read-safe by default; the only transmit path is an explicit 'draft send'."
    ),
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _main() -> None:
    """gmail-ai-broker -- see the per-command help below."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


if __name__ == "__main__":  # pragma: no cover
    app()
