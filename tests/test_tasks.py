"""Stage-3 task record: fail-open git snapshot + last-write-wins (criteria 10, 7)."""
from __future__ import annotations

import subprocess

import pytest

from cage import tasks


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
    return run


# ── criterion 10 — snapshot is fail-open in a non-repo, never raises
def test_snapshot_non_repo_omits_fields(proj):
    snap = tasks.git_snapshot(proj)
    assert snap == {} or "commit" not in snap  # no .git ⇒ nothing, no exception


def test_snapshot_in_repo_collects_sha_and_branch(proj):
    _git_init(proj)
    snap = tasks.git_snapshot(proj)
    assert "commit" in snap and len(snap["commit"]) >= 4
    assert snap.get("branch")  # a named branch, not "HEAD"


def test_snapshot_detached_head_omits_branch(proj):
    run = _git_init(proj)
    sha = subprocess.run(("git", "-C", str(proj), "rev-parse", "HEAD"),
                         capture_output=True, text=True).stdout.strip()
    run("checkout", sha)  # detached
    snap = tasks.git_snapshot(proj)
    assert "branch" not in snap  # detached ⇒ omitted, never the literal "HEAD"


def test_snapshot_diff_counts_and_top_level_dirs(proj):
    run = _git_init(proj)
    (proj / "app").mkdir()
    (proj / "app" / "b.py").write_text("y = 2\n")
    run("add", "app/b.py")
    (proj / "a.py").write_text("x = 1\nx = 2\n")  # unstaged edit
    snap = tasks.git_snapshot(proj)
    # diff stats are present and numeric; dirs are top-level only, never full paths
    assert isinstance(snap.get("files_changed"), int)
    if "dirs" in snap:
        assert all("/" not in d for d in snap["dirs"])


# ── criterion 10 — tasks.jsonl last-write-wins by id; re-closing is idempotent
def test_last_write_wins_and_idempotent(proj):
    tasks.record(proj, "t1", type="feature", outcome="redo", snapshot=False)
    tasks.record(proj, "t1", outcome="ok", snapshot=False)  # re-close
    latest = tasks.read(proj)
    assert set(latest) == {"t1"}            # one logical task, not two
    assert latest["t1"]["outcome"] == "ok"  # newest wins
    assert latest["t1"]["type"] == "feature"  # earlier fields carried forward


# ── criterion 7 — PII guard: no message, author, or paths beyond top-level dirs
def test_no_pii_fields_recorded(proj):
    _git_init(proj)
    tasks.record(proj, "t1", type="feature")
    row = tasks.read(proj)["t1"]
    forbidden = {"message", "author", "email", "files", "paths", "diff", "content"}
    assert not (forbidden & set(row)), f"PII-risk field leaked: {forbidden & set(row)}"
