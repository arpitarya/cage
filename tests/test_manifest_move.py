"""The capture manifest moves to `state/`, and copilot CLI gets a name — P3a + P3b.

**P3a.** `imports.jsonl` moved from `ledger/` to `state/`. Its behaviour had been a state
file's for two releases: never read by a derived view, supplying **labels only**, moving
zero numeric cells when deleted. The move is consistent with the state law, not in tension
with it.

Two things make it dangerous rather than routine, and both are asserted here:

  * **It walked out from under `cleanup.NEVER`'s `"ledger/"` umbrella**, which was its
    only protection. It is an append-only audit trail — nothing reconstructs a deleted
    row — and cleanup is a closed allowlist, so a `state/` class added years from now
    would eat it with *nothing going red*. `tests/test_cleanup.py` carries the survival
    case; this file asserts the entry exists at all.
  * **The old file must keep being read.** 208 rows sit there in the maintainer's own
    ledger. A one-way move is not a crash — it is every existing chat title quietly
    falling back to a session id.

**P3b.** Copilot CLI's name was `""` because cage looked in `events.jsonl`, which really
has no title. The name is in the sibling `workspace.yaml`
([probe](../work/research/2026-08-14-chat-title-store-probes.md)). Kiro carries no title
at any depth and keeps `""` **permanently** — the probe is what makes that a finding
rather than a TODO.
"""
from __future__ import annotations

import json

import pytest

from cage import chats, cleanup, manifest, paths, policy
from tests.conftest import metric_twin


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.setenv("CAGE_BASE", str(root / ".cage"))
    monkeypatch.delenv("CAGE_LEDGER", raising=False)
    monkeypatch.delenv("CAGE_IMPORTS_LOG", raising=False)
    return root


def _row(session, name):
    return {"kind": "import", "import_id": "i_1", "session_uid": "n_1",
            "ts": "2026-08-10T00:00:00Z", "agent": "claude", "surface": "",
            "session": session, "session_name": name, "source_path": "~/x",
            "files_scanned": 1, "rows_appended": 1,
            "tokens_in": 1, "tokens_out": 1, "cached_in": 0}


# ── P3a · the move ──────────────────────────────────────────────────────────────

def test_the_manifest_now_lives_in_state(proj):
    foot = paths.Footprint(proj)
    assert foot.imports == foot.state / "imports.jsonl"
    assert foot.imports_legacy == foot.ledger / "imports.jsonl"


def test_a_new_row_is_written_to_state_only(proj):
    manifest.record_import(proj, import_id="i_1", agent="claude", surface="",
                           session="s1", session_uid="n_1", source_path="~/x",
                           files_scanned=1, rows_appended=1, tokens_in=1,
                           tokens_out=1, cached_in=0, ts="2026-08-10T00:00:00Z",
                           session_name="A chat")
    foot = paths.Footprint(proj)
    assert foot.imports.exists()
    assert not foot.imports_legacy.exists(), "the legacy file must never be created"


def test_the_env_override_matches_the_capture_log_pattern(proj, monkeypatch, tmp_path):
    elsewhere = tmp_path / "elsewhere.jsonl"
    monkeypatch.setenv("CAGE_IMPORTS_LOG", str(elsewhere))
    assert paths.Footprint(proj).imports == elsewhere


def test_both_homes_are_read(proj):
    """The property that keeps existing names alive. Nothing is migrated; the old file is
    read where it lies."""
    foot = paths.Footprint(proj)
    foot.ledger.mkdir(parents=True, exist_ok=True)
    foot.imports_legacy.write_text(json.dumps(_row("old", "Older chat")) + "\n",
                                   encoding="utf-8")
    manifest.record_import(proj, import_id="i_2", agent="claude", surface="",
                           session="new", session_uid="n_2", source_path="~/x",
                           files_scanned=1, rows_appended=1, tokens_in=1,
                           tokens_out=1, cached_in=0, ts="2026-08-11T00:00:00Z",
                           session_name="Newer chat")
    rows = manifest.read(proj)
    assert [r["session"] for r in rows] == ["old", "new"], "legacy first — it is older"


def test_the_legacy_file_is_never_written_or_rewritten(proj):
    foot = paths.Footprint(proj)
    foot.ledger.mkdir(parents=True, exist_ok=True)
    original = json.dumps(_row("old", "Older chat")) + "\n"
    foot.imports_legacy.write_text(original, encoding="utf-8")
    for i in range(3):
        manifest.record_import(proj, import_id=f"i_{i}", agent="claude", surface="",
                               session=f"s{i}", session_uid=f"n_{i}", source_path="~/x",
                               files_scanned=1, rows_appended=1, tokens_in=1,
                               tokens_out=1, cached_in=0, ts="2026-08-11T00:00:00Z")
    assert foot.imports_legacy.read_text(encoding="utf-8") == original


def test_titles_from_the_legacy_home_do_not_regress_to_session_ids(proj):
    """The user-visible failure a one-way move produces: no error, no crash, just every
    existing chat losing its name. Asserted through `chats`, which is the only consumer."""
    foot = paths.Footprint(proj)
    foot.ledger.mkdir(parents=True, exist_ok=True)
    foot.imports_legacy.write_text(json.dumps(_row("sess-abc", "Older chat")) + "\n",
                                   encoding="utf-8")
    # `metric_twin` (conftest), never a per-file copy: claude HAS a spine, so `spend()`
    # supersedes a bare `calls` row and a calls-only fixture would assert over an EMPTY
    # ledger — passing while pinning nothing. Real capture dual-writes; so does this.
    from cage import ledger, schema
    row = schema.make_call(
        route="chat", provider="anthropic", model="m", agent="claude-code",
        session="sess-abc", tokens_in=10, ts="2026-08-10T00:00:00Z")
    ledger.append_row(proj, "calls", row)
    metric_twin(proj, row)
    rows = chats.summarize(proj, policy.load(foot.policy))["rows"]
    assert [r["title"] for r in rows] == ["Older chat"]


def test_the_manifest_is_named_in_the_never_list(proj):
    """It lost the `"ledger/"` umbrella. Cleanup is a **closed allowlist**, so nothing
    fails today either way — this asserts the entry exists so a future `state/` class
    cannot quietly make an audit trail cleanable. `test_cleanup.py` runs the survival case
    at `days=0` for both homes."""
    assert "imports.jsonl" in cleanup.NEVER
    assert "ledger/" in cleanup.NEVER          # the legacy home stays covered too


def test_deleting_the_manifest_still_moves_zero_numeric_cells(proj):
    """The carve-out's own guard, re-asserted at the new location. The manifest supplies
    LABELS; if the move had let it reach a number, the state law would be broken by the
    file's new home rather than by its content."""
    from cage import ledger, schema
    row = schema.make_call(
        route="chat", provider="anthropic", model="m", agent="claude-code",
        session="sess-abc", tokens_in=10, tokens_out=2, ts="2026-08-10T00:00:00Z")
    ledger.append_row(proj, "calls", row)
    metric_twin(proj, row)          # see the note above — claude has a spine
    manifest.record_import(proj, import_id="i_1", agent="claude", surface="",
                           session="sess-abc", session_uid="n_1", source_path="~/x",
                           files_scanned=1, rows_appended=1, tokens_in=10,
                           tokens_out=2, cached_in=0, ts="2026-08-10T00:00:00Z",
                           session_name="A chat")
    pol = policy.load(paths.Footprint(proj).policy)

    # `title` and `named` are the LABEL pair — both are expected to move, and `named`
    # exists precisely so a view can say "this name is a fallback" rather than passing a
    # session id off as a title. Everything else is a cell and must not move. The same
    # split `test_chats.py::test_deleting_manifest_changes_zero_numeric_cells` makes.
    LABELS = ("title", "named")

    def cells(d):
        return [{k: v for k, v in r.items() if k not in LABELS} for r in d["rows"]]

    with_manifest = chats.summarize(proj, pol)
    assert [r["title"] for r in with_manifest["rows"]] == ["A chat"]
    assert with_manifest["rows"][0]["named"] is True
    paths.Footprint(proj).imports.unlink()
    without = chats.summarize(proj, pol)
    assert cells(without) == cells(with_manifest)
    assert without["rows"][0]["title"] == "sess-abc"     # the fallback, not a fabrication
    assert without["rows"][0]["named"] is False          # …and it says so


# ── P3b · names ─────────────────────────────────────────────────────────────────

def _cli_session(tmp_path, sid, yaml_text=None):
    d = tmp_path / "session-state" / sid
    d.mkdir(parents=True)
    (d / "events.jsonl").write_text('{"type":"session.start","data":{}}\n',
                                    encoding="utf-8")
    if yaml_text is not None:
        (d / "workspace.yaml").write_text(yaml_text, encoding="utf-8")
    return d / "events.jsonl"


def test_copilot_cli_name_comes_from_the_sibling_workspace_yaml(tmp_path):
    from cage import transcript
    f = _cli_session(tmp_path, "s1",
                     "id: s1\ncwd: /w/x\nname: 'How does auth work'\nuser_named: false\n")
    assert transcript.session_name_copilot_cli(f) == "How does auth work"


@pytest.mark.parametrize("raw,want", [
    ("name: plain\n", "plain"),
    ("name: 'single quoted'\n", "single quoted"),
    ('name: "double quoted"\n', "double quoted"),
    ("name:    padded   \n", "padded"),
    ("name: has: a colon\n", "has: a colon"),
])
def test_the_flat_yaml_reader_handles_the_shapes_that_actually_occur(tmp_path, raw, want):
    from cage import transcript
    f = _cli_session(tmp_path, "s1", f"id: s1\n{raw}user_named: false\n")
    assert transcript.session_name_copilot_cli(f) == want


def test_no_name_key_stays_honestly_empty(tmp_path):
    """8 of 32 real session dirs have no `name:` at all. That is the honest-empty case and
    must never be filled from the session id or the cwd."""
    from cage import transcript
    f = _cli_session(tmp_path, "s1", "id: s1\ncwd: /w/x\nuser_named: false\n")
    assert transcript.session_name_copilot_cli(f) == ""


def test_a_missing_workspace_yaml_is_empty_not_an_error(tmp_path):
    """The two stores are not in bijection — 32 `workspace.yaml` to 24 `events.jsonl` on a
    real machine — so neither side may be assumed present."""
    from cage import transcript
    assert transcript.session_name_copilot_cli(_cli_session(tmp_path, "s1")) == ""


def test_the_reader_fails_closed_on_anything_it_does_not_understand(tmp_path):
    """It reads ONE key with a regex rather than parsing YAML (`dependencies = []`), so
    the contract is: understood ⇒ the name, anything else ⇒ `""`. Never a guess."""
    from cage import transcript
    for text in ("", "\x00\x01 binary junk\n", "name:\n", "[not yaml at all]\n",
                 "workspace:\n  name: nested\n"):
        f = _cli_session(tmp_path / text[:4].encode().hex(), "s1", text)
        assert transcript.session_name_copilot_cli(f) == "", repr(text)


def test_a_nested_name_key_is_never_lifted(tmp_path):
    """The regex is anchored at column 0. A `name:` belonging to some future nested block
    is not the conversation's name, and lifting it would put an unrelated string on a
    user's chat row."""
    from cage import transcript
    f = _cli_session(tmp_path, "s1", "id: s1\nmodel:\n  name: gpt-5-mini\n")
    assert transcript.session_name_copilot_cli(f) == ""


def test_kiro_keeps_the_honest_empty_permanently():
    """Probed 2026-08-14: `conversations_v2` carries no title at any depth — every
    title-shaped key belongs to an embedded tool schema — and `latest_summary` is NULL on
    all 20 rows. This is a **finding**, not a gap: there is nothing to lift, and the
    transcript text must never be mined for a name.

    Asserted structurally, because the alternative failure is silent: if a future edit
    ever hands kiro a name lifter, it will be because someone synthesized one."""
    from cage import importcmd
    src = __import__("inspect").getsource(importcmd)
    assert "session_name_kiro" not in src
    assert "_kiro_name" not in src
