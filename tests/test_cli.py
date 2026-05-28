"""CLI behavior tests (offline): version, the send guard, spec-file parsing."""

from __future__ import annotations

from typer.testing import CliRunner

from gmail_ai_broker import __version__
from gmail_ai_broker.cli.main import _load_filter_spec, app

runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_draft_send_refuses_without_yes():
    # Must NOT reach config/network -- the guard short-circuits first.
    result = runner.invoke(app, ["draft", "send", "d1"])
    assert result.exit_code == 2
    assert "refusing to send" in (result.stdout + str(result.stderr))


def test_load_filter_spec_reads_toml(tmp_path):
    f = tmp_path / "spec.toml"
    f.write_text(
        "[criteria]\nfrom = \"billing@example.com\"\n[action]\nadd_label_ids = [\"L1\"]\n"
    )
    spec = _load_filter_spec(f)
    assert spec.to_gmail_resource() == {
        "criteria": {"from": "billing@example.com"},
        "action": {"addLabelIds": ["L1"]},
    }


def test_load_filter_spec_reads_json(tmp_path):
    f = tmp_path / "spec.json"
    f.write_text('{"criteria": {"subject": "tax"}, "action": {"add_label_ids": ["L2"]}}')
    spec = _load_filter_spec(f)
    assert spec.to_gmail_resource() == {
        "criteria": {"subject": "tax"},
        "action": {"addLabelIds": ["L2"]},
    }
