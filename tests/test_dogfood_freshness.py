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


def _freshness_problem(dogfood_dir: Path, today: dt.date) -> str | None:
    """None when fresh; else a message naming exactly what's wrong."""
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
        parsed_date = dt.date.fromisoformat(snapshot_date)
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

    age_days = (today - parsed_date).days
    if age_days > MAX_AGE_DAYS:
        return (f"docs/dogfood/latest.md's snapshot is {age_days} days old "
                f"(> {MAX_AGE_DAYS}). This is a calendar-triggered freshness "
                f"reminder, not a code regression — refresh the snapshot per "
                f"docs/dogfood-report.handoff.md. {skip_hint}")

    return None


def _maybe_skip() -> None:
    if os.environ.get(_SKIP_ENV):
        pytest.skip(f"{_SKIP_ENV} is set — the dogfood freshness guard's "
                    "bisect/old-tag escape hatch")


# ── the guard itself, against the real repo ──────────────────────────────────

def test_dogfood_snapshot_is_fresh():
    _maybe_skip()
    problem = _freshness_problem(DOGFOOD_DIR, dt.date.today())
    assert problem is None, problem


def test_skip_env_var_skips(monkeypatch):
    monkeypatch.setenv(_SKIP_ENV, "1")
    with pytest.raises(pytest.skip.Exception):
        _maybe_skip()


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
