"""docs/CLI.md is the complete CLI reference, and this is the gate that keeps it true.

A prose doc that names a dead verb is the F1 failure class in documentation form: the
reader copies it, it exits 1, and nobody learns why. `tests/test_skills_layer.py`
already applies the live parser to the shipped skill text; this applies it to the doc a
human reads. Bidirectional on purpose — a doc can lie by naming what does not exist
*and* by omitting what does.

Ground truth is `cli.build_parser()`, never a fixture and never `verbmap.REMOVED`: the
parser is the same code the CLI runs.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from cage import cli

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "CLI.md"

# Documented once under "Capture-on-read flags" instead of in every table — they sit on
# ~20 read views and repeating them would bury the flags that actually differ.
SHARED_FLAGS = {"--no-import", "--quiet", "--why-ledger"}

# argparse adds this everywhere; the doc names it once, on the front door.
UNIVERSAL_FLAGS = {"--help"}

# The root parser's own flags live under "## Global", which names no command path, so
# the per-section check below cannot locate them. The vocabulary check still covers them.
ROOT = ""


# ── ground truth: walk the live parser ────────────────────────────────────────

def _subaction(par):
    return next((a for a in par._actions if isinstance(a, argparse._SubParsersAction)), None)


def _choice_positional(par):
    """The first positional that closes over a fixed choice list."""
    return next((a for a in par._actions
                 if not a.option_strings and not isinstance(a, argparse._SubParsersAction)
                 and a.choices), None)


def _group_actions(par):
    """`prices`/`study`/`policy` take their action as a positional choice rather than a
    subparser (docs/CLI.md § Known gaps), yet `cage --help` presents them as groups
    beside `insights`/`task`/`authorship`/`data`. So their actions are addressable
    commands and the reference must cover each one.

    `cage hook` is deliberately NOT expanded this way: it is one hidden verb that takes
    an event argument, not a group, and `cage --help` never lists it at all."""
    a = _choice_positional(par)
    return list(a.choices) if a is not None and a.dest == "action" else []


def _walk(par, path, out):
    flags = {o for a in par._actions for o in a.option_strings if o.startswith("--")}
    sub = _subaction(par)
    if sub:
        out[" ".join(path)] = (flags, False)
        for name, sp in sub.choices.items():
            _walk(sp, path + [name], out)
        return
    actions = _group_actions(par)
    if actions:
        out[" ".join(path)] = (flags, False)  # the group itself is not a leaf
        for name in actions:
            out[" ".join(path + [name])] = (flags, True)
        return
    out[" ".join(path)] = (flags, True)


def _surface():
    out: dict[str, tuple[set[str], bool]] = {}
    _walk(cli.build_parser(), [], out)
    return out


SURFACE = _surface()
LEAVES = sorted(p for p, (_, leaf) in SURFACE.items() if leaf and p)
GROUPS = sorted(p for p, (_, leaf) in SURFACE.items() if not leaf and p)
ALL_PARSER_FLAGS = {f for flags, _ in SURFACE.values() for f in flags} | UNIVERSAL_FLAGS


# ── the doc ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def doc() -> str:
    assert DOC.exists(), f"{DOC.relative_to(REPO)} is the CLI reference and must exist"
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sections(doc) -> dict[str, str]:
    """Split on `## ` headings — the unit a command's flags are documented in."""
    out, title, buf = {}, "(preamble)", []
    for line in doc.splitlines():
        if line.startswith("## "):
            out[title] = "\n".join(buf)
            title, buf = line[3:].strip(), []
        else:
            buf.append(line)
    out[title] = "\n".join(buf)
    return out


_CODE_SPAN = re.compile(r"`([^`]+)`")
_WORDS = re.compile(r"^cage((?: [a-z][a-z0-9-]*)*)")


def _named_paths(doc: str) -> set[str]:
    """Command paths the doc names inside a code span. Prose is not checked: `cage
    installs no scheduler` is a sentence, not a command, and an allowlist of English
    words would rot faster than the doc."""
    found = set()
    for span in _CODE_SPAN.findall(doc):
        m = _WORDS.match(span.strip())
        if not m:
            continue
        found.add(" ".join(m.group(1).split()))
    return found


# ── 1. every leaf the parser knows is documented ──────────────────────────────

@pytest.mark.parametrize("path", LEAVES)
def test_every_command_appears_in_the_reference(doc, path):
    assert f"cage {path}" in doc, (
        f"`cage {path}` exists in the parser but docs/CLI.md never names it. "
        "A silently undocumented command is how a surface grows without a reader.")


@pytest.mark.parametrize("group", GROUPS)
def test_every_group_appears_in_the_reference(doc, group):
    assert f"cage {group}" in doc


def test_the_headline_count_matches_the_parser():
    """The doc opens with a count; a count that drifts is worse than no count."""
    body = DOC.read_text(encoding="utf-8")
    assert f"**{len(LEAVES)} addressable commands**" in body, (
        f"docs/CLI.md's headline count is stale — the parser has {len(LEAVES)} leaves")


# ── 2. nothing the doc names is dead ──────────────────────────────────────────

def _resolvable(path: str) -> bool:
    """Walk the live parser the way argparse would. Trailing tokens past a leaf are
    arguments, not commands (`cage query gross-vs-net` names a topic id), so resolution
    stops as soon as there is nothing left to dispatch on."""
    par, tokens = cli.build_parser(), path.split()
    for i, tok in enumerate(tokens):
        sub = _subaction(par)
        if sub is not None:
            if tok not in sub.choices:
                return False          # a group that has no such child
            par = sub.choices[tok]
            continue
        pos = _choice_positional(par)
        if pos is not None:
            return tok in pos.choices  # closed choice list; the rest are arguments
        return True                    # a leaf with free positionals
    return True


def test_no_command_named_in_the_reference_is_dead(doc):
    dead = sorted(p for p in _named_paths(doc) if not _resolvable(p))
    assert not dead, (
        "docs/CLI.md names commands that do not parse:\n  " + "\n  ".join(
            f"`cage {d}`" for d in dead))


def test_the_dead_command_detector_actually_detects():
    """A gate is only worth having if it fires. Pin both regimes."""
    assert _resolvable("insights chats") and _resolvable("study report")
    assert _resolvable("hook tool") and _resolvable("query gross-vs-net")
    assert not _resolvable("rep")            # no argparse abbreviation
    assert not _resolvable("insights attribute")
    assert not _resolvable("study delete")   # closed choice list
    assert not _resolvable("attrib")         # the pre-v0.32 spelling, now grouped
    # the money surface, gone in v0.51 (USAGE-ONLY, ADR 0011)
    assert not _resolvable("prices list") and not _resolvable("insights roi")
    assert not _resolvable("hook budget") and not _resolvable("task quality")


# ── 3. the flag vocabulary is bidirectional ───────────────────────────────────

_FLAG = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*)")


def _doc_flags(doc: str) -> set[str]:
    return {f for span in _CODE_SPAN.findall(doc) for f in _FLAG.findall(span)}


def test_every_documented_flag_exists(doc):
    invented = sorted(_doc_flags(doc) - ALL_PARSER_FLAGS)
    assert not invented, (
        "docs/CLI.md documents flags the parser does not have:\n  " + "\n  ".join(invented))


def test_every_parser_flag_is_documented(doc):
    missing = sorted(ALL_PARSER_FLAGS - _doc_flags(doc) - SHARED_FLAGS)
    assert not missing, (
        "these flags exist but docs/CLI.md never names them:\n  " + "\n  ".join(missing))


# ── 4. a flag unique to one command is documented in that command's section ───

def _unique_flags() -> dict[str, str]:
    """flag → the single command path that owns it."""
    owners: dict[str, list[str]] = {}
    for path, (flags, _) in SURFACE.items():
        for f in flags:
            owners.setdefault(f, []).append(path)
    return {f: paths[0] for f, paths in owners.items()
            if len(paths) == 1 and paths[0] != ROOT}


UNIQUE = _unique_flags()


@pytest.mark.parametrize("flag", sorted(UNIQUE))
def test_a_single_owner_flag_sits_in_its_command_section(sections, flag):
    """A shared vocabulary check would pass if `--record` were documented under `data`
    instead of `insights estimate`. A flag with exactly one owner has no such excuse."""
    path = UNIQUE[flag]
    hosts = [t for t, body in sections.items()
             if f"cage {path}" in body and f"`{flag}" in body]
    assert hosts, (
        f"`{flag}` belongs only to `cage {path}`, but no docs/CLI.md section documents "
        "both together")


# ── 5. the doc states its own maintenance trigger ─────────────────────────────

def test_the_reference_declares_how_it_is_maintained(doc):
    """Per CLAUDE.md every maintained doc carries a standing owner-trigger. Without it
    the next agent has a reference with no rule attached to it."""
    assert "## Maintaining this file" in doc
    assert "DOC-REGISTRY.md" in doc
    assert "tests/test_cli_reference.py" in doc


def test_the_reference_is_registered_as_maintained():
    reg = (REPO / "work" / "DOC-REGISTRY.md").read_text(encoding="utf-8")
    assert "CLI.md" in reg, "docs/CLI.md is a maintained doc and needs a DOC-REGISTRY row"
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "docs/CLI.md" in readme, "the README must link the CLI reference"
