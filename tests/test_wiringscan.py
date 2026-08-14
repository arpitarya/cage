"""Stale-wiring liveness: detect an orphaned wiring artifact, heal it on re-setup.

A wiring artifact whose cage command uses a verb the current CLI rejects exits 1 —
and because hook/shim stdout goes nowhere and both shims fail open to exit 0, a dead
verb is indistinguishable from cage being absent. That is the root cause behind F1
(v0.28.0 renamed 31 verbs; `anton/bin/graphify` and a global SessionStart hook were
silently dead for 9 days while `cage doctor` reported ✅).

**The must-preserve test below (`test_import_claude_stale_hook_is_stripped`) is the
load-bearing one.** That command is healed today by an *accident*: the old predicate
matched the substring `" import"`, which `" import-claude"` happens to contain.
Retiring that coincidence for a parser-based predicate must keep the case healing —
this is the single place a wrong move silently turns capture off. It is asserted green
before and after the swap.
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
    ("cage mcp", True),
    ("cage insights chats", True),
    # dead: renamed in v0.28.0 …
    # … SURFACE-CUT (v0.50) removed the rollup family and the whole `data` group; both
    # spellings are still installed on real machines, so both must read as dead.
    ("cage insights attrib", False),
    ("cage report --by agent", False),
    ("cage data export --json", False),
    ("cage import-claude --project .", False),
    ("cage graphify --help", False),
    ("cage export --json", False),
    ("cage matrix", False),
    # … the hook verbs, removed outright with the hook machinery (empty tail in
    # verbmap.REMOVED — a pre-removal settings.json still names them) …
    ("cage hook-stop", False),
    ("cage hook-session-start", False),
    ("cage hook-post-commit", False),
    ('cage hook-prepare-commit-msg "$1"', False),
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
            "cage import --agent claude --since 7d",
            "/abs/path/cage import --agent claude --since 7d",
            '"$CLAUDE_PROJECT_DIR/.cage/bin/cage-run" import --agent claude --since 7d',
            "python3 -m cage import --agent claude --since 7d",
            "py -3 -m cage import --agent claude --since 7d",
            # the kiro self-locating one-liner — mid-command shim reference
            'r="$(git rev-parse --show-toplevel 2>/dev/null)" && [ -x "$r/.cage/bin/'
            'cage-run" ] && exec "$r/.cage/bin/cage-run" import --agent claude '
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
    # `export`/`attrib` map to an EMPTY tail since SURFACE-CUT (removed, no
    # replacement), and `heal_tail` never rewrites to an empty fix — it returns the tail
    # untouched and the scan reports it as dead-with-no-remediation instead. Inventing a
    # replacement for a deleted command is the one thing heal must never do.
    assert wiringscan.heal_tail("export --json") == "export --json"
    assert wiringscan.heal_tail("attrib") == "attrib"
    # live verbs and unmappable dead ones are returned untouched — heal never guesses
    assert wiringscan.heal_tail("hook-stop") == "hook-stop"
    assert wiringscan.heal_tail("import --agent claude") == "import --agent claude"
    assert wiringscan.heal_tail("adopt") == "adopt"


@pytest.fixture
def homes(tmp_path, monkeypatch):
    """Redirect every agent home off the real machine (mirrors test_portable_wiring)."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude_home"))
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


# ── the must-preserve case ──────────────────────────────────────────────────────
# This is the real historical form found installed on a live machine, not a
# synthetic one. `cage import-claude` shipped in claudewire until v0.28.0 (048a962).

def test_import_claude_stale_hook_is_stripped(homes):
    """MUST-PRESERVE: a v0.27 Claude backfill/banner hook naming a dead verb must not
    survive `cage setup`. Hookless heal STRIPS every cage-owned hook entry (capture is
    pull-based now) rather than rewriting it — foreign hooks are never touched."""
    _plant_claude(homes, ["/old/bin/cage import-claude --project .",
                          "/old/bin/cage hook-session-start"])
    agents.install(homes, ("claude",))
    cmds = _claude_commands(homes)
    assert not any(paths.cage_command_tail(c) is not None for c in cmds), \
        f"a stale cage hook survived setup: {cmds}"


def test_stale_hook_in_a_non_session_slot_is_stripped(homes):
    """A stale cage hook in any event slot (not just SessionStart) is stripped — the
    heal walks every event, not one blessed slot."""
    _plant_claude(homes, ["/old/bin/cage import-claude --project ."],
                  SessionEnd="/old/bin/cage export --json")
    agents.install(homes, ("claude",))
    cmds = _claude_commands(homes)
    assert not any(paths.cage_command_tail(c) is not None for c in cmds), cmds


def test_copilot_stale_hook_file_is_deleted(homes):
    """The user-level `~/.copilot/hooks/cage.json` is wholly cage-owned, so the hookless
    heal deletes it outright (capture is pull-based — no copilot hook is wired)."""
    path = homes / "copilot_home" / "hooks" / "cage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "hooks": {
        e: [{"type": "command", "bash": "/old/bin/cage export --agent copilot",
             "powershell": "/old/bin/cage export --agent copilot",
             "cwd": ".", "timeoutSec": 30}]
        for e in ("agentStop", "sessionStart", "sessionEnd")}}, indent=2),
        encoding="utf-8")
    agents.install(homes, ("copilot",))
    assert not path.exists(), "the cage-owned copilot hook file survived heal"


# ── detection: exactly the stale set, nothing foreign ───────────────────────────

_FOREIGN_HOOK = "npm run lint"
_FOREIGN_CAGEISH = 'echo "cage keeps the ledger"'   # names cage, is not a cage command


def _plant_everything(root: Path) -> None:
    """A project wired the way v0.27 left it, plus two foreign hooks that must be
    treated as none of cage's business."""
    _plant_claude(root, ["/old/bin/cage import-claude --project ."],
                  Stop=_FOREIGN_HOOK, SessionEnd=_FOREIGN_CAGEISH)
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
    assert verbs == ["graphify", "import-claude"], verbs
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
    # `graphify` (the top-level, pre-tiering spelling) maps to a REAL tail again: the
    # `data` group is still gone, but the interceptor door it fronted came back as
    # `cage interceptor graphify` (PG, v0.51), so an artifact carrying the adopt-era
    # spelling is healable rather than merely reportable.
    assert by_verb["graphify"].fix == "interceptor graphify"
    # `adopt` was removed outright, never renamed (and is absent from verbmap.REMOVED —
    # the reason detection uses the parser). No replacement may ever be invented for it.
    assert wiringscan.remediation(("adopt",)) == ""
    assert "no replacement" in wiringscan.Dead("x", "adopt", "", True).line


def test_a_freshly_wired_project_scans_clean(homes):
    """The handoff's §10 open question: a clean `cage setup` must produce zero
    findings — every verb cage emits today is parser-valid."""
    agents.install(homes, ("claude", "copilot", "kiro"))
    scan = wiringscan.run(homes, assets=False)
    assert scan.dead == [], [d.line for d in scan.dead]
    assert not scan.interceptor_dead


# ── heal ────────────────────────────────────────────────────────────────────────

def _snapshot(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): p.read_text(encoding="utf-8", errors="ignore")
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_install_heals_every_stale_artifact(homes):
    """Every artifact `agents.install` manages heals — a re-setup over a v0.27-era tree
    leaves no dead verb behind at all."""
    _plant_everything(homes)
    agents.install(homes, ("claude", "copilot", "kiro"))
    dead = wiringscan.run(homes, assets=False).dead
    assert dead == [], [d.line for d in dead]


def test_foreign_hooks_are_byte_identical_after_heal(homes):
    _plant_everything(homes)
    agents.install(homes, ("claude", "copilot", "kiro"))
    cmds = _claude_commands(homes)
    assert _FOREIGN_HOOK in cmds, f"a foreign hook was rewritten or dropped: {cmds}"
    assert _FOREIGN_CAGEISH in cmds, f"a cage-mentioning foreign hook was touched: {cmds}"


def test_second_install_is_byte_identical(homes):
    """Idempotence: healing a healed tree changes nothing (no mtime churn, no diff)."""
    _plant_everything(homes)
    agents.install(homes, ("claude", "copilot", "kiro"))
    before = _snapshot(homes)
    agents.install(homes, ("claude", "copilot", "kiro"))
    assert _snapshot(homes) == before


@posix_only
def test_graphify_shim_is_refreshed_then_left_alone(homes):
    from cage import adoptcmd
    _plant_everything(homes)
    assert adoptcmd.refresh_shim(homes) is True          # stale → rewritten
    assert adoptcmd.refresh_shim(homes) is False         # current → untouched
    body = (homes / "bin" / "graphify").read_text(encoding="utf-8")
    assert "cage interceptor graphify" in body and "cage graphify " not in body


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
    agents.install(homes, ("claude", "copilot", "kiro"))
    assert _check(doctorcmd.run(homes), "wiring")["level"] == "ok"


# NB: the stale-*asset* tests were removed with the rendered skill/prompt/steering
# assets and their byte-digest check (`wiringscan.stale_assets`). A dead *wired command*
# is now the only wiring fault — covered by `test_doctor_fails_on_dead_wiring_*` above.


# ── the scan changes no number ──────────────────────────────────────────────────

def test_derived_views_are_byte_identical(proj, capsys):
    """Determinism: this change touches detection and wiring only. A derived view must
    render byte-for-byte the same before and after a scan runs over the same project."""
    from cage import cli, demo
    demo.seed(proj)
    assert cli.main(["--ledger", str(proj), "insights", "chats"]) == 0
    before = capsys.readouterr().out
    wiringscan.run(proj)
    assert cli.main(["--ledger", str(proj), "insights", "chats"]) == 0
    assert capsys.readouterr().out == before


# ── P2.5a/5b: the inventory's bookkeeping ─────────────────────────────────────

def _wired(tmp_path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".cage").mkdir()
    agents.install(proj, hooks=True)
    return proj


def test_a_wired_hook_is_never_relisted_as_an_unexplained_leftover(tmp_path):
    """5a. `covered` collected the SPEC display (`".claude/settings.json (L1 hooks)"`)
    but `_leftover` matches against the raw enumeration's bare paths, so nothing ever
    matched and every wired hook command re-listed as an `other` row. Reproduced
    against this repo: four phantom `.claude/settings.json` rows plus kiro's."""
    proj = _wired(tmp_path)
    others = [a.display for a in wiringscan.inventory(proj).items
              if a.kind == "other" and a.scope == "project"]
    assert others == [], f"wired artifacts re-listed as leftovers: {others}"


def test_the_annotation_stripper_handles_kiros_singular_display(tmp_path):
    """5a's trap, pinned directly. kiro's spec display is `" (L1 hook)"` — SINGULAR —
    so the obvious `.removesuffix(" (L1 hooks)")` fixes claude and copilot and leaves
    kiro silently broken: two-of-three, the exact failure mode this repo keeps paying
    for. Any trailing parenthetical is stripped instead."""
    assert wiringscan._base_display(".kiro/hooks/cage.kiro.hook (L1 hook)") == \
        ".kiro/hooks/cage.kiro.hook"
    assert wiringscan._base_display(".claude/settings.json (L1 hooks)") == \
        ".claude/settings.json"
    assert wiringscan._base_display(".mcp.json") == ".mcp.json"
    # And every hook spec cage actually builds round-trips to a real enumerated path.
    proj = _wired(tmp_path)
    enumerated = {d for d, _ in wiringscan.committed_artifacts(proj)}
    for agent in agents.SURFACES:
        for spec in wiringscan._SPECS[agent](proj):
            if spec.kind == "hooks" and spec.present:
                assert wiringscan._base_display(spec.display) in enumerated, spec.display


def test_committed_enumeration_covers_every_committed_wired_file(tmp_path):
    """5b. `.github/hooks/cage.json` (copilot's REPO-level L1 hook) and
    `.kiro/settings/mcp.json` (the committed path-free MCP entry) were never walked, so
    a dead verb in either was invisible to the headline `wiring` check — in files a
    teammate inherits on clone, which is the whole reason they are committed."""
    proj = _wired(tmp_path)
    enumerated = {d for d, _ in wiringscan.committed_artifacts(proj)}
    assert {".github/hooks/cage.json", ".kiro/settings/mcp.json"} <= enumerated, enumerated


def test_a_dead_verb_in_copilots_repo_hook_is_now_visible(tmp_path):
    """The consequence of 5b, asserted where it bites: before, this scan came back
    clean and `cage doctor` reported OK while every copilot hook exited 1."""
    proj = _wired(tmp_path)
    path = proj / ".github" / "hooks" / "cage.json"
    data = cfgio.load_json(path)
    for entries in data["hooks"].values():
        for h in entries:
            h["bash"] = h["bash"].replace('cage-run" hook session-start',
                                          'cage-run" adopt')
    cfgio.save_json(path, data)

    dead = {d.artifact for d in wiringscan.run(proj).dead}
    assert ".github/hooks/cage.json" in dead, dead


def test_5b_did_not_reintroduce_5as_duplicate_rows(tmp_path):
    """The ordering constraint, made a test rather than a note: landing 5b first
    multiplies 5a's phantom leftovers, because the two files it adds are exactly the
    ones whose specs carry an annotated display."""
    proj = _wired(tmp_path)
    inv = wiringscan.inventory(proj)
    displays = [a.display for a in inv.items if a.kind == "other"]
    assert not any(d.startswith(".github/") or d.startswith(".kiro/") for d in displays), \
        displays
