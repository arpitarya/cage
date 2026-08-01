"""The capture manifest (`imports.jsonl`, plan §4): one audit row per import sweep
(per agent×surface) and per graphify run, the `import_id` FK threaded onto call/savings
rows, and the counts-never-content / never-a-derived-view invariants.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from cage import graphifymeter, importcmd, ledger, manifest, paths
from srcseed import mkcage


def _root(tmp_path, monkeypatch):
    mkcage(tmp_path)
    for env in ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _claude_log(path, uuid, tin, tout):
    path.write_text(json.dumps({"type": "assistant", "uuid": uuid,
                                "timestamp": "2026-06-14T10:00:00Z",
                                "message": {"model": "claude-opus-4-8",
                                            "usage": {"input_tokens": tin, "output_tokens": tout}}})
                    + "\n", encoding="utf-8")
    return str(path)


def test_import_writes_a_manifest_row_and_threads_the_fk(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    tp = _claude_log(tmp_path / "s.jsonl", "u1", 1000, 200)
    importcmd.run(root, "claude", SimpleNamespace(agent="claude", path=tp, project=None, since=None))
    calls = ledger.calls(root)
    rows = manifest.read(root)
    assert len(calls) == 1 and len(rows) == 1
    m = rows[0]
    assert m["kind"] == "import" and m["agent"] == "claude" and m["surface"] == ""
    assert m["rows_appended"] == 1 and m["tokens_in"] == 1000
    # per-session row (plan §4): the log's session id + a cage-minted unique id
    assert m["session"] == "s" and m["session_uid"].startswith("n_")
    # no summary record + no cwd ⇒ no name (honest empty ⇒ field omitted)
    assert "session_name" not in m
    # the FK on the call row points back at this manifest row
    assert calls[0]["import_id"] == m["import_id"]
    assert m["cage_version"]  # stamped


def _claude_log_named(path, uuid, tin, tout, *, summary=None, cwd=None):
    lines = []
    if summary is not None:
        lines.append(json.dumps({"type": "summary", "summary": summary}))
    rec = {"type": "assistant", "uuid": uuid, "timestamp": "2026-06-14T10:00:00Z",
           "message": {"model": "claude-opus-4-8",
                       "usage": {"input_tokens": tin, "output_tokens": tout}}}
    if cwd is not None:
        rec["cwd"] = cwd
    lines.append(json.dumps(rec))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def test_claude_session_name_from_summary_record(tmp_path, monkeypatch):
    # A: names always captured — claude lifts the `summary` record's text.
    root = _root(tmp_path, monkeypatch)
    tp = _claude_log_named(tmp_path / "sess.jsonl", "u1", 100, 20, summary="fix the auth bug")
    importcmd.run(root, "claude", SimpleNamespace(agent="claude", path=tp, project=None, since=None))
    m = [r for r in manifest.read(root) if r["kind"] == "import"][0]
    assert m["session_name"] == "fix the auth bug" and m["session"] == "sess"


def test_claude_session_name_falls_back_to_cwd_basename(tmp_path, monkeypatch):
    # No summary record ⇒ the claude fallback is the cwd basename (the `project` axis).
    root = _root(tmp_path, monkeypatch)
    tp = _claude_log_named(tmp_path / "s2.jsonl", "u1", 100, 20, cwd="/Users/x/my_programs/cage")
    importcmd.run(root, "claude", SimpleNamespace(agent="claude", path=tp, project=None, since=None))
    m = [r for r in manifest.read(root) if r["kind"] == "import"][0]
    assert m["session_name"] == "cage"


def test_kiro_manifest_name_is_honest_empty(tmp_path, monkeypatch):
    # copilot CLI / kiro carry no session title — the manifest name stays "" (omitted),
    # never a fabricated name or a session-id-as-name (plan §4).
    root = _root(tmp_path, monkeypatch)
    klog = tmp_path / "tokens_generated.jsonl"
    klog.write_text(json.dumps({"model": "agent", "provider": "kiro",
                                "promptTokens": 500, "generatedTokens": 0}) + "\n",
                    encoding="utf-8")
    importcmd.run(root, "kiro", SimpleNamespace(agent="kiro", path=str(klog), project=None, since=None))
    # The manifest rides with the rows: kiro's land in the machine ledger (ADR 0006), and
    # a manifest row in the project pointing at rows that aren't there would be a dangling FK.
    rows = [r for r in manifest.read(paths.global_home()) if r["kind"] == "import"]
    assert rows and all("session_name" not in r for r in rows)  # honest empty, omitted
    assert [r for r in manifest.read(root) if r["kind"] == "import"] == []


def test_names_never_leak_onto_call_rows(tmp_path, monkeypatch):
    # The DoD PII line: a name lives ONLY in imports.jsonl — never on a call row.
    root = _root(tmp_path, monkeypatch)
    tp = _claude_log_named(tmp_path / "s3.jsonl", "u1", 100, 20, summary="secret prose title")
    importcmd.run(root, "claude", SimpleNamespace(agent="claude", path=tp, project=None, since=None))
    for c in ledger.calls(root):
        assert "session_name" not in c
        assert "secret prose title" not in json.dumps(c)
    for r in ledger.receipts(root):
        assert "session_name" not in r


def test_manifest_is_never_read_by_a_derived_view(tmp_path, monkeypatch):
    # Determinism: the manifest is an audit trail. A report over the same ledger is
    # byte-identical whether or not a manifest exists.
    from cage import cli, demo
    root = _root(tmp_path, monkeypatch)
    demo.seed(root)
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.main(["--ledger", str(root), "insights", "attrib"])
    before = buf.getvalue()
    # write a manifest row directly, then re-render
    manifest.record_import(root, import_id="i_x", agent="claude", surface="", session="s1",
                           session_uid="n_x", source_path="~/x", files_scanned=1,
                           rows_appended=1, tokens_in=1, tokens_out=1, cached_in=0,
                           est_cost_usd=0.0, unpriced_rows=0, ts="2026-07-01T00:00:00Z")
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        cli.main(["--ledger", str(root), "insights", "attrib"])
    assert buf2.getvalue() == before  # the manifest changed no number


def test_manifest_source_path_is_tilde_relative_no_username(tmp_path, monkeypatch):
    # The stored source_path is tilde-relative (PII: no username / absolute path). With
    # HOME pointing at the sandbox, the isolated claude home is under `~`, so `_tilde`
    # strips it — exactly as it does for a real `~/.claude` on a live machine.
    monkeypatch.setenv("HOME", str(tmp_path))
    root = _root(tmp_path, monkeypatch)
    cl = tmp_path / "home-claude_config_dir" / "projects" / "p"
    cl.mkdir(parents=True)
    _claude_log(cl / "s.jsonl", "u1", 100, 50)
    importcmd.run(root, "claude", SimpleNamespace(agent="claude", path=None, project=None, since=None))
    rows = [m for m in manifest.read(root) if m["kind"] == "import"]
    assert rows and all(m["source_path"].startswith("~") for m in rows)  # tilde-relative
    assert all(str(tmp_path) not in m["source_path"] for m in rows)      # no absolute prefix


def test_copilot_vscode_name_lifting(tmp_path):
    # Verified against the real VS Code chat store (2026-07-25): a user `customTitle`
    # (a `kind:1 k:["customTitle"]` patch record) wins over the auto `generatedTitle`;
    # absent both, the name is "". Parse-only — no import needed.
    from cage import transcript
    # 1. customTitle patch record wins over a first-request generatedTitle.
    p1 = tmp_path / "sess1.jsonl"
    p1.write_text("\n".join([
        json.dumps({"kind": 0, "v": {"version": 3, "sessionId": "sess1"}}),
        json.dumps({"kind": 2, "k": ["requests"], "v": [
            {"requestId": "r1", "response": [{"generatedTitle": "auto title"}]}]}),
        json.dumps({"kind": 1, "k": ["customTitle"], "v": "my named session"}),
    ]) + "\n", encoding="utf-8")
    assert transcript.session_name_copilot_vscode(p1) == "my named session"
    # 2. customTitle folded into kind:0.v also counts.
    p2 = tmp_path / "sess2.jsonl"
    p2.write_text(json.dumps({"kind": 0, "v": {"customTitle": "folded title"}}) + "\n",
                  encoding="utf-8")
    assert transcript.session_name_copilot_vscode(p2) == "folded title"
    # 3. no customTitle ⇒ the first request's generatedTitle is the fallback.
    p3 = tmp_path / "sess3.jsonl"
    p3.write_text(json.dumps({"kind": 2, "k": ["requests"], "v": [
        {"requestId": "r1", "response": [{"generatedTitle": "auto only"}]}]}) + "\n",
        encoding="utf-8")
    assert transcript.session_name_copilot_vscode(p3) == "auto only"
    # 4. neither ⇒ honest empty, never fabricated.
    p4 = tmp_path / "sess4.jsonl"
    p4.write_text(json.dumps({"kind": 0, "v": {"sessionId": "sess4"}}) + "\n", encoding="utf-8")
    assert transcript.session_name_copilot_vscode(p4) == ""


def test_graphify_run_writes_a_linked_graphify_manifest(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    src = tmp_path / "big.py"
    src.write_text("x" * 8000, encoding="utf-8")
    graphifymeter._meter(root, f"NODE l [src={src} loc=L1 community=0]", ["query", "x"], "cage")
    gm = [m for m in manifest.read(root) if m["kind"] == "graphify"]
    assert len(gm) == 1
    m = gm[0]
    assert m["tool"] == "graphify" and m["op"] == "query" and m["import_id"].startswith("g_")
    assert m["source_files"] == 1 and m["saved"] > 0
    assert m["session_name"] == "cage"  # graphify's name = the task (plan §4)
    # the manifest's saving_id points at a real savings-tree row
    saving_ids = {s["id"] for s in ledger.savings(root)}
    assert m["saving_id"] in saving_ids


def test_manifest_write_is_fail_open(tmp_path, monkeypatch):
    # A manifest write error never breaks capture: make imports.jsonl's parent a file.
    root = _root(tmp_path, monkeypatch)
    foot = paths.Footprint(root)
    foot.ledger.parent.mkdir(parents=True, exist_ok=True)
    # point imports at an unwritable location by making the ledger dir a file
    tp = _claude_log(tmp_path / "s.jsonl", "u1", 100, 50)
    # sabotage: create imports.jsonl as a directory so append fails
    foot.ledger.mkdir(parents=True, exist_ok=True)
    (foot.ledger / "imports.jsonl").mkdir()
    out = importcmd.run(root, "claude", SimpleNamespace(agent="claude", path=tp, project=None, since=None))
    assert any("imported" in line for line in out)  # capture still succeeded
    assert len(ledger.calls(root)) == 1             # the call row landed
