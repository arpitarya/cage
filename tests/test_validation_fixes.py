"""Regression tests for the fixes found by the disposable-repo validation pass.

Each test pins a specific finding so it can't silently regress:
  A. concurrent import sweeps must not double-count one turn (the import lock);
  B. `cage export --json` is an alias for `--format json`;
  C. `cage demo` is idempotent — re-running never doubles the §4.4 tables;
  D. `cage setup --project-only` scaffolds `.cage/` with no agent flag.
"""
from __future__ import annotations

import json
import threading

import pytest

from cage import cli, demo, importcmd, ledger, paths, schema
from cage import metering as meter


# ── A. import lock: concurrent sweeps dedupe one turn ───────────────────────────
@pytest.mark.skipif(importcmd._fcntl is None, reason="POSIX flock unavailable")
def test_import_lock_serializes_concurrent_appends(proj):
    """Two sweeps racing on the read-check-append section must land the row once.
    Mirrors the fixed critical section in `importcmd.run` (build `seen`, then append)."""
    root = proj
    foot = paths.Footprint(root)
    row = schema.make_call(route="chat", provider="anthropic", model="claude-opus-4-8",
                           tokens_in=10, tokens_out=1, call_id="c_dup_regression")
    barrier = threading.Barrier(2)

    def sweep():
        barrier.wait()  # maximise overlap on the critical section
        with importcmd._import_lock(foot):
            seen = {c.get("id") for c in ledger.calls(root)}
            if row["id"] not in seen:
                ledger.append_row(root, "calls", row)

    threads = [threading.Thread(target=sweep) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ids = [c["id"] for c in ledger.calls(root)]
    assert ids.count("c_dup_regression") == 1


def test_import_lock_is_failopen(proj):
    """The lock never raises into the capture path — it just yields."""
    foot = paths.Footprint(proj)
    with importcmd._import_lock(foot):
        pass  # no exception = fail-open contract holds


# ── B. cage export --json alias ─────────────────────────────────────────────────
def test_export_json_alias_is_summary(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    meter._policy_for.cache_clear()
    demo.seed(proj)
    assert cli.main(["export", "--json", "--no-import"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "total" in payload and payload["total"]["calls"] == 1


# ── C. cage demo idempotency ────────────────────────────────────────────────────
def test_demo_seed_is_idempotent(proj):
    first = demo.seed(proj)
    second = demo.seed(proj)
    assert first == second
    calls = [c for c in ledger.calls(proj) if c.get("task") == demo.TASK]
    receipts = [r for r in ledger.receipts(proj) if r.get("task") == demo.TASK]
    assert len(calls) == 1 and len(receipts) == 3  # not doubled


def test_cli_demo_twice_keeps_444(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    meter._policy_for.cache_clear()
    assert cli.main(["demo"]) == 0
    assert cli.main(["demo"]) == 0  # second run is a no-op
    capsys.readouterr()
    assert cli.main(["attrib"]) == 0
    out = capsys.readouterr().out
    assert "41,400" in out  # §4.4 total, not 82,800


# ── D. cage setup --project-only scaffolds standalone ───────────────────────────
def test_setup_project_only_scaffolds_without_agent(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    rc = cli.main(["setup", "--project-only", "--no-graphify"])
    assert rc == 0
    assert (proj / ".cage").is_dir()
    out = capsys.readouterr().out
    assert ".cage/ ready" in out


# ── E. the global ~/.cage is never a *project* root (full-test-plan finding #1) ──
def test_global_cage_is_not_a_project_root(tmp_path, monkeypatch):
    """With a global ledger at $CAGE_HOME/.cage, a fresh dir under it must NOT
    resolve to the home as its project — `cage init` there was re-initialising the
    global instead of scaffolding the project's own `.cage/` (§3.7 precedence:
    override → project → global; the global is a fallback tier, not a project)."""
    home = tmp_path / "home"
    (home / ".cage").mkdir(parents=True)          # the machine-wide global sink
    monkeypatch.setenv("CAGE_HOME", str(home))
    project = home / "my_programs" / "newproj"
    project.mkdir(parents=True)
    assert paths.find_project_root(project) is None            # global ≠ project
    assert paths.resolve_root(project) == home                 # …but stays the sink
    assert "global" in paths.active_ledger_source(project)     # labelled honestly
    (project / ".cage").mkdir()                                # now a real project
    assert paths.find_project_root(project) == project
    assert "project" in paths.active_ledger_source(project)


def test_real_home_cage_is_not_a_project_root_under_cage_home(tmp_path, monkeypatch):
    """With CAGE_HOME redirected (tests, the dummyrepo runner), the *real* `~/.cage`
    is still a global sink — never a project. Without this, any sandbox under $HOME
    resolved its "project" to the home dir and wrote fixture/study rows into the
    user's real global ledger (2026-07 manual validation, S1/S2/S3/S9 fallout)."""
    real_home = tmp_path / "realhome"
    (real_home / ".cage").mkdir(parents=True)                  # the user's real global
    monkeypatch.setattr(paths.Path, "home", staticmethod(lambda: real_home))
    monkeypatch.setenv("CAGE_HOME", str(tmp_path / "iso"))     # redirected global
    sandbox = real_home / "my_programs" / "sandbox-repo"
    sandbox.mkdir(parents=True)
    assert paths.find_project_root(sandbox) is None            # home ≠ project
    assert paths.resolve_root(sandbox) == tmp_path / "iso"     # the redirect wins


def test_hook_in_no_project_dir_writes_global_not_a_stray_footprint(tmp_path, monkeypatch):
    """A hook firing in a dir with no project `.cage/` must capture into the global
    ledger — the old `find_project_root or cwd` fallback scaffolded a stray `.cage/`
    in the session's cwd and split the ledger (2026-07 manual validation: a Claude
    session in a fresh dir left `.cage/ledger/` there and 0 rows in `~/.cage`)."""
    import json
    from cage import hooks
    home = tmp_path / "home"
    (home / ".cage").mkdir(parents=True)
    monkeypatch.setenv("CAGE_HOME", str(home))
    monkeypatch.delenv("CAGE_BASE", raising=False)
    nowhere = tmp_path / "no-project-session-dir"
    nowhere.mkdir()
    assert hooks._root({"cwd": str(nowhere)}) == home          # global, not cwd
    # And metering's library default follows the same precedence.
    from cage import ledger, metering
    monkeypatch.chdir(nowhere)
    assert metering.record_call(route="chat", provider="anthropic",
                                model="claude-opus-4-8", tokens_in=10)
    assert not (nowhere / ".cage").exists()                    # no stray footprint
    assert len(ledger.calls(home)) == 1                        # landed globally


# ── F. malformed --since is a typed error, not a silent no-filter (finding #2) ──
def test_since_garbage_is_typed_error(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    assert cli.main(["report", "--since", "garbage"]) == 1
    err = capsys.readouterr().err
    assert "invalid --since 'garbage'" in err and "7d" in err
    assert cli.main(["report", "--since", "7d"]) == 0  # valid forms untouched
    assert ledger.valid_since(None) and ledger.valid_since("2w")
    assert not ledger.valid_since("next tuesday")
