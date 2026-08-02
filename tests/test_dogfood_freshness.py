"""Guard: docs/dogfood/'s published snapshot must not silently rot (plan
docs/dogfood-report.handoff.md §5 D3, §8 R1/R2).

Reads **frontmatter only, never numbers** — the only reason this can run in CI with
no ledger. Two required assertions: `latest.md`'s `snapshot_date` is <= 60 days old,
and it agrees with the newest `docs/dogfood/<date>.md` filename (without the second
check, the guard is satisfiable by editing one frontmatter line and never re-running
the numbers). A missing/empty `docs/dogfood/` FAILS — a green check that asserts
nothing is worse than a red one. `CAGE_SKIP_DOGFOOD_FRESHNESS=1` is the bisect/old-tag
escape hatch (handoff §8 R1): a date-based assertion can go red on a boundary with no
code change, so the failure message says so in plain words.

**The two halves are gated differently, and that split is the point.**

- **Structural** (dir exists · `latest.md` exists · parseable `snapshot_date` · it
  agrees with the newest dated filename) runs **always, everywhere**. It is not
  date-dependent, anyone can fix it from the repo alone, and it is the half with teeth.
- **Age** (<= 60 days) runs **only when `CAGE_DOGFOOD_FRESHNESS` opts in** — which the
  canonical repo's CI sets and nobody else does. Left unconditional it was a **calendar
  bomb**: on ~2026-10-02 the suite went red on *every machine with no code change*, and
  a fork could not heal it at all, because the snapshot derives from the maintainer's
  own `~/.cage`. Under "green, or no release" that would have blocked every release on
  a docs refresh only one person on earth could perform.

Opt-in rather than skip-on-fork because the failure mode of guessing wrong is
asymmetric: a guard that is silently off for the maintainer is a stale snapshot, while
a guard that is wrongly on for a contributor is a red suite they cannot fix.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOGFOOD_DIR = REPO_ROOT / "docs" / "dogfood"
MAX_AGE_DAYS = 60
_SKIP_ENV = "CAGE_SKIP_DOGFOOD_FRESHNESS"
# Set by the canonical repo's CI only. Absent ⇒ the *age* assertion does not run;
# the structural ones still do. See the module docstring for why this is opt-in.
_AGE_ENV = "CAGE_DOGFOOD_FRESHNESS"
_DATE_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Minimal stdlib `key: value` frontmatter reader — the same flat `---`
    block shape every doc/*.md in this repo already uses. No YAML dependency."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm


def _newest_snapshot_date(dogfood_dir: Path) -> str | None:
    if not dogfood_dir.is_dir():
        return None
    dates = [m.group(1) for p in dogfood_dir.iterdir()
             if (m := _DATE_FILENAME_RE.match(p.name))]
    return max(dates) if dates else None


def _structure_problem(dogfood_dir: Path) -> str | None:
    """None when the published snapshot is structurally intact; else what's wrong.

    **Date-independent by construction** — every check here is answerable from the repo
    alone, which is why this half runs on every machine while the age check does not.
    """
    skip_hint = f"Set {_SKIP_ENV}=1 if you are bisecting or building an old tag."

    if not dogfood_dir.is_dir():
        return ("docs/dogfood/ is missing — see docs/dogfood-report.handoff.md. "
                f"{skip_hint}")

    latest = dogfood_dir / "latest.md"
    if not latest.is_file():
        return f"docs/dogfood/latest.md is missing. {skip_hint}"

    fm = _parse_frontmatter(latest.read_text(encoding="utf-8"))
    snapshot_date = fm.get("snapshot_date")
    if not snapshot_date:
        return (f"docs/dogfood/latest.md has no snapshot_date in its frontmatter. "
                f"{skip_hint}")

    try:
        dt.date.fromisoformat(snapshot_date)
    except ValueError:
        return (f"docs/dogfood/latest.md's snapshot_date {snapshot_date!r} is not a "
                f"YYYY-MM-DD date. {skip_hint}")

    newest_filename_date = _newest_snapshot_date(dogfood_dir)
    if newest_filename_date is None:
        return (f"docs/dogfood/ has no dated <YYYY-MM-DD>.md snapshot file. "
                f"{skip_hint}")

    if snapshot_date != newest_filename_date:
        return (f"docs/dogfood/latest.md's snapshot_date ({snapshot_date}) does not "
                f"match the newest docs/dogfood/<date>.md filename "
                f"({newest_filename_date}) — latest.md must be refreshed by "
                f"re-running the snapshot, not by editing one frontmatter line. "
                f"{skip_hint}")

    return None


def _age_problem(dogfood_dir: Path, today: dt.date) -> str | None:
    """None when the snapshot is within `MAX_AGE_DAYS`; else the reminder.

    Assumes the structure is already intact (`_structure_problem` ran first); an
    unparseable or absent date is that function's fault to report, not this one's."""
    fm = _parse_frontmatter((dogfood_dir / "latest.md").read_text(encoding="utf-8"))
    parsed_date = dt.date.fromisoformat(fm["snapshot_date"])
    age_days = (today - parsed_date).days
    if age_days > MAX_AGE_DAYS:
        return (f"docs/dogfood/latest.md's snapshot is {age_days} days old "
                f"(> {MAX_AGE_DAYS}). This is a calendar-triggered freshness "
                f"reminder, not a code regression — refresh the snapshot per "
                f"docs/dogfood-report.handoff.md. "
                f"Set {_SKIP_ENV}=1 if you are bisecting or building an old tag.")
    return None


def _freshness_problem(dogfood_dir: Path, today: dt.date) -> str | None:
    """Both halves, structure first. Kept as one entry point so the failure-mode
    tests below exercise the same ordering the real guard does."""
    return _structure_problem(dogfood_dir) or _age_problem(dogfood_dir, today)


def _maybe_skip() -> None:
    if os.environ.get(_SKIP_ENV):
        pytest.skip(f"{_SKIP_ENV} is set — the dogfood freshness guard's "
                    "bisect/old-tag escape hatch")


# ── the guard itself, against the real repo ──────────────────────────────────

def test_dogfood_structure_is_intact():
    """Unconditional, everywhere. Not date-dependent, and fixable from the repo alone."""
    _maybe_skip()
    problem = _structure_problem(DOGFOOD_DIR)
    assert problem is None, problem


def test_dogfood_snapshot_is_fresh():
    """Opt-in: the canonical repo's CI sets `CAGE_DOGFOOD_FRESHNESS`, nobody else does.

    Unconditional, this was a calendar bomb — red on every machine on ~2026-10-02 with
    no code change, and unfixable by a fork (the snapshot derives from the maintainer's
    own `~/.cage`). See the module docstring."""
    _maybe_skip()
    if not os.environ.get(_AGE_ENV):
        pytest.skip(f"{_AGE_ENV} is not set — the age check is opt-in and belongs to "
                    "the canonical repo's CI (a fork cannot refresh this snapshot). "
                    "The structural assertions ran regardless.")
    assert _structure_problem(DOGFOOD_DIR) is None      # age is meaningless without it
    problem = _age_problem(DOGFOOD_DIR, dt.date.today())
    assert problem is None, problem


def test_skip_env_var_skips(monkeypatch):
    monkeypatch.setenv(_SKIP_ENV, "1")
    with pytest.raises(pytest.skip.Exception):
        _maybe_skip()


def test_the_age_check_is_opt_in_but_the_structural_one_is_not(monkeypatch):
    """The calendar bomb, asserted as a property rather than trusted to a comment: an
    over-age snapshot must NOT fail a machine that did not opt in, and a structurally
    broken one must fail every machine either way."""
    monkeypatch.delenv(_AGE_ENV, raising=False)
    monkeypatch.delenv(_SKIP_ENV, raising=False)
    with pytest.raises(pytest.skip.Exception):
        test_dogfood_snapshot_is_fresh()
    # ...and the half that still has teeth is not gated on anything.
    assert _structure_problem(DOGFOOD_DIR) is None


def test_an_over_age_snapshot_is_only_a_problem_for_the_age_half(tmp_path):
    _write_snapshot(tmp_path, "2026-01-01")
    stale = dt.date(2027, 1, 1)
    assert _structure_problem(tmp_path) is None          # structure is fine forever
    assert _age_problem(tmp_path, stale) is not None     # only the calendar objects


# ── failure-mode coverage, all on tmp_path — never mutate the real
#    docs/dogfood/ (handoff §9) ───────────────────────────────────────────────

def _write_snapshot(dir_: Path, date_str: str, frontmatter_date: str | None = None):
    dir_.mkdir(parents=True, exist_ok=True)
    stamp = date_str if frontmatter_date is None else frontmatter_date
    body = f"---\ndoc: dogfood snapshot\nsnapshot_date: {stamp}\n---\n\nbody\n"
    (dir_ / f"{date_str}.md").write_text(body, encoding="utf-8")
    (dir_ / "latest.md").write_text(body, encoding="utf-8")


def test_fresh_snapshot_passes(tmp_path):
    _write_snapshot(tmp_path, "2026-01-01")
    assert _freshness_problem(tmp_path, dt.date(2026, 1, 20)) is None  # 19 days


def test_boundary_60_days_passes(tmp_path):
    _write_snapshot(tmp_path, "2026-01-01")
    assert _freshness_problem(tmp_path, dt.date(2026, 3, 2)) is None  # exactly 60


def test_61_days_old_fails(tmp_path):
    _write_snapshot(tmp_path, "2026-01-01")
    problem = _freshness_problem(tmp_path, dt.date(2026, 3, 3))  # 61 days
    assert problem is not None
    assert "61 days old" in problem
    assert "calendar-triggered freshness reminder, not a code regression" in problem
    assert _SKIP_ENV in problem


def test_frontmatter_filename_mismatch_fails(tmp_path):
    _write_snapshot(tmp_path, "2026-06-15", frontmatter_date="2026-06-10")
    problem = _freshness_problem(tmp_path, dt.date(2026, 6, 16))
    assert problem is not None
    assert "does not match" in problem
    assert "2026-06-10" in problem and "2026-06-15" in problem


def test_missing_directory_fails(tmp_path):
    missing = tmp_path / "does-not-exist"
    problem = _freshness_problem(missing, dt.date(2026, 6, 16))
    assert problem is not None
    assert "is missing" in problem
    assert _SKIP_ENV in problem


def test_empty_directory_fails(tmp_path):
    problem = _freshness_problem(tmp_path, dt.date(2026, 6, 16))
    assert problem is not None
    assert "latest.md is missing" in problem


def test_missing_dated_snapshot_fails(tmp_path):
    # latest.md present, but no <date>.md sibling — nothing to cross-check against.
    body = "---\ndoc: dogfood snapshot\nsnapshot_date: 2026-06-15\n---\n\nbody\n"
    (tmp_path / "latest.md").write_text(body, encoding="utf-8")
    problem = _freshness_problem(tmp_path, dt.date(2026, 6, 16))
    assert problem is not None
    assert "no dated" in problem


def test_missing_snapshot_date_field_fails(tmp_path):
    (tmp_path / "latest.md").write_text("---\ndoc: dogfood snapshot\n---\n\nbody\n",
                                        encoding="utf-8")
    (tmp_path / "2026-06-15.md").write_text("x", encoding="utf-8")
    problem = _freshness_problem(tmp_path, dt.date(2026, 6, 16))
    assert problem is not None
    assert "no snapshot_date" in problem
