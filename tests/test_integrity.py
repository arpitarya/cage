"""The tamper-evidence chain — P6. [ADR-INTEGRITY](../docs/adr/0010_integrity.md).

Append-only is the law every other guarantee rests on, and nothing was checking it. This
file pins what the chain detects, what it refuses to call tampering, and — mostly — the
four things it must never become.

The invariants, in the order they would hurt if broken:

  1. **Report-only.** Never changes an exit code, never blocks a read or a write.
  2. **The lock is never load-bearing.** A miss yields `unverified`; it never breaks the
     chain. `lockutil` proceeds unlocked by contract, and depending on it here would break
     fail-open in a way nothing else tests.
  3. **`ledger.append_row` stays off this path.** Integrity must not make capture slower or
     less fail-open — the chain advances once per sweep.
  4. **Never read by a derived view.** Deleting the manifest moves zero numeric cells.

And the classification that decides whether anyone ever reads the report: designed churn
(`cursors.json`, the logs) is `expected`, a truncated tail is `damaged` — **not**
tampering, because `ledger.read` tolerates it by design — and only a changed *recorded
prefix* is `altered-history`.
"""
from __future__ import annotations

import json

import pytest

from cage import cleanup, integrity, ledger, paths, schema

TS = "2026-08-10T12:00:00Z"


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / ".cage" / "state").mkdir(parents=True)
    monkeypatch.setenv("CAGE_BASE", str(root / ".cage"))
    monkeypatch.delenv("CAGE_LEDGER", raising=False)
    return root


def _call(proj, cid, tin=10):
    ledger.append_row(proj, "calls", schema.make_call(
        route="chat", provider="anthropic", model="m", agent="lib",
        tokens_in=tin, ts=TS, call_id=cid))


def _shard(proj):
    return paths.Footprint(proj).shard("calls", TS)


# ── the chain itself ────────────────────────────────────────────────────────────

def test_a_first_checkpoint_records_every_tracked_file(proj):
    _call(proj, "c_1")
    m = integrity.checkpoint(proj)
    assert any(k.endswith("calls-2026-08.jsonl") for k in m), m
    entry = next(v for k, v in m.items() if k.endswith("calls-2026-08.jsonl"))
    assert entry["current"] != integrity.GENESIS
    assert entry["size"] == _shard(proj).stat().st_size


def test_growth_is_chained_and_reported_as_nothing(proj):
    _call(proj, "c_1")
    integrity.checkpoint(proj)
    _call(proj, "c_2")
    integrity.checkpoint(proj)
    assert integrity.findings(proj) == []
    verdicts = {r["path"]: r["verdict"] for r in integrity.verify(proj)}
    assert all(v == "ok" for v in verdicts.values()), verdicts


def test_the_chain_is_a_function_of_bytes_only(proj, tmp_path):
    """Determinism: the same bytes must chain to the same value, in a different ledger, at
    a different time. A wall clock anywhere in the hash would break that silently."""
    _call(proj, "c_1")
    a = integrity.checkpoint(proj)
    other = tmp_path / "other"
    (other / ".cage" / "state").mkdir(parents=True)
    dst = paths.Footprint(other).shard("calls", TS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(_shard(proj).read_bytes())
    b = integrity.checkpoint(other)
    key = next(k for k in a if k.endswith("calls-2026-08.jsonl"))
    assert a[key]["current"] == b[key]["current"]


def test_a_first_run_reports_nothing_rather_than_everything(proj):
    """An entry with no recorded state is skipped — *not yet checkpointed* is not a
    finding, and reporting it would make a first run look like a disaster."""
    _call(proj, "c_1")
    assert integrity.verify(proj) == []
    assert integrity.findings(proj) == []


# ── the two verdicts, never blended ─────────────────────────────────────────────

def test_a_rewritten_prefix_is_altered_history(proj):
    """**The one real tamper signal.** Under append-only a recorded row is never edited, so
    a changed prefix is never legitimate. Note this is a change in the MIDDLE of the file,
    not at the tail — which is why verification replays rather than comparing one digest."""
    _call(proj, "c_1", tin=10)
    _call(proj, "c_2", tin=20)
    integrity.checkpoint(proj)
    sh = _shard(proj)
    sh.write_bytes(sh.read_bytes().replace(b'"tokens_in": 10', b'"tokens_in": 99'))
    bad = integrity.findings(proj)
    assert [r["verdict"] for r in bad] == ["altered-history"], bad
    assert "already recorded" in bad[0]["detail"]


def test_a_truncated_tail_is_damaged_and_never_tampering(proj):
    """`ledger.read` tolerates a truncated tail **by design** (a crash mid-write). Calling
    that tampering would turn a documented fail-open behaviour into an alarm."""
    _call(proj, "c_1")
    _call(proj, "c_2")
    integrity.checkpoint(proj)
    sh = _shard(proj)
    sh.write_bytes(sh.read_bytes()[:-40])
    bad = integrity.findings(proj)
    assert [r["verdict"] for r in bad] == ["damaged"], bad
    assert "altered" not in bad[0]["detail"]


def test_the_two_verdicts_are_distinguishable(proj):
    """Merging them into one scary word is the failure this asserts against."""
    assert {"altered-history", "damaged"} <= {
        "altered-history", "damaged", "unverified", "expected", "ok"}


# ── the two non-findings that keep the report readable ──────────────────────────

def test_designed_churn_is_expected_not_a_finding(proj):
    """`cursors.json` is rewritten wholesale every import and the logs are pruned by
    design. Reporting them would fire on every run and train the reader to ignore the one
    report that matters."""
    st = paths.Footprint(proj).state
    (st / "cursors.json").write_text('{"claude": {"a": 1}}', encoding="utf-8")
    integrity.checkpoint(proj)
    (st / "cursors.json").write_text('{"claude": {"b": 2}}', encoding="utf-8")
    assert integrity.findings(proj) == []
    v = {r["path"]: r["verdict"] for r in integrity.verify(proj)}
    assert v["state/cursors.json"] == "expected"


def test_a_lock_miss_marks_unverified_and_never_breaks_the_chain(proj, monkeypatch):
    """**Invariant 2.** `lockutil` proceeds unlocked by contract; a chain that depended on
    it would quietly promote it to a correctness guarantee it is not built to be. The
    segment is marked, the chain still verifies, and nothing is reported as a finding —
    a stated unknown, never a fabricated verdict."""
    import contextlib

    @contextlib.contextmanager
    def missing(_lock, on_miss=None):
        if on_miss is not None:
            on_miss(None)
        yield

    _call(proj, "c_1")
    monkeypatch.setattr(integrity.lockutil, "locked", missing)
    integrity.checkpoint(proj)
    v = {r["path"]: r["verdict"] for r in integrity.verify(proj)}
    key = next(k for k in v if k.endswith("calls-2026-08.jsonl"))
    assert v[key] == "unverified"
    assert integrity.findings(proj) == []      # a stated unknown is not a finding
    # …and the chain is intact: a real rewrite is still caught afterwards.
    sh = _shard(proj)
    sh.write_bytes(sh.read_bytes().replace(b'"tokens_in": 10', b'"tokens_in": 99'))
    assert [r["verdict"] for r in integrity.findings(proj)] == ["altered-history"]


# ── the four things it must never become ────────────────────────────────────────

def test_it_never_changes_an_exit_code(proj):
    """**Invariant 1**, at the surface that could break it. A finding is a WARN; doctor
    fails only on `fail`, and the `cage authorship verify` precedent is report-only."""
    from cage import doctorcmd
    _call(proj, "c_1")
    integrity.checkpoint(proj)
    sh = _shard(proj)
    sh.write_bytes(sh.read_bytes().replace(b'"tokens_in": 10', b'"tokens_in": 99'))
    level, detail = doctorcmd._integrity(proj)
    assert level == doctorcmd._WARN
    assert "altered-history" in detail
    assert level != doctorcmd._FAIL


def test_doctor_never_checkpoints(proj):
    """Doctor's contract is that running it records nothing — and a check that advanced the
    baseline it is about to compare against could never report the same finding twice. An
    early draft did exactly this and broke bundle determinism."""
    from cage import doctorcmd
    _call(proj, "c_1")
    before = integrity.manifest_path(proj).exists()
    doctorcmd._integrity(proj)
    assert integrity.manifest_path(proj).exists() == before


def test_append_row_is_off_this_path(proj):
    """**Invariant 3.** The capture write path must not get slower or less fail-open. The
    chain advances at sweep boundaries, so a bare append writes no manifest."""
    _call(proj, "c_1")
    assert not integrity.manifest_path(proj).exists()


def test_deleting_the_manifest_moves_zero_numeric_cells(proj):
    """**Invariant 4**, the same guard the manifest and provenance carve-outs carry."""
    from cage import chats, policy
    _call(proj, "c_1", tin=123)
    integrity.checkpoint(proj)
    pol = policy.load(paths.Footprint(proj).policy)
    before = chats.summarize(proj, pol)
    integrity.manifest_path(proj).unlink()
    assert chats.summarize(proj, pol) == before


def test_the_manifest_is_protected_from_cleanup(proj):
    assert "integrity.json" in cleanup.NEVER


def test_the_manifest_never_hashes_itself(proj):
    """A manifest cannot hash itself — recording would change the bytes it just hashed,
    so it would report itself altered on every single run."""
    _call(proj, "c_1")
    integrity.checkpoint(proj)
    integrity.checkpoint(proj)
    m = integrity.read_manifest(proj)
    assert "state/integrity.json" not in m
    assert integrity.findings(proj) == []


def test_an_unreadable_manifest_is_empty_not_an_error(proj):
    integrity.manifest_path(proj).write_text("{not json", encoding="utf-8")
    assert integrity.read_manifest(proj) == {}
    assert integrity.verify(proj) == []


def test_checkpoint_never_raises_into_capture(proj, monkeypatch):
    """Fail-open, like every write path. A diagnostic must never be the thing that breaks
    an import."""
    monkeypatch.setattr(integrity, "_tracked", lambda _r: (_ for _ in ()).throw(OSError("nope")))
    assert integrity.checkpoint(proj) == {}


def test_an_import_advances_the_chain(proj, tmp_path):
    """The wiring: the sweep is where the chain moves, and it must actually fire."""
    from types import SimpleNamespace

    from cage import importcmd
    from srcseed import mkcage
    mkcage(proj)
    tp = tmp_path / "s.jsonl"
    tp.write_text(json.dumps({
        "type": "assistant", "uuid": "u1", "timestamp": "2026-06-14T10:00:00Z",
        "message": {"model": "claude-opus-4-8",
                    "usage": {"input_tokens": 10, "output_tokens": 5}}}) + "\n",
        encoding="utf-8")
    importcmd.run(proj, "claude", SimpleNamespace(path=str(tp), project=None, since=None))
    assert integrity.read_manifest(proj), "the sweep did not checkpoint"
