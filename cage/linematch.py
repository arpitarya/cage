"""Line matching — the mechanism behind agent-vs-human authorship (v2, P1).

**Never observe the human. Observe the agent precisely; the human is the residual.**

A Claude transcript records the exact text an `Edit`/`Write`/`MultiEdit`/`NotebookEdit`
block proposed. A commit records the exact lines that landed. Intersect them and the
agent's contribution is *directly evidenced*; every added line that matches no agent
proposal is "not the agent", which is the actual observation — so it is labelled
``human~`` (estimated), never ``human``.

Four rules make that honest rather than merely plausible:

1. **Normalization is ONE function applied to BOTH sides.** `_norm` here is the whole
   correctness argument: if the proposal side and the diff side normalized differently,
   every count this module produces would be noise. Nothing else in cage may normalize
   a line for matching.
2. **A minimum-content gate.** A line whose normalized form is shorter than
   `constants.MIN_MATCH_CHARS` (`}`, `)`, blanks, one-char continuations) is excluded
   from matching **on both sides** and counted toward ``unknown``. Such lines occur in
   nearly every diff; matching on them would manufacture agreement between an agent
   proposal and an unrelated human edit.
3. **Matching consumes 1:1.** A proposed line matches at most one added line, via a
   multiset. Ten identical proposed `return None` lines cannot claim thirty added ones.
4. **Unknown is a first-class bucket and is never redistributed.** Sub-gate lines and
   binary files go to ``unknown``; they are shown, never folded into agent or human.

**Counts-never-content.** Every string this module touches — proposed lines, diff
lines — lives in process memory for the length of one import and is then dropped. No
line body and no line *hash* is written, logged, or shipped. `schema.make_provenance`
persists integers only, and `tests/test_authorship_capture.py` plants sentinel strings
in a fixture transcript and greps every written shard to prove it.
"""
from __future__ import annotations

import re
import subprocess
from collections import Counter
from pathlib import Path

from cage.constants import MIN_MATCH_CHARS

# Per-file classification of what happened to an agent's proposal. Counts, not a
# score: the proposal explicitly forbids collapsing these into an "acceptance %"
# (the enum is the resolution the source supports).
KEPT = "kept"                    # every matchable proposed line landed verbatim
LANDED_MODIFIED = "landed-modified"  # the file landed; some proposed lines diverged
DROPPED = "dropped"              # the file is absent from the commit entirely
NOT_PROPOSED = "not-proposed"    # in the commit, never proposed (the human shadow)
UNREADABLE = "unreadable"        # binary: git reports no lines, so nothing is matchable

_WS = re.compile(r"\s+")


def normalize(line: str) -> str:
    """The canonical form both sides are compared in: collapse every internal run of
    whitespace to one space and strip the ends.

    Deliberately narrow. It absorbs the differences a *formatter-free* round trip
    introduces — indentation the agent guessed at, a trailing space, tabs vs spaces —
    and nothing else. It does NOT lowercase, strip comments, or drop punctuation: two
    lines differing in any of those are genuinely different lines, and folding them
    together would let the matcher claim work it cannot see."""
    return _WS.sub(" ", line).strip()


def matchable(norm: str) -> bool:
    """Whether a normalized line clears the min-content gate (rule 2)."""
    return len(norm) >= MIN_MATCH_CHARS


def _prepare(lines) -> tuple[list[str], int]:
    """Normalize a side and split it into (matchable lines, sub-gate count)."""
    keep, gated = [], 0
    for raw in lines:
        n = normalize(raw)
        if matchable(n):
            keep.append(n)
        else:
            gated += 1
    return keep, gated


class FileMatch:
    """One file's outcome inside one commit, for one agent session. Counts only."""

    __slots__ = ("path", "verdict", "suggested", "kept", "kept_modified", "dropped",
                 "added_matchable", "added_gated", "agent_lines")

    def __init__(self, path: str, verdict: str, *, suggested: int = 0, kept: int = 0,
                 kept_modified: int = 0, dropped: int = 0, added_matchable: int = 0,
                 added_gated: int = 0, agent_lines: int = 0):
        self.path = path
        self.verdict = verdict
        self.suggested = suggested
        self.kept = kept
        self.kept_modified = kept_modified
        self.dropped = dropped
        self.added_matchable = added_matchable
        self.added_gated = added_gated
        self.agent_lines = agent_lines

    def __repr__(self) -> str:  # pragma: no cover — debugging aid only
        return (f"FileMatch({self.path!r}, {self.verdict!r}, suggested={self.suggested}, "
                f"kept={self.kept}, agent={self.agent_lines})")


def match_file(proposed, added) -> tuple[int, int, int]:
    """``(suggested, kept, agent_lines)`` for one file: how many proposed lines were
    matchable, how many of those landed verbatim, and how many *added* lines that
    accounts for.

    The 1:1 consumption rule (rule 3) is what the `Counter` is for — each proposed
    line can be spent against at most one added line, so a repeated boilerplate line
    can never inflate either side. `kept` and `agent_lines` are therefore equal here;
    they are returned separately because they answer different questions and a future
    fuzzy matcher would separate them (see `schema.make_provenance`)."""
    prop, _ = _prepare(proposed)
    add, _ = _prepare(added)
    pool = Counter(add)
    kept = 0
    for line in prop:
        if pool[line] > 0:
            pool[line] -= 1
            kept += 1
    return len(prop), kept, kept


def match_commit(proposed_by_file: dict, added_by_file: dict,
                 binary_files=()) -> tuple[list[FileMatch], dict]:
    """Match one session's proposals against one commit's added lines.

    ``proposed_by_file`` / ``added_by_file`` are ``{repo-relative path: [raw lines]}``;
    ``binary_files`` names paths git reported as binary (numstat ``-``), whose lines
    cannot be read at all and therefore go wholly to ``unknown``.

    Returns ``(per-file matches, commit totals)`` where the totals are::

        {"suggested", "kept", "kept_modified", "dropped", "agent_lines",
         "added", "unknown", "not_proposed_files", "binary_files"}

    ``added`` is every added line the commit contains and ``unknown`` is the sub-gate
    share of it. Binary files contribute a **file count**, never a line count: git's
    numstat reports ``-`` for them, so cage does not know how many lines they carry
    and will not invent one — they are named as unreadable rather than folded into a
    line bucket as if they had been measured.

    The human residual is deliberately NOT computed here: it is
    ``added − unknown − Σ agent_lines`` across **all** agents/sessions on the commit,
    so only a caller holding every row can compute it without double-counting a line
    two agents both proposed."""
    matches: list[FileMatch] = []
    totals = {"suggested": 0, "kept": 0, "kept_modified": 0, "dropped": 0,
              "agent_lines": 0, "added": 0, "unknown": 0, "not_proposed_files": 0,
              "binary_files": 0}

    for path in sorted(set(added_by_file) | set(proposed_by_file) | set(binary_files)):
        added = added_by_file.get(path)
        proposed = proposed_by_file.get(path)
        in_commit = path in added_by_file or path in binary_files

        if path in binary_files:
            # Nothing readable: `git show` prints no +lines and numstat prints `-`, so
            # neither side of the match exists. Counted as a file, never as lines.
            # A proposal against a binary path is pathological (an agent writing text
            # to one would make git see text); if it happens the proposed lines stay
            # `suggested` and land in `kept_modified` — the file DID land, and cage
            # cannot show any line of it matched. Never `kept`, never `dropped`.
            totals["binary_files"] += 1
            sug = 0
            if proposed is not None:
                sug = len(_prepare(proposed)[0])
                totals["suggested"] += sug
                totals["kept_modified"] += sug
            matches.append(FileMatch(path, UNREADABLE, suggested=sug,
                                     kept_modified=sug))
            continue

        if not in_commit:
            # Proposed, never landed. Every matchable proposed line is `dropped`.
            sug, _ = _prepare(proposed or [])
            m = FileMatch(path, DROPPED, suggested=len(sug), dropped=len(sug))
            matches.append(m)
            totals["suggested"] += m.suggested
            totals["dropped"] += m.dropped
            continue

        add_keep, add_gated = _prepare(added or [])
        totals["added"] += len(added or [])
        totals["unknown"] += add_gated

        if proposed is None:
            matches.append(FileMatch(path, NOT_PROPOSED, added_matchable=len(add_keep),
                                     added_gated=add_gated))
            totals["not_proposed_files"] += 1
            continue

        suggested, kept, agent_lines = match_file(proposed, added or [])
        modified = suggested - kept
        verdict = KEPT if (suggested and kept == suggested) else LANDED_MODIFIED
        matches.append(FileMatch(path, verdict, suggested=suggested, kept=kept,
                                 kept_modified=modified, added_matchable=len(add_keep),
                                 added_gated=add_gated, agent_lines=agent_lines))
        totals["suggested"] += suggested
        totals["kept"] += kept
        totals["kept_modified"] += modified
        totals["agent_lines"] += agent_lines

    return matches, totals


# ── reading a commit's added lines (transient, never persisted) ───────────────

_DIFF_FILE = re.compile(r"^\+\+\+ b/(.*)$")
_NUMSTAT = re.compile(r"^(\d+|-)\t(\d+|-)\t(.+)$")


def _git(root: Path, *args: str) -> str | None:
    """Read-only git, 5s timeout, fail-open — the `tasks._git` idiom."""
    try:
        out = subprocess.run(("git", "-C", str(root), *args), capture_output=True,
                             text=True, timeout=5, check=True, errors="replace")
        return out.stdout
    except (OSError, subprocess.SubprocessError):
        return None


def commit_added_lines(root: Path, sha: str) -> tuple[dict, set]:
    """``({repo-relative path: [added lines]}, {binary paths})`` for one commit.

    Read with ``--unified=0`` (context lines carry no authorship signal and would
    inflate every side) and ``--no-color``/``--no-ext-diff``/``--no-textconv`` so a
    user's diff configuration cannot change what cage measures — a `textconv` filter
    would otherwise feed the matcher a *rendering* of the file rather than the file.
    ``--first-parent`` is deliberately absent: `git show` on a merge already prints no
    diff, which is the honest answer (a merge commit adds no lines of its own).

    The returned strings are transient by contract — the caller matches on them and
    drops them. Fail-open ⇒ ``({}, set())``."""
    out = _git(root, "show", "--format=", "--unified=0", "--no-color", "--no-ext-diff",
               "--no-textconv", sha)
    added: dict[str, list[str]] = {}
    if out:
        current = None
        for line in out.splitlines():
            if line.startswith("+++ "):
                m = _DIFF_FILE.match(line)
                current = m.group(1) if m else None
                if current == "/dev/null":
                    current = None
                elif current is not None:
                    added.setdefault(current, [])
                continue
            if line.startswith("--- ") or line.startswith("@@"):
                continue
            if current is not None and line.startswith("+"):
                added[current].append(line[1:])
    return added, commit_binary_files(root, sha)


def commit_binary_files(root: Path, sha: str) -> set:
    """Paths git's numstat reports as binary (``-`` for both counts) — no readable
    lines, so their whole contribution is `unknown` rather than silently zero."""
    out = _git(root, "show", "--numstat", "--format=", sha)
    if not out:
        return set()
    binary = set()
    for line in out.splitlines():
        m = _NUMSTAT.match(line)
        if m and m.group(1) == "-" and m.group(2) == "-":
            binary.add(m.group(3))
    return binary


def commit_numstat(root: Path, sha: str) -> dict:
    """``{path: (added, removed)}`` for one commit, binary files excluded (numstat
    reports ``-`` for them). The *measured* line counts the provenance row stores —
    read from git, never inferred from the diff parse."""
    out = _git(root, "show", "--numstat", "--format=", sha)
    if not out:
        return {}
    rows: dict[str, tuple[int, int]] = {}
    for line in out.splitlines():
        m = _NUMSTAT.match(line)
        if not m:
            continue
        a, r, f = m.groups()
        if a == "-" or r == "-":
            continue
        rows[f] = (int(a), int(r))
    return rows
