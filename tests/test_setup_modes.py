"""`cage setup` modes — the collapsed setup cluster (--project-only / --wire-only /
--status). These absorbed the old `adopt` and `hooks` verbs; the wiring underneath
is the same idempotent `adoptcmd` / `agents` engine."""
from __future__ import annotations

import pytest

from cage import agents, cli, metering


@pytest.fixture
def homes(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude_home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex_home"))
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    return proj


def test_status_reports_wiring_changes_nothing(homes, capsys):
    # Nothing wired yet → every surface reads "not wired", and .cage/ is untouched.
    assert cli.main(["setup", "--status"]) == 0
    out = capsys.readouterr().out
    assert "not wired" in out
    for s in agents.SURFACES:
        assert s in out
    assert not (homes / ".cage").exists()  # --status mutates nothing


def test_wire_only_wires_agent_without_scaffold(homes, capsys):
    assert cli.main(["setup", "--wire-only", "--kiro"]) == 0
    assert agents.status(homes) == {"claude": False, "codex": False,
                                    "copilot": False, "kiro": True}
    # wire-only does not scaffold the project ledger or graphify shim
    assert not (homes / "bin" / "graphify").exists()


def test_wire_only_without_agent_prompts_and_exits_2(homes, capsys):
    assert cli.main(["setup", "--wire-only"]) == 2
    out = capsys.readouterr().out
    assert "Pick an agent" in out


def test_project_only_scaffolds_without_global_skill(homes):
    # --project-only = old `adopt`: scaffold (+ graphify), agent wiring opt-in.
    assert cli.main(["setup", "--project-only", "--no-graphify", "--kiro"]) == 0
    assert (homes / ".cage").is_dir()
    assert agents.status(homes)["kiro"] is True


def test_status_after_wire_only_reflects_change(homes, capsys):
    cli.main(["setup", "--wire-only", "--codex"])
    capsys.readouterr()  # drain
    assert cli.main(["setup", "--status"]) == 0
    out = capsys.readouterr().out
    assert "✔ codex" in out


def test_wire_only_is_idempotent(homes):
    assert cli.main(["setup", "--wire-only", "--claude"]) == 0
    assert cli.main(["setup", "--wire-only", "--claude"]) == 0  # no double-write, no raise
    assert agents.status(homes)["claude"] is True


def test_removed_verbs_no_longer_parse(homes):
    # `adopt` and `hooks` were removed outright — argparse rejects them.
    with pytest.raises(SystemExit):
        cli.main(["adopt", "--claude"])
    with pytest.raises(SystemExit):
        cli.main(["hooks", "install", "--claude"])
