"""The transcript→`calls` writer is retired for claude and copilot — P5.

**The two-strikes gate for this phase.** A returning writer does not raise, does not warn
and changes no user-visible output — it just silently doubles claude's recorded traffic
(measured at **1.979× on rows / 1.881× on tokens**, the
[P0 cross-check](../work/regression/2026-08-14-calls-vs-metric-crosscheck.md)). Nothing in
the suite would notice, because a second copy of the same facts looks exactly like more
facts. So it is asserted directly.

What must stay true, and each has a test below:

  1. **No built-in sweep writes a `calls` row for claude or copilot** — the retirement.
  2. **`cage.meter` still does** — the consumer writer is untouched, and the assertion is
     in the same test so "no calls rows anywhere" can never be mistaken for success.
  3. **The parsers survive** — `transcript.parse_calls` and friends are the
     `[sources.<name>] format = …` custom-source contract (10.1). Deleting them would
     break user config silently.
  4. **Kiro is retired too — and its facts RELOCATED, not dropped.** See below.

**Kiro: retired, on a condition.** For claude and copilot the retired leg was a
*duplicate*: `ledger/claude/` and `ledger/copilot/` hold the same traffic, so stopping the
writer lost nothing. Kiro IDE had no such twin — `parse_kiro_ide_metrics` reads
`devdata.sqlite`, absent on every install ever probed — so retiring its leg unchanged
would have ENDED kiro IDE capture rather than de-duplicating it. That is why P5 kept it
and flagged it as KIRO-CALLS-LEG.

**Arpit ratified the retirement on 2026-08-15 with the condition attached: "retire it and
capture the data in ledger/kiro."** So `tokens_generated.jsonl` is now read into the
kiro-metrics ledger as `source="ide-log"`, and the tests below assert the retirement and
the relocation TOGETHER. That pairing is the whole gate: "no kiro calls rows" alone is
satisfied just as well by deleting the leg outright, which is precisely what the condition
forbade — and nothing else in the suite would have noticed, because kiro rows were already
excluded from every total by `ABSENT_SPINES` and so their disappearance changes no number
a user ever sees.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cage import importcmd, ledger, metering, paths, schema, transcript
from srcseed import mkcage


def _claude_line(uuid: str, tin: int, tout: int) -> str:
    return json.dumps({"type": "assistant", "uuid": uuid,
                       "timestamp": "2026-06-14T10:00:00Z",
                       "message": {"model": "claude-opus-4-8",
                                   "usage": {"input_tokens": tin,
                                             "output_tokens": tout}}})


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    mkcage(root)
    monkeypatch.setenv("CAGE_BASE", str(root / ".cage"))
    monkeypatch.delenv("CAGE_LEDGER", raising=False)
    monkeypatch.chdir(root)
    return root


# ── 1 + 2 · the gate ────────────────────────────────────────────────────────────

def test_a_full_sweep_writes_no_calls_row_but_record_call_still_does(proj, tmp_path):
    """**The gate, and both halves live in one test on purpose.**

    Asserting only "no calls rows" would pass just as happily on a ledger where capture is
    broken outright — which is the failure this whole program keeps guarding against. The
    `record_call` half is what makes the first half mean *retired* rather than *dead*."""
    tp = tmp_path / "session.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    importcmd.run(proj, "claude", SimpleNamespace(path=str(tp), project=None, since=None))

    assert ledger.spend(proj), "capture produced nothing — the assertion below is vacuous"
    assert [c for c in ledger.calls(proj) if c.get("agent") == "claude-code"] == []

    call_id = metering.record_call(route="chat", provider="anthropic", model="m",
                                   tokens_in=10, tokens_out=2, root=proj)
    assert call_id, "`cage.meter`'s writer must be untouched"
    assert [c for c in ledger.calls(proj) if c.get("id") == call_id]


def test_the_retirement_is_per_agent_not_a_disabled_writer(proj, tmp_path):
    """`ledger.append_row(root, "calls", …)` still works for everything else. If the
    *substrate* had been disabled instead of the legs, retired-agent history (373 codex
    rows in one real ledger) would stop being writable too — and a bundle import, which
    replays those rows, would silently drop them."""
    from cage import schema
    ok = ledger.append_row(proj, "calls", schema.make_call(
        route="chat", provider="openai", model="gpt-5-codex", agent="codex",
        tokens_in=500, ts="2026-05-10T00:00:00Z"))
    assert ok
    assert [c["agent"] for c in ledger.calls(proj)] == ["codex"]
    assert ledger.spend(proj)[0]["basis"] == "calls"


# ── 3 · the parsers survive ─────────────────────────────────────────────────────

def test_the_parsers_are_kept_for_the_custom_source_contract():
    """10.1. `_PARSERS` is the `[sources.<name>] format = …` contract; deleting the four
    parsers would break a user's config with no error — the row kind would simply stop
    appearing. They are unreachable from the built-in path and fully reachable from config."""
    for fmt in ("claude", "copilot", "kiro"):
        assert fmt in importcmd._PARSERS
    for name in ("parse_calls", "parse_copilot_calls", "parse_copilot_vscode_calls",
                 "parse_kiro_calls"):
        assert callable(getattr(transcript, name)), name


def test_a_custom_source_still_writes_calls_rows(proj, tmp_path, monkeypatch):
    """The contract exercised end to end: a `[sources.<name>]` tool declaring
    `format = "claude"` reuses the kept parser and still lands `calls` rows under its own
    agent name. This is the route that would have broken silently."""
    logs = tmp_path / "router"
    logs.mkdir()
    (logs / "r.jsonl").write_text(_claude_line("cx1", 50, 10) + "\n", encoding="utf-8")
    foot = paths.Footprint(proj)
    foot.policy.write_text(
        foot.policy.read_text(encoding="utf-8")
        + f'\n[sources.myrouter]\npaths = ["{logs.as_posix()}"]\n'
          'format = "claude"\nglob = "*.jsonl"\n', encoding="utf-8")
    importcmd.run(proj, "all", SimpleNamespace(path=None, project=None, since=None))
    rows = [c for c in ledger.calls(proj) if c.get("agent") == "myrouter"]
    assert rows and rows[0]["tokens_in"] == 50


def test_a_custom_claude_source_inherits_the_quarantined_defects():
    """⚠ **Documented, not fixed.** A custom source declaring `format = "claude"` reuses
    `parse_calls` and therefore inherits CLAUDE-DEDUP (rows ~1.98× inflated) and
    CLAUDE-SUBAGENT-KEY (subagent spend mis-keyed). ADR-CLAUDE forbids "fixing" these on
    the way out — the 2.00× measurement has to outlive the code — so the caveat is recorded
    in ADR-CONSUMERS instead of being discovered by whoever writes that config.

    Asserted as a documentation gate rather than a behaviour one: the behaviour is
    deliberate, and what must not happen is it going unmentioned."""
    from pathlib import Path
    adr = (Path(__file__).resolve().parents[1] / "docs" / "adr" / "0007_consumer.md")
    text = adr.read_text(encoding="utf-8").lower()
    assert "claude-dedup" in text
    assert 'format = "claude"' in text or "format = `claude`" in text


# ── 4 · kiro: retired AND relocated ─────────────────────────────────────────────

def _kiro_log(tmp_path, tin=1200, tout=0):
    log = tmp_path / "tokens_generated.jsonl"
    log.write_text(json.dumps({"model": "agent", "provider": "kiro",
                               "promptTokens": tin, "generatedTokens": tout}) + "\n",
                   encoding="utf-8")
    return log


def test_kiros_calls_writer_is_retired_and_its_store_still_captured(proj, tmp_path):
    """**Both halves in one test, and that is the point.**

    The retirement half alone would pass on a kiro leg deleted outright — and deleting it
    outright was the one outcome Arpit's ratification ruled out, because kiro IDE has no
    metric twin. So the relocation is asserted in the same breath: the same store, the
    same number, in `ledger/kiro/` under `source="ide-log"`.

    A failure here is a real regression in either direction — a returning `calls` writer
    (silent double-recording) or a vanished IDE capture (silent data loss, invisible in
    every total because kiro was never in one)."""
    log = _kiro_log(tmp_path)
    importcmd.run(proj, "kiro", SimpleNamespace(path=str(log), project=None, since=None))
    sink = paths.kiro_routed(proj) or proj

    assert [c for c in ledger.calls(sink) if c.get("agent") == "kiro"] == []

    rows = [r for r in ledger.kiro_metrics(sink) if r.get("source") == "ide-log"]
    assert rows, "the store lost its only reader — retirement without relocation"
    assert rows[0]["tokens_in"] == 1200
    assert rows[0]["surface"] == "ide" and rows[0]["agent"] == "kiro"


def test_the_relocated_rows_are_capture_only_by_kind_not_by_exception(proj, tmp_path):
    """Why the move is an improvement rather than a lateral. As `calls` rows these were
    spend that every total had to exclude BY NAME (`ABSENT_SPINES["kiro"]`, a maintained
    exception that fails open — forget it once and kiro's `0`-output rows start deflating
    a real average). As kiro-metrics rows they cannot reach a spend basis at all: the kind
    is capture-only, so the exclusion is structural.

    `absent_reason` is asserted alongside, because "excluded from the total" must keep
    rendering as `—` with a stated reason and never as a fabricated `0`."""
    log = _kiro_log(tmp_path)
    importcmd.run(proj, "kiro", SimpleNamespace(path=str(log), project=None, since=None))
    sink = paths.kiro_routed(proj) or proj
    assert [r for r in ledger.spend(sink) if r.get("agent") == "kiro"] == []
    from cage import units
    assert units.absent_reason("kiro", units.TOKENS)


def test_reimport_never_double_records_the_relocated_store(proj, tmp_path):
    """The `calls` leg's line-index+content-hash id survived the move, so the append-only
    log stays safe to re-read. Asserted because the dedupe anchor changed kinds: metrics
    rows dedupe against `ledger.kiro_metrics_raw`, a different seen-set from the call-id
    one this leg used to ride."""
    log = _kiro_log(tmp_path)
    args = SimpleNamespace(path=str(log), project=None, since=None)
    importcmd.run(proj, "kiro", args)
    sink = paths.kiro_routed(proj) or proj
    once = [r for r in ledger.kiro_metrics(sink) if r.get("source") == "ide-log"]
    importcmd.run(proj, "kiro", args)
    twice = [r for r in ledger.kiro_metrics(sink) if r.get("source") == "ide-log"]
    assert [r["id"] for r in once] == [r["id"] for r in twice]


def test_exactly_one_of_the_two_ide_grains_is_manifest_eligible(proj):
    """`ide` (devdata.sqlite) and `ide-log` (tokens_generated.jsonl) are the SAME counter
    from Kiro's two IDE stores. Listing both in `_MANIFEST_SOURCES` would count one
    install's IDE traffic twice the day `devdata.sqlite` finally ships — the `copilot`
    `cli`/`cli-delta` hazard, one store later. Pinned as a rule rather than as today's
    value so flipping the pair stays legal and adding to it does not."""
    both = {"ide", "ide-log"}
    listed = both & set(importcmd._MANIFEST_SOURCES["kiro"])
    assert len(listed) == 1, f"exactly one of {both} may be manifest-eligible, got {listed}"
    assert both <= set(schema.KIRO_METRIC_SOURCES), "both grains must remain writable"


# ── the knock-ons P5 had to carry with it ───────────────────────────────────────

def test_gate_three_still_sees_a_healthy_install(proj, tmp_path):
    """`captured_surfaces` is "has this agent EVER captured?". Left reading `calls` it
    would be empty for claude and copilot on a perfectly healthy install, and every
    surface built on it would report *never captured* — a silent false negative."""
    tp = tmp_path / "session.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    importcmd.run(proj, "claude", SimpleNamespace(path=str(tp), project=None, since=None))
    assert "claude" in ledger.captured_surfaces(proj)


def test_the_capture_manifest_still_gets_a_row(proj, tmp_path):
    """`_write_manifest` returns early on an empty `collected`, and `collected` was filled
    only by the retired leg. Left alone, P5 would have stopped writing the manifest — and
    its one consumer is the chat-title map, so **every new chat would silently lose its
    name**. Nothing would have failed."""
    from cage import manifest
    tp = tmp_path / "session.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    importcmd.run(proj, "claude", SimpleNamespace(path=str(tp), project=None, since=None))
    rows = [r for r in manifest.read(proj) if r.get("kind") == "import"]
    assert rows, "the capture manifest stopped being written"
    assert rows[0]["session"] == "session"
    assert rows[0]["import_id"], "the manifest FK must still be threaded onto the rows"


def test_the_cursor_still_advances(proj, tmp_path):
    """`_ingest_claude_metrics` had no cursor of its own — it rode the retired leg's. A
    missing advance is not a correctness bug (id-dedupe covers it) and never fails: every
    sweep just silently re-reads every transcript forever."""
    tp = tmp_path / "session.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    importcmd.run(proj, "claude", SimpleNamespace(path=str(tp), project=None, since=None))
    cur = paths.Footprint(proj).state / "cursors.json"
    assert cur.exists() and json.loads(cur.read_text(encoding="utf-8")).get("claude")
