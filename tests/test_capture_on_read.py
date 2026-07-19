"""Capture-on-read (capture-architecture Phase 1) — the lazy pre-read sweep.

A read (report / insights / MCP) sweeps the log registry into the ledger before it
answers, so a number is never staler than the instant it's shown — no hook, no scheduler.
Suppressible (`--no-import`, `CAGE_CAPTURE=0`, `CAGE_CAPTURE_ON_READ=0`), throttled,
fail-open. The whole determinism suite pins it OFF (conftest); these tests opt back in
over isolated empty homes so a sweep can never read the developer's real transcripts.
"""
from __future__ import annotations

import datetime as _dt
import json
from types import SimpleNamespace

import pytest

from cage import importcmd, ledger, paths, report


@pytest.fixture(autouse=True)
def _on_read_isolated(monkeypatch, tmp_path):
    """Turn capture-on-read ON, but point every agent home at an isolated empty dir so
    the sweep only ever sees what a test plants — never the real ~/.claude etc."""
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")
    for env in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))


def _claude_log(d, uuid, tin, tout):
    slug = d / "claude" / "projects" / "repo"
    slug.mkdir(parents=True, exist_ok=True)
    f = slug / "s.jsonl"
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "assistant", "uuid": uuid, "cwd": "/repo",
                             "timestamp": "2026-06-14T10:00:00Z",
                             "message": {"model": "claude-opus-4-8",
                                         "usage": {"input_tokens": tin,
                                                   "output_tokens": tout}}}) + "\n")
    return f


def _proj(tmp_path):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    return root


def _read_args(**kw):
    base = dict(no_import=False, quiet=False, why_ledger=False, since=None)
    base.update(kw)
    return SimpleNamespace(**base)


# ── the sweep runs before a read ──────────────────────────────────────────────

def test_sweep_runs_before_a_read(tmp_path, monkeypatch):
    root = _proj(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    _claude_log(tmp_path, "u1", 100, 50)
    summary = importcmd.ensure_captured(root, _read_args())
    assert summary and summary["calls"] == 1 and "claude" in summary["agents"]
    assert len(ledger.calls(root)) == 1  # the planted turn is now captured


# ── throttle suppresses a back-to-back second sweep ───────────────────────────

def test_throttle_suppresses_second_sweep(tmp_path, monkeypatch):
    root = _proj(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    _claude_log(tmp_path, "u1", 100, 50)
    assert importcmd.ensure_captured(root, _read_args()) is not None  # first sweep imports

    # A new turn lands, but the throttle window (default 60s, _last_import just now)
    # suppresses the immediate second read — no re-sweep.
    _claude_log(tmp_path, "u2", 70, 30)
    assert importcmd.ensure_captured(root, _read_args()) is None
    assert len(ledger.calls(root)) == 1  # u2 not yet captured (throttled)

    # Backdate the cursor past the window → the next read sweeps and picks up u2.
    foot = paths.Footprint(root)
    cur = json.loads(foot.cursors.read_text())
    cur["_last_import"] = (_dt.datetime.now(_dt.timezone.utc)
                           - _dt.timedelta(hours=1)).isoformat()
    foot.cursors.write_text(json.dumps(cur))
    assert importcmd.ensure_captured(root, _read_args()) is not None
    assert len(ledger.calls(root)) == 2


# ── suppression: CAGE_CAPTURE=0 and --no-import both disable it ────────────────

def test_cage_capture_env_disables(tmp_path, monkeypatch):
    root = _proj(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    _claude_log(tmp_path, "u1", 100, 50)
    monkeypatch.setenv("CAGE_CAPTURE", "0")
    assert importcmd.ensure_captured(root, _read_args()) is None
    assert len(ledger.calls(root)) == 0  # capture paused — nothing swept


def test_no_import_flag_disables(tmp_path, monkeypatch):
    root = _proj(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    _claude_log(tmp_path, "u1", 100, 50)
    assert importcmd.ensure_captured(root, _read_args(no_import=True)) is None
    assert len(ledger.calls(root)) == 0


def test_on_read_env_disables(tmp_path, monkeypatch):
    root = _proj(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    _claude_log(tmp_path, "u1", 100, 50)
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "0")  # the determinism-suite switch
    assert importcmd.ensure_captured(root, _read_args()) is None
    assert len(ledger.calls(root)) == 0


# ── fail-open: a capture error never blocks the read ──────────────────────────

def test_capture_error_read_still_succeeds(tmp_path, monkeypatch):
    from cage import cli
    root = _proj(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))

    def _boom(*a, **k):
        raise RuntimeError("sweep exploded")

    monkeypatch.setattr(importcmd, "run", _boom)
    # ensure_captured swallows the error (returns None) and the read still renders.
    assert importcmd.ensure_captured(root, _read_args()) is None
    assert cli.main(["report"]) == 0


# ── concurrent reads don't double-append ──────────────────────────────────────

def test_concurrent_reads_no_double_append(tmp_path, monkeypatch):
    root = _proj(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    _claude_log(tmp_path, "u1", 100, 50)
    # Two sweeps with no throttle between them (window disabled) — id-dedupe + the
    # import lock keep the turn single.
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")
    foot = paths.Footprint(root)
    importcmd.ensure_captured(root, _read_args())
    # force the throttle open, sweep again — same file, no new row
    cur = json.loads(foot.cursors.read_text())
    cur["_last_import"] = "2020-01-01T00:00:00+00:00"
    foot.cursors.write_text(json.dumps(cur))
    importcmd.ensure_captured(root, _read_args())
    assert len(ledger.calls(root)) == 1  # deduped, not doubled


# ── warm cache ⇒ byte-identical derived output (the determinism guard) ─────────

def test_warm_cache_byte_identical(tmp_path, monkeypatch, capsys):
    from cage import cli, schema
    root = _proj(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    # A fixed ledger + a WARM cursor (last import just now) — a warm cache means the
    # throttle suppresses the sweep entirely, so capture-on-read is a pure no-op and the
    # derived output is byte-identical whether it's on or off. (A *cold* read legitimately
    # sweeps and refreshes _last_import/_health — that's the feature, and the golden suite
    # pins capture-on-read off so those never move under a fixed ledger.)
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-opus-4-8",
        tokens_in=100, tokens_out=10, agent="claude-code", call_id="c_fixed"))
    foot = paths.Footprint(root)
    foot.cursors.parent.mkdir(parents=True, exist_ok=True)
    foot.cursors.write_text(json.dumps(
        {"_last_import": _dt.datetime.now(_dt.timezone.utc).isoformat()}))

    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "0")
    assert cli.main(["report", "--by", "agent"]) == 0
    off = capsys.readouterr().out

    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")  # on, but throttled ⇒ no sweep
    assert cli.main(["report", "--by", "agent"]) == 0
    warm = capsys.readouterr().out
    assert warm == off  # byte-identical derived output on a warm cache


# ── the summary line is counts-only and correctly worded ──────────────────────

def test_summary_line_counts_only():
    assert importcmd.capture_summary_line(None) == ""
    assert importcmd.capture_summary_line({"calls": 0, "agents": [], "savings": 0}) == ""
    line = importcmd.capture_summary_line({"calls": 240, "agents": ["claude", "codex"],
                                           "savings": 3})
    assert line == ("· captured 240 new calls (claude, codex) + 3 graphify savings "
                    "since last read")
    assert "token" not in line and "prompt" not in line  # counts only, no content
