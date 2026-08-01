"""`cage import [--agent ...]` — unified hookless metering across all three agents.

Claude + Copilot import on-disk usage logs; Kiro (no usage log) prints the
proxy fallback. Every surface in agents.SURFACES is reachable and first-class.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from cage import agents, clicmds, importcmd, ledger, paths
from srcseed import mkcage


def _args(agent="all", path=None, project=None, since=None):
    return SimpleNamespace(agent=agent, path=path, project=project, since=since)


def _init_root(d, monkeypatch):
    mkcage(d)
    # Isolate every agent home so a default (path-less) import never reads real machine
    # data (~/.claude, ~/.copilot, Kiro's user-data dir).
    for env in ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(d / f"home-{env.lower()}"))
    monkeypatch.chdir(d)
    return d


def _claude_line(uuid, tin, tout):
    return json.dumps({"type": "assistant", "uuid": uuid, "timestamp": "2026-06-14T10:00:00Z",
                       "message": {"model": "claude-opus-4-8",
                                   "usage": {"input_tokens": tin, "output_tokens": tout}}})


# --- the loud per-agent×surface import rollup (plan §2.2) ----------------------

def test_import_rollup_hand_derived_reference():
    """Assert `_import_rollup` against a hand-computed reference (cage-lab discipline):
    two priced claude turns + one UNPRICED copilot/auto vscode row → exact per-bucket and
    total lines, with the unpriced row surfacing as UNPRICED, never a silent $0."""
    from cage import policy, schema
    pol = policy.load(None)  # bundled prices (anthropic rows present)
    rows = [
        schema.make_call(route="chat", provider="anthropic", model="claude-opus-4-8",
                         tokens_in=1000, tokens_out=200, cached_in=0, agent="claude-code"),
        schema.make_call(route="chat", provider="anthropic", model="claude-opus-4-8",
                         tokens_in=2000, tokens_out=100, cached_in=0, agent="claude-code"),
        schema.make_call(route="chat", provider="", model="copilot/auto",
                         tokens_in=500, tokens_out=50, agent="copilot", surface="vscode"),
    ]
    lines = importcmd._import_rollup(rows, pol, deduped=0)
    text = "\n".join(lines)
    # claude bucket: 2 calls, 3000 in, 300 out, priced (a real $ figure, not UNPRICED)
    claude_line = next(l for l in lines if l.strip().startswith("claude"))
    assert "3,000" in claude_line and "300" in claude_line
    assert "$" in claude_line and "UNPRICED" not in claude_line
    # copilot/auto bucket: 1 call, UNPRICED (never $0)
    cop_line = next(l for l in lines if "vscode" in l)
    assert "UNPRICED (copilot/auto)" in cop_line
    # total row: 3 calls, 3500 in, 350 out, and the unpriced count is surfaced
    total_line = next(l for l in lines if l.strip().startswith("total"))
    assert "3,500" in total_line and "350" in total_line and "(1 unpriced)" in total_line


def test_import_rollup_empty_is_quiet():
    from cage import policy
    assert importcmd._import_rollup([], policy.load(None), deduped=0) == []


# --- consumer capture switches ------------------------------------------------

def test_capture_switch_env_overrides_policy(monkeypatch):
    from cage import policy
    monkeypatch.delenv("CAGE_CAPTURE", raising=False)
    assert policy.capture_enabled({}) is True                            # default on
    assert policy.capture_enabled({"capture": {"enabled": False}}) is False
    monkeypatch.setenv("CAGE_CAPTURE", "0")                              # env beats policy
    assert policy.capture_enabled({"capture": {"enabled": True}}) is False
    monkeypatch.setenv("CAGE_CAPTURE", "1")
    assert policy.capture_enabled({"capture": {"enabled": False}}) is True


def test_import_agent_scoped_pulls_only_that_agent(tmp_path, monkeypatch):
    # `cage import --agent claude --path <file>` records Claude's turn and never sweeps
    # another agent's log (the Stop hook that used to guarantee this is gone; the
    # agent-scoped pull import is the surviving guarantee).
    root = _init_root(tmp_path, monkeypatch)             # isolates COPILOT_HOME etc.
    cx = tmp_path / "home-copilot_home" / "session-state" / "s" / "events.jsonl"
    cx.parent.mkdir(parents=True)
    cx.write_text('{"foreign": "log"}\n', encoding="utf-8")  # would be swept, if we swept
    tp = tmp_path / "live.jsonl"
    tp.write_text(_claude_line("u1", 100, 40) + "\n", encoding="utf-8")
    clicmds.cmd_import(_args(agent="claude", path=str(tp)))
    assert {c["agent"] for c in ledger.calls(root)} == {"claude-code"}   # copilot NOT pulled in


def test_import_skipped_when_capture_disabled(tmp_path, monkeypatch, capsys):
    root = _init_root(tmp_path, monkeypatch)
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    monkeypatch.setenv("CAGE_CAPTURE", "0")                              # consumer pauses capture
    assert clicmds.cmd_import(_args(agent="claude", path=str(tp))) == 0
    assert "capture disabled" in capsys.readouterr().out
    assert ledger.calls(root) == []                                     # nothing imported
    monkeypatch.setenv("CAGE_CAPTURE", "1")                              # re-enable
    clicmds.cmd_import(_args(agent="claude", path=str(tp)))
    assert len(ledger.calls(root)) == 1


def test_import_skipped_when_policy_disables_capture(tmp_path, monkeypatch, capsys):
    root = _init_root(tmp_path, monkeypatch)
    monkeypatch.delenv("CAGE_CAPTURE", raising=False)
    mkcage(root)
    # Disable capture in the active config (cage.toml wins over legacy policy.toml).
    (root / ".cage" / "cage.toml").write_text("[capture]\nenabled = false\n", encoding="utf-8")
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    assert clicmds.cmd_import(_args(agent="claude", path=str(tp))) == 0
    assert "capture disabled" in capsys.readouterr().out
    assert ledger.calls(root) == []


# --- every agent is reachable -------------------------------------------------

def test_all_four_agents_reachable(tmp_path, monkeypatch, capsys):
    _init_root(tmp_path, monkeypatch)
    for a in agents.SURFACES:
        assert clicmds.cmd_import(_args(agent=a)) == 0  # never raises, always exits 0
    capsys.readouterr()


def test_default_all_runs_every_adapter(tmp_path, monkeypatch, capsys):
    _init_root(tmp_path, monkeypatch)
    assert clicmds.cmd_import(_args()) == 0  # --agent all is the default
    out = capsys.readouterr().out
    for a in agents.SURFACES:
        assert a in out  # one line per agent, none dropped


# --- log-bearing agents: import + idempotency ---------------------------------

def test_claude_import_counts_and_idempotent(tmp_path, monkeypatch, capsys):
    root = _init_root(tmp_path, monkeypatch)
    tp = tmp_path / "session.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n" + _claude_line("u2", 200, 60) + "\n",
                  encoding="utf-8")
    clicmds.cmd_import(_args(agent="claude", path=str(tp)))
    calls = ledger.calls(root)
    assert len(calls) == 2
    assert calls[0]["tokens_in"] == 100 and calls[0]["tokens_out"] == 50
    assert "✔ claude: imported 2 call(s) from 1 file(s)." in capsys.readouterr().out
    before = b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls"))
    clicmds.cmd_import(_args(agent="claude", path=str(tp)))  # re-import → no double count
    assert b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls")) == before


def test_import_is_noop_when_already_recorded_same_turns(tmp_path, monkeypatch, capsys):
    """A call seen by two capture paths dedupes by id (no double-count)."""
    root = _init_root(tmp_path, monkeypatch)
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("dup", 100, 50) + "\n", encoding="utf-8")
    from cage import transcript
    ledger.append_new(root, transcript.parse_calls(tp, session=tp.stem))  # a prior capture path got it
    capsys.readouterr()
    clicmds.cmd_import(_args(agent="claude", path=str(tp)))  # import the same turn
    assert len(ledger.calls(root)) == 1  # still one — id dedupe across hook + import
    assert "imported 0 call(s)" in capsys.readouterr().out


def test_malformed_file_does_not_abort(tmp_path, monkeypatch):
    root = _init_root(tmp_path, monkeypatch)
    scan = tmp_path / "scan"
    scan.mkdir()
    (scan / "good.jsonl").write_text(_claude_line("u1", 10, 5) + "\n", encoding="utf-8")
    (scan / "bad.jsonl").write_text("{not json\n", encoding="utf-8")
    assert clicmds.cmd_import(_args(agent="claude", path=str(scan))) == 0
    assert len(ledger.calls(root)) == 1  # the good file still imported


def _copilot_shutdown(model, tin, tout, cached=0):
    # Real Copilot CLI 1.0.65 shape: per-model metrics nest tokens under `usage`;
    # inputTokens is the TOTAL input (already includes cache read/write).
    return json.dumps({"type": "session.shutdown", "timestamp": "2026-06-14T10:00:00Z",
                       "data": {"totalPremiumRequests": 1, "currentModel": model,
                                "modelMetrics": {model: {"usage": {
                                    "inputTokens": tin, "outputTokens": tout,
                                    "cacheReadTokens": cached}}}}})


def test_copilot_import_counts_and_idempotent(tmp_path, monkeypatch, capsys):
    root = _init_root(tmp_path, monkeypatch)
    # a Copilot CLI session dir: session-state/<id>/events.jsonl
    ev = tmp_path / "home-copilot_home" / "session-state" / "sess-1" / "events.jsonl"
    ev.parent.mkdir(parents=True)
    ev.write_text(_copilot_shutdown("gpt-5-mini", 1200, 80, cached=300) + "\n", encoding="utf-8")
    clicmds.cmd_import(_args(agent="copilot"))
    calls = ledger.calls(root)
    assert len(calls) == 1
    assert calls[0]["agent"] == "copilot" and calls[0]["provider"] == "openai"
    # inputTokens is the total (already includes cache) — not summed again
    assert calls[0]["tokens_in"] == 1200 and calls[0]["tokens_out"] == 80
    assert calls[0]["cached_in"] == 300
    assert "✔ copilot: imported 1 call(s) from 1 file(s)." in capsys.readouterr().out
    before = b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls"))
    clicmds.cmd_import(_args(agent="copilot"))  # re-import → idempotent by session id
    assert b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls")) == before


def test_kiro_import_counts_and_idempotent(tmp_path, monkeypatch, capsys):
    # Kiro's coarse usage log: one JSON object per call (prompt tokens reliable,
    # output often 0, generic provider/model). Imported best-effort, deduped by content.
    # From inside a project the rows land in the MACHINE ledger (ADR 0006) — the log is
    # one global file with no project dimension, so a per-project kiro cost is fiction.
    root = _init_root(tmp_path, monkeypatch)
    log = tmp_path / "tokens_generated.jsonl"
    log.write_text(
        json.dumps({"model": "agent", "provider": "kiro", "promptTokens": 1200,
                    "generatedTokens": 340}) + "\n"
        + json.dumps({"model": "agent", "provider": "kiro", "promptTokens": 13,
                      "generatedTokens": 0}) + "\n", encoding="utf-8")
    clicmds.cmd_import(_args(agent="kiro", path=str(log)))
    assert ledger.calls(root) == []                     # not in the project ledger
    machine = paths.global_home()
    calls = ledger.calls(machine)
    assert len(calls) == 2 and {c["agent"] for c in calls} == {"kiro"}
    assert {c["tokens_in"] for c in calls} == {1200, 13}  # the 0-output line still counts
    out = capsys.readouterr().out
    assert "✔ kiro: imported 2 call(s) from 1 file(s) →" in out
    # the line names the sink — tilde-relative when under the real home (importcmd._tilde,
    # "machine-portable in tests"), which the sandboxed tmp_path IS on a Windows runner
    assert importcmd._tilde(paths.Footprint(machine).base) in out
    before = b"".join(p.read_bytes() for p in paths.Footprint(machine).shards("calls"))
    clicmds.cmd_import(_args(agent="kiro", path=str(log)))  # re-import → idempotent
    assert b"".join(p.read_bytes() for p in paths.Footprint(machine).shards("calls")) == before


def test_all_four_agents_are_log_bearing():
    # Every surface now has an on-disk import path — none is proxy-only.
    assert set(importcmd.LOG_BEARING) == set(agents.SURFACES)
