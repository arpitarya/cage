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

def test_R1_report_tokens_default(run):
    go = run(seed.wmh)
    seed.set_last_import(go.root, _now())
    out = go("R1", ["report", "--by", "agent"])
    assert "$0" not in out and "gross tok" in out  # no dollar figures by default
    # Same reason as above: kiro contributes no spend rows, so its input-only caveat
    # has no number to qualify and correctly does not render.
    assert "kiro: input-only log" not in out








def test_R5_report_empty(run):
    go = run()
    out = go("R5", ["report"])
    assert "No calls recorded yet." in out
    assert "cage import" in out and "cage doctor" in out


def test_R6_report_stale_advice(run):
    """The import-age advice — the one staleness signal that outlived the price file.

    This test also pinned `bundled prices are N days old`; that signal went with the
    price table (USAGE-ONLY, ADR 0011). What it was really guarding — advice renders
    ONCE, at the bottom, never inline — is kept and now asserted on the surviving line."""
    go = run(seed.stale)
    out = go("R6", ["report", "--by", "agent"])
    assert "last import: 3d ago" in out
    assert out.count("last import:") == 1


def test_R7_report_capture_health_warning(run):
    # kiro is installed but its log matched nothing and it has never captured a row —
    # the triple-gated "capture is off for this agent" ⚠ (docs/capture-health).
    # spend_only seeds claude/copilot (not kiro), so the table renders and only kiro warns.
    go = run(seed.spend_only)
    seed.set_last_import(go.root, _now())
    seed.set_capture_gap(go.root, "kiro")
    out = go("R7", ["report", "--by", "agent"])
    assert "⚠ kiro: ~/.kiro exists but ~/.kiro/sessions matched 0 files" in out
    assert "[sources.kiro] replace=true, paths=[]" in out  # the runnable opt-out
    assert "claude" in out and "kiro" not in out.splitlines()[3]  # kiro not a table row


# ── §2 · insights surfaces (current verb names — Phase 3 regroups the doors) ──







def test_I5_compare_groups_and_refusal(run):
    go = run(seed.compare_estimate)
    out = go("I5", ["insights", "compare", "--label", "docfix"])
    assert "agent-only" in out and "graphify" in out
    assert "insufficient data (n=2 < 5)" in out
    assert "observed difference" in out  # the observational caveat renders


def test_I6_estimate_band_and_refusal(run):
    go = run(seed.compare_estimate)
    out = go("I6a", ["insights", "estimate", "--label", "docfix"])
    assert "median" in out and "IQR" in out
    out = go("I6b", ["insights", "estimate", "--label", "refactor"])
    assert "insufficient history" in out  # refuses with the gate named, exit 0








def test_I9_adoption_both_halves(run):
    go = run(seed.adoption_mixed)
    out = go("I9a", ["insights", "adoption"])
    a, b = out.index("A · invocations"), out.index("B · per-agent attribution")
    assert a < b                                 # two halves, ordered, never blended
    assert "claude" not in out[a:b]              # half A is agent-blind, by substrate
    assert "coverage: 3 of 4 savings rows (75%)" in out
    assert "cannot" in out and "which agent spawned it" in out
    # one row is agent-unknown, so the STRONG claim is withheld: it could be theirs
    assert "no savings row attributed to: copilot, kiro" in out
    assert "NOT evidence they never invoked the tool" in out
    assert "no evidence of invocation" not in out
    assert "$" not in out                        # no currency, ever, in this view


def test_I9_adoption_no_evidence(run):
    # every savings row found an agent, so "no evidence of invocation" IS supportable —
    # and is still stated as absence of evidence, never as proof of non-use.
    go = run(seed.adoption_attributed)
    out = go("I9d", ["insights", "adoption"])
    assert "coverage: 2 of 2 savings rows (100%)" in out
    assert "no evidence of invocation: copilot, kiro" in out
    assert "not proof of non-use" in out


def test_I9_adoption_half_b_refusal(run):
    # every invocation came through the shim ⇒ nothing attributable. The half RENDERS
    # its refusal rather than vanishing — suppressing it would make "cage cannot
    # attribute these" read like "cage has no per-agent answer at all".
    go = run(seed.adoption_shim_only)
    out = go("I9b", ["insights", "adoption"])
    assert "B · per-agent attribution" in out
    assert "per-agent attribution unavailable" in out
    assert "agent   tool" not in out             # and no empty table in its place


def test_I9_adoption_empty(run):
    go = run()
    out = go("I9c", ["insights", "adoption"])
    assert "No tool invocations and no savings receipts recorded yet." in out
    assert "cage import" in out and "cage doctor" in out


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

def test_O1_overview_tokens_default(run):
    go = run(seed.wmh)
    out = go("O1", [])
    assert "tokens" in out and "spent" not in out
    assert "$0" not in out  # no dollar figures on the token headline




# ── the named negative-net law (plan Phase 2.2) ───────────────────────────────



# ── determinism: goldens are stable under a double run ────────────────────────

def test_goldens_deterministic_double_run(run, capsys):
    go = run(seed.wmh)
    seed.set_last_import(go.root, _now())
    assert cli.main(["report", "--by", "agent"]) == 0
    a = capsys.readouterr().out
    assert cli.main(["report", "--by", "agent"]) == 0
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
