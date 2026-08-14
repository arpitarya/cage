"""ADR-CLI carries rendered CLI output, and this is the gate that keeps it true.

`tests/test_cli_reference.py` proves every command and flag ADR-CLI *names* is live —
but it strips fenced blocks first (`_strip_fences`), because a Mermaid diagram is an
illustration rather than a citation. Output blocks are fenced, so they sit in the one
blind spot that gate has: a verb deleted tomorrow could live on in an output block
here forever and nothing would turn red. That is the F1 failure class with a longer
fuse than the one the reference gate already catches.

So this gate reads what that one skips. Three assertions, in order of what they buy:

1. every block declares its provenance class — GATED or CAPTURED;
2. every GATED block is byte-identical to the golden it cites, so ADR-CLI and
   `tests/test_output_spec.py` cannot drift apart (one artifact, two readers);
3. every block's `$ cage …` invocation resolves in `cli.build_parser()`.

What it deliberately does NOT check: the *body* of a CAPTURED block. Nothing can —
`cage doctor` prints a probe of the local filesystem, and pinning that would assert a
fact about the reader's machine that cage never measured (`test_output_spec.py` makes
the same call the removed `cage study join` block once had). The honest handling is a
declared class, not a
fake golden, which is why assertion 1 exists at all.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from cage import cli

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "adr" / "0002_cli.md"
GOLD = REPO / "tests" / "fixtures" / "goldens"

HEADING = "## What the output looks like"
END = "## Maintaining this record"

_GOLDEN_LINK = re.compile(r"tests/fixtures/goldens/([A-Za-z0-9_]+)\.txt")


# ── parse the section into (invocation, body, marker) triples ─────────────────

def _section() -> str:
    text = DOC.read_text(encoding="utf-8")
    assert HEADING in text, (
        f"ADR-CLI must carry a '{HEADING}' section — it is where the rendered output lives")
    return text[text.index(HEADING):text.index(END, text.index(HEADING))]


def _blocks() -> list[tuple[str, str, str]]:
    """(body, marker, label) per fenced block — marker is the `<sub>` line under it."""
    out, lines, i = [], _section().splitlines(), 0
    while i < len(lines):
        if lines[i].startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            body = "\n".join(lines[i + 1:j])
            k = j + 1
            while k < len(lines) and not lines[k].strip():
                k += 1
            marker = lines[k] if k < len(lines) else ""
            out.append((body, marker, body.splitlines()[0] if body.splitlines() else "(empty)"))
            i = j + 1
            continue
        i += 1
    return out


BLOCKS = _blocks()


def test_the_section_carries_blocks():
    """A gate over nothing passes forever. Pin that the section is non-empty."""
    assert len(BLOCKS) >= 10, (
        f"ADR-CLI's '{HEADING}' has {len(BLOCKS)} output block(s) — the section covers "
        "every view that prints, so this is a deletion, not a trim")


# ── 1. every block declares its provenance class ──────────────────────────────

@pytest.mark.parametrize("body,marker,label", BLOCKS, ids=[b[2] for b in BLOCKS])
def test_every_block_declares_its_class(body, marker, label):
    assert "**GATED**" in marker or "**CAPTURED**" in marker, (
        f"the output block for `{label}` declares no provenance class. Every block is "
        "GATED (byte-exact from a golden, checked below) or CAPTURED (real stdout, body "
        "unchecked) — an undeclared block is a reader trusting prose at golden strength.")


# ── 2. a GATED block IS its golden ────────────────────────────────────────────

GATED = [(b, m, l) for b, m, l in BLOCKS if "**GATED**" in m]


def test_there_are_gated_blocks():
    assert GATED, "every output block went CAPTURED — the gate below now checks nothing"


@pytest.mark.parametrize("body,marker,label", GATED, ids=[b[2] for b in GATED])
def test_a_gated_block_matches_its_golden(body, marker, label):
    m = _GOLDEN_LINK.search(marker)
    assert m, f"the GATED block for `{label}` cites no golden file"
    f = GOLD / f"{m.group(1)}.txt"
    assert f.exists(), f"{label} cites {f.relative_to(REPO)}, which does not exist"
    # Trailing newlines only: a fence eats the final one, and that is a markdown
    # artifact rather than a difference in what the CLI printed.
    assert body.rstrip("\n") == f.read_text(encoding="utf-8").rstrip("\n"), (
        f"ADR-CLI's block for `{label}` has drifted from {f.relative_to(REPO)}. Both are "
        "the same artifact: re-bless the golden "
        "(CAGE_BLESS_GOLDENS=1 pytest tests/test_output_spec.py), then paste it here.")


# ── 3. no dead verb hides inside a fence ──────────────────────────────────────

def _subaction(par):
    return next((a for a in par._actions if isinstance(a, argparse._SubParsersAction)), None)


def _choice_positional(par):
    return next((a for a in par._actions
                 if not a.option_strings and not isinstance(a, argparse._SubParsersAction)
                 and a.choices), None)


def _resolvable(path: str) -> bool:
    """The same walk as tests/test_cli_reference.py::_resolvable — trailing tokens past a
    leaf are arguments, not commands."""
    par, tokens = cli.build_parser(), path.split()
    for tok in tokens:
        sub = _subaction(par)
        if sub is not None:
            if tok not in sub.choices:
                return False
            par = sub.choices[tok]
            continue
        pos = _choice_positional(par)
        if pos is not None:
            return tok in pos.choices
        return True
    return True


_WORDS = re.compile(r"^cage((?: [a-z][a-z0-9-]*)*)")


@pytest.mark.parametrize("body,marker,label", BLOCKS, ids=[b[2] for b in BLOCKS])
def test_every_block_opens_with_a_live_invocation(body, marker, label):
    first = body.splitlines()[0] if body.splitlines() else ""
    assert first.startswith("$ cage"), (
        f"an output block must open with its invocation (`$ cage …`); this one opens "
        f"`{first[:40]}`. The line is what makes the block checkable at all.")
    m = _WORDS.match(first[2:].strip())
    assert m, f"cannot parse the invocation `{first}`"
    path = " ".join(m.group(1).split())
    assert _resolvable(path), (
        f"ADR-CLI's output section shows `cage {path}`, which does not parse. Fences are "
        "invisible to tests/test_cli_reference.py, so this gate is the only thing that "
        "catches a removed verb living on in a pasted output block.")


def test_the_dead_verb_detector_actually_detects():
    """A gate is only worth having if it fires."""
    assert _resolvable("insights commits") and _resolvable("doctor")
    assert not _resolvable("data export")      # the group deleted in v0.50
    assert not _resolvable("insights verdict")  # the money surface, gone in v0.51

