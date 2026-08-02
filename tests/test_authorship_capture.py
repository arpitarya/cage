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
    return _git(repo, "rev-parse", "--short", "HEAD")


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
    assert row["schema_ver"] == 1


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
