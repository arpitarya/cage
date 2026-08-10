"""Multi-agent wiring: claude / copilot / kiro installers + MCP dispatch.

Capture is pull-based (`cage import` / capture-on-read), so MCP is the only wired
surface. `install` writes the MCP entry (referencing the committed shim on committed
files) and *heals* — strips/deletes any hook artifacts a pre-removal version wrote.
"""
from __future__ import annotations

import json

import pytest

from cage import agents, cfgio, mcpserver


@pytest.fixture
def homes(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude_home"))
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "copilot_home"))  # user-level heal target
    return tmp_path


def test_every_surface_has_a_wire_module():
    # Convention: one `<agent>wire.py` per agent, each exposing the standard interface
    # (hookless: install + status only). A new agent must add its own wire file.
    import importlib
    for surface in agents.SURFACES:
        wire = importlib.import_module(f"cage.{surface}wire")
        for fn in ("install", "status"):
            assert callable(getattr(wire, fn, None)), f"{surface}wire missing {fn}()"


def test_install_all_surfaces(homes):
    from cage import runshim
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj)
    assert agents.status(proj) == {"claude": True, "copilot": True, "kiro": True}
    # The committed shim is written alongside the wiring (both twins, plan §5).
    assert (proj / ".cage" / "bin" / "cage-run").exists()
    assert (proj / ".cage" / "bin" / "cage-run.cmd").exists()
    # Claude MCP — committed file references the shim, never a binary path.
    assert (cfgio.load_json(proj / ".mcp.json")["mcpServers"]["cage"]["command"]
            == f"${{CLAUDE_PROJECT_DIR:-.}}/{runshim.SHIM_REL}")
    # Copilot MCP (VS Code) references the workspace-relative shim.
    vs = cfgio.load_json(proj / ".vscode" / "mcp.json")["servers"]
    assert vs["cage"]["command"] == f"${{workspaceFolder}}/{runshim.SHIM_REL}"
    # Kiro MCP stays absolute (Kiro spawns servers from its install dir — the ONE
    # documented portability exception; gitignore-advised).
    assert "cage" in cfgio.load_json(proj / ".kiro" / "settings" / "mcp.json")["mcpServers"]
    # No hooks are ever wired now — capture is pull-based.
    assert not (proj / ".claude" / "settings.json").exists() or \
        "hooks" not in cfgio.load_json(proj / ".claude" / "settings.json")


def test_copilot_install_strips_stale_repo_hook(homes):
    # A pre-removal `.github/hooks/cage.json` is wholly cage-owned → stripped; the MCP
    # entry is what install now writes.
    from cage import copilotwire
    proj = homes / "proj"
    proj.mkdir()
    legacy = proj / ".github" / "hooks" / "cage.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"version":1,"hooks":{"agentStop":[{"type":"command",'
                      '"bash":"cage import --agent copilot --since 7d"}]}}', encoding="utf-8")
    copilotwire.install(proj)
    assert not legacy.exists()  # stale repo hook removed (cage owned it entirely)
    assert copilotwire.status(proj) is True  # MCP wired


def test_copilot_migration_preserves_foreign_repo_hooks(homes):
    from cage import cfgio, copilotwire
    proj = homes / "proj"
    proj.mkdir()
    legacy = proj / ".github" / "hooks" / "cage.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"version":1,"hooks":{"sessionStart":[{"type":"command",'
                      '"bash":"npm run lint"},{"type":"command","bash":"cage import --agent all --project . --since 7d"}]}}',
                      encoding="utf-8")
    copilotwire.install(proj)
    kept = cfgio.load_json(legacy)["hooks"]["sessionStart"]  # foreign hook survives
    assert [h["bash"] for h in kept] == ["npm run lint"]


def test_committed_wiring_never_carries_resolved_path(homes, monkeypatch):
    # Even when cage resolves to an absolute path on THIS machine, EVERY committed file
    # must be machine-independent. Claude/Copilot reach that through the shim; Kiro,
    # which resolves neither a relative path nor a variable, reaches it by carrying no
    # path at all (`python3 -m cage mcp`) — the last exception, closed.
    from cage import kirowire, runshim
    monkeypatch.setattr("cage.paths.cage_bin", lambda: "/opt/cage/bin/cage")
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj)
    assert (cfgio.load_json(proj / ".mcp.json")["mcpServers"]["cage"]["command"]
            == f"${{CLAUDE_PROJECT_DIR:-.}}/{runshim.SHIM_REL}")
    vs = cfgio.load_json(proj / ".vscode" / "mcp.json")["servers"]
    assert vs["cage"]["command"] == f"${{workspaceFolder}}/{runshim.SHIM_REL}"
    kiro = cfgio.load_json(proj / ".kiro" / "settings" / "mcp.json")["mcpServers"]["cage"]
    assert kiro == kirowire.PATH_FREE
    # No committed file names this machine's cage, in any of the three.
    for rel in (".mcp.json", ".vscode/mcp.json", ".kiro/settings/mcp.json"):
        assert "/opt/cage/bin/cage" not in (proj / rel).read_text(encoding="utf-8")


def test_reinstall_migrates_legacy_absolute_mcp_and_strips_hooks(homes):
    # An old install wired the machine's absolute cage path into `.mcp.json` and left
    # cage hooks in `.claude/settings.json`; re-running setup migrates the MCP entry to
    # the shim (portable, reported) and strips the stale hooks — no duplicates.
    from cage import runshim
    proj = homes / "proj"
    proj.mkdir()
    settings = proj / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {
        "Stop": [{"hooks": [{"type": "command", "command": "/opt/cage/bin/cage hook-stop"}]}],
    }}), encoding="utf-8")
    mcp = proj / ".mcp.json"
    mcp.write_text(json.dumps({"mcpServers": {"cage": {"command": "/opt/cage/bin/cage",
                                                       "args": ["mcp"]}}}), encoding="utf-8")
    out = agents.install(proj, ("claude",))
    assert (cfgio.load_json(mcp)["mcpServers"]["cage"]["command"]
            == f"${{CLAUDE_PROJECT_DIR:-.}}/{runshim.SHIM_REL}")   # migrated to shim
    assert "migrated" in out["claude"]                            # migration is reported
    # the stale cage hook is gone (foreign hooks would survive)
    data = cfgio.load_json(settings)
    assert not data.get("hooks", {}).get("Stop")
    # second run: already portable — nothing further migrates
    out2 = agents.install(proj, ("claude",))
    assert "migrated" not in out2.get("claude", {})


def test_reresolve_cage_command_leaves_foreign_hooks_alone():
    from cage import paths
    # only cage commands are rewritten; a foreign hook is never touched
    assert paths.reresolve_cage_command("npm run lint") is None
    assert paths.reresolve_cage_command("/abs/cage mcp") is not None


def test_install_is_idempotent(homes):
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj, ("claude",))
    before = (proj / ".mcp.json").read_bytes()
    agents.install(proj, ("claude",))
    assert (proj / ".mcp.json").read_bytes() == before  # not duplicated / churned


def test_install_selected_surface_only(homes):
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj, ("kiro",))
    s = agents.status(proj)
    assert s["kiro"] is True and s["claude"] is False


def test_adopt_no_surface_skips_all_wiring(homes):
    # Agent wiring is opt-in: plain `cage adopt` scaffolds but touches no agent.
    from cage import adoptcmd
    proj = homes / "proj"
    proj.mkdir()
    res = adoptcmd.run(proj, graphify=False)  # no PATH/shim mutation in tests
    assert "hooks" not in res
    assert agents.status(proj) == {"claude": False, "copilot": False, "kiro": False}


def test_adopt_surface_subset(homes):
    from cage import adoptcmd
    proj = homes / "proj"
    proj.mkdir()
    res = adoptcmd.run(proj, graphify=False, surfaces=("kiro",))
    assert set(res["hooks"]) == {"kiro"}
    s = agents.status(proj)
    assert s["kiro"] is True and s["claude"] is False


def test_mcp_tools_list_and_call(seeded, monkeypatch):
    root, _ = seeded
    monkeypatch.chdir(root)
    listed = mcpserver._handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {t["name"] for t in listed["result"]["tools"]}
    assert {"cage_report", "cage_attrib", "cage_budget", "cage_why"} <= names
    called = mcpserver._handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                "params": {"name": "cage_report", "arguments": {}}})
    assert "Ledger by route" in called["result"]["content"][0]["text"]


def test_mcp_unknown_method_errors():
    r = mcpserver._handle({"jsonrpc": "2.0", "id": 9, "method": "bogus"})
    assert r["error"]["code"] == -32601


# ── a hook file cage did not write: refuse, never crash, never delete ──────────
#
# P2.4. `{"hooks": {"sessionStart": ["cage import"]}}` — a plausible hand edit — crashed
# `cage setup`, `cage setup --status` and `cage doctor --wiring` alike with
# `AttributeError: 'str' object has no attribute 'get'`, at SIX sites. The sharper half
# was silent: a non-dict `hooks` VALUE was coerced to `{}`, fell through to
# `path.unlink()` on the DEFAULT (`--no-hooks`) setup path, and took every other
# top-level key in the user's file with it.
#
# The fix has to keep two invariants that pull in opposite directions, which is why
# "nothing left to preserve" and "a shape I don't understand" are now different
# branches: `test_copilot_migration_removes_stale_repo_hook` above requires the unlink
# to STILL fire when only cage's own entries were there, and
# `test_copilot_migration_preserves_foreign_repo_hooks` requires foreign entries to
# survive. Both stay green.

_FOREIGN = {"version": 1, "myTeamSettings": {"keep": "me"}}


def _copilot_hookfile(proj, hooks):
    from cage import cfgio
    path = proj / ".github" / "hooks" / "cage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    cfgio.save_json(path, {**_FOREIGN, "hooks": hooks})
    return path


def test_a_non_dict_hooks_table_is_left_alone_not_deleted(homes, capsys):
    """The data-loss path, and it ran on the DEFAULT setup path (`hooks=False`).
    Emptiness is a conclusion cage may only draw about a shape it actually read."""
    from cage import copilotwire
    proj = homes / "proj"
    proj.mkdir()
    path = _copilot_hookfile(proj, "not-a-dict")
    before = path.read_bytes()

    assert copilotwire._wire_hooks(proj, False) == 0     # the default `cage setup` path
    assert path.exists(), "cage deleted a file whose shape it never understood"
    assert path.read_bytes() == before                   # and did not rewrite it either
    assert copilotwire._wire_hooks(proj, True) == 0      # --hooks refuses too
    assert path.read_bytes() == before
    # Fail-open, but never silent.
    assert "left" in capsys.readouterr().err


def test_a_non_dict_hook_entry_is_preserved_as_foreign_not_crashed_on(homes):
    """cage only ever writes `{"bash": …}`, so a bare string is foreign BY
    CONSTRUCTION — it must be kept, which is exactly what makes the file non-empty and
    keeps the unlink from firing."""
    from cage import cfgio, copilotwire
    proj = homes / "proj"
    proj.mkdir()
    path = _copilot_hookfile(proj, {"sessionStart": ["cage import"]})

    assert copilotwire._wire_hooks(proj, True) == len(agents.HOOK_EVENTS["copilot"])
    assert copilotwire.hook_status(proj) == len(agents.HOOK_EVENTS["copilot"])
    # Unwiring returns the file to exactly what it was — foreign key and entry intact.
    assert copilotwire._wire_hooks(proj, False) == 0
    data = cfgio.load_json(path)
    assert data["myTeamSettings"] == {"keep": "me"}
    assert data["hooks"]["sessionStart"] == ["cage import"]


def test_claude_settings_survive_a_hook_shape_cage_never_wrote(homes):
    """`.claude/settings.json` is the USER's file, not cage's, so coercing an
    unreadable `hooks` value would have `data.pop("hooks")` strip a table cage never
    understood."""
    from cage import cfgio, claudewire
    proj = homes / "proj"
    (proj / ".claude").mkdir(parents=True)
    settings = proj / ".claude" / "settings.json"
    cfgio.save_json(settings, {"permissions": {"allow": ["Bash"]},
                               "hooks": {"SessionStart": ["cage import"]}})
    before = settings.read_bytes()

    # The non-dict ENTRY case: cage wires around it, then unwires back to the byte.
    assert claudewire._wire_hooks(proj, True) == len(agents.HOOK_EVENTS["claude"])
    assert claudewire.hook_status(proj) == len(agents.HOOK_EVENTS["claude"])
    assert cfgio.load_json(settings)["permissions"] == {"allow": ["Bash"]}
    assert claudewire._wire_hooks(proj, False) == 0
    assert settings.read_bytes() == before

    # The non-dict TABLE case: refuse outright.
    cfgio.save_json(settings, {"permissions": {"allow": ["Bash"]}, "hooks": "nope"})
    guarded = settings.read_bytes()
    assert claudewire._wire_hooks(proj, True) == 0
    assert settings.read_bytes() == guarded


def test_setup_and_status_survive_a_hand_edited_hook_file(homes, monkeypatch, capsys):
    """End to end through the real front door — `cage setup` and `cage setup --status`
    both walked straight into the AttributeError."""
    from cage import cli
    proj = homes / "proj"
    proj.mkdir()
    (proj / ".cage").mkdir()
    _copilot_hookfile(proj, {"sessionStart": ["cage import"]})
    monkeypatch.chdir(proj)

    for argv in (["setup", "--all", "--wire-only", "--hooks"],
                 ["setup", "--status"],
                 ["setup", "--all", "--wire-only"]):
        args = cli.build_parser().parse_args(argv)
        assert args.fn(args) == 0, argv
    capsys.readouterr()
