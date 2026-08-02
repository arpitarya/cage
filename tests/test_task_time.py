"""P4 — `cage task time <duration>`: the one number on the authorship surfaces a
person asserts outright.

The v1 axis died because an *inferred* interval was multiplied by a rate and read as
measured. v2's answer is that the only unmarked human number is one a human typed —
and that it is never multiplied by anything.
"""
from __future__ import annotations

import pytest

from cage import cli, commitview, tasks
from cage.errors import CageError


# ── parsing: strict at the boundary, never fail-open ──────────────────────────

@pytest.mark.parametrize("spec,minutes", [
    ("45m", 45), ("45min", 45), ("90", 90), ("2h", 120), ("1h30m", 90),
    ("1h 30min", 90), ("  2h  ", 120), ("1H30M", 90),
])
def test_durations_cage_accepts(spec, minutes):
    assert tasks.parse_duration(spec) == minutes


@pytest.mark.parametrize("spec", [
    "", "   ", "soon", "2d", "1w", "-30m", "1.5h", "h", "m", "about an hour", "45s",
])
def test_durations_cage_rejects(spec):
    """Fail-open belongs on the WRITE path; this is a person asserting a figure, so a
    typo must be refused rather than silently become a different number."""
    with pytest.raises(ValueError):
        tasks.parse_duration(spec)


def test_zero_is_rejected_because_absence_already_means_unknown():
    for spec in ("0", "0m", "0h"):
        with pytest.raises(ValueError, match="greater than zero"):
            tasks.parse_duration(spec)


def test_days_are_not_a_unit():
    """A commit-scale attestation in days is a different claim, and it would sail past
    `max_est_gap` on the estimator side. It earns its own decision, not a silent `d`."""
    with pytest.raises(ValueError):
        tasks.parse_duration("3d")


# ── recording ─────────────────────────────────────────────────────────────────

@pytest.fixture
def proj_at(proj, monkeypatch):
    monkeypatch.chdir(proj)
    return proj


def _run(argv, capsys):
    code = cli.main(argv)
    return code, capsys.readouterr().out


def test_it_writes_attested_minutes_and_its_method(proj_at, capsys):
    from cage import clicmds
    clicmds.close_task(proj_at, "t_alpha")
    code, out = _run(["task", "time", "1h30m", "--task", "t_alpha"], capsys)
    assert code == 0 and "1h30m" in out
    row = tasks.read(proj_at)["t_alpha"]
    assert row["human_minutes"] == 90
    assert row["human_minutes_method"] == "attested"


def test_re_attesting_supersedes_and_never_rewrites(proj_at, capsys):
    from cage import clicmds
    clicmds.close_task(proj_at, "t_alpha")
    _run(["task", "time", "30m", "--task", "t_alpha"], capsys)
    _run(["task", "time", "45m", "--task", "t_alpha"], capsys)
    assert tasks.read(proj_at)["t_alpha"]["human_minutes"] == 45   # last write wins
    raw = [r for r in __import__("cage").ledger.read_kind(proj_at, "tasks")
           if r.get("human_minutes")]
    assert len(raw) == 2, "both attestations are still on disk — append-only"


def test_it_does_not_re_snapshot_git_over_the_recorded_commit(proj_at, capsys):
    """The hours attach to the sha the task recorded at close. Re-running git here
    would overwrite it with `now` — a different commit."""
    tasks.record(proj_at, "t_alpha", outcome="ok", snapshot=False, commit="abc1234")
    _run(["task", "time", "45m", "--task", "t_alpha"], capsys)
    assert tasks.read(proj_at)["t_alpha"]["commit"] == "abc1234"


def test_a_bad_duration_is_a_typed_cli_error(proj_at):
    from cage import clicmds

    class A:
        duration, task = "half an hour", None
    with pytest.raises(CageError, match="cannot read"):
        clicmds.cmd_task_time(A())


def test_with_no_tasks_at_all_it_says_what_to_do(proj_at):
    from cage import clicmds

    class A:
        duration, task = "45m", None
    with pytest.raises(CageError, match="no task to attest against"):
        clicmds.cmd_task_time(A())


def test_it_defaults_to_the_most_recent_task(proj_at, capsys):
    tasks.record(proj_at, "t_old", outcome="ok", snapshot=False,
                 ts="2026-07-01T09:00:00Z")
    tasks.record(proj_at, "t_new", outcome="ok", snapshot=False,
                 ts="2026-07-02T09:00:00Z")
    _run(["task", "time", "45m"], capsys)
    known = tasks.read(proj_at)
    assert known["t_new"]["human_minutes"] == 45
    assert "human_minutes" not in known["t_old"]


# ── it says where the number will and will not show up ────────────────────────

def test_attesting_an_open_task_says_it_needs_closing(proj_at, capsys):
    tasks.record(proj_at, "t_open", snapshot=False)
    _code, out = _run(["task", "time", "45m", "--task", "t_open"], capsys)
    assert "still open" in out and "cage task outcome t_open" in out


def test_attesting_a_dirty_close_says_the_hours_stay_off_the_commit(proj_at, capsys):
    """Its recorded sha is the commit BEFORE the work landed — the same guard the call
    join applies. Accepted, but never silently."""
    tasks.record(proj_at, "t_dirty", outcome="ok", snapshot=False, commit="abc1234",
                 files_changed=3)
    _code, out = _run(["task", "time", "45m", "--task", "t_dirty"], capsys)
    assert "uncommitted work" in out and "not on a commit" in out


# ── the standing guard: minutes, never money ──────────────────────────────────

def test_no_rate_or_currency_is_derived_from_an_attestation(proj_at, capsys):
    tasks.record(proj_at, "t_alpha", outcome="ok", snapshot=False, commit="abc1234")
    _code, out = _run(["task", "time", "2h", "--task", "t_alpha"], capsys)
    assert "$" not in out and "rate" not in out.lower()
    row = tasks.read(proj_at)["t_alpha"]
    assert not any("usd" in k or "cost" in k or "rate" in k for k in row)


def test_an_attestation_outranks_the_estimator_everywhere():
    """Pinned at the one place the two meet."""
    est = commitview._hours(3600, 600, None, estimate_on=True, cap_s=4 * 3600)
    att = commitview._hours(3600, 600, 120, estimate_on=True, cap_s=4 * 3600)
    assert est["tier"] == commitview.ESTIMATED and att["tier"] == commitview.ATTESTED
    assert att["value"] == 2.0                      # the asserted figure, untouched
    # …and it still wins where the estimator would have refused outright.
    for kw in ({"cap_s": 1}, {"estimate_on": False}):
        assert commitview._hours(9999, 0, 120, **{"estimate_on": True, "cap_s": 4 * 3600,
                                                  **kw})["tier"] == commitview.ATTESTED
