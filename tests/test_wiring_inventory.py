"""`cage doctor --wiring` — the installed-artifact inventory (docs/wiring-inventory
.handoff.md). Renders `wiringscan.inventory()`; asserts the status taxonomy, the
partial/not-wired distinction, read-only-ness, and JSON/text parity. Plain `cage
doctor` output is asserted unchanged by `tests/test_doctor.py`.
"""
from __future__ import annotations

import json

import pytest

from cage import agents, cfgio, cli, doctorcmd, paths, setupcmd, wiringscan


def _rollup(rep, agent):
    return next(r for r in rep["rollups"] if r["agent"] == agent)


def _item(rep, agent, kind):
    return next((it for it in rep["items"] if it["agent"] == agent and it["kind"] == kind), None)


# ── verdict taxonomy ─────────────────────────────────────────────────────────────

def test_fresh_project_every_agent_not_wired(proj):
    rep = doctorcmd.wiring_report(proj)
    assert {r["agent"] for r in rep["rollups"]} == set(agents.SURFACES)
    for r in rep["rollups"]:
        assert r["verdict"] == "not wired"
        assert r["missing"] == []  # informational — never a nagging "missing" list


def test_fully_wired_project_all_current(proj):
    agents.install(proj, ("claude", "copilot", "kiro"))
    rep = doctorcmd.wiring_report(proj)
    for agent in agents.SURFACES:
        assert _rollup(rep, agent)["verdict"] == "fully wired"
    assert _item(rep, "claude", "hook")["status"] == "current"
    assert _item(rep, "claude", "mcp")["status"] == "current"
    assert _item(rep, "copilot", "instructions")["status"] == "current"
    assert _item(rep, "copilot", "mcp")["status"] == "current"
    copilot_hook = _item(rep, "copilot", "hook")
    assert copilot_hook["status"] == "current" and copilot_hook["scope"] == "global"
    assert _item(rep, "kiro", "steering")["status"] == "current"
    assert _item(rep, "kiro", "hook")["status"] == "current"


def test_partial_wiring_names_the_missing_piece(proj):
    agents.install(proj, ("kiro",))
    (proj / ".kiro" / "steering" / "cage.md").unlink()
    rep = doctorcmd.wiring_report(proj)
    r = _rollup(rep, "kiro")
    assert r["verdict"] == "partially wired"
    assert r["missing"] == ["steering"]
    # the still-present required pieces still render as rows
    assert _item(rep, "kiro", "hook")["status"] == "current"


def test_kiro_mcp_gitignore_exception_never_flagged_missing(proj):
    """handoff §8: `.kiro/settings/mcp.json` is a known gitignore exception — its
    absence must never demote a fully-wired kiro to partial."""
    agents.install(proj, ("kiro",))
    (proj / ".kiro" / "settings" / "mcp.json").unlink()
    rep = doctorcmd.wiring_report(proj)
    r = _rollup(rep, "kiro")
    assert r["verdict"] == "fully wired"
    assert _item(rep, "kiro", "mcp") is None  # absent + optional → no row, no noise


def test_claude_git_hooks_absent_is_not_partial(proj):
    """Git hooks are best-effort (gitcommithook.py) — `agents.install` never even
    attempts them without a `.git` dir, and their absence must not read as partial."""
    agents.install(proj, ("claude",))
    assert not (proj / ".git").exists()
    rep = doctorcmd.wiring_report(proj)
    assert _rollup(rep, "claude")["verdict"] == "fully wired"
    assert _item(rep, "claude", "git-hook") is None


# ── dead / stale / foreign ────────────────────────────────────────────────────────

def test_dead_hook_reports_dead_and_needs_healing(proj):
    agents.install(proj, ("claude",))
    settings = proj / ".claude" / "settings.json"
    data = cfgio.load_json(settings)
    data["hooks"]["SessionEnd"] = [{"hooks": [{"type": "command",
                                              "command": '"$CLAUDE_PROJECT_DIR/.cage/bin/cage-run" export --json'}]}]
    cfgio.save_json(settings, data)
    rep = doctorcmd.wiring_report(proj)
    hook = _item(rep, "claude", "hook")
    assert hook["status"] == "dead"
    assert "not a command" in hook["detail"]
    r = _rollup(rep, "claude")
    assert r["verdict"] == "needs healing"
    assert r["dead"] == 1 and r["stale"] == 0


def test_dead_verb_only_hook_is_dead_not_not_wired(proj):
    """A hook whose only entry names a legacy dead verb must read as broken, not
    absent — `claudewire.status()` alone would misreport this as 'not wired' since
    it only matches the current canonical command form."""
    settings = proj / ".claude" / "settings.json"
    cfgio.save_json(settings, {"hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "/old/bin/cage import-claude --project ."}]}]}})
    rep = doctorcmd.wiring_report(proj)
    hook = _item(rep, "claude", "hook")
    assert hook is not None and hook["status"] == "dead"
    assert _rollup(rep, "claude")["verdict"] == "needs healing"


def test_foreign_git_hook_shown_never_judged(proj):
    hooks_dir = proj / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "post-commit").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    rep = doctorcmd.wiring_report(proj)
    foreign = next(it for it in rep["items"] if it["kind"] == "git-hook")
    assert foreign["status"] == "foreign"
    assert foreign["agent"] == ""
    # a foreign hook must never count against claude's rollup
    assert _rollup(rep, "claude")["verdict"] == "not wired"


def test_stale_global_asset_folds_into_needs_healing(proj, monkeypatch):
    setupcmd.run(("claude",), scope="global")
    skill = paths.claude_home() / "skills" / "cage" / "SKILL.md"
    skill.write_text("stale bytes\n", encoding="utf-8")
    agents.install(proj, ("claude",))  # wiring itself stays current
    rep = doctorcmd.wiring_report(proj)
    asset = next(it for it in rep["items"] if it["kind"] == "skill" and it["scope"] == "global")
    assert asset["status"] == "stale"
    r = _rollup(rep, "claude")
    assert r["verdict"] == "needs healing"
    assert r["dead"] == 0 and r["stale"] == 1


def test_asset_rows_never_gate_the_rollup_alone(proj):
    """Skill/prompt/steering presence is informational only — `cage setup` (assets)
    and `cage setup --wire-only` (hooks/MCP) are separate invocations."""
    setupcmd.run(("claude",), scope="global")  # asset only, no wiring at all
    rep = doctorcmd.wiring_report(proj)
    assert _rollup(rep, "claude")["verdict"] == "not wired"
    assert any(it["kind"] == "skill" for it in rep["items"])


def test_orphaned_codex_leftover_surfaces_generically(proj):
    """codex has no wire module (removed v0.33.0); a pre-existing artifact is neither
    hand-enumerated as an agent nor silently dropped — it shows up via the leftover
    sweep, tagged by whatever's actually on disk."""
    codex = proj / ".codex" / "hooks.json"
    codex.parent.mkdir(parents=True)
    cfgio.save_json(codex, {"hooks": {"Stop": [
        {"hooks": [{"type": "command", "command": "/old/bin/cage import-codex --since 7d"}]}]}})
    rep = doctorcmd.wiring_report(proj)
    row = next(it for it in rep["items"] if ".codex" in it["display"])
    assert row["status"] == "dead"  # import-codex was removed outright
    assert {r["agent"] for r in rep["rollups"]} == set(agents.SURFACES)  # codex never joins the agent list


# ── JSON / text parity, version footer, read-only ─────────────────────────────────

def test_json_and_text_share_one_data_structure(proj):
    agents.install(proj, ("claude", "copilot", "kiro"))
    rep = doctorcmd.wiring_report(proj)
    json.dumps(rep)  # must be plain-JSON-serializable
    text = doctorcmd.render_wiring_text(rep)
    for r in rep["rollups"]:
        assert r["agent"] in text
    for it in rep["items"]:
        assert it["display"] in text


def test_version_footer_present_and_zipapp_tag(proj, monkeypatch):
    rep = doctorcmd.wiring_report(proj)
    assert rep["version"]["cage"]
    assert rep["version"]["zipapp"] is False
    assert rep["version"]["project"] is None  # no project policy.toml yet

    monkeypatch.setattr("cage.paths.distribution", lambda: "zipapp")
    rep2 = doctorcmd.wiring_report(proj)
    assert rep2["version"]["zipapp"] is True
    assert "(zipapp)" in doctorcmd.render_wiring_text(rep2)


def test_version_footer_reads_project_policy_meta(proj):
    from cage import initcmd
    initcmd.run(proj)
    rep = doctorcmd.wiring_report(proj)
    assert rep["version"]["project"] is not None


def test_wiring_report_is_read_only(proj):
    agents.install(proj, ("claude", "copilot", "kiro"))
    before = sorted(p.relative_to(proj) for p in proj.rglob("*") if p.is_file())
    doctorcmd.wiring_report(proj)
    after = sorted(p.relative_to(proj) for p in proj.rglob("*") if p.is_file())
    assert before == after  # not one new/changed file from the read


def test_plain_doctor_unaffected_by_wiring_report(proj):
    from cage import initcmd
    initcmd.run(proj)
    before = doctorcmd.run(proj)
    doctorcmd.wiring_report(proj)  # side-effect-free — must not perturb the next read
    after = doctorcmd.run(proj)
    assert before == after


# ── CLI wiring ────────────────────────────────────────────────────────────────────

def test_cli_wiring_flag_text(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    agents.install(proj, ("claude",))
    assert cli.main(["doctor", "--wiring"]) == 0
    out = capsys.readouterr().out
    assert "Wiring inventory" in out
    assert "claude" in out


def test_cli_wiring_flag_json(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    agents.install(proj, ("claude",))
    assert cli.main(["doctor", "--wiring", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "items" in payload and "rollups" in payload and "version" in payload


def test_cli_plain_doctor_still_works_alongside_wiring_flag(proj, monkeypatch, capsys):
    """The flag is additive — plain `cage doctor` must stay untouched by its
    existence (golden-covered in tests/test_output_spec.py; this just proves the
    dispatch branch never falls through into the regular check list)."""
    monkeypatch.chdir(proj)
    exit_code = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "Wiring inventory" not in out
    assert exit_code in (0, 1)
