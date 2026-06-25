"""Ledger scale (plan §3.6): month partitioning, `scope`, team aggregation, size warning.

Covers the handoff Definition of Done and Non-negotiables — partition target by `ts`,
reader globs legacy + dated, `--since` shard skipping, `scope` round-trip + filter +
absent-flag byte-identity, `ledger-sync` dry-run vs write, the shared union-by-id helper,
`--team` merged-read + empty-ref fallback, the stderr size warning, and determinism.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import contextlib

import pytest

from cage import (attribution, ledger, ledgersync, mergeutil, paths, policy,
                  report, schema, tasks)


def _git_init(root):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    def run(*a):
        subprocess.run(("git", "-C", str(root), *a), check=True, capture_output=True, env=env)
    run("init")
    (root / "a.py").write_text("x = 1\n")
    run("add", "a.py")
    run("commit", "-m", "init")


def _call(ts, **kw):
    return schema.make_call(route="chat", provider="anthropic",
                            model="claude-sonnet-4-6", tokens_in=100, tokens_out=10,
                            ts=ts, **kw)


def _pol(root):
    return policy.load(paths.Footprint(root).policy)


# ── (a) month partitioning ──────────────────────────────────────────────────────

def test_write_targets_month_shard_from_row_ts(proj):
    ledger.append_row(proj, "calls", _call("2026-05-10T12:00:00Z"))
    ledger.append_row(proj, "calls", _call("2026-06-20T12:00:00Z"))
    names = sorted(p.name for p in paths.Footprint(proj).ledger.glob("calls*.jsonl"))
    assert names == ["calls-2026-05.jsonl", "calls-2026-06.jsonl"]


def test_reader_globs_legacy_plus_dated_in_chrono_order(proj):
    foot = paths.Footprint(proj)
    foot.ledger.mkdir(parents=True, exist_ok=True)
    # a legacy unpartitioned file (pre-§3.6) plus two dated shards
    ledger.append(foot.ledger / "calls.jsonl", _call("2026-04-01T00:00:00Z", task="LEGACY"))
    ledger.append_row(proj, "calls", _call("2026-06-20T00:00:00Z", task="JUN"))
    ledger.append_row(proj, "calls", _call("2026-05-10T00:00:00Z", task="MAY"))
    assert [c["task"] for c in ledger.calls(proj)] == ["LEGACY", "MAY", "JUN"]


def test_since_skips_below_cutoff_shards(proj):
    ledger.append_row(proj, "calls", _call("2026-05-10T00:00:00Z", task="MAY"))
    ledger.append_row(proj, "calls", _call("2026-06-20T00:00:00Z", task="JUN"))
    # _month_entirely_below is the deterministic skip law (clock-independent)
    import datetime as dt
    cut = dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc)
    assert ledger._month_entirely_below("calls-2026-05.jsonl", cut) is True
    assert ledger._month_entirely_below("calls-2026-06.jsonl", cut) is False
    assert ledger._month_entirely_below("calls.jsonl", cut) is False  # legacy never skipped


def test_truncated_tail_tolerated_per_shard(proj):
    ledger.append_row(proj, "calls", _call("2026-06-01T00:00:00Z", task="OK"))
    shard = paths.Footprint(proj).shard("calls", "2026-06-01T00:00:00Z")
    with shard.open("a") as fh:
        fh.write('{"id": "c_partial", "ts": "2026-06-0')  # crash mid-append
    rows = ledger.calls(proj)
    assert [r["task"] for r in rows] == ["OK"]  # partial line dropped


# ── (b) scope ───────────────────────────────────────────────────────────────────

def test_scope_round_trips_and_serializes(proj):
    cid = ledger.append_row(proj, "calls", _call("2026-06-01T00:00:00Z", scope="billing"))
    assert cid is True
    row = ledger.calls(proj)[0]
    assert row["scope"] == "billing"
    assert "scope" in schema.CALL_FIELDS and "scope" in schema.RECEIPT_FIELDS
    # survives a JSON round-trip (plain serialization)
    assert json.loads(json.dumps(row))["scope"] == "billing"


def test_scope_filter_and_absent_flag_byte_identity(proj):
    for sc, tin in (("billing", 100), ("auth", 300), ("", 50)):
        ledger.append_row(proj, "calls", schema.make_call(route="chat", provider="anthropic",
            model="claude-sonnet-4-6", tokens_in=tin, tokens_out=1, scope=sc,
            ts="2026-06-10T00:00:00Z"))
    pol = _pol(proj)
    billing = report.summarize(proj, pol, scope="billing")
    assert billing["total"]["calls"] == 1 and billing["total"]["tokens_in"] == 100
    # absent flag (None) == today's whole-ledger output, byte-for-byte
    assert report.render_report(report.summarize(proj, pol)) == \
           report.render_report(report.summarize(proj, pol, scope=None))


def _commit_tracked(root, *rel):
    for r in rel:
        p = root / r
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("v = 1\n")
    subprocess.run(("git", "-C", str(root), "add", *rel), check=True, capture_output=True)
    subprocess.run(("git", "-C", str(root), "commit", "-m", "add"), check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def test_scope_for_resolver_single_dir(proj):
    _git_init(proj)
    _commit_tracked(proj, "billing/x.py")
    (proj / "billing" / "x.py").write_text("v = 2\n")  # unstaged change → shows in diff
    assert tasks.scope_for(proj) == "billing"  # exactly one top-level dir


def test_scope_for_multi_dir_is_blank(proj):
    _git_init(proj)
    _commit_tracked(proj, "billing/x.py", "auth/y.py")
    (proj / "billing" / "x.py").write_text("v = 2\n")
    (proj / "auth" / "y.py").write_text("v = 2\n")
    assert tasks.scope_for(proj) == ""  # ambiguous → unknown, fail-open


# ── (c) team aggregation: shared union helper, ledger-sync, --team ───────────────

def test_union_by_id_first_by_id_no_collision():
    a = [{"id": "c_1", "v": 1}, {"id": "r_1", "v": 2}]
    b = [{"id": "c_1", "v": 99}, {"id": "c_2", "v": 3}]  # c_1 repeats
    merged = {r["id"]: r["v"] for r in mergeutil.union_by_id(a, b)}
    assert merged == {"c_1": 1, "r_1": 2, "c_2": 3}  # first-by-id wins, union the rest


def test_union_by_id_collision_callback():
    out = mergeutil.union_by_id([{"id": "x", "v": 1}], [{"id": "x", "v": 2}],
                                on_collision=lambda p, n: n)  # caller picks newest
    assert out == [{"id": "x", "v": 2}]


def test_union_by_id_drops_idless_rows():
    assert mergeutil.union_by_id([{"id": "a"}], [{"no": "id"}]) == [{"id": "a"}]


def test_ledger_sync_dry_run_does_not_write(proj, monkeypatch):
    _git_init(proj)
    ledger.append_row(proj, "calls", _call("2026-06-01T00:00:00Z"))
    monkeypatch.delenv("CAGE_NOTES_WRITE", raising=False)
    res = ledgersync.sync(proj)  # default dry-run
    assert res["wrote"] is False and res["rows"] == 1
    listed = subprocess.run(("git", "-C", str(proj), "notes", "--ref=refs/notes/cage-ledger", "list"),
                            capture_output=True, text=True)
    assert listed.stdout.strip() == ""  # nothing pushed


def test_ledger_sync_writes_under_env(proj):
    _git_init(proj)
    ledger.append_row(proj, "calls", _call("2026-06-01T00:00:00Z"))
    ledger.append_row(proj, "receipts", schema.make_receipt(tool="graphify",
        raw_alternative=1000, actual=200, ts="2026-06-01T00:00:00Z"))
    res = ledgersync.sync(proj, write=True)
    assert res["wrote"] is True and res["rows"] == 2
    team = ledgersync.read_team(proj)
    assert len(team["calls"]) == 1 and len(team["receipts"]) == 1


def test_team_read_falls_back_to_local_when_ref_empty(proj):
    _git_init(proj)
    ledger.append_row(proj, "calls", _call("2026-06-01T00:00:00Z", task="T", scope=""))
    assert ledgersync.read_team(proj) is None  # no ref yet
    rep = report.summarize(proj, _pol(proj), dim="task", team=True)  # degrades to local
    assert rep["total"]["calls"] == 1


def test_team_read_uses_merged_ref(proj):
    _git_init(proj)
    ledger.append_row(proj, "calls", _call("2026-06-01T00:00:00Z", task="T"))
    ledgersync.sync(proj, write=True)
    # drop the local shard: --team must still see the row from the ref
    for p in paths.Footprint(proj).ledger.glob("calls-*.jsonl"):
        p.unlink()
    assert report.summarize(proj, _pol(proj), dim="task")["total"]["calls"] == 0
    assert report.summarize(proj, _pol(proj), dim="task", team=True)["total"]["calls"] == 1
    assert attribution.attribute(proj, "T", _pol(proj), team=True) is not None


# ── (d) ledger-size warning ─────────────────────────────────────────────────────

def _read_capturing(root):
    err, out = io.StringIO(), io.StringIO()
    ledger._warned_dirs.clear()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        ledger.calls(root)
    return out.getvalue(), err.getvalue()


def test_size_warning_silent_below_threshold(proj):
    ledger.append_row(proj, "calls", _call("2026-06-01T00:00:00Z"))
    out, err = _read_capturing(proj)  # default ~418 MB threshold
    assert err == "" and out == ""


def test_size_warning_fires_to_stderr_above_threshold(proj):
    foot = paths.Footprint(proj)
    foot.policy.parent.mkdir(parents=True, exist_ok=True)
    foot.policy.write_text("[ledger]\nwarn_mb = 0.0001\n")  # ~100-byte threshold → fires
    ledger.append_row(proj, "calls", _call("2026-06-01T00:00:00Z"))
    out, err = _read_capturing(proj)
    assert "ledger is" in err and out == ""  # stderr only, stdout untouched


def test_policy_warn_mb_overrides_constant(proj):
    foot = paths.Footprint(proj)
    foot.policy.parent.mkdir(parents=True, exist_ok=True)
    foot.policy.write_text("[ledger]\nwarn_mb = 0.0001\n")
    assert ledger._warn_threshold(foot) == int(0.0001 * 1_000_000)  # policy beats constant
    foot.policy.write_text("")  # no [ledger] → derived fallback
    from cage.constants import LEDGER_WARN_BYTES
    assert ledger._warn_threshold(foot) == LEDGER_WARN_BYTES


def test_size_warning_fires_once_per_dir(proj):
    foot = paths.Footprint(proj)
    foot.policy.parent.mkdir(parents=True, exist_ok=True)
    foot.policy.write_text("[ledger]\nwarn_mb = 0.0001\n")
    ledger.append_row(proj, "calls", _call("2026-06-01T00:00:00Z"))
    ledger._warned_dirs.clear()
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        ledger.calls(proj); ledger.calls(proj); ledger.receipts(proj)
    assert err.getvalue().count("ledger is") == 1  # once per invocation, not per shard


def test_size_warning_swallows_stat_error(proj, monkeypatch):
    # a stat failure during the byte-sum must never raise out of a read
    foot = paths.Footprint(proj)
    foot.policy.parent.mkdir(parents=True, exist_ok=True)
    foot.policy.write_text("[ledger]\nwarn_mb = 0.0001\n")
    ledger.append_row(proj, "calls", _call("2026-06-01T00:00:00Z"))
    import pathlib
    def boom(self):
        raise OSError("stat blew up")
    monkeypatch.setattr(pathlib.Path, "stat", boom)
    ledger._warned_dirs.clear()
    assert len(ledger.calls(proj)) == 1  # read still succeeds


# ── determinism ─────────────────────────────────────────────────────────────────

def test_same_ledger_same_tables(proj):
    for sc, ts in (("billing", "2026-05-01T00:00:00Z"), ("auth", "2026-06-01T00:00:00Z")):
        ledger.append_row(proj, "calls", _call(ts, scope=sc, task="T"))
    pol = _pol(proj)
    a = report.render_report(report.summarize(proj, pol, dim="task"))
    b = report.render_report(report.summarize(proj, pol, dim="task"))
    assert a == b  # same ledger + policy ⇒ byte-identical
