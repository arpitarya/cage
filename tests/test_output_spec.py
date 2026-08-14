"""Golden tests for docs/cli-output-spec.md (plan Phases 1+2+5.6).

Every fixture under `tests/fixtures/goldens/` is one spec code block: the first
line is the invocation (`$ cage …`), the rest is the byte-exact stdout. These
files are the single artifact behind BOTH surfaces — this test asserts the live
output equals them, and `python -m tools.docgen --target spec` regenerates the
spec's code blocks from them (so documented and tested output cannot disagree).

Regenerate after an intentional rendering change:
    CAGE_BLESS_GOLDENS=1 python -m pytest tests/test_output_spec.py
    python -m tools.docgen --target spec

The S1/S2 study mockups (`join`/`start`/`stop`) are deliberately NOT byte-pinned:
join runs wiring + doctor, whose output is machine-dependent by design — they
get shape assertions here and stay illustrative in the spec.
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
    text = "$ cage " + " ".join(argv) + "\n" + out if argv else out
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












# ── §4 · cage study ───────────────────────────────────────────────────────────

def test_S1_S2_study_join_start_shapes(run, capsys):
    """S1/S2 stay shape-asserted (join wires agents + runs doctor — output is
    machine-dependent by design; a byte golden here would be dishonest)."""
    go = run()
    assert cli.main(["study", "join", "baseline"]) == 0
    out = capsys.readouterr().out
    assert "enrolled: machine m_" in out and "phase 'baseline' started" in out
    assert cli.main(["study", "start", "plugin"]) == 0
    out = capsys.readouterr().out
    assert "phase 'plugin' started" in out
    assert cli.main(["study", "stop"]) == 0
    assert "phase stopped" in capsys.readouterr().out


def test_S3_study_report_healthy(run):
    go = run(seed.fleet)
    out = go("S3", ["study", "report"])
    assert "estimated" in out
    assert "not a controlled experiment" in out or "work mix" in out


def test_S4_study_report_refusal(run):
    go = run(lambda r: seed.fleet(r, complete=3))
    out = go("S4", ["study", "report"])
    assert "insufficient machines with both phases (n=3 < 5)" in out


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
