"""`cage insights adoption` — the honesty boundary, pinned.

The view's whole value is keeping three unknowns apart: *never invoked* · *invoked and
cage filed nothing* · *invoked and cage cannot say by whom*. These tests assert the
boundary itself, not just the rendering — a blend of any two would still "look fine".

Also pinned here: the diagnostic-only invariant. This is the first view that READS the
usage breadcrumb, so it is the one place that could quietly turn a count into a price.
It never does, and `test_no_currency_anywhere` / `test_adoption_does_not_perturb_money_views`
are what keep that true rather than aspirational.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cage import adoption, ledger, paths, schema, usagelog
from cage.policy import load as load_policy


@pytest.fixture
def root(proj):
    (proj / ".cage" / "ledger").mkdir(parents=True)
    return proj


def _call(root: Path, cid: str, *, agent: str, session: str = "", ts: str = "2026-07-01T09:00:00Z"):
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="chat", provider="anthropic",
                                   model="claude-sonnet-4-6", tokens_in=100,
                                   tokens_out=50, agent=agent, session=session,
                                   ts=ts, call_id=cid))


def _saving(root: Path, *, tool: str = "graphify", session: str = "", call: str = "",
            ts: str = "2026-07-01T10:00:00Z", sid: str | None = None) -> str:
    """One savings row. ``call``/``session`` are the two join links the view resolves;
    both empty is exactly what the interceptor writes (it cannot know its caller)."""
    row = schema.make_savings(tool=tool, raw_alternative=1000, actual=100,
                              session=session, unit="tokens", method="modeled",
                              ts=ts, savings_id=sid)
    if call:
        row["call"] = call
    ledger.append_row(root, ("savings", tool), row)
    return row["id"]


def _usage(root: Path, *, op: str = "query", outcome: str = "receipt",
           route: str = "shim") -> None:
    usagelog.record(root, op=op, args_hash="deadbeef", exit=0, ms=5,
                    outcome=outcome, route=route)


# ── the two halves stay separate ─────────────────────────────────────────────

def test_both_halves_render_and_are_visibly_separate(root):
    _usage(root, outcome="receipt", route="shim")
    _usage(root, outcome="unmeasurable", route="shim")
    _call(root, "c_1", agent="claude-code", session="s1")
    _saving(root, session="s1")
    out = adoption.render_adoption(adoption.summarize(root))
    a_at, b_at = out.index("A · invocations"), out.index("B · per-agent attribution")
    assert a_at < b_at                                   # ordered, and both present
    assert "agent-blind" in out[a_at:b_at]               # half A never names an agent
    assert "claude" not in out[a_at:b_at]
    assert "claude" in out[b_at:]


def test_outcomes_are_read_from_the_field_not_re_derived(root):
    """A usage row recording `receipt` is counted as a receipt even with an EMPTY ledger.
    Re-deriving 'did a receipt land?' from the receipts would give a different — and
    wrong — answer; the recorded verdict is the only source."""
    _usage(root, outcome="receipt")
    _usage(root, outcome="unmeasurable")
    _usage(root, outcome="error")
    assert ledger.receipts(root) == []                   # nothing to re-derive from
    u = adoption.summarize(root)["usage"]
    assert u["outcomes"]["receipt"] == 1
    assert u["outcomes"]["unmeasurable"] == 1
    assert u["outcomes"]["error"] == 1
    assert u["runs"] == 3


def test_outcome_columns_cover_every_closed_outcome(root):
    """The columns come from `usagelog.OUTCOMES`, so a new outcome can never be silently
    dropped from the table."""
    for o in usagelog.OUTCOMES:
        _usage(root, outcome=o)
    out = adoption.render_adoption(adoption.summarize(root))
    for o in usagelog.OUTCOMES:
        assert o.replace("-", " ") in out


# ── half B: what is attributable, and what honestly is not ───────────────────

def test_shim_row_is_agent_unknown_with_the_structural_reason(root):
    """The interceptor stamps an empty session on purpose — a subprocess cannot know
    which agent spawned it. That row is agent-unknown, never bucketed as 'other'."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _saving(root)                                        # no call, no session — the shim
    data = adoption.summarize(root)
    assert data["attribution"]["attributed"] == 0
    assert data["attribution"]["unknown"] == [
        {"tool": "graphify", "reason": adoption.NO_LINK, "rows": 1}]
    out = adoption.render_adoption(data)
    assert "agent-unknown" in out
    assert "cannot" in out and "which agent spawned it" in out
    assert "structural, not a capture gap" in out
    assert "other" not in out.lower().split("agent-unknown")[1][:200]


def test_unjoined_link_is_a_separate_reason_from_no_link(root):
    """A session nothing in `calls` carries is a CAPTURE GAP, not the shim's structural
    limit — different fact, different fix, so it is never merged with it."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _saving(root, session="ghost-session")
    unknown = adoption.summarize(root)["attribution"]["unknown"]
    assert unknown == [{"tool": "graphify", "reason": adoption.UNJOINED, "rows": 1}]
    assert "capture gap worth chasing" in adoption.render_adoption(adoption.summarize(root))


def test_transcript_session_join_names_the_agent(root):
    _call(root, "c_1", agent="claude-code", session="s1")
    _saving(root, session="s1")
    rows = adoption.summarize(root)["attribution"]["agents"]
    assert rows == [{"agent": "claude", "tool": "graphify", "rows": 1,
                     "via": [adoption.VIA_SESSION]}]


def test_linked_call_join_is_exact_and_named_separately(root):
    """A receipt carrying a `call` id resolves the agent directly — a stronger link than
    the session, and labelled as such so the two are never passed off as one another."""
    _call(root, "c_1", agent="copilot", session="s1")
    _saving(root, tool="compressor", call="c_1")
    rows = adoption.summarize(root)["attribution"]["agents"]
    assert rows == [{"agent": "copilot", "tool": "compressor", "rows": 1,
                     "via": [adoption.VIA_CALL]}]


def test_ambiguous_session_stays_unknown_rather_than_picking_one(root):
    """Two agents share a session id ⇒ genuinely ambiguous. Resolving it to either name
    would invent a fact, so the row stays unknown."""
    _call(root, "c_1", agent="claude-code", session="shared")
    _call(root, "c_2", agent="copilot", session="shared")
    _saving(root, session="shared")
    att = adoption.summarize(root)["attribution"]
    assert att["attributed"] == 0
    assert att["unknown"] == [{"tool": "graphify", "reason": adoption.UNJOINED, "rows": 1}]


def test_never_invoked_is_phrased_as_no_evidence(root):
    """Every savings row found an agent, so the strong claim is sound — and even then it
    is stated as absence of evidence, never as proof of non-use."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _call(root, "c_2", agent="kiro", session="s2")
    _saving(root, session="s1")
    data = adoption.summarize(root)
    assert data["attribution"]["no_evidence"] == ["kiro"]
    assert data["attribution"]["no_evidence_claim"] == adoption.NO_EVIDENCE
    out = adoption.render_adoption(data)
    assert "no evidence of invocation: kiro" in out
    assert "not proof of non-use" in out
    assert "never invoked" not in out.lower()            # never stated as a fact


def test_no_evidence_weakens_when_anything_is_unattributed(root):
    """The distinction the whole view turns on. One agent-unknown row could belong to
    ANY agent, so 'kiro shows no evidence of invocation' is no longer supportable —
    asserting it would blend 'never ran' with 'ran, unattributable'."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _call(root, "c_2", agent="kiro", session="s2")
    _saving(root, session="s1", sid="s_1")
    _saving(root, sid="s_2")                              # the shim: agent-unknown
    data = adoption.summarize(root)
    assert data["attribution"]["no_evidence"] == ["kiro"]
    assert data["attribution"]["no_evidence_claim"] == adoption.NOT_ATTRIBUTED
    out = adoption.render_adoption(data)
    assert "no savings row attributed to: kiro" in out
    assert "NOT evidence they never invoked the tool" in out
    assert "1 row(s) above are\n    agent-unknown and could belong to any of them" in out
    assert "no evidence of invocation" not in out         # the strong claim is withheld


def test_lib_metered_calls_are_not_an_agent_that_could_adopt(root):
    """`lib` is `make_call`'s default for library metering — an adapter, not an agent.
    Listing it as 'no evidence of invocation' would be noise, not a finding."""
    _call(root, "c_1", agent="lib", session="s1")
    assert adoption.summarize(root)["attribution"]["no_evidence"] == []


def test_legacy_human_rows_are_excluded(root):
    """The Tier-1 human axis was amputated in v0.36; such a row is not a tool-adoption
    fact and is excluded exactly as the money views exclude it."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _saving(root, tool="human", session="s1")
    assert adoption.summarize(root)["attribution"]["rows"] == 0


# ── the stated decision: an empty half B refuses, it never vanishes ──────────

def test_empty_half_b_prints_an_explicit_refusal_not_an_empty_table(root):
    """The decision this view had to make. Every invocation came via the shim, so nothing
    is attributable — the half still renders, as a refusal naming the count and the cause.
    Suppressing it would make 'cage cannot attribute these' read like 'cage has no
    per-agent answer at all', which is the exact conflation the view exists to prevent."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _saving(root, sid="s_a")
    _saving(root, sid="s_b")
    out = adoption.render_adoption(adoption.summarize(root))
    assert "B · per-agent attribution" in out             # the half is NOT suppressed
    assert "per-agent attribution unavailable" in out
    assert "none of the 2 savings rows" in out
    body = out[out.index("B · per-agent attribution"):]
    assert "agent   tool" not in body                     # and no empty table either


def test_coverage_percentage_is_stated(root):
    _call(root, "c_1", agent="claude-code", session="s1")
    _saving(root, session="s1", sid="s_1")
    _saving(root, sid="s_2")
    out = adoption.render_adoption(adoption.summarize(root))
    assert "coverage: 1 of 2 savings rows (50%) are agent-attributable" in out


# ── empty states are honest, never zeros ─────────────────────────────────────

def test_empty_ledger_is_an_honest_empty(root):
    out = adoption.render_adoption(adoption.summarize(root))
    assert "No tool invocations and no savings receipts recorded yet." in out
    assert "cage import" in out and "cage doctor" in out
    assert "0" not in out.replace("cage doctor", "")     # no fabricated zero table


def test_no_graphify_but_savings_present_says_so(root):
    """Savings exist but the breadcrumb never ran — half A must say *no runs recorded*,
    not render a grid of zeros that reads like a measurement."""
    _call(root, "c_1", agent="claude-code", session="s1")
    _saving(root, session="s1")
    out = adoption.render_adoption(adoption.summarize(root))
    assert "no graphify runs recorded" in out
    assert "no usage breadcrumb on disk yet" in out
    assert "runs  receipt" not in out                     # half A prints no table at all


# ── the diagnostic-only invariant ────────────────────────────────────────────

def test_no_currency_anywhere(root):
    """Usage rows are never priced. This view counts them and prints no dollar figure —
    in ANY of its three output formats."""
    for o in usagelog.OUTCOMES:
        _usage(root, outcome=o)
    _call(root, "c_1", agent="claude-code", session="s1")
    _saving(root, session="s1")
    _saving(root, sid="s_x")
    data = adoption.summarize(root)
    text = adoption.render_adoption(data)
    blob = json.dumps(data) + text + adoption.render_csv(data)
    assert "$" not in blob
    for word in ("usd", "cost", "dollar", "saved"):
        assert word not in blob.lower()
    # the disclaimer itself is the one place "priced" may appear, and it must
    assert "usage rows are diagnostic and are never priced" in text
    assert blob.lower().count("price") == 1


def test_adoption_does_not_perturb_money_views(root):
    """Reading the usage log must not make it readable BY a money view — report/roi stay
    byte-identical across an adoption render (the GC1 invariant, from the new caller)."""
    from cage import report, roi
    (root / "store.py").write_text("x = 1\n" * 200)
    _usage(root)
    _call(root, "c_1", agent="claude-code", session="s1")
    _saving(root, session="s1")
    pol = load_policy(paths.Footprint(root).policy)
    before = (report.render_report(report.summarize(root, pol)), roi.by_tool(root, pol))
    adoption.render_adoption(adoption.summarize(root))
    after = (report.render_report(report.summarize(root, pol)), roi.by_tool(root, pol))
    assert before == after


def test_summarize_is_deterministic(root):
    for o in usagelog.OUTCOMES:
        _usage(root, outcome=o, route="shim")
    _usage(root, route="transcript")
    _call(root, "c_1", agent="claude-code", session="s1")
    _call(root, "c_2", agent="copilot", session="s2")
    _saving(root, session="s1", sid="s_1")
    _saving(root, tool="fux", session="s2", sid="s_2")
    _saving(root, sid="s_3")
    first = adoption.summarize(root)
    assert first == adoption.summarize(root)
    assert adoption.render_adoption(first) == adoption.render_adoption(first)


# ── CSV parity + MCP mirror ──────────────────────────────────────────────────

def test_csv_carries_the_same_numbers_and_keeps_the_halves_apart(root):
    import csv as _csv
    import io
    _usage(root, outcome="receipt", route="shim")
    _usage(root, outcome="unmeasurable", route="shim")
    _call(root, "c_1", agent="claude-code", session="s1")
    _call(root, "c_2", agent="kiro", session="s2")
    _saving(root, session="s1", sid="s_1")
    _saving(root, sid="s_2")
    data = adoption.summarize(root)
    rows = list(_csv.DictReader(io.StringIO(adoption.render_csv(data))))
    sections = {r["section"] for r in rows}
    assert sections == {"usage", "attribution"}          # distinguishable when flattened
    total = next(r for r in rows if r["dimension"] == "total")
    assert total["rows"] == "2" and total["receipt"] == "1" and total["unmeasurable"] == "1"
    agent_row = next(r for r in rows if r["dimension"] == "agent")
    assert agent_row["agent"] == "claude" and agent_row["rows"] == "1"
    unknown = next(r for r in rows if r["dimension"] == "agent-unknown")
    assert unknown["reason"] == adoption.NO_LINK and unknown["rows"] == "1"
    # the weakened claim survives into CSV — a spreadsheet must not read the strong one
    weak = next(r for r in rows if r["dimension"] == adoption.NOT_ATTRIBUTED)
    assert weak["key"] == "kiro" and weak["reason"] == adoption.NOT_ATTRIBUTED
    assert not [r for r in rows if r["dimension"] == adoption.NO_EVIDENCE]
    # a cell that does not apply is EMPTY, never a 0 that reads as "none"
    assert agent_row["receipt"] == "" and total["agent"] == ""


def test_csv_is_lf_and_header_only_when_empty(root):
    out = adoption.render_csv(adoption.summarize(root))
    assert "\r" not in out
    assert out.splitlines()[0].startswith("section,dimension,key,agent,tool,rows")


def test_mcp_mirrors_the_view(root, monkeypatch):
    from cage import mcpserver
    _usage(root)
    _call(root, "c_1", agent="claude-code", session="s1")
    _saving(root, session="s1")
    monkeypatch.setattr(mcpserver, "_root", lambda: root)
    assert any(t["name"] == "cage_adoption" for t in mcpserver.TOOLS)
    text, _ = mcpserver._call("cage_adoption", {})
    assert "A · invocations" in text and "B · per-agent attribution" in text
    csv_text, _ = mcpserver._call("cage_adoption", {"format": "csv"})
    assert csv_text.splitlines()[0].startswith("section,")


def test_cli_wiring(root, monkeypatch, capsys):
    from cage import cli
    monkeypatch.chdir(root)
    _usage(root)
    assert cli.main(["insights", "adoption", "--no-import"]) == 0
    assert "A · invocations" in capsys.readouterr().out
    assert cli.main(["insights", "adoption", "--no-import", "--csv"]) == 0
    assert capsys.readouterr().out.startswith("section,")


def test_since_windows_both_halves(root):
    _usage(root)                                          # stamped now → inside any window
    _call(root, "c_1", agent="claude-code", session="s1", ts="2020-01-01T00:00:00Z")
    _saving(root, session="s1", ts="2020-01-01T00:00:00Z")
    data = adoption.summarize(root, since="30d")
    assert data["usage"]["runs"] == 1                     # the fresh usage row survives
    assert data["attribution"]["rows"] == 0               # the 2020 saving does not


def test_unstamped_call_does_not_make_a_clean_session_ambiguous(root):
    """A call with no agent is an unknown, not a competing agent. Letting it into the
    session set would lose a real attribution to a false ambiguity."""
    _call(root, "c_1", agent="claude-code", session="s1")
    ledger.append(paths.Footprint(root).calls,
                  {"id": "c_2", "ts": "2026-07-01T09:00:00Z", "session": "s1",
                   "agent": "", "route": "chat", "provider": "anthropic",
                   "model": "claude-sonnet-4-6", "tokens_in": 1, "tokens_out": 1})
    _saving(root, session="s1")
    assert adoption.summarize(root)["attribution"]["agents"] == [
        {"agent": "claude", "tool": "graphify", "rows": 1, "via": [adoption.VIA_SESSION]}]
