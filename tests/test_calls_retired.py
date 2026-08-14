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
  4. **Kiro is the stated exception** — it keeps its writer. See the module note below.

**Kiro, and why it deviates from the spec.** For claude and copilot the retired leg was a
*duplicate*: `ledger/claude/` and `ledger/copilot/` hold the same traffic. Kiro IDE has no
metric twin — `parse_kiro_ide_metrics` reads `devdata.sqlite`, absent on every install ever
probed — so its `calls` leg is the ONLY reader of `tokens_generated.jsonl`. Removing it
would not de-duplicate kiro; it would end kiro IDE capture, take ADR-KIRO's routing
decision's subject matter with it, and leave the upgrade-watch without a baseline. The
handoff's reason (the rows are unsummable) is already handled by `ABSENT_SPINES`, which
keeps them out of every total. Kept as the smaller reversible choice and flagged for
Arpit — deleting `import_kiro`'s five-line leg implements the spec as written.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cage import importcmd, ledger, metering, paths, transcript
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
    adr = (Path(__file__).resolve().parents[1] / "docs" / "adr" / "0006_consumer.md")
    text = adr.read_text(encoding="utf-8").lower()
    assert "claude-dedup" in text
    assert 'format = "claude"' in text or "format = `claude`" in text


# ── 4 · kiro, the stated exception ──────────────────────────────────────────────

def test_kiro_keeps_its_calls_writer(proj, tmp_path):
    """The deviation, pinned so it is a decision rather than an oversight — and so that
    implementing the spec as written is a deliberate act that turns this test red."""
    log = tmp_path / "tokens_generated.jsonl"
    log.write_text(json.dumps({"model": "agent", "provider": "kiro",
                               "promptTokens": 1200, "generatedTokens": 0}) + "\n",
                   encoding="utf-8")
    importcmd.run(proj, "kiro", SimpleNamespace(path=str(log), project=None, since=None))
    sink = paths.kiro_routed(proj) or proj
    rows = [c for c in ledger.calls(sink) if c.get("agent") == "kiro"]
    assert rows, "kiro IDE has no metric twin — retiring this leg ends its capture"
    assert rows[0]["tokens_in"] == 1200


def test_kiro_rows_still_never_reach_a_token_total(proj, tmp_path):
    """And the reason keeping them is cheap: `ABSENT_SPINES` already excludes them from
    every total, so they cost nothing and render `—` with a stated reason — never a 0."""
    log = tmp_path / "tokens_generated.jsonl"
    log.write_text(json.dumps({"model": "agent", "provider": "kiro",
                               "promptTokens": 1200, "generatedTokens": 0}) + "\n",
                   encoding="utf-8")
    importcmd.run(proj, "kiro", SimpleNamespace(path=str(log), project=None, since=None))
    sink = paths.kiro_routed(proj) or proj
    assert [r for r in ledger.spend(sink) if r.get("agent") == "kiro"] == []
    from cage import units
    assert units.absent_reason("kiro", units.TOKENS)


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
