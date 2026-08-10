"""P1 — the authorship capture pass: line matching, commit windows, and the one
guarantee the whole design rests on (counts get written, content never does).

The v1 human axis died for inventing precision, so these tests are weighted toward
the places v2 could do the same: a match that shouldn't happen, a window that grabs
the wrong commit, a residual that quietly absorbs the unknown bucket.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cage import (authorcapture, commitjoin, importcmd, ledger, linematch, paths,
                  policy, schema)
from cage.constants import MIN_MATCH_CHARS

# Sentinel strings planted in the fixture transcript's proposed edits. If ANY of these
# reaches disk, the counts-never-content guarantee is broken. They are deliberately
# weird enough that no other test artifact could produce them by accident.
PLANT = "ZZQPLANT_SECRET_TOKEN_7717"
PLANT_DROPPED = "ZZQPLANT_NEVER_LANDED_9931"


# ── a real git repo + a real transcript ───────────────────────────────────────

def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(("git", "-C", str(repo), *args), capture_output=True,
                         text=True, check=True)
    return out.stdout.strip()


@pytest.fixture(autouse=True)
def _authorship_on(monkeypatch):
    """The suite pins the pass OFF (conftest); this file is the one that tests it."""
    monkeypatch.setenv("CAGE_AUTHORSHIP", "1")


@pytest.fixture
def repo(tmp_path):
    """A git repo with a deterministic identity (never the developer's own)."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "commit.gpgsign", "false")
    return r


def _commit(repo: Path, files: dict, when: str) -> str:
    """Commit ``{relative path: content}`` with an exact committer timestamp, so the
    window arithmetic is asserted against a known clock rather than `now`."""
    for rel, body in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    _git(repo, "add", "-A")
    env = {"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when}
    subprocess.run(("git", "-C", str(repo), "commit", "-q", "-m", "c"),
                   check=True, capture_output=True,
                   env={**__import__("os").environ, **env})
    # FULL sha — what cage records since 2026-08-11 (`commitjoin.prefix_match`).
    # A short one is exercised deliberately by the back-compat tests, not here.
    return _git(repo, "rev-parse", "HEAD")


def _transcript(path: Path, session: str, blocks: list[dict]) -> Path:
    """A Claude transcript carrying assistant turns with edit tool-use blocks.
    ``blocks`` items are ``{"ts", "tool", "file", ...tool payload}``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, b in enumerate(blocks):
        inp = {k: v for k, v in b.items() if k not in ("ts", "tool", "file")}
        inp["file_path"] = b["file"]
        lines.append(json.dumps({
            "type": "assistant", "uuid": f"u{i:04d}", "timestamp": b["ts"],
            "cwd": str(path.parent),
            "message": {"model": "claude-sonnet-4-6", "usage": {"input_tokens": 10,
                                                                "output_tokens": 5},
                        "content": [{"type": "tool_use", "name": b["tool"],
                                     "input": inp}]}}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ── normalization + the min-content gate ──────────────────────────────────────

def test_normalization_is_whitespace_only():
    """It must absorb indentation and nothing else — folding case or punctuation
    would let the matcher claim lines it cannot actually see."""
    assert linematch.normalize("    def f():") == "def f():"
    assert linematch.normalize("def\tf( a ,  b )") == "def f( a , b )"
    assert linematch.normalize("  x = 1  \n".rstrip("\n")) == "x = 1"
    # NOT normalized away — these are genuinely different lines.
    assert linematch.normalize("DEF F()") != linematch.normalize("def f()")
    assert linematch.normalize("x = 1  # note") != linematch.normalize("x = 1")


def test_the_gate_excludes_punctuation_noise_and_little_else():
    assert not linematch.matchable(linematch.normalize("}"))
    assert not linematch.matchable(linematch.normalize("   "))
    assert not linematch.matchable(linematch.normalize(")"))
    assert linematch.matchable(linematch.normalize("pass"))
    assert linematch.matchable(linematch.normalize("else:"))
    assert MIN_MATCH_CHARS == 4


def test_sub_gate_lines_go_to_unknown_never_to_human_or_agent():
    """The gate's whole point: a `}` the agent proposed and a `}` a human typed are
    indistinguishable, so neither may claim it."""
    _m, totals = linematch.match_commit({"a.py": ["}", "}"]}, {"a.py": ["}", "}"]})
    assert totals["kept"] == 0 and totals["agent_lines"] == 0
    assert totals["unknown"] == 2 and totals["suggested"] == 0


def test_matching_consumes_one_to_one():
    """Ten identical proposed lines cannot claim thirty added ones."""
    sug, kept, agent = linematch.match_file(["return None"] * 10, ["return None"] * 3)
    assert (sug, kept, agent) == (10, 3, 3)
    sug, kept, agent = linematch.match_file(["return None"] * 2, ["return None"] * 9)
    assert (sug, kept, agent) == (2, 2, 2)


def test_the_four_file_verdicts():
    proposed = {"kept.py": ["alpha beta gamma"],
                "modified.py": ["alpha beta gamma", "delta epsilon"],
                "gone.py": ["never landed here"]}
    added = {"kept.py": ["alpha beta gamma"],
             "modified.py": ["alpha beta gamma", "delta epsilon CHANGED"],
             "human.py": ["written by a person"]}
    matches, totals = linematch.match_commit(proposed, added)
    verdict = {m.path: m.verdict for m in matches}
    assert verdict["kept.py"] == linematch.KEPT
    assert verdict["modified.py"] == linematch.LANDED_MODIFIED
    assert verdict["gone.py"] == linematch.DROPPED
    assert verdict["human.py"] == linematch.NOT_PROPOSED
    assert totals["not_proposed_files"] == 1
    # suggested partitions exactly — the invariant `make_provenance` documents.
    assert totals["suggested"] == totals["kept"] + totals["kept_modified"] + totals["dropped"]


def test_binary_files_are_counted_as_files_never_as_lines():
    """numstat reports `-` for a binary file, so cage does not know its line count and
    must not invent one — it is named unreadable, not folded into a line bucket."""
    matches, totals = linematch.match_commit({}, {}, binary_files={"logo.png"})
    assert totals["binary_files"] == 1
    assert totals["added"] == 0 and totals["unknown"] == 0
    assert [m.verdict for m in matches] == [linematch.UNREADABLE]


# ── commit windows ────────────────────────────────────────────────────────────

def test_windows_are_half_open_with_an_inclusive_upper_bound(repo):
    a = _commit(repo, {"a.txt": "1\n"}, "2026-07-01T10:00:00+00:00")
    b = _commit(repo, {"b.txt": "2\n"}, "2026-07-01T12:00:00+00:00")
    w = commitjoin.commit_windows(repo)
    assert [x.sha for x in w] == [a, b]
    assert w[0].lo == ""  # the oldest commit's window is open below
    # Exactly at a commit's own timestamp ⇒ that commit (inclusive upper bound).
    assert commitjoin.window_for(w, "2026-07-01T10:00:00+00:00").sha == a
    assert commitjoin.window_for(w, "2026-07-01T10:00:01+00:00").sha == b
    assert commitjoin.window_for(w, "2026-07-01T12:00:00+00:00").sha == b
    # After the newest commit ⇒ NO window. Deliberately unrecorded, never guessed.
    assert commitjoin.window_for(w, "2026-07-01T12:00:01+00:00") is None


# ── REV-TS: one UTC normal form ───────────────────────────────────────────────
#
# Three timestamp shapes meet in one string compare here — git's `%cI` (committer
# **local** offset), a call's `…SSZ`, and a transcript turn's `…SS.mmmZ`. The tests
# above are green only because they never leave UTC and never sit on a boundary,
# which is exactly the pair of blind spots that let the skew ship. These fixtures
# are that pair, and they must fail before the fix.

def test_a_non_utc_repo_buckets_an_edit_on_the_commit_it_actually_follows(repo):
    """Offset skew. Committer dates in `+05:30`, probe in UTC. 05:00Z is 10:30 IST —
    *after* the 09:00 IST commit (03:30Z) and before the 14:00 one (08:30Z) — so the
    edit belongs to the second commit. A raw string compare reads `05` < `09` and
    hands it to the first."""
    c1 = _commit(repo, {"a.txt": "1\n"}, "2026-07-01T09:00:00+05:30")   # 03:30Z
    c2 = _commit(repo, {"b.txt": "2\n"}, "2026-07-01T14:00:00+05:30")   # 08:30Z
    w = commitjoin.commit_windows(repo)
    assert [x.sha for x in w] == [c1, c2]
    assert commitjoin.window_for(w, "2026-07-01T05:00:00.000Z").sha == c2
    # Genuinely before the first commit ⇒ still lands on it (open lower bound).
    assert commitjoin.window_for(w, "2026-07-01T03:00:00.000Z").sha == c1
    # Genuinely after the newest ⇒ no window, never a wrapped-around match.
    assert commitjoin.window_for(w, "2026-07-01T09:00:00.000Z") is None


def test_the_inclusive_upper_bound_holds_on_a_non_utc_bound(repo):
    """The same-second boundary, where it is actually reachable. The module's contract
    is *an edit made at the same second as the commit is part of it*; c2's bound is
    08:30:00Z written as `14:00:00+05:30`, so an edit at exactly 08:30:00Z is c2's. A
    raw compare reads `08` < `09` and gives it to c1 instead."""
    c1 = _commit(repo, {"a.txt": "1\n"}, "2026-07-01T09:00:00+05:30")   # 03:30Z
    c2 = _commit(repo, {"b.txt": "2\n"}, "2026-07-01T14:00:00+05:30")   # 08:30Z
    w = commitjoin.commit_windows(repo)
    assert commitjoin.window_for(w, "2026-07-01T08:30:00Z").sha == c2
    assert commitjoin.window_for(w, "2026-07-01T08:30:00.000Z").sha == c2
    # Anywhere inside that second is still c2 — `%cI` carries no sub-second, so cage
    # does not have the precision to push .999 into the next window.
    assert commitjoin.window_for(w, "2026-07-01T08:30:00.999Z").sha == c2
    assert commitjoin.window_for(w, "2026-07-01T08:30:01Z") is None
    # The lower bound stays exclusive across representations: 03:30:00Z is c1's own
    # instant, so it belongs to c1, not to the window that opens there.
    assert commitjoin.window_for(w, "2026-07-01T03:30:00Z").sha == c1


def test_a_pure_utc_repo_keeps_the_bound_it_already_gets_right(repo):
    """**Not a red fixture — a guard.** Git renders `%cI` as `…Z` (never `+00:00`)
    when the offset is zero, so in a pure-UTC repo the bounds already share the
    probes' shape and `.` (0x2E) sorting below `Z` (0x5A) makes sub-second probes
    land in the right window *by accident*. This currently passes and must keep
    passing: it is what forbids a millisecond normal form, which would push
    `12:00:00.999Z` out of the commit stamped `12:00:00` and break the inclusive
    bound in the one case that works today."""
    a = _commit(repo, {"a.txt": "1\n"}, "2026-07-01T10:00:00+00:00")
    b = _commit(repo, {"b.txt": "2\n"}, "2026-07-01T12:00:00+00:00")
    w = commitjoin.commit_windows(repo)
    assert [x.hi for x in w] == ["2026-07-01T10:00:00Z", "2026-07-01T12:00:00Z"]
    assert commitjoin.window_for(w, "2026-07-01T10:00:00.000Z").sha == a
    assert commitjoin.window_for(w, "2026-07-01T10:00:00Z").sha == a
    assert commitjoin.window_for(w, "2026-07-01T12:00:00.999Z").sha == b
    assert commitjoin.window_for(w, "2026-07-01T12:00:01.000Z") is None


def test_mixed_offset_history_sorts_chronologically_not_lexicographically(repo):
    """Local commits plus a GitHub-web/CI merge stamped `+00:00`. c1 is 06:30Z and c2
    is 09:00Z, so c2 is later — but the raw strings sort `09…+00:00` *below*
    `12…+05:30` and reverse them, building a window whose bounds run backwards."""
    c1 = _commit(repo, {"a.txt": "1\n"}, "2026-07-01T12:00:00+05:30")   # 06:30Z
    c2 = _commit(repo, {"b.txt": "2\n"}, "2026-07-01T09:00:00+00:00")   # 09:00Z
    w = commitjoin.commit_windows(repo)
    assert [x.sha for x in w] == [c1, c2]
    assert w[0].lo == "" and w[0].hi < w[1].hi      # never a negative window
    assert commitjoin.window_for(w, "2026-07-01T08:00:00.000Z").sha == c2


def test_capture_on_a_non_utc_repo_records_the_commit_the_work_landed_in(repo, tmp_path):
    """End to end, and the reason it matters: `originrecord` freezes a row by
    `(sha, agent, session, method)`, so a sha chosen by a skewed compare is wrong
    forever — the fix is forbidden from rewriting it."""
    body = f"def one():\n    return '{PLANT}'\n"
    tr = _transcript(tmp_path / "logs" / "sess-ist.jsonl", "sess-ist", [
        {"ts": "2026-07-01T05:00:00.000Z", "tool": "Write",
         "file": str(repo / "mod.py"), "content": body},
    ])
    _commit(repo, {"seed.txt": "s\n"}, "2026-07-01T09:00:00+05:30")      # 03:30Z
    landed = _commit(repo, {"mod.py": body}, "2026-07-01T14:00:00+05:30")  # 08:30Z
    root = tmp_path / "ledger"
    summary = authorcapture.capture(root, [tr], repo=repo, cursor={})
    assert summary["rows"] == 1
    rows = ledger.provenance(root)
    assert [r["sha"] for r in rows] == [landed]
    assert rows[0]["agent_lines"] == 2


def test_windows_fail_open_outside_a_repo(tmp_path):
    assert commitjoin.commit_windows(tmp_path) == []
    assert commitjoin.toplevel(tmp_path) is None


def test_an_empty_repo_has_no_windows(repo):
    assert commitjoin.commit_windows(repo) == []


# ── the capture pass end to end ───────────────────────────────────────────────

def _seed(repo: Path, tmp_path: Path):
    """One commit containing agent-proposed lines, human lines, and gate noise."""
    body = (f"def one():\n"
            f"    return '{PLANT}'\n"
            f"}}\n"
            f"def typed_by_a_person():\n"
            f"    return 'human wrote this line'\n")
    tr = _transcript(tmp_path / "logs" / "sess-a.jsonl", "sess-a", [
        {"ts": "2026-07-01T09:00:00.000Z", "tool": "Write",
         "file": str(repo / "mod.py"),
         "content": f"def one():\n    return '{PLANT}'\n}}\n"},
        {"ts": "2026-07-01T09:05:00.000Z", "tool": "Edit",
         "file": str(repo / "never.py"),
         "old_string": "", "new_string": f"x = '{PLANT_DROPPED}'\n"},
    ])
    sha = _commit(repo, {"mod.py": body}, "2026-07-01T10:00:00+00:00")
    return tr, sha


def test_capture_writes_rows_and_reimport_writes_zero(repo, tmp_path):
    tr, sha = _seed(repo, tmp_path)
    root = tmp_path / "ledger"
    cursor: dict = {}

    first = authorcapture.capture(root, [tr], repo=repo, cursor=cursor)
    assert first["rows"] == 1 and first["commits"] == 1
    rows = ledger.provenance(root)
    assert len(rows) == 1
    row = rows[0]
    assert row["sha"] == sha and row["method"] == "transcript"
    assert row["origin"] == "agent" and row["agent"] == authorcapture.AGENT
    assert row["files"] == ["mod.py"]          # `never.py` was dropped, so not a file here
    assert row["session_id"] == "sess-a"
    # Two proposed lines cleared the gate (`}` did not); both landed verbatim.
    assert row["suggested"] == 3               # 2 in mod.py + 1 in never.py
    assert row["kept"] == 2 and row["agent_lines"] == 2
    assert row["dropped"] == 1                 # never.py never landed
    assert "kept_modified" not in row          # 0 ⇒ omitted (additive-optional)
    assert row["suggested"] == row["kept"] + row["dropped"]

    # Idempotent: the dedupe key is (sha, agent, session, method).
    again = authorcapture.capture(root, [tr], repo=repo, cursor=cursor)
    assert again["rows"] == 0
    assert len(ledger.provenance(root)) == 1


def test_no_line_body_and_no_line_hash_ever_reaches_disk(repo, tmp_path):
    """THE guarantee. Plant sentinels in the proposed text, run capture, then grep
    every byte cage wrote — the row, the shards, the state dir, the debug log."""
    tr, _sha = _seed(repo, tmp_path)
    root = tmp_path / "ledger"
    import os
    os.environ["CAGE_DEBUG"] = "1"   # write the most cage can possibly write
    try:
        authorcapture.capture(root, [tr], repo=repo, cursor={})
    finally:
        os.environ.pop("CAGE_DEBUG", None)

    written = [p for p in paths.Footprint(root).base.rglob("*") if p.is_file()]
    assert written, "the pass wrote nothing at all — the test would pass vacuously"
    import hashlib
    digests = {h(p.encode()).hexdigest()
               for p in (PLANT, PLANT_DROPPED)
               for h in (hashlib.sha1, hashlib.sha256, hashlib.md5)}
    for f in written:
        blob = f.read_text(encoding="utf-8", errors="replace")
        assert PLANT not in blob, f"a proposed LINE BODY leaked into {f.name}"
        assert PLANT_DROPPED not in blob, f"a dropped line body leaked into {f.name}"
        for d in digests:
            assert d not in blob, f"a line HASH leaked into {f.name}"
            assert d[:12] not in blob, f"a truncated line hash leaked into {f.name}"


def test_a_commit_that_does_not_exist_yet_is_left_for_the_next_import(repo, tmp_path):
    """The window rule's other half: work after the newest commit is unrecorded now
    and recorded exactly once later — never attributed to HEAD-at-import."""
    _commit(repo, {"seed.txt": "0\n"}, "2026-07-01T08:00:00+00:00")
    tr = _transcript(tmp_path / "logs" / "sess-b.jsonl", "sess-b", [
        {"ts": "2026-07-01T09:00:00.000Z", "tool": "Write",
         "file": str(repo / "later.py"), "content": "value = 'landed later on'\n"}])
    root = tmp_path / "ledger"
    cursor: dict = {}

    early = authorcapture.capture(root, [tr], repo=repo, cursor=cursor)
    assert early["rows"] == 0 and early["uncovered"] == 1
    assert ledger.provenance(root) == []

    sha = _commit(repo, {"later.py": "value = 'landed later on'\n"},
                  "2026-07-01T10:00:00+00:00")
    late = authorcapture.capture(root, [tr], repo=repo, cursor=cursor)
    assert late["rows"] == 1
    assert [r["sha"] for r in ledger.provenance(root)] == [sha]
    # And still exactly once.
    assert authorcapture.capture(root, [tr], repo=repo, cursor=cursor)["rows"] == 0
    assert len(ledger.provenance(root)) == 1


def test_the_cursor_stops_re_reading_a_covered_transcript(repo, tmp_path):
    tr, _sha = _seed(repo, tmp_path)
    root, cursor = tmp_path / "ledger", {}
    assert authorcapture.capture(root, [tr], repo=repo, cursor=cursor)["files_read"] == 1
    # Covered + unchanged ⇒ never parsed again (the steady-state no-op).
    assert authorcapture.capture(root, [tr], repo=repo, cursor=cursor)["files_read"] == 0
    tr.write_text(tr.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert authorcapture.capture(root, [tr], repo=repo, cursor=cursor)["files_read"] == 1


def test_edits_outside_the_repo_are_ignored_not_guessed_at(repo, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    _commit(repo, {"a.txt": "1\n"}, "2026-07-01T10:00:00+00:00")
    tr = _transcript(tmp_path / "logs" / "sess-c.jsonl", "sess-c", [
        {"ts": "2026-07-01T09:00:00.000Z", "tool": "Write",
         "file": str(other / "foreign.py"), "content": "alpha = 'beta gamma'\n"}])
    root = tmp_path / "ledger"
    assert authorcapture.capture(root, [tr], repo=repo, cursor={})["rows"] == 0
    assert ledger.provenance(root) == []


def test_capture_is_fail_open_with_no_repo_and_no_commits(repo, tmp_path):
    root = tmp_path / "ledger"
    assert authorcapture.capture(root, [], repo=tmp_path / "nope",
                                 cursor={})["skipped"] == "no-commits"
    assert authorcapture.capture(root, [], repo=repo, cursor={})["skipped"] == "no-commits"
    assert ledger.provenance(root) == []


def test_per_agent_coverage_is_stated_not_silently_zero():
    note = authorcapture.coverage_note()
    assert "copilot" in note and "kiro" in note
    assert set(authorcapture.COVERAGE_GAPS) == {"copilot", "kiro"}


# ── the substrate stays additive ──────────────────────────────────────────────

def test_a_row_with_no_counts_is_byte_identical_to_the_pre_v2_contract():
    row = schema.make_provenance(sha="abc1234", files=["a.py"], agent="x")
    assert tuple(row) == schema.PROVENANCE_FIELDS
    assert row["schema_ver"] == 1


def test_counts_are_omitted_at_zero_and_present_when_set():
    row = schema.make_provenance(sha="abc1234", files=["a.py"], suggested=5, kept=3,
                                 kept_modified=0, dropped=2, agent_lines=3)
    assert row["suggested"] == 5 and row["kept"] == 3 and row["dropped"] == 2
    assert "kept_modified" not in row       # omitted at its default
    assert "residual_lines" not in row      # not supplied ⇒ absent (the version gate)
    assert row["schema_ver"] == 1


def test_residual_lines_is_the_one_count_written_at_zero():
    """Its default is the `None` *omit* sentinel, not 0 — so a caller that does not
    line-match writes the pre-v2 row exactly, while a caller that does can record a
    real zero. Absent and zero are different facts and must stay distinguishable."""
    assert schema.PROVENANCE_ZERO_BEARING_COUNTS == ("residual_lines",)
    assert "residual_lines" in schema.PROVENANCE_COUNT_FIELDS
    omitted = schema.make_provenance(sha="abc1234", files=["a.py"])
    assert tuple(omitted) == schema.PROVENANCE_FIELDS      # byte-identical to pre-v2
    zero = schema.make_provenance(sha="abc1234", files=["a.py"], residual_lines=0)
    assert zero["residual_lines"] == 0
    assert schema.make_provenance(sha="abc1234", files=["a.py"],
                                  residual_lines=7)["residual_lines"] == 7


def test_the_write_boundary_passes_a_zero_through_and_drops_a_none():
    """`originrecord.record`'s `**counts` filter must not pre-empt the factory's
    omit-vs-write decision, and must not `int(None)` inside a never-raising path."""
    from cage import originrecord
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        assert originrecord.record_transcript(root, sha="abc1234", files=["a.py"],
                                              agent="claude-code", session_id="s1",
                                              agent_lines=4, residual_lines=0)
        assert originrecord.record_transcript(root, sha="def5678", files=["b.py"],
                                              agent="claude-code", session_id="s2",
                                              agent_lines=4, residual_lines=None)
        rows = {r["sha"]: r for r in ledger.provenance(root)}
        assert rows["abc1234"]["residual_lines"] == 0
        assert "residual_lines" not in rows["def5678"]


def test_residual_lines_is_the_not_the_agent_side_of_this_rows_own_files(repo, tmp_path):
    """`_seed`'s commit adds 5 lines to mod.py: 4 clear the gate (`}` does not), and
    2 of those matched the agent. So the row's residual is the other 2 — scoped to the
    files THIS row landed, never the commit's `unattributed` bucket."""
    tr, _sha = _seed(repo, tmp_path)
    root = tmp_path / "ledger"
    authorcapture.capture(root, [tr], repo=repo, cursor={})
    row = ledger.provenance(root)[0]
    assert row["agent_lines"] == 2
    assert row["residual_lines"] == 2


def test_a_zero_residual_is_written_and_survives_the_row_round_trip(repo, tmp_path):
    """THE deviation from omitted-at-0, and it must be real rather than accidental.

    Everything matchable in the commit matched the agent, so the residual is a genuine
    0 — and `0` must reach disk, because absence of the key is what marks a row as
    predating the count. If this ever regresses to an omitted key, every such chat
    silently drops from `agent%` to `—` and reads as "no evidence"."""
    body = "def only_the_agent():\n    return 'wrote every line here'\n"
    tr = _transcript(tmp_path / "logs" / "sess-z.jsonl", "sess-z", [
        {"ts": "2026-07-01T09:00:00.000Z", "tool": "Write",
         "file": str(repo / "solo.py"), "content": body}])
    _commit(repo, {"solo.py": body}, "2026-07-01T10:00:00+00:00")
    root = tmp_path / "ledger"
    assert authorcapture.capture(root, [tr], repo=repo, cursor={})["rows"] == 1
    row = ledger.provenance(root)[0]
    assert row["agent_lines"] == 2
    assert "residual_lines" in row, "a zero residual was omitted — the version gate is broken"
    assert row["residual_lines"] == 0
    # And it survives the jsonl round-trip, not just the in-memory dict.
    assert json.loads(json.dumps(row))["residual_lines"] == 0


def test_the_residual_is_floored_at_zero_and_never_negative():
    assert authorcapture._residual([], [], 0) == 0
    m = linematch.FileMatch("a.py", linematch.KEPT, added_matchable=3, agent_lines=9)
    assert authorcapture._residual([m], ["a.py"], 9) == 0       # floored, not -6
    assert authorcapture._residual([m], ["a.py"], 1) == 2
    # A file the row did not land contributes nothing — that is commit scope, not ours.
    assert authorcapture._residual([m], [], 0) == 0


def test_chat_sums_reconcile_with_the_per_commit_buckets(repo, tmp_path):
    """The arbiter check (FORMULAS §2.14): a chat's `agent_lines`/`residual_lines` must
    equal the `agent`/`human~` buckets `commitview` derives for that session's commits.
    Two derivations of one fact that disagree would make the friendlier surface a lie —
    so this asserts across the seam rather than re-implementing either side."""
    from cage import chats, commitview
    from cage.policy import load as load_policy
    tr, sha = _seed(repo, tmp_path)
    root = tmp_path / "ledger"
    authorcapture.capture(root, [tr], repo=repo, cursor={})

    prov = ledger.provenance(root)
    buckets = commitview._buckets(linematch.commit_diff(repo, sha), prov)

    (root / ".cage" / "ledger").mkdir(parents=True, exist_ok=True)
    ledger.append(paths.Footprint(root).calls, schema.make_call(
        route="chat", provider="anthropic", model="claude-sonnet-4-6", tokens_in=10,
        agent="claude-code", session="sess-a", ts="2026-07-01T09:00:00Z", call_id="c1"))
    row = chats.summarize(root, load_policy(paths.Footprint(root).policy))["rows"][0]

    assert row["agent_lines"] == buckets["agent"] == 2
    assert row["residual_lines"] == buckets["human"] == 2
    assert row["agent_pct"] == 50.0


def test_record_drops_unknown_count_keys():
    """The substrate contract closes at the write boundary, not at the factory —
    a typo must never smuggle a field into the row."""
    from cage import originrecord
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        assert originrecord.record_transcript(root, sha="abc1234", files=["a.py"],
                                              agent="claude-code", kept=2,
                                              keptt=99, session_id="s")
        row = ledger.provenance(root)[0]
        assert row["kept"] == 2 and "keptt" not in row


# ── policy ────────────────────────────────────────────────────────────────────

def test_authorship_switches_default_on_and_are_overridable(monkeypatch):
    assert policy.authorship_estimate_hours({}) is True
    assert policy.authorship_max_est_gap({}) == "4h"
    assert policy.authorship_estimate_hours({"authorship": {"estimate_hours": False}}) is False
    assert policy.authorship_max_est_gap({"authorship": {"max_est_gap": "2d"}}) == "2d"
    monkeypatch.setenv("CAGE_AUTHORSHIP_ESTIMATE", "0")
    assert policy.authorship_estimate_hours({}) is False


def test_a_malformed_gap_falls_back_rather_than_widening_the_guard():
    """A cap nobody can parse must not become no cap at all."""
    assert policy.authorship_max_est_gap({"authorship": {"max_est_gap": "soon"}}) == "4h"
    assert policy.authorship_max_est_gap({"authorship": {"max_est_gap": ""}}) == "4h"


def test_the_bundled_policy_documents_the_authorship_table():
    text = policy.default_toml()
    assert "[authorship]" in text and "estimate_hours" in text
    assert "max_est_gap" in text
    # Shipped commented — the defaults live in code and upgrade with the package.
    assert "\n[authorship]\n" not in text


# ── the import sweep is opt-in and cannot move a money number ─────────────────

def test_glob_source_is_the_one_glob(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    (d / "a.jsonl").write_text("", encoding="utf-8")
    (d / "b.txt").write_text("", encoding="utf-8")
    assert [p.name for p in importcmd.glob_source(d, "*.jsonl")] == ["a.jsonl"]
    assert importcmd.glob_source(d, []) == []
    assert importcmd.glob_source(tmp_path / "absent", "*.jsonl") == []


def test_capture_is_switchable_off_entirely(repo, tmp_path, monkeypatch):
    """The widest PII surface cage has gets its own opt-out: metering spend and
    letting cage read your diffs are separate consents."""
    tr, _sha = _seed(repo, tmp_path)
    root = tmp_path / "ledger"
    monkeypatch.setenv("CAGE_AUTHORSHIP", "0")
    assert authorcapture.capture(root, [tr], repo=repo, cursor={})["skipped"] == "disabled"
    assert ledger.provenance(root) == []
    monkeypatch.delenv("CAGE_AUTHORSHIP")
    assert authorcapture.capture(root, [tr], repo=repo, cursor={},
                                 pol={"authorship": {"capture": False}})["skipped"] == "disabled"
    assert ledger.provenance(root) == []


def test_import_claude_without_the_cursor_never_writes_provenance(repo, tmp_path,
                                                                  monkeypatch):
    """Capture of CALLS is byte-identical whether or not authorship runs — the pass is
    strictly additive and reaches only `provenance.jsonl`."""
    tr, _sha = _seed(repo, tmp_path)
    monkeypatch.chdir(repo)   # the pass anchors on the CWD's repo, by design

    class A:
        path = None
        project = None
        since = None

    root = tmp_path / "ledger"
    pol = {"sources": {"claude": {"paths": [str(tr.parent)], "glob": "*.jsonl",
                                  "replace": True}}}
    n, _m = importcmd.import_claude(root, A(), pol=pol)
    assert n > 0                                  # calls captured
    assert ledger.provenance(root) == []          # authorship did not run

    # Opting in adds provenance and changes NOT ONE call row.
    before = [json.dumps(c, sort_keys=True) for c in ledger.calls(root)]
    importcmd.import_claude(root, A(), pol=pol, authorship_cursor={})
    assert [json.dumps(c, sort_keys=True) for c in ledger.calls(root)] == before
    assert len(ledger.provenance(root)) == 1


# ── P3.2: coverage is judged over THIS repo's edits only ──────────────────────

def test_an_edit_in_another_repo_never_holds_this_transcript_uncovered(repo, tmp_path):
    """`_uncovered` was handed the raw parse result with no repo filter, while
    `_repo_relative` was applied only to bucketing. So an edit in a DIFFERENT repo,
    newer than this repo's newest commit, kept the transcript permanently uncovered —
    and on a repo whose last commit is old, nearly every transcript on the machine has
    some newer edit somewhere. The cursor never advanced and every sweep re-parsed
    every file, forever."""
    _commit(repo, {"seed.txt": "0\n"}, "2026-07-01T08:00:00+00:00")
    elsewhere = tmp_path / "some-other-project"
    elsewhere.mkdir()
    tr = _transcript(tmp_path / "logs" / "sess-x.jsonl", "sess-x", [
        # Inside this repo, and already committed above ⇒ covered.
        {"ts": "2026-07-01T07:00:00.000Z", "tool": "Write",
         "file": str(repo / "seed.txt"), "content": "0\n"},
        # A LATER edit, but in a repo this sweep knows nothing about.
        {"ts": "2026-07-01T09:00:00.000Z", "tool": "Write",
         "file": str(elsewhere / "unrelated.py"), "content": "x = 1\n"}])
    root, cursor = tmp_path / "ledger", {}

    first = authorcapture.capture(root, [tr], repo=repo, cursor=cursor)
    assert first["files_read"] == 1
    assert first["uncovered"] == 0, "another repo's edit held this transcript open"
    # The point of the fix: the cursor advances, so the steady state is a no-op.
    assert authorcapture.capture(root, [tr], repo=repo, cursor=cursor)["files_read"] == 0


def test_an_in_repo_edit_after_the_newest_commit_still_holds_it_open(repo, tmp_path):
    """The control — the filter must not have turned coverage into "always covered".
    An edit in THIS repo awaiting a commit is exactly what `uncovered` is for."""
    _commit(repo, {"seed.txt": "0\n"}, "2026-07-01T08:00:00+00:00")
    tr = _transcript(tmp_path / "logs" / "sess-y.jsonl", "sess-y", [
        {"ts": "2026-07-01T09:00:00.000Z", "tool": "Write",
         "file": str(repo / "later.py"), "content": "value = 'landed later on'\n"}])
    root, cursor = tmp_path / "ledger", {}

    assert authorcapture.capture(root, [tr], repo=repo, cursor=cursor)["uncovered"] == 1
    assert authorcapture.capture(root, [tr], repo=repo, cursor=cursor)["files_read"] == 1


def test_the_empty_newest_branch_is_unreachable_from_capture(repo, tmp_path):
    """The handoff asked for the `newest == ""` interaction to be asserted. It cannot
    be reached through `capture()`: a repo with no commits short-circuits at
    `skipped="no-commits"` **before** any transcript is parsed, so `_uncovered` never
    runs with an empty `newest`. Recorded here rather than left looking like coverage —
    a test that appears to exercise a branch it cannot reach is worse than none.

    The branch is therefore defensive only, and it is unit-tested directly below."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    tr = _transcript(tmp_path / "logs" / "sess-z.jsonl", "sess-z", [
        {"ts": "2026-07-01T09:00:00.000Z", "tool": "Write",
         "file": str(elsewhere / "unrelated.py"), "content": "x = 1\n"}])

    res = authorcapture.capture(tmp_path / "ledger", [tr], repo=repo, cursor={})
    assert res["skipped"] == "no-commits"
    assert res["files_read"] == 0


def test_uncovered_with_no_newest_commit_reads_the_filtered_list(repo, tmp_path):
    """The defensive branch, exercised where it actually lives. `_uncovered` falls back
    to `bool(edits)` when there is no newest commit — and because the caller now passes
    the IN-REPO subset, a transcript that touched only other projects has nothing here
    to wait for. Both halves asserted so the filter and the fallback stay in step."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    outside = [{"ts": "2026-07-01T09:00:00.000Z", "file": str(elsewhere / "u.py")}]
    inside = [{"ts": "2026-07-01T09:00:00.000Z", "file": str(repo / "a.py")}]

    assert authorcapture._in_repo(outside, repo) == []
    assert authorcapture._in_repo(inside, repo) == inside
    assert authorcapture._uncovered(authorcapture._in_repo(outside, repo), "") is False
    assert authorcapture._uncovered(authorcapture._in_repo(inside, repo), "") is True
    # Unfiltered — the pre-fix call — would have held it open on another repo's work.
    assert authorcapture._uncovered(outside, "") is True


# ── P3.5: paths git does not print plainly ────────────────────────────────────
#
# There was NO non-ASCII path fixture anywhere in `tests/` before this. Both defects
# below are invisible to an ASCII-only corpus, and both end the same way: `commit_diff`
# returns no `added` entry for the file, so `match_commit` scores every line the agent
# genuinely landed as **DROPPED** — three maps keyed three different ways for one file.

def _quoted_path_repo(repo):
    """A commit touching a non-ASCII path and a path with a space — the two shapes git
    does not print verbatim."""
    return _commit(repo, {"café.py": "value = 'ünïcode content here'\n",
                          "a b.py": "spaced = 'a path with a space in it'\n"},
                   "2026-07-01T10:00:00+00:00")


def test_a_non_ascii_path_is_read_not_c_quoted(repo):
    """With git's default `core.quotePath`, `+++ "b/caf\\303\\251.py"` never matches
    `_DIFF_FILE`. The flag has to be set INSIDE `_git` (and before the subcommand,
    the only position git accepts), so a new git read cannot forget it."""
    from cage import linematch
    sha = _quoted_path_repo(repo)
    diff = linematch.commit_diff(repo, sha)

    assert "café.py" in diff["added"], diff["added"].keys()
    assert "café.py" in diff["numstat"]
    assert not any(k.startswith('"') or "\\3" in k for k in diff["added"]), \
        "a C-quoted path leaked through as a key"


def test_a_path_with_a_space_loses_gits_disambiguating_tab(repo):
    """The half `core.quotePath=false` does NOT fix, and it is a separate defect: git
    appends a literal tab to `+++ b/a b.py`, so the capture was `"a b.py\\t"` — a key
    that can never match the numstat name `a b.py`."""
    from cage import linematch
    sha = _quoted_path_repo(repo)
    diff = linematch.commit_diff(repo, sha)

    assert "a b.py" in diff["added"], diff["added"].keys()
    assert not any(k.endswith("\t") for k in diff["added"])
    # The two maps must agree — disagreeing is exactly what scored a file DROPPED.
    assert set(diff["added"]) == set(diff["numstat"])


def test_an_agents_lines_in_such_a_file_are_KEPT_not_DROPPED(repo):
    """The consequence, asserted where a reader would feel it: before the fix these
    landed lines scored DROPPED — cage reporting the agent proposed work that never
    shipped, when it shipped in a file git spelled differently."""
    from cage import linematch
    sha = _quoted_path_repo(repo)
    diff = linematch.commit_diff(repo, sha)
    proposed = {"café.py": ["value = 'ünïcode content here'"],
                "a b.py": ["spaced = 'a path with a space in it'"]}

    _matches, totals = linematch.match_commit(proposed, diff["added"], diff["binary"])
    assert totals["kept"] == 2, totals
    assert totals["dropped"] == 0, totals


def test_numstat_reads_a_non_ascii_path_too(repo):
    """`originrecord._git` is a second helper with its own subprocess call — the flag
    belongs in both, or `cage authorship origin` disagrees with the line matcher about
    which files a commit touched."""
    from cage import originrecord
    sha = _quoted_path_repo(repo)
    names = {f for f, _a, _r in originrecord.commit_numstat(repo, sha)}
    assert {"café.py", "a b.py"} <= names, names


def test_a_non_ascii_top_level_dir_is_not_stamped_mangled(repo):
    """A THIRD site, not in the handoff's list: `tasks.git_snapshot` splits
    `git diff --name-only` on "/" for its top-level-dirs-only PII guard. C-quoting
    makes that dir `"caf\\303\\251` — leading quote included — and `scope_for` stamps it
    onto ledger rows, where it is persisted and never rewritten."""
    from cage import tasks
    _commit(repo, {"café/x.py": "x = 1\n"}, "2026-07-01T10:00:00+00:00")
    # An UNSTAGED edit — `git diff --name-only` compares the work tree to the index.
    (repo / "café" / "x.py").write_text("x = 2\n", encoding="utf-8")

    assert tasks.git_snapshot(repo).get("dirs") == ["café"]
    assert tasks.scope_for(repo) == "café"


# ── P4.1: a rename's numstat name is not a path ───────────────────────────────

def test_numstat_path_resolves_every_rename_shape_git_emits():
    """`git show --numstat` renders a rename in the NAME column, in two shapes, and
    neither can key-match a `+++ b/<path>` line. Both degenerate braced forms are real
    and are what the `/`-collapse exists for — a move *into* a dir has an empty old
    side, a move *out of* one has an empty new side."""
    from cage import linematch
    assert linematch.numstat_path("old.py => new.py") == "new.py"
    assert linematch.numstat_path("top.py => sub/top.py") == "sub/top.py"
    assert linematch.numstat_path("d/{keep.py => moved.py}") == "d/moved.py"
    assert linematch.numstat_path("d/{a => b}/f.py") == "d/b/f.py"
    assert linematch.numstat_path("{ => d}/x.py") == "d/x.py"
    assert linematch.numstat_path("d/{a => }/x.py") == "d/x.py"
    # A path with no rename in it is returned untouched.
    assert linematch.numstat_path("plain.py") == "plain.py"
    assert linematch.numstat_path("café.py") == "café.py"


def test_a_renamed_file_keys_to_where_it_landed(repo):
    """The defect, end to end: `numstat` keyed the arrow string and `added` keyed the
    real path, so a renamed file's counts went to a phantom entry and the file itself
    got none. `cage insights commit` then rendered `old.py => new.py` as a path."""
    from cage import linematch
    _commit(repo, {"old.py": "alpha beta gamma\ndelta epsilon zeta\n"},
            "2026-07-01T09:00:00+00:00")
    _git(repo, "mv", "old.py", "new.py")
    (repo / "new.py").write_text(
        "alpha beta gamma\ndelta epsilon zeta\nlambda mu nu added\n", encoding="utf-8")
    sha = _commit(repo, {}, "2026-07-01T10:00:00+00:00")

    diff = linematch.commit_diff(repo, sha)
    assert "new.py" in diff["numstat"], diff["numstat"]
    assert not any("=>" in k for k in diff["numstat"]), diff["numstat"]
    # The two maps agree again — disagreeing is the whole defect.
    assert set(diff["added"]) <= set(diff["numstat"])


def test_a_renamed_file_scores_KEPT_not_DROPPED(repo):
    """The consequence a reader feels: the agent's landed line was scored against a key
    nothing else used, so the file read as never having shipped."""
    from cage import linematch
    _commit(repo, {"old.py": "alpha beta gamma\n"}, "2026-07-01T09:00:00+00:00")
    _git(repo, "mv", "old.py", "new.py")
    (repo / "new.py").write_text("alpha beta gamma\nlambda mu nu added\n",
                                 encoding="utf-8")
    sha = _commit(repo, {}, "2026-07-01T10:00:00+00:00")

    diff = linematch.commit_diff(repo, sha)
    _m, totals = linematch.match_commit({"new.py": ["lambda mu nu added"]},
                                        diff["added"], diff["binary"])
    assert totals["kept"] == 1 and totals["dropped"] == 0, totals


def test_originrecord_numstat_agrees_with_the_line_matcher_on_a_rename(repo):
    """The two modules keep duplicate `_NUMSTAT` patterns, which is exactly how this
    class of bug survives — so they share ONE rename parser."""
    from cage import linematch, originrecord
    _commit(repo, {"d/keep.py": "x = 1\n"}, "2026-07-01T09:00:00+00:00")
    _git(repo, "mv", "d/keep.py", "d/moved.py")
    sha = _commit(repo, {}, "2026-07-01T10:00:00+00:00")

    names = {f for f, _a, _r in originrecord.commit_numstat(repo, sha)}
    assert names == set(linematch.commit_diff(repo, sha)["numstat"]) or not names
    assert not any("=>" in n for n in names), names
    assert "d/moved.py" in names, names


# ── P4.2: an Edit's context lines are not proposals ───────────────────────────

def test_context_lines_are_transported_raw_never_normalized_in_transcript(tmp_path):
    """`transcript` sits outside `linematch`'s normalizer boundary (rule 1), so it may
    only carry `old_string` verbatim. If it ever starts comparing or normalizing, there
    are two matchers and they will drift."""
    from cage import transcript
    tr = _transcript(tmp_path / "logs" / "s.jsonl", "s", [
        {"ts": "2026-07-01T09:00:00.000Z", "tool": "Edit",
         "file": str(tmp_path / "a.py"),
         "old_string": "  anchor line above\n  the changed line\n",
         "new_string": "  anchor line above\n  the NEW changed line\n"}])
    edit = transcript.parse_edits(tr, session="s")[0]

    assert edit["context"] == ["  anchor line above", "  the changed line"]
    assert edit["lines"] == ["  anchor line above", "  the NEW changed line"]


def test_subtract_context_removes_only_restated_lines():
    """The subtraction consumes 1:1 like `match_file`, and never touches a sub-gate
    line — those are not matchable on either side, and removing them would quietly move
    lines out of `unknown`, which is never redistributed."""
    from cage import linematch
    proposed = ["anchor line above", "the NEW changed line", "anchor line above"]
    context = ["anchor line above", "the old changed line"]
    assert linematch.subtract_context(proposed, context) == \
        ["the NEW changed line", "anchor line above"]     # one of two copies removed

    # Normalization is the same one both sides use — indentation must not defeat it.
    assert linematch.subtract_context(["    x = compute()"], ["x = compute()"]) == []
    # Sub-gate lines survive on both sides.
    assert linematch.subtract_context(["}", "}"], ["}"]) == ["}", "}"]
    # No context ⇒ untouched.
    assert linematch.subtract_context(["a b c d"], []) == ["a b c d"]


def test_an_edits_unchanged_context_no_longer_inflates_suggested(repo, tmp_path):
    """The defect end to end. `old_string` was read NOWHERE in the package, so every
    anchor line an `Edit` re-stated entered `suggested` — and `kept_modified` with it,
    via `modified = suggested - kept`."""
    anchor = "def existing_function(argument):"
    added = "    freshly_authored_line = 1"
    _commit(repo, {"m.py": f"{anchor}\n    pass\n"}, "2026-07-01T09:00:00+00:00")
    tr = _transcript(tmp_path / "logs" / "s.jsonl", "s", [
        {"ts": "2026-07-01T09:30:00.000Z", "tool": "Edit", "file": str(repo / "m.py"),
         "old_string": f"{anchor}\n    pass\n",
         "new_string": f"{anchor}\n{added}\n    pass\n"}])
    _commit(repo, {"m.py": f"{anchor}\n{added}\n    pass\n"},
            "2026-07-01T10:00:00+00:00")

    res = authorcapture.capture(tmp_path / "ledger", [tr], repo=repo, cursor={})
    assert res["rows"] == 1
    row = ledger.provenance(tmp_path / "ledger")[0]
    # Only the ONE genuinely new line is a proposal; the re-stated anchor is not.
    assert row["suggested"] == 1, row
    assert row["kept"] == 1, row
    assert not row.get("kept_modified"), row


def test_a_multiedit_subtracts_each_blocks_own_context(repo, tmp_path):
    """`MultiEdit` carries one `old_string` per edit; all of them are context."""
    from cage import transcript
    tr = _transcript(tmp_path / "logs" / "s.jsonl", "s", [
        {"ts": "2026-07-01T09:00:00.000Z", "tool": "MultiEdit",
         "file": str(repo / "m.py"),
         "edits": [{"old_string": "first anchor line\n", "new_string": "first anchor line\nbrand new alpha\n"},
                   {"old_string": "second anchor line\n", "new_string": "second anchor line\nbrand new beta\n"}]}])
    e = transcript.parse_edits(tr, session="s")[0]
    from cage import linematch
    assert linematch.subtract_context(e["lines"], e["context"]) == \
        ["brand new alpha", "brand new beta"]


def test_write_and_notebook_have_no_context_to_subtract(tmp_path):
    """Stated, not papered over: a `Write` carries a whole file body and a
    `NotebookEdit` a whole cell — there is no `old_string`, so their unchanged lines
    stay unsubtractable and their `suggested` stays inflated. There is no evidence in
    the transcript to fix it with."""
    from cage import transcript
    tr = _transcript(tmp_path / "logs" / "w.jsonl", "w", [
        {"ts": "2026-07-01T09:00:00.000Z", "tool": "Write",
         "file": str(tmp_path / "a.py"), "content": "line one here\nline two here\n"}])
    assert transcript.parse_edits(tr, session="w")[0]["context"] == []
