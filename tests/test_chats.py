"""`cage insights chats` — per-chat detail view.

Pins the mechanism the proposal made binding: group by (agent, surface, session) off
the ledger alone, join a title from `imports.jsonl` for **display only**, rank/bound
at render time, and never let the manifest move a numeric cell — that last one is the
scoped carve-out `manifest.py`'s docstring documents and this file is what keeps true.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cage import chats, ledger, manifest, paths, schema
from cage.constants import CHATS_DEFAULT_ROWS
from cage.policy import load as load_policy


@pytest.fixture
def root(proj):
    (proj / ".cage" / "ledger").mkdir(parents=True)
    return proj


@pytest.fixture
def pol(root):
    return load_policy(paths.Footprint(root).policy)


def _call(root: Path, cid: str, *, agent: str, session: str = "", surface: str = "",
          provider: str = "anthropic", model: str = "claude-sonnet-4-6",
          tin: int = 100, tout: int = 50, cached: int = 0, cache_write: int = 0,
          premium: int = 0, ts: str = "2026-07-01T09:00:00Z", extra: dict | None = None):
    row = schema.make_call(route="chat", provider=provider, model=model,
                           tokens_in=tin, tokens_out=tout, cached_in=cached,
                           cache_write_in=cache_write, premium=premium, agent=agent,
                           session=session, surface=surface, ts=ts, call_id=cid)
    if extra:
        row.update(extra)
    ledger.append(paths.Footprint(root).calls, row)


def _name(root: Path, *, agent: str, session: str, name: str,
          ts: str = "2026-07-01T09:05:00Z", surface: str = ""):
    """Write a manifest row the way a real import sweep does: `_write_manifest` maps
    the ledger's raw ``agent`` (e.g. ``claude-code``) to its SURFACES name (``claude``)
    *before* writing — so a caller here passes the same raw agent it passed to
    ``_call`` and the join still lands on the mapped bucket key."""
    from cage import agents as _agents
    mapped = _agents.row_surface(agent) or agent
    manifest.record_import(
        root, import_id=manifest.new_import_id(), agent=mapped, surface=surface,
        session=session, session_uid=manifest.new_session_uid(), source_path="",
        files_scanned=1, rows_appended=1, tokens_in=0, tokens_out=0, cached_in=0,
        est_cost_usd=0.0, unpriced_rows=0, ts=ts, session_name=name)


# ── grouping math ─────────────────────────────────────────────────────────────

def test_grouping_sums_within_one_bucket(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1", tin=100, tout=10, cached=5)
    _call(root, "c_2", agent="claude-code", session="s1", tin=200, tout=20, cached=15)
    rows = chats.summarize(root, pol)["rows"]
    assert len(rows) == 1
    r = rows[0]
    assert r["calls"] == 2 and r["tokens_in"] == 300 and r["tokens_out"] == 30
    assert r["cached_in"] == 20


def test_different_sessions_are_separate_rows(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _call(root, "c_2", agent="claude-code", session="s2")
    rows = chats.summarize(root, pol)["rows"]
    assert {r["session"] for r in rows} == {"s1", "s2"}


def test_bucket_key_includes_surface(root, pol):
    """Copilot's CLI and VS Code stores are genuinely separate — same session id under
    two surfaces must not collapse into one row."""
    _call(root, "c_1", agent="copilot", session="s1", surface="cli", tin=100)
    _call(root, "c_2", agent="copilot", session="s1", surface="vscode", tin=200)
    rows = chats.summarize(root, pol)["rows"]
    assert len(rows) == 2
    assert {r["surface"] for r in rows} == {"cli", "vscode"}


# ── title join ────────────────────────────────────────────────────────────────

def test_title_last_write_wins(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _name(root, agent="claude-code", session="s1", name="first title", ts="2026-07-01T09:01:00Z")
    _name(root, agent="claude-code", session="s1", name="renamed", ts="2026-07-01T09:02:00Z")
    r = chats.summarize(root, pol)["rows"][0]
    assert r["title"] == "renamed" and r["named"] is True


def test_no_name_falls_back_to_session_id(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    r = chats.summarize(root, pol)["rows"][0]
    assert r["title"] == "s1" and r["named"] is False


def test_untitled_fallback_is_shortened_for_display_not_csv(root, pol):
    long_session = "s" * 40
    _call(root, "c_1", agent="claude-code", session=long_session)
    data = chats.summarize(root, pol)
    text = chats.render_chats(data)
    assert long_session not in text and long_session[:12] in text
    csv_text = chats.render_csv(data)
    assert long_session in csv_text  # CSV keeps the full, unshortened label


# ── money independence: the one law amendment, pinned ──────────────────────────

def test_deleting_manifest_changes_zero_numeric_cells(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1", tin=100, tout=10, cached=5)
    _call(root, "c_2", agent="copilot", session="s2", surface="cli", tin=200, tout=20)
    _name(root, agent="claude-code", session="s1", name="my chat")
    before = chats.summarize(root, pol)
    paths.Footprint(root).imports.unlink()
    after = chats.summarize(root, pol)
    numeric_fields = ("calls", "tokens_in", "cached_in", "cache_write_in",
                      "tokens_out", "premium", "cost", "unpriced_calls",
                      "unpriced_tokens")
    before_by_session = {r["session"]: r for r in before["rows"]}
    after_by_session = {r["session"]: r for r in after["rows"]}
    assert set(before_by_session) == set(after_by_session)
    for sess, b in before_by_session.items():
        a = after_by_session[sess]
        for f in numeric_fields:
            assert a[f] == b[f], f"{f} moved for {sess}"
    assert before_by_session["s1"]["title"] == "my chat"
    assert after_by_session["s1"]["title"] == "s1"
    assert after_by_session["s1"]["named"] is False


def test_determinism(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _call(root, "c_2", agent="copilot", session="s2", surface="vscode")
    _name(root, agent="claude-code", session="s1", name="chat one")
    first = chats.summarize(root, pol)
    assert first == chats.summarize(root, pol)
    assert chats.render_chats(first) == chats.render_chats(first)


# ── ranking + truncation (no-silent-caps law) ───────────────────────────────────

def test_sort_is_tokens_in_desc_then_session_id(root, pol):
    _call(root, "c_1", agent="claude-code", session="s_b", tin=100)
    _call(root, "c_2", agent="claude-code", session="s_a", tin=100)
    _call(root, "c_3", agent="claude-code", session="s_z", tin=500)
    rows = chats.summarize(root, pol)["rows"]
    assert [r["session"] for r in rows] == ["s_z", "s_a", "s_b"]


def test_truncation_footer_counts_the_cut(root, pol):
    n = CHATS_DEFAULT_ROWS + 7
    for i in range(n):
        _call(root, f"c_{i}", agent="claude-code", session=f"s_{i:03d}", tin=1000 - i)
    data = chats.summarize(root, pol)
    out = chats.render_chats(data)
    assert "7 more chat(s) — --all to show" in out
    assert "s_000" in out                              # highest tokens_in — shown
    assert f"s_{CHATS_DEFAULT_ROWS:03d}" not in out     # past the cut — not shown
    full = chats.render_chats(data, show_all=True)
    assert "more chat(s)" not in full
    for i in range(n):
        assert f"s_{i:03d}" in full


def test_csv_is_never_truncated(root, pol):
    n = CHATS_DEFAULT_ROWS + 3
    for i in range(n):
        _call(root, f"c_{i}", agent="claude-code", session=f"s_{i:03d}", tin=1000 - i)
    data = chats.summarize(root, pol)
    import csv as _csv
    import io
    rows = list(_csv.DictReader(io.StringIO(chats.render_csv(data))))
    assert len(rows) == n


# ── kiro-IDE: one row, no fabricated per-chat identity ──────────────────────────

def test_kiro_ide_collapses_to_one_row_with_the_honest_label(root, pol):
    _call(root, "c_k1", agent="kiro", session="kiro", surface="ide",
          provider="kiro", model="agent", tin=100, tout=0)
    _call(root, "c_k2", agent="kiro", session="kiro", surface="ide",
          provider="kiro", model="agent", tin=200, tout=0)
    data = chats.summarize(root, pol)
    rows = data["rows"]
    assert len(rows) == 1
    assert rows[0]["title"] == chats.KIRO_IDE_LABEL
    assert rows[0]["calls"] == 2
    out = chats.render_chats(data)
    assert chats.KIRO_IDE_LABEL in out
    assert "collapse into this one row" in out


# ── legacy-human exclusion (calls never really carry this, but the predicate is
#    applied uniformly with every other money view — proven with a hand-crafted row,
#    same technique as tests/test_legacy_ledger.py) ─────────────────────────────

def test_legacy_human_row_is_excluded_and_footnoted(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1", tin=100)
    _call(root, "c_2", agent="claude-code", session="s2", tin=50,
          extra={"tool": "human"})
    data = chats.summarize(root, pol)
    assert data["legacy_human"] == 1
    assert {r["session"] for r in data["rows"]} == {"s1"}
    out = chats.render_chats(data)
    assert "1 legacy human-axis row(s) excluded" in out


# ── UNPRICED: counted, never a silent $0 ────────────────────────────────────────

def test_unpriced_row_shows_dash_not_zero_under_usd(root, pol):
    from cage import display
    _call(root, "c_1", agent="copilot", session="s1", provider="", model="copilot/auto",
          tin=100, tout=10)
    data = chats.summarize(root, pol)
    assert data["unpriced_calls"] == 1
    out = chats.render_chats(data, disp=display.Display(usd=True))
    assert "—" in out
    assert "UNPRICED" in out


def test_unpriced_gap_line_in_token_view(root, pol):
    _call(root, "c_1", agent="copilot", session="s1", provider="", model="copilot/auto")
    out = chats.render_chats(chats.summarize(root, pol))
    assert "1 call unpriced" in out


# ── empty states ──────────────────────────────────────────────────────────────

def test_empty_ledger_is_an_honest_empty(root, pol):
    out = chats.render_chats(chats.summarize(root, pol))
    assert "No chats recorded yet." in out
    assert "cage import" in out and "cage doctor" in out


def test_filtered_empty_names_the_filter_not_the_ledger(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1", ts="2020-01-01T00:00:00Z")
    data = chats.summarize(root, pol, since="7d")
    out = chats.render_chats(data)
    assert "the filter is empty, not the ledger" in out
    assert "since 7d" in out


# ── --agent filter ───────────────────────────────────────────────────────────

def test_agent_filter(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _call(root, "c_2", agent="copilot", session="s2", surface="cli")
    data = chats.summarize(root, pol, agent="copilot")
    assert [r["agent"] for r in data["rows"]] == ["copilot"]


# ── CLI wiring ────────────────────────────────────────────────────────────────

def test_cli_wiring(root, monkeypatch, capsys):
    from cage import cli
    monkeypatch.chdir(root)
    _call(root, "c_1", agent="claude-code", session="s1")
    assert cli.main(["insights", "chats", "--no-import"]) == 0
    assert "Chats" in capsys.readouterr().out
    assert cli.main(["insights", "chats", "--no-import", "--csv"]) == 0
    assert capsys.readouterr().out.startswith("chat,")
    assert cli.main(["insights", "chats", "--no-import", "--all"]) == 0
    assert cli.main(["insights", "chats", "--no-import", "--usd"]) == 0
    assert cli.main(["insights", "chats", "--no-import", "--agent", "copilot"]) == 0
