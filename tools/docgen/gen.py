"""The docgen engine — see the package docstring for the three targets."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs" / "cli-output-spec.md"
FORMULAS = REPO / "docs" / "formulas.md"
POLICY = REPO / "cage" / "data" / "policy.toml"
GOLDENS = REPO / "tests" / "fixtures" / "goldens"

GOLDEN_ANCHOR = re.compile(r"<!--\s*golden:\s*([A-Za-z0-9_-]+)\s*-->")
FORMULA_ANCHOR = re.compile(r"<!--\s*formula:\s*([a-z0-9-]+)\s*-->")

# Which bundled-policy tables carry a `# formula:` comment line, and from which
# registry entry the one-line formula comes (its first line, interpolated).
POLICY_FORMULA_MAP = (
    ("[budgets]", "budget"),
    ("[human]", "human-cost"),
    ("[human.confidence]", "confidence"),
)


def _replace_anchored_blocks(text: str, anchor: re.Pattern, content_for) -> str:
    """Rewrite the ``` block that follows each anchor comment with
    ``content_for(name)``; everything else (all prose) passes through."""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        m = anchor.search(lines[i])
        i += 1
        if not m:
            continue
        name = m.group(1)
        while i < len(lines) and not lines[i].strip():
            out.append(lines[i])
            i += 1
        if i >= len(lines) or not lines[i].startswith("```"):
            raise SystemExit(f"docgen: anchor {name!r} is not followed by a code fence")
        out.append(lines[i])  # the opening fence
        i += 1
        while i < len(lines) and lines[i].strip() != "```":
            i += 1  # drop the stale block body
        if i >= len(lines):
            raise SystemExit(f"docgen: anchor {name!r}: unterminated code fence")
        out.extend(content_for(name).split("\n"))
        out.append(lines[i])  # the closing fence
        i += 1
    return "\n".join(out)


def _anchored(text: str, anchor: re.Pattern) -> set[str]:
    return set(anchor.findall(text))


# ── target: spec ──────────────────────────────────────────────────────────────

def gen_spec() -> str:
    def content(name: str) -> str:
        f = GOLDENS / f"{name}.txt"
        if not f.exists():
            raise SystemExit(f"docgen: no golden fixture for spec anchor {name!r} — "
                             "run CAGE_BLESS_GOLDENS=1 pytest tests/test_output_spec.py")
        return f.read_text(encoding="utf-8").rstrip("\n")

    text = _replace_anchored_blocks(SPEC.read_text(encoding="utf-8"),
                                    GOLDEN_ANCHOR, content)
    orphans = {f.stem for f in GOLDENS.glob("*.txt")} - _anchored(text, GOLDEN_ANCHOR)
    if orphans:
        raise SystemExit("docgen: golden fixture(s) with no spec anchor — every "
                         f"pinned output must be documented: {sorted(orphans)}")
    return text


# ── target: formulas ──────────────────────────────────────────────────────────

def _registry():
    sys.path.insert(0, str(REPO))
    from cage import explain, policy
    from cage.explain_data import REGISTRY
    os.environ.pop("CAGE_HUMAN_RATE", None)  # deterministic build-time values
    live = explain._live(policy.load(None))
    return {e.id: e for e in REGISTRY}, live


def gen_formulas() -> str:
    reg, live = _registry()

    def content(name: str) -> str:
        if name not in reg:
            raise SystemExit(f"docgen: formula anchor {name!r} matches no registry id")
        return reg[name].formula.format(**live)

    text = _replace_anchored_blocks(FORMULAS.read_text(encoding="utf-8"),
                                    FORMULA_ANCHOR, content)
    calc_ids = {e.id for e in reg.values() if e.kind == "calculation"}
    missing = calc_ids - _anchored(text, FORMULA_ANCHOR)
    if missing:
        raise SystemExit("docgen: calculation entries missing from docs/formulas.md "
                         f"(add an anchored block for each): {sorted(missing)}")
    return text


# ── target: policy (bundled policy.toml — two generated regions) ──────────────
# gen_policy owns TWO regions of the bundled cage/data/policy.toml: (1) the
# `# formula:` comment lines above their budget/human headers, and (2) the inert,
# ~-relative `[sources]` comment block between the sentinels below. Both regenerate
# from `--target policy`; `--check` gates drift on both. (One writer per file keeps
# TARGETS 1:1 with files — a separate `sources` target would race this one.)
SOURCES_START = "# cage:sources-start"
SOURCES_END = "# cage:sources-end"


def _regen_formula_comments(text: str, reg, live) -> str:
    """Region 1: rewrite each `# formula: …` line that sits directly above its
    budget/human header; strip any stale managed line elsewhere. Prose survives."""
    want: dict[str, str] = {}
    for header, rid in POLICY_FORMULA_MAP:
        first = reg[rid].formula.format(**live).split("\n")[0].rstrip()
        want[header] = f"# formula: {first}"
    out: list[str] = []
    for line in text.split("\n"):
        if line.strip() in want:
            while out and out[-1].startswith("# formula: "):
                out.pop()  # drop any stale managed line already queued directly above
            out.append(want[line.strip()])
        elif line.startswith("# formula: "):
            continue  # managed line no longer above its header — regenerate away
        out.append(line)
    return "\n".join(out)


def _sources_block() -> str:
    """The generated interior between the sources sentinels — every line a comment,
    ~-relative and env-independent (paths.builtin_source_docs)."""
    sys.path.insert(0, str(REPO))
    from cage import paths
    out = [
        "# [sources] — where cage looks for each agent's session log. GENERATED by",
        "# `python -m tools.docgen --target policy` from the built-in registry in",
        "# cage/paths.py; every line below is a COMMENT. The bundle ships NO active",
        "# [sources] table — these defaults live in code and upgrade with the package",
        "# (pip install -U). Uncomment/edit only to PIN or extend a location: an active",
        "# [sources.<agent>] shadows the built-in for THIS project and is never synced",
        "# by `cage policy sync`. Full contract: docs/sources.md.",
        "#",
        "# Schema:",
        "#   [sources.<agent>]    paths = [\"~/dir\", ...]   add locations (built-ins kept)",
        "#                        glob  = \"**/*.jsonl\"     optional; default = the format's",
        "#                        replace = true           drop the built-ins first",
        "#   [[sources.<agent>]]  path = \"~/dir\"           array form: one glob per path",
        "#                        glob = \"usage-*.ndjson\"",
        "#   [sources.<tool>]     format = \"claude|codex|copilot|kiro\"   custom tool (name",
        "#                        paths  = [...]           ∉ the four); rows stamp agent=<tool>",
        "#   A glob char (*?[) in a `path` is rejected — put the pattern in `glob = `.",
        "#   An empty `glob = \"\"` is an error (drop the key to use the format default).",
        "#",
    ]
    docs = paths.builtin_source_docs()
    for i, d in enumerate(docs):
        out.append(f"# {d['agent']}   (redirect home: {', '.join(d['env'])})")
        for path, glob, meaning in d["sources"]:
            out.append(f"#   {path}")
            out.append(f"#     glob {glob}   — {meaning}")
        if d["other_os"]:
            out.append("#     other OS:")
            out.extend(f"#       {line}" for line in d["other_os"])
        if i != len(docs) - 1:
            out.append("#")
    return "\n".join(out)


def _regen_sources_block(text: str) -> str:
    """Region 2: replace everything between the sentinels with the freshly generated
    block; the sentinel lines themselves and all surrounding prose survive. Fail loudly
    if either sentinel is missing — never guess an insertion point or append a second."""
    lines = text.split("\n")
    try:
        i, j = lines.index(SOURCES_START), lines.index(SOURCES_END)
    except ValueError:
        raise SystemExit(
            f"docgen: sources sentinels ({SOURCES_START!r} / {SOURCES_END!r}) not "
            f"found in {POLICY.relative_to(REPO)} — add both (a start line and an end "
            "line) and rerun `python -m tools.docgen --target policy`; never guess "
            "where the block goes")
    if j < i:
        raise SystemExit(f"docgen: sources sentinels out of order in "
                         f"{POLICY.relative_to(REPO)}")
    return "\n".join(lines[:i + 1] + [_sources_block()] + lines[j:])


def gen_policy() -> str:
    reg, live = _registry()
    text = POLICY.read_text(encoding="utf-8")
    text = _regen_formula_comments(text, reg, live)  # region 1
    text = _regen_sources_block(text)                # region 2
    return text


# ── driver ────────────────────────────────────────────────────────────────────

TARGETS = {"spec": (SPEC, gen_spec), "formulas": (FORMULAS, gen_formulas),
           "policy": (POLICY, gen_policy)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.docgen")
    ap.add_argument("--target", choices=[*TARGETS, "all"], default="all")
    ap.add_argument("--check", action="store_true",
                    help="verify the generated surfaces match (exit 1 on drift)")
    args = ap.parse_args(argv)
    names = list(TARGETS) if args.target == "all" else [args.target]
    drift = []
    for name in names:
        path, gen = TARGETS[name]
        new = gen()
        old = path.read_text(encoding="utf-8")
        if new == old:
            print(f"✔ {name}: {path.relative_to(REPO)} up to date")
        elif args.check:
            drift.append(name)
            print(f"✗ {name}: {path.relative_to(REPO)} DRIFTED — "
                  f"run `python -m tools.docgen --target {name}`")
        else:
            path.write_text(new, encoding="utf-8")
            print(f"✔ {name}: {path.relative_to(REPO)} regenerated")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
