"""Tests for tools/docgen — the build-time doc/comment generators (plan §5.6).

docgen is build-time only (never imported by the cage package at runtime); these
tests guard the drift gates it exists to provide: the spec's code blocks equal
the golden fixtures, the formulas catalogue equals the explain registry, the
bundled policy.toml formula comments equal the same registry, every calculation
entry is catalogued, every golden fixture is documented, regeneration is
byte-deterministic, and nothing under tools/ ships in the wheel.
"""
from __future__ import annotations

from tools.docgen import gen


def test_spec_matches_goldens():
    assert gen.gen_spec() == gen.SPEC.read_text(encoding="utf-8")


def test_formulas_match_registry():
    assert gen.gen_formulas() == gen.FORMULAS.read_text(encoding="utf-8")


def test_policy_comments_match_registry():
    assert gen.gen_policy() == gen.POLICY.read_text(encoding="utf-8")


def test_regeneration_is_deterministic():
    assert gen.gen_spec() == gen.gen_spec()
    assert gen.gen_formulas() == gen.gen_formulas()
    assert gen.gen_policy() == gen.gen_policy()


def test_every_calculation_entry_is_catalogued():
    """A new calculation entry without an anchored formulas.md block must fail
    the gate (gen_formulas raises SystemExit naming the id) — the CLAUDE.md
    'catalogue in the same change' rule, made mechanical."""
    reg, _ = gen._registry()
    calc = {e.id for e in reg.values() if e.kind == "calculation"}
    anchored = gen._anchored(gen.FORMULAS.read_text(encoding="utf-8"),
                             gen.FORMULA_ANCHOR)
    assert calc <= anchored


def test_every_golden_fixture_is_documented():
    anchored = gen._anchored(gen.SPEC.read_text(encoding="utf-8"),
                             gen.GOLDEN_ANCHOR)
    fixtures = {f.stem for f in gen.GOLDENS.glob("*.txt")}
    assert fixtures <= anchored


def test_docgen_never_ships_in_wheel():
    """Same rule (and same filter) as skillgen: the wheel discovers `cage*` only,
    so the tools/ namespace — docgen included — is repo-only, never shipped."""
    import pytest
    find_packages = pytest.importorskip("setuptools").find_packages
    discovered = find_packages(where=str(gen.REPO), include=["cage*"])
    assert not any(p == "tools" or p.startswith("tools.") for p in discovered)
    assert (gen.REPO / "tools" / "docgen" / "gen.py").exists()
