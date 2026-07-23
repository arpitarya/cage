"""Stale-wiring liveness: detect an orphaned wiring artifact, heal it on re-setup.

A wiring artifact whose cage command uses a verb the current CLI rejects exits 1 —
and because hook/shim stdout goes nowhere and both shims fail open to exit 0, a dead
verb is indistinguishable from cage being absent. That is the root cause behind F1
(v0.28.0 renamed 31 verbs; `anton/bin/graphify` and a global SessionStart hook were
silently dead for 9 days while `cage doctor` reported ✅).

**The must-preserve tests below (`test_import_claude_still_heals` /
`test_import_codex_still_heals`) are the load-bearing ones.** Those two commands are
healed today by an *accident*: the old predicate matched the substring `" import"`,
which `" import-claude"` happens to contain. Retiring that coincidence for a
parser-based predicate must keep both cases healing — this is the single place a wrong
move silently turns capture off. They are asserted green before and after the swap.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cage import agents, cfgio, paths, verbmap, wiringscan

posix_only = pytest.mark.skipif(os.name != "posix", reason="sh shim — POSIX hosts")


# ── the liveness oracle (pure — no filesystem) ──────────────────────────────────

@pytest.mark.parametrize("command, live", [
    # live: every verb cage actually emits into a wiring artifact today
    ("cage import --agent claude --project .", True),
    ("cage hook-stop", True),
    ("cage hook-session-start", True),
    ("cage hook-session-end", True),
    ("cage hook-post-tool-use", True),
    ("cage hook-post-commit", True),
    ('cage hook-prepare-commit-msg "$1"', True),
    ("cage mcp", True),
    ("cage data graphify --help", True),
    ("cage insights attrib", True),
    # dead: renamed in v0.28.0 …
    ("cage import-claude --project .", False),
    ("cage import-codex --since 7d", False),
    ("cage graphify --help", False),
    ("cage export --json", False),
    ("cage matrix", False),
    # … and removed outright (NOT in verbmap.REMOVED — why the parser is the oracle)
    ("cage adopt", False),
    # foreign commands are never ours to judge
    ("npm run lint", True),
    ('echo "cage is great"', True),
    ("", True),
])
def test_parser_liveness(command, live):
    assert (not wiringscan.is_dead_cage_command(command)) is live, command


def test_every_command_shape_yields_its_verb():
    """All four wiring shapes must resolve to the same verb — a shape we fail to parse
    scans as 'foreign' and its dead verb goes unreported."""
    for command in (
            "cage import --agent codex --since 7d",
            "/abs/path/cage import --agent codex --since 7d",
            '"$CLAUDE_PROJECT_DIR/.cage/bin/cage-run" import --agent codex --since 7d',
            "python3 -m cage import --agent codex --since 7d",
            "py -3 -m cage import --agent codex --since 7d",
            # the codex/kiro self-locating one-liner — mid-command shim reference
            'r="$(git rev-parse --show-toplevel 2>/dev/null)" && [ -x "$r/.cage/bin/'
            'cage-run" ] && exec "$r/.cage/bin/cage-run" import --agent codex '
            '--since 7d; exit 0'):
        assert paths.cage_verb_path(command) == ("import",), command


def test_removed_verbs_map_to_parser_valid_tails():
    """PROPERTY: every `verbmap.REMOVED` remediation must be a command the CLI accepts.

    This is the guard that would have caught this whole class at the rename commit — a
    remediation that doesn't parse heals a dead verb into another dead verb."""
    for old, new in verbmap.REMOVED.items():
        verbs = tuple(t for t in new.split() if not t.startswith("-"))[:2]
        assert wiringscan.is_live_verb(verbs), \
            f"REMOVED[{old!r}] = {new!r} is not a parser-valid command"


def test_removed_keys_are_all_actually_dead():
    """The converse: nothing in REMOVED may still be a live verb (a stale map entry
    would make the heal rewrite a working command)."""
    for old in verbmap.REMOVED:
        assert not wiringscan.is_live_verb((old,)), f"{old!r} is in REMOVED but still live"


def test_heal_tail_rewrites_dead_verbs_only():
    assert wiringscan.heal_tail("import-claude --project .") == \
        "import --agent claude --project ."
    assert wiringscan.heal_tail("export --json") == "data export --json"
    assert wiringscan.heal_tail("matrix") == "insights matrix"
    # live verbs and unmappable dead ones are returned untouched — heal never guesses
    assert wiringscan.heal_tail("hook-stop") == "hook-stop"
    assert wiringscan.heal_tail("import --agent claude") == "import --agent claude"
    assert wiringscan.heal_tail("adopt") == "adopt"


@pytest.fixture
def homes(tmp_path, monkeypatch):
    """Redirect every agent home off the real machine (mirrors test_portable_wiring)."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude_home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex_home"))
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "copilot_home"))
    monkeypatch.setenv("KIRO_HOME", str(tmp_path / "kiro_home"))
    monkeypatch.setenv("CAGE_HOME", str(tmp_path / "cage_home"))
    return tmp_path


def _claude_commands(root: Path) -> list[str]:
    data = cfgio.load_json(root / ".claude" / "settings.json")
    return [h.get("command", "")
            for entries in data.get("hooks", {}).values()
            for e in entries for h in e.get("hooks", [])]


def _copilot_commands() -> list[str]:
    path = paths.copilot_home() / "hooks" / "cage.json"
    return [h.get("bash", "")
            for arr in cfgio.load_json(path).get("hooks", {}).values() for h in arr]


def _plant_claude(root: Path, session_start: list[str], **events: str) -> None:
    """Write a v0.27-era .claude/settings.json with the given raw commands."""
    hooks = {"SessionStart": [{"hooks": [{"type": "command", "command": c}
                                         for c in session_start]}]}
    for event, command in events.items():
        hooks[event] = [{"hooks": [{"type": "command", "command": command}]}]
    path = root / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hooks": hooks}, indent=2) + "\n", encoding="utf-8")


# ── the two must-preserve cases ─────────────────────────────────────────────────
# These are the real historical forms found installed on a live machine, not
# synthetic ones. `cage import-claude` shipped in claudewire until v0.28.0
# (048a962); `cage import-codex` until v0.9.0 (26788ff).

def test_import_claude_still_heals(homes):
    """MUST-PRESERVE: the v0.27 Claude backfill hook heals to the current form.

    Healed today only because `" import-claude"` contains the substring `" import"`.
    The parser-based predicate must catch it as a *dead verb* instead — same outcome,
    non-accidental reason."""
    _plant_claude(homes, ["/old/bin/cage import-claude --project .",
                          "/old/bin/cage hook-session-start"])
    agents.install(homes, ("claude",))
    cmds = _claude_commands(homes)
    assert not any("import-claude" in c for c in cmds), \
        f"dead verb `import-claude` survived setup: {cmds}"
    assert any("import --agent claude --project ." in c for c in cmds), \
        f"current backfill missing after heal: {cmds}"


def test_codex_import_hook_is_no_longer_managed(homes):
    """Codex was removed completely: `agents.install` no longer has a wire module for
    it, so a pre-existing `.codex/hooks.json` from before the removal is untouched —
    orphaned wiring, not healed (the wiringscan orphan-ownership gap, a deferred
    follow-up per docs/codex-removal.handoff.md §2)."""
    path = homes / ".codex" / "hooks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    before = json.dumps({"hooks": {
        event: [{"hooks": [{"type": "command",
                            "command": "/old/bin/cage import-codex --since 7d"}]}]
        for event in ("Stop", "SessionStart")}}, indent=2) + "\n"
    path.write_text(before, encoding="utf-8")
    out = agents.install(homes, ("codex",))
    assert "codex" not in out  # no wire module ran
    assert path.read_text(encoding="utf-8") == before  # byte-identical, untouched


def test_dead_verb_heals_in_a_non_import_slot(homes):
    """A dead verb that is *not* an import must heal too — the old substring predicate
    could only ever see `import`-shaped commands."""
    _plant_claude(homes, ["/old/bin/cage import-claude --project ."],
                  SessionEnd="/old/bin/cage export --json")
    agents.install(homes, ("claude",))
    cmds = _claude_commands(homes)
    assert any("data export --json" in c for c in cmds), cmds
    assert not any(c.endswith("cage-run\" export --json") for c in cmds), cmds


def test_copilot_stale_entry_is_replaced_not_duplicated(homes):
    """The duplicate-entry bug: a dead-verb entry matched neither old test, so setup
    kept it *and* appended a correct one — the dead command still fired every event."""
    path = homes / "copilot_home" / "hooks" / "cage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "hooks": {
        e: [{"type": "command", "bash": "/old/bin/cage export --agent copilot",
             "powershell": "/old/bin/cage export --agent copilot",
             "cwd": ".", "timeoutSec": 30}]
        for e in ("agentStop", "sessionStart", "sessionEnd")}}, indent=2),
        encoding="utf-8")
    agents.install(homes, ("copilot",))
    cmds = _copilot_commands()
    assert not any("export --agent copilot" in c for c in cmds), \
        f"dead entry survived alongside the new one: {cmds}"
    assert len(cmds) == 3 and all("import --agent copilot" in c for c in cmds), cmds


def test_healed_backfill_precedes_the_banner(homes):
    """Ordering must survive the heal: SessionStart runs backfill *then* banner.

    Once the heal rewrites a dead verb in place, `import-claude` becomes byte-identical
    to the current backfill — so the old drop-then-prepend no longer fires and cannot be
    what guarantees the order. Planted banner-first to pin it."""
    _plant_claude(homes, ["/old/bin/cage hook-session-start",
                          "/old/bin/cage import-claude --project ."])
    agents.install(homes, ("claude",))
    start = [h.get("command", "")
             for e in cfgio.load_json(homes / ".claude" / "settings.json")
             .get("hooks", {}).get("SessionStart", [])
             for h in e.get("hooks", [])]
    backfill = next(i for i, c in enumerate(start) if " import " in c)
    banner = next(i for i, c in enumerate(start) if "hook-session-start" in c)
    assert backfill < banner, f"backfill must precede the banner: {start}"


# ── detection: exactly the stale set, nothing foreign ───────────────────────────

_FOREIGN_HOOK = "npm run lint"
_FOREIGN_CAGEISH = 'echo "cage keeps the ledger"'   # names cage, is not a cage command


def _plant_everything(root: Path) -> None:
    """A project wired the way v0.27 left it, plus two foreign hooks that must be
    treated as none of cage's business."""
    _plant_claude(root, ["/old/bin/cage import-claude --project ."],
                  Stop=_FOREIGN_HOOK, SessionEnd=_FOREIGN_CAGEISH)
    codex = root / ".codex" / "hooks.json"
    codex.parent.mkdir(parents=True, exist_ok=True)
    codex.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": "/old/bin/cage import-codex --since 7d"}]}]}},
        indent=2) + "\n", encoding="utf-8")
    shim = root / "bin" / "graphify"
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(
        "#!/usr/bin/env bash\n"
        "# cage: graphify metering interceptor — routes queries through `cage graphify`\n"
        "# Installed by `cage adopt`.\n"
        'if command -v cage >/dev/null 2>&1 && cage graphify --help >/dev/null 2>&1; then\n'
        '  exec cage graphify -- "$REAL" "$@"\n'
        "fi\n", encoding="utf-8")
    shim.chmod(0o755)


def test_scan_flags_exactly_the_stale_artifacts(homes):
    _plant_everything(homes)
    scan = wiringscan.run(homes, assets=False)
    verbs = sorted({d.command for d in scan.dead})
    assert verbs == ["graphify", "import-claude", "import-codex"], verbs
    assert scan.interceptor_dead
    # every foreign hook is absent from the findings — detection never judges them
    flagged = " ".join(d.artifact + d.command for d in scan.dead)
    assert "npm" not in flagged and "keeps the ledger" not in flagged
    # …and neither is shell *prose*: the shim's own comments mention `cage adopt` and
    # "cage absent", which nothing executes. Only executable lines are evidence.
    assert "adopt" not in flagged and "absent" not in flagged


def test_scan_reports_remediation_only_when_one_exists(homes):
    _plant_everything(homes)
    by_verb = {d.command: d for d in wiringscan.run(homes, assets=False).dead}
    assert by_verb["import-claude"].fix == "import --agent claude"
    assert by_verb["graphify"].fix == "data graphify"
    # `adopt` was removed outright, never renamed (and is absent from verbmap.REMOVED —
    # the reason detection uses the parser). No replacement may ever be invented for it.
    assert wiringscan.remediation(("adopt",)) == ""
    assert "no replacement" in wiringscan.Dead("x", "adopt", "", True).line


def test_a_freshly_wired_project_scans_clean(homes):
    """The handoff's §10 open question: a clean `cage setup` must produce zero
    findings — every verb cage emits today is parser-valid."""
    agents.install(homes, ("claude", "codex", "copilot", "kiro"))
    scan = wiringscan.run(homes, assets=False)
    assert scan.dead == [], [d.line for d in scan.dead]
    assert not scan.interceptor_dead


# ── heal ────────────────────────────────────────────────────────────────────────

def _snapshot(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): p.read_text(encoding="utf-8", errors="ignore")
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_install_heals_every_stale_artifact(homes):
    """Every artifact `agents.install` still manages heals; `.codex/hooks.json` is the
    one exception — codex has no wire module anymore, so it stays dead/orphaned rather
    than healing (the deferred orphan-scanner gap, docs/codex-removal.handoff.md §2)."""
    _plant_everything(homes)
    agents.install(homes, ("claude", "copilot", "kiro"))
    dead = wiringscan.run(homes, assets=False).dead
    assert dead == [wiringscan.Dead(".codex/hooks.json", "import-codex", "", True)]


def test_foreign_hooks_are_byte_identical_after_heal(homes):
    _plant_everything(homes)
    agents.install(homes, ("claude", "copilot", "kiro"))
    cmds = _claude_commands(homes)
    assert _FOREIGN_HOOK in cmds, f"a foreign hook was rewritten or dropped: {cmds}"
    assert _FOREIGN_CAGEISH in cmds, f"a cage-mentioning foreign hook was touched: {cmds}"


def test_second_install_is_byte_identical(homes):
    """Idempotence: healing a healed tree changes nothing (no mtime churn, no diff)."""
    _plant_everything(homes)
    agents.install(homes, ("claude", "codex", "copilot", "kiro"))
    before = _snapshot(homes)
    agents.install(homes, ("claude", "codex", "copilot", "kiro"))
    assert _snapshot(homes) == before


@posix_only
def test_graphify_shim_is_refreshed_then_left_alone(homes):
    from cage import adoptcmd
    _plant_everything(homes)
    assert adoptcmd.refresh_shim(homes) is True          # stale → rewritten
    assert adoptcmd.refresh_shim(homes) is False         # current → untouched
    body = (homes / "bin" / "graphify").read_text(encoding="utf-8")
    assert "cage data graphify" in body and "cage graphify " not in body


def test_refresh_never_creates_a_shim(homes):
    """Refresh-only: a project that never installed the interceptor must not get one."""
    from cage import adoptcmd
    assert adoptcmd.refresh_shim(homes) is False
    assert not (homes / "bin" / "graphify").exists()


# ── doctor ──────────────────────────────────────────────────────────────────────

def _check(res, name):
    return next(c for c in res["checks"] if c["name"] == name)


def test_doctor_fails_on_dead_wiring_and_names_the_fix(homes):
    from cage import doctorcmd, initcmd
    initcmd.run(homes)
    _plant_everything(homes)
    res = doctorcmd.run(homes)
    wiring = _check(res, "wiring")
    assert wiring["level"] == "fail"
    assert "import-claude" in wiring["detail"]
    assert "import --agent claude" in wiring["detail"]      # the remediation, not just the fault


def test_doctor_interceptor_is_liveness_not_existence(homes):
    """The exact false ✅ from F1: the shim exists and is on PATH, but is dead."""
    from cage import doctorcmd, initcmd
    initcmd.run(homes)
    _plant_everything(homes)
    res = doctorcmd.run(homes)
    interceptor = _check(res, "interceptor")
    assert interceptor["level"] == "fail"
    assert "UNMETERED" in interceptor["detail"]


def test_doctor_receipts_line_is_qualified_by_a_dead_interceptor(homes):
    from cage import doctorcmd, initcmd
    initcmd.run(homes)
    _plant_everything(homes)
    checks = [c["name"] for c in doctorcmd.run(homes)["checks"]]
    assert checks.index("wiring") < checks.index("receipts")   # order is load-bearing
    detail = _check(doctorcmd.run(homes), "receipts")["detail"]
    assert "interceptor is dead" in detail and "see wiring above" in detail


def test_doctor_receipts_line_is_plain_when_wiring_is_healthy(homes):
    from cage import doctorcmd, initcmd
    initcmd.run(homes)
    detail = _check(doctorcmd.run(homes), "receipts")["detail"]
    assert "receipts: 0" in detail and "interceptor is dead" not in detail


def test_doctor_wiring_is_ok_on_a_freshly_wired_project(homes):
    from cage import doctorcmd, initcmd
    initcmd.run(homes)
    agents.install(homes, ("claude", "codex", "copilot", "kiro"))
    assert _check(doctorcmd.run(homes), "wiring")["level"] == "ok"


def test_stale_asset_is_advisory_not_a_failure(homes):
    """An edited/stale skill file is `·`: the agent sees a wrong verb, errors, and
    adapts — strictly less severe than capture being silently off."""
    from cage import doctorcmd, initcmd, setupcmd
    initcmd.run(homes)
    setupcmd.run(("claude",), scope="global")
    skill = paths.claude_home() / "skills" / "cage" / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\nstale\n", encoding="utf-8")
    stale = wiringscan.stale_assets()
    assert [s.artifact for s in stale] and all(s.agent == "claude" for s in stale)
    assert _check(doctorcmd.run(homes), "wiring")["level"] == "warn"


def test_freshly_installed_assets_are_not_stale(homes):
    from cage import setupcmd
    setupcmd.run(("claude", "codex", "copilot", "kiro"), scope="global")
    assert wiringscan.stale_assets() == []


# ── the scan changes no number ──────────────────────────────────────────────────

def test_derived_views_are_byte_identical(proj, capsys):
    """Determinism: this change touches detection and wiring only. A derived view must
    render byte-for-byte the same before and after a scan runs over the same project."""
    from cage import cli, demo
    demo.seed(proj)
    assert cli.main(["--ledger", str(proj), "insights", "attrib"]) == 0
    before = capsys.readouterr().out
    wiringscan.run(proj)
    assert cli.main(["--ledger", str(proj), "insights", "attrib"]) == 0
    assert capsys.readouterr().out == before
