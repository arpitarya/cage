"""`cage insights graphify` — per-chat graphify usage & GROSS saving.

Pins the join mechanism the handoff made binding: reuse `chats.summarize` verbatim
for the chat universe, join `ledger.savings` rows onto it by `session` alone (a
savings row carries no agent), and never let an unassignable/unmatched receipt
redistribute into a chat row.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cage import constants, graphifychat, ledger, paths, savings, schema
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
          tin: int = 100, tout: int = 50, ts: str = "2026-07-01T09:00:00Z"):
    row = schema.make_call(route="chat", provider=provider, model=model,
                           tokens_in=tin, tokens_out=tout, agent=agent,
                           session=session, surface=surface, ts=ts, call_id=cid)
    ledger.append(paths.Footprint(root).calls, row)


def _credit(root: Path, *, session: str, agent: str = "kiro", credits: float = 3.5,
            ts: str = "2026-07-01T10:00:00Z"):
    ledger.append_row(root, "credits", schema.make_credit(
        session=session, credits=credits, agent=agent, turns=4, ts=ts))


def _savings(root: Path, *, session: str, raw_alternative: float, actual: float,
            tool: str = "graphify", op: str = "query", method: str = "modeled",
            confidence: float = constants.GRAPHIFY_RECEIPT_CONFIDENCE,
            ts: str = "2026-07-01T09:05:00Z"):
    return savings.record(root, tool=tool, raw_alternative=raw_alternative,
                          actual=actual, op=op, session=session, unit="tokens",
                          method=method, confidence=confidence, ts=ts)


# ── the join ─────────────────────────────────────────────────────────────────

def test_a_receipt_joins_its_session_and_computes_the_counterfactual(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1", tin=100, tout=50)
    _savings(root, session="s1", raw_alternative=1000, actual=200)
    data = graphifychat.summarize(root, pol)
    r = data["rows"][0]
    assert r["session"] == "s1" and r["receipts"] == 1
    assert r["saved"] == 800
    assert r["tokens"] == 150
    assert r["without"] == 950
    assert r["pct"] == pytest.approx(800 / 950 * 100)
    assert r["has_gfx"] is True


def test_multiple_receipts_on_one_session_sum(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _savings(root, session="s1", raw_alternative=500, actual=100)
    _savings(root, session="s1", raw_alternative=300, actual=50, ts="2026-07-01T09:06:00Z")
    r = graphifychat.summarize(root, pol)["rows"][0]
    assert r["receipts"] == 2
    assert r["saved"] == 650


def test_no_agent_field_on_savings_join_is_by_session_only(root, pol):
    """The join key is `session` alone — a copilot chat's session correctly picks up
    a savings row that (like every savings row) carries no agent field at all."""
    _call(root, "c_1", agent="copilot", session="s1", surface="cli")
    _savings(root, session="s1", raw_alternative=400, actual=100)
    r = graphifychat.summarize(root, pol)["rows"][0]
    assert r["agent"] == "copilot" and r["saved"] == 300


def test_another_sessions_receipts_never_leak_into_this_chat(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _call(root, "c_2", agent="claude-code", session="s2")
    _savings(root, session="s1", raw_alternative=500, actual=100)
    by = {r["session"]: r for r in graphifychat.summarize(root, pol)["rows"]}
    assert by["s1"]["saved"] == 400
    assert by["s2"]["receipts"] == 0 and by["s2"]["saved"] == 0


# ── unassignable / unmatched ─────────────────────────────────────────────────

def test_unassignable_shim_rows_are_tallied_never_redistributed(root, pol):
    """A `session=""` savings row (the native shim's honest-empty session, GC3)
    never attaches to any chat and is tallied apart."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _savings(root, session="", raw_alternative=200, actual=50)
    data = graphifychat.summarize(root, pol)
    assert data["rows"][0]["receipts"] == 0
    assert data["unassignable"] == {"receipts": 1, "saved": 150.0}


def test_unmatched_session_is_tallied_never_redistributed(root, pol):
    """A savings session with no corresponding chat row (a different ledger root,
    a deleted call) is tallied apart, never guessed onto some other chat."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _savings(root, session="ghost", raw_alternative=200, actual=50)
    data = graphifychat.summarize(root, pol)
    assert data["rows"][0]["receipts"] == 0
    assert data["unmatched"] == {"receipts": 1, "saved": 150.0}
    out = graphifychat.render_view(data, all_chats=True)
    assert "1 graphify receipt(s) unmatched" in out


def test_unassignable_and_unmatched_footer_lines(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _savings(root, session="s1", raw_alternative=500, actual=100)
    _savings(root, session="", raw_alternative=200, actual=50)
    _savings(root, session="ghost", raw_alternative=90, actual=10)
    out = graphifychat.render_view(graphifychat.summarize(root, pol))
    assert "1 graphify receipt(s) unassignable" in out
    assert "1 graphify receipt(s) unmatched" in out


# ── worst-case method / confidence ────────────────────────────────────────────

def test_worst_case_method_and_confidence_across_receipts(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _savings(root, session="s1", raw_alternative=500, actual=100,
             method="modeled", confidence=0.6)
    _savings(root, session="s1", raw_alternative=300, actual=100,
             method="estimated", confidence=0.3, ts="2026-07-01T09:06:00Z")
    r = graphifychat.summarize(root, pol)["rows"][0]
    assert r["method"] == "estimated"          # least-trusted wins
    assert r["confidence"] == 0.3               # min wins


# ── refusal vs a real zero ────────────────────────────────────────────────────

def test_no_receipts_dashes_gfx_cells_but_tokens_still_render(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1", tin=100, tout=50)
    data = graphifychat.summarize(root, pol)
    out = graphifychat.render_view(data, all_chats=True)
    row = next(l for l in out.splitlines() if l.startswith("s1"))
    cells = row.split()
    assert cells[3] == "—"          # gfx uses
    assert cells[4] == "150"        # tokens — a real fact, not a refusal
    assert cells[5] == "—"          # without gfx
    assert cells[6] == "—"          # saved
    assert cells[7] == "—"          # saved%


def test_no_receipts_is_excluded_by_default_only_all_chats_shows_it(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    data = graphifychat.summarize(root, pol)
    default_out = graphifychat.render_view(data)
    assert "s1" not in default_out
    all_out = graphifychat.render_view(data, all_chats=True)
    assert "s1" in all_out


def test_a_measured_zero_saved_renders_zero_percent_not_a_dash(root, pol):
    """THE distinction the view exists for: a real receipt whose raw==actual (saved
    0) is a MEASURED zero, not an absence of usage."""
    _call(root, "c_1", agent="claude-code", session="s1", tin=100, tout=0)
    _savings(root, session="s1", raw_alternative=100, actual=100)
    r = graphifychat.summarize(root, pol)["rows"][0]
    assert r["saved"] == 0 and r["has_gfx"] is True
    out = graphifychat.render_view(graphifychat.summarize(root, pol))
    assert "0%" in out


def test_kiro_credit_chat_shows_saved_but_dashes_token_cells(root, pol):
    """A kiro-CLI credit chat carries no token counts at all — `saved` still shows
    (a real receipt joined), tokens/without/pct dash with their own footnote."""
    _credit(root, session="kc1", credits=2.0)
    _savings(root, session="kc1", raw_alternative=500, actual=100)
    data = graphifychat.summarize(root, pol)
    r = data["rows"][0]
    assert r["from_credits"] is True and r["saved"] == 400
    assert r["tokens"] is None and r["without"] is None and r["pct"] is None
    out = graphifychat.render_view(data)
    row = next(l for l in out.splitlines() if l.startswith("kc1"))
    cells = row.split()
    assert cells[4] == "—" and cells[5] == "—" and cells[7] == "—"  # tokens/without/pct
    assert cells[6] == "400"                                        # saved shown
    assert "kiro CLI reports credits only" in out


# ── negative saved (never clamped) ───────────────────────────────────────────

def test_negative_saved_renders_honestly_never_clamped(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1", tin=10, tout=0)
    _savings(root, session="s1", raw_alternative=100, actual=150)  # answer cost > read cost
    r = graphifychat.summarize(root, pol)["rows"][0]
    assert r["saved"] == -50
    assert r["without"] == -40  # tokens(10) + saved(-50), never clamped to 0
    out = graphifychat.render_view(graphifychat.summarize(root, pol))
    assert "-50" in out


# ── determinism ───────────────────────────────────────────────────────────────

def test_determinism(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1", tin=100, tout=50)
    _call(root, "c_2", agent="copilot", session="s2", surface="cli")
    _savings(root, session="s1", raw_alternative=500, actual=100)
    first = graphifychat.summarize(root, pol)
    assert first == graphifychat.summarize(root, pol)
    assert (graphifychat.render_view(first) ==
            graphifychat.render_view(graphifychat.summarize(root, pol)))
    assert (graphifychat.render_csv(first) ==
            graphifychat.render_csv(graphifychat.summarize(root, pol)))


# ── flags ─────────────────────────────────────────────────────────────────────

def test_since_filter(root, pol):
    _call(root, "c_old", agent="claude-code", session="s_old", ts="2020-01-01T00:00:00Z")
    _savings(root, session="s_old", raw_alternative=200, actual=50,
             ts="2020-01-01T00:05:00Z")
    _call(root, "c_new", agent="claude-code", session="s_new",
          ts="2026-08-12T09:00:00Z")
    _savings(root, session="s_new", raw_alternative=200, actual=50,
             ts="2026-08-12T09:05:00Z")
    data = graphifychat.summarize(root, pol, since="7d")
    assert {r["session"] for r in data["rows"] if r["has_gfx"]} == {"s_new"}


def test_agent_filter(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _call(root, "c_2", agent="copilot", session="s2", surface="cli")
    _savings(root, session="s1", raw_alternative=200, actual=50)
    _savings(root, session="s2", raw_alternative=200, actual=50)
    data = graphifychat.summarize(root, pol, agent="copilot")
    assert [r["agent"] for r in data["rows"]] == ["copilot"]


def test_all_flag_lifts_the_default_row_cap(root, pol):
    n = constants.GRAPHIFY_CHATS_DEFAULT_ROWS + 5
    for i in range(n):
        sess = f"s_{i:03d}"
        _call(root, f"c_{i}", agent="claude-code", session=sess)
        _savings(root, session=sess, raw_alternative=1000 - i, actual=10)
    data = graphifychat.summarize(root, pol)
    default_out = graphifychat.render_view(data)
    assert "5 more chat(s) — --all to show" in default_out
    full_out = graphifychat.render_view(data, show_all=True)
    assert "more chat(s)" not in full_out
    for i in range(n):
        assert f"s_{i:03d}" in full_out


def test_csv_never_truncates_and_never_filters_by_receipts(root, pol):
    import csv as _csv
    import io
    _call(root, "c_1", agent="claude-code", session="s1")   # no receipt
    _call(root, "c_2", agent="claude-code", session="s2")
    _savings(root, session="s2", raw_alternative=200, actual=50)
    data = graphifychat.summarize(root, pol)
    rows = list(_csv.DictReader(io.StringIO(graphifychat.render_csv(data))))
    assert {r["session"] for r in rows} == {"s1", "s2"}
    by = {r["session"]: r for r in rows}
    assert by["s1"]["saved"] == "" and by["s1"]["receipts"] == ""
    assert by["s2"]["saved"] == "150"


def test_csv_kiro_credit_chat_leaves_token_cells_empty_not_zero(root, pol):
    import csv as _csv
    import io
    _credit(root, session="kc1", credits=1.0)
    _savings(root, session="kc1", raw_alternative=300, actual=100)
    data = graphifychat.summarize(root, pol)
    row = next(iter(_csv.DictReader(io.StringIO(graphifychat.render_csv(data)))))
    assert row["tokens"] == "" and row["without_graphify"] == "" and row["pct"] == ""
    assert row["saved"] == "200"


# ── empty states ──────────────────────────────────────────────────────────────

def test_empty_no_savings_at_all_diagnoses(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    out = graphifychat.render_view(graphifychat.summarize(root, pol))
    assert "No graphify savings recorded yet." in out
    assert "cage query graphify-coverage" in out
    assert "cage doctor" in out
    assert "cage insights roi" in out


def test_empty_filtered_blames_the_filter_when_savings_exist_elsewhere(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _savings(root, session="s1", raw_alternative=200, actual=50)
    data = graphifychat.summarize(root, pol, agent="copilot")
    out = graphifychat.render_view(data)
    assert "the filter is empty, not the ledger" in out


def test_empty_default_view_points_at_all_chats_flag(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")  # no receipt anywhere
    _savings(root, session="ghost", raw_alternative=200, actual=50)  # unmatched, so any_savings True
    out = graphifychat.render_view(graphifychat.summarize(root, pol))
    assert "--all-chats" in out


# ── CLI wiring ────────────────────────────────────────────────────────────────

def test_cli_wiring(root, monkeypatch, capsys):
    from cage import cli
    monkeypatch.chdir(root)
    _call(root, "c_1", agent="claude-code", session="s1")
    _savings(root, session="s1", raw_alternative=200, actual=50)
    assert cli.main(["insights", "graphify", "--no-import"]) == 0
    assert "Graphify per-chat" in capsys.readouterr().out
    assert cli.main(["insights", "graphify", "--no-import", "--csv"]) == 0
    assert capsys.readouterr().out.startswith("chat,")
    assert cli.main(["insights", "graphify", "--no-import", "--all"]) == 0
    assert cli.main(["insights", "graphify", "--no-import", "--all-chats"]) == 0
    assert cli.main(["insights", "graphify", "--no-import", "--agent", "copilot"]) == 0
