"""Tests for tools/skillgen — the build-time renderer for cage's skill assets.

skillgen is build-time only (never imported by the cage package at runtime), so
these tests import it directly from the repo's ``tools`` namespace. They guard the
invariants the renderer exists to protect: byte-determinism, the four-agents
product invariant, the per-host anchor lines (frontmatter/commands/PII claim), no
unfilled slots, that --check passes clean and fails on drift, and that nothing
under tools/skillgen/ ships in the wheel.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tools.skillgen import gen

# The four sacred agents (agents.SURFACES) plus the generic `agents` target.
SACRED = ("claude", "codex", "copilot", "kiro")
ALL_HOSTS = SACRED + ("agents",)

REPO_ROOT = gen.REPO_ROOT


@pytest.fixture(scope="module")
def platforms():
    return gen.load_platforms()


def test_all_hosts_present_four_sacred_plus_agents(platforms):
    """All five hosts parse; the four sacred agents are never dropped."""
    for key in ALL_HOSTS:
        assert key in platforms, f"missing platform '{key}'"
    for key in SACRED:
        assert key in platforms, f"four-agents invariant broken: '{key}' missing"


def test_every_host_renders(platforms):
    for key in ALL_HOSTS:
        arts = gen.render(platforms[key])
        assert len(arts) == 1
        assert arts[0].content.strip(), f"{key} rendered empty"


def test_render_is_deterministic(platforms):
    """Same fragments => byte-identical render (no clocks/random)."""
    first = gen.render_all(platforms)
    second = gen.render_all(platforms)
    assert [(a.path, a.content) for a in first] == [(b.path, b.content) for b in second]


def test_render_all_dedupes_shared_path(platforms):
    """claude and codex share one file and must render byte-identical; the full
    render therefore yields 4 unique files, not 5."""
    arts = gen.render_all(platforms)
    paths = [a.path for a in arts]
    assert len(paths) == len(set(paths)) == 4
    claude = gen.render(platforms["claude"])[0]
    codex = gen.render(platforms["codex"])[0]
    assert claude.path == codex.path == "cage/data/skills/cage/SKILL.md"
    assert claude.content == codex.content


def test_render_all_raises_on_shared_path_drift(platforms):
    """If two hosts target one path with different content, render_all raises
    rather than silently picking one (the shared-path guard)."""
    drifted = dict(platforms)
    drifted["codex"] = replace(platforms["codex"], header="# divergent header")
    with pytest.raises(ValueError, match="conflicting content to the same path"):
        gen.render_all(drifted)


def test_no_unfilled_slots(platforms):
    for art in gen.render_all(platforms):
        assert "@@" not in art.content, f"unfilled slot in {art.path}"


def test_unfilled_slot_raises(platforms):
    """A core slot the renderer can't fill must raise with the leftover name."""
    bogus = replace(platforms["claude"], header="keep @@MYSTERY@@ slot")
    with pytest.raises(ValueError, match="@@MYSTERY@@"):
        gen.render(bogus)


@pytest.mark.parametrize("key", ALL_HOSTS)
def test_anchor_lines_per_host(platforms, key):
    """Each host retains cage's non-negotiable lines: the command references and
    the counts-never-content / PII-safe claim."""
    body = gen.render(platforms[key])[0].content
    for cmd in ("cage report", "cage attrib", "cage budget", "cage matrix", "cage roi"):
        assert cmd in body, f"{key} dropped command anchor {cmd!r}"
    assert "counts" in body and "never prompt bodies" in body, f"{key} dropped the PII claim"
    assert "PII-safe" in body, f"{key} dropped the PII-safe claim"


@pytest.mark.parametrize("key", ALL_HOSTS)
def test_frontmatter_and_description_verbatim(platforms, key):
    """Frontmatter shape matches the host kind and the description is verbatim."""
    p = platforms[key]
    body = gen.render(p)[0].content
    assert body.startswith("---\n"), f"{key} missing frontmatter open"
    if p.kind == "steering":
        assert "inclusion: always" in body
    else:
        assert p.description is not None
        assert f"description: {p.description}" in body, f"{key} description not verbatim"
    if p.kind == "skill":
        assert f"name: {p.name}" in body


def test_check_clean_after_bless(platforms):
    """The committed + blessed state must be clean (this is what CI runs)."""
    assert gen.check(gen.render_all(platforms)) == []
    assert gen.main(["--check"]) == 0


def test_check_flags_drift(platforms, tmp_path, monkeypatch):
    """check() reports drift when a rendered artifact diverges from disk, and
    main(--check) exits 1."""
    real = gen.render_all(platforms)
    mutated = [replace(real[0], content=real[0].content + "\nDRIFT\n")] + real[1:]
    problems = gen.check(mutated)
    assert any("out of date" in m for m in problems)

    monkeypatch.setattr(gen, "render_all", lambda *a, **k: mutated)
    assert gen.main(["--check"]) == 1


def test_editing_core_updates_every_host(platforms, tmp_path, monkeypatch):
    """One edit to core.md propagates to every host in a single render (the whole
    point of single-sourcing)."""
    core = (gen.FRAGMENTS_DIR / "core" / "core.md").read_text()
    sentinel = "ZZ_SENTINEL_LINE_ZZ"
    patched = core.replace("Every command takes", f"{sentinel}\n\nEvery command takes")
    monkeypatch.setattr(gen, "_read_fragment", _patched_reader("core/core.md", patched))
    for key in ALL_HOSTS:
        assert sentinel in gen.render(platforms[key])[0].content


def _patched_reader(target_rel, patched_text):
    real_read = gen._read_fragment

    def reader(rel):
        if rel == target_rel:
            return gen._normalise(patched_text)
        return real_read(rel)

    return reader


def test_skillgen_not_imported_by_cage_runtime():
    """No cage runtime module may import tools.skillgen."""
    import cage

    pkg_dir = Path(cage.__file__).resolve().parent
    offenders = []
    for py in pkg_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "tools.skillgen" in text or "import skillgen" in text:
            offenders.append(str(py.relative_to(pkg_dir)))
    assert offenders == [], f"cage runtime imports skillgen: {offenders}"


def test_wheel_excludes_skillgen():
    """The wheel is built from `[tool.setuptools.packages.find] include=["cage*"]`,
    so no `tools` package is ever discovered/shipped. This tests that exact filter
    (deterministic; the full `python -m build` content inspection is the manual
    §9 verify step). The rendered agents asset, by contrast, IS shipped — it lives
    under cage/data and is covered by the `data/skills/**/*` package-data glob."""
    from setuptools import find_packages

    discovered = find_packages(where=str(REPO_ROOT), include=["cage*"])
    assert not any(p == "tools" or p.startswith("tools.") for p in discovered), \
        f"wheel would ship tools/: {[p for p in discovered if p.startswith('tools')]}"
    assert "cage" in discovered, "sanity: cage package should be discovered"

    # The skillgen tree exists but is outside any shipped package.
    assert (gen.SKILLGEN_DIR / "gen.py").exists()

    # The new agents asset is rendered and committed under the shipped data tree.
    agents_skill = REPO_ROOT / "cage" / "data" / "skills" / "agents" / "cage" / "SKILL.md"
    assert agents_skill.exists(), "rendered agents skill asset is missing from cage/data"
