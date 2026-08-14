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
    # **Dual-write the metric twin**, exactly as real capture does. `chats.summarize`
    # reads `ledger.spend`, which supersedes a `calls` row for any agent that has a
    # metric spine (USAGE-ONLY, ADR 0011) — so a calls-only fixture reads as an empty
    # ledger and every assertion below would pin nothing. The twin carries the same
    # counts and the same bucket key `(agent, surface, session)`.
    from cage import agents as _ag
    surf = _ag.row_surface(agent) or agent
    if surf == "claude":
        ledger.append_row(root, "claude", schema.make_claude_metric(
            session=session, source="request", request=cid, provider=provider,
            model=model, tokens_in=tin, tokens_out=tout, cached_in=cached,
            cache_write_in=cache_write, surface=surface, ts=ts))
    elif surf == "copilot":
        ledger.append_row(root, "copilot", schema.make_copilot_metric(
            source="chat", session=session, surface=surface or "vscode", model=model,
            tokens_in=tin, tokens_out=tout, cached_in=cached, ts=ts,
            **({"credits": (extra or {}).get("credits")}
               if (extra or {}).get("credits") is not None else {})))


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
        ts=ts, session_name=name)


def _prov(root: Path, *, session: str, agent: str = "claude-code", sha: str = "abc1234",
          files: tuple = ("a.py",), agent_lines: int = 0,
          residual_lines: int | None = 0, **counts):
    """One provenance row the way `authorcapture` writes it. ``residual_lines=None``
    writes a **pre-upgrade** row (key absent), which is the version gate."""
    from cage import originrecord
    return originrecord.record_transcript(root, sha=sha, files=list(files), agent=agent,
                                          session_id=session, agent_lines=agent_lines,
                                          residual_lines=residual_lines, **counts)


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


# ── agent%: the authorship join ───────────────────────────────────────────────

def test_agent_pct_is_read_from_the_recorded_counts(root, pol):
    """READ, never re-derived — no matcher and no git run at render time."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _prov(root, session="s1", agent_lines=62, residual_lines=38)
    r = chats.summarize(root, pol)["rows"][0]
    assert (r["agent_lines"], r["residual_lines"]) == (62, 38)
    assert r["agent_pct"] == 62.0
    assert r["auth_refusal"] == ""
    assert "62%" in chats.render_chats(chats.summarize(root, pol))


def test_the_join_normalizes_the_agent_name_on_both_sides(root, pol):
    """Provenance stamps `claude-code`, the bucket keys on `claude` — one
    normalization function (`agents.row_surface`), never a second mapping."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _prov(root, session="s1", agent="claude-code", agent_lines=3, residual_lines=1)
    r = chats.summarize(root, pol)["rows"][0]
    assert r["agent"] == "claude" and r["agent_pct"] == 75.0


def test_rows_from_many_commits_sum_into_one_chat(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _prov(root, session="s1", sha="aaa1111", agent_lines=10, residual_lines=10)
    _prov(root, session="s1", sha="bbb2222", agent_lines=30, residual_lines=10)
    r = chats.summarize(root, pol)["rows"][0]
    assert (r["agent_lines"], r["residual_lines"], r["auth_rows"]) == (40, 20, 2)
    assert r["agent_pct"] == pytest.approx(66.667, abs=0.001)


def test_another_sessions_rows_never_leak_into_this_chat(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _call(root, "c_2", agent="claude-code", session="s2")
    _prov(root, session="s1", agent_lines=9, residual_lines=1)
    _prov(root, session="s2", sha="bbb2222", agent_lines=1, residual_lines=9)
    by = {r["session"]: r for r in chats.summarize(root, pol)["rows"]}
    assert by["s1"]["agent_pct"] == 90.0
    assert by["s2"]["agent_pct"] == 10.0


# ── the refusal triad: `—` is never 0% ────────────────────────────────────────

def test_refusal_no_landed_evidence(root, pol):
    """A chat with no provenance row: nothing landed, or it landed in another repo.
    "Nothing landed" is not "the agent wrote nothing"."""
    _call(root, "c_1", agent="claude-code", session="s1")
    r = chats.summarize(root, pol)["rows"][0]
    assert r["agent_pct"] is None and r["auth_refusal"] == chats.NO_EVIDENCE
    out = chats.render_chats(chats.summarize(root, pol))
    assert "no landed code evidence" in out
    assert "`—` is never 0%" in out


def test_refusal_coverage_names_the_reason_verbatim(root, pol):
    """Copilot/kiro stores cannot be line-matched at all — the reason comes from
    `authorcapture.coverage_note()`, never re-worded here."""
    from cage import authorcapture
    _call(root, "c_1", agent="copilot", session="s1", surface="vscode")
    r = chats.summarize(root, pol)["rows"][0]
    assert r["agent_pct"] is None and r["auth_refusal"] == chats.COVERAGE
    assert authorcapture.coverage_note() in chats.render_chats(chats.summarize(root, pol))


def test_refusal_pre_upgrade_rows_are_excluded_and_counted(root, pol):
    """Frozen rows predating `residual_lines` contribute to NEITHER sum — folding
    their `agent_lines` into the numerator with no denominator would inflate it."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _prov(root, session="s1", agent_lines=50, residual_lines=None)
    r = chats.summarize(root, pol)["rows"][0]
    assert r["auth_refusal"] == chats.PRE_UPGRADE
    assert r["agent_pct"] is None
    assert (r["agent_lines"], r["residual_lines"]) == (0, 0)
    assert r["auth_pre_upgrade"] == 1
    out = chats.render_chats(chats.summarize(root, pol))
    assert "1 provenance row(s) predate residual counts — excluded" in out


def test_a_mixed_chat_computes_over_the_carrying_rows_only(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _prov(root, session="s1", sha="aaa1111", agent_lines=8, residual_lines=2)
    _prov(root, session="s1", sha="bbb2222", agent_lines=99, residual_lines=None)
    r = chats.summarize(root, pol)["rows"][0]
    assert r["agent_pct"] == 80.0          # the pre-upgrade row's 99 is not in it
    assert r["auth_pre_upgrade"] == 1
    assert "1 provenance row(s) predate residual counts" in chats.render_chats(
        chats.summarize(root, pol))


def test_a_real_zero_percent_renders_zero_not_a_dash(root, pol):
    """THE distinction the column exists for. A dash spent on absence of evidence
    would leave nothing to say "measured, and it was none of it"."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _prov(root, session="s1", agent_lines=0, residual_lines=40)
    r = chats.summarize(root, pol)["rows"][0]
    assert r["agent_pct"] == 0.0 and r["auth_refusal"] == ""
    out = chats.render_chats(chats.summarize(root, pol))
    assert "0%" in out
    assert "no landed code evidence" not in out


def test_a_row_with_no_matchable_line_refuses_rather_than_dividing_by_zero(root, pol):
    """A commit of only binary files lands a row carrying zeros on both sides. There
    is no share to compute, so it refuses as `no evidence` — never 0%, never a crash."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _prov(root, session="s1", agent_lines=0, residual_lines=0)
    r = chats.summarize(root, pol)["rows"][0]
    assert r["agent_pct"] is None and r["auth_refusal"] == chats.NO_EVIDENCE


def test_a_session_split_across_surfaces_is_footnoted_not_silently_doubled(root, pol):
    """Provenance carries no surface, so its counts attach to every bucket sharing
    `(agent, session)` — the reader is told, rather than shown two rows that look
    like independent evidence."""
    _call(root, "c_1", agent="claude-code", session="s1", surface="cli")
    _call(root, "c_2", agent="claude-code", session="s1", surface="vscode")
    _prov(root, session="s1", agent_lines=3, residual_lines=1)
    rows = chats.summarize(root, pol)["rows"]
    assert len(rows) == 2 and all(r["auth_split"] for r in rows)
    assert "not independent evidence" in chats.render_chats(chats.summarize(root, pol))


# ── the v0.36 guard: no money ever touches an authorship number ────────────────

def test_no_authorship_number_is_ever_combined_with_a_usd_value(root, pol):
    """The standing guard from the human-axis removal. `chats.py` legitimately imports
    `prices` for the `cost` column, so the guard is **per formula**, not per import:
    no expression in this module may put an authorship count and a money value on the
    same line, and `--usd` must move no authorship cell."""
    import inspect
    import re
    from cage import display
    src = inspect.getsource(chats)
    money = ("cost", "usd", "credits", "price", "rate", "minutes")
    author = ("agent_lines", "residual_lines", "agent_pct")
    for i, line in enumerate(src.splitlines(), 1):
        code = line.split("#", 1)[0]
        if not any(a in code for a in author):
            continue
        # A dict/tuple that merely carries both names side by side is fine; an
        # ARITHMETIC operator between them is not.
        for m in money:
            assert not re.search(rf"\b{m}\w*\b\s*[-+*/]|[-+*/]\s*\w*\b{m}\b", code), \
                f"chats.py:{i} combines money with an authorship count: {line.strip()}"

    _call(root, "c_1", agent="claude-code", session="s1")
    _prov(root, session="s1", agent_lines=7, residual_lines=3)
    plain = chats.summarize(root, pol)["rows"][0]
    assert plain["agent_pct"] == 70.0
    # And the presentation switch cannot move it either.
    out = chats.render_chats(chats.summarize(root, pol), disp=display.Display())
    assert "70%" in out


# ── money independence: the one law amendment, pinned ──────────────────────────

def test_deleting_manifest_changes_zero_numeric_cells(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1", tin=100, tout=10, cached=5)
    _call(root, "c_2", agent="copilot", session="s2", surface="cli", tin=200, tout=20)
    _name(root, agent="claude-code", session="s1", name="my chat")
    before = chats.summarize(root, pol)
    paths.Footprint(root).imports.unlink()
    after = chats.summarize(root, pol)
    numeric_fields = ("calls", "tokens_in", "cached_in", "cache_write_in",
                      "tokens_out", "credits")
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


def test_deleting_provenance_changes_zero_pre_existing_cells(root, pol):
    """The **second** scoped carve-out, on the first one's exact terms: `agent%` reads
    `provenance.jsonl`, and deleting that file must move no pre-existing cell — only
    the new authorship cells fall to their refusal. If a number here ever depended on
    an authorship row, the money views would inherit a dependency on a diff-reading
    capture path that is opt-in and can be switched off."""
    _call(root, "c_1", agent="claude-code", session="s1", tin=100, tout=10, cached=5)
    _call(root, "c_2", agent="copilot", session="s2", surface="cli", tin=200, tout=20)
    _name(root, agent="claude-code", session="s1", name="my chat")
    _prov(root, session="s1", agent_lines=40, residual_lines=10)
    before = chats.summarize(root, pol)
    assert {r["session"]: r["agent_pct"] for r in before["rows"]}["s1"] == 80.0

    paths.Footprint(root).provenance.unlink()
    after = chats.summarize(root, pol)

    pre_existing = ("calls", "tokens_in", "cached_in", "cache_write_in", "tokens_out",
                    "premium", "credits", "title", "named", "agent", "surface")
    b = {r["session"]: r for r in before["rows"]}
    a = {r["session"]: r for r in after["rows"]}
    assert set(a) == set(b)
    for sess, row in b.items():
        for f in pre_existing:
            assert a[sess][f] == row[f], f"{f} moved for {sess}"
    # Only the authorship cells changed — and they refuse rather than reading 0%.
    assert a["s1"]["agent_pct"] is None
    assert a["s1"]["auth_refusal"] == chats.NO_EVIDENCE
    assert a["s1"]["agent_lines"] == 0


def test_determinism(root, pol):
    _call(root, "c_1", agent="claude-code", session="s1")
    _call(root, "c_2", agent="copilot", session="s2", surface="vscode")
    _name(root, agent="claude-code", session="s1", name="chat one")
    _prov(root, session="s1", agent_lines=5, residual_lines=3)
    first = chats.summarize(root, pol)
    assert first == chats.summarize(root, pol)
    assert chats.render_chats(first) == chats.render_chats(first)
    assert chats.render_csv(first) == chats.render_csv(first)


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

def test_kiro_ide_chats_are_absent_because_kiro_has_no_token_spine(root, pol):
    """The honest consequence of `ledger.ABSENT_SPINES` (USAGE-ONLY, ADR 0011).

    Kiro's IDE `calls` rows are suppressed from `spend()` — there is no IDE token store
    on this install, so cage will not present a token figure for it. It renders NOTHING
    here rather than a fabricated row, and the reason is stated on `cage report` and by
    `cage doctor`'s three-way store probe. The constant-session collapse this test used
    to pin (`KIRO_IDE_LABEL`) is still implemented and still correct — it simply has no
    rows to apply to until a Kiro ships the store."""
    _call(root, "c_k1", agent="kiro", session="kiro", surface="ide",
          provider="kiro", model="agent", tin=100, tout=0)
    _call(root, "c_k2", agent="kiro", session="kiro", surface="ide",
          provider="kiro", model="agent", tin=200, tout=0)
    assert chats.summarize(root, pol)["rows"] == []
    from cage import ledger as _l, units
    assert _l.SPEND_SOURCES["kiro"] == ()
    assert units.absent_reason("kiro", units.TOKENS)


def test_csv_carries_the_authorship_counts_and_leaves_a_refusal_empty(root, pol):
    """`—` never enters CSV, and neither does a fabricated 0: a refused chat's three
    authorship cells are **empty**, because writing `0,0` would put the very claim the
    text dash refuses to make (*this agent wrote none of it*) into machine-readable
    data. The empty-not-dash rule `credits` already follows."""
    import csv as _csv
    import io
    _call(root, "c_1", agent="claude-code", session="s1", tin=900)
    _call(root, "c_2", agent="copilot", session="s2", surface="vscode", tin=800)
    _call(root, "c_3", agent="claude-code", session="s3", tin=700)
    _prov(root, session="s1", agent_lines=45, residual_lines=15)
    rows = list(_csv.DictReader(io.StringIO(chats.render_csv(chats.summarize(root, pol)))))
    by = {r["session"]: r for r in rows}

    assert (by["s1"]["agent_lines"], by["s1"]["residual_lines"]) == ("45", "15")
    assert by["s1"]["agent_pct"] == "75"            # 0–100, 1dp (trailing zero trimmed)
    for sess in ("s2", "s3"):                       # coverage · no-evidence
        assert by[sess]["agent_lines"] == ""
        assert by[sess]["residual_lines"] == ""
        assert by[sess]["agent_pct"] == ""
    assert "—" not in chats.render_csv(chats.summarize(root, pol))


def test_csv_agent_pct_keeps_one_decimal(root, pol):
    import csv as _csv
    import io
    _call(root, "c_1", agent="claude-code", session="s1")
    _prov(root, session="s1", agent_lines=1, residual_lines=2)   # 33.333…
    row = next(iter(_csv.DictReader(io.StringIO(
        chats.render_csv(chats.summarize(root, pol))))))
    assert row["agent_pct"] == "33.3"
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


# ── structural absence: the filter is blamed only when the filter is the reason ──
#
# `cage insights chats --agent kiro` printing "the filter is empty, not the ledger" is
# a true sentence about the filter and a misleading one about kiro-IDE: its rows route
# to the machine ledger (ADR 0006), a fact cage has in hand at render time. Saying
# *filter* when the answer is *architecture* sends a reader to check their typing
# instead of the ledger they actually want. (Kiro-CLI conversations used to carry a
# second structural reason here — their credits rows carried no call at all, so no
# chat row could exist for them. CHATS-CREDITS removed that limit: a credits row now
# renders its own chat row, tested in the section below.)

def _credit(root: Path, *, session: str, agent: str = "kiro", credits: float = 3.5,
            turns: int = 4, ts: str = "2026-07-01T10:00:00Z"):
    """One kiro-CLI credits row — a different row shape with no tokens and no call."""
    ledger.append_row(root, "credits", schema.make_credit(
        session=session, credits=credits, agent=agent, turns=turns, ts=ts))


def test_the_routed_sink_is_named_in_the_empty_view_too(root, pol):
    """The kiro-routing line was computed and then dropped on the empty path — an
    agent showing nothing is indistinguishable from an agent whose capture broke,
    which is the failure this line exists to prevent."""
    out = chats.render_chats(chats.summarize(root, pol, agent="kiro"),
                             kiro_route="· kiro is not counted here — …")
    assert "kiro is not counted here" in out


def test_a_filter_that_really_is_the_reason_still_says_so(root, pol):
    """An agent with no rows at all (no calls, no credits) still gets the plain
    filter-is-empty message — copilot's absence here has nothing to do with kiro's
    credits row existing elsewhere in the ledger."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _credit(root, session="kc1")
    out = chats.render_chats(chats.summarize(root, pol, agent="copilot"))
    assert "the filter is empty, not the ledger" in out


def test_a_filtered_view_is_never_told_about_another_agents_reason(root, pol):
    _credit(root, session="kc1")
    out = chats.render_chats(chats.summarize(root, pol, agent="claude"),
                             kiro_route="· kiro is not counted here — …")
    assert "kiro" not in out


# ── CHATS-CREDITS: a kiro-CLI conversation is its own chat row ─────────────────

def test_a_credit_conversation_renders_as_a_chat_row_not_a_refusal(root, pol):
    """The defect this change fixes: a kiro-CLI conversation used to make the whole
    view refuse with a false `cage report` pointer. It now renders like any other
    chat — `calls` and all four token cells dashed (nothing was ever a call), the
    old refusal text gone entirely."""
    _credit(root, session="kc1", credits=3.5)
    out = chats.render_chats(chats.summarize(root, pol, agent="kiro"))
    assert "recorded as credits, not token calls" not in out
    assert "carries no calls" not in out
    assert "the filter is empty, not the ledger" not in out
    lines = out.splitlines()
    row = next(l for l in lines if l.startswith("kc1"))
    cells = row.split()
    assert cells[:2] == ["kc1", "kiro"]
    # calls, tokens_in, cached_in, cache_write, tokens_out all dash; credits filled
    assert cells[3:8] == ["—"] * 5
    assert "3.50" in cells


def test_a_non_empty_view_still_names_the_usage_it_shows(root, pol):
    """The unfiltered view renders both the call chat and the credits chat, and
    footnotes the credits-only-store limit rather than the old silent-omission gap
    (there is no longer anything silently omitted)."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _credit(root, session="kc1")
    out = chats.render_chats(chats.summarize(root, pol))
    assert "s1" in out and "kc1" in out
    assert "kiro CLI reports credits only" in out


def test_reading_credits_adds_a_row_and_moves_no_call_chat_cell(root, pol):
    """The third money-independent carve-out, restated for the new shape: a credits
    row can never perturb a *call* chat's cells — it only ever adds a row of its
    own. Deleting the credits shard removes that row and changes nothing else."""
    _call(root, "c_1", agent="claude-code", session="s1", tin=100, tout=10, cached=5)
    _credit(root, session="kc1", credits=7.0)
    before = chats.summarize(root, pol)
    assert {r["session"] for r in before["rows"]} == {"s1", "kc1"}
    s1_before = next(r for r in before["rows"] if r["session"] == "s1")

    from cage import paths
    for f in paths.Footprint(root).shards("credits"):
        f.unlink()
    after = chats.summarize(root, pol)
    assert {r["session"] for r in after["rows"]} == {"s1"}
    s1_after = after["rows"][0]
    numeric_fields = ("calls", "tokens_in", "cached_in", "cache_write_in",
                      "tokens_out", "credits")
    for f in numeric_fields:
        assert s1_after[f] == s1_before[f], f"{f} moved"
    assert chats.render_csv(before) != chats.render_csv(after)  # the credits row left
def test_credit_row_since_filters_by_ts(root, pol):
    _credit(root, session="kc_old", credits=1.0, ts="2020-01-01T00:00:00Z")
    _credit(root, session="kc_new", credits=1.0)  # default ts: 2026-07-01T10:00:00Z
    data = chats.summarize(root, pol, since="7d")
    assert {r["session"] for r in data["rows"]} == set()
    data_recent = chats.summarize(root, pol, since="100d")
    assert {r["session"] for r in data_recent["rows"]} == {"kc_new"}


def test_credit_row_agent_pct_refuses_via_existing_coverage_gap(root, pol):
    """No new authorship logic: kiro is already in `authorcapture.COVERAGE_GAPS`, so
    a credits chat's `agent%` refuses the same way a kiro call chat's would."""
    from cage import authorcapture
    _credit(root, session="kc1")
    r = chats.summarize(root, pol)["rows"][0]
    assert r["auth_refusal"] == chats.COVERAGE
    assert authorcapture.coverage_note() in chats.render_chats(chats.summarize(root, pol))


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
    assert cli.main(["insights", "chats", "--no-import", "--agent", "copilot"]) == 0


# ── COPILOT-PREMIUM-DEAD (closed 2026-08-11) ──────────────────────────────────

def test_the_lossy_premium_duplicate_is_gone_from_both_tables(root, pol):
    """`premium` is `floor(credits)` — the same counter as an int — so a column of it
    beside `credits` could only ever agree-but-rounded or print `0`. Fails before the
    fix: both tables carried the column."""
    _call(root, "c_1", agent="copilot", session="s1", surface="cli", premium=2,
          extra={"credits": 2.4})
    data = chats.summarize(root, pol)
    text, csv = chats.render_chats(data), chats.render_csv(data)
    assert "premium" not in text.splitlines()[2]
    assert "premium" not in csv.splitlines()[0].split(",")
    # …and the counter it duplicated is still on both, unrounded in the data.
    assert "credits" in text.splitlines()[2] and "credits" in csv.splitlines()[0]
    assert "2.4" in csv


def test_premium_no_longer_reaches_this_view_and_loses_nothing(root, pol):
    """`premium` was a `calls`-row field, and `calls` is no longer the spend basis for
    copilot (USAGE-ONLY, ADR 0011) — the copilot metric row carries no such field, so
    the payload's `premium` stays 0.

    **Nothing real is lost, which is why this is a pin rather than a defect.** Premium
    is `floor(credits)` (COPILOT-PREMIUM-DEAD): a lossy integer duplicate of a figure
    that DOES survive on the metric row. The substrate field is untouched on the
    append-only `calls` rows that carry it; it simply is not a derived cell any more."""
    _call(root, "c_1", agent="copilot", session="s1", surface="cli", premium=3,
          extra={"credits": 3.4})
    row = chats.summarize(root, pol)["rows"][0]
    assert row["premium"] == 0
    assert row["credits"] == pytest.approx(3.4), "the precise figure survives"
