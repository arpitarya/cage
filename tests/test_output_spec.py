"""Golden tests for the GATED output blocks in docs/adr/0002_cli.md (ADR-CLI).

`docs/cli-output-spec.md` and `tools/docgen` were absorbed into ADR-CLI and no
longer exist — ADR-CLI's "What the output looks like" section is the one place
documented and tested output live, and `tests/test_adr_output_blocks.py` is what
keeps that section honest against these same goldens (every GATED block byte-
identical to the fixture it cites; every CAPTURED block's invocation still live).

Every fixture under `tests/fixtures/goldens/` backs exactly one GATED block: the
first line is the invocation (`$ cage …`), the rest is the byte-exact stdout.
This test asserts the live output equals them.

Regenerate after an intentional rendering change:
    CAGE_BLESS_GOLDENS=1 python -m pytest tests/test_output_spec.py
then paste the new body into the matching GATED block in docs/adr/0002_cli.md.

The S1–S4 study fixtures went with the fleet study in v0.51 (STUDY-CUT); §4 is
deliberately left as a gap in the numbering rather than renumbered, so a golden
id in an old commit or changelog entry still means what it meant.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from cage import cli, metering as meter

import goldenseed as seed

GOLD = Path(__file__).parent / "fixtures" / "goldens"


def _bless() -> bool:
    return os.environ.get("CAGE_BLESS_GOLDENS") == "1"


def _check(name: str, argv: list[str], out: str) -> None:
    # Always prefixed, even for the bare `cage` invocation (argv=[]) — ADR-CLI shows
    # every GATED block with its `$ cage …` invocation line so the block is checkable
    # by test_adr_output_blocks.py; a bare invocation just renders `$ cage ` (trailing
    # space, no args).
    text = "$ cage " + " ".join(argv) + "\n" + out
    f = GOLD / f"{name}.txt"
    if _bless():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    assert f.exists(), f"golden {name} missing — CAGE_BLESS_GOLDENS=1 to create it"
    assert text == f.read_text(encoding="utf-8"), f"golden {name} drifted"


@pytest.fixture
def run(proj, monkeypatch, capsys):
    """Seeded-CLI runner: `run(seed_fn)(name, argv)` executes `cage argv` in an
    isolated project and asserts stdout against the named golden."""
    monkeypatch.chdir(proj)
    meter._policy_for.cache_clear()

    def _factory(seed_fn=None):
        if seed_fn is not None:
            seed_fn(proj)

        def _go(name: str, argv: list[str], expect_exit: int = 0) -> str:
            assert cli.main(argv) == expect_exit
            out = capsys.readouterr().out
            # A view that names a file does so under the per-test tmp root —
            # normalize to a placeholder so the golden stays byte-stable.
            for raw in {str(proj.resolve()), str(proj)}:
                out = out.replace(raw, "<project>")
            # Goldens are OS-independent doc artifacts; a Windows-native path prints
            # `<project>\.cage\policy.toml`. Fold separators to `/` so the one blessed
            # golden matches every OS (no golden legitimately contains a backslash).
            out = out.replace("\\", "/")
            _check(name, argv, out)
            return out
        _go.root = proj
        return _go
    return _factory


# ── the daily four (ADR-OUTPUT-GOLDENS) ────────────────────────────────────────

def test_H1_bare_cage(run):
    """The front door: `_ROOT_HELP` in cage/cli.py is a hardcoded constant (no ledger
    dependency), so an empty project is enough — this pins the constant itself."""
    go = run()
    out = go("H1", [])
    assert "daily:" in out and "groups (run any group name for its commands):" in out


def test_H2_import_nothing_wired(run):
    """The empty case is the one worth printing: three agents, zero calls, and a
    warning that names the cause rather than a silent success."""
    go = run()
    out = go("H2", ["import"])
    assert "no [sources] in cage.toml" in out
    assert out.count("imported 0 call(s)") == 3


def test_W1_setup_status(run):
    go = run()
    out = go("W1", ["setup", "--status"])
    assert "not wired" in out


def test_H4_query_saved(run):
    go = run()
    out = go("H4", ["query", "saved"])
    assert "GROSS" in out and "cage/savings.py" in out


# ── §1 · cage report ──────────────────────────────────────────────────────────

def test_I10_chats_titled(run):
    go = run(seed.chats_titled)
    out = go("I10a", ["insights", "chats"])
    assert "fix the flaky test" in out and "refactor the parser" in out
    assert "s_ct1" not in out                    # a real title replaces the id


def test_I10_chats_untitled_and_kiro(run):
    go = run(seed.chats_untitled)
    out = go("I10b", ["insights", "chats"])
    # kiro no longer renders here at all: it has no token spine, so its rows are
    # suppressed from `spend()` and the view shows a reason rather than a figure
    # (`ledger.ABSENT_SPINES`, USAGE-ONLY ADR 0011). The constant-session collapse
    # this asserted is still implemented — it simply has no rows to apply to.
    assert "kiro" not in out.split("agent%")[1]
    assert "s_cu2" in out                        # no title ⇒ the honest session id


def test_I10_chats_empty(run):
    go = run()
    out = go("I10c", ["insights", "chats"])
    assert "No chats recorded yet." in out


def test_I10_chats_truncated(run):
    go = run(seed.chats_truncated)
    out = go("I10d", ["insights", "chats"])
    assert "3 more chat(s) — --all to show" in out


def test_I11_insights_graphify(run):
    go = run(seed.graphify_chats)
    out = go("I11", ["insights", "graphify"])
    assert "saved%" in out and "67%" in out


def test_I12_insights_why(run):
    go = run(seed.why_call)
    out = go("I12", ["insights", "why", "c_why1"])
    assert "graphify" in out and "fux" in out and "compressor" in out
    assert "measured" in out and "modeled" in out


# ── §3 · cage prices ──────────────────────────────────────────────────────────

def _prices_project(root: Path) -> None:
    from cage import initcmd
    initcmd.run(root)
    assert cli.main(["prices", "set", "openai", "gpt-5.3-codex",
                     "--input", "2.50", "--output", "10.00",
                     "--cache-read", "0.25"]) == 0
    assert cli.main(["prices", "alias", "-", "copilot/auto",
                     "--to", "anthropic/claude-sonnet-4-6"]) == 0
    assert cli.main(["prices", "route-tool", "graphify",
                     "--to", "anthropic/claude-sonnet-4-6"]) == 0












# ── §5 · cage policy ──────────────────────────────────────────────────────────

def _old_policy_project(root: Path) -> None:
    from cage import initcmd, tomledit
    initcmd.run(root)
    tomledit.update_meta(root, {"policy_version": "0.19.0"})


def test_P5_policy_diff(run, capsys):
    go = run()
    _old_policy_project(go.root)
    capsys.readouterr()
    out = go("P5", ["policy", "diff"])
    assert "dry-run" in out or "nothing written" in out




# ── overview (bare cage — handoff §10) ────────────────────────────────────────

def test_goldens_deterministic_double_run(run, capsys):
    """Same ledger + same policy ⇒ same table, twice (the determinism law). Rendered
    through `insights chats` since SURFACE-CUT deleted `report`; the property under
    test is the renderer's freedom from clocks/random, not the particular view."""
    go = run(seed.wmh)
    seed.set_last_import(go.root, _now())
    assert cli.main(["insights", "chats"]) == 0
    a = capsys.readouterr().out
    assert cli.main(["insights", "chats"]) == 0
    assert a == capsys.readouterr().out


def _now() -> str:
    import datetime as _dt
    return (_dt.datetime.now(_dt.timezone.utc)
            .isoformat(timespec="seconds").replace("+00:00", "Z"))


# ── §HR1 · the commit surfaces (agent-vs-human v2) ───────────────────────────

def test_A1_commits_mixed(run, monkeypatch):
    """Every state the list view owes a reader, in one table: an attributed commit
    with all four buckets, two unattributed ones refusing with `—`, and the Σ row."""
    monkeypatch.setenv("CAGE_AUTHORSHIP", "1")
    go = run(seed.commits_mixed)
    out = go("A1", ["insights", "commits"])
    assert "$" not in out                            # the standing v1 guard
    assert out.count("—") >= 8                       # refusals render, never 0
    assert "Never redistributed, never a score" in out
    assert "50% /  33% /  17% /   0%" in out   # all four buckets exercised


def test_A2_commits_all_refused(run, monkeypatch):
    """An empty ledger: every cell refuses and the Σ row refuses with them."""
    monkeypatch.setenv("CAGE_AUTHORSHIP", "1")
    go = run(seed.commits_bare)
    out = go("A2", ["insights", "commits"])
    assert "no authorship rows recorded yet" in out
    import re as _re
    sigma = _re.split(r"\s{2,}", out.split("Σ")[1].split("\n")[0].strip())
    assert sigma[1:6] == ["—"] * 5, sigma   # the total refuses with its rows


def test_A3_commit_detail(run, monkeypatch):
    """The detail view: tokens, origin+confidence, four buckets, suggested-vs-kept,
    the per-file table, and the time line."""
    monkeypatch.setenv("CAGE_AUTHORSHIP", "1")
    go = run(seed.commits_mixed)
    import subprocess
    sha = subprocess.run(("git", "-C", str(go.root), "log", "--format=%h",
                          "--skip=1", "-n", "1"), capture_output=True,
                         text=True, check=True).stdout.strip()
    out = go("A3", ["insights", "commit", sha])
    assert "counts, not a score" in out and "$" not in out
    assert "human only by attestation" in out


def test_A4_authorship_summary(run, monkeypatch):
    """Unknown-rate first — the coverage gap is the headline, not a footnote."""
    monkeypatch.setenv("CAGE_AUTHORSHIP", "1")
    go = run(seed.commits_mixed)
    out = go("A4", ["authorship", "summary"])
    assert out.index("UNKNOWN") < out.index("recorded")
    assert "unknown by ABSENCE" in out


def test_A5_authorship_origin_detail(run, monkeypatch):
    """Per-commit provenance rows: agent, files, method, origin, confidence."""
    monkeypatch.setenv("CAGE_AUTHORSHIP", "1")
    go = run(seed.commits_mixed)
    import subprocess
    sha = subprocess.run(("git", "-C", str(go.root), "log", "--format=%h",
                          "--skip=1", "-n", "1"), capture_output=True,
                         text=True, check=True).stdout.strip()
    out = go("A5", ["authorship", "origin", sha])
    assert "origin=agent" in out and "confidence=" in out
    assert "transcript" in out
