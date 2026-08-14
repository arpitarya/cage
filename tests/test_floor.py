"""L0 — the floor: cage works with **no hooks, no MCP, no steering**, on all three agents.

The binding rule of the agent-surface ladder
([work/archive/v0.41-agent-surface-layers.proposal.md](../work/archive/v0.41-agent-surface-layers.proposal.md)):
*L0 must work perfectly, alone, forever.* Every layer above it (L1 hooks+steering,
L2 MCP, L3 skills) is opt-in and degrades cleanly to absent — **if adding or removing
a layer changes a number, the layer is wrong.**

This file is the proof, and it exists *before* those layers are built so they are
judged against it rather than shipped against a moving target. Four claims:

1. **Zero wiring captures** — a project with no wiring artifact of any kind imports
   each agent's real session log to the exact expected rows (the corpus fixtures).
2. **Adding a layer changes no number** — `agents.install` (today: MCP + the shim) on
   the *same* project leaves the ledger shards byte-identical and every derived view's
   stdout byte-identical.
3. **Removing a layer changes no number** — deleting every wiring artifact again is
   likewise byte-identical, in both directions.
4. **No skill/prompt/steering asset ships**, and no surface claims one — the v0.36
   hookless rebuild deleted that machinery, and the README claimed it for eleven
   releases after (the P0 residue).

A new layer is wired into this file by adding its artifacts to `_WIRING_ARTIFACTS`
and its installer to the `test_layer_changes_no_number` round-trip — never by
relaxing an assertion.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from cage import agents, cli, clicmds, ledger, paths
from srcseed import mkcage

CORPUS = Path(__file__).parent / "fixtures" / "transcripts"

# Every project-level path any agent-surface layer writes into. L0 requires **all** of
# them absent; a layer installs some subset. Add a row when a layer lands — the floor
# assertions then cover it for free.
_WIRING_ARTIFACTS = (
    ".cage/bin/cage-run",        # the runtime-resolving shim every committed file cites
    ".mcp.json",                 # L2 · claude
    ".vscode/mcp.json",          # L2 · copilot
    ".kiro/settings/mcp.json",   # L2 · kiro
    ".claude/settings.json",     # L1 · claude hooks (removed in v0.36; L1 rebuilds here)
    ".github/hooks",             # L1 · copilot repo-level hooks
    ".kiro/hooks",               # L1 · kiro one-hook-per-file
    ".claude/skills",            # L3 · claude skill
    ".github/prompts",           # L3 · copilot prompt
    ".kiro/steering",            # L1/L3 · kiro steering
)

# The derived views the floor pins. Usage, savings, adoption and the raw CSV — a layer
# that leaked into any of them would move one of these. `--no-import` keeps the read a
# pure function of the ledger (capture-on-read is pinned off suite-wide anyway).
#
# **Three entries changed in USAGE-ONLY (ADR 0011), and the gate did not weaken.** The
# list named `report --usd`, `insights roi` and `task quality`; all three commands were
# deleted with the money subsystem, so the old list could only ever exit 2. They are
# replaced ONE-FOR-ONE by live views of the same kinds — a second report shape, a
# second savings view, a second per-conversation view — so the count, the breadth and
# the byte-identical assertion are unchanged. This is the substitution the standing
# rule allows; what it forbids is *relaxing an assertion*, and none was relaxed.
_VIEWS = (
    ["report", "--by", "agent"],
    ["report", "--by", "model"],
    ["report", "--csv"],
    ["insights", "attrib"],
    ["insights", "graphify"],
    ["insights", "adoption"],
    ["insights", "chats"],
    ["insights", "commits"],
)


def _spec(agent: str) -> dict:
    return json.loads((CORPUS / agent / "cli" / "expected.json").read_text(encoding="utf-8"))


def _bare_project(d: Path, monkeypatch) -> Path:
    """A scaffolded project with a ledger and **no wiring of any kind**, and every agent
    home redirected into `d` so the pathless scan can never read real machine data."""
    mkcage(d)
    for env in ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_DATA_DIR", "CAGE_VSCODE_USER"):
        monkeypatch.setenv(env, str(d / f"home-{env.lower()}"))
    monkeypatch.delenv("CAGE_CAPTURE", raising=False)
    monkeypatch.chdir(d)
    return d


def _plant(agent: str, home: Path) -> None:
    spec = _spec(agent)
    dst = home / spec["plant"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CORPUS / agent / "cli" / spec["log"], dst)


def _assert_unwired(root: Path) -> None:
    present = [a for a in _WIRING_ARTIFACTS if (root / a).exists()]
    assert present == [], f"floor project is not bare — wiring present: {present}"


def _sink(root: Path, agent: str) -> Path:
    """Where this agent's rows land. Kiro's IDE log is a *machine* fact and routes to
    the machine ledger (ADR 0006); the others land in the project."""
    return (paths.kiro_routed(root) or root) if agent == "kiro" else root


def _ledger_bytes(root: Path, agent: str) -> dict[str, bytes]:
    fp = paths.Footprint(_sink(root, agent))
    return {kind: b"".join(p.read_bytes() for p in fp.shards(kind))
            for kind in ("calls", "receipts", "tasks")}


def _render(root: Path, capsys) -> dict[str, str]:
    """Every pinned view's stdout, with the per-test tmp path folded to a placeholder
    (it is the only legitimately machine-varying substring)."""
    out: dict[str, str] = {}
    for argv in _VIEWS:
        assert cli.main([*argv, "--no-import"]) == 0, f"view failed: {argv}"
        text = capsys.readouterr().out
        for raw in {str(root.resolve()), str(root)}:
            text = text.replace(raw, "<project>")
        out[" ".join(argv)] = text
    return out


def _strip_wiring(root: Path) -> int:
    removed = 0
    for a in _WIRING_ARTIFACTS:
        p = root / a
        if p.is_dir():
            shutil.rmtree(p)
            removed += 1
        elif p.exists():
            p.unlink()
            removed += 1
    return removed


# ── 1 · zero wiring captures, on all three agents ─────────────────────────────

@pytest.mark.parametrize("agent", agents.SURFACES)
def test_floor_captures_with_zero_wiring(agent, tmp_path, monkeypatch, capsys):
    """No hooks, no MCP, no steering — `cage import` still parses the agent's real
    session log to the exact expected rows. This is the whole of L0's promise."""
    spec = _spec(agent)
    root = _bare_project(tmp_path, monkeypatch)
    _assert_unwired(root)
    _plant(agent, tmp_path / f"home-{spec['env'].lower()}")

    assert clicmds.cmd_import(SimpleNamespace(
        agent=agent, path=None, project=None, since=None)) == 0
    assert f"✔ {agent}: imported {len(spec['rows'])} call(s)" in capsys.readouterr().out

    rows = ledger.calls(_sink(root, agent))
    volatile = set(spec["volatile"]) | {"import_id"}
    actual = sorted(({k: v for k, v in r.items() if k not in volatile} for r in rows),
                    key=lambda r: r["id"])
    expected = sorted(({k: v for k, v in r.items() if k not in volatile}
                       for r in spec["rows"]), key=lambda r: r["id"])
    assert actual == expected

    # Capture wired nothing on its way through — the floor stays the floor.
    _assert_unwired(root)


@pytest.mark.parametrize("agent", agents.SURFACES)
def test_floor_derives_and_reports_with_zero_wiring(agent, tmp_path, monkeypatch, capsys):
    """Every derived view renders (exit 0, non-empty) over a ledger captured with no
    wiring — capture is only half the floor; the read surface is the other half."""
    spec = _spec(agent)
    root = _bare_project(tmp_path, monkeypatch)
    _plant(agent, tmp_path / f"home-{spec['env'].lower()}")
    assert clicmds.cmd_import(SimpleNamespace(
        agent=agent, path=None, project=None, since=None)) == 0
    capsys.readouterr()

    views = _render(root, capsys)
    assert all(v.strip() for v in views.values()), "a derived view rendered empty"
    _assert_unwired(root)


# ── 2 + 3 · a layer changes no number, added or removed ───────────────────────

@pytest.mark.parametrize("agent", agents.SURFACES)
def test_layer_changes_no_number(agent, tmp_path, monkeypatch, capsys):
    """Install every layer cage ships onto a project whose ledger is already captured,
    then remove it again. **The ledger bytes and every view's stdout must be identical
    at all three points.** This is the acceptance criterion the L1/L2/L3 phases are
    judged against — a phase that cannot meet it is wrong, and the number is never the
    thing that gets adjusted."""
    spec = _spec(agent)
    root = _bare_project(tmp_path, monkeypatch)
    _plant(agent, tmp_path / f"home-{spec['env'].lower()}")
    assert clicmds.cmd_import(SimpleNamespace(
        agent=agent, path=None, project=None, since=None)) == 0
    capsys.readouterr()

    bare_ledger, bare_views = _ledger_bytes(root, agent), _render(root, capsys)

    # ← EVERY layer cage ships: the shim + L2 MCP + L1 hooks + L1 steering. When a new
    # layer lands it is added here and to `_WIRING_ARTIFACTS` — the floor is extended to
    # cover it, never narrowed to accommodate it.
    agents.install(root, hooks=True)
    capsys.readouterr()
    installed = [a for a in _WIRING_ARTIFACTS if (root / a).exists()]
    assert installed, "agents.install wired nothing — the test would prove nothing"

    assert _ledger_bytes(root, agent) == bare_ledger, "installing a layer wrote to the ledger"
    assert _render(root, capsys) == bare_views, "installing a layer moved a derived number"

    assert _strip_wiring(root)                 # ← and back down to the floor
    _assert_unwired(root)
    assert _ledger_bytes(root, agent) == bare_ledger
    assert _render(root, capsys) == bare_views, "removing a layer moved a derived number"


def test_install_is_idempotent_and_byte_identical(tmp_path, monkeypatch, capsys):
    """Two teammates running `cage setup` must not churn a committed diff — so the
    second install must reproduce the first's bytes exactly (multi-user hygiene, and a
    standing gate for every layer the ladder adds)."""
    root = _bare_project(tmp_path, monkeypatch)

    def _bytes() -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        for a in _WIRING_ARTIFACTS:
            p = root / a
            if p.is_file():
                out[a] = p.read_bytes()
            elif p.is_dir():
                out.update({str(f.relative_to(root)): f.read_bytes()
                            for f in sorted(p.rglob("*")) if f.is_file()})
        return out

    agents.install(root, hooks=True)
    capsys.readouterr()
    first = _bytes()
    assert first, "agents.install wired no file — nothing to compare"
    agents.install(root, hooks=True)
    capsys.readouterr()
    assert _bytes() == first


# ── 4 · no skill/prompt/steering asset ships, and nothing claims one ──────────

def test_no_skill_prompt_or_steering_asset_ships():
    """The hookless rebuild deleted the rendered assets and `tools/skillgen`. L3 will
    rebuild from the ladder's design — until it does, shipping nothing is the truth."""
    data = paths.bundled_data()
    for name in ("skills", "prompts", "steering"):
        assert not (data / name).is_dir(), f"cage/data/{name}/ is back without a design"
    assert not (Path(__file__).parents[1] / "tools" / "skillgen").exists()


def test_setup_no_longer_accepts_no_skill():
    """`--no-skill` skipped an asset that no longer exists. argparse exits 2 on an
    unknown flag — a removed flag must *fail*, never be silently accepted."""
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["setup", "--no-skill"])
    assert exc.value.code == 2


@pytest.mark.parametrize("doc", ["README.md", "CLAUDE.md", "docs/example/setup.md"])
def test_no_surface_claims_a_skill_that_does_not_exist(doc):
    """The README promised a `cage` skill three times — once on *"all four agents"*,
    wrong twice over (no skill exists; there have been **three** agents since v0.33).
    It was live on PyPI. A claim is residue exactly like a dead verb is."""
    text = (Path(__file__).parents[1] / doc).read_text(encoding="utf-8")
    lowered = text.lower()
    assert "--no-skill" not in text, f"{doc} documents a flag that no longer parses"
    assert "all four agents" not in lowered, f"{doc} claims four agents; there are three"
    assert "wires skill" not in lowered, f"{doc} claims `cage setup` wires a skill"
    assert "the `cage` skill" not in lowered, f"{doc} claims a skill that does not ship"
