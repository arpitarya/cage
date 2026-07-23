"""skillgen: render cage's committed skill/prompt/steering assets from fragments.

Build-time only. Nothing under ``tools/skillgen/`` ships in the wheel or is ever
imported by the ``cage`` package at runtime. The fragments under
``tools/skillgen/fragments/`` are the single source of truth a human edits; the
rendered files under ``cage/data/skills/``, ``cage/data/prompts/`` and
``cage/data/steering/`` are generated, committed artifacts. This module renders
those artifacts and guards them against drift.

cage ships the flagship ``cage`` skill four ways — a Claude/Codex slash-command
SKILL.md, a Copilot ``.prompt.md``, and a Kiro steering doc — plus a generic
``agents`` (Agent Skills) target. They are the *same* pitch wrapped differently;
hand-maintaining four files lets the wording drift. skillgen single-sources the
shared body in ``fragments/core/core.md`` and fills a handful of per-host slots
(frontmatter, header, intro framing, metering note) from ``platforms.toml``.

Usage (from the repo root)::

    python -m tools.skillgen                 # render every host's asset
    python -m tools.skillgen --platform claude
    python -m tools.skillgen --check         # byte-diff render vs committed + expected/, exit 1 on drift
    python -m tools.skillgen --bless         # rewrite expected/ from the current render

The render is deterministic: per-host slots are filled in a fixed order, output is
LF-newline with one trailing newline, and no clock/version/random value is ever
written into a generated file ($0, stdlib-only, like the rest of cage).
"""
from __future__ import annotations

import argparse
import re
import sys
import tomllib  # Python 3.11+ stdlib (cage requires >=3.11)
from dataclasses import dataclass
from pathlib import Path

# tools/skillgen/gen.py -> repo root is two parents up.
SKILLGEN_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLGEN_DIR.parent.parent
FRAGMENTS_DIR = SKILLGEN_DIR / "fragments"
EXPECTED_DIR = SKILLGEN_DIR / "expected"
PLATFORMS_TOML = SKILLGEN_DIR / "platforms.toml"

# The frontmatter shape per host kind. `skill` carries name+description (Agent
# Skills spec); `prompt` carries description only (Copilot); `steering` is the
# always-on Kiro doc with no description field.
_SKILL_KINDS = frozenset({"skill", "prompt", "steering"})


@dataclass(frozen=True)
class Platform:
    """One render unit parsed from platforms.toml."""

    key: str
    kind: str          # skill | prompt | steering
    skill_dst: str     # rendered file path, relative to REPO_ROOT
    header: str        # the H1 line
    intro: str         # intro fragment basename under fragments/intro/
    meter: str         # metering-note fragment basename under fragments/meter/
    name: str = "cage"
    description: str | None = None  # PRESERVED VERBATIM; required for skill/prompt


def load_platforms() -> dict[str, Platform]:
    """Parse platforms.toml into Platform records, keyed by platform name."""
    data = tomllib.loads(PLATFORMS_TOML.read_text(encoding="utf-8"))
    out: dict[str, Platform] = {}
    for key, cfg in data.get("platform", {}).items():
        kind = cfg["kind"]
        if kind not in _SKILL_KINDS:
            raise ValueError(f"platform '{key}': unknown kind '{kind}'")
        out[key] = Platform(
            key=key,
            kind=kind,
            skill_dst=cfg["skill_dst"],
            header=cfg["header"],
            intro=cfg["intro"],
            meter=cfg["meter"],
            name=cfg.get("name", "cage"),
            description=cfg.get("description"),
        )
    return out


def _normalise(text: str) -> str:
    """Force LF newlines and exactly one trailing newline."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip("\n") + "\n"


def _read_fragment(rel: str) -> str:
    """Read a fragment file under fragments/, normalised to LF newlines."""
    return _normalise((FRAGMENTS_DIR / rel).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class RenderedArtifact:
    """A single generated file: its repo-relative path and exact bytes."""

    path: str  # relative to REPO_ROOT
    content: str


def _render_frontmatter(platform: Platform) -> str:
    """Render the YAML frontmatter for this host's kind.

    skill   -> name + description (Agent Skills spec).
    prompt  -> description only (Copilot reusable prompt).
    steering-> ``inclusion: always`` (Kiro always-on doc).

    The description is preserved verbatim from platforms.toml — never invented.
    """
    if platform.kind == "steering":
        return "---\ninclusion: always\n---"
    if platform.description is None:
        raise ValueError(f"platform '{platform.key}' ({platform.kind}) is missing a description")
    lines = ["---"]
    if platform.kind == "skill":
        lines.append(f"name: {platform.name}")
    lines.append(f"description: {platform.description}")
    lines.append("---")
    return "\n".join(lines)


def _render_core(platform: Platform) -> str:
    """Fill the shared core template's per-host slots for this platform."""
    template = _read_fragment("core/core.md")
    body = (
        template.replace("@@FRONTMATTER@@", _render_frontmatter(platform))
        .replace("@@HEADER@@", platform.header)
        .replace("@@INTRO@@", _read_fragment(f"intro/{platform.intro}.md").rstrip("\n"))
        .replace("@@METER@@", _read_fragment(f"meter/{platform.meter}.md").rstrip("\n"))
    )
    if "@@" in body:
        leftover = sorted(set(re.findall(r"@@\w+@@", body)))
        raise ValueError(f"unfilled core slots for '{platform.key}': {leftover}")
    return _normalise(body)


def render(platform: Platform) -> list[RenderedArtifact]:
    """Render the committed artifact(s) for one platform (cage: exactly one)."""
    return [RenderedArtifact(platform.skill_dst, _render_core(platform))]


def render_all(platforms: dict[str, Platform], only: str | None = None) -> list[RenderedArtifact]:
    """Render the selected platforms (or all), deduped by output path.

    Two platforms rendering to the same output path must be byte-identical —
    the collision is the guard against per-host slots silently drifting apart.
    """
    keys = [only] if only else sorted(platforms)
    by_path: dict[str, RenderedArtifact] = {}
    order: list[str] = []
    for key in keys:
        if key not in platforms:
            raise SystemExit(
                f"error: unknown platform '{key}'. Known: {', '.join(sorted(platforms))}"
            )
        for art in render(platforms[key]):
            prior = by_path.get(art.path)
            if prior is None:
                by_path[art.path] = art
                order.append(art.path)
            elif prior.content != art.content:
                raise ValueError(
                    f"platforms render conflicting content to the same path '{art.path}' "
                    f"(one is '{key}'); shared-path hosts must be byte-identical"
                )
    return [by_path[p] for p in order]


def write_artifacts(artifacts: list[RenderedArtifact]) -> list[str]:
    """Write artifacts to disk under REPO_ROOT. Returns the paths written."""
    written: list[str] = []
    for art in artifacts:
        dst = REPO_ROOT / art.path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(art.content, encoding="utf-8", newline="\n")
        written.append(art.path)
    return written


def _expected_path(rel: str) -> Path:
    """Map a repo-relative artifact path to its expected/ snapshot path.

    The artifact path is flattened (``/`` -> ``__``) into a single filename so the
    snapshot tree stays flat and fully tracked (no ``skills/`` path component a
    .gitignore might swallow).
    """
    return EXPECTED_DIR / rel.replace("/", "__")


def bless(artifacts: list[RenderedArtifact]) -> list[str]:
    """Write the current render into expected/ as the blessed snapshot."""
    written: list[str] = []
    for art in artifacts:
        dst = _expected_path(art.path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(art.content, encoding="utf-8", newline="\n")
        written.append(str(dst.relative_to(SKILLGEN_DIR)))
    return written


def check(artifacts: list[RenderedArtifact]) -> list[str]:
    """Byte-diff the render against both committed artifacts and expected/.

    Returns human-readable drift messages; empty means clean. This is the
    anti-drift guard wired into CI and pre-commit: any hand-edit of a generated
    file, or a stale expected/ snapshot, is caught here.
    """
    problems: list[str] = []
    for art in artifacts:
        committed = REPO_ROOT / art.path
        if not committed.exists():
            problems.append(f"missing committed artifact: {art.path} (run: python -m tools.skillgen)")
        elif committed.read_text(encoding="utf-8") != art.content:
            problems.append(f"committed artifact out of date: {art.path} (run: python -m tools.skillgen)")

        snapshot = _expected_path(art.path)
        if not snapshot.exists():
            problems.append(f"missing expected/ snapshot: {art.path} (run: python -m tools.skillgen --bless)")
        elif snapshot.read_text(encoding="utf-8") != art.content:
            problems.append(f"expected/ snapshot out of date: {art.path} (run: python -m tools.skillgen --bless)")
    return problems


def headings(markdown: str) -> list[str]:
    """Return the ATX markdown headings in source order, ignoring code fences.

    A ``#``-prefixed line inside a fenced code block is a shell comment, not a
    heading, so fence state is tracked to avoid counting it.
    """
    out: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in markdown.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence, fence_marker = False, ""
            continue
        if in_fence:
            continue
        if stripped.startswith("#"):
            hashes = len(stripped) - len(stripped.lstrip("#"))
            if 1 <= hashes <= 6 and stripped[hashes:hashes + 1] == " ":
                out.append(stripped.strip())
    return out


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m tools.skillgen",
        description="Render and guard cage's committed skill/prompt/steering assets.",
    )
    p.add_argument("--platform", help="render or check just this platform key")
    p.add_argument("--check", action="store_true",
                   help="byte-diff render vs committed + expected/, exit 1 on drift")
    p.add_argument("--bless", action="store_true",
                   help="rewrite expected/ from the current render")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    platforms = load_platforms()
    artifacts = render_all(platforms, only=args.platform)

    if args.check:
        problems = check(artifacts)
        if problems:
            print("check FAILED (skill assets have drifted):", file=sys.stderr)
            for m in problems:
                print(f"  {m}", file=sys.stderr)
            return 1
        print(f"check OK: {len(artifacts)} artifact(s) match committed output and expected/.")
        return 0

    if args.bless:
        written = bless(artifacts)
        print(f"blessed {len(written)} artifact(s) into expected/.")
        return 0

    written = write_artifacts(artifacts)
    print(f"rendered {len(written)} artifact(s):")
    for path in written:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
