"""P3 — the commit views. Weighted toward the refusals, because on these surfaces a
refusal is the product: the v1 axis died printing a number where it owed a `—`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from cage import cli, commitjoin, commitview, ledger, originrecord, schema, tasks


@pytest.fixture(autouse=True)
def _authorship_on(monkeypatch):
    monkeypatch.setenv("CAGE_AUTHORSHIP", "1")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(("git", "-C", str(repo), *args), capture_output=True,
                          text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "cageproj"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "commit.gpgsign", "false")
    return r


def _commit(repo: Path, files: dict, when: str) -> str:
    for rel, body in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    _git(repo, "add", "-A")
    subprocess.run(("git", "-C", str(repo), "commit", "-q", "-m", "c"), check=True,
                   capture_output=True,
                   env={**os.environ, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})
    # FULL sha — what cage records since 2026-08-11 (`commitjoin.prefix_match`).
    # A short one is exercised deliberately by the back-compat tests, not here.
    return _git(repo, "rev-parse", "HEAD")


AGENT_BODY = "def one():\n    return 'alpha beta gamma'\n"
HUMAN_EXTRA = "def two():\n    return 'typed by a person'\n"


@pytest.fixture
def world(repo, tmp_path):
    """A repo with three commits and a ledger describing the middle one:

    c1  seed                       — no calls, no authorship  → unattributed
    c2  agent wrote mod.py, a person added a function + a generated blob
    c3  a later commit so c2 has a bounded window
    """
    root = tmp_path / "ledger"
    c1 = _commit(repo, {"seed.txt": "0\n"}, "2026-07-01T09:00:00+00:00")
    c2 = _commit(repo, {"mod.py": AGENT_BODY + HUMAN_EXTRA,
                        "generated.json": '{"a": "a long generated value here"}\n'},
                 "2026-07-01T10:00:00+00:00")
    c3 = _commit(repo, {"after.txt": "later work landed here\n"},
                 "2026-07-01T11:00:00+00:00")
    # Calls inside c2's window, stamped with this repo's basename.
    for i, ts in enumerate(("2026-07-01T09:10:00+00:00", "2026-07-01T09:50:00+00:00")):
        ledger.append_row(root, "calls", schema.make_call(
            route="chat", provider="anthropic", model="claude-sonnet-4-6",
            tokens_in=1000, tokens_out=100, cached_in=400, cache_write_in=50,
            agent="claude-code", project=repo.name, session="s1", ts=ts,
            call_id=f"c_t{i}"))
    # The authorship row the P1 pass would have written for c2.
    originrecord.record_transcript(root, sha=c2, files=["mod.py"], agent="claude-code",
                                   lines_added=4, lines_removed=0, session_id="s1",
                                   suggested=2, kept=2, agent_lines=2)
    return {"repo": repo, "root": root, "c1": c1, "c2": c2, "c3": c3}


def _summary(world, **kw):
    return commitview.summarize(world["root"], {}, repo=world["repo"], **kw)


# ── the four buckets ──────────────────────────────────────────────────────────

def test_the_residual_splits_and_generated_files_land_in_unattributed(world):
    """The P1 dogfood's finding, pinned: a file nobody proposed is NOT human."""
    row = next(r for r in _summary(world)["rows"] if r["sha"] == world["c2"])
    assert row["agent"] == 2                     # the two proposed lines matched
    assert row["human"] == 2                     # the person's two lines, same file
    assert row["unattributed"] == 1              # generated.json — nobody proposed it
    assert row["unknown"] == 0


def test_the_four_buckets_are_never_redistributed(world):
    """Every classified added line sits in exactly one bucket, and `unknown` is one of
    them — it is never folded into agent or human to make a split reach 100."""
    for row in _summary(world)["rows"]:
        classified = sum(row[b] for b in commitview.BUCKETS)
        assert classified <= row["added"]
        assert all(row[b] >= 0 for b in commitview.BUCKETS)


def test_the_agent_count_is_read_never_re_derived(world):
    """Re-matching at render time would be a second matcher, free to disagree with the
    one that wrote the row. The view reads `agent_lines`."""
    rows = ledger.provenance(world["root"])
    assert rows[0]["agent_lines"] == 2
    row = next(r for r in _summary(world)["rows"] if r["sha"] == world["c2"])
    assert row["agent"] == rows[0]["agent_lines"]


def test_two_agents_cannot_each_claim_the_same_line(world):
    """A second session proposing the same file must not double the agent bucket past
    what the commit actually contains."""
    originrecord.record_transcript(world["root"], sha=world["c2"], files=["mod.py"],
                                   agent="claude-code", session_id="s2",
                                   suggested=2, kept=2, agent_lines=2)
    row = next(r for r in _summary(world)["rows"] if r["sha"] == world["c2"])
    assert row["agent"] <= row["added"]
    assert row["agent"] + row["human"] + row["unattributed"] + row["unknown"] <= row["added"]


# ── refusals: the product ─────────────────────────────────────────────────────

def test_an_unattributed_commit_renders_a_dash_never_zero(world):
    d = _summary(world)
    text = commitview.render_commits(d)
    c1 = next(r for r in d["rows"] if r["sha"] == world["c1"])
    assert not c1["attributed"] and c1["tokens_in"] == 0
    # The TABLE abbreviates (display only); the row data carries the full sha.
    line = next(ln for ln in text.splitlines()
                if ln.startswith(commitview._short(world["c1"])))
    assert commitview.DASH in line and " 0 " not in line
    assert "unattributed — no joinable call" in text
    assert "never 0" in text


def test_the_total_row_refuses_when_nothing_is_attributed(world, tmp_path):
    """`0` under a column of `—` would be the exact conflation this view prevents."""
    empty = commitview.summarize(tmp_path / "noledger", {}, repo=world["repo"])
    assert empty["totals"]["attributed"] == 0
    text = commitview.render_commits(empty)
    sigma = next(ln for ln in text.splitlines() if ln.startswith("Σ"))
    cells = re.split(r"\s{2,}", sigma.strip())
    # cells: [Σ n, date, tok in, tok out, cache r, cache w, hours, split]
    assert cells[2:7] == [commitview.DASH] * 5, sigma


def test_csv_leaves_an_unattributed_cell_empty_not_zero(world):
    rows = commitview.render_csv(_summary(world)).splitlines()
    head = rows[0].split(",")
    c1 = next(r for r in rows[1:] if r.startswith(world["c1"])).split(",")
    cell = dict(zip(head, c1))
    assert cell["attributed"] == "false"
    for col in ("calls", "tokens_in", "tokens_out", "cache_read", "cache_write"):
        assert cell[col] == "", f"{col} must be empty, never 0 — CSV never gates but it"\
                                " must not invent a measurement either"


def test_not_a_git_repo_refuses_with_the_reason(tmp_path):
    d = commitview.summarize(tmp_path / "l", {}, repo=None)
    # cwd under pytest IS a repo, so force the no-repo path explicitly.
    d = {**d, "ok": False, "reason": "not a git repository — these views are per-commit"}
    text = commitview.render_commits(d)
    assert "not a git repository" in text and "No commits to report on" in text


def test_a_missing_sha_refuses_rather_than_rendering_empty(world):
    d = _summary(world, sha="deadbee")
    assert not d["ok"] and "not a commit in this history" in d["reason"]


# ── hours: three visibly distinct tiers ───────────────────────────────────────

def _hours(**kw):
    base = {"row_wall": 3600, "agent_span": 600, "attested_min": None,
            "estimate_on": True, "cap_s": 4 * 3600}
    return commitview._hours(base["row_wall"] if "wall" not in kw else kw["wall"],
                             kw.get("span", base["agent_span"]),
                             kw.get("attested", base["attested_min"]),
                             estimate_on=kw.get("estimate_on", True),
                             cap_s=kw.get("cap_s", 4 * 3600))


def test_an_attestation_always_wins_over_the_estimate():
    h = _hours(attested=45)
    assert h["tier"] == commitview.ATTESTED and h["value"] == 0.75
    # …even when the estimator would happily have produced a number, and even when
    # the gap is past the cap.
    assert _hours(attested=45, wall=99999, cap_s=10)["tier"] == commitview.ATTESTED
    assert _hours(attested=45, estimate_on=False)["tier"] == commitview.ATTESTED


def test_the_estimator_is_wall_minus_span_floored_at_zero():
    assert _hours(wall=3600, span=600)["value"] == 0.83
    assert _hours(wall=600, span=3600)["value"] == 0.0     # floored, never negative


def test_the_estimator_refuses_past_the_gap_cap():
    h = _hours(wall=5 * 3600, cap_s=4 * 3600)
    assert h["value"] is None and h["reason"] == commitview.GAP_TOO_WIDE


def test_the_estimator_refuses_with_no_agent_span_to_subtract():
    """Otherwise `wall − nothing` is the raw commit gap printed in an hours column —
    an interval cage never observed, wearing a number. The v1 mistake exactly."""
    h = _hours(span=None)
    assert h["value"] is None and h["reason"] == commitview.NO_AGENT_SPAN


def test_the_kill_switch_leaves_only_attestation():
    h = _hours(estimate_on=False)
    assert h["value"] is None and h["reason"] == commitview.NO_ESTIMATE
    assert _hours(estimate_on=False, attested=30)["tier"] == commitview.ATTESTED


def test_the_first_commit_has_no_wall_clock():
    assert _hours(wall=None)["reason"] == commitview.NO_WALL


def test_the_tiers_are_visibly_distinct_in_the_cell():
    assert commitview._hours_cell({"hours": {"value": 0.8, "tier": commitview.ATTESTED}}) == "0.8*"
    assert commitview._hours_cell({"hours": {"value": 1.5, "tier": commitview.ESTIMATED}}) == "1.5~"
    assert commitview._hours_cell({"hours": {"value": None, "tier": None}}) == commitview.DASH


def test_a_refused_hours_cell_carries_its_reason_into_csv(world):
    csv = commitview.render_csv(_summary(world))
    assert "human_hours_refused" in csv.splitlines()[0]
    assert commitview.NO_AGENT_SPAN in csv or commitview.GAP_TOO_WIDE in csv


# ── the standing v1 guard ─────────────────────────────────────────────────────

_MONEY = re.compile(r"[$€£]\s?-?[\d.,]|\bcost_usd\b|\bhourly\b|\bper hour\b|\brate\b")


def test_no_usd_rate_or_valuation_appears_on_any_of_these_surfaces(world):
    """The standing v1 guard. The word `USD` is allowed in exactly one place — the
    footnote that states the omission is deliberate — but no *figure*, column or key
    may carry money or a rate."""
    d = _summary(world)
    surfaces = {
        "commits": commitview.render_commits(d),
        "commit": commitview.render_commit(_summary(world, sha=world["c2"])),
        "csv": commitview.render_csv(d),
        "authorship": commitview.render_authorship(
            commitview.summarize_authorship(world["root"], {}, repo=world["repo"])),
    }
    for name, text in surfaces.items():
        hit = _MONEY.search(text)
        assert hit is None, f"{name}: money/rate leaked — {hit.group(0)!r}"
        # `usd` may appear only inside the by-design disclaimer.
        for line in text.lower().splitlines():
            if "usd" in line:
                assert "no usd on this surface, by design" in line, f"{name}: {line}"

    # The JSON payload is checked by KEY, not by serializing it: the tmp path it
    # carries is the test's own name, and grepping the blob would fail on that
    # instead of on a real leak.
    def _keys(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from _keys(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from _keys(v)
    banned = {k for k in _keys(d)
              if any(w in k.lower() for w in ("usd", "cost", "price", "rate", "dollar"))}
    assert not banned, f"a money key reached the payload: {banned}"


def test_the_module_never_imports_a_pricing_path():
    """Structural, not aspirational: enforced against the module's real imports, not
    against prose that happens to mention them."""
    import ast
    tree = ast.parse(Path(commitview.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[-1] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported |= {a.name for a in node.names}
            if node.module:
                imported.add(node.module.split(".")[-1])
    assert not (imported & {"prices", "convert", "receiptprice", "netsaved", "roi"}), \
        f"a pricing path reached the authorship surface: {imported}"


# ── determinism ───────────────────────────────────────────────────────────────

def test_same_ledger_same_bytes(world):
    for render, kw in ((commitview.render_commits, {}),
                       (commitview.render_commit, {"sha": world["c2"]})):
        a = render(_summary(world, **kw))
        b = render(_summary(world, **kw))
        assert a == b
    assert commitview.render_csv(_summary(world)) == commitview.render_csv(_summary(world))


def test_show_all_never_perturbs_a_number(world):
    d = _summary(world)
    capped, full = commitview.render_commits(d), commitview.render_commits(d, show_all=True)
    sigma_a = next(ln for ln in capped.splitlines() if ln.startswith("Σ"))
    sigma_b = next(ln for ln in full.splitlines() if ln.startswith("Σ"))
    assert sigma_a == sigma_b


# ── `cage authorship summary` ────────────────────────────────────────────────

def test_authorship_summary_leads_with_the_unknown_rate(world):
    d = commitview.summarize_authorship(world["root"], {}, repo=world["repo"])
    assert d["commits"] == 3 and d["with_rows"] == 1
    text = commitview.render_authorship(d)
    body = text.splitlines()
    assert "UNKNOWN" in body[2], "the coverage gap is the headline, not a footnote"
    assert "unknown by ABSENCE" in text
    assert "counts, not a score" in text


def test_a_dangling_sha_is_counted_unmatched_never_chased(world):
    originrecord.record_transcript(world["root"], sha="deadbee", files=["gone.py"],
                                   agent="claude-code", session_id="s9")
    d = commitview.summarize_authorship(world["root"], {}, repo=world["repo"])
    assert d["unmatched"] == ["deadbee"]
    assert "not in this history" in commitview.render_authorship(d)


# ── the CLI surface ───────────────────────────────────────────────────────────

def test_the_three_verbs_dispatch(world, monkeypatch, capsys):
    monkeypatch.chdir(world["repo"])
    monkeypatch.setenv("CAGE_BASE", str(world["root"] / ".cage"))
    for argv in (["insights", "commits"], ["insights", "commit", world["c2"]],
                 ["authorship", "summary"]):
        assert cli.main(argv) == 0
        assert capsys.readouterr().out.strip()


def test_the_json_envelope_is_cage_v1(world, monkeypatch, capsys):
    monkeypatch.chdir(world["repo"])
    monkeypatch.setenv("CAGE_BASE", str(world["root"] / ".cage"))
    assert cli.main(["insights", "commits", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schemaVersion"] == "cage.v1" and payload["command"] == "commits"
    assert "rows" in payload["data"]


def test_csv_and_json_are_mutually_exclusive(world, monkeypatch):
    from cage.errors import CageError
    monkeypatch.chdir(world["repo"])
    monkeypatch.setenv("CAGE_BASE", str(world["root"] / ".cage"))
    with pytest.raises(CageError):
        from cage import clicmds

        class A:
            csv, json, html, since, all = "-", True, None, None, False
            no_import = quiet = why_ledger = True
        clicmds.cmd_commits(A())


# ── task-time attestation reaches the view (P4's read side) ──────────────────

def test_attested_minutes_from_a_clean_task_reach_the_commit(world):
    tasks.record(world["root"], "t1", outcome="ok", snapshot=False,
                 commit=world["c2"], human_minutes=90)
    row = next(r for r in _summary(world)["rows"] if r["sha"] == world["c2"])
    assert row["hours"]["tier"] == commitview.ATTESTED and row["hours"]["value"] == 1.5


def test_a_dirty_task_snapshot_does_not_donate_its_hours(world):
    """Its sha is the PRIOR commit — the same guard the call join applies."""
    tasks.record(world["root"], "t1", outcome="ok", snapshot=False,
                 commit=world["c2"], human_minutes=90, files_changed=4)
    row = next(r for r in _summary(world)["rows"] if r["sha"] == world["c2"])
    assert row["hours"]["tier"] != commitview.ATTESTED


# ── P3.4: window selection is a set, and what it hides is never silent ────────

def test_the_since_window_selects_by_sha_membership(world):
    """`wanted` was a list and `w not in wanted` ran inside the per-commit loop, so
    selection was O(n²) on top of the one `git show` each row already costs. A set of
    shas is the same selection; this pins that the *selection* did not change."""
    every = {r["sha"] for r in _summary(world)["rows"]}
    assert every == {world["c1"], world["c2"], world["c3"]}
    only_one = _summary(world, sha=world["c2"])
    assert [r["sha"] for r in only_one["rows"]] == [world["c2"]]


def test_a_window_records_how_many_commits_it_hid(world):
    """No silent caps. The row cap already footnotes its cut; a `--since` window that
    drops commits from the *read* had no counterpart, so a narrow window looked like a
    repo with less history rather than a view showing less of it."""
    data = _summary(world, since="1h")
    assert data["windowed_out"] == 3

    # When the window empties the view entirely there is already an honest message —
    # "the window is empty, not the repository" — so the count is the half that was
    # missing: a window that hides SOME commits.
    partial = {**data, "windowed_out": 2, "since": "1h",
               "rows": _summary(world)["rows"][:1], "ok": True}
    partial["totals"] = commitview._totals(partial["rows"])
    text = commitview.render_commits(partial)
    assert "2 commit(s) older than 1h not read" in text
    assert "--since WINDOW or --all" in text


def test_no_window_reports_nothing_hidden(world):
    """The control: with no `--since`, nothing is windowed out and the footnote is
    absent — a `0 commits older than None` line would be worse than silence."""
    data = _summary(world)
    assert not data.get("windowed_out")
    assert "not read" not in commitview.render_commits(data)


def test_the_detail_view_still_resolves_a_commit_outside_any_window(world):
    """`cage insights commit <sha>` shares this summarizer, which is exactly why no
    default window may be introduced inside it — an old sha must keep resolving."""
    data = _summary(world, sha=world["c1"])
    assert data["ok"] and [r["sha"] for r in data["rows"]] == [world["c1"]]


# ── P4.3: a ledger holding BOTH sha shapes ────────────────────────────────────

def test_a_short_sha_provenance_row_still_joins_to_a_full_sha_window(world):
    """The back-compat case, and the one that matters: every provenance row written
    before 2026-08-11 carries a short sha, is append-only, and can never be rewritten.
    An exact join would have silently dropped all of them the day cage started
    recording full shas — the buckets would read `unattr 100%` on work the agent
    demonstrably did."""
    short = world["c3"][:7]
    originrecord.record_transcript(world["root"], sha=short, files=["after.txt"],
                                   agent="claude-code", session_id="s_short",
                                   suggested=1, kept=1, agent_lines=1)
    row = next(r for r in _summary(world)["rows"] if r["sha"] == world["c3"])

    assert row["suggested"] == 1 and row["kept"] == 1
    assert "s_short" in row["sessions"]
    # And it is NOT reported as provenance cage could not place.
    d = commitview.summarize_authorship(world["root"], {}, repo=world["repo"])
    assert short not in d["unmatched"], d["unmatched"]


def test_an_attestation_written_with_a_short_sha_still_wins(world):
    """The `attested always wins` break, pinned. A task row carrying a short `commit`
    never equalled a full window sha, so `attested.get(w.sha)` returned None and
    `_hours` fell through to the `~` ESTIMATE — a person's own assertion about their
    time silently replaced by an inference."""
    tasks.record(world["root"], "t_att", outcome="ok")
    rows = tasks.read(world["root"])
    rows["t_att"].update(commit=world["c2"][:7], human_minutes=90, files_changed=0)
    ledger.append_row(world["root"], "tasks", rows["t_att"])

    row = next(r for r in _summary(world)["rows"] if r["sha"] == world["c2"])
    assert row["hours"]["tier"] == commitview.ATTESTED, row["hours"]
    assert row["hours"]["value"] == 1.5


def test_an_ambiguous_prefix_refuses_instead_of_rendering_the_oldest(world, monkeypatch):
    """The real defect behind "full shas". Prefix matching already existed and was
    already symmetric; what was missing was noticing TWO hits — and `render_commit`
    takes `rows[0]` over an OLDEST-first sort, so an ambiguous probe rendered the
    oldest match confidently. (The proposal recorded this symptom backwards.)"""
    windows = commitjoin.commit_windows(world["repo"])
    monkeypatch.setattr(commitjoin, "commit_windows", lambda _r: [
        commitjoin.Window("abc1230000000000000000000000000000000000", "", "2026-07-01T09:00:00Z"),
        commitjoin.Window("abc1231111111111111111111111111111111111",
                          "2026-07-01T09:00:00Z", "2026-07-01T10:00:00Z")])

    d = _summary(world, sha="abc123")
    assert not d["ok"]
    assert "ambiguous" in d["reason"] and "matches 2 commits" in d["reason"]
    assert "more characters" in d["reason"]
    # A longer probe resolves normally — the refusal is about the probe, not the repo.
    assert _summary(world, sha="abc1230")["ok"]
    del windows


def test_a_sha_that_is_simply_absent_still_says_so(world):
    """`no-match` and `ambiguous` must stay distinct messages: *cage does not have it*
    and *cage cannot tell which* are different answers to the reader."""
    d = _summary(world, sha="deadbeef")
    assert not d["ok"]
    assert "not a commit in this history" in d["reason"]
    assert "ambiguous" not in d["reason"]


def test_the_rendered_table_abbreviates_but_the_data_carries_the_full_sha(world):
    """The recorded decision: precision in the data, brevity in the display — the same
    split as tokens vs `$`. `--json`/`--csv` must never carry an abbreviated key, since
    an abbreviated key is exactly what this change exists to stop storing."""
    d = _summary(world)
    assert all(len(r["sha"]) == 40 for r in d["rows"])
    text = commitview.render_commits(d)
    assert commitview._short(world["c2"]) in text
    assert world["c2"] not in text                      # never the full 40 in a table
    csv = commitview.render_csv(d)
    assert world["c2"] in csv                           # but always in the data


# ── COMMITS-WINDOW · the cost bound (verdict B, 2026-08-11) ───────────────────

def _diff_calls(monkeypatch) -> list[str]:
    """Spy on the ONE expensive thing this view does: one `git show --numstat`
    subprocess per commit READ. Counting rendered rows would not have caught the
    defect — the rows were always capped; the subprocesses never were."""
    from cage import linematch
    seen: list[str] = []
    real = linematch.commit_diff

    def spy(repo, sha):
        seen.append(sha)
        return real(repo, sha)

    monkeypatch.setattr(commitview.linematch, "commit_diff", spy)
    return seen


def test_the_limit_bounds_the_subprocesses_not_just_the_rendered_rows(world, monkeypatch):
    """The whole defect: `render_commits` capped the table at 20 *after* every commit in
    the history had already paid for its own `git show`. Fails before the fix — three
    commits were read no matter what the caller asked for."""
    seen = _diff_calls(monkeypatch)
    d = _summary(world, limit=1)
    assert len(seen) == 1, f"read {len(seen)} commits for a 1-row view"
    assert len(d["rows"]) == 1
    assert d["limited_out"] == 2


def test_the_limit_keeps_the_NEWEST_commits(world, monkeypatch):
    """Capping on the rank axis means the rows a reader scans first, not an arbitrary
    slice: `windows` is oldest-first and the table is newest-first."""
    del monkeypatch
    d = _summary(world, limit=1)
    assert [r["sha"] for r in d["rows"]] == [world["c3"]]


def test_the_commits_it_never_read_are_footnoted_never_silently_cut(world):
    """No silent caps. And the Σ row now covers only what was read, so the footnote has
    to say *not read*, not merely *not shown* — otherwise a bounded total reads as a
    whole-history one."""
    text = commitview.render_commits(_summary(world, limit=1))
    assert "2 older commit(s) not read" in text
    assert "--all" in text and "--csv/--json are never capped" in text


def test_no_limit_reads_everything_byte_for_byte(world, monkeypatch):
    """`--all` and the CSV/JSON paths lift the bound entirely — the trade accepted in
    the compare doc is that they pay full cost, honestly rather than accidentally."""
    seen = _diff_calls(monkeypatch)
    d = _summary(world)
    assert len(seen) == 3 and len(d["rows"]) == 3 and d["limited_out"] == 0


def test_the_detail_view_is_never_capped_at_any_age(world, monkeypatch):
    """`cage insights commit <sha>` must render a commit of any age — a cost bound on
    the list view must never become a reachability bound on a specific commit."""
    seen = _diff_calls(monkeypatch)
    d = _summary(world, sha=world["c1"], limit=1)      # the OLDEST commit
    assert d["ok"] and [r["sha"] for r in d["rows"]] == [world["c1"]]
    assert seen == [world["c1"]] and d["limited_out"] == 0


def test_the_limit_never_moves_a_number_for_the_rows_it_did_read(world):
    """Determinism: bounding the read is a cost decision, never a value one. Every cell
    of a row that survives the cap is byte-identical to its uncapped self."""
    full = {r["sha"]: r for r in _summary(world)["rows"]}
    for r in _summary(world, limit=1)["rows"]:
        assert r == full[r["sha"]]
