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
    # P3a (v0.51): the capture manifest moved OUT of `ledger/` into `state/`, losing the
    # `"ledger/"` umbrella that was its only protection. It is an append-only audit trail
    # — nothing reconstructs a deleted row — so it is named in `NEVER` explicitly, and
    # **both homes** are asserted here. Without this case a future `state/` cleanup class
    # would eat it with nothing going red, which is exactly the hazard the savings-tree
    # comment beside `NEVER` warns about, realized one directory over.
    (st / "imports.jsonl").write_text('{"kind":"import","session_name":"n"}\n',
                                      encoding="utf-8")
    # P4 (v0.51): savings moved from `ledger/savings/<tool>/` to `ledger/<tool>/`. BOTH
    # are asserted — the move stayed inside `ledger/`, so the umbrella still covers it,
    # and this is the case that would catch a future move that did not. A savings row is
    # unrecoverable; a per-tool cleanup class must never exist.
    from cage import savings as _savings
    _savings.record(root, tool="graphify", raw_alternative=500, actual=100, ts=OLD_TS)
    legacy_sav = Footprint(root).savings_dir / "graphify" / "savings-2026-01.jsonl"
    legacy_sav.parent.mkdir(parents=True, exist_ok=True)
    legacy_sav.write_text('{"id":"s_legacy","tool":"graphify","saved":1.0}\n',
                          encoding="utf-8")
    (Footprint(root).ledger / "imports.jsonl").write_text(
        '{"kind":"import","session_name":"legacy"}\n', encoding="utf-8")
    pol_path = Footprint(root).policy
    pol_path.write_text("[cleanup]\ndays = 0\n", encoding="utf-8")
    for p in (st / "machine.json", st / "limits.json", pol_path, st / "imports.jsonl"):
        _age(p)
    keep = {p: p.read_bytes() for p in
            (st / "machine.json", st / "limits.json", pol_path,
             Footprint(root).ledger / "study.jsonl",
             st / "imports.jsonl", Footprint(root).ledger / "imports.jsonl",
             legacy_sav, *Footprint(root).savings_shards())}
    shards = b"".join(p.read_bytes() for p in Footprint(root).shards("calls"))
    cleanup.prune(root, policy.load(pol_path), days=0)
    for p, content in keep.items():
        assert p.read_bytes() == content, f"{p.name} must never be cleaned"
    assert b"".join(p.read_bytes() for p in Footprint(root).shards("calls")) == shards


def test_maybe_run_warns_but_never_deletes(root, monkeypatch, capsys):
    """The auto path (v0.37): a reminder on stderr, never a deletion. The reminder
    names the count, the reclaimable size, and the runnable fix.

    SURFACE-CUT deleted `cage data cleanup --apply` in v0.50; STATE-RETENTION
    restored a manual prune verb as `cage clean` (not re-grouped under a revived
    `data`), so the reminder names *that* fix — never a dead verb, which is exactly
    the failure the wiring-liveness gate exists to catch."""
    _seed_state(root)
    pol = policy.load(None)
    cleanup.maybe_run(root, pol)
    stamp = Footprint(root).state / "cleanup.stamp"
    assert stamp.exists()
    assert (Footprint(root).state / "junk.tmp").exists()   # never deleted by auto
    out, err = capsys.readouterr()
    assert out == ""                                        # never stdout
    assert "state/ item(s)" in err and "KB reclaimable" in err
    assert "cage clean --apply" in err
    assert "cage data cleanup" not in err   # never advertise a verb that is gone
    # within the throttle window: a second call must not re-scan or re-print
    calls = []
    monkeypatch.setattr(cleanup, "scan", lambda *a, **k: calls.append(1) or [])
    cleanup.maybe_run(root, pol)
    assert calls == []
    assert capsys.readouterr().err == ""
    # and a raising scan never propagates (fail-open)
    stamp.unlink()
    monkeypatch.setattr(cleanup, "scan", lambda *a, **k: 1 / 0)
    cleanup.maybe_run(root, pol)  # must not raise


def test_maybe_run_silent_when_nothing_stale(root, capsys):
    """A '0 items' reminder trains people to ignore it — so there must be none."""
    cleanup.maybe_run(root, policy.load(None))  # freshly-created, empty state/
    out, err = capsys.readouterr()
    assert out == "" and err == ""
    assert (Footprint(root).state / "cleanup.stamp").exists()  # throttle still ticks


def test_cleanup_warn_switch_suppresses_reminder_not_the_gate(root, monkeypatch, capsys):
    """[cleanup] warn / CAGE_CLEANUP_WARN silences the reminder text but the auto
    path still runs its (no-op) sweep and still ticks the throttle stamp."""
    _seed_state(root)
    monkeypatch.setenv("CAGE_CLEANUP_WARN", "0")
    cleanup.maybe_run(root, policy.load(None))
    assert capsys.readouterr().err == ""
    assert (Footprint(root).state / "junk.tmp").exists()
    assert (Footprint(root).state / "cleanup.stamp").exists()


def test_cleanup_enabled_false_disables_the_auto_path_entirely(root, monkeypatch, capsys):
    """enabled=false ⇒ no automatic anything (the decided semantics) — not even the
    throttle stamp is touched. A manual `cage data cleanup --apply` still works
    (proven by test_apply_ignores_cleanup_enabled_env)."""
    _seed_state(root)
    monkeypatch.setenv("CAGE_CLEANUP", "0")
    cleanup.maybe_run(root, policy.load(None))
    assert capsys.readouterr().err == ""
    assert not (Footprint(root).state / "cleanup.stamp").exists()


def test_cleanup_warn_default_and_env_precedence():
    assert policy.cleanup_warn({}) is True
    assert policy.cleanup_warn({"cleanup": {"warn": False}}) is False


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
        for argv in (["insights", "chats"], ["insights", "graphify"],
                     ["insights", "commits"]):
            assert cli.main(argv) == 0
            out.append(capsys.readouterr().out)
        return out
    before = views()
    cleanup.prune(root, policy.load(None))
    assert views() == before

# ── `cage clean` — the manual verb, restored (ADR-CLEANUP, STATE-RETENTION) ───
# `cage data cleanup --apply` went with the whole `data` group in SURFACE-CUT (v0.50).
# `cleanup.py` was deliberately KEPT regardless (decision: Arpit, 2026-08-14) because
# `importcmd.run` and `cage doctor` both import it — the library tests above never
# stopped running. This restores the CLI door onto that same library code, as its own
# top-level verb rather than a revived `data` group.

def test_clean_dry_run_default(root, capsys):
    _seed_state(root)
    assert cli.main(["clean"]) == 0
    out = capsys.readouterr().out
    assert "candidate(s)" in out and "dry-run" in out
    assert (Footprint(root).state / "junk.tmp").exists()   # nothing deleted


def test_clean_apply_prunes(root, capsys):
    st = _seed_state(root)
    assert cli.main(["clean", "--apply"]) == 0
    out = capsys.readouterr().out
    assert "applied" in out
    assert not (st / "junk.tmp").exists()
    assert cleanup.scan(root, policy.load(None)) == []


def test_clean_apply_ignores_cleanup_enabled_env(root, monkeypatch, capsys):
    """An explicitly-typed `cage clean --apply` always runs, even with the automatic
    reminder switched off — `[cleanup] enabled` gates only `maybe_run`."""
    st = _seed_state(root)
    monkeypatch.setenv("CAGE_CLEANUP", "0")
    assert cli.main(["clean", "--apply"]) == 0
    capsys.readouterr()
    assert not (st / "junk.tmp").exists()


def test_clean_json(root, capsys):
    _seed_state(root)
    assert cli.main(["clean", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["applied"] is None
    assert payload["items"]


def test_clean_days_override(root, capsys):
    """`--days` overrides the retention window for this run only, same as `scan`/`prune`
    (`test_never_list_survives_days_zero` pins that the never-list still holds at 0)."""
    st = _seed_state(root)
    (st / "pending-fresh.jsonl").write_text("{}\n", encoding="utf-8")
    assert cli.main(["clean", "--days", "0", "--apply"]) == 0
    capsys.readouterr()
    # days=0 is maximally aggressive: even the "fresh" buffer (untouched since creation,
    # so its age is > 0) is now stale and gets pruned too.
    assert not (st / "pending-fresh.jsonl").exists()
