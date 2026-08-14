"""USAGE-ONLY (ADR 0011) — cage measures token and credit USAGE, never cost.

This file is the regression pin for the money subsystem's deletion. It holds the
invariants that have no other owner now that fifteen modules and their tests are gone:

1. **No `$` reaches any output path** — the grep gate (§1). The deletion's own contract.
2. **One basis, no cutover** (§2) — `spend()` partitions by AGENT, not by time, and an
   agent with no metric spine keeps resolving from `calls` rather than vanishing.
3. **The per-agent unit policy** (§3) — two absences, two distinct reasons, never a `0`.
4. **The cross-agent credit law** (§4) — copilot credits and kiro credits are different
   units and are never summed.
5. **Capture invariants that outlived their pricing** (§5) — the `credits` None sentinel
   (inherited from the deleted `test_copilot_credits.py`, whose ladder is gone but whose
   *capture* rules are not), and kiro credits retagged `measured`.
6. **The three-way kiro-IDE probe** (§6) — db absent / table missing / column drift,
   which used to render one indistinguishable zero.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sqlite3

import pytest

from cage import chats, ledger, schema, transcript, units

REPO = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def proj(tmp_path):
    (tmp_path / ".cage" / "ledger").mkdir(parents=True)
    return tmp_path


def _call(root, cid, *, agent="claude-code", tin=100, tout=10, credits=None, ts=None):
    row = schema.make_call(route="chat", provider="anthropic", model="claude-sonnet-5",
                           tokens_in=tin, tokens_out=tout, agent=agent,
                           credits=credits, call_id=cid, ts=ts)
    ledger.append_row(root, "calls", row)
    return row


# ── §1 · the grep gate: no currency in any output path ───────────────────────────
#
# Mirrors `test_queue_honesty`'s style: a cheap mechanical assertion over the source
# that cannot be satisfied by a passing unit test elsewhere. It is deliberately a
# **source** scan rather than an output scan — an output scan only covers the states a
# fixture happens to produce, and the whole point is that no state produces a dollar.

#: Modules that may mention money only in PROSE (a docstring explaining what was removed
#: and why). Code in them is still scanned.
_PROSE_ONLY = {"verbmap.py"}

#: Identifiers that would reintroduce currency. `est_cost_usd` is deliberately absent:
#: the FIELD survives on call rows under the append-only law and is read by nothing.
_BANNED = ("call_usd", "saved_usd", "price_match", "usd_per_credit", "render.usd",
           "signed_usd", "credits_usd", "net_usd", "cost_usd", "unpriced")


def _py_sources():
    return sorted(p for p in (REPO / "cage").glob("*.py"))


def test_no_currency_identifier_survives_anywhere_in_cage():
    """No module defines, calls, or references a currency identifier."""
    offenders = []
    for path in _py_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
            if name and any(b.split(".")[-1] == name for b in _BANNED):
                offenders.append(f"{path.name}:{node.lineno} {name}")
    assert not offenders, "currency identifiers survive: " + "; ".join(offenders)


#: A currency rendering: `$` immediately followed by a digit. Deliberately narrow —
#: a bare `$` is a regex end-anchor in a dozen legitimate places and `${VAR}` is shell
#: interpolation in every wire module, so a wider pattern would cry wolf, and a gate
#: that cries wolf gets ignored (the same reason `test_queue_honesty` refuses to gate
#: on counts). `$0` is exempt: it is cage's own cost-of-cage slogan, not a figure.
#: The *formatters* that built currency strings are caught by the identifier test
#: above, which is the load-bearing half of this pair.
_CURRENCY = re.compile(r"\$(?!0\b)\d")


def test_no_dollar_sign_in_any_rendered_string():
    """No string literal renders a currency figure."""
    offenders = []
    for path in _py_sources():
        if path.name in _PROSE_ONLY:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and _CURRENCY.search(node.value):
                offenders.append(f"{path.name}:{node.lineno} {node.value[:60]!r}")
    assert not offenders, "currency renderings survive: " + "; ".join(offenders)


def test_the_deleted_modules_are_gone():
    """The fifteen money modules stay deleted — a re-add must be a deliberate ADR
    reversal, not an accidental resurrection by a future refactor."""
    gone = ("convert", "prices", "creditprice", "receiptprice", "roi", "netsaved",
            "matrix", "regression", "quality", "verdict", "recommend", "budget",
            "forecast", "pricescmd", "pricestoml")
    present = [m for m in gone if (REPO / "cage" / f"{m}.py").exists()]
    assert not present, f"deleted money modules are back: {present}"


# ── §2 · one basis, no cutover ───────────────────────────────────────────────────

def test_spend_cutover_no_longer_exists():
    from cage import constants
    assert not hasattr(constants, "SPEND_CUTOVER")


def test_spend_partitions_by_agent_not_by_time(proj):
    """An agent WITH a metric spine resolves from the metric ledger for all of history;
    the `calls` rows it supersedes are not double-counted."""
    _call(proj, "c_old", agent="claude-code", tin=100, ts="2020-01-01T00:00:00Z")
    _call(proj, "c_new", agent="claude-code", tin=200, ts="2030-01-01T00:00:00Z")
    ledger.append_row(proj, "claude", schema.make_claude_metric(
        session="s1", source="request", request="r1", tokens_in=7, tokens_out=1,
        ts="2020-06-01T00:00:00Z"))
    rows = ledger.spend(proj)
    assert [r["basis"] for r in rows] == ["metrics"], \
        "a claude calls row survived into spend() — the agent has a spine"
    assert sum(r.get("tokens_in", 0) for r in rows) == 7


def test_an_agent_with_no_spine_still_resolves_from_calls(proj):
    """The `calls` fallback is scoped, not universal. Dropping it entirely — the
    tempting reading of "one basis" — silently zeroes every library-, proxy- and
    codex-metered row (measured at 373 codex rows in one real ledger)."""
    _call(proj, "c_lib", agent="lib", tin=50)
    _call(proj, "c_codex", agent="codex", tin=60)
    rows = ledger.spend(proj)
    assert {r["agent"] for r in rows} == {"lib", "codex"}
    assert all(r["basis"] == "calls" for r in rows)
    assert sum(r["tokens_in"] for r in rows) == 110


def test_kiro_has_no_token_spine_and_says_why():
    assert ledger.SPEND_SOURCES["kiro"] == ()
    assert "kiro" in ledger.ABSENT_SPINES
    assert ledger.ABSENT_SPINES["kiro"]  # a reason, not an empty string


def test_kiro_calls_do_not_fall_back_to_a_second_basis(proj):
    """kiro is in `SPEND_SOURCES` with an empty tuple, so its `calls` rows are
    suppressed and it renders `—` with a reason — never a silent second basis."""
    _call(proj, "c_k", agent="kiro", tin=999)
    assert ledger.spend(proj) == []


# ── §3 · the per-agent unit policy ───────────────────────────────────────────────

def test_each_absence_has_its_own_reason():
    claude = units.absent_reason("claude", units.CREDITS)
    kiro = units.absent_reason("kiro", units.TOKENS)
    assert claude and kiro and claude != kiro, \
        "the two absences must not read alike — one is a vendor law, one a missing file"
    assert units.absent_reason("claude", units.TOKENS) is None
    assert units.absent_reason("copilot", units.CREDITS) is None


def test_an_unknown_agent_is_not_claimed_to_be_missing_anything():
    assert units.has("some-future-agent", units.CREDITS)
    assert units.absent_reason("some-future-agent", units.TOKENS) is None


def test_report_footer_states_each_absence_with_its_reason(proj):
    _call(proj, "c_1", agent="claude-code")
    ledger.append_row(proj, "claude", schema.make_claude_metric(
        session="s1", source="request", request="r1", tokens_in=5, tokens_out=1))
    out = chats.render_chats(chats.summarize(proj, {}))
    assert units.ABSENT["claude"][units.CREDITS] in out
    assert " 0.00" not in out, "an absent credit rendered as a zero"


# ── §4 · the cross-agent credit law ──────────────────────────────────────────────

def test_credits_are_summable_within_one_agent_only():
    assert units.summable(units.CREDITS, ["copilot"])
    assert units.summable(units.CREDITS, ["copilot", "copilot"])
    assert not units.summable(units.CREDITS, ["copilot", "kiro"])
    assert units.summable(units.TOKENS, ["copilot", "kiro"]), "tokens are one unit"


def test_blank_agents_never_flip_the_credit_law():
    assert units.summable(units.CREDITS, ["copilot", "", None])
    assert not units.summable(units.CREDITS, ["copilot", "", "kiro"])


def test_report_refuses_a_cross_agent_credit_total(proj):
    """Per-group cells stay (each is correct); the TOTAL is None and the view says why
    rather than inventing a unit."""
    ledger.append_row(proj, "credits", schema.make_credit(
        session="k1", credits=4.0, agent="kiro"))
    ledger.append_row(proj, "credits", schema.make_credit(
        session="c1", credits=9.0, agent="copilot"))
    data = chats.summarize(proj, {})
    assert not units.summable(units.CREDITS, data["agents_present"])
    out = chats.render_chats(data)
    assert "NOT summed across agents" in out


def test_report_totals_credits_for_a_single_agent(proj):
    ledger.append_row(proj, "credits", schema.make_credit(
        session="k1", credits=4.0, agent="kiro"))
    ledger.append_row(proj, "credits", schema.make_credit(
        session="k2", credits=2.5, agent="kiro"))
    data = chats.summarize(proj, {})
    assert units.summable(units.CREDITS, data["agents_present"])
    assert sum(r["credits"] or 0 for r in data["rows"]) == pytest.approx(6.5)


# ── §5 · capture invariants that outlived their pricing ──────────────────────────
#
# Inherited from the deleted `test_copilot_credits.py`. Its ladder is gone; these are
# rules about what capture RECORDS, which the deletion did not touch.

def test_absent_credits_and_a_recorded_zero_stay_different_facts(proj):
    """The one additive field whose default is a None sentinel rather than zero."""
    no_credit = _call(proj, "c_1", credits=None)
    zero = _call(proj, "c_2", credits=0.0)
    assert "credits" not in no_credit, "absence must not be written as a key"
    assert zero["credits"] == 0.0, "a recorded zero is a real billing fact"


def test_chats_renders_absent_credits_as_a_dash_and_a_recorded_zero_as_zero(proj):
    _call(proj, "c_1", agent="copilot", credits=0.0)
    assert chats._credits_cell({"credits": 0.0}) == "0.00"
    assert chats._credits_cell({"credits": None}) == "—"


def test_kiro_credits_are_measured_not_estimated():
    """AWS's own recorded charge, read back verbatim. It was `estimated` only while it
    stood in for dollars cage could not see; nothing stands in for anything now."""
    assert schema.make_credit(session="s", credits=1.0)["method"] == "measured"


def test_credits_are_never_derived_from_tokens(proj):
    """Neither direction. A token-only row records no credit at all."""
    row = _call(proj, "c_1", tin=1_000_000, tout=1_000_000)
    assert "credits" not in row


# ── §6 · the three-way kiro-IDE probe ────────────────────────────────────────────

def test_probe_reports_an_absent_store(tmp_path):
    state, detail = transcript.probe_kiro_ide_store(tmp_path / "devdata.sqlite")
    assert state == "absent" and detail


def test_probe_distinguishes_a_missing_table(tmp_path):
    db = tmp_path / "devdata.sqlite"
    sqlite3.connect(db).close()
    state, detail = transcript.probe_kiro_ide_store(db)
    assert state == "no-table" and "tokens_generated" in detail


def test_probe_distinguishes_column_drift(tmp_path):
    """The one state that is a cage defect rather than a fact about the machine —
    and the one the old single zero hid completely."""
    db = tmp_path / "devdata.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE tokens_generated (id INTEGER, tokens_prompt INTEGER)")
    con.commit()
    con.close()
    state, detail = transcript.probe_kiro_ide_store(db)
    assert state == "drift"
    assert "tokens_generated" in detail and "timestamp" in detail


def test_probe_reports_a_healthy_store(tmp_path):
    db = tmp_path / "devdata.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE tokens_generated "
                "(id INTEGER, tokens_prompt INTEGER, tokens_generated INTEGER, "
                " timestamp TEXT)")
    con.execute("INSERT INTO tokens_generated VALUES (1, 10, 5, '2026-01-01T00:00:00Z')")
    con.commit()
    con.close()
    state, detail = transcript.probe_kiro_ide_store(db)
    assert state == "ok" and "1 row" in detail
