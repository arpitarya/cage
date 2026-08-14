"""KIRO-METRICS — the `.cage/ledger/kiro/` per-chat metrics ledger.

Capture-only: a new row shape (`schema.make_kiro_metric`) fed by Kiro's IDE
`devdata.sqlite` and CLI SQLite store, collapsed last-write-wins at read
(`ledger.kiro_metrics`), and read by NO derived view in this build. What this file
pins, following `docs/kiro-metrics-ledger.handoff.md` §9 (mirrors
`tests/test_copilot_metrics.py`'s structure — the twin kind):

1. The substrate — enum validation, omit-at-zero, None-sentinel `credits`, `km_` ids.
2. The IDE parser records exactly what `devdata.sqlite` carries, verbatim.
3. The CLI parser: conv + turn rows, the upgrade-watch (NULL token slots today), and
   both `conversations_v2`/`conversations` table shapes.
4. `parse_kiro_cli_credits` stays byte-identical after the `_kiro_cli_conversations`
   extraction (the existing `tests/test_kiro_routing.py` suite is the primary pin;
   this file adds one direct regression check too).
5. Counts-never-content: a `history[].user` sentinel never reaches a written shard byte.
6. Re-import is idempotent; a grown conversation appends a fresh row and the collapse
   read resolves to the latest/largest.
7. Routing (ADR 0006, inherited never re-decided): IDE rows land only in the routed
   sink; CLI rows stay workspace-scoped to the project.
8. No derived view moves by one byte whether the `kiro/` tree exists or not.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from cage import cli, doctorcmd, importcmd, ledger, paths, schema, transcript
from srcseed import mkcage

PROMPT_BODY_SENTINEL = "please refactor the auth module to use JWT tokens instead"

_HOME_ENVS = ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_HOME",
              "KIRO_DATA_DIR", "CAGE_VSCODE_USER")


def _isolate(tmp_path, monkeypatch, name="proj"):
    """The `test_kiro_routing.py` isolation helper, duplicated here (own file, own
    fixtures) — every kiro home dir env points inside `tmp_path`, so this test's
    machine-ledger writes never touch a real `~/.kiro` or a sibling test's tmp dir."""
    for env in _HOME_ENVS:
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    root = tmp_path / name
    mkcage(root)
    monkeypatch.chdir(root)
    return root


def _args(agent="all", **kw):
    return SimpleNamespace(agent=agent, path=None, project=None, since=None, **kw)


# ── 1 · substrate ────────────────────────────────────────────────────────────

def test_make_kiro_metric_validates_source():
    with pytest.raises(ValueError):
        schema.make_kiro_metric(source="bogus")


def test_make_kiro_metric_omit_at_zero():
    row = schema.make_kiro_metric(source="ide", metric_id="km_x")
    for k in ("session", "surface", "turn", "model", "provider", "tokens_in",
              "tokens_out", "cached_in", "cached_out", "credits", "context_pct",
              "turns", "chunks", "prompt_bytes", "response_bytes", "tool_uses",
              "row_ref", "project"):
        assert k not in row


def test_make_kiro_metric_none_sentinel_credits_never_omit_at_default():
    """`credits` is None-sentinel — a recorded 0.0 must survive, distinct from an
    omitted (never-recorded) figure (the `make_call.credits` law, generalized)."""
    zero = schema.make_kiro_metric(source="cli-conv", credits=0.0, metric_id="km_zero")
    assert zero["credits"] == 0.0
    absent = schema.make_kiro_metric(source="cli-conv", metric_id="km_absent")
    assert "credits" not in absent


def test_make_kiro_metric_default_id_namespace():
    row = schema.make_kiro_metric(source="ide")
    assert row["id"].startswith("km_")


# ── fixture builders ─────────────────────────────────────────────────────────

def _devdata_db(path: Path, rows: list[tuple]) -> Path:
    """rows = [(id, tokens_prompt, tokens_generated, timestamp)] — a minimal
    `devdata.sqlite` `tokens_generated` table, plus one extra unrecognized column to
    prove the explicit-column SELECT (`parse_kiro_ide_metrics`) survives it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE tokens_generated (id INTEGER, tokens_prompt INTEGER, "
               "tokens_generated INTEGER, timestamp TEXT, model TEXT)")
    for row_id, tin, tout, ts in rows:
        con.execute("INSERT INTO tokens_generated VALUES (?,?,?,?,?)",
                   (row_id, tin, tout, ts, "unexpected-extra-column-value"))
    con.commit()
    con.close()
    return path


def _cli_turn(*, message_id="", model_id="claude-haiku-4.5", ts_ms=1755080400000,
             chunks=3, tool_uses=1, prompt_bytes=42, response_bytes=99,
             context_pct=3.0, tokens: dict | None = None) -> dict:
    rm = {"model_id": model_id, "context_usage_percentage": context_pct,
         "stream_end_timestamp_ms": ts_ms,
         "time_between_chunks": list(range(chunks)),
         "tool_use_ids_and_names": [[f"t{i}", "execute_bash"] for i in range(tool_uses)],
         "user_prompt_length": prompt_bytes, "response_size": response_bytes}
    if message_id:
        rm["message_id"] = message_id
    if tokens:
        rm.update(tokens)
    return {"user": {"content": PROMPT_BODY_SENTINEL}, "request_metadata": rm}


def _cli_doc(*, model_id="claude-haiku-4.5", credits=0.5, turns=None) -> dict:
    doc = {"model_info": {"model_id": model_id}, "history": turns or []}
    if credits is not None:
        doc["user_turn_metadata"] = {"usage_info": [{"value": credits, "unit": "credit"}]}
    return doc


def _cli_db(path: Path, rows: list[tuple], table: str = "conversations_v2") -> Path:
    """rows = [(key, conversation_id, doc, updated_at)]. ``table="conversations"``
    builds the older `(key, value)`-only shape, `conversation_id` inline in the doc —
    the `_kiro_cli_conversations` fallback path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    if table == "conversations_v2":
        con.execute("CREATE TABLE conversations_v2 (key TEXT, conversation_id TEXT, "
                   "value TEXT, created_at INTEGER, updated_at INTEGER)")
        for key, cid, doc, updated_at in rows:
            con.execute("INSERT INTO conversations_v2 VALUES (?,?,?,?,?)",
                       (key, cid, json.dumps(doc), 1, updated_at))
    else:
        con.execute("CREATE TABLE conversations (key TEXT, value TEXT)")
        for key, cid, doc, _updated_at in rows:
            con.execute("INSERT INTO conversations VALUES (?,?)",
                       (key, json.dumps({**doc, "conversation_id": cid})))
    con.commit()
    con.close()
    return path


# ── 2 · IDE devdata.sqlite parser ────────────────────────────────────────────

def test_ide_parser_exact_rows(tmp_path):
    db = _devdata_db(tmp_path / "devdata.sqlite",
                     [(1, 100, 20, "2026-08-13T10:00:00Z"),
                      (2, 50, 0, "2026-08-13T10:05:00Z")])
    rows = transcript.parse_kiro_ide_metrics(db)
    assert len(rows) == 2
    assert rows[0]["source"] == "ide" and rows[0]["surface"] == "ide"
    assert rows[0]["session"] == "kiro"
    assert rows[0]["tokens_in"] == 100 and rows[0]["tokens_out"] == 20
    assert rows[0]["row_ref"] == "1"
    assert rows[0]["ts"] == "2026-08-13T10:00:00.000Z"
    assert rows[1]["tokens_in"] == 50 and "tokens_out" not in rows[1]


def test_ide_parser_skips_both_counts_zero(tmp_path):
    db = _devdata_db(tmp_path / "devdata.sqlite", [(1, 0, 0, "2026-08-13T10:00:00Z")])
    assert transcript.parse_kiro_ide_metrics(db) == []


def test_ide_parser_survives_extra_unknown_column(tmp_path):
    """`_devdata_db` always adds an extra `model` column beyond the four
    (`id, tokens_prompt, tokens_generated, timestamp`) the explicit-column SELECT
    reads — it must never leak into the row, and its presence must never crash."""
    db = _devdata_db(tmp_path / "devdata.sqlite", [(1, 10, 5, "2026-08-13T10:00:00Z")])
    rows = transcript.parse_kiro_ide_metrics(db)
    assert len(rows) == 1
    assert "model" not in rows[0]


def test_ide_parser_missing_db_returns_empty(tmp_path):
    assert transcript.parse_kiro_ide_metrics(tmp_path / "nope.sqlite") == []


def test_ide_parser_epoch_ms_timestamp(tmp_path):
    """`timestamp` shape is one of the pending real-store probes — the fallback path
    for a raw epoch-ms number must also work, not just ISO text."""
    db = _devdata_db(tmp_path / "devdata.sqlite", [(1, 10, 5, 1755080400000)])
    rows = transcript.parse_kiro_ide_metrics(db)
    assert rows[0]["ts"] is not None


# ── 3 · CLI SQLite store parser ──────────────────────────────────────────────

def test_cli_metrics_parser_conv_and_turn_rows(tmp_path):
    doc = _cli_doc(credits=0.5, turns=[_cli_turn(message_id="m1")])
    db = _cli_db(tmp_path / "data.sqlite3", [("/w/proj", "c1", doc, 1755080500000)])
    rows = transcript.parse_kiro_cli_metrics(db)
    conv = [r for r in rows if r["source"] == "cli-conv"][0]
    turn = [r for r in rows if r["source"] == "cli-turn"][0]
    assert conv["session"] == "c1" and conv["surface"] == "cli"
    assert conv["credits"] == 0.5 and conv["turns"] == 1
    assert conv["project"] == "proj"
    assert turn["session"] == "c1" and turn["turn"] == "0" and turn["row_ref"] == "m1"
    assert turn["chunks"] == 3 and turn["tool_uses"] == 1
    assert turn["prompt_bytes"] == 42 and turn["response_bytes"] == 99
    assert turn["context_pct"] == 3.0
    assert "tokens_in" not in turn and "cached_in" not in turn  # NULL today — upgrade-watch


def test_cli_metrics_upgrade_watch_records_non_null_token_slots(tmp_path):
    """The day kiro-cli fills `request_metadata`'s token slots, capture must pick them
    up with zero code change — this pins that path with a fixture that has them."""
    doc = _cli_doc(credits=0.2, turns=[_cli_turn(tokens={
        "uncached_input_tokens": 120, "output_tokens": 45,
        "cache_read_input_tokens": 10, "cache_write_input_tokens": 3})])
    db = _cli_db(tmp_path / "data.sqlite3", [("/w/proj", "c2", doc, 1755080500000)])
    turn = [r for r in transcript.parse_kiro_cli_metrics(db) if r["source"] == "cli-turn"][0]
    assert turn["tokens_in"] == 120 and turn["tokens_out"] == 45
    assert turn["cached_in"] == 10 and turn["cached_out"] == 3


def test_cli_metrics_conversations_table_variant(tmp_path):
    doc = _cli_doc(credits=0.75, turns=[_cli_turn(message_id="mX")])
    db = _cli_db(tmp_path / "data.sqlite3", [("/w/proj", "c3", doc, None)],
               table="conversations")
    rows = transcript.parse_kiro_cli_metrics(db)
    conv = [r for r in rows if r["source"] == "cli-conv"][0]
    turn = [r for r in rows if r["source"] == "cli-turn"][0]
    assert conv["session"] == "c3" and conv["credits"] == 0.75
    assert turn["row_ref"] == "mX"


def test_cli_metrics_credits_none_sentinel_when_usage_info_absent(tmp_path):
    doc = {"model_info": {}, "history": [_cli_turn()]}  # no user_turn_metadata at all
    db = _cli_db(tmp_path / "data.sqlite3", [("/w/proj", "c4", doc, 1)])
    conv = [r for r in transcript.parse_kiro_cli_metrics(db) if r["source"] == "cli-conv"][0]
    assert "credits" not in conv


def test_cli_metrics_credits_real_zero_recorded_distinct_from_absent(tmp_path):
    """`usage_info` present (even empty) sums to a real 0.0 and must be RECORDED —
    only a wholly-absent `user_turn_metadata` is the None-sentinel case."""
    doc = {"model_info": {}, "user_turn_metadata": {"usage_info": []}, "history": []}
    db = _cli_db(tmp_path / "data.sqlite3", [("/w/proj", "c5", doc, 1)])
    conv = [r for r in transcript.parse_kiro_cli_metrics(db) if r["source"] == "cli-conv"]
    assert len(conv) == 1
    assert conv[0]["credits"] == 0.0


def test_cli_metrics_missing_db_returns_empty(tmp_path):
    assert transcript.parse_kiro_cli_metrics(tmp_path / "nope.sqlite3") == []


# ── 4 · parse_kiro_cli_credits stays byte-identical after the refactor ──────

def test_parse_kiro_cli_credits_regression_pin(tmp_path):
    doc = _cli_doc(credits=0.5, turns=[_cli_turn()])
    db = _cli_db(tmp_path / "data.sqlite3", [("/w/proj", "c1", doc, 1755080500000)])
    rows = transcript.parse_kiro_cli_credits(db)
    assert len(rows) == 1
    r = rows[0]
    assert r["session"] == "c1" and r["agent"] == "kiro" and r["credits"] == 0.5
    assert r["turns"] == 1 and r["project"] == "proj"
    assert r["id"].startswith("k_cred")


def test_kiro_cli_conversations_enumerates_both_tables(tmp_path):
    v2 = _cli_db(tmp_path / "v2.sqlite3", [("/w/a", "cA", _cli_doc(), 1)])
    legacy = _cli_db(tmp_path / "legacy.sqlite3", [("/w/b", "cB", _cli_doc(), None)],
                    table="conversations")
    assert {c[1] for c in transcript._kiro_cli_conversations(v2)} == {"cA"}
    assert {c[1] for c in transcript._kiro_cli_conversations(legacy)} == {"cB"}


# ── 5 · counts-never-content on the written shard bytes ─────────────────────

def test_written_shard_bytes_never_carry_the_prompt_body(proj):
    root = proj
    doc = _cli_doc(credits=0.5, turns=[_cli_turn(message_id="m1")])
    db = _cli_db(root / "cli-store" / "data.sqlite3",
               [("/w/proj", "c1", doc, 1755080500000)])
    parse = lambda f: transcript.parse_kiro_cli_metrics(f)
    importcmd._ingest_kiro_metrics(root, [db], parse, src=db.parent)
    shard_bytes = b"".join(sh.read_bytes()
                          for sh in paths.Footprint(root).kiro_metric_shards())
    assert PROMPT_BODY_SENTINEL.encode("utf-8") not in shard_bytes
    assert len(ledger.kiro_metrics_raw(root)) == 2


# ── 6 · ingest: idempotency + no cross-kind bleed ────────────────────────────

def test_ingest_kiro_metrics_idempotent(proj):
    root = proj
    doc = _cli_doc(credits=0.5, turns=[_cli_turn(message_id="m1")])
    db = _cli_db(root / "data.sqlite3", [("/w/proj", "c1", doc, 1)])
    parse = lambda f: transcript.parse_kiro_cli_metrics(f)
    first = importcmd._ingest_kiro_metrics(root, [db], parse, src=db.parent)
    second = importcmd._ingest_kiro_metrics(root, [db], parse, src=db.parent)
    assert first == 2  # conv + turn
    assert second == 0
    assert len(ledger.kiro_metrics_raw(root)) == 2


def test_ingest_kiro_metrics_never_touches_call_or_credits_kind(proj):
    """Metrics rows must never enter the call-id `seen` set, the `credits` kind, or
    either's view — they are neither calls nor credits (handoff §4.5, §6)."""
    root = proj
    doc = _cli_doc(credits=0.5, turns=[_cli_turn(message_id="m1")])
    db = _cli_db(root / "data.sqlite3", [("/w/proj", "c1", doc, 1)])
    parse = lambda f: transcript.parse_kiro_cli_metrics(f)
    importcmd._ingest_kiro_metrics(root, [db], parse, src=db.parent)
    assert ledger.calls(root) == []
    assert ledger.read_kind(root, "credits") == []


# ── 7 · growth → fresh row + collapse ────────────────────────────────────────

def test_kiro_metrics_collapse_keeps_latest_largest_row(proj):
    root = proj
    old = schema.make_kiro_metric(source="cli-conv", session="s1", turns=1,
                                  ts="2026-08-01T00:00:00Z", metric_id="km_old")
    new = schema.make_kiro_metric(source="cli-conv", session="s1", turns=3,
                                  ts="2026-08-01T00:05:00Z", metric_id="km_new")
    ledger.append_row(root, "kiro", old)
    ledger.append_row(root, "kiro", new)
    collapsed = ledger.kiro_metrics(root)
    assert len(collapsed) == 1 and collapsed[0]["id"] == "km_new"


def test_kiro_metrics_distinct_grain_keys_never_collapse(proj):
    root = proj
    a = schema.make_kiro_metric(source="ide", row_ref="1", tokens_in=5,
                                ts="2026-08-01T00:00:00Z", metric_id="km_a")
    b = schema.make_kiro_metric(source="ide", row_ref="2", tokens_in=5,
                                ts="2026-08-01T00:01:00Z", metric_id="km_b")
    ledger.append_row(root, "kiro", a)
    ledger.append_row(root, "kiro", b)
    assert {r["id"] for r in ledger.kiro_metrics(root)} == {"km_a", "km_b"}


def test_growth_appends_fresh_row_via_real_parser(tmp_path):
    doc1 = _cli_doc(credits=0.5, turns=[_cli_turn(message_id="m1")])
    doc2 = _cli_doc(credits=0.5,
                    turns=[_cli_turn(message_id="m1"), _cli_turn(message_id="m2")])
    db1 = _cli_db(tmp_path / "data1.sqlite3", [("/w/proj", "c1", doc1, 1)])
    db2 = _cli_db(tmp_path / "data2.sqlite3", [("/w/proj", "c1", doc2, 2)])
    conv1 = [r for r in transcript.parse_kiro_cli_metrics(db1) if r["source"] == "cli-conv"][0]
    conv2 = [r for r in transcript.parse_kiro_cli_metrics(db2) if r["source"] == "cli-conv"][0]
    assert conv1["id"] != conv2["id"]  # grown conversation → fresh id
    assert conv2["turns"] == 2


# ── 8 · kiro_metrics() since-skipping ────────────────────────────────────────

def test_kiro_metrics_since_skips_old_months(proj):
    root = proj
    ledger.append_row(root, "kiro", schema.make_kiro_metric(
        source="cli-conv", session="old", credits=0.1, ts="2020-01-01T00:00:00Z",
        metric_id="km_old_month"))
    ledger.append_row(root, "kiro", schema.make_kiro_metric(
        source="cli-conv", session="new", credits=0.2,  # ts omitted → defaults to now()
        metric_id="km_new_month"))
    all_rows = ledger.kiro_metrics(root)
    assert {r["id"] for r in all_rows} == {"km_old_month", "km_new_month"}
    recent = ledger.kiro_metrics(root, since="30d")
    assert {r["id"] for r in recent} == {"km_new_month"}
    # raw feeds the import seen-set and must never apply a window
    assert {r["id"] for r in ledger.kiro_metrics_raw(root)} == {"km_old_month", "km_new_month"}


# ── 9 · routing (ADR 0006, inherited never re-decided) ──────────────────────

def test_kiro_metrics_ide_rows_route_to_sink_cli_rows_stay_workspace_scoped(
        tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    devdata = paths.kiro_devdata_db()
    _devdata_db(devdata, [(1, 100, 20, "2026-08-13T10:00:00Z")])
    doc = _cli_doc(credits=0.5, turns=[_cli_turn(message_id="m1")])
    clidb = _cli_db(tmp_path / "kiro-cli" / "data.sqlite3",
                   [(str(root.resolve()), "mine", doc, 1755080500000)])
    foot = paths.Footprint(root)
    foot.policy.write_text(
        foot.policy.read_text(encoding="utf-8")
        + f'\n[[sources.kirocli]]\npath = "{clidb.as_posix()}"\nglob = "*"\n'
          'format = "kiro-cli"\n', encoding="utf-8")
    importcmd.run(root, "all", _args())

    # IDE rows: sink (machine ledger) only, never the project.
    assert [r for r in ledger.kiro_metrics_raw(root) if r["source"] == "ide"] == []
    sink_ide = [r for r in ledger.kiro_metrics_raw(paths.global_home())
               if r["source"] == "ide"]
    assert len(sink_ide) == 1

    # CLI rows: workspace-scoped to the project, never the sink.
    project_cli = [r for r in ledger.kiro_metrics_raw(root)
                  if r["source"] in ("cli-conv", "cli-turn")]
    assert len(project_cli) == 2
    sink_cli = [r for r in ledger.kiro_metrics_raw(paths.global_home())
              if r["source"] in ("cli-conv", "cli-turn")]
    assert sink_cli == []


def test_kiro_metrics_reimport_is_idempotent_against_the_routed_sink(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    devdata = paths.kiro_devdata_db()
    _devdata_db(devdata, [(1, 100, 20, "2026-08-13T10:00:00Z")])
    importcmd.run(root, "all", _args())
    first = len(ledger.kiro_metrics_raw(paths.global_home()))
    importcmd.run(root, "all", _args())
    second = len(ledger.kiro_metrics_raw(paths.global_home()))
    assert first == second == 1


# ── 10 · byte-identity: no derived view moves ────────────────────────────────

def _render(argv: list[str], capsys) -> str:
    assert cli.main([*argv, "--no-import"]) == 0
    return capsys.readouterr().out


def test_report_and_chats_byte_identical_with_kiro_tree_present_or_absent(proj, capsys):
    from cage import demo
    demo.seed(proj)
    ledger.append_row(proj, "kiro", schema.make_kiro_metric(
        source="ide", session="kiro", surface="ide", tokens_in=999, tokens_out=999,
        row_ref="1", ts="2026-08-13T00:00:00Z", metric_id="km_present"))
    before = {" ".join(v): _render(v, capsys)
             for v in (["insights", "chats"], ["insights", "chats"])}
    for sh in paths.Footprint(proj).kiro_metric_shards():
        sh.unlink()
    after = {" ".join(v): _render(v, capsys)
            for v in (["insights", "chats"], ["insights", "chats"])}
    assert before == after


# ── 11 · doctor advisory ──────────────────────────────────────────────────────

def test_doctor_kiro_metrics_advisory_renders_per_source(proj):
    root = proj
    ledger.append_row(root, "kiro", schema.make_kiro_metric(
        source="ide", tokens_in=10, row_ref="1", ts="2026-08-13T00:00:00Z",
        metric_id="km_1"))
    level, detail = doctorcmd._kiro_metrics(root)
    assert level == "ok"
    assert "ide: 1 row(s)" in detail
    assert "cli-conv: none yet" in detail
    assert "cli-turn: none yet" in detail


def test_doctor_kiro_metrics_upgrade_watch_surfaces_when_armed_vs_tripped(proj):
    root = proj
    ledger.append_row(root, "kiro", schema.make_kiro_metric(
        source="cli-turn", session="s1", turn="0", ts="2026-08-13T00:00:00Z",
        metric_id="km_armed"))
    _level, armed = doctorcmd._kiro_metrics(root)
    assert "upgrade-watch armed" in armed
    ledger.append_row(root, "kiro", schema.make_kiro_metric(
        source="cli-turn", session="s1", turn="1", tokens_in=50,
        ts="2026-08-13T00:00:00Z", metric_id="km_tripped"))
    _level, tripped = doctorcmd._kiro_metrics(root)
    assert "non-NULL token slots detected" in tripped


def test_doctor_kiro_metrics_never_fails_or_warns_on_empty_ledger(proj):
    level, _detail = doctorcmd._kiro_metrics(proj)
    assert level == "ok"


def test_doctor_run_includes_kiro_metrics_check(proj):
    from cage import initcmd
    initcmd.run(proj)
    names = {c["name"] for c in doctorcmd.run(proj)["checks"]}
    assert "kiro-metrics" in names
