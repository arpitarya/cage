"""Fleet study (roadmap P5) — machine id, phase markers, bundles, paired report.

Exact-number assertions over 7 simulated machines (5 complete, 1 with a mid-week
gap, 1 missing the second phase): paired delta −7,000 tok / −$0.0350 per
machine-day at the bundled opus prices ($5/$25 per MTok).
"""
from __future__ import annotations

import getpass
import json
import socket
import zipfile
from types import SimpleNamespace

import pytest

from cage import clicmds, ledger, machine, paths, policy, schema, study, tasks
from cage.constants import MIN_COMPARE_N
from cage.errors import CageError

_MODEL = dict(route="chat", provider="anthropic", model="claude-opus-4-8", agent="claude-code")


def _seed_machine(base, name, plugin_days, baseline=True):
    root = base / name
    (root / ".cage").mkdir(parents=True)
    machine.ensure(root)
    if baseline:
        study.start(root, "baseline", ts="2026-06-01T00:00:00Z")
        for d in ("01", "02", "03"):
            ledger.append_row(root, "calls", schema.make_call(
                tokens_in=12_000, tokens_out=500, session=f"s-{name}",
                ts=f"2026-06-{d}T10:00:00Z", **_MODEL))
        study.stop(root, ts="2026-06-03T23:59:59Z")
    if plugin_days:
        study.start(root, "plugin", ts="2026-06-08T00:00:00Z")
        for d in plugin_days:
            ledger.append_row(root, "calls", schema.make_call(
                tokens_in=5_000, tokens_out=500, session=f"s-{name}",
                ts=f"2026-06-{d}T10:00:00Z", **_MODEL))
        study.stop(root, ts="2026-06-10T23:59:59Z")
    return root


@pytest.fixture
def fleet(tmp_path):
    """7 machine roots + their bundles + a fresh analysis root."""
    roots = [_seed_machine(tmp_path, f"mach-{i}", ("08", "09", "10")) for i in range(1, 6)]
    roots.append(_seed_machine(tmp_path, "mach-6", ("08", "10")))   # gap: 06-09
    roots.append(_seed_machine(tmp_path, "mach-7", None))           # missing plugin
    bundles = [str(study.export_bundle(r, str(tmp_path / f"b{i}.zip")))
               for i, r in enumerate(roots)]
    analysis = tmp_path / "analysis"
    (analysis / ".cage").mkdir(parents=True)
    return analysis, bundles, roots


# ── machine id ────────────────────────────────────────────────────────────────

def test_machine_id_opaque_and_stable(proj):
    mid = machine.ensure(proj)
    assert mid.startswith("m_") and len(mid) == 18
    assert machine.ensure(proj) == mid  # generated once
    for leak in (socket.gethostname(), getpass.getuser()):
        assert leak.lower() not in mid.lower()  # opaque — nothing derivable


def test_rows_stamped_only_after_enrollment(proj):
    ledger.append_row(proj, "calls", schema.make_call(
        tokens_in=1, tokens_out=1, ts="2026-06-01T10:00:00Z", **_MODEL))
    assert "machine" not in ledger.calls(proj)[0]  # legacy contract untouched
    mid = machine.ensure(proj)
    ledger.append_row(proj, "calls", schema.make_call(
        tokens_in=2, tokens_out=1, ts="2026-06-01T11:00:00Z", **_MODEL))
    assert ledger.calls(proj)[1]["machine"] == mid
    tasks.record(proj, "t1", outcome="ok", ts="2026-06-01T12:00:00Z", snapshot=False)
    assert tasks.read(proj)["t1"]["machine"] == mid  # tasks stamped too


# ── phase markers ─────────────────────────────────────────────────────────────

def test_phase_resolution_edge_cases(proj):
    study.start(proj, "a", ts="2026-06-02T00:00:00Z")
    study.start(proj, "b", ts="2026-06-04T00:00:00Z")  # start-without-stop: b wins forward
    tl = study._timelines(study.markers(proj))[machine.machine_id(proj)]
    assert study.phase_of("2026-06-01T09:00:00Z", tl) == ""      # pre-enrollment → unphased
    assert study.phase_of("2026-06-03T09:00:00Z", tl) == "a"
    assert study.phase_of("2026-06-05T09:00:00Z", tl) == "b"     # last marker wins
    assert study.phase_of("2026-07-01T09:00:00Z", tl) == "b"     # no stop → extends
    study.stop(proj, ts="2026-07-02T00:00:00Z")
    tl = study._timelines(study.markers(proj))[machine.machine_id(proj)]
    assert study.phase_of("2026-07-03T09:00:00Z", tl) == ""      # stopped → unphased


def test_phase_label_guard(proj):
    with pytest.raises(CageError, match="phase must be one short token"):
        study.start(proj, "two words")


# ── bundles ───────────────────────────────────────────────────────────────────

def test_bundle_members_and_counts_only_manifest(fleet):
    _, bundles, roots = fleet
    with zipfile.ZipFile(bundles[0]) as zf:
        assert set(zf.namelist()) == {"manifest.json", "calls.jsonl", "receipts.jsonl",
                                      "tasks.jsonl", "study.jsonl"}
        man = json.loads(zf.read("manifest.json"))
        assert man["machine"] == machine.machine_id(roots[0])
        assert man["rows"] == {"calls": 6, "receipts": 0, "tasks": 0, "study": 4}
        assert man["span"] == {"first": "2026-06-01T10:00:00Z", "last": "2026-06-10T10:00:00Z"}


def test_import_merges_and_is_idempotent(fleet):
    analysis, bundles, _ = fleet
    lines = study.import_bundles(analysis, bundles)
    assert len(lines) == 7 and "merged 6 calls" in lines[0]
    assert len(ledger.calls(analysis)) == 6 * 5 + 5 + 3   # 5 full + gap machine + baseline-only
    shard_bytes = b"".join(p.read_bytes() for p in paths.Footprint(analysis).shards("calls"))
    again = study.import_bundles(analysis, bundles)
    assert all("merged 0 calls" in ln for ln in again)     # double import: nothing new
    assert b"".join(p.read_bytes()
                    for p in paths.Footprint(analysis).shards("calls")) == shard_bytes


def test_task_update_rows_survive_merge(proj, tmp_path):
    machine.ensure(proj)
    tasks.record(proj, "t1", ts="2026-06-01T10:00:00Z", snapshot=False)          # open
    tasks.record(proj, "t1", outcome="ok", ts="2026-06-02T10:00:00Z", snapshot=False)  # close
    b = study.export_bundle(proj, str(tmp_path / "b.zip"))
    analysis = tmp_path / "an"
    (analysis / ".cage").mkdir(parents=True)
    study.import_bundles(analysis, [str(b)])
    # merge identity is the whole row for tasks — the close update is not dropped
    assert tasks.read(analysis)["t1"].get("outcome") == "ok"


def test_bad_bundle_is_typed_error(proj, tmp_path):
    bad = tmp_path / "not-a-bundle.zip"
    bad.write_text("junk", encoding="utf-8")
    with pytest.raises(CageError, match="cannot import study bundle"):
        study.import_bundles(proj, [str(bad)])


# ── the report ────────────────────────────────────────────────────────────────

def test_report_exact_coverage_and_paired_delta(fleet):
    analysis, bundles, _ = fleet
    study.import_bundles(analysis, bundles)
    d = study.summarize(analysis, policy.load(None))
    assert d["phases"] == ["baseline", "plugin"] and d["paired_machines"] == 6
    gapped = next(m for m in d["machines"] if m["phases"]["plugin"]["gaps"])
    assert gapped["phases"]["plugin"] == {**gapped["phases"]["plugin"],
                                          "days": 2, "gaps": ["2026-06-09"]}
    missing = next(m for m in d["machines"] if not m["phases"]["plugin"]["days"])
    assert missing["phases"]["baseline"]["days"] == 3
    assert d["delta"] == {"ok": True, "method": "estimated",
                          "d_tokens_per_day": -7_000.0, "d_usd_per_day": -0.035,
                          "per_machine": d["delta"]["per_machine"]}
    assert set(d["delta"]["per_machine"].values()) == {-0.035}
    assert d["pooled"]["baseline"]["n_days"] == 21 and d["pooled"]["plugin"]["n_days"] == 17
    text = study.render_study(d)
    assert "⚠ gap days: 2026-06-09" in text
    assert "MISSING — no rows in this phase" in text
    assert "-7,000 tok/day · -$0.0350/day per machine (estimated)" in text
    assert "not a randomized experiment" in text
    assert "n=6 machines" in text  # only complete machines pair


def test_refusal_below_min_machines(tmp_path):
    analysis = tmp_path / "an"
    (analysis / ".cage").mkdir(parents=True)
    bundles = [str(study.export_bundle(_seed_machine(tmp_path, f"m{i}", ("08", "09", "10")),
                                       str(tmp_path / f"b{i}.zip"))) for i in range(2)]
    study.import_bundles(analysis, bundles)
    d = study.summarize(analysis, policy.load(None))
    assert d["delta"] == {"ok": False,
                          "reason": f"insufficient machines with both phases (n=2 < {MIN_COMPARE_N})"}
    assert "it never numbers" in study.render_study(d)


def test_pre_enrollment_rows_counted_unphased(proj):
    ledger.append_row(proj, "calls", schema.make_call(
        tokens_in=100, tokens_out=10, ts="2026-05-20T10:00:00Z", **_MODEL))  # before any marker
    machine.ensure(proj)
    study.start(proj, "baseline", ts="2026-06-01T00:00:00Z")
    d = study.summarize(proj, policy.load(None))
    assert d["unphased_calls"] == 1  # visible, excluded from deltas — never silent


def test_clock_skew_resolves_per_machine(tmp_path):
    """A row lands in the phase its OWN machine's markers say — another machine's
    overlapping window can never cross-assign it."""
    a = _seed_machine(tmp_path, "a", ("08", "09", "10"))
    b = tmp_path / "b"
    (b / ".cage").mkdir(parents=True)
    machine.ensure(b)
    study.start(b, "plugin", ts="2026-06-01T00:00:00Z")  # b's clock says June 1 is plugin
    ledger.append_row(b, "calls", schema.make_call(
        tokens_in=1_000, tokens_out=100, ts="2026-06-02T10:00:00Z", **_MODEL))
    analysis = tmp_path / "an"
    (analysis / ".cage").mkdir(parents=True)
    study.import_bundles(analysis, [str(study.export_bundle(a, str(tmp_path / "ba.zip"))),
                                    str(study.export_bundle(b, str(tmp_path / "bb.zip")))])
    d = study.summarize(analysis, policy.load(None))
    mb = next(m for m in d["machines"] if m["machine"] == machine.machine_id(b))
    assert mb["phases"]["plugin"]["days"] == 1   # b's June-2 row is plugin, per b's markers
    assert mb["phases"]["baseline"]["days"] == 0  # …despite a's baseline covering June 2


def test_deterministic_and_cli(fleet, monkeypatch, capsys):
    analysis, bundles, _ = fleet
    monkeypatch.chdir(analysis)
    assert clicmds.cmd_import(SimpleNamespace(bundles=bundles)) == 0
    capsys.readouterr()
    args = SimpleNamespace(action="report", phase=None, json=True)
    assert clicmds.cmd_study(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schemaVersion"] == "cage.v1" and payload["command"] == "study"
    assert payload["data"]["delta"]["d_tokens_per_day"] == -7_000.0
    pol = policy.load(None)
    assert study.render_study(study.summarize(analysis, pol)) == \
        study.render_study(study.summarize(analysis, pol))
