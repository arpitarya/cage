"""P0 fixture corpus — every agent × surface log, parsed to exact rows.

Each `tests/fixtures/transcripts/<agent>/<surface>/` dir carries a sanitized session-log
sample in the agent's real on-disk shape plus `expected.json` (the exact call rows + plant
metadata — see the corpus README).

**Split in two by P5 (v0.51), and NOT regenerated.** The built-in import path no longer
writes `calls` rows for the three agents, so a single "import then compare to
expected.json" test could only have been made green by blessing whatever the new code
produced — which would have thrown away the evidence this corpus exists to be. The
parsers themselves did not change: they are kept, reachable through `importcmd._PARSERS`,
as the `[sources.<name>] format = "..."` custom-source contract (decision 10.1). So:

  * :func:`test_the_parsers_still_produce_exact_rows` keeps the byte-for-byte assertion,
    calling the parsers **directly** through `_PARSERS`. `expected.json` is untouched, and
    this is now also the only test that exercises the custom-source route end to end.
  * :func:`test_import_captures_the_same_facts` runs the real pathless `cage import` and
    asserts the **facts survive the basis change** — same token totals, in the ledger the
    agent captures into.

Verified when the split was made: claude and copilot token totals are **identical** before
and after P5. Only the row *grain* moved (copilot CLI: 2 call rows → 1 `cli-delta` row).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from cage import agents, clicmds, ledger, paths
from srcseed import mkcage

CORPUS = Path(__file__).parent / "fixtures" / "transcripts"
SURFACES_TESTED = ("cli", "vscode")
FIXTURES = sorted(p.parent.relative_to(CORPUS) for p in CORPUS.glob("*/*/expected.json"))


def _load(fixture: Path) -> dict:
    return json.loads((CORPUS / fixture / "expected.json").read_text(encoding="utf-8"))


def _plant(fixture: Path, spec: dict, home: Path) -> None:
    dst = home / spec["plant"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CORPUS / fixture / spec["log"], dst)
    # Sidecars: files a store keeps BESIDE the log that the parser also reads — VS Code's
    # `workspaceStorage/<hash>/workspace.json`, which is the only carrier that names the
    # project for every request in a chat. Planted at their real relative layout, because
    # the parser deliberately checks that layout before trusting the file.
    for rel, src in (spec.get("sidecars") or {}).items():
        side = home / rel
        side.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CORPUS / fixture / src, side)


def _isolated_root(d, monkeypatch):
    mkcage(d)
    # Isolate every agent home so the default (pathless) scan never reads real machine data.
    for env in ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_DATA_DIR",
                "CAGE_VSCODE_USER"):
        monkeypatch.setenv(env, str(d / f"home-{env.lower()}"))
    monkeypatch.delenv("CAGE_CAPTURE", raising=False)
    monkeypatch.chdir(d)
    return d


def _comparable(rows: list[dict], volatile: list[str]) -> list[dict]:
    out = []
    for r in rows:
        r = dict(r)
        for v in volatile:
            assert r.pop(v), f"volatile field {v!r} missing/empty on {r.get('id')}"
        # `import_id` is the per-sweep capture-manifest FK (plan §4) — a fresh random id
        # each import run, so it is non-deterministic by nature (like `ts`) and stripped
        # before the exact-row comparison. Its presence is asserted separately.
        r.pop("import_id", None)
        out.append(r)
    return sorted(out, key=lambda r: r["id"])


def test_corpus_covers_every_agent_and_surface():
    # The three-agent invariant, structurally: a missing fixture dir is a failure,
    # never a silently narrower parametrization.
    want = {Path(a) / s for a in agents.SURFACES for s in SURFACES_TESTED}
    assert set(FIXTURES) == want


@pytest.mark.parametrize("fixture", FIXTURES, ids=[str(f) for f in FIXTURES])
def test_the_parsers_still_produce_exact_rows(fixture, tmp_path, monkeypatch):
    """The corpus's original assertion, kept intact and pointed at the parsers.

    P5 removed the built-in transcript→`calls` legs; it did **not** remove the parsers.
    They survive as the `[sources.<name>] format = "claude"|"copilot"|"kiro"` contract
    (10.1) — deleting them would break user config silently — so `expected.json` is still
    exactly what they must produce, and this test is now the thing that keeps that promise.

    ⚠ **A custom source declaring `format = "claude"` inherits CLAUDE-DEDUP and
    CLAUDE-SUBAGENT-KEY** (its rows are ~1.98× inflated and subagent spend is mis-keyed).
    That is recorded in ADR-CONSUMERS rather than fixed here: ADR-CLAUDE forbids "fixing"
    these parsers on the way out — the 2.00× measurement has to outlive the code."""
    from cage import importcmd
    agent = fixture.parts[0]
    spec = _load(fixture)
    root = _isolated_root(tmp_path, monkeypatch)
    home = tmp_path / f"home-{spec['env'].lower()}"
    _plant(fixture, spec, home)

    log = home / spec["plant"]
    rows = importcmd._PARSERS[agent](log)
    actual = _comparable(rows, spec["volatile"])
    expected = sorted(spec["rows"], key=lambda r: r["id"])
    assert actual == expected  # exact rows: ids, tokens, provider/model, session, project


@pytest.mark.parametrize("fixture", FIXTURES, ids=[str(f) for f in FIXTURES])
def test_import_captures_the_same_facts(fixture, tmp_path, monkeypatch):
    """The new built-in path, asserted on the **facts** rather than the row shape.

    Rows land in the ledger the agent captures INTO — `root` for claude/copilot, the
    machine ledger for kiro (ADR 0006). Routing moves *where* rows land, never *what* is
    parsed.

    Token totals are the invariant: they were identical before and after P5 for claude and
    copilot. The row *count* is deliberately not asserted — the grain legitimately changed
    (copilot CLI: 2 call rows → 1 `cli-delta` row covering the same session), and pinning a
    count would have been pinning the grain rather than the fact.

    **⚠ Kiro asserts a LOSS, and it is the sharpest consequence of P5.** For claude and
    copilot the retired leg was a *duplicate* — the metric ledger carries the same facts.
    Kiro IDE has **no metric twin**: `parse_kiro_ide_metrics` reads `devdata.sqlite`, which
    is absent on every install probed, so the retired `calls` leg was the **only** reader
    of `tokens_generated.jsonl`. After P5 the Kiro IDE log is read by nothing.

    That was the decision (the 2026-08-14 field probe: 28 rows, 1,576 in / **0 out**,
    model `"agent"` on every row, one byte-identical 6-row block repeated — unsummable, and
    already excluded from every total by `ABSENT_SPINES`). It is asserted here **with its
    reason** so nobody restores the leg by accident while reading a green suite, and it is
    filed as `KIRO-IDE-CAPTURE-STOPPED` — stopping a writer needs its own justification,
    its own ADR update and its own queue line, per the SURFACE-CUT rule."""
    agent = fixture.parts[0]
    spec = _load(fixture)
    root = _isolated_root(tmp_path, monkeypatch)
    _plant(fixture, spec, tmp_path / f"home-{spec['env'].lower()}")

    args = SimpleNamespace(agent=agent, path=None, project=None, since=None)
    assert clicmds.cmd_import(args) == 0
    sink = (paths.kiro_routed(root) or root) if agent == "kiro" else root

    want_in = sum(r.get("tokens_in", 0) for r in spec["rows"])
    want_out = sum(r.get("tokens_out", 0) for r in spec["rows"])
    if agent == "kiro":
        assert ledger.spend(sink) == [], "kiro has no token spine — never a fabricated 0"
        # …and its rows are in `calls`, because **kiro keeps its writer** (the one P5
        # deviation, see `importcmd.import_kiro`): it has no metric twin, so retiring the
        # leg would have ended kiro IDE capture rather than de-duplicating it.
        got = ledger.calls(sink)
        assert sum(r.get("tokens_in", 0) for r in got) == want_in
        assert sum(r.get("tokens_out", 0) for r in got) == want_out
    else:
        got = ledger.spend(sink)
        assert got, "capture produced nothing"
        assert sum(r.get("tokens_in", 0) for r in got) == want_in
        assert sum(r.get("tokens_out", 0) for r in got) == want_out

    # No `calls` row is written for claude or copilot any more (P5). Kiro is the stated
    # exception above — asserting `== []` for all three would have quietly encoded the
    # spec-as-written rather than the code as it is.
    if agent != "kiro":
        assert ledger.calls(sink) == []

    # Idempotency: a re-import (cursor + id-dedupe) leaves every shard byte-identical.
    def snapshot():
        base = paths.Footprint(sink).ledger
        return {p.relative_to(base).as_posix(): p.read_bytes()
                for p in sorted(base.rglob("*.jsonl"))}
    before = snapshot()
    assert before, "nothing was written — the idempotency check would be vacuous"
    assert clicmds.cmd_import(args) == 0
    assert snapshot() == before


def test_unverified_stand_ins_are_flagged_not_silent():
    # The three VS Code stand-ins (handoff §10) must say so in expected.json and the
    # README — an invented format masquerading as verified is worse than a gap.
    readme = (CORPUS / "README.md").read_text(encoding="utf-8")
    for fixture in FIXTURES:
        spec = _load(fixture)
        if not spec["format_verified"]:
            assert fixture.parts[1] == "vscode"  # only extension formats may be stand-ins
            assert "UNVERIFIED-FORMAT" in readme
    verified = {f.as_posix() for f in FIXTURES if _load(f)["format_verified"]}
    # Every CLI format is pinned against a real client log. (as_posix: `str(Path)`
    # renders `claude\cli` on Windows and the comparison keys must be OS-independent.)
    assert {f"{a}/cli" for a in agents.SURFACES} <= verified
