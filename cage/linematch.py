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


def subtract_context(proposed, context) -> list[str]:
    """Drop the lines a block was merely **re-stating** from the ones it proposed.

    An `Edit` block's `new_string` is a replacement block, not a diff: it repeats
    surrounding lines to anchor the edit, and those were already in the file. They were
    entering `suggested` — and `kept_modified`, via ``modified = suggested - kept``.

    **This lives here, not in `transcript.py`, and that is the design call.** Rule 1 of
    this module is that normalization is one function applied to both sides and nothing
    else in cage may normalize a line for matching. Deciding "is this proposed line the
    same as that context line" *is* matching, so it obeys the same `normalize` + gate as
    `match_file`; doing it on the transcript side would put a second, drifting
    comparison outside the boundary rule 1 draws. `transcript._context_lines` therefore
    only transports the raw `old_string`.

    Consumes 1:1 through a multiset, exactly like `match_file` — three re-stated copies
    of a line remove three, not every occurrence. **Sub-gate lines are never subtracted**
    (rule 2): they are not matchable on either side, and removing them would quietly move
    lines out of the `unknown` bucket, which is never redistributed.

    **The opposite error, stated because it is real:** when an agent legitimately
    *re-adds* a line that was in `old_string` — moving a line, or restoring one it just
    deleted — that line is now subtracted and the agent is under-credited. That is the
    deliberate direction to err in: this module's whole premise is to observe the agent
    precisely and let the human be the residual, so an unearned proposal is a worse
    failure than a missed one.

    **Scope of the harm being fixed, honestly:** inflation of `suggested`/`kept_modified`
    was certain. False *agent credit* additionally required a context line to coincide
    with a genuinely human-added line, which `MIN_MATCH_CHARS` and 1:1 consumption make
    possible but not routine. Historical provenance rows are frozen by their idempotency
    key and keep the old, inflated counts; only rows written from here on are corrected.
    """
    if not context:
        return list(proposed)
    pool = Counter(n for c in context if matchable(n := normalize(c)))
    out = []
    for raw in proposed:
        n = normalize(raw)
        if matchable(n) and pool[n] > 0:
            pool[n] -= 1
            continue
        out.append(raw)
    return out


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

# The trailing `\t?` is the SECOND half of the quoted-path defect, and it survives the
# `core.quotePath=false` fix: git appends a literal tab to a `+++ b/<path>` line whenever
# the path needs disambiguating — which a path containing a **space** always does. Without
# it the capture is `"a b.py\t"`, which can never key-match the numstat name `a b.py`, so
# the file is DROPPED for a reason that has nothing to do with encoding. A real trailing
# tab in a filename cannot be confused with it: git C-quotes control characters regardless
# of `quotePath`, so an unquoted trailing tab is always the disambiguator.
_DIFF_FILE = re.compile(r"^\+\+\+ b/(.*?)\t?$")
_NUMSTAT = re.compile(r"^(\d+|-)\t(\d+|-)\t(.+)$")
# `git show --numstat` renders a RENAME in the name column, in one of two shapes, and
# neither can ever key-match a `+++ b/<path>` line:
#     old.py => new.py                 (plain)
#     d/{a => b}/f.py                  (braced — a shared prefix and/or suffix)
# The braced form's degenerate cases are real and must not be special-cased away:
# `{ => d}/x.py` (moved INTO a dir, empty old) and `d/{a => }/x.py` (moved OUT, empty
# new) — the latter is why the result is `/`-collapsed rather than concatenated blindly.
_RENAME_BRACE = re.compile(r"^(.*)\{(.*) => (.*)\}(.*)$")


def numstat_path(name: str) -> str:
    """The **destination** path from a numstat name column.

    A rename must resolve to where the file *landed*, because that is the key every
    other map in this module uses — `added` comes from `+++ b/<path>`, which git always
    writes as the new path. Left unparsed, `numstat` and `added` disagreed for every
    renamed file: the counts went to a phantom key (`old.py => new.py`), the real file
    got none, and `cage insights commit` rendered that arrow string as if it were a
    path. Shared by `commit_diff` and `originrecord.commit_numstat` so the two cannot
    drift — they already keep duplicate `_NUMSTAT` patterns, which is how this class of
    bug survives.

    A path genuinely containing " => " is not distinguishable here and would be
    misread; git quotes control characters but not this, so the ambiguity is inherent to
    the porcelain format. `-z` output would remove it and is a larger change.
    """
    if (m := _RENAME_BRACE.match(name)) is not None:
        prefix, _old, new, suffix = m.groups()
        joined = f"{prefix}{new}{suffix}"
        return joined.replace("//", "/").strip("/") if "//" in joined else joined
    if " => " in name:
        return name.split(" => ", 1)[1]
    return name


def _git(root: Path, *args: str) -> str | None:
    """Read-only git, 5s timeout, fail-open — the `tasks._git` idiom.

    **`core.quotePath=false` is not optional here.** With git's default, a path holding
    any non-ASCII byte is emitted C-quoted, so `+++ "b/caf\\303\\251.py"` never matches
    `_DIFF_FILE`, the file gets no `added` entry, and `match_commit` scores the landed
    file **DROPPED** — three maps keyed three different ways for one file. It is passed
    as `-c` before the subcommand (the only position git accepts) and set here rather
    than at each call site, so a new git read cannot forget it."""
    try:
        out = subprocess.run(("git", "-C", str(root), "-c", "core.quotePath=false",
                              *args), capture_output=True,
                             text=True, timeout=5, check=True, errors="replace")
        return out.stdout
    except (OSError, subprocess.SubprocessError):
        return None


def commit_diff(root: Path, sha: str) -> dict:
    """Everything one commit's diff can tell cage, from **one** git invocation::

        {"added":   {repo-relative path: [added lines]},   # transient, never persisted
         "numstat": {path: (added, removed)},              # the measured line counts
         "binary":  {path, …}}                             # numstat reported `-`

    One call, because the views read a diff per commit and two subprocesses per commit
    is twice the cost for the same bytes — `git show --numstat --unified=0` prints the
    numstat block and then the patch.

    Read with ``--unified=0`` (context lines carry no authorship signal and would
    inflate every side) and ``--no-color``/``--no-ext-diff``/``--no-textconv`` so a
    user's diff configuration cannot change what cage measures — a `textconv` filter
    would otherwise feed the matcher a *rendering* of the file rather than the file.
    ``--first-parent`` is deliberately absent: `git show` on a merge already prints no
    diff, which is the honest answer (a merge commit adds no lines of its own).

    The ``added`` strings are transient by contract — the caller matches on them and
    drops them. Fail-open ⇒ empty everything."""
    out = _git(root, "show", "--format=", "--numstat", "--unified=0", "--no-color",
               "--no-ext-diff", "--no-textconv", sha)
    added: dict[str, list[str]] = {}
    numstat: dict[str, tuple[int, int]] = {}
    binary: set = set()
    if not out:
        return {"added": added, "numstat": numstat, "binary": binary}
    current = None
    in_patch = False
    for line in out.splitlines():
        if not in_patch:
            m = _NUMSTAT.match(line)
            if m:
                a, r, f = m.groups()
                f = numstat_path(f)   # a rename keys to where the file LANDED
                if a == "-" or r == "-":
                    binary.add(f)
                else:
                    numstat[f] = (int(a), int(r))
                continue
            if line.startswith("diff --git"):
                in_patch = True   # the numstat block is over; everything after is patch
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
    return {"added": added, "numstat": numstat, "binary": binary}


def commit_added_lines(root: Path, sha: str) -> tuple[dict, set]:
    """``({path: [added lines]}, {binary paths})`` — the matcher's view of `commit_diff`."""
    d = commit_diff(root, sha)
    return d["added"], d["binary"]


def commit_numstat(root: Path, sha: str) -> dict:
    """``{path: (added, removed)}``, binary files excluded (numstat reports ``-``).
    The *measured* line counts a provenance row stores — read from git, never inferred
    from the patch parse."""
    return commit_diff(root, sha)["numstat"]
