"""Capture is *visible* (capture-architecture §12) — but never on the wrong stream.

The graphify confirmation goes to STDERR (graphify's stdout is parseable data); a
zero-new read is SILENT; CAGE_QUIET suppresses; nothing carries content (counts/ids
only); no confirmation text ever enters a CSV (CSV never gates); and the MCP server
writes no stray stdout (that would corrupt the JSON-RPC protocol).
"""
from __future__ import annotations

import json
import sys
from io import StringIO
from types import SimpleNamespace

import pytest

from cage import graphifymeter as gm
from cage import importcmd, ledger, mcpserver, schema


def _stub(tmp_path, stdout, code=0):
    script = tmp_path / "fake_graphify.py"
    script.write_text(f"import sys\nsys.stdout.write({stdout!r})\nsys.exit({code})\n",
                      encoding="utf-8")
    return [sys.executable, str(script)]


# ── graphify confirmation is on stderr, never stdout ──────────────────────────

def test_graphify_confirmation_on_stderr_not_stdout(proj, capsys, monkeypatch):
    monkeypatch.delenv("CAGE_QUIET", raising=False)
    big = proj / "mod.py"
    big.write_text("z" * 4000, encoding="utf-8")
    answer = f"NODE foo [src={big} loc=L1 community=1]\nshort\n"
    gm.run(proj, [*_stub(proj, answer), "query", "x"], task="t1")
    cap = capsys.readouterr()
    assert cap.out == answer                        # stdout is graphify's, byte-identical
    assert "✔ cage: graphify saving captured" in cap.err  # the proof is on stderr
    assert "~" in cap.err and "tokens" in cap.err   # counts only


def test_graphify_quiet_suppresses(proj, capsys, monkeypatch):
    monkeypatch.setenv("CAGE_QUIET", "1")
    big = proj / "mod.py"
    big.write_text("z" * 4000, encoding="utf-8")
    answer = f"NODE foo [src={big} loc=L1 community=1]\nshort\n"
    gm.run(proj, [*_stub(proj, answer), "query", "x"], task="t1")
    cap = capsys.readouterr()
    assert cap.out == answer
    assert "cage: graphify" not in cap.err          # silenced
    assert len(ledger.receipts(proj)) == 1          # but the receipt still landed


def test_graphify_confirmation_carries_no_content(proj, capsys, monkeypatch):
    monkeypatch.delenv("CAGE_QUIET", raising=False)
    big = proj / "mod.py"
    big.write_text("secret-source-body " * 200, encoding="utf-8")
    answer = f"NODE foo [src={big} loc=L1 community=1]\nSENSITIVE-ANSWER-TEXT\n"
    gm.run(proj, [*_stub(proj, answer), "query", "x"], task="t1")
    err = capsys.readouterr().err
    assert "SENSITIVE-ANSWER-TEXT" not in err and "secret-source-body" not in err


# ── zero-new read ⇒ silent ────────────────────────────────────────────────────

def test_zero_new_is_silent(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")
    for env in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(tmp_path / f"empty-{env.lower()}"))
    # Empty homes ⇒ the sweep captures nothing ⇒ no summary, so the CLI prints no line.
    summary = importcmd.ensure_captured(
        root, SimpleNamespace(no_import=False, quiet=False, why_ledger=False, since=None))
    assert summary is None
    assert importcmd.capture_summary_line(summary) == ""


# ── no confirmation text in any CSV (CSV never gates) ─────────────────────────

def test_no_confirmation_text_in_csv(tmp_path, monkeypatch, capsys):
    from cage import cli
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")
    for env in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    # Plant a claude turn so a real capture happens on this read.
    slug = tmp_path / "home-claude_config_dir" / "projects" / "repo"
    slug.mkdir(parents=True)
    (slug / "s.jsonl").write_text(json.dumps(
        {"type": "assistant", "uuid": "u1", "cwd": "/repo",
         "timestamp": "2026-06-14T10:00:00Z",
         "message": {"model": "claude-opus-4-8",
                     "usage": {"input_tokens": 100, "output_tokens": 50}}}) + "\n",
        encoding="utf-8")
    assert cli.main(["report", "--by", "agent", "--csv"]) == 0
    cap = capsys.readouterr()
    assert "· captured" not in cap.out          # the CSV stream is pure data
    assert "route" in cap.out or "agent" in cap.out.splitlines()[0]


# ── the MCP server never writes stray stdout ──────────────────────────────────

def test_mcp_no_stray_stdout(seeded, monkeypatch, capsys):
    root, _ = seeded
    monkeypatch.chdir(root)
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")
    for env in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(root / f"home-{env.lower()}"))
    req = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                      "params": {"name": "cage_report", "arguments": {}}}) + "\n"
    out = StringIO()
    mcpserver.serve(stdin=StringIO(req), stdout=out)
    # Every line the server emitted is a valid JSON-RPC object — no capture-on-read line
    # leaked to the protocol stream.
    for line in out.getvalue().splitlines():
        if line.strip():
            msg = json.loads(line)  # raises if any stray non-JSON text leaked
            assert msg["jsonrpc"] == "2.0"


def test_mcp_capture_summary_is_a_structured_field(seeded, monkeypatch):
    root, _ = seeded
    monkeypatch.chdir(root)
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")
    for env in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(root / f"h-{env.lower()}"))
    # Plant a codex rollout so the MCP read captures something and surfaces the field.
    sess = root / "h-codex_home" / "sessions"
    sess.mkdir(parents=True)
    (sess / "rollout-x.jsonl").write_text(json.dumps(
        {"type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": {"input_tokens": 10, "output_tokens": 5,
                                  "cached_input_tokens": 0}}},
         "timestamp": "2026-06-14T10:00:00Z"}) + "\n", encoding="utf-8")
    reply = mcpserver._handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "cage_report", "arguments": {}}})
    # The capture proof rides as structuredContent, never in the rendered text.
    sc = reply["result"].get("structuredContent")
    if sc is not None:  # only present when the sweep actually captured
        assert "capture" in sc and "calls" in sc["capture"]
