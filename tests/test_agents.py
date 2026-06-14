"""Multi-agent wiring: claude / codex / copilot / kiro installers + MCP dispatch."""
from __future__ import annotations

import json

import pytest

from cage import agents, cfgio, mcpserver


@pytest.fixture
def homes(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude_home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex_home"))
    return tmp_path


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
    assert cfgio.load_json(proj / ".mcp.json")["mcpServers"]["cage"]["command"] == "cage"
    # Kiro + Copilot MCP configs
    assert "cage" in cfgio.load_json(proj / ".kiro" / "settings" / "mcp.json")["mcpServers"]
    assert "cage" in cfgio.load_json(proj / ".vscode" / "mcp.json")["servers"]
    # Codex TOML block (HOME-level)
    cfg = (homes / "codex_home" / "config.toml").read_text()
    assert "[mcp_servers.cage]" in cfg


def test_install_is_idempotent(homes):
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj, ("claude",))
    agents.install(proj, ("claude",))
    settings = cfgio.load_json(proj / ".claude" / "settings.json")
    assert len(settings["hooks"]["SessionEnd"]) == 1  # not duplicated


def test_install_selected_surface_only(homes):
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj, ("kiro",))
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


def test_setup_installs_global_asset_for_all_four(tmp_path, monkeypatch):
    from cage import setupcmd
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setenv("CAGE_VSCODE_USER", str(tmp_path / "vscode"))
    monkeypatch.setenv("KIRO_HOME", str(tmp_path / "kiro"))
    out = setupcmd.run()
    assert set(out) == {"claude", "codex", "copilot", "kiro"}
    assert (tmp_path / "claude" / "skills" / "cage" / "SKILL.md").exists()
    assert (tmp_path / "codex" / "skills" / "cage" / "SKILL.md").exists()
    assert (tmp_path / "vscode" / "prompts" / "cage.prompt.md").exists()
    assert (tmp_path / "kiro" / "steering" / "cage.md").exists()
