"""QUEUE-HONESTY — `docs/OPEN-WORK.md`'s header must not contradict git.

The queue's header carries a reconciliation note, and **it has been wrong six times in
a week** — most sharply on 2026-08-11, when it asserted *"local HEAD == origin/main,
nothing is unreleased in tree"* over 8 unpushed commits and 47 staged files. Every other
drift surface in this repo is instrumented (`test_cli_reference.py` against the live
parser, `test_doc_links.py` against `git ls-files`, `wiringscan` against installed
artifacts); this one was not.

**The design the pre-mortem forced.** The obvious gate — assert `HEAD == origin/main` —
was rejected: it goes red on every legitimate in-flight change, and a gate that cries
wolf trains its maintainer to ignore it, which is worse than no gate. So:

- **Fail only on a contradiction.** A header that states no claim passes. A header
  saying "8 commits ahead" while git agrees passes. Only *clean-and-pushed asserted over
  a dirty or unpushed tree* fails — and it names both sides.
- **Counts are never checked.** "8 commits ahead", "47 staged files" are true-at-writing
  and volatile by design; gating them would redden on the next commit. Only the
  *durable* claims are checked: `__version__`, the latest tag, and clean/pushed.
- **Skip, never fail, when ground truth is unavailable** — no git binary, no `origin`
  remote, a shallow clone. An unanswerable question is not a failure; this is the same
  fail-open discipline the write path uses. **This is load-bearing for CI**, whose
  checkout depth is not guaranteed to resolve `origin/main` — see
  `test_absent_ground_truth_is_silence_not_failure`.
- **A past-tense recital never fires.** The header deliberately narrates its own
  corrections ("this header previously said…", "it claimed nothing was unreleased").
  Firing on those is the single most likely false positive, so past-tense sentences are
  dropped before any claim is read — asserted directly in
  `test_a_past_tense_recital_of_a_correction_never_fires`.

The matcher is a **pure function** of (text, ground truth) so both directions are
hermetic: the falsified header is tested against fabricated git state, not against
whatever the working tree happens to look like today.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "docs" / "OPEN-WORK.md"

# A sentence that recites a *past* state — the header's own correction log. Never a claim.
_PAST = re.compile(
    r"\b(previously|used to|had been|has gone stale|had gone stale|no longer|"
    r"was|were|had|claimed|said|asserted|turned out|de-staled)\b", re.I)
# `__version__ … 0.48.0` / `version is 0.48.0`
_VERSION = re.compile(r"(?:__version__|\bversion\b)[^.\d]{0,40}?(\d+\.\d+\.\d+)")
# `latest tag … v0.48.0`
_TAG = re.compile(r"\btags?\b[^.\d]{0,40}?v?(\d+\.\d+\.\d+)")
# The clean-and-pushed family. Each is a positive assertion that git can refute.
# **Markdown decoration is skipped between tokens** — this repo writes the claim as
# ``` `HEAD` is `origin/main` ```, and a matcher wanting bare words silently never fired
# on the one spelling the file actually uses.
_D = r"[`*_\s]*"
_PUSHED = re.compile(rf"HEAD{_D}(?:is|==|=){_D}origin/main|nothing is unreleased|"
                     r"\btree is clean\b|\bclean tree\b|nothing (?:un)?staged|"
                     r"fully pushed|nothing to push", re.I)


def _claim_sentences(text: str):
    """Present-tense sentences from the header (everything above the first `## `).

    Sentences are split on `·` and `;` too — the header packs several claims into one
    line separated by them, and a past-tense clause must not suppress a live sibling.
    **Closing markdown emphasis is part of the terminator**: the real header ends its
    correction log with `…gone stale six times in a week.** As of 2026-08-12: …`, and a
    splitter that required whitespace *immediately* after the `.` fused the two — the
    past-tense clause then silently suppressed the live version claim beside it, leaving
    the gate green on a header it was no longer reading (found by falsifying the real
    file, not by reasoning about the regex — see the test of this exact shape below).
    """
    head = text.split("\n## ", 1)[0]
    for sentence in re.split(r"(?<=[.;])[*_`)\]]*\s+|\n\n|·", head):
        if sentence.strip() and not _PAST.search(sentence):
            yield sentence


def contradictions(text: str, *, version=None, tag=None, dirty=None, unpushed=None):
    """Every place the header's checkable claims disagree with git. Empty = honest.

    Each ground-truth argument may be ``None`` — *unavailable*, not *false* — and a claim
    with no ground truth to check against is simply not checked.
    """
    out = []
    for s in _claim_sentences(text):
        if version and (m := _VERSION.search(s)) and m.group(1) != version:
            out.append(f"header says version {m.group(1)}, __init__.py says {version}")
        if tag and (m := _TAG.search(s)) and m.group(1) != tag.lstrip("v"):
            out.append(f"header says tag {m.group(1)}, git's latest tag is {tag}")
        if _PUSHED.search(s):
            if dirty:
                out.append(f"header claims a clean/pushed tree; git reports "
                           f"{dirty} uncommitted path(s)")
            if unpushed:
                out.append(f"header claims a clean/pushed tree; git reports "
                           f"{unpushed} commit(s) not on origin/main")
    return out


# ── ground truth ────────────────────────────────────────────────────────────────────
def _git(*args):
    """Git's answer, or ``None`` when the question cannot be asked here."""
    try:
        p = subprocess.run(("git", "-C", str(REPO)) + args,
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def _ground_truth() -> dict:
    from cage import __version__
    tags = _git("tag", "--sort=-v:refname")
    dirty = _git("status", "--porcelain")
    ahead = _git("log", "--oneline", "origin/main..HEAD")
    return {"version": __version__,
            "tag": tags.split("\n")[0] if tags else None,
            "dirty": None if dirty is None else len([x for x in dirty.split("\n") if x]),
            "unpushed": None if ahead is None else len([x for x in ahead.split("\n") if x])}


# ── the gate ────────────────────────────────────────────────────────────────────────
def test_the_queue_header_does_not_contradict_git():
    """The gate itself, against the real file and the real repo."""
    truth = _ground_truth()
    if truth["tag"] is None and truth["dirty"] is None:
        import pytest
        pytest.skip("no git ground truth here (no repo, no tags) — unanswerable, not failed")
    bad = contradictions(QUEUE.read_text(encoding="utf-8"), **truth)
    assert not bad, ("docs/OPEN-WORK.md's header contradicts git:\n" +
                     "\n".join(f"  · {b}" for b in bad) +
                     "\nReconcile the header against git — never the other way round.")


# ── the design, asserted in both directions ─────────────────────────────────────────
_REAL_SHAPE = ("**⚠ Before trusting anything here, reconcile with git.** As of 2026-08-11: "
               "`__version__` and latest tag are `0.48.0`; local `HEAD` is **8 commits "
               "ahead of `origin/main`** with **47 staged-uncommitted files**.")


def test_a_falsified_clean_and_pushed_claim_fails():
    """The 2026-08-11 defect, reproduced exactly: the header asserted clean-and-pushed
    over 8 unpushed commits and 47 staged files, and nothing caught it."""
    text = ("**As of today:** `__version__` is `0.48.0`; local `HEAD` is `origin/main` "
            "and nothing is unreleased in tree.\n\n## Your hands\n")
    bad = contradictions(text, version="0.48.0", tag="v0.48.0", dirty=47, unpushed=8)
    assert len(bad) == 2 and all("clean/pushed" in b for b in bad), bad
    assert "47 uncommitted" in bad[0] and "8 commit(s)" in bad[1]   # names BOTH sides


def test_the_claim_is_matched_in_the_repo_s_own_markdown_house_style():
    """The second false negative found by falsifying the real file: every claim here is
    written decorated — ``` `HEAD` is `origin/main` ``` — and a matcher wanting bare
    words fired on none of them while looking, from its green result, exactly like a
    matcher that had checked and found nothing wrong."""
    for spelling in ("`HEAD` is `origin/main`.", "HEAD == origin/main.",
                     "**`HEAD`** = **`origin/main`**.", "local `HEAD` is origin/main."):
        assert contradictions(spelling + "\n\n## x\n", dirty=1) == [
            "header claims a clean/pushed tree; git reports 1 uncommitted path(s)"], spelling


def test_a_falsified_version_or_tag_fails():
    text = "As of today: `__version__` and latest tag are `0.47.0`.\n\n## Your hands\n"
    bad = contradictions(text, version="0.48.0", tag="v0.48.0", dirty=0, unpushed=0)
    assert bad == ["header says version 0.47.0, __init__.py says 0.48.0",
                   "header says tag 0.47.0, git's latest tag is v0.48.0"]


def test_the_real_header_passes_against_the_real_repo():
    """The other direction, and the one that matters: the shipped header must be
    honest *as written*, not merely un-parseable."""
    truth = _ground_truth()
    if truth["tag"] is None:
        import pytest
        pytest.skip("no tags reachable here")
    assert contradictions(QUEUE.read_text(encoding="utf-8"), **truth) == []
    # …and the fixture above is the real header's shape, so this test cannot pass by
    # the parser having silently stopped recognising the header's own phrasing.
    assert contradictions(_REAL_SHAPE, version="0.47.0", tag="v0.47.0") == [
        "header says version 0.48.0, __init__.py says 0.47.0",
        "header says tag 0.48.0, git's latest tag is v0.47.0"]


def test_a_header_that_states_no_claim_passes():
    """Silence is not a contradiction. The pre-mortem's whole point: a gate that fires
    on absence would force the header to keep asserting things to stay green."""
    assert contradictions("**Next:** commit and push.\n\n## Your hands\n",
                          version="0.48.0", tag="v0.48.0", dirty=47, unpushed=8) == []


def test_an_ahead_by_n_claim_is_not_checked():
    """Counts are true-at-writing and volatile by design — gating them would redden on
    the very next commit, which is the failure mode this gate exists to avoid."""
    text = ("`HEAD` is **8 commits ahead of `origin/main`** with **47 staged files**."
            "\n\n## Your hands\n")
    assert contradictions(text, version="0.48.0", tag="v0.48.0", dirty=65, unpushed=9) == []


def test_a_past_tense_recital_of_a_correction_never_fires():
    """The most likely false positive, written as a test. The header narrates its own
    corrections; a correction is *evidence the file is maintained*, and a gate that
    punished it would delete the record to stay green."""
    text = ("This header previously said `HEAD` was `origin/main` and nothing was "
            "unreleased in tree; it had claimed the version was `0.47.0`. It has gone "
            "stale six times in a week.\n\n## Your hands\n")
    assert contradictions(text, version="0.48.0", tag="v0.48.0", dirty=47, unpushed=8) == []


def test_a_live_claim_beside_a_past_tense_one_is_still_checked():
    """The false *negative* the past-tense rule invites, and the one this gate actually
    shipped with for an hour: the real header's correction log and its live claim sit in
    one line — `…gone stale six times in a week.** As of 2026-08-12: __version__ … are
    0.48.0`. Fusing them makes the gate silently stop reading the file it guards, which
    is indistinguishable from passing. Suppression must be per *clause*, never per line.
    """
    text = ("**⚠ reconcile with git — this header had gone stale six times in a "
            "week.** As of 2026-08-12: `__version__` and latest tag are `0.48.0`; the "
            "sweep is unpushed.\n\n## Your hands\n")
    assert contradictions(text, version="0.47.0", tag="v0.47.0") == [
        "header says version 0.48.0, __init__.py says 0.47.0",
        "header says tag 0.48.0, git's latest tag is v0.47.0"]
    # …while the past-tense clause it shares the line with still suppresses nothing else.
    assert contradictions(text, dirty=65, unpushed=8) == []


def test_absent_ground_truth_is_silence_not_failure():
    """No git binary, no `origin`, a shallow CI clone: unanswerable, so nothing is
    asserted. `_git` returns ``None`` on any failure and `contradictions` treats ``None``
    as *unavailable*, never as *false* — the same fail-open discipline as the write path.
    """
    text = ("`__version__` and latest tag are `0.48.0`; `HEAD` is `origin/main` and the "
            "tree is clean.\n\n## Your hands\n")
    assert contradictions(text) == []                       # nothing known ⇒ nothing said
    assert contradictions(text, dirty=47) == [              # …and a known leg still binds
        "header claims a clean/pushed tree; git reports 47 uncommitted path(s)"]
    assert _git("rev-parse", "definitely-not-a-ref") is None
