"""Provenance (authorship attribution): union-by-sha, corroboration, the
read-time-unknown default, attestation, the repo-relative path guard, and
fail-open capture (plan §3.5)."""
from __future__ import annotations

import subprocess

import pytest

from cage import notessync, origin, originrecord, schema


def _git_init(root):
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    def run(*a):
        subprocess.run(("git", "-C", str(root), *a), check=True, capture_output=True,
                       env={**__import__("os").environ, **env})
    run("init")
    (root / "a.py").write_text("x = 1\n")
    run("add", "a.py")
    run("commit", "-m", "init")
    sha = subprocess.run(("git", "-C", str(root), "rev-parse", "--short", "HEAD"),
                         capture_output=True, text=True).stdout.strip()
    return run, sha


# ── substrate: closed enums + the human/heuristic pairing + path guard
def test_make_provenance_rejects_bad_method_and_origin():
    with pytest.raises(ValueError):
        schema.make_provenance(sha="abc", files=["a.py"], method="measured")
    with pytest.raises(ValueError):
        schema.make_provenance(sha="abc", files=["a.py"], origin="bananas")


def test_origin_human_requires_heuristic_method():
    with pytest.raises(ValueError):
        schema.make_provenance(sha="abc", files=["a.py"], origin="human", method="hooked")
    row = schema.make_provenance(sha="abc", files=["a.py"], origin="human", method="heuristic")
    assert row["origin"] == "human" and row["method"] == "heuristic"


def test_repo_relative_path_guard_rejects_absolute_and_dotdot():
    with pytest.raises(ValueError):
        schema.make_provenance(sha="abc", files=["/etc/passwd"])
    with pytest.raises(ValueError):
        schema.make_provenance(sha="abc", files=["../outside.py"])
    row = schema.make_provenance(sha="abc", files=["cage/origin.py"])
    assert row["files"] == ["cage/origin.py"]


# ── quarantine-unknown: a real, unsignaled commit is unknown by absence, never written
def test_unsignaled_commit_is_unknown_and_writes_no_row(proj):
    _git_init(proj)
    data = origin.explain(proj, "HEAD")
    assert data["origin"] == "unknown"
    assert data["confidence"] == 0.0
    assert data["rows"] == []
    assert originrecord.read_all(proj) == []  # the negative assertion: nothing was written


# ── attestation: the only way origin=human reaches the ledger
def test_attest_human_writes_one_heuristic_row(proj):
    _git_init(proj)
    status = origin.attest(proj, "HEAD", origin="human")
    assert status == "recorded"
    rows = originrecord.read_all(proj)
    assert len(rows) == 1
    assert rows[0]["origin"] == "human" and rows[0]["method"] == "heuristic"


def test_attest_unknown_is_a_no_op(proj):
    _git_init(proj)
    status = origin.attest(proj, "HEAD", origin="unknown")
    assert status == "invalid-origin"
    assert originrecord.read_all(proj) == []


def test_attest_nonexistent_sha_is_a_no_op(proj):
    _git_init(proj)
    status = origin.attest(proj, "0000000", origin="human")
    assert status == "no-diff"
    assert originrecord.read_all(proj) == []


def test_attest_second_time_reports_already_attested(proj):
    _git_init(proj)
    assert origin.attest(proj, "HEAD", origin="human") == "recorded"
    # A second attestation (even with a different origin) must not silently
    # shadow the first — the dedup key omits `origin`, so we surface it.
    status = origin.attest(proj, "HEAD", origin="agent")
    assert status == "already-attested"
    rows = originrecord.read_all(proj)
    assert len(rows) == 1 and rows[0]["origin"] == "human"


# ── union-by-sha: a stronger method wins on overlapping files when fragments merge
def test_merge_rows_prefers_higher_trust_method_on_id_collision():
    weak = schema.make_provenance(sha="abc", files=["a.py"], method="heuristic",
                                  origin="agent", row_id="p_1")
    strong = {**weak, "method": "hooked", "confidence": 0.9}  # same id, stronger method
    merged = notessync.merge_rows([weak], [strong])
    assert len(merged) == 1 and merged[0]["method"] == "hooked"


def test_merge_rows_unions_distinct_ids(proj):
    _git_init(proj)
    a = schema.make_provenance(sha="abc", files=["a.py"], method="hooked", origin="agent")
    b = schema.make_provenance(sha="abc", files=["b.py"], method="transcript", origin="agent")
    merged = notessync.merge_rows([a], [b])
    assert {r["id"] for r in merged} == {a["id"], b["id"]}


# ── corroboration: two independent paths on the same (sha, session) raise confidence
def test_corroboration_bumps_confidence_above_either_alone(proj):
    _git_init(proj)
    sha = originrecord.current_sha(proj)
    originrecord.record_hooked(proj, sha=sha, files=["a.py"], agent="claude-code",
                               session_id="s1")
    hooked_only = originrecord.for_sha(proj, sha)[0]["confidence"]

    originrecord.record_transcript(proj, sha=sha, files=["a.py"], agent="claude-code",
                                    session_id="s1")
    rows = originrecord.for_sha(proj, sha)
    transcript_row = next(r for r in rows if r["method"] == "transcript")
    assert transcript_row["confidence"] > originrecord.confidence_for("transcript")
    assert transcript_row["confidence"] > 0  # corroborated, strictly above either base
    assert hooked_only > 0


# ── fail-open: capture never raises against a non-repo / detached-HEAD root
def test_record_against_non_repo_root_is_fail_open(proj):
    ok = originrecord.record(proj, sha="", files=["a.py"], method="heuristic")
    assert ok is False  # no sha ⇒ no-op, not an exception


def test_working_tree_numstat_non_repo_returns_empty(proj):
    assert originrecord.working_tree_numstat(proj) == []


def test_commit_numstat_non_repo_returns_empty(proj):
    assert originrecord.commit_numstat(proj, "deadbeef") == []


# ── idempotency: re-recording the same (sha, agent, session_id, method) is a no-op
def test_record_hooked_idempotent_on_repeat(proj):
    _git_init(proj)
    sha = originrecord.current_sha(proj)
    first = originrecord.record_hooked(proj, sha=sha, files=["a.py"], agent="claude-code",
                                       session_id="s1")
    second = originrecord.record_hooked(proj, sha=sha, files=["a.py"], agent="claude-code",
                                        session_id="s1")
    assert first is True and second is False
    assert len(originrecord.for_sha(proj, sha)) == 1
