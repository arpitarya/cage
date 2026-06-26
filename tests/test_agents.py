"""Multi-agent wiring: claude / codex / copilot / kiro installers + MCP dispatch."""
from __future__ import annotations

import json

import pytest

from cage import agents, cfgio, mcpserver


@pytest.fixture
def homes(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude_home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex_home"))
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "copilot_home"))  # user-level hooks
    return tmp_path


def test_every_surface_has_a_wire_module():
    # Convention: one `<agent>wire.py` per agent, each exposing the standard interface.
    # A new agent must add its own wire file — this guards the convention.
    import importlib
    for surface in agents.SURFACES:
        wire = importlib.import_module(f"cage.{surface}wire")
        for fn in ("install", "status", "backfill_status", "realtime_status"):
            assert callable(getattr(wire, fn, None)), f"{surface}wire missing {fn}()"


def test_install_all_surfaces(homes):
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj)
    assert agents.status(proj) == {"claude": True, "codex": True,
                                   "copilot": True, "kiro": True}
    # Claude hooks + MCP
    settings = cfgio.load_json(proj / ".claude" / "settings.json")
    cmds = [h["command"] for e in settings["hooks"]["SessionEnd"] for h in e["hooks"]]
    assert "cage hook-session-end" in cmds
    # Stop = the real-time per-turn capture path
    stop = [h["command"] for e in settings["hooks"]["Stop"] for h in e["hooks"]]
    assert "cage hook-stop" in stop
    assert cfgio.load_json(proj / ".mcp.json")["mcpServers"]["cage"]["command"] == "cage"
    # Kiro + Copilot MCP configs
    assert "cage" in cfgio.load_json(proj / ".kiro" / "settings" / "mcp.json")["mcpServers"]
    assert "cage" in cfgio.load_json(proj / ".vscode" / "mcp.json")["servers"]
    # Each agent's hook imports ONLY its own log — no cross-agent sweep.
    # Copilot CLI hooks live at the USER level (~/.copilot/hooks), the only location the
    # local CLI fires from — agentStop (real-time) + sessionStart backfill.
    cop_hooks = cfgio.load_json(homes / "copilot_home" / "hooks" / "cage.json")["hooks"]
    for ev in ("agentStop", "sessionStart"):
        assert any(h["bash"] == "cage import --agent copilot --since 7d" for h in cop_hooks[ev])
    # Kiro Agent Hooks: real-time Stop + SessionStart backfill, Kiro only
    kiro_hooks = cfgio.load_json(proj / ".kiro" / "hooks" / "cage.kiro.hook")["hooks"]
    for trig in ("Stop", "SessionStart"):
        assert any(h["trigger"] == trig and h["action"]["command"] == "cage import --agent kiro"
                   for h in kiro_hooks)
    # All four now have BOTH real-time and backfill capture wired
    assert agents.realtime_status(proj) == {a: True for a in agents.SURFACES}
    assert agents.backfill_status(proj) == {a: True for a in agents.SURFACES}
    # Codex TOML block (HOME-level)
    cfg = (homes / "codex_home" / "config.toml").read_text()
    assert "[mcp_servers.cage]" in cfg


def test_copilot_hook_is_user_level_and_migrates_stale_repo_hook(homes):
    # Copilot's hook must live at the USER level (~/.copilot/hooks) — the repo-level
    # .github/hooks/cage.json does not fire for the local CLI. Re-wiring also strips a
    # stale repo-level cage hook left by a pre-fix install.
    from cage import copilotwire
    proj = homes / "proj"
    proj.mkdir()
    legacy = proj / ".github" / "hooks" / "cage.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"version":1,"hooks":{"agentStop":[{"type":"command",'
                      '"bash":"cage import --agent copilot --since 7d"}]}}', encoding="utf-8")
    copilotwire.install(proj)
    assert not legacy.exists()  # stale repo hook removed (cage owned it entirely)
    user_hook = homes / "copilot_home" / "hooks" / "cage.json"
    assert user_hook.exists()  # the firing location
    assert copilotwire.realtime_status(proj) is True


def test_copilot_migration_preserves_foreign_repo_hooks(homes):
    from cage import copilotwire, cfgio
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


def test_hooks_use_resolved_cage_path(homes, monkeypatch):
    # Hooks must carry the *resolved* cage path so GUI-launched agents (whose PATH omits
    # ~/.local/bin) can find it — a bare `cage` is the #1 reason a wired hook never fires.
    monkeypatch.setattr("cage.paths.cage_bin", lambda: "/opt/cage/bin/cage")
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj)
    s = cfgio.load_json(proj / ".claude" / "settings.json")["hooks"]
    assert s["Stop"][0]["hooks"][0]["command"] == "/opt/cage/bin/cage hook-stop"
    cx = cfgio.load_json(proj / ".codex" / "hooks.json")["hooks"]
    assert cx["Stop"][0]["hooks"][0]["command"] == "/opt/cage/bin/cage import --agent codex --since 7d"
    k = cfgio.load_json(proj / ".kiro" / "hooks" / "cage.kiro.hook")["hooks"]
    assert k[0]["action"]["command"] == "/opt/cage/bin/cage import --agent kiro"
    assert cfgio.load_json(proj / ".mcp.json")["mcpServers"]["cage"]["command"] == "/opt/cage/bin/cage"


def test_reinstall_heals_bare_cage_hook_without_duplicating(homes, monkeypatch):
    # An old install wired a bare `cage`; re-running setup must upgrade it to the
    # resolved path (so it fires under a GUI PATH) and not accumulate duplicates.
    proj = homes / "proj"
    proj.mkdir()
    monkeypatch.setattr("cage.paths.cage_bin", lambda: "cage")   # legacy bare install
    agents.install(proj, ("claude", "codex", "kiro"))
    monkeypatch.setattr("cage.paths.cage_bin", lambda: "/opt/cage/bin/cage")  # cage now resolves
    agents.install(proj, ("claude", "codex", "kiro"))            # re-run setup heals
    s = cfgio.load_json(proj / ".claude" / "settings.json")["hooks"]
    assert len(s["Stop"]) == 1 and len(s["SessionStart"]) == 2   # healed, not duplicated
    assert s["Stop"][0]["hooks"][0]["command"] == "/opt/cage/bin/cage hook-stop"
    cx = cfgio.load_json(proj / ".codex" / "hooks.json")["hooks"]
    assert len(cx["Stop"]) == 1
    assert cx["Stop"][0]["hooks"][0]["command"] == "/opt/cage/bin/cage import --agent codex --since 7d"


def test_reresolve_cage_command_leaves_foreign_hooks_alone():
    from cage import paths
    # only cage commands are rewritten; a foreign hook is never touched
    assert paths.reresolve_cage_command("npm run lint") is None
    assert paths.reresolve_cage_command("/abs/cage hook-stop") is not None


def test_setup_project_scope_writes_into_repo(homes):
    # scope="project" puts every agent's asset in the repo, never the machine home.
    from cage import setupcmd
    proj = homes / "proj"
    proj.mkdir()
    out = setupcmd.run(scope="project", root=proj)
    assert (proj / ".claude" / "skills" / "cage" / "SKILL.md").exists()
    assert (proj / ".codex" / "skills" / "cage" / "SKILL.md").exists()
    assert (proj / ".github" / "prompts" / "cage.prompt.md").exists()
    assert (proj / ".kiro" / "steering" / "cage.md").exists()
    # nothing leaked into the agent homes
    assert not (homes / "codex_home" / "skills" / "cage").exists()
    assert all(str(proj) in v for v in out.values())


def test_setup_project_scope_requires_root():
    from cage import setupcmd
    import pytest as _pytest
    with _pytest.raises(ValueError):
        setupcmd.run(("codex",), scope="project")


def test_install_is_idempotent(homes):
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj, ("claude",))
    agents.install(proj, ("claude",))
    settings = cfgio.load_json(proj / ".claude" / "settings.json")
    assert len(settings["hooks"]["SessionEnd"]) == 1  # not duplicated


def _start_cmds(settings: dict) -> list[str]:
    return [h["command"] for e in settings["hooks"]["SessionStart"] for h in e["hooks"]]


_CLAUDE_BACKFILL = "cage import-claude --project ."  # Claude only — no cross-agent sweep


def test_claude_sessionstart_backfill_before_banner(homes):
    # SessionStart backfills the previous Claude session, *then* prints the banner.
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj, ("claude",))
    cmds = _start_cmds(cfgio.load_json(proj / ".claude" / "settings.json"))
    assert _CLAUDE_BACKFILL in cmds  # Claude's own log only
    assert "cage hook-session-start" in cmds
    # the backfill runs before the banner so the banner reflects the just-imported spend
    assert cmds.index(_CLAUDE_BACKFILL) < cmds.index("cage hook-session-start")
    assert agents.backfill_status(proj)["claude"] is True


def test_claude_sessionstart_backfill_no_duplicate_on_reinstall(homes):
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj, ("claude",))
    agents.install(proj, ("claude",))
    cmds = _start_cmds(cfgio.load_json(proj / ".claude" / "settings.json"))
    assert cmds.count(_CLAUDE_BACKFILL) == 1
    assert cmds.count("cage hook-session-start") == 1


def test_codex_capture_hooks_wired_and_idempotent(homes):
    # Codex reads a project .codex/hooks.json (same schema/events as Claude) — wire the
    # real-time Stop hook + the SessionStart backfill, both running the import command.
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj, ("codex",))
    agents.install(proj, ("codex",))  # idempotent
    hooks = cfgio.load_json(proj / ".codex" / "hooks.json")["hooks"]
    imp = "cage import --agent codex --since 7d"  # Codex only — no cross-agent sweep
    for event in ("Stop", "SessionStart"):
        cmds = [h["command"] for e in hooks[event] for h in e["hooks"]]
        assert cmds == [imp]  # wired into each event exactly once
    assert agents.backfill_status(proj)["codex"] is True
    assert agents.realtime_status(proj)["codex"] is True  # real-time capture wired
    # the MCP read surface is still wired in the global config
    assert "[mcp_servers.cage]" in (homes / "codex_home" / "config.toml").read_text()


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
    assert agents.status(proj) == {"claude": False, "codex": False,
                                   "copilot": False, "kiro": False}


def test_adopt_surface_subset(homes):
    from cage import adoptcmd
    proj = homes / "proj"
    proj.mkdir()
    res = adoptcmd.run(proj, graphify=False, surfaces=("kiro",))
    assert set(res["hooks"]) == {"kiro"}
    s = agents.status(proj)
    assert s["kiro"] is True and s["claude"] is False


def test_wizard_apply_wires_one_agent_and_skill(homes, monkeypatch):
    # The `cage setup` wizard's apply() routes project+skill through the same
    # idempotent primitives; flagged path picks exactly one surface.
    from cage import wizard
    monkeypatch.setenv("CAGE_VSCODE_USER", str(homes / "vscode"))
    monkeypatch.setenv("KIRO_HOME", str(homes / "kiro_home"))
    proj = homes / "proj"
    proj.mkdir()
    log = wizard.apply(proj, agent="claude", skill=True, project=True, graphify=False)
    s = agents.status(proj)
    assert s["claude"] is True and s["codex"] is False
    assert any("metering + MCP wired" in line for line in log)
    assert any("global skill" in line for line in log)


def test_wizard_apply_all_wires_every_agent(homes, monkeypatch):
    # agent="all" (the wizard default) wires every surface in one go.
    from cage import wizard
    monkeypatch.setenv("CAGE_VSCODE_USER", str(homes / "vscode"))
    monkeypatch.setenv("KIRO_HOME", str(homes / "kiro_home"))
    proj = homes / "proj"
    proj.mkdir()
    log = wizard.apply(proj, agent="all", skill=True, project=True, graphify=False)
    assert agents.status(proj) == {a: True for a in agents.SURFACES}  # all four wired
    assert any("all agents metering + MCP wired" in line for line in log)


def test_wizard_apply_skill_only_skips_project(homes):
    from cage import wizard
    proj = homes / "proj"
    proj.mkdir()
    log = wizard.apply(proj, agent="codex", skill=True, project=False, graphify=False)
    assert agents.status(proj)["codex"] is False  # no per-project wiring
    assert not (proj / ".cage").exists()           # init never ran
    assert any("global skill" in line for line in log)


def test_wizard_interactive_plan_defaults_to_all(monkeypatch):
    # empty agent answer → "all" (option 1), the default — capture for every agent.
    from cage import wizard
    answers = iter(["", "n", "y", "n"])  # default agent · no skill · yes project · no graphify
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))
    assert wizard.interactive_plan() == {
        "agent": "all", "skill": False, "skill_scope": "global",
        "project": True, "graphify": False}


def test_wizard_interactive_plan_parses_answers(monkeypatch):
    from cage import wizard
    # options are ("all", claude, codex, copilot, kiro) → "3" = codex
    answers = iter(["3", "n", "y", "n"])  # codex · no skill · yes project · no graphify
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))
    assert wizard.interactive_plan() == {
        "agent": "codex", "skill": False, "skill_scope": "global",
        "project": True, "graphify": False}


def test_wizard_interactive_plan_skill_scope_defaults_to_project(monkeypatch):
    # codex (option 3) · yes skill · empty scope (→ default) · empty project · empty graphify
    from cage import wizard
    answers = iter(["3", "y", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))
    plan = wizard.interactive_plan()
    assert plan["agent"] == "codex" and plan["skill"] is True
    assert plan["skill_scope"] == "project"   # repo-level is the default
    assert plan["project"] is True            # scaffold default stays yes
    assert plan["graphify"] is False          # graphify default is now no


def test_wizard_interactive_plan_skill_scope_global_explicit(monkeypatch):
    # choosing scope option 2 still selects global
    from cage import wizard
    answers = iter(["3", "y", "2", "y", "n"])
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))
    assert wizard.interactive_plan()["skill_scope"] == "global"


def test_wizard_apply_installs_repo_level_codex_skill(homes):
    from cage import wizard
    proj = homes / "proj"
    proj.mkdir()
    log = wizard.apply(proj, agent="codex", skill=True, project=False,
                       graphify=False, skill_scope="project")
    # Skill lands in the repo, not the codex home; logged as a repo skill.
    assert (proj / ".codex" / "skills" / "cage" / "SKILL.md").exists()
    assert not (homes / "codex_home" / "skills" / "cage").exists()
    assert any("repo skill" in line for line in log)


def test_wizard_prompt_yes_no_default_and_reject(monkeypatch):
    from cage import wizard
    monkeypatch.setattr("builtins.input", lambda *a: "")       # empty → default
    assert wizard.prompt_yes_no("ok?", default=True) is True
    monkeypatch.setattr("builtins.input", lambda *a: "no")
    assert wizard.prompt_yes_no("ok?", default=True) is False


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


def test_setup_installs_global_asset_for_all_four(tmp_path, monkeypatch):
    from cage import setupcmd
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setenv("CAGE_VSCODE_USER", str(tmp_path / "vscode"))
    monkeypatch.setenv("KIRO_HOME", str(tmp_path / "kiro"))
    out = setupcmd.run()
    # Both skills (cage + cage-doctor) ship to all four agents — namespaced keys.
    assert set(out) == {
        "claude:cage", "codex:cage", "copilot:cage", "kiro:cage",
        "claude:cage-doctor", "codex:cage-doctor", "copilot:cage-doctor", "kiro:cage-doctor",
    }
    assert (tmp_path / "claude" / "skills" / "cage" / "SKILL.md").exists()
    assert (tmp_path / "codex" / "skills" / "cage" / "SKILL.md").exists()
    assert (tmp_path / "vscode" / "prompts" / "cage.prompt.md").exists()
    assert (tmp_path / "kiro" / "steering" / "cage.md").exists()
    # The new doctor skill is installed for every agent too.
    assert (tmp_path / "claude" / "skills" / "cage-doctor" / "SKILL.md").exists()
    assert (tmp_path / "vscode" / "prompts" / "cage-doctor.prompt.md").exists()
    assert (tmp_path / "kiro" / "steering" / "cage-doctor.md").exists()
