"""Configurable import paths — the `[sources]` policy table (plan Phase 4).

The two must-never-skip tests are first: **empty-`[sources]` byte-identity** (capture
is byte-for-byte unchanged for everyone who doesn't use it) and the **full precedence
matrix** (env home override > policy > built-in, replace/disabled, dedup). Then
expansion, custom-tool end-to-end (a fixture log at a policy path → rows stamped with
the tool name, reports split by it), cursor incrementality on a policy path, the
portability warn/no-warn guard, and `policy sync` ownership.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from cage import (agents, importcmd, ledger, paths, pathprobe, policy, policysync,
                  report)


def _imp_args(agent="all", path=None, project=None, since=None):
    return SimpleNamespace(agent=agent, path=path, project=project, since=since)


def _claude_line(uuid, tin, tout, cwd="/Users/me/my_programs/widget"):
    return json.dumps({"type": "assistant", "uuid": uuid, "cwd": cwd,
                       "timestamp": "2026-06-14T10:00:00Z",
                       "message": {"model": "claude-opus-4-8",
                                   "usage": {"input_tokens": tin, "output_tokens": tout}}})


_HOME_ENVS = ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_HOME",
              "KIRO_DATA_DIR", "CAGE_VSCODE_USER")


def _isolate_homes(d, monkeypatch):
    """Point every agent home at a throwaway dir so a pathless sweep never reads the
    developer's real logs — hermetic + deterministic (import tests). Note: this sets
    the home env overrides, so built-in candidates resolve with `env` provenance."""
    for env in _HOME_ENVS:
        monkeypatch.setenv(env, str(d / f"home-{env.lower()}"))


def _no_env(monkeypatch):
    """Clear every home env override so built-in candidates carry `built-in`
    provenance — the baseline for the provenance/precedence assertions. The resolver
    never touches disk, so leaving homes at their real defaults is safe here."""
    for env in _HOME_ENVS:
        monkeypatch.delenv(env, raising=False)


def _write_policy(root, body: str):
    base = root / ".cage"
    base.mkdir(parents=True, exist_ok=True)
    (base / "policy.toml").write_text(body, encoding="utf-8")


# ── MUST-NEVER-SKIP 1: empty/absent [sources] is byte-identical to the built-ins ──

def test_empty_sources_is_byte_identical_to_builtin_registry(monkeypatch):
    _no_env(monkeypatch)
    for pol in ({}, {"sources": {}}):  # no key, and an empty [sources] table
        res = paths.resolve_log_sources(pol)
        assert res.problems == [] and res.disabled == []
        for agent in agents.SURFACES:
            got = [(s.path, s.glob) for s in res.sources if s.agent == agent]
            assert got == paths._builtin_log_sources(agent), agent
            assert all(s.provenance == "built-in"
                       for s in res.sources if s.agent == agent)
    # The legacy per-agent accessor is unchanged with no policy.
    assert len(paths.agent_log_sources("copilot")) == 2


def test_empty_sources_import_is_identical_to_no_sources_key(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    # Plant one claude log in the isolated claude home so a real sweep captures it.
    cl = tmp_path / "home-claude_config_dir" / "projects" / "p"
    cl.mkdir(parents=True)
    (cl / "session-x.jsonl").write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")

    def _capture(body):
        root = tmp_path / body[:4]
        _write_policy(root, body)
        monkeypatch.chdir(root)
        importcmd.run(root, "all", _imp_args())
        return paths.Footprint(root).calls.read_bytes() if paths.Footprint(root).calls.exists() \
            else b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls"))

    no_key = _capture("# no sources table\n")
    empty = _capture("[sources]\n")
    assert no_key and no_key == empty  # same rows, byte-for-byte


# ── MUST-NEVER-SKIP 2: the full precedence matrix ─────────────────────────────

def test_precedence_env_beats_policy_beats_builtin(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    # env home override on codex only → its built-in candidate is tagged `env`;
    # claude keeps `built-in`.
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-redirected"))
    add = tmp_path / "extra-claude"
    pol = {"sources": {"claude": {"paths": [str(add)]}}}
    res = paths.resolve_log_sources(pol)

    claude = [s for s in res.sources if s.agent == "claude"]
    assert [s.provenance for s in claude] == ["built-in", "policy"]  # built-in first, add second
    assert claude[1].path == add and claude[1].fmt == "claude"
    codex = [s for s in res.sources if s.agent == "codex"]
    assert codex and all(s.provenance == "env" for s in codex)  # redirected home ⇒ env


def test_replace_drops_builtins_and_empty_disables(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    only = tmp_path / "only-codex"
    pol = {"sources": {
        "codex": {"paths": [str(only)], "replace": True},   # replace built-ins
        "kiro": {"paths": [], "replace": True},              # disable entirely
    }}
    res = paths.resolve_log_sources(pol)
    codex = [s for s in res.sources if s.agent == "codex"]
    assert [s.path for s in codex] == [only] and codex[0].provenance == "policy"
    assert not [s for s in res.sources if s.agent == "kiro"]
    assert res.disabled == ["kiro"]


def test_policy_path_equal_to_builtin_dedupes_to_builtin(monkeypatch):
    _no_env(monkeypatch)
    builtin_dir = paths._builtin_log_sources("claude")[0][0]  # ~/.claude/projects
    pol = {"sources": {"claude": {"paths": [str(builtin_dir)]}}}
    claude = [s for s in paths.resolve_log_sources(pol).sources if s.agent == "claude"]
    assert len(claude) == 1 and claude[0].provenance == "built-in"  # deduped, keeps built-in


# ── expansion, validation ─────────────────────────────────────────────────────

def test_tilde_and_env_var_expand(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    monkeypatch.setenv("MYLOGS", str(tmp_path / "shared"))
    pol = {"sources": {"claude": {"paths": ["~/alt", "$MYLOGS/claude"]}}}
    added = [s for s in paths.resolve_log_sources(pol).sources
             if s.agent == "claude" and s.provenance == "policy"]
    assert added[0].path == paths.Path.home() / "alt"
    assert added[1].path == tmp_path / "shared" / "claude"
    assert added[0].raw == "~/alt"  # raw kept for the portability check


def test_glob_entry_rejected_as_problem(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    pol = {"sources": {"claude": {"paths": ["/logs/*.jsonl"]}}}
    res = paths.resolve_log_sources(pol)
    assert not [s for s in res.sources if s.provenance == "policy"]
    assert any("glob" in p for p in res.problems)


def test_custom_tool_needs_format_and_reserved_names(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    # missing format → rejected, contributes nothing
    res = paths.resolve_log_sources({"sources": {"mytool": {"paths": ["/x"]}}})
    assert any("format" in p for p in res.problems)
    assert not paths.custom_tool_sources({"sources": {"mytool": {"paths": ["/x"]}}})
    # a bad format value is also rejected — the tool contributes no sources
    bad = paths.resolve_log_sources({"sources": {"t": {"paths": ["/x"], "format": "grok"}}})
    assert bad.problems and not [s for s in bad.sources if s.agent == "t"]


# ── custom-tool import end-to-end ─────────────────────────────────────────────

def test_custom_tool_imports_and_stamps_agent_name(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    logs = tmp_path / "router-logs"
    logs.mkdir()
    (logs / "session-r1.jsonl").write_text(_claude_line("cu1", 200, 40) + "\n",
                                           encoding="utf-8")
    root = tmp_path / "proj"
    _write_policy(root, f'[sources.myrouter]\npaths = ["{logs}"]\nformat = "claude"\n')
    monkeypatch.chdir(root)

    lines = importcmd.run(root, "all", _imp_args())
    rows = ledger.calls(root)
    assert rows and all(r["agent"] == "myrouter" for r in rows)  # stamped with the tool name
    assert any("myrouter (custom, format=claude)" in ln for ln in lines)

    # reports split by the tool name.
    rep = report.summarize(root, policy.load(paths.Footprint(root).policy), dim="agent")
    assert "myrouter" in rep["groups"]


def test_custom_tool_cursor_incremental(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    logs = tmp_path / "rl"
    logs.mkdir()
    (logs / "s.jsonl").write_text(_claude_line("c1", 10, 5) + "\n", encoding="utf-8")
    root = tmp_path / "proj"
    _write_policy(root, f'[sources.myrouter]\npaths = ["{logs}"]\nformat = "claude"\n')
    monkeypatch.chdir(root)

    importcmd.run(root, "all", _imp_args())
    assert len(ledger.calls(root)) == 1
    cur = json.loads(paths.Footprint(root).cursors.read_text())
    assert "myrouter" in cur and str(logs / "s.jsonl") in cur["myrouter"]  # own cursor bucket
    importcmd.run(root, "all", _imp_args())  # unchanged file → skip
    assert len(ledger.calls(root)) == 1


# ── portability guard ─────────────────────────────────────────────────────────

def _probe(root, pol, monkeypatch, *, committed):
    monkeypatch.setattr(pathprobe, "_git_tracked", lambda *a, **k: committed)
    return pathprobe.probe(root, pol)


def test_portability_warns_only_on_committed_machine_absolute_project_path(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    abs_pol = {"sources": {"claude": {"paths": ["/Users/dev/logs"]}}}
    tilde_pol = {"sources": {"claude": {"paths": ["~/logs"]}}}

    warns = _probe(root, abs_pol, monkeypatch, committed=True)["portability"]
    assert warns and "machine-absolute" in warns[0]
    assert not _probe(root, tilde_pol, monkeypatch, committed=True)["portability"]  # ~ exempt
    assert not _probe(root, abs_pol, monkeypatch, committed=False)["portability"]   # uncommitted exempt


def test_portability_never_warns_for_global_policy(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    # No project .cage/ → active sink is global (~/.cage), which is per-machine by nature.
    fresh = tmp_path / "no-project"
    fresh.mkdir()
    monkeypatch.chdir(fresh)
    abs_pol = {"sources": {"claude": {"paths": ["/Users/dev/logs"]}}}
    assert not _probe(fresh, abs_pol, monkeypatch, committed=True)["portability"]


def test_doctor_paths_shows_provenance_and_disabled(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    pol = {"sources": {"claude": {"paths": ["~/alt"]},
                       "kiro": {"paths": [], "replace": True}}}
    out = pathprobe.run(root, pol)
    # homes are env-redirected here, so built-ins read as [env]; the point is that
    # every candidate carries *a* provenance tag and the policy add reads [policy].
    assert "[policy]" in out and ("[built-in]" in out or "[env]" in out)
    assert "disabled by policy" in out
    assert "provenance: built-in" in out  # the legend line


# ── policy sync ownership ─────────────────────────────────────────────────────

def test_bundle_ships_no_sources_table():
    assert "sources" not in policy.bundled_raw()  # asserted invariant


def test_policy_sync_never_touches_sources(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    root = tmp_path / "proj"
    _write_policy(root, '[meta]\npolicy_version = "0.25"\n\n'
                        '[sources.claude]\npaths = ["~/alt"]\n')
    monkeypatch.chdir(root)
    d = policysync.sync_view(root)
    flat = json.dumps(d)
    assert "sources" not in flat  # never in add/update/customized/orphan/project_own
