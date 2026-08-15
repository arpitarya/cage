"""Kiro capture routing — two stores, ADR-LEDGER unified the fix (2026-08-15).

- **IDE** (`tokens_generated.jsonl`): one global file with no project/session/timestamp.
  From 2026-08-01 to 2026-08-15 (ADR-KIRO, since reversed) these rows were a *machine*
  fact routed unconditionally to `~/.cage`. **ADR-LEDGER reversed that**: IDE rows now
  capture into whichever ledger is active for the run, exactly like every other agent —
  no separate sink, no special-casing. The accepted cost is the mirror image of the old
  guarantee: the SAME underlying turn, imported from two different projects, is now
  stored as a separate row in each one. Since KIRO-CALLS-LEG (ratified 2026-08-15) those
  rows land as kiro-METRICS rows (`ledger/kiro/`, `source="ide-log"`) rather than `calls`
  rows — that relocation is orthogonal to this file's routing tests and unaffected by
  ADR-LEDGER.
- **CLI** (`conversations_v2` SQLite): keyed by the cwd it ran in, with a real
  conversation id — genuinely project-attributable, so it always got (and still gets)
  the opposite treatment: scoped to the project tree and stamped with `project`. **This
  half is completely unaffected by ADR-LEDGER** and its tests are unchanged below.

The load-bearing risk this file exists to pin, post-reversal, is that IDE rows land in
the SAME ledger as claude/copilot with no collateral: no second lock, no second policy
file, no leftover branch that still tries to route somewhere else. So the claude/copilot
legs are asserted **byte-identical** whether or not a kiro log is present, and the sweep
summary is asserted to count kiro's rows exactly like every other agent's.
"""
from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

from cage import chats, importcmd, ledger, paths, transcript
from srcseed import mkcage

_HOME_ENVS = ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_HOME",
              "KIRO_DATA_DIR", "CAGE_VSCODE_USER")


def _isolate(tmp_path, monkeypatch, name="proj"):
    for env in _HOME_ENVS:
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    root = tmp_path / name
    mkcage(root)
    monkeypatch.chdir(root)
    return root


def _args(agent="all", **kw):
    return SimpleNamespace(agent=agent, path=None, project=None, since=None, **kw)


def _kiro_log(lines=2, start=100):
    log = paths.kiro_token_log()
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("".join(
        json.dumps({"model": "agent", "provider": "kiro",
                    "promptTokens": start + i, "generatedTokens": 0}) + "\n"
        for i in range(lines)), encoding="utf-8")
    return log


def _claude_log(uuid="u1", tin=100, tout=20):
    d = paths.claude_home() / "projects" / "p"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{uuid}.jsonl").write_text(json.dumps({
        "type": "assistant", "uuid": uuid, "timestamp": "2026-06-14T10:00:00Z",
        "cwd": "/w/demo",
        "message": {"model": "claude-opus-4-8",
                    "usage": {"input_tokens": tin, "output_tokens": tout}}}) + "\n",
        encoding="utf-8")


def _kiro_rows(root):
    """The IDE store's rows in whichever ledger they landed in. `ledger/kiro/`'s
    `ide-log` grain since KIRO-CALLS-LEG — the CLI grains are excluded so a test about
    the IDE leg cannot pass on a CLI row."""
    return [r for r in ledger.kiro_metrics(root) if r.get("source") == "ide-log"]


def _shards(root):
    """Bytes of the shards the IDE rows live in — `kiro/chats-*.jsonl`. Deliberately NOT
    the `calls` shards: those are empty for every agent now, so a byte-comparison on them
    is two empty strings agreeing."""
    return b"".join(p.read_bytes() for p in paths.Footprint(root).kiro_metric_shards())


# ── the resolver: one place the rule lives ────────────────────────────────────

def test_kiro_sink_is_always_the_runs_own_active_ledger(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    assert paths.kiro_ledger(root) == root      # ADR-LEDGER: never a separate sink
    assert paths.kiro_routed(root) is None       # nothing to route, ever


def test_kiro_sink_is_the_active_ledger_with_no_project_too(tmp_path, monkeypatch):
    # No project ⇒ the sweep root IS the machine ledger, same as before — but now that's
    # true because it's just `resolve_root`'s normal answer, not because of any kiro-
    # specific fallback.
    monkeypatch.chdir(tmp_path)
    g = paths.global_home()
    assert paths.kiro_ledger(g) == g
    assert paths.kiro_routed(g) is None


def test_explicit_ledger_override_still_wins_trivially(tmp_path, monkeypatch):
    # Kept post-reversal: `kiro_ledger` must still answer with the run's OWN root under
    # an override, not silently ignore it — even though there is no longer a second sink
    # for the override to out-rank.
    root = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CAGE_BASE", str(tmp_path / "lab" / ".cage"))
    assert paths.kiro_routed(root) is None
    assert paths.kiro_ledger(root) == root


def test_cage_ledger_dir_override_changes_nothing_about_routing(tmp_path, monkeypatch):
    # CAGE_LEDGER re-points the ledger dir alone; `kiro_routed` is a constant now, so this
    # exercises no special interaction — it is pinned so a future re-introduction of a
    # routing branch is caught immediately by this case too.
    root = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CAGE_LEDGER", str(tmp_path / "shared-ledger"))
    assert paths.kiro_routed(root) is None


# ── the routing itself ────────────────────────────────────────────────────────

def test_ide_rows_land_in_the_project_ledger_not_a_machine_sink(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    _kiro_log(2)
    importcmd.run(root, "all", _args())
    assert len(_kiro_rows(root)) == 2 and ledger.calls(root) == []
    # No separate machine ledger was ever touched by this sweep.
    assert not (paths.global_home() / ".cage" / "ledger").exists()


def test_two_projects_one_machine_each_get_their_own_copy(tmp_path, monkeypatch):
    """The accepted cost, pinned rather than left implicit. Kiro's log is one global
    file with no project field, so importing it from two different projects now stores
    the SAME underlying turns twice — once per ledger. ADR-LEDGER names this cost and
    accepts it in exchange for "everything in the active ledger, always"."""
    a = _isolate(tmp_path, monkeypatch, "a")
    _kiro_log(3)
    importcmd.run(a, "all", _args())
    b = _isolate(tmp_path, monkeypatch, "b")
    importcmd.run(b, "all", _args())
    rows_a, rows_b = _kiro_rows(a), _kiro_rows(b)
    assert len(rows_a) == 3 and len(rows_b) == 3
    # Same underlying rows, stored independently — ids match across the two ledgers.
    assert {r["id"] for r in rows_a} == {r["id"] for r in rows_b}


def test_reimport_is_idempotent_against_the_project_ledger(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    _kiro_log(2)
    importcmd.run(root, "all", _args())
    before = _shards(root)
    assert before, "byte-identical must be asserted about rows that exist"
    lines = importcmd.run(root, "all", _args())
    assert _shards(root) == before                          # 0 new, byte-identical
    assert any("imported 0 call(s)" in l for l in lines if "kiro" in l)


def test_ledger_override_keeps_kiro_in_the_named_ledger(tmp_path, monkeypatch):
    # cage-lab's isolation depends on this: under --ledger, kiro captures into exactly
    # the named sink — same guarantee as before ADR-LEDGER, now for the ordinary reason
    # every agent gets it (there's only ever one root to capture into) rather than a
    # kiro-specific override check.
    root = _isolate(tmp_path, monkeypatch)
    base = tmp_path / "lab" / ".cage"                      # the lab's own named store
    base.mkdir(parents=True)
    (base / "cage.toml").write_text(
        paths.Footprint(root).policy.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("CAGE_BASE", str(base))
    _kiro_log(2)
    importcmd.run(root, "all", _args())
    assert len(_kiro_rows(root)) == 2                      # Footprint is re-based to `base`
    # The default machine ledger is never even created: under an override every Footprint
    # is re-based, so `ledger.calls(global_home())` would read `base` too — the honest
    # assertion is against the directory on disk.
    assert not (paths.global_home() / ".cage" / "ledger").exists()


# ── the hard constraint: the other two agents are untouched ───────────────────

def test_claude_and_copilot_capture_is_byte_identical(tmp_path, monkeypatch):
    """Asserted, not reasoned about. The same claude sweep is run twice — once with a
    kiro log present and once without — and the project ledger's claude rows must be
    identical either way. Before ADR-LEDGER this pinned that the (now-retired) routed
    leg never perturbed claude's own capture; post-reversal it pins the same guarantee
    for the ordinary reason every agent needs it — one agent's presence in `[sources]`
    must never change another agent's rows. `import_id` is the per-sweep manifest FK (a
    fresh id per run, non-deterministic by nature, like `ts`) and is stripped, exactly as
    the fixture corpus does."""
    def sweep(name, with_kiro):
        root = _isolate(tmp_path, monkeypatch, name)
        _claude_log()
        if with_kiro:
            _kiro_log(2)
        importcmd.run(root, "all", _args())
        rows = ledger.spend(root)   # P5: claude resolves from `ledger/claude/`
        assert rows, "the claude leg must actually capture, or this proves nothing"
        return [{k: v for k, v in r.items() if k != "import_id"} for r in rows]

    assert sweep("no-kiro", False) == sweep("with-kiro", True)


def test_the_project_ledger_now_gains_kiro_metrics_rows_but_never_a_calls_row(tmp_path, monkeypatch):
    """Since ADR-LEDGER, kiro's IDE rows DO land in this project's ledger — the reversal
    this file exists to pin. What's still true, unchanged by the reversal: kiro never
    produces a `calls` row (KIRO-CALLS-LEG relocated that capture to `ledger/kiro/`
    metrics rows, orthogonal to routing), so `spend()` — which reads `calls` — still
    shows claude only, and kiro contributes no tokens to any total."""
    root = _isolate(tmp_path, monkeypatch)
    _claude_log()
    _kiro_log(4)
    importcmd.run(root, "all", _args())
    assert {c["agent"] for c in ledger.spend(root)} == {"claude-code"}
    assert len(_kiro_rows(root)) == 4                       # the reversal: now present
    assert [c for c in ledger.calls(root) if c.get("agent") == "kiro"] == []


# ── the summary line counts kiro like every other agent ───────────────────────

def test_summary_reports_kiro_like_any_other_agent_no_sink_note(tmp_path, monkeypatch):
    """Since ADR-LEDGER there is no second sink to name: the per-agent kiro line reads
    exactly like claude's or copilot's (no `sink_note`), and the rollup table still never
    totals kiro's tokens — unchanged, because kiro is a metrics-only capture (never a
    `calls`/spend row) regardless of which ledger it lands in."""
    root = _isolate(tmp_path, monkeypatch)
    _claude_log(tin=100, tout=20)
    _kiro_log(2, start=1000)
    lines = importcmd.run(root, "all", _args())
    text = "\n".join(lines)
    kiro_line = next(l for l in lines if l.startswith("✔ kiro"))
    assert kiro_line.endswith("file(s).")                   # plain full stop, no sink_note
    assert "machine ledger" not in kiro_line and "~/.cage" not in kiro_line
    total = next(l for l in lines if l.strip().startswith("total"))
    assert "100" in total and "1,000" not in total and "2,001" not in total
    assert "kiro" not in text.split("agent    surface")[-1]  # not a rollup bucket either


def test_capture_on_read_never_announces_kiro_metrics_rows(tmp_path, monkeypatch):
    """`ensure_captured`'s before/after diff reads `spend() + calls()` — kiro's IDE rows
    are neither, so a kiro-only import stays silent (`None`) whether or not the rows now
    land locally. Unaffected by ADR-LEDGER; what changed is only WHERE the rows this
    silent sweep captured actually are."""
    root = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")
    _kiro_log(3)
    summary = importcmd.ensure_captured(root, _args(no_import=False))
    assert summary is None                                  # kiro never trips this diff
    assert len(_kiro_rows(root)) == 3                        # but it was captured, HERE


def test_project_capture_switch_still_pauses_everything(tmp_path, monkeypatch):
    # The one capture switch left standing: since there's no separate machine-sink policy
    # to compose with anymore, this project's own `[capture] enabled` is the whole story.
    root = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CAGE_CAPTURE", "0")
    _kiro_log(2)
    importcmd.run(root, "all", _args())
    assert _kiro_rows(root) == []


# ── the read side no longer has anything to explain ───────────────────────────

def test_kiro_routed_line_is_always_empty_since_the_reversal(tmp_path, monkeypatch):
    """`chats.kiro_routed_line` used to explain why a project view showed no kiro
    (ADR-KIRO). Since ADR-LEDGER there is nothing to explain — kiro rows are simply in
    the ledger you're looking at — so this now always returns `""`, everywhere."""
    from cage import policy
    root = _isolate(tmp_path, monkeypatch)
    pol = policy.load(paths.Footprint(root).policy)
    assert chats.kiro_routed_line(root, pol) == ""
    monkeypatch.chdir(tmp_path)
    g = paths.global_home()
    assert chats.kiro_routed_line(g, policy.load(None)) == ""


# ── K3/K4: the two HONEST-LIMITs, pinned so they can't regress silently ───────

def _rep(**kw):
    base = {"dim": "agent", "since": None, "groups": {}, "kiro_rows": 0}
    base.update(kw)
    return base


# ── kiro CLI: the OPPOSITE fix ────────────────────────────────────────────────

def _cli_db(path, rows):
    """rows = [(key/cwd, conversation_id)] — a minimal conversations_v2 store."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE conversations_v2 (key TEXT, conversation_id TEXT, "
                "value TEXT, created_at INTEGER, updated_at INTEGER)")
    for key, cid in rows:
        doc = {"model_info": {"model_id": "claude-haiku-4.5"},
               "user_turn_metadata": {"usage_info": [{"value": 0.5, "unit": "credit"}]},
               "history": [{"user": {"content": "SECRET"},
                            "request_metadata": {"context_usage_percentage": 3.0}}]}
        con.execute("INSERT INTO conversations_v2 VALUES (?,?,?,?,?)",
                    (key, cid, json.dumps(doc), 1, 2))
    con.commit()
    con.close()
    return path


def test_cli_credits_are_scoped_to_the_workspace_tree(tmp_path):
    db = _cli_db(tmp_path / "data.sqlite3",
                 [("/w/mine", "c1"), ("/w/mine/sub", "c2"), ("/w/other", "c3"),
                  ("/w/mine-lab", "c4")])
    rows = transcript.parse_kiro_cli_credits(db, workspace="/w/mine")
    # the tree, not the directory — and never the sibling whose name merely starts the same
    assert {r["session"] for r in rows} == {"c1", "c2"}


def test_cli_credits_unscoped_reads_the_whole_machine(tmp_path):
    db = _cli_db(tmp_path / "data.sqlite3", [("/w/a", "c1"), ("/w/b", "c2")])
    assert len(transcript.parse_kiro_cli_credits(db)) == 2


def test_cli_credit_row_stamps_project_basename_never_the_path(tmp_path):
    db = _cli_db(tmp_path / "data.sqlite3", [("/w/my-repo/sub", "c1")])
    row = transcript.parse_kiro_cli_credits(db)[0]
    assert row["project"] == "sub"                 # the cwd basename, like a call row
    assert "/w/my-repo" not in json.dumps(row)     # the path never enters the ledger


def test_cli_key_normalization_survives_a_symlinked_workspace(tmp_path):
    """The near-miss that returns zero rows and reads as "no kiro usage": kiro stores the
    symlink-RESOLVED cwd (verified on a real store — `/tmp/x` is keyed `/private/tmp/x`),
    so the workspace must be resolved the same way before comparison."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    db = _cli_db(tmp_path / "data.sqlite3", [(str(real), "c1")])
    assert len(transcript.parse_kiro_cli_credits(db, workspace=str(link))) == 1


def test_cli_workspace_resolver_precedence(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    assert paths.kiro_cli_workspace(root) == str(root.resolve())   # project tree
    monkeypatch.chdir(tmp_path)
    assert paths.kiro_cli_workspace(paths.global_home()) == ""     # the whole machine


def test_cli_credits_import_is_scoped_and_stamped(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    db = _cli_db(tmp_path / "kiro-cli" / "data.sqlite3",
                 [(str(root.resolve()), "mine"), ("/elsewhere", "theirs")])
    foot = paths.Footprint(root)
    # .as_posix(): a raw Windows `\` in a TOML basic string is an escape character —
    # same fix as `paths.sources_toml` (v0.37.0).
    foot.policy.write_text(foot.policy.read_text(encoding="utf-8")
                           + f'\n[[sources.kirocli]]\npath = "{db.as_posix()}"\n'
                             'glob = "*"\nformat = "kiro-cli"\n', encoding="utf-8")
    importcmd.run(root, "all", _args())
    # P2 (v0.51): the top-level `credits-*.jsonl` shard is no longer WRITTEN — `cli-conv`
    # rows in `ledger/kiro/` are the credits home and `ledger.credits` projects them.
    # The property under test is unchanged and is asserted through the reader every
    # consumer actually uses, which is the stronger place for it: ADR 0006 cwd scoping,
    # and the `project` stamp. Asserting the raw shard would now pass vacuously on [].
    assert ledger.read_kind(root, "credits") == [], "the retired shard must stay unwritten"
    credits = ledger.credits(root)
    assert [c["session"] for c in credits] == ["mine"]   # the other cwd is not this project
    assert credits[0]["project"] == root.name
    assert credits[0]["method"] == "measured" and credits[0]["unit"] == "credits"

# ── K3 and K4's report-footer cases went with `cage report` (SURFACE-CUT) ────────
# Three tests pinned `report._kiro_limits_caveat` — the footer stating that kiro rows
# carry no time, session or project, that it composes with the input-only caveat, and
# that it names the `--since` window as the reading that would be wrong. It was a
# report-footer helper with no other caller and is gone. **ADR 0006's other half is
# still pinned above**: `chats.kiro_routed_line` (rescued from report.py) still proves
# a project view says WHY kiro is absent rather than showing nothing.

# K4's two cases pinned `report._surface_caveat` — a blank `surface` cell must read as
# "the source does not say", never as "cli". That caveat only ever rendered on
# `cage report --by surface`, and `--by` died with the command, so there is no longer a
# surface-dimension view for it to appear on. The FINDING it encoded (claude's CLI and
# VS Code share one store with no marker) is unchanged and still true of the data;
# `cage insights chats` shows the same blank cell and is pinned by its own goldens.
