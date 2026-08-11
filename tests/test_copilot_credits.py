"""COPILOT-CREDITS — billed credits as rung 1 of the copilot pricing ladder.

The feature exists because Copilot's stores persist the credit figure GitHub itself
billed, and cage was dropping it — leaving `copilot/auto` (the majority of real VS Code
traffic) loudly UNPRICED with no price-table row that could ever match it.

What this file pins, in the order the ladder is read:

1. **Capture is verbatim, and absence is a fact.** A recorded credit is stored exactly
   as the store wrote it; a missing one leaves the row byte-identical to the legacy
   contract; a recorded `0.0` is a REAL zero that must never collapse into absence.
2. **One rung wins per row**, resolved at the single pricing choke point so every view
   inherits it — including the case that motivated the work: a row whose model no price
   table can match, but whose credits price it exactly.
3. **The method law holds at rung 1** — `modeled`, never `measured`. The count is fact;
   the dollar is a rate the user configured and cage cannot verify.
4. **Nothing is ever blended silently** — a total spanning both bases names the split,
   and credits with no rate render as a count rather than vanishing.
5. **A legacy ledger is untouched, byte for byte**, in the ledger and on every surface.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cage import (chats, creditprice, doctorcmd, ledger, paths, prices, report,
                  schema, transcript)
from cage.policy import load as load_policy


@pytest.fixture
def root(proj):
    (proj / ".cage" / "ledger").mkdir(parents=True)
    return proj


@pytest.fixture
def pol(root):
    return load_policy(paths.Footprint(root).policy)


def _rate(root: Path, rate: float, agent: str = "copilot"):
    """Set the `[billing.<agent>]` rate in the project's cage.toml and reload.

    Written into **cage.toml**, not prices.toml — that placement is the §10 resolution
    and is load-bearing: `[credits]` is a price section this loader reads from the
    prices file alone, so a rate filed there would have merged as absent. A partial
    project policy is enough; `policy.load` merges it over the bundled default."""
    p = paths.Footprint(root).policy
    p.parent.mkdir(parents=True, exist_ok=True)
    prior = p.read_text(encoding="utf-8") if p.exists() else ""
    p.write_text(prior + f'\n[billing.{agent}]\nusd_per_credit = {rate}\n', encoding="utf-8")
    return load_policy(p)


def _call(root: Path, cid: str, *, credits=None, model: str = "copilot/auto",
          provider: str = "", agent: str = "copilot", tin: int = 1000, tout: int = 100,
          session: str = "s1", surface: str = "vscode", ts: str = "2026-07-01T09:00:00Z"):
    row = schema.make_call(route="chat", provider=provider, model=model, tokens_in=tin,
                           tokens_out=tout, agent=agent, session=session,
                           surface=surface, ts=ts, credits=credits, call_id=cid)
    ledger.append(paths.Footprint(root).calls, row)
    return row


# ── 1 · capture ───────────────────────────────────────────────────────────────

def _vscode_store(tmp_path: Path, *reqs: dict) -> Path:
    """A minimal chatSessions jsonl in the real store's shape (kind:0 header, then a
    kind:2 `requests` patch) — the format pinned against copilot-chat 0.54.0."""
    p = tmp_path / "sess.jsonl"
    head = {"kind": 0, "v": {"sessionId": "sess"}}
    body = {"kind": 2, "k": ["requests"], "v": list(reqs)}
    p.write_text(json.dumps(head) + "\n" + json.dumps(body) + "\n", encoding="utf-8")
    return p


def _req(rid: str, **extra) -> dict:
    req = {"requestId": rid, "timestamp": 1783447814720, "modelId": "copilot/auto",
           "agent": {"extensionId": {"value": "github.copilot-chat"}},
           "promptTokens": 25343, "completionTokens": 95}
    req.update(extra)
    return req


def test_vscode_credits_captured_verbatim(tmp_path):
    """The real store's values are fractional to 6dp — they must arrive unrounded.
    Rounding at capture would quietly restate what the vendor billed."""
    store = _vscode_store(tmp_path, _req("r1", copilotCredits=1.382565))
    row = transcript.parse_copilot_vscode_calls(store)[0]
    assert row["credits"] == 1.382565


def test_vscode_absent_credits_stay_absent(tmp_path):
    """No credit recorded ⇒ NO key on the row. This is the legacy-contract guarantee:
    the overwhelming majority of real requests carry no credit, and they must stay
    byte-identical to rows written before the field existed."""
    store = _vscode_store(tmp_path, _req("r1"))
    assert "credits" not in transcript.parse_copilot_vscode_calls(store)[0]


def test_vscode_zero_credits_is_a_real_zero(tmp_path):
    """A recorded 0.0 (an included / 0x-rate model) is a billing FACT, and the whole
    reason `make_call`'s default is a `None` sentinel rather than 0.0: the usual
    omit-at-default idiom would erase the difference between 'billed nothing' and
    'we don't know'."""
    store = _vscode_store(tmp_path, _req("r1", copilotCredits=0))
    row = transcript.parse_copilot_vscode_calls(store)[0]
    assert row["credits"] == 0.0 and creditprice.recorded(row) == 0.0


@pytest.mark.parametrize("bad", ["1.5", None, {"v": 1}, [1], True])
def test_vscode_malformed_credits_read_as_absent(tmp_path, bad):
    """Fail-open on the capture path: a malformed field is skipped with absent
    semantics, never coerced. `True` is in the list deliberately — bool is an int
    subclass, and a `True` credit is malformed data, not the number 1."""
    store = _vscode_store(tmp_path, _req("r1", copilotCredits=bad))
    assert "credits" not in transcript.parse_copilot_vscode_calls(store)[0]


def test_cli_credits_are_float_where_premium_floors_to_zero(tmp_path):
    """The defect that made the CLI half necessary: `totalPremiumRequests` is
    fractional in every real sample (0.33), and the legacy int `premium` field floors
    it to 0 and then drops the key — 13 copilot-CLI rows in a real ledger, not one
    carrying a premium. `credits` carries it; `premium` is left exactly as it was."""
    ev = tmp_path / "events.jsonl"
    ev.write_text(json.dumps({
        "type": "session.shutdown", "timestamp": "2026-06-14T11:00:00Z",
        "data": {"totalPremiumRequests": 0.33,
                 "modelMetrics": {"claude-haiku-4.5": {"usage": {
                     "inputTokens": 15553, "outputTokens": 92}}}}}) + "\n",
        encoding="utf-8")
    row = transcript.parse_copilot_calls(ev, session="0f3c2b1a")[0]
    assert row["credits"] == 0.33
    assert "premium" not in row  # int(0.33) == 0 → omitted, exactly as before


def test_cli_cumulative_credits_are_delta_not_double_counted(tmp_path):
    """A resumed session writes a SECOND cumulative shutdown. Credits follow the same
    delta discipline as the token counters, so the rows sum to the true total."""
    ev = tmp_path / "events.jsonl"
    def shutdown(prem, tin):
        return json.dumps({"type": "session.shutdown", "timestamp": "2026-06-14T11:00:00Z",
                           "data": {"totalPremiumRequests": prem,
                                    "modelMetrics": {"m": {"usage": {
                                        "inputTokens": tin, "outputTokens": 10}}}}})
    ev.write_text(shutdown(0.33, 100) + "\n" + shutdown(0.90, 250) + "\n", encoding="utf-8")
    rows = transcript.parse_copilot_calls(ev, session="s")
    assert sum(r["credits"] for r in rows) == pytest.approx(0.90)


# ── the delta must land on a row the loop actually EMITS ──────────────────────
#
# `prev_cred` advances once per shutdown, before the per-model loop. A model whose
# token counters did not move is skipped (`if not (din or dout): continue`) — so if
# the credit delta was pinned to a fixed index and *that* model idled, the delta went
# on the floor: no row carried it, the cursor had already moved, and no debug line was
# written. Billed spend, permanently undercounted. Dict order decided whether it
# happened, which is why the fix is a deterministic pick among emitted rows.

def _shutdown(prem, models):
    return json.dumps({"type": "session.shutdown",
                       "timestamp": "2026-06-14T11:00:00Z",
                       "data": {"totalPremiumRequests": prem,
                                "modelMetrics": {m: {"usage": {"inputTokens": tin,
                                                               "outputTokens": tout}}
                                                 for m, (tin, tout) in models.items()}}})


def test_the_credit_delta_survives_when_the_first_listed_model_idles(tmp_path):
    """A resumed session whose second shutdown used only model B. Model A is still
    first in `modelMetrics` and its counters have not moved, so it emits no row."""
    ev = tmp_path / "events.jsonl"
    ev.write_text(
        _shutdown(0.33, {"a": (100, 10), "b": (50, 5)}) + "\n" +
        _shutdown(0.90, {"a": (100, 10), "b": (500, 50)}) + "\n", encoding="utf-8")
    rows = transcript.parse_copilot_calls(ev, session="s")
    assert all(r["model"] != "a" or r["tokens_in"] for r in rows)   # 'a' idled in #2
    # The full billed total survives — this summed to 0.33 before the fix.
    assert sum(r.get("credits") or 0 for r in rows) == pytest.approx(0.90)


def test_the_delta_lands_on_the_largest_row_not_on_dict_order(tmp_path):
    """Deterministic and explicable: the biggest token mover carries the shutdown's
    credits. Ties break on model name, so re-parsing is byte-identical."""
    ev = tmp_path / "events.jsonl"
    ev.write_text(_shutdown(1.5, {"small": (10, 1), "big": (900, 90)}) + "\n",
                  encoding="utf-8")
    rows = {r["model"]: r for r in transcript.parse_copilot_calls(ev, session="s")}
    assert rows["big"]["credits"] == pytest.approx(1.5)
    assert rows["small"].get("credits") is None


def test_a_credit_delta_with_no_emitting_model_is_not_silently_dropped(tmp_path):
    """Every model idled but GitHub still billed. Dropping it undercounts real spend
    forever, so a zero-token carrier row keeps it — a true statement (this shutdown
    billed N credits and moved no tokens), never a fabricated call."""
    ev = tmp_path / "events.jsonl"
    ev.write_text(_shutdown(0.33, {"a": (100, 10)}) + "\n" +
                  _shutdown(0.90, {"a": (100, 10)}) + "\n", encoding="utf-8")
    rows = transcript.parse_copilot_calls(ev, session="s")
    assert sum(r.get("credits") or 0 for r in rows) == pytest.approx(0.90)
    carrier = [r for r in rows if not r["tokens_in"] and not r["tokens_out"]]
    assert len(carrier) == 1 and carrier[0]["credits"] == pytest.approx(0.57)


def test_a_counter_that_goes_backwards_never_produces_negative_dollars(tmp_path):
    """A store rewrite or a reset on resume makes the cumulative counter drop. Stored
    verbatim that is a negative delta, quietly shrinking every USD total. Treat it as
    a reset: the new cumulative value IS the delta."""
    ev = tmp_path / "events.jsonl"
    ev.write_text(_shutdown(5.0, {"a": (100, 10)}) + "\n" +
                  _shutdown(1.0, {"a": (200, 20)}) + "\n", encoding="utf-8")
    rows = transcript.parse_copilot_calls(ev, session="s")
    assert all((r.get("credits") or 0) >= 0 for r in rows)
    assert sum(r.get("credits") or 0 for r in rows) == pytest.approx(6.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_counter_is_absent_and_costs_no_other_row(tmp_path, bad):
    """`json.dumps`/`json.loads` both accept bare `NaN`/`Infinity` — so a store can
    emit one and Python will read it back. `int()` *raises* on both, and that exception
    escaped the parser and cost **the whole file's rows**, which is a far bigger loss
    than the one bad field. Absent ≠ a recorded 0.0, and the tokens still land."""
    ev = tmp_path / "events.jsonl"
    ev.write_text(json.dumps({
        "type": "session.shutdown", "timestamp": "2026-06-14T11:00:00Z",
        "data": {"totalPremiumRequests": bad,
                 "modelMetrics": {"a": {"usage": {"inputTokens": 100,
                                                  "outputTokens": 10}}}}}) + "\n",
        encoding="utf-8")
    rows = transcript.parse_copilot_calls(ev, session="s")
    assert len(rows) == 1 and rows[0]["tokens_in"] == 100   # the tokens survive
    assert "credits" not in rows[0] and "premium" not in rows[0]


# ── 2 · rung selection ────────────────────────────────────────────────────────

def test_rung1_prices_a_model_no_table_can_match(root):
    """The finding this feature retires: `copilot/auto` matches no price row, so the
    token rung cannot price it at all — but the recorded credit prices it exactly,
    with no price-table row involved."""
    c = _call(root, "c1", credits=2.5)
    assert prices.call_usd_match(load_policy(paths.Footprint(root).policy), c)[1] == "none"
    usd, match, key = prices.call_usd_match(_rate(root, 0.04), c)
    assert (usd, match, key) == (0.1, creditprice.MATCH, None)


def test_rung1_beats_a_priceable_model(root):
    """Rung order is not "whatever is available" — a recorded credit outranks a
    perfectly good price row, because GitHub computed it with the routing and rates
    cage cannot see."""
    c = _call(root, "c1", credits=1.0, provider="anthropic", model="claude-sonnet-4-6")
    usd, match, _ = prices.call_usd_match(_rate(root, 0.04), c)
    assert match == creditprice.MATCH and usd == 0.04


def test_rung2_when_no_credits_recorded(root):
    """Absence falls THROUGH — never derived from tokens, and never a fabricated 0."""
    c = _call(root, "c1", provider="anthropic", model="claude-sonnet-4-6")
    _, match, _ = prices.call_usd_match(_rate(root, 0.04), c)
    assert match in ("exact", "family", "alias")


def test_rung2_when_credits_recorded_but_no_rate(root, pol):
    """No rate configured ⇒ rung 1 is skipped entirely, and the row prices the old way.
    A credit is not a dollar until you say what a credit costs."""
    c = _call(root, "c1", credits=2.5, provider="anthropic", model="claude-sonnet-4-6")
    _, match, _ = prices.call_usd_match(pol, c)
    assert match != creditprice.MATCH and creditprice.unrated(pol, c)


def test_recorded_zero_prices_at_zero_via_rung1(root):
    """A real zero prices at $0.0000 *through rung 1* — distinguishable from a row that
    simply could not price, which stays UNPRICED."""
    c = _call(root, "c1", credits=0.0)
    usd, match, _ = prices.call_usd_match(_rate(root, 0.04), c)
    assert usd == 0.0 and match == creditprice.MATCH


def test_zero_rate_still_prices(root):
    """A rate of exactly 0 is a legitimate statement (credits cost nothing marginally),
    distinct from an unset rate — it prices, it does not skip the rung."""
    c = _call(root, "c1", credits=5.0)
    usd, match, _ = prices.call_usd_match(_rate(root, 0.0), c)
    assert usd == 0.0 and match == creditprice.MATCH


def test_the_ladder_has_exactly_one_implementation():
    """ONE ladder: `call_usd_match` is the only caller of the rung-1 resolver, and
    `call_usd` reaches it only by wrapping that. A second copy in any view is a spec
    violation, so this greps the package for one."""
    import subprocess
    hits = subprocess.run(["grep", "-rln", "creditprice.resolve", "cage/"],
                          capture_output=True, text=True).stdout.split()
    assert hits == ["cage/prices.py"]


# ── 3 · method law ────────────────────────────────────────────────────────────

def test_rung1_is_modeled_never_measured(root):
    """The count is recorded fact; the dollar is a rate the user configured and cage
    cannot check against an invoice. A `measured` tag here would let that rate read as
    an invoice — the one thing method tagging exists to prevent."""
    assert creditprice.method_for({creditprice.CREDITS: 1}) == "modeled"
    assert creditprice.method_for({creditprice.CREDITS: 1, creditprice.TOKENS: 9}) == "modeled"
    assert creditprice.method_for({creditprice.TOKENS: 9}) == "measured"


def test_report_csv_degrades_to_modeled_when_credits_priced(root):
    _call(root, "c1", credits=2.0)
    pol = _rate(root, 0.04)
    rep = report.summarize(root, pol, dim="agent")
    assert report.render_csv(rep).strip().splitlines()[-1].endswith("modeled")


def test_report_csv_stays_measured_without_credits(root, pol):
    _call(root, "c1", provider="anthropic", model="claude-sonnet-4-6")
    rep = report.summarize(root, pol, dim="agent")
    assert report.render_csv(rep).strip().splitlines()[-1].endswith("measured")


# ── 4 · rendering: never blended, never silent ────────────────────────────────

def _usd_report(root, pol, dim="agent") -> str:
    from cage import display
    return report.render_report(report.summarize(root, pol, dim=dim),
                                disp=display.Display(usd=True))


def test_mixed_basis_total_names_the_split(root):
    """A total that sums a credits-priced and a token-priced cell must SAY so, with the
    split — verdict C rule 4. Silence here would blend the two axes in one number."""
    _call(root, "c1", credits=2.0)
    _call(root, "c2", provider="anthropic", model="claude-sonnet-4-6")
    out = _usd_report(root, _rate(root, 0.04))
    assert "copilot priced on two bases" in out
    assert "1 call(s) by credits×rate (2.00 cr → $0.0800)" in out
    assert "1 call(s) by token×table" in out


def test_split_footnote_never_borrows_another_agents_spend(root):
    """The footnote claims *this agent's* rows priced two ways, so both halves must
    count only that agent's calls. Tallying the token side view-wide made it report a
    claude call's dollars as copilot's token-table half — a wrong number in the one
    line whose whole job is to keep the two bases apart.

    Here copilot's only other row is UNPRICED, so copilot has NO token-priced call and
    earns no split footnote at all — even though a token-priced claude call exists."""
    _call(root, "c1", credits=2.0)                                   # copilot, rung 1
    _call(root, "c2")                                                # copilot, UNPRICED
    _call(root, "c3", agent="claude", session="s2", provider="anthropic",
          model="claude-sonnet-4-6")                                 # claude, rung 2
    out = _usd_report(root, _rate(root, 0.04))
    assert "priced on two bases" not in out


def test_split_footnote_is_per_agent(root):
    """Two agents each splitting across both rungs get one footnote each — the claim is
    never aggregated into a single cross-agent 'two bases' line."""
    _call(root, "c1", credits=2.0)
    _call(root, "c2", provider="anthropic", model="claude-sonnet-4-6")
    _call(root, "c3", agent="kiro", session="s3", credits=1.0)
    _call(root, "c4", agent="kiro", session="s3", provider="anthropic",
          model="claude-sonnet-4-6")
    pol = _rate(root, 0.04)
    pol = _rate(root, 0.10, agent="kiro")
    out = _usd_report(root, pol)
    assert "copilot priced on two bases" in out
    assert "kiro priced on two bases" in out


def test_single_basis_prints_no_split_footnote(root):
    """The footnote is for a MIXED total only — printing it over a uniform one would
    train readers to skip it."""
    _call(root, "c1", credits=2.0)
    assert "priced on two bases" not in _usd_report(root, _rate(root, 0.04))


def test_rate_unset_shows_credits_as_a_count_never_a_dollar(root, pol):
    """Recorded but unpriceable credits surface as a COUNT with a runnable fix — they
    neither vanish nor acquire an invented dollar."""
    _call(root, "c1", credits=2.5)
    _call(root, "c2", credits=1.5)
    out = _usd_report(root, pol)
    assert "2 call(s) carry recorded credits (4.00 cr) — not priced" in out
    assert "[billing.copilot] usd_per_credit" in out


def test_unpriced_block_gains_the_second_fix_line(root, pol):
    """An unpriced row that carries credits needs a RATE, not a price-table alias.
    Offering only the alias fix would send the reader to solve the harder problem."""
    _call(root, "c1", credits=2.5)          # copilot/auto: unpriced, but has credits
    out = _usd_report(root, pol)
    assert "UNPRICED" in out
    assert "cage prices alias" in out                       # the token-rung fix
    assert "1 of these rows carry recorded credits" in out  # the credits-rung fix


def test_no_second_fix_line_when_unpriced_rows_have_no_credits(root, pol):
    _call(root, "c1")
    out = _usd_report(root, pol)
    assert "UNPRICED" in out and "carry recorded credits" not in out


def test_credits_priced_row_reports_no_cache_split(root):
    """A credits-priced dollar did not come from the price table, so no slice of it may
    be attributed to `cache_read` — that would describe a total that was never
    token-derived."""
    c = _call(root, "c1", credits=2.0)
    c  # noqa: B018 — row is in the ledger; the assertion is on the rollup
    rep = report.summarize(root, _rate(root, 0.04), dim="agent")
    assert rep["total"]["usd"] == 0.08 and rep["total"]["cache_usd"] == 0.0


# ── 5 · chats view ────────────────────────────────────────────────────────────

def test_chats_credits_column_dash_in_text_absent_in_csv(root, pol):
    """`—` reads as *not recorded* and is the honest cell for claude/kiro and for the
    many copilot requests the store leaves bare. It must never reach CSV."""
    _call(root, "c1", agent="claude", session="s2", model="claude-sonnet-4-6",
          provider="anthropic")
    data = chats.summarize(root, pol)
    assert "—" in chats.render_chats(data)
    csv = chats.render_csv(data)
    assert "—" not in csv
    assert csv.splitlines()[1].split(",")[10] == ""   # credits column, empty not 0


def test_chats_credits_column_sums_and_renders_2dp(root):
    _call(root, "c1", credits=1.382565, session="s1")
    _call(root, "c2", credits=0.100185, session="s1")
    data = chats.summarize(root, _rate(root, 0.04))
    assert "1.48" in chats.render_chats(data)                  # display: 2dp
    assert "1.48275" in chats.render_csv(data)                 # data: full precision


def _csv_rows(root):
    """Read by HEADER, never by column index — the chats CSV gains columns (`agent%`
    added three in CHATS-AUTHOR), and a positional read turns that into a false
    failure about credits."""
    import csv as _csv
    import io
    return list(_csv.DictReader(io.StringIO(chats.render_csv(_chats_data(root)))))


def test_chats_priced_via_names_the_basis(root):
    _call(root, "c1", credits=2.0, session="s1")
    _call(root, "c2", agent="claude", session="s2", provider="anthropic",
          model="claude-sonnet-4-6")
    vias = sorted(r["priced_via"] for r in _csv_rows(root))
    assert vias == [creditprice.CREDITS, creditprice.TOKENS]


def test_chats_priced_via_mixed_when_a_chat_spans_both(root):
    """A chat is not forced to pick a winner — a bucket whose rows priced differently
    says `mixed` rather than claiming one basis for all of it."""
    _call(root, "c1", credits=2.0, session="s1")
    _call(root, "c2", session="s1", provider="anthropic", model="claude-sonnet-4-6")
    assert _csv_rows(root)[0]["priced_via"] == creditprice.MIXED


def _chats_data(root):
    return chats.summarize(root, _rate(root, 0.04))


# ── 6 · legacy ledgers are untouched ──────────────────────────────────────────

def test_legacy_ledger_rows_are_byte_identical(root, pol):
    """The additive-field guarantee, asserted on the bytes: a row written with no
    credits carries no `credits` key, so a pre-COPILOT-CREDITS ledger re-renders and
    re-serializes exactly as before."""
    _call(root, "c1", provider="anthropic", model="claude-sonnet-4-6")
    raw = paths.Footprint(root).calls.read_text(encoding="utf-8")
    assert "credits" not in raw
    assert "credits" not in json.loads(raw.splitlines()[0])


def test_legacy_ledger_surfaces_gain_no_new_lines(root, pol):
    """No credits anywhere ⇒ not one of the new advisory/footnote lines may fire. This
    is what keeps every pre-existing golden byte-identical."""
    _call(root, "c1", provider="anthropic", model="claude-sonnet-4-6")
    out = _usd_report(root, pol)
    for phrase in ("priced on two bases", "carry recorded credits",
                   "of these rows carry recorded credits"):
        assert phrase not in out


def test_doctor_credits_check_is_advisory_never_a_fault(root, pol):
    """Credit coverage is a property of the vendor's logging, not the user's setup —
    so it never fails and never warns, in any state."""
    assert doctorcmd._credits(root)[0] == "ok"
    _call(root, "c1", credits=2.5)
    assert doctorcmd._credits(root)[0] == "ok"          # recorded, no rate
    _rate(root, 0.04)
    assert doctorcmd._credits(root)[0] == "ok"          # recorded, rate set


# ── 7 · determinism ───────────────────────────────────────────────────────────

def test_same_ledger_and_policy_give_the_same_bytes(root):
    _call(root, "c1", credits=2.0)
    _call(root, "c2", provider="anthropic", model="claude-sonnet-4-6")
    pol = _rate(root, 0.04)
    assert _usd_report(root, pol) == _usd_report(root, pol)
    assert (report.render_csv(report.summarize(root, pol, dim="agent"))
            == report.render_csv(report.summarize(root, pol, dim="agent")))


def test_rate_is_not_env_overridable(root, monkeypatch):
    """A billing rate is durable configuration. If the environment could move it, the
    one number people quote would stop being a function of (ledger, policy)."""
    monkeypatch.setenv("CAGE_USD_PER_CREDIT", "9.99")
    monkeypatch.setenv("CAGE_BILLING_COPILOT", "9.99")
    c = _call(root, "c1", credits=2.0)
    pol = load_policy(paths.Footprint(root).policy)
    assert prices.call_usd_match(pol, c)[1] != creditprice.MATCH


# ── REV-CREDITS defect 2 · one basis per shutdown (closed 2026-08-11) ─────────

def _multi_model_shutdown(tmp_path, credits: float = 3.0):
    """One shutdown, three models. GitHub computes `totalPremiumRequests` over ALL of
    them, so exactly one row can carry it — and the other two must not then price a
    second time off the token table."""
    ev = tmp_path / "events.jsonl"
    ev.write_text(json.dumps({
        "type": "session.shutdown", "timestamp": "2026-06-14T11:00:00Z",
        "data": {"totalPremiumRequests": credits, "modelMetrics": {
            "claude-haiku-4.5": {"usage": {"inputTokens": 100, "outputTokens": 10}},
            "claude-sonnet-4-6": {"usage": {"inputTokens": 9000, "outputTokens": 900}},
            "gpt-5": {"usage": {"inputTokens": 500, "outputTokens": 50}}}}}) + "\n",
        encoding="utf-8")
    return transcript.parse_copilot_calls(ev, session="0f3c2b1a")


def test_a_multi_model_shutdown_links_every_sibling_to_its_carrier(tmp_path):
    """Fails before the fix: the two non-carrier rows carried no link at all, so
    nothing downstream could tell that their billing had already been counted."""
    rows = _multi_model_shutdown(tmp_path)
    assert len(rows) == 3
    carrier = [r for r in rows if "credits" in r]
    assert len(carrier) == 1 and carrier[0]["model"] == "claude-sonnet-4-6"
    others = [r for r in rows if r is not carrier[0]]
    assert all(r["billed_with"] == carrier[0]["id"] for r in others)
    assert "billed_with" not in carrier[0]      # a carrier bills for itself


def test_the_shutdown_is_billed_once_not_once_per_model(tmp_path):
    """THE defect. With a rate configured the carrier priced GitHub's figure for the
    WHOLE shutdown and its two siblings priced their own tokens at cage's list rates —
    the same spend billed twice, on two bases, inside one shutdown."""
    from cage import prices
    pol = {"billing": {"copilot": {"usd_per_credit": 0.04}},
           "prices": {"copilot": {"claude-haiku-4.5": {"in_per_mtok": 1.0,
                                                       "out_per_mtok": 5.0},
                                  "gpt-5": {"in_per_mtok": 1.0, "out_per_mtok": 5.0}}}}
    rows = _multi_model_shutdown(tmp_path, credits=3.0)
    priced = [prices.call_usd_match(pol, r) for r in rows]
    assert sum(usd for usd, _m, _k in priced) == pytest.approx(0.12)   # 3.0 × $0.04
    assert {m for _u, m, _k in priced} == {"credits"}                  # ONE basis
    # …and the $0 rows name where their dollars went, so it is never a bare zero.
    zeros = [k for u, _m, k in priced if u == 0.0]
    assert len(zeros) == 2 and all(k and k.startswith("c_cop") for k in zeros)


def test_with_no_rate_the_whole_shutdown_falls_through_together(tmp_path):
    """The suppression is conditional on the carrier actually pricing by credits. With
    no `[billing.copilot] usd_per_credit` the carrier drops to rung 2, so its siblings
    must too — otherwise the shutdown would price at one model's tokens, not all three."""
    from cage import prices
    rows = _multi_model_shutdown(tmp_path)
    table: dict = {}
    for r in rows:            # two of the three share a provider — merge, never clobber
        table.setdefault(r["provider"], {})[r["model"]] = {
            "input": 1.0, "output": 5.0, "cache_read": 0.1}
    pol = {"prices": table}
    matches = [prices.call_usd_match(pol, r)[1] for r in rows]
    assert "credits" not in matches and all(m != "none" for m in matches)


def test_a_shutdown_with_no_credits_is_byte_identical(tmp_path):
    """No credit delta ⇒ no group basis to suppress ⇒ nothing stamped. The additive
    field must never appear on a row that bills for itself."""
    ev = tmp_path / "events.jsonl"
    ev.write_text(json.dumps({
        "type": "session.shutdown", "timestamp": "2026-06-14T11:00:00Z",
        "data": {"modelMetrics": {
            "claude-haiku-4.5": {"usage": {"inputTokens": 100, "outputTokens": 10}},
            "gpt-5": {"usage": {"inputTokens": 500, "outputTokens": 50}}}}}) + "\n",
        encoding="utf-8")
    rows = transcript.parse_copilot_calls(ev, session="0f3c2b1a")
    assert len(rows) == 2 and all("billed_with" not in r for r in rows)


def test_a_recorded_zero_credit_still_covers_its_siblings(tmp_path):
    """`is not None`, never truthiness: a shutdown that billed a real 0.0 has still been
    billed as a group, so its siblings are still covered and must not price at tokens."""
    rows = _multi_model_shutdown(tmp_path, credits=0.0)
    carrier = [r for r in rows if r.get("credits") == 0.0]
    assert len(carrier) == 1
    assert sum("billed_with" in r for r in rows) == 2
