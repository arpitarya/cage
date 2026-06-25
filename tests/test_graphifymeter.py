"""`cage graphify` external adapter — transparent passthrough + parsed receipt.

Covers handoff criteria 1 (byte-identical stdout/stderr/exit; metering never alters
the result), 3 (one tool="graphify" modeled receipt), 4 (no emit when no source file
resolves), 7 (meta = op only). Dependency-free: graphify is a deterministic stub
script, so the non-determinism of real graphify never enters the assertion.
"""
from __future__ import annotations

import sys

from cage import graphifymeter as gm
from cage import ledger, paths


def _stub(tmp_path, stdout, stderr="", code=0):
    """Write a tiny deterministic 'graphify' stand-in; return the argv to run it."""
    script = tmp_path / "fake_graphify.py"
    script.write_text(
        "import sys\n"
        f"sys.stdout.write({stdout!r})\n"
        f"sys.stderr.write({stderr!r})\n"
        f"sys.exit({code})\n",
        encoding="utf-8")
    return [sys.executable, str(script)]


# ── criterion 1 — passthrough is byte-identical and exit code is preserved ──────
def test_passthrough_is_byte_identical(proj, capsys):
    out = "NODE foo [src= loc=L1 community=1]\nanswer body\n"
    err = "a warning line\n"
    rc = gm.run(proj, [*_stub(proj, out, err, code=3), "query", "x"])
    captured = capsys.readouterr()
    assert rc == 3                       # exit code passed through
    assert captured.out == out           # stdout byte-identical
    assert captured.err == err           # stderr byte-identical


def test_metering_never_breaks_result(proj, capsys, monkeypatch):
    # force the metering side to blow up; graphify's result must be untouched
    monkeypatch.setattr(gm, "_cited_files", lambda *a, **k: (_ for _ in ()).throw(RuntimeError))
    out = "NODE foo [src=/nope loc=L1 community=1]\n"
    rc = gm.run(proj, [*_stub(proj, out, "", 0), "query", "x"])
    assert rc == 0 and capsys.readouterr().out == out


# ── criterion 3 — one graphify receipt from an answer citing a real file ────────
def test_files_one_modeled_receipt(proj, capsys):
    big = proj / "mod.py"
    big.write_text("z" * 4000, encoding="utf-8")     # ~1000 toks whole
    answer = f"NODE foo [src={big} loc=L1 community=1]\nshort\n"
    gm.run(proj, [*_stub(proj, answer, "", 0), "query", "x"], task="t1")
    rcpts = ledger.receipts(proj)
    assert len(rcpts) == 1
    r = rcpts[0]
    assert r["tool"] == "graphify" and r["unit"] == "tokens"
    assert r["method"] == "modeled" and r["confidence"] == 0.6
    assert r["task"] == "t1" and r["meta"] == {"op": "query"}     # criterion 7
    assert r["raw_alternative"] == 1000 and r["actual"] == gm.toks(answer)
    assert r["saved"] == r["raw_alternative"] - r["actual"] > 0


# ── criterion 4 — nothing filed when no source file parses/resolves ─────────────
def test_no_emit_when_no_file_resolves(proj, capsys):
    answer = "NODE foo [src=/does/not/exist.py loc=L1 community=1]\n" + "x" * 100
    gm.run(proj, [*_stub(proj, answer, "", 0), "query", "x"])
    assert ledger.receipts(proj) == []


def test_no_emit_for_path_op_citing_no_files(proj):
    # `path` output cites no src= — unmeasurable → no receipt
    answer = "Shortest path (2 hops):\n  a --calls--> b\n"
    gm.run(proj, [*_stub(proj, answer, "", 0), "path", "a", "b"])
    assert ledger.receipts(proj) == []


# ── explain format (Source: <file> Lnn) parses too ──────────────────────────────
def test_explain_source_line_parses(proj):
    f = proj / "thing.py"
    f.write_text("q" * 8000, encoding="utf-8")       # ~2000 toks
    answer = f"Node: run()\n  Source:    {f} L71\n  Type: code\n"
    gm.run(proj, [*_stub(proj, answer, "", 0), "explain", "run"], task="t2")
    rcpts = ledger.receipts(proj)
    assert len(rcpts) == 1 and rcpts[0]["meta"] == {"op": "explain"}
    assert rcpts[0]["raw_alternative"] == 2000
