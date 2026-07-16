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
    assert "$0" not in out and "saved tok" in out  # no dollar figures by default
    assert "kiro: input-only log — tok out not recorded" in out
    assert "unpriced — matters when you view $" in out


def test_R2_report_usd(run):
    go = run(seed.wmh)
    seed.set_last_import(go.root, _now())
    out = go("R2", ["report", "--by", "agent", "--usd"])
    assert "· usd" in out.splitlines()[0]
    assert "≈ priced by family" in out and "≈ graphify priced at task model" in out
    assert "kiro: input-only log — cost understated" in out
    assert out.count("⚠") == 1


def test_R3_report_usd_no_receipts(run):
    go = run(seed.spend_only)
    seed.set_last_import(go.root, _now())
    out = go("R3", ["report", "--by", "agent", "--usd"])
    header = out.splitlines()[3]
    assert "saved" not in header and "net" not in header  # spend-only grid
    assert "no savings receipts in this window" in out


def test_R4_report_by_model_unpriced(run):
    go = run(seed.wmh)
    seed.set_last_import(go.root, _now())
    out = go("R4", ["report", "--by", "model", "--usd"])
    assert "—" in out                      # the fully-unpriced bucket's cost cell
    assert "(+ unpriced)" in out           # the TOTAL says the gap out loud
    assert "agent (kiro)" in out           # generic model bucket named by its agent
    assert "fix: cage prices" in out


def test_R5_report_empty(run):
    go = run()
    out = go("R5", ["report"])
    assert "No calls recorded yet." in out
    assert "cage import" in out and "cage doctor" in out


def test_R6_report_stale_advice(run):
    go = run(seed.stale)
    out = go("R6", ["report", "--by", "agent"])
    assert "last import: 3d ago" in out
    assert "bundled prices are 61 days old" in out
    # advice renders once, at the bottom, with its runnable explain pointer
    assert "(`cage query prices-freshness` explains)" in out
    assert out.count("bundled prices are") == 1


def test_R7_report_capture_health_warning(run):
    # codex is installed but its log matched nothing and it has never captured a row —
    # the triple-gated "capture is off for this agent" ⚠ (docs/capture-health). wmh
    # seeds claude/copilot/kiro (not codex), so the table renders and only codex warns.
    go = run(seed.wmh)
    seed.set_last_import(go.root, _now())
    seed.set_capture_gap(go.root, "codex")
    out = go("R7", ["report", "--by", "agent"])
    assert "⚠ codex: ~/.codex exists but ~/.codex/sessions matched 0 files" in out
    assert "[sources.codex] replace=true, paths=[]" in out  # the runnable opt-out
    assert "claude" in out and "codex" not in out.splitlines()[3]  # codex not a table row


# ── §2 · insights surfaces (current verb names — Phase 3 regroups the doors) ──

def test_I2_verdict_saving(run):
    go = run(seed.verdict_saving)
    out = go("I2", ["insights", "verdict", "graphify"])
    assert "SAVING" in out and "marginal saving" in out


def test_I3_verdict_costing_negative_net(run):
    go = run(seed.verdict_costing)
    out = go("I3", ["insights", "verdict", "graphify"])
    assert "COSTING" in out


def test_I4_verdict_insufficient(run):
    go = run(seed.wmh)
    out = go("I4", ["insights", "verdict", "fux"], expect_exit=0)
    assert "INSUFFICIENT DATA" in out


def test_I5_compare_groups_and_refusal(run):
    go = run(seed.compare_estimate)
    out = go("I5", ["insights", "compare", "--label", "docfix", "--agent-only"])
    assert "agent-only" in out and "graphify" in out
    assert "insufficient data (n=2 < 5)" in out
    assert "observed difference" in out  # the observational caveat renders


def test_I6_estimate_band_and_refusal(run):
    go = run(seed.compare_estimate)
    out = go("I6a", ["insights", "estimate", "--label", "docfix"])
    assert "median" in out and "IQR" in out
    out = go("I6b", ["insights", "estimate", "--label", "refactor"])
    assert "insufficient history" in out  # refuses with the gate named, exit 0


def test_I7_matrix_tokens_default(run):
    go = run(seed.matrix_task)
    out = go("I7", ["insights", "matrix", "--task", "t_9f31"])
    assert "cost" not in out and "$" not in out
    assert "22,171" in out and "1,660" in out
    assert "✓ smaller" in out


def test_I8_matrix_usd(run):
    go = run(seed.matrix_task)
    out = go("I8a", ["insights", "matrix", "--task", "t_9f31", "--usd"])
    assert "base model anthropic/claude-sonnet-4-6" in out
    assert "$0.0665" in out and "$0.0050" in out and "✓ cheaper" in out


def test_I8_matrix_usd_unpriceable(run):
    go = run(seed.matrix_unpriceable)
    out = go("I8b", ["insights", "matrix", "--usd"])
    assert "22,171" in out                       # the token grid never refuses
    assert "cost column unavailable" in out
    assert "fix: cage prices route-tool graphify" in out


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


def test_P1_prices_list(run, capsys):
    go = run(seed.wmh)
    _prices_project(go.root)
    capsys.readouterr()  # drop the setup output
    go("P1", ["prices", "list"])


def test_P2_prices_unpriced(run, capsys):
    go = run(seed.wmh)
    out = go("P2a", ["prices", "unpriced"])
    assert "fix: cage prices" in out
    # …and the clean state on a fully-priced ledger
    from cage import pricescmd, policy
    d = pricescmd.unpriced_view(go.root, policy.load(None))
    assert d["total_calls"] == 2  # the two copilot/auto calls


def test_P2b_prices_unpriced_clean(run):
    go = run(seed.spend_only)
    out = go("P2b", ["prices", "unpriced"])
    assert "✔" in out


def test_P3_prices_writes(run, capsys):
    from cage import initcmd
    go = run()
    initcmd.run(go.root)
    capsys.readouterr()
    out = go("P3a", ["prices", "set", "anthropic", "claude-sonnet-4.6",
                     "--input", "3.00", "--output", "15.00", "--cache-read", "0.30"])
    assert "re-price immediately" in out
    out = go("P3b", ["prices", "route-tool", "graphify",
                     "--to", "anthropic/claude-sonnet-4-6"])
    assert "graphify" in out


def test_P4_prices_sync(run, capsys):
    from cage import initcmd, pricestoml
    go = run()
    initcmd.run(go.root)
    pricestoml.update_meta(go.root, {"prices_version": "2020-01-01"})
    capsys.readouterr()
    go("P4a", ["prices", "sync"])
    go("P4b", ["prices", "sync", "--update"])
    out = go("P4c", ["prices", "sync"])
    assert "already in sync" in out.lower() or "in sync" in out


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
    out = go("S3", ["study", "report", "--agent-only"])
    assert "estimated" in out
    assert "not a controlled experiment" in out or "work mix" in out


def test_S4_study_report_refusal(run):
    go = run(lambda r: seed.fleet(r, complete=3))
    out = go("S4", ["study", "report", "--agent-only"])
    assert "insufficient machines with both phases (n=3 < 5)" in out


# ── §5 · cage policy ──────────────────────────────────────────────────────────

def _old_policy_project(root: Path) -> None:
    from cage import initcmd, pricestoml
    initcmd.run(root)
    pricestoml.update_meta(root, {"policy_version": "0.19.0"})


def test_P5_policy_diff(run, capsys):
    go = run()
    _old_policy_project(go.root)
    capsys.readouterr()
    out = go("P5", ["policy", "diff"])
    assert "dry-run" in out or "nothing written" in out


def test_P6_policy_sync(run, capsys):
    go = run()
    _old_policy_project(go.root)
    capsys.readouterr()
    go("P6a", ["policy", "sync", "--apply"])
    out = go("P6b", ["policy", "sync"])
    assert "in sync" in out


# ── overview (bare cage — handoff §10) ────────────────────────────────────────

def test_O1_overview_tokens_default(run):
    go = run(seed.wmh)
    out = go("O1", [])
    assert "tokens" in out and "spent" not in out
    assert "$0" not in out  # no dollar figures on the token headline


def test_O2_overview_usd(run):
    go = run(seed.wmh)
    out = go("O2", ["--usd"])
    assert "spent" in out and "saved" in out and "net" in out


# ── the named negative-net law (plan Phase 2.2) ───────────────────────────────

def test_negative_net_with_receipts_always_renders(run, capsys):
    """A negative net backed by real receipts is NEVER suppressed, smoothed, or
    gated away — the metric that can embarrass a tool is the product."""
    go = run(seed.verdict_costing)
    assert cli.main(["report", "--by", "task", "--usd"]) == 0
    out = capsys.readouterr().out
    assert "net" in out and "-$" in out          # the column renders, negative
    assert cli.main(["insights", "roi"]) == 0
    out = capsys.readouterr().out
    assert "-$" in out or "-0." in out           # roi's net is negative too
    assert cli.main(["insights", "verdict", "graphify"]) == 0
    assert "COSTING" in capsys.readouterr().out


# ── determinism: goldens are stable under a double run ────────────────────────

def test_goldens_deterministic_double_run(run, capsys):
    go = run(seed.wmh)
    seed.set_last_import(go.root, _now())
    assert cli.main(["report", "--by", "agent", "--usd"]) == 0
    a = capsys.readouterr().out
    assert cli.main(["report", "--by", "agent", "--usd"]) == 0
    assert a == capsys.readouterr().out


def _now() -> str:
    import datetime as _dt
    return (_dt.datetime.now(_dt.timezone.utc)
            .isoformat(timespec="seconds").replace("+00:00", "Z"))
