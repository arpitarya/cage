"""DOC-LINK-CHECK — every `.md` link in a LIVE doc resolves, **case-sensitively**.

The prose twin of `test_cli_reference.py`'s dead-verb gate. Source comments and docs
cite each other by path, and a broken citation fails **silently**: nothing errors, and a
reader chasing a "design of record" finds nothing. DOC-CASE found the sharpest version of
that — a citation whose only fault is CASE (`docs/formulas.md` vs `docs/FORMULAS.md`) is
completely invisible on macOS's case-insensitive filesystem and breaks on GitHub and on
every Linux CI box. So resolution here is against `git ls-files`, which is
case-preserving, and never against the filesystem.

**The policy, decided 2026-08-11.** A naive walker went red on **155** links on day one,
nearly all of them history: `CHANGELOG.md`/`WORKLOG.md`/`archive/`/`regression/` entries
pointing at handoff pairs that gained a `vX.Y-` prefix *when they were archived*. Those
links were correct when written, and rewriting a dated record to keep a link green would
falsify the record. So the corpus splits, and the split is the decision:

- **LIVE** — the docs a reader navigates as *current*: root `*.md`, `docs/*.md`,
  `docs/adr/`, `work/compare/`, `docs/example/`, `work/cage-lab/`,
  `work/dogfood/`, `work/research/`, `work/*.md`. **A dangling link here FAILS.**
- **HISTORY** — dated, append-only records: `work/archive/**`, `work/regression/**`,
  `work/WORKLOG.md`, `work/IMPLEMENTATION.md`, `CHANGELOG.md`. **Exempt from failure**,
  because a link that pointed at a then-live doc is *true as history*.

**The exemption is counted, never silent** (`test_history_dangle_count_is_reported`) —
a silently-skipped corpus is how "we check links" turns into "we check some links and
nobody remembers which".

Links inside code spans and fenced blocks are **illustrations, not citations**, and are
skipped: `docs/doc-size-discipline.md` quotes a `[finding](…-….md)` link *as an example
of a link* while explaining how to measure one.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# A doc tree that is a dated record, not a live surface. See the module docstring.
HISTORY_DIRS = ("work/archive/", "work/regression/")
HISTORY_FILES = {"work/WORKLOG.md", "work/IMPLEMENTATION.md", "CHANGELOG.md"}

_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+?\.md)(#[^)]*)?\)")
_FENCE = re.compile(r"^\s*(```|~~~)")
_CODE_SPAN = re.compile(r"`[^`]*`")


def _tracked() -> set[str]:
    """Every tracked path, exactly as git records it — the case-preserving oracle."""
    out = subprocess.run(("git", "-C", str(REPO), "ls-files"),
                         capture_output=True, text=True, check=True).stdout
    return set(out.split("\n")) - {""}


def _is_history(path: str) -> bool:
    return path.startswith(HISTORY_DIRS) or path in HISTORY_FILES


def _resolve(doc: str, target: str) -> str:
    """`target` as written in `doc`, normalized to a repo-relative POSIX path.

    Hand-rolled rather than `Path.resolve()` **on purpose**: resolving touches the
    filesystem, and on a case-insensitive one that is precisely the check that cannot
    be trusted here.
    """
    parts: list[str] = []
    for seg in (Path(doc).parent / target).as_posix().split("/"):
        if seg == "..":
            if parts:
                parts.pop()
        elif seg not in (".", ""):
            parts.append(seg)
    return "/".join(parts)


def _links(text: str):
    """Every markdown `.md` link outside a code span or fenced block."""
    fenced = False
    for line in text.splitlines():
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        for m in _LINK.finditer(_CODE_SPAN.sub(lambda s: " " * len(s.group()), line)):
            t = m.group(1)
            if not t.startswith(("http://", "https://", "mailto:")):
                yield t


def _dangling(paths) -> list[tuple[str, str]]:
    tracked = _tracked()
    bad = []
    for f in paths:
        for t in _links((REPO / f).read_text(encoding="utf-8")):
            if _resolve(f, t) not in tracked:
                bad.append((f, t))
    return bad


def _docs() -> list[str]:
    out = subprocess.run(("git", "-C", str(REPO), "ls-files", "*.md"),
                         capture_output=True, text=True, check=True).stdout
    return sorted(p for p in out.split("\n") if p)


def test_every_live_doc_link_resolves():
    """The gate. A dangling citation in a doc a reader navigates as current is a bug of
    the same class as a dead verb in prose — and a CASE-only break is the invisible
    variant this test exists for, since git is case-preserving and macOS is not."""
    bad = _dangling(f for f in _docs() if not _is_history(f))
    assert not bad, "dangling .md links in LIVE docs:\n" + "\n".join(
        f"  {f} → {t}" for f, t in bad)


def test_the_check_is_case_sensitive_not_filesystem_sensitive():
    """DOC-CASE's exact class, asserted directly: `docs/formulas.md` names a real file on
    a case-insensitive checkout and no file at all on GitHub. If this ever passes, the
    walker has started asking the filesystem instead of git."""
    assert (REPO / "docs" / "FORMULAS.md").exists()
    assert _resolve("README.md", "docs/formulas.md") not in _tracked()
    assert _resolve("README.md", "docs/FORMULAS.md") in _tracked()


def test_a_link_inside_a_code_span_is_an_illustration_not_a_citation():
    """`docs/doc-size-discipline.md` quotes a link *as an example of a link*. Treating
    that as a citation would force a real file to exist for a piece of prose."""
    assert list(_links("see `[finding](regression/2026-01-01-nope.md)` for the shape")) == []
    assert list(_links("see [finding](regression/2026-01-01-nope.md) for the shape")) == \
        ["regression/2026-01-01-nope.md"]
    assert list(_links("```\n[x](nope.md)\n```")) == []


def test_history_dangle_count_is_reported_never_silently_skipped():
    """The exemption is a **decision**, so it states its own size. A history link that
    pointed at a then-live doc is true as history and is never repaired; what must not
    happen is the corpus quietly shrinking until nobody knows what is checked.

    The bound is deliberately loose — this asserts the exemption is *bounded and known*,
    not that it holds a specific number, which would turn every archived pair into a
    test edit."""
    hist = _dangling(f for f in _docs() if _is_history(f))
    assert len(hist) < 400, (
        f"{len(hist)} dangling links in HISTORY docs — well past the ~155 measured when "
        "the exemption was granted. Either the archive rename convention changed or "
        "live docs are landing in the history set.")
    # And the split must stay non-trivial in both directions: a HISTORY set that
    # captured everything would make the live gate vacuous.
    assert any(not _is_history(f) for f in _docs())
