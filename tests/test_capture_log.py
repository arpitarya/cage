"""Always-on capture breadcrumb — `state/capture.log` (F6, docs/debugging-capture.md).

One line per agent per real import run: `ts · agent · files_seen · rows_new ·
rows_total · src`. Unlike `debug.log` this is never gated on `CAGE_DEBUG` — it's the
standing proof-of-capture the 2026-07-22 report needed to make F1 diagnosable.
Size-managed by the `capture-log` cleanup class; a write failure is fail-open and
traced under `CAGE_DEBUG`.
"""
from __future__ import annotations

import datetime as _dt
import json
from types import SimpleNamespace

from cage import agents, capturelog, cleanup, debuglog, importcmd, paths, policy

_HOME_ENVS = ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_HOME",
              "KIRO_DATA_DIR", "CAGE_VSCODE_USER")


def _isolate(tmp_path, monkeypatch):
    for env in _HOME_ENVS:
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    return root


def _imp(root, agent="all"):
    return importcmd.run(root, agent,
                         SimpleNamespace(agent=agent, path=None, project=None, since=None))


def _rows(root):
    return capturelog.tail(root, 0)


def _codex_log(root):
    d = paths.codex_home() / "sessions" / "2026" / "06"
    d.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"timestamp": "2026-06-14T10:00:00Z", "type": "event_msg",
                       "payload": {"type": "token_count", "info": {
                           "total_token_usage": {"input_tokens": 100, "output_tokens": 40,
                                                 "cached_input_tokens": 0}},
                           "model": "gpt-5.3-codex"}})
    (d / "rollout-2026-06-14-x.jsonl").write_text(line + "\n", encoding="utf-8")


# ── one line per swept agent per real run ──────────────────────────────────────

def test_real_import_appends_one_line_per_swept_agent(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    _imp(root, "all")
    rows = _rows(root)
    assert {r["agent"] for r in rows} == set(agents.SURFACES)
    for r in rows:
        assert set(r) >= {"ts", "agent", "files_seen", "rows_new", "rows_total", "src"}


def test_single_agent_import_appends_only_that_agent(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    _imp(root, "codex")
    assert [r["agent"] for r in _rows(root)] == ["codex"]


def test_first_ever_import_records_rows_new_and_rows_total(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.codex_home().mkdir(parents=True)
    _codex_log(root)
    _imp(root, "codex")
    rows = [r for r in _rows(root) if r["agent"] == "codex"]
    assert len(rows) == 1
    assert rows[0]["files_seen"] == 1
    assert rows[0]["rows_new"] == 1
    assert rows[0]["rows_total"] == 1
    assert rows[0]["src"]  # a tilde/absolute path, never empty on a real hit


def test_first_import_agrees_with_capture_health(tmp_path, monkeypatch):
    # Cross-check against the F2 fix (docs/regression/2026-07-22-capture-report.md):
    # capture.log's rows_new/rows_total must agree with cursors["_health"]["captured"]
    # for the very first import of an agent, in the SAME run.
    root = _isolate(tmp_path, monkeypatch)
    paths.codex_home().mkdir(parents=True)
    _codex_log(root)
    _imp(root, "codex")
    health = importcmd.capture_health(root)["codex"]
    row = next(r for r in _rows(root) if r["agent"] == "codex")
    assert health["captured"] is True
    assert row["rows_new"] > 0 and row["rows_total"] > 0


def test_second_import_no_new_rows_keeps_rows_total_steady(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.codex_home().mkdir(parents=True)
    _codex_log(root)
    _imp(root, "codex")
    _imp(root, "codex")  # re-import: cursor-unchanged, nothing new
    rows = [r for r in _rows(root) if r["agent"] == "codex"]
    assert len(rows) == 2
    assert rows[1]["rows_new"] == 0
    assert rows[1]["rows_total"] == 1  # the one row from the first run, still there


# ── no-op / throttled reads stay silent ────────────────────────────────────────

def test_no_op_throttled_read_appends_nothing(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")  # opt back in over isolated homes
    args = SimpleNamespace(agent="all", path=None, project=None, since=None, no_import=False)
    pol = policy.load(None)
    importcmd.ensure_captured(root, args, pol=pol)  # first sweep — real, appends
    n_after_first = len(_rows(root))
    assert n_after_first == len(agents.SURFACES)
    summary = importcmd.ensure_captured(root, args, pol=pol)  # throttled — no sweep at all
    assert summary is None
    assert len(_rows(root)) == n_after_first  # not a single new line


def test_capture_disabled_appends_nothing(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CAGE_CAPTURE", "0")
    _imp(root, "all")
    assert _rows(root) == []


# ── size management (cleanup) ──────────────────────────────────────────────────

def test_capture_log_is_size_managed_by_cleanup(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    _imp(root, "codex")
    foot = paths.Footprint(root)
    old_ts = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=90)).isoformat()
    rows = [json.loads(l) for l in
            foot.capture_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert rows
    for r in rows:
        r["ts"] = old_ts
    foot.capture_log.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    pol = policy.load(None)
    counts = cleanup.prune(root, pol, days=30)
    assert counts.get("capture-log")
    assert foot.capture_log.read_text(encoding="utf-8").strip() == ""


def test_capture_log_never_in_the_never_list():
    assert "state/capture.log" not in cleanup.NEVER
    assert "capture.log" not in cleanup.NEVER
    assert "capture-log" in cleanup.CLASSES


# ── fail-open ──────────────────────────────────────────────────────────────────

def test_write_failure_is_fail_open_and_logged(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    state = root / ".cage" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "capture.log").mkdir()  # a directory in the way → the append raises
    lines = _imp(root, "codex")  # must not raise; import still succeeds
    assert any("codex" in l for l in lines)
    events = [e for e in debuglog.tail(root, 0) if e.get("event") == "exception"]
    assert any(e.get("context") == "capture.log" for e in events)


# ── doctor bundle ──────────────────────────────────────────────────────────────

# ── determinism: never read by any derived view ────────────────────────────────

def test_derived_views_byte_identical_with_and_without_the_breadcrumb(tmp_path, monkeypatch):
    from cage import demo, ledger, policy, report
    root = _isolate(tmp_path, monkeypatch)
    demo.seed(root)
    pol = policy.load(None)
    rep = report.summarize(root, pol, dim="agent")
    before = report.render_report(rep)
    foot = paths.Footprint(root)
    assert not foot.capture_log.exists()  # no import has run yet — nothing written
    capturelog.record(root, "claude", files_seen=9, rows_new=3, rows_total=12, src="~/x")
    assert foot.capture_log.exists()
    after = report.render_report(report.summarize(root, pol, dim="agent"))
    assert before == after  # the breadcrumb existing/growing never changes a rendered table


def test_doctor_bundle_includes_capture_log(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    _imp(root, "codex")
    from cage import doctorbundle
    out = doctorbundle.run(root, str(tmp_path / "bundle.zip"))
    import zipfile
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "state/capture.log" in names
