"""F3 — capture is present but token-thin (work/regression/2026-07-22-capture-report.md).

Distinct from `test_capture_health.py`'s triple-gated "installed but capturing
nothing" warning (files==0): this is the narrower, separate signal for an agent
whose log IS matching rows but those rows carry ~0 tokens (Kiro's `tokens_out`
is 0 by design — module docstring, cage/transcript.py). `doctorcmd._capture_quality`
must never fire for the files==0 case (that stays silent per
`test_kiro_present_but_empty_is_silent_not_broken`) and must fire once real,
token-thin rows exist.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from cage import debuglog, doctorcmd, importcmd, ledger, paths, schema
from srcseed import mkcage

_HOME_ENVS = ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_HOME",
              "KIRO_DATA_DIR", "CAGE_VSCODE_USER")


def _isolate(tmp_path, monkeypatch):
    for env in _HOME_ENVS:
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    root = tmp_path / "proj"
    mkcage(root)
    monkeypatch.chdir(root)
    return root


def _plant_kiro_log(root, rows):
    log = paths.kiro_token_log()
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _quality(root):
    return doctorcmd._capture_quality(root)


# ── the detection itself ────────────────────────────────────────────────────

def test_no_calls_is_ok_not_warn(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    level, detail = _quality(root)
    assert level == "ok"


def test_thin_kiro_capture_warns_and_states_the_limit(tmp_path, monkeypatch):
    """A thin log is a WARN that names the agent and the counts — and, since v0.51, says
    there is **no** higher-fidelity route rather than naming one.

    This test used to assert `cage data meter` / `cage data proxy` were recommended. Both
    verbs — and `proxy.py`/`metercmd.py` themselves — were deleted by SURFACE-CUT (v0.50),
    so the assertion went on pinning advice that could not be followed: a test holding a
    dead command in place. The replacement below binds the detail line to the **live
    parser** instead, so any future remedy this check prints has to be runnable."""
    root = _isolate(tmp_path, monkeypatch)
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="chat", provider="kiro", model="agent",
                                   agent="kiro", tokens_in=198, tokens_out=0,
                                   session="s"))
    level, detail = _quality(root)
    assert level == "warn"
    assert "kiro" in detail
    assert "198" in detail and "0 output" in detail
    assert "no higher-fidelity route" in detail
    _assert_every_cage_command_is_live(detail)


def _assert_every_cage_command_is_live(text: str) -> None:
    """Every `cage …` this check prints must parse. Doctor's whole job is surfacing
    silent breakage; advice naming a deleted verb is that failure wearing doctor's
    uniform, and it is what this file previously asserted *for*."""
    import re

    from cage import wiringscan
    for m in re.finditer(r"`?cage ([a-z][a-z-]*(?: [a-z][a-z-]*)?)", text):
        verbs = tuple(m.group(1).split())
        assert wiringscan.is_live_verb(verbs) or wiringscan.is_live_verb(verbs[:1]), \
            f"doctor advice names a dead verb: cage {' '.join(verbs)}"


def test_healthy_agent_with_real_output_tokens_does_not_warn(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="chat", provider="anthropic",
                                   model="claude-sonnet-4-6", agent="claude-code",
                                   tokens_in=1000, tokens_out=200, session="s"))
    level, _ = _quality(root)
    assert level == "ok"


def test_mixed_agents_only_the_thin_one_is_named(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="chat", provider="anthropic",
                                   model="claude-sonnet-4-6", agent="claude-code",
                                   tokens_in=1000, tokens_out=200, session="s"))
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="chat", provider="kiro", model="agent",
                                   agent="kiro", tokens_in=50, tokens_out=0,
                                   session="s2"))
    level, detail = _quality(root)
    assert level == "warn"
    assert "kiro" in detail
    assert "claude" not in detail  # the healthy agent is never named


def test_registered_as_a_doctor_check(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="chat", provider="kiro", model="agent",
                                   agent="kiro", tokens_in=198, tokens_out=0,
                                   session="s"))
    res = doctorcmd.run(root)
    row = next(c for c in res["checks"] if c["name"] == "capture-quality")
    assert row["level"] == "warn"
    assert "kiro" in row["detail"]


# ── the boundary with the existing files==0 gate ────────────────────────────

def test_never_fires_on_the_files_zero_case(tmp_path, monkeypatch):
    """A present-but-EMPTY kiro log (0 rows) must stay `ok` here too — this check
    requires calls > 0, so it can never collide with the separate files==0 gate's
    documented silence (test_capture_health.py::test_kiro_present_but_empty_is_silent_not_broken)."""
    root = _isolate(tmp_path, monkeypatch)
    _plant_kiro_log(root, [])
    importcmd.run(root, "kiro",
                  SimpleNamespace(agent="kiro", path=None, project=None, since=None))
    level, _ = _quality(root)
    assert level == "ok"


# ── import-time logging (the src/exists/bytes/rows/tokens visibility) ──────

def _debug_events(root, event):
    log = paths.Footprint(root).debug_log
    if not log.exists():
        return []
    out = []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("event") == event:
            out.append(r)
    return out


def test_kiro_src_logs_existed_bytes_rows_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv("CAGE_DEBUG", "1")
    root = _isolate(tmp_path, monkeypatch)
    _plant_kiro_log(root, [
        {"model": "agent", "provider": "kiro", "promptTokens": 120, "generatedTokens": 0},
        {"model": "agent", "provider": "kiro", "promptTokens": 78, "generatedTokens": 0},
    ])
    importcmd.run(root, "kiro",
                  SimpleNamespace(agent="kiro", path=None, project=None, since=None))
    # F3's visibility rides with kiro's DATA. Since ADR-LEDGER (2026-08-15) that is
    # THIS run's own ledger — no separate machine sink for the trace to split across.
    events = _debug_events(root, "kiro-src")
    assert len(events) == 1
    e = events[0]
    assert e["exists"] is True
    assert e["bytes"] > 0
    assert e["rows_parsed"] == 2
    assert e["tokens_in"] == 198
    assert e["tokens_out"] == 0
    # counts-never-content: the src is a path, never the parsed token content
    assert "promptTokens" not in json.dumps(e)


def test_kiro_src_logs_nonexistent_source_honestly(tmp_path, monkeypatch):
    monkeypatch.setenv("CAGE_DEBUG", "1")
    root = _isolate(tmp_path, monkeypatch)
    # no log planted — src resolves but the file is absent
    importcmd.run(root, "kiro",
                  SimpleNamespace(agent="kiro", path=None, project=None, since=None))
    events = _debug_events(root, "kiro-src")
    assert len(events) == 1
    assert events[0]["exists"] is False
    assert events[0]["rows_parsed"] == 0


def test_kiro_src_logging_is_unconditional_even_when_cursor_skips(tmp_path, monkeypatch):
    """The whole point of F3: visibility must not depend on there being anything
    NEW to import. A second run against an unchanged file (cursor-skipped) must
    still log the src's current state."""
    monkeypatch.setenv("CAGE_DEBUG", "1")
    root = _isolate(tmp_path, monkeypatch)
    _plant_kiro_log(root, [
        {"model": "agent", "provider": "kiro", "promptTokens": 198, "generatedTokens": 0},
    ])
    args = SimpleNamespace(agent="kiro", path=None, project=None, since=None)
    importcmd.run(root, "kiro", args)
    importcmd.run(root, "kiro", args)  # unchanged file — cursor should skip re-ingest
    events = _debug_events(root, "kiro-src")
    assert len(events) == 2  # logged both times regardless of cursor state


def test_kiro_src_logging_never_breaks_import_on_error(tmp_path, monkeypatch):
    """Fail-open: a broken planted log must not abort the import."""
    monkeypatch.setenv("CAGE_DEBUG", "1")
    root = _isolate(tmp_path, monkeypatch)
    log = paths.kiro_token_log()
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("not json at all\n", encoding="utf-8")
    result = importcmd.run(root, "kiro",
                           SimpleNamespace(agent="kiro", path=None, project=None, since=None))
    assert result  # completes without raising


def test_kiro_leaves_no_routing_pointer_since_the_reversal(tmp_path, monkeypatch):
    """Before ADR-LEDGER (2026-08-15), a routed kiro leg left a `route="sink"` pointer
    in the sweep root's own debug log — the signpost that made the split trace
    navigable (F3). Since the reversal there is no split to signpost: kiro's own
    `kiro-src` events (asserted elsewhere in this file) already live in this same log,
    so no separate pointer event is emitted."""
    monkeypatch.setenv("CAGE_DEBUG", "1")
    root = _isolate(tmp_path, monkeypatch)
    importcmd.run(root, "kiro",
                  SimpleNamespace(agent="kiro", path=None, project=None, since=None))
    routes = [e for e in _debug_events(root, "import") if e.get("route") == "sink"]
    assert routes == []
