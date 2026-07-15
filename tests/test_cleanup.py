"""State-dir cleanup — the closed allowlist, the never-list, and the auto path."""
from __future__ import annotations

import json
import os
import time

import pytest

from cage import cleanup, cli, ledger, policy, schema
from cage.paths import Footprint

OLD_TS = "2020-01-01T00:00:00+00:00"
NEW_TS = "2099-01-01T00:00:00+00:00"


@pytest.fixture
def root(proj, monkeypatch):
    (proj / ".cage" / "state").mkdir(parents=True)
    monkeypatch.chdir(proj)
    return proj


def _age(path, days=90):
    old = time.time() - days * 86400
    os.utime(path, (old, old))


def _seed_state(root):
    st = Footprint(root).state
    (st / "debug.log").write_text(
        json.dumps({"ts": OLD_TS, "event": "old"}) + "\n"
        + json.dumps({"ts": NEW_TS, "event": "new"}) + "\n", encoding="utf-8")
    (st / "hooks-seen.jsonl").write_text(json.dumps({"ts": OLD_TS}) + "\n", encoding="utf-8")
    (st / "pending-stale.jsonl").write_text("{}\n", encoding="utf-8")
    _age(st / "pending-stale.jsonl")
    (st / "pending-fresh.jsonl").write_text("{}\n", encoding="utf-8")
    # a real absolute path on THIS OS (ntpath.isabs on Python 3.13+ no longer
    # treats a drive-less "/x" as absolute on Windows) whose file is gone
    gone = str((st.parent.parent / "deleted-source-log.jsonl").resolve())
    (st / "cursors.json").write_text(json.dumps(
        {"claude": {gone: [1, 2]}, "_last_import": OLD_TS}),
        encoding="utf-8")
    (st / "junk.tmp").write_text("x", encoding="utf-8")
    _age(st / "junk.tmp")
    return st


def test_every_allowlist_class_ages_out(root):
    st = _seed_state(root)
    pol = policy.load(None)
    classes = {i["cls"] for i in cleanup.scan(root, pol)}
    assert classes == {"debug-log", "hooks-seen", "pending-buffer",
                       "cursor-orphan", "tmp"}
    counts = cleanup.prune(root, pol)
    assert sum(counts.values()) == 5
    assert not (st / "pending-stale.jsonl").exists()
    assert (st / "pending-fresh.jsonl").exists()
    assert not (st / "junk.tmp").exists()
    assert "old" not in (st / "debug.log").read_text()
    assert "new" in (st / "debug.log").read_text()
    cursors = json.loads((st / "cursors.json").read_text())
    assert cursors["claude"] == {} and cursors["_last_import"] == OLD_TS
    assert cleanup.scan(root, pol) == []  # converges


def test_never_list_survives_days_zero(root):
    """days=0 is maximally aggressive — the never-list must still be untouchable
    because scan never looks at it, not because the rows happen to be fresh."""
    st = _seed_state(root)
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-opus-4-8", tokens_in=10,
        ts=OLD_TS, call_id="c_keep"))
    (st / "machine.json").write_text('{"id": "m_x"}', encoding="utf-8")
    (st / "limits.json").write_text("{}", encoding="utf-8")
    (Footprint(root).ledger / "study.jsonl").write_text("{}\n", encoding="utf-8")
    pol_path = Footprint(root).policy
    pol_path.write_text("[cleanup]\ndays = 0\n", encoding="utf-8")
    for p in (st / "machine.json", st / "limits.json", pol_path):
        _age(p)
    keep = {p: p.read_bytes() for p in
            (st / "machine.json", st / "limits.json", pol_path,
             Footprint(root).ledger / "study.jsonl")}
    shards = b"".join(p.read_bytes() for p in Footprint(root).shards("calls"))
    cleanup.prune(root, policy.load(pol_path), days=0)
    for p, content in keep.items():
        assert p.read_bytes() == content, f"{p.name} must never be cleaned"
    assert b"".join(p.read_bytes() for p in Footprint(root).shards("calls")) == shards


def test_dry_run_touches_nothing(root, capsys):
    st = _seed_state(root)
    before = {p.name: p.read_bytes() for p in st.iterdir() if p.is_file()}
    assert cli.main(["data", "cleanup"]) == 0
    out = capsys.readouterr().out
    assert "dry-run" in out and "--apply" in out
    after = {p.name: p.read_bytes() for p in st.iterdir() if p.is_file()}
    assert after == before


def test_apply_flag_and_env_toggle(root, capsys, monkeypatch):
    _seed_state(root)
    monkeypatch.setenv("CAGE_CLEANUP", "0")
    assert cli.main(["data", "cleanup", "--apply"]) == 0
    assert "DISABLED" in capsys.readouterr().out
    assert (Footprint(root).state / "junk.tmp").exists()  # env off ⇒ nothing applied
    monkeypatch.delenv("CAGE_CLEANUP")
    assert cli.main(["data", "cleanup", "--apply"]) == 0
    assert "✔ applied" in capsys.readouterr().out
    assert not (Footprint(root).state / "junk.tmp").exists()


def test_maybe_run_throttles_and_fails_open(root, monkeypatch):
    _seed_state(root)
    pol = policy.load(None)
    cleanup.maybe_run(root, pol)
    stamp = Footprint(root).state / "cleanup.stamp"
    assert stamp.exists()
    assert not (Footprint(root).state / "junk.tmp").exists()
    # within the throttle window: prune must not run again
    calls = []
    monkeypatch.setattr(cleanup, "prune", lambda *a, **k: calls.append(1) or {})
    cleanup.maybe_run(root, pol)
    assert calls == []
    # and a raising prune never propagates (fail-open)
    stamp.unlink()
    monkeypatch.setattr(cleanup, "prune", lambda *a, **k: 1 / 0)
    cleanup.maybe_run(root, pol)  # must not raise


def test_import_run_piggybacks_cleanup(root, monkeypatch):
    from cage import importcmd
    seen = []
    monkeypatch.setattr(cleanup, "maybe_run", lambda r, pol: seen.append(r))

    class A:
        path = project = since = None
        agent = "claude"
    importcmd.run(root, "claude", A())
    assert seen == [root]


def test_derived_views_identical_before_and_after_cleanup(root, capsys):
    """State files are never read by derived views — cleanup can't change a number."""
    _seed_state(root)
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-opus-4-8",
        tokens_in=100_000, tokens_out=10_000, ts="2026-07-01T00:00:00Z",
        call_id="c_det"))
    def views():
        out = []
        for argv in (["report", "--by", "model"], ["insights", "compare"], []):
            assert cli.main(argv) == 0
            out.append(capsys.readouterr().out)
        return out
    before = views()
    cleanup.prune(root, policy.load(None))
    assert views() == before
