"""P2 — placing calls on commits. The join is `modeled`, so these tests are weighted
toward the ways it could quietly claim a call it has no right to.
"""
from __future__ import annotations

from cage import commitjoin as cj
from cage import schema

W = [cj.Window("aaa1111", "", "2026-07-01T10:00:00+00:00"),
     cj.Window("bbb2222", "2026-07-01T10:00:00+00:00", "2026-07-01T12:00:00+00:00"),
     cj.Window("ccc3333", "2026-07-01T12:00:00+00:00", "2026-07-01T14:00:00+00:00")]


def _call(ts, *, agent="claude-code", surface="", project="cage", task="",
          session="s1", cid=None, tin=100, tout=10):
    return schema.make_call(route="chat", provider="anthropic", model="m",
                            tokens_in=tin, tokens_out=tout, agent=agent,
                            surface=surface, project=project, task=task,
                            session=session, ts=ts, call_id=cid)


def _reason(res, reason):
    return next((e for e in res["excluded"] if e["reason"] == reason), None)


# ── the one normal form (REV-TS) ──────────────────────────────────────────────

def test_the_normal_form_is_one_fixed_shape():
    assert cj.norm_ts("2026-07-01T10:00:00+00:00") == "2026-07-01T10:00:00Z"
    assert cj.norm_ts("2026-07-01T10:00:00Z") == "2026-07-01T10:00:00Z"
    # The offset is applied, not dropped: 09:00 IST is 03:30Z.
    assert cj.norm_ts("2026-07-01T09:00:00+05:30") == "2026-07-01T03:30:00Z"
    assert cj.norm_ts("2026-07-01T11:00:00-08:00") == "2026-07-01T19:00:00Z"


def test_sub_seconds_are_truncated_never_rounded():
    """Rounding is non-monotone at a boundary — `…59.999` would round *up* into the
    next second and out of the window it belongs in."""
    assert cj.norm_ts("2026-07-01T10:00:00.999Z") == "2026-07-01T10:00:00Z"
    assert cj.norm_ts("2026-07-01T10:00:59.999999Z") == "2026-07-01T10:00:59Z"


def test_a_naive_timestamp_is_assumed_utc_never_left_naive():
    """Returning naive is how a comparison against an aware cutoff raises at a caller
    holding two kinds of datetime without knowing it."""
    assert cj.norm_ts("2026-07-01T10:00:00") == "2026-07-01T10:00:00Z"
    assert cj.as_utc("2026-07-01T10:00:00").tzinfo is not None
    assert cj.as_utc("2026-07-01T09:00:00+05:30").utcoffset().total_seconds() == 0


def test_normalization_is_idempotent():
    for raw in ("2026-07-01T09:00:00+05:30", "2026-07-01T10:00:00.500Z",
                "2026-07-01T10:00:00", ""):
        once = cj.norm_ts(raw)
        assert cj.norm_ts(once) == once


def test_unusable_input_yields_the_empty_string_not_a_guess():
    for bad in ("", None, "not a timestamp", "2026-13-45T99:99:99Z"):
        assert cj.norm_ts(bad) == ""
        assert cj.as_utc(bad) is None
    # "" sorts below every real timestamp — that is what keeps the oldest window
    # open below, so it must never become a real value.
    assert "" < cj.norm_ts("1970-01-01T00:00:00Z")


def test_the_normal_form_totally_orders_a_mixed_corpus():
    """The property the raw strings lack. Every shape cage actually meets — git's
    local offset, a call's `…SSZ`, a transcript's `…SS.mmmZ` — in one sort."""
    ist, utc, ms, pst = ("2026-07-01T12:00:00+05:30",     # 06:30Z
                         "2026-07-01T09:00:00+00:00",     # 09:00Z
                         "2026-07-01T05:00:00.250Z",      # 05:00Z
                         "2026-07-01T23:00:00-08:00")     # 2026-07-02T07:00Z
    raw = [ist, utc, ms, pst]
    assert sorted(raw, key=cj.norm_ts) == [ms, ist, utc, pst]   # chronological
    assert sorted(raw) != sorted(raw, key=cj.norm_ts)           # raw order is not


def test_a_window_cannot_be_built_holding_a_raw_bound():
    """Structural, not conventional: the skew was invisible for exactly as long as it
    depended on every caller remembering to normalize."""
    w = cj.Window("aaa1111", "2026-07-01T09:00:00+05:30", "2026-07-01T14:00:00+05:30")
    assert (w.lo, w.hi) == ("2026-07-01T03:30:00Z", "2026-07-01T08:30:00Z")
    assert cj.Window("bbb2222", "", "2026-07-01T10:00:00Z").lo == ""   # open below
    assert w.sha == "aaa1111" and tuple(w) == (w.sha, w.lo, w.hi)


# ── the window join ───────────────────────────────────────────────────────────

def test_a_call_lands_on_the_commit_whose_window_holds_it():
    res = cj.join_calls([_call("2026-07-01T11:00:00+00:00")], W, project="cage")
    assert list(res["by_sha"]) == ["bbb2222"]
    assert res["by_sha"]["bbb2222"]["via"] == {cj.VIA_TASK: 0, cj.VIA_WINDOW: 1}
    assert res["unattributed"] == ["aaa1111", "ccc3333"]


def test_a_commit_with_no_joinable_call_is_unattributed_never_zero():
    """The distinction the view depends on: 'nothing joined here' is not 'this cost
    nothing'. Unattributed commits are listed and counted, never folded into a total."""
    res = cj.join_calls([], W, project="cage")
    assert res["by_sha"] == {} and res["joined"] == 0
    assert res["unattributed"] == ["aaa1111", "bbb2222", "ccc3333"]


def test_work_newer_than_head_is_excluded_as_not_yet_committed():
    res = cj.join_calls([_call("2026-07-01T18:00:00+00:00", cid="c_a")], W,
                        project="cage")
    assert _reason(res, cj.AFTER_HEAD)["calls"] == 1
    assert res["by_sha"] == {}


def test_a_call_predating_the_first_commit_lands_on_it():
    """Not a fallback: the work that produced a repo's first commit precedes it, so
    the oldest window is open below and there is no `before-history` exclusion."""
    res = cj.join_calls([_call("2026-06-01T09:00:00+00:00", cid="c_b")], W,
                        project="cage")
    assert list(res["by_sha"]) == ["aaa1111"]
    assert res["excluded"] == []


# ── per-agent joinability is stated, never assumed ────────────────────────────

def test_sources_without_per_call_timestamps_are_excluded_and_counted():
    calls = [_call("2026-07-01T11:00:00+00:00", agent="copilot", surface="cli",
                   cid="c_cli"),
             _call("2026-07-01T11:00:00+00:00", agent="kiro", surface="ide",
                   cid="c_kiro")]
    res = cj.join_calls(calls, W, project="cage")
    assert res["by_sha"] == {}
    grp = _reason(res, cj.NO_TS_FIDELITY)
    assert grp["calls"] == 2 and grp["tokens"] == 220   # counted, not dropped silently


def test_the_joinability_table_names_every_gap():
    note = cj.joinability_note()
    assert "copilot/cli" in note and "kiro" in note
    assert "shutdown" in note and "IMPORT time" in note
    ok, why = cj.ts_fidelity("claude", "")
    assert ok and "per-turn" in why
    ok, why = cj.ts_fidelity("copilot", "vscode")
    assert ok and "per-request" in why


def test_an_unrecognised_source_is_excluded_rather_than_assumed():
    """cage never assumes a new capture route's timestamps are per-call."""
    ok, why = cj.ts_fidelity("brandnew", "")
    assert not ok and "has not verified" in why
    res = cj.join_calls([_call("2026-07-01T11:00:00+00:00", agent="brandnew")], W,
                        project="cage")
    assert _reason(res, cj.NO_TS_FIDELITY)["calls"] == 1


# ── project confirmation: three outcomes, not two ────────────────────────────

def test_an_unstamped_call_is_unconfirmable_not_adopted():
    """The global ledger is the default sink, so adopting unstamped rows would pull
    every other repo's spend onto these commits."""
    res = cj.join_calls([_call("2026-07-01T11:00:00+00:00", project="")], W,
                        project="cage")
    assert res["by_sha"] == {}
    assert _reason(res, cj.NO_PROJECT)["calls"] == 1
    assert _reason(res, cj.OTHER_PROJECT) is None   # a distinct fact, kept distinct


def test_another_projects_call_is_excluded_under_its_own_reason():
    res = cj.join_calls([_call("2026-07-01T11:00:00+00:00", project="elsewhere")], W,
                        project="cage")
    assert _reason(res, cj.OTHER_PROJECT)["calls"] == 1


def test_every_exclusion_reason_has_rendered_text():
    for reason in (cj.NO_TS_FIDELITY, cj.OTHER_PROJECT, cj.NO_PROJECT,
                   cj.AFTER_HEAD, cj.DANGLING_TASK):
        assert cj.EXCLUSION_TEXT[reason]


# ── task-id join wins, and is not trusted blindly ────────────────────────────

def test_the_task_join_wins_over_the_window():
    """A task id is an asserted link; a window is an inferred one."""
    tasks = {"t1": {"id": "t1", "outcome": "ok", "commit": "ccc3333"}}
    # ts would put it in bbb2222 — the task says ccc3333, and the task wins.
    res = cj.join_calls([_call("2026-07-01T11:00:00+00:00", task="t1")], W,
                        tasks, project="cage")
    assert list(res["by_sha"]) == ["ccc3333"]
    assert res["by_sha"]["ccc3333"]["via"][cj.VIA_TASK] == 1


def test_a_task_closed_on_a_dirty_tree_falls_back_to_the_window():
    """Its snapshot sha is the PRIOR commit — the work had not landed yet — so
    trusting it would put the spend on the wrong commit."""
    tasks = {"t1": {"id": "t1", "outcome": "ok", "commit": "aaa1111",
                    "files_changed": 3, "insertions": 40}}
    res = cj.join_calls([_call("2026-07-01T11:00:00+00:00", task="t1")], W,
                        tasks, project="cage")
    assert list(res["by_sha"]) == ["bbb2222"]                 # the window got it right
    assert res["by_sha"]["bbb2222"]["via"][cj.VIA_WINDOW] == 1
    assert res["dirty_tasks"] == 1                            # counted, not hidden


def test_an_open_task_never_joins():
    tasks = {"t1": {"id": "t1", "commit": "ccc3333"}}          # no outcome ⇒ open
    res = cj.join_calls([_call("2026-07-01T11:00:00+00:00", task="t1")], W,
                        tasks, project="cage")
    assert list(res["by_sha"]) == ["bbb2222"]                 # window, not task


def test_a_dangling_task_sha_is_excluded_not_chased():
    tasks = {"t1": {"id": "t1", "outcome": "ok", "commit": "deadbee"}}
    res = cj.join_calls([_call("2026-07-01T11:00:00+00:00", task="t1")], W,
                        tasks, project="cage")
    assert res["by_sha"] == {}
    assert _reason(res, cj.DANGLING_TASK)["calls"] == 1


def test_the_session_window_fallback_is_taskgroups_not_a_second_join():
    """A task-less call sharing a closed task's session and span is adopted by
    `taskgroup.join_rows` — reused, never re-implemented."""
    tasks = {"t1": {"id": "t1", "outcome": "ok", "commit": "ccc3333"}}
    anchored = _call("2026-07-01T11:00:00+00:00", task="t1", cid="c_anchor")
    orphan = _call("2026-07-01T11:00:00+00:00", task="", cid="c_orphan")
    res = cj.join_calls([anchored, orphan], W, tasks, project="cage")
    assert res["by_sha"]["ccc3333"]["via"][cj.VIA_TASK] == 2


# ── determinism ───────────────────────────────────────────────────────────────

def test_the_join_is_a_pure_function_of_its_inputs():
    calls = [_call("2026-07-01T11:00:00+00:00", cid=f"c_{i}") for i in range(5)]
    calls += [_call("2026-07-01T13:00:00+00:00", agent="kiro", cid="c_k")]
    a = cj.join_calls(calls, W, project="cage")
    b = cj.join_calls(calls, W, project="cage")
    assert a["excluded"] == b["excluded"]
    assert {k: v["via"] for k, v in a["by_sha"].items()} == \
           {k: v["via"] for k, v in b["by_sha"].items()}
    assert a["unattributed"] == b["unattributed"]


# ── P4.3: full shas + a prefix-symmetric join with an ambiguity refusal ────────

def test_prefix_match_is_symmetric_in_both_directions():
    """The back-compat mechanism. cage wrote SHORT shas until 2026-08-11 and writes full
    ones now; those rows are append-only, so both shapes coexist forever and a match has
    to work whichever side is abbreviated."""
    full = "a852987f30a58879499e391267eba09ed4674688"
    other = "c4908c70f51734f9328ce3f524f80b81fb25294b"

    assert cj.prefix_match({full, other}, "a852987") == (full, "ok")
    assert cj.prefix_match({"a852987", other}, full) == ("a852987", "ok")
    assert cj.prefix_match({full, other}, full) == (full, "ok")


def test_prefix_match_refuses_an_ambiguous_probe_rather_than_picking_one():
    """A probe matching two commits is a refusal, and a DISTINCT one from "no match":
    *cannot tell which* and *do not have it* are different answers, and collapsing them
    is what let an ambiguous prefix render a confident wrong commit."""
    a = "abc1230000000000000000000000000000000000"
    b = "abc1231111111111111111111111111111111111"

    assert cj.prefix_match({a, b}, "abc123") == (None, cj.AMBIGUOUS)
    assert cj.prefix_match({a, b}, "abc1230") == (a, "ok")
    assert cj.prefix_match({a, b}, "ffff") == (None, "no-match")
    assert cj.prefix_match({a, b}, "") == (None, "empty")


def test_head_and_windows_record_full_shas(tmp_path):
    """The write side. Both were `--short`, which is why they agreed — by coincidence of
    the moment: git's abbreviation length grows with the repo, so rows written months
    apart stop comparing equal, silently."""
    import subprocess
    r = tmp_path / "repo"
    r.mkdir()
    for a in (("init", "-q", "-b", "main"), ("config", "user.email", "t@e.invalid"),
              ("config", "user.name", "t")):
        subprocess.run(("git", "-C", str(r), *a), check=True, capture_output=True)
    (r / "a.txt").write_text("1\n", encoding="utf-8")
    subprocess.run(("git", "-C", str(r), "add", "-A"), check=True, capture_output=True)
    subprocess.run(("git", "-C", str(r), "commit", "-qm", "c"), check=True,
                   capture_output=True)

    assert len(cj.head(r)) == 40
    assert [len(w.sha) for w in cj.commit_windows(r)] == [40]
