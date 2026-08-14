"""`docs/FORMULAS.md` §2.7's graphify coverage matrix, re-derived from the code.

**A two-strikes gate** (house rule: a failure class the WORKLOG records twice becomes a
mechanical gate in the same change that records the second occurrence).

The drift: `graphifytx.GRAPHIFY_COVERAGE` gained the copilot-VS-Code and kiro-CLI routes
in **v0.47.0**, and §2.7 went on calling copilot VS Code *"usage-row-only"* and kiro
*"HONEST-LIMIT"* for three releases. ADR-COVERAGE's own veto condition says that class of
drift is *"caught by review alone"* — review missed it twice, so it stops being caught by
review.

**What this binds, and what it deliberately does not.** It asserts the *shape* of the
claim — every surface named, and each one's ✅/❌ verdict matching the table — never the
prose. The `why` column is human writing and must stay free to be written well; the
falsifiable half is *which surfaces can file a receipt*, which is exactly what went stale.

Scope note: this is the same detector as `test_cli_reference.py` (a doc gated against
live code) pointed at the one matrix that has now rotted twice.
"""
from __future__ import annotations

import re
from pathlib import Path

from cage.graphifytx import GRAPHIFY_COVERAGE

FORMULAS = Path(__file__).resolve().parents[1] / "docs" / "FORMULAS.md"


def _doc_matrix() -> dict[str, bool]:
    """`{"agent/surface": files_receipts}` parsed from §2.7's markdown table."""
    text = FORMULAS.read_text(encoding="utf-8")
    start = text.index("### 2.7 ")
    body = text[start:text.index("### 2.8 ", start)]
    out: dict[str, bool] = {}
    # `^\s*` — the table is indented inside a bullet, so an anchored `^\|` silently
    # matches nothing and every assertion below passes over an EMPTY dict. That is the
    # vacuous-gate failure this repo has already paid for once with the fenced diagrams;
    # `test_the_parse_is_not_vacuous` below is the backstop.
    # `N/A` is accepted beside `✅`/`❌` because ADR-COVERAGE's legend split the old
    # single cross into N/A (*nothing to build*) and ❌ (*buildable, unbuilt*), and every
    # False row in `GRAPHIFY_COVERAGE` is the first kind. The gate binds the VERDICT
    # (can this surface file a receipt?), never which of the two absence marks the doc
    # spells it with — a doc that switched marks should not fail a coverage test.
    for row in re.finditer(r"^\s*\|\s*([a-z]+)\s+([a-z+]+)\s*\|\s*(✅|❌|N/A)\s*\|", body, re.M):
        agent, surface, tick = row.groups()
        out[f"{agent}/{surface}"] = tick == "✅"
    return out


def _code_matrix() -> dict[str, bool]:
    return {f"{agent}/{surface}": ok for agent, surface, ok, _ in GRAPHIFY_COVERAGE}


def test_the_parse_is_not_vacuous():
    """The gate's own gate. A markdown parse that matches nothing makes every equality
    below trivially true — a green test covering nothing, which is worse than no test
    because it reads as coverage. (It happened on the first run of this very file: the
    table is indented inside a bullet, so an `^\\|` anchor matched zero rows.)"""
    assert len(_doc_matrix()) == len(GRAPHIFY_COVERAGE) >= 5


def test_formulas_names_every_surface_the_code_knows():
    """A surface missing from the doc is the failure mode that actually happened: the two
    routes that shipped in v0.47.0 were simply never added, so the paragraph stayed
    self-consistent while being wrong."""
    assert set(_doc_matrix()) == set(_code_matrix())


def test_every_verdict_matches_the_code():
    """Can-file / cannot-file per surface. This is the falsifiable half — a cannot-file
    printed for a route that has worked for three releases understates cage's own
    coverage, and a ✅ for one that cannot file would be the worse direction: a promised
    receipt that never lands."""
    assert _doc_matrix() == _code_matrix()


def test_the_one_structural_refusal_is_still_stated_as_a_refusal():
    """kiro-IDE cannot file from its store — measured, 26/26 empty completions — and the
    doc must keep saying so. A refusal quietly upgraded to ✅ is how a stated limit turns
    into a silent zero, which is the one thing cage never renders."""
    assert _doc_matrix()["kiro/ide"] is False
    body = FORMULAS.read_text(encoding="utf-8")
    assert "interceptor is the only route here" in body.lower()
