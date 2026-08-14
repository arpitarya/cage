"""P1 coverage audit — "fail-open but never silent", tested not aspirational.

Every swallow-site on the capture/write path must leave at least one
attributable line in the debug log under ``CAGE_DEBUG=1`` when forced to fail
(handoff §2 P1). Each test forces exactly one site and asserts its context /
skip marker shows up — so a future edit that silently swallows a new failure
mode has to consciously break a named test.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cage import (compress, debuglog, graphifymeter, importcmd, ledger,
                  metering, responsecache, transcript)
from srcseed import mkcage


@pytest.fixture
def root(tmp_path, monkeypatch):
    mkcage(tmp_path)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    monkeypatch.delenv("CAGE_CAPTURE", raising=False)
    for env in ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _events(root: Path) -> list[dict]:
    return debuglog.tail(root, 0)


def _contexts(root: Path) -> set[str]:
    return {e.get("context", "") for e in _events(root) if e.get("event") == "exception"}


def _skips(root: Path) -> set[str]:
    return {e.get("skip", "") for e in _events(root) if e.get("skip")}


def _boom(*_a, **_k):
    raise RuntimeError("forced failure (audit)")


def _args(**kw):
    return SimpleNamespace(agent=kw.pop("agent", "claude"), path=None, project=None,
                           since=None, **kw)


# NB: the hook swallow-site tests (Stop/SessionEnd/PostToolUse/post-commit/
# prepare-commit-msg) were removed with the hook machinery. The "fail-open but never
# silent" discipline is now audited on the surviving capture paths below: the pull
# import sweep (importcmd.py), the ledger/meter write path, cleanup, and every receipt
# push/skip site (F6 — the F1 instrument).


# ── importcmd.py ---------------------------------------------------------------

def test_ingest_parse_failure_logs(root, monkeypatch):
    home = root / "home-claude_config_dir" / "projects" / "p"
    home.mkdir(parents=True)
    (home / "s.jsonl").write_text("{}\n", encoding="utf-8")
    # P5: the built-in claude path parses through `parse_claude_chat_metrics`, not
    # `parse_calls` — patching the retired parser would have made this pass while
    # exercising nothing. The property is unchanged: a parser that raises is RECORDED,
    # and the sweep still returns (fail-open but never silent).
    monkeypatch.setattr(transcript, "parse_claude_chat_metrics", _boom)
    importcmd.run(root, "claude", _args())  # fail-open: never raises
    assert "import.ingest" in _contexts(root)


def test_broken_policy_logs(root):
    # Broken content in the ACTIVE config (cage.toml wins over legacy policy.toml).
    (root / ".cage" / "cage.toml").write_text("[debug]\n[debug]\n", encoding="utf-8")
    out = importcmd.run(root, "claude", _args())
    assert any("imported" in line for line in out)  # degraded to default policy, kept going
    assert "import.policy" in _contexts(root)


def test_unavailable_lock_logs(root, monkeypatch):
    # `--agent claude`, not kiro: the sweep's lock and cursors are per-ROOT, and kiro's
    # rows (with their lock and cursors) now route to the machine ledger — ADR 0006.
    (root / ".cage" / "state").write_text("", encoding="utf-8")  # state is a file → no lock
    monkeypatch.setenv("CAGE_DEBUG_LOG", str(root / "dbg.log"))
    importcmd.run(root, "claude", _args(agent="claude"))
    assert "import.lock" in _contexts(root)


def test_corrupt_cursors_load_logs(root):
    state = root / ".cage" / "state"
    state.mkdir(parents=True)
    (state / "cursors.json").write_text("{not json", encoding="utf-8")
    importcmd.run(root, "claude", _args(agent="claude"))
    assert "import.cursors-load" in _contexts(root)


def test_unwritable_cursors_save_logs(root):
    state = root / ".cage" / "state"
    (state / "cursors.json").mkdir(parents=True)  # a directory → write_text raises OSError
    importcmd.run(root, "claude", _args(agent="claude"))
    assert "import.cursors-save" in _contexts(root)


def test_nonempty_log_parsing_to_zero_rows_logs(root):
    # The format-drift signature (handoff §8): bytes present, zero rows recovered.
    home = root / "home-claude_config_dir" / "projects" / "p"
    home.mkdir(parents=True)
    (home / "s.jsonl").write_text(json.dumps({"type": "user", "message": {}}) + "\n",
                                  encoding="utf-8")
    importcmd.run(root, "claude", _args())
    assert "parsed-zero-rows" in _skips(root)


# ── ledger.py / metering.py ------------------------------------------------------

def test_ledger_append_failure_logs(root, monkeypatch):
    blocker = root / "not-a-dir"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setenv("CAGE_LEDGER", str(blocker / "ledger"))  # parent is a file → OSError
    assert ledger.append_row(root, "calls", {"id": "c_x", "ts": "2026-06-14T10:00:00Z"}) is False
    monkeypatch.delenv("CAGE_LEDGER")  # read the debug log via the normal footprint
    events = [e for e in _events(root) if e.get("event") == "ledger.append"]
    assert events and events[0]["result"] == "write-failed" and events[0]["row_id"] == "c_x"


def test_meter_record_failure_logs(root, monkeypatch):
    monkeypatch.setattr(metering, "record_call", _boom)
    with metering.meter("chat", root=root) as m:
        m.usage(provider="anthropic", model="claude-opus-4-8", tokens_in=1, tokens_out=1)
    # the metered block itself never raised (fail-open), and the swallow is attributable
    assert "meter.record" in _contexts(root)


# ── cleanup.py ----------------------------------------------------------------

def test_cleanup_prune_failure_logs(root, monkeypatch):
    from cage import cleanup, policy
    st = root / ".cage" / "state"
    st.mkdir(parents=True, exist_ok=True)
    stale = st / "pending-x.jsonl"
    stale.write_text("{}\n", encoding="utf-8")
    import os as _os
    import time as _time
    old = _time.time() - 90 * 86400
    _os.utime(stale, (old, old))
    monkeypatch.setattr(cleanup, "_apply_item", _boom)
    cleanup.prune(root, policy.load(None))          # per-item fail-open
    assert "cleanup.prune" in _contexts(root)
    monkeypatch.setattr(cleanup, "scan", _boom)
    (st / "cleanup.stamp").unlink(missing_ok=True)
    cleanup.maybe_run(root, policy.load(None))      # whole-body fail-open
    assert "cleanup.prune" in _contexts(root)


# ── receipt sites (F6 — the F1 instrument) -----------------------------------
# Every receipt push/skip site logs whether a receipt was produced and, if not, why —
# a `CAGE_DEBUG`-gated trail, unlike `state/capture.log`'s always-on breadcrumb.

def _receipt_events(root: Path, tool: str) -> list[dict]:
    return [e for e in _events(root) if e.get("event") == "receipt" and e.get("tool") == tool]


def test_graphify_meter_logs_skip_and_produce(root):
    graphifymeter._meter(root, "no citations here at all", ["query", "x"], "t")
    ev = _receipt_events(root, "graphify")
    assert ev[-1]["produced"] is False and ev[-1]["skip_reason"] == "no-source-file-parsed"

    src = root / "big.py"
    src.write_text("x" * 4000, encoding="utf-8")
    answer = f"NODE label [src={src} loc=L1 community=0]"
    graphifymeter._meter(root, answer, ["query", "x"], "t")
    ev = _receipt_events(root, "graphify")
    assert ev[-1]["produced"] is True and ev[-1]["skip_reason"] == ""


def test_metering_record_receipt_logs_produce_and_skip(root, monkeypatch):
    rid = metering.record_receipt(tool="rc-ok", raw_alternative=10, actual=2, root=root)
    assert rid
    ev = _receipt_events(root, "rc-ok")
    assert ev[-1]["produced"] is True

    blocker = root / "not-a-dir"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setenv("CAGE_LEDGER", str(blocker / "ledger"))  # parent is a file → OSError
    rid2 = metering.record_receipt(tool="rc-fail", raw_alternative=10, actual=2, root=root)
    assert rid2 == ""
    monkeypatch.delenv("CAGE_LEDGER")
    ev2 = _receipt_events(root, "rc-fail")
    assert ev2[-1]["produced"] is False and ev2[-1]["skip_reason"] == "push-sink-unresolved"


def test_responsecache_lookup_logs_miss_and_hit(root):
    responsecache.lookup(root, "prompt-x")  # miss — nothing cached yet
    ev = _receipt_events(root, "response-cache")
    assert ev[-1]["produced"] is False and ev[-1]["skip_reason"] == "cache-miss"

    responsecache.store(root, "prompt-x", "value", 50)
    responsecache.lookup(root, "prompt-x")  # hit
    ev = _receipt_events(root, "response-cache")
    assert ev[-1]["produced"] is True


def test_compress_receipt_logs_skip_and_produce(root):
    compress.receipt("{}", root=root)  # nothing to shrink — no saving to claim
    ev = _receipt_events(root, "compressor")
    assert ev[-1]["produced"] is False and ev[-1]["skip_reason"] == "no-saving-to-claim"

    big = json.dumps({"a": list(range(1000))})
    compress.receipt(big, root=root)
    ev = _receipt_events(root, "compressor")
    assert ev[-1]["produced"] is True
