"""Portable wiring (plan §5): committed wired files carry no absolute paths; the
committed `.cage/bin/cage-run` shim resolves cage at runtime, fail-open when absent.

The no-absolute-path greps here are THE invariant that must never rot — a committed
absolute path ships one dev's filesystem to the whole team and breaks every clone.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from cage import agents, cfgio, cleanup, doctorcmd, paths, policy, runshim

posix_only = pytest.mark.skipif(os.name != "posix", reason="sh shim — POSIX hosts")


@pytest.fixture
def homes(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude_home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex_home"))
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "copilot_home"))
    monkeypatch.setenv("KIRO_HOME", str(tmp_path / "kiro_home"))
    return tmp_path


# Every project-committed file each wire module writes commands into. The ONE
# exception (.kiro/settings/mcp.json — absolute by necessity, see kirowire.py)
# is deliberately absent here and asserted separately.
_COMMITTED = (".claude/settings.json", ".mcp.json", ".vscode/mcp.json",
              ".codex/hooks.json", ".kiro/hooks/cage.kiro.hook")


def test_committed_files_contain_no_absolute_cage_path(homes, monkeypatch):
    # The regression grep: wire everything on a machine where cage resolves to a
    # deep absolute path, then grep every committed file for it. Must never rot.
    abs_bin = "/opt/weird prefix/bin/cage"
    monkeypatch.setattr("cage.paths.cage_bin", lambda: abs_bin)
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj)
    for rel in _COMMITTED:
        text = (proj / rel).read_text(encoding="utf-8")
        assert abs_bin not in text, f"absolute cage path leaked into committed {rel}"
        assert "/opt/" not in text, f"machine path fragment leaked into committed {rel}"
    # the shim itself is machine-independent bytes — nothing absolute inside either
    for shim in ("cage-run", "cage-run.cmd"):
        assert abs_bin not in (proj / ".cage" / "bin" / shim).read_text(encoding="utf-8")
    # user-level files keep the resolved absolute path (per-machine, never cloned)
    cop = cfgio.load_json(homes / "copilot_home" / "hooks" / "cage.json")["hooks"]
    assert all(abs_bin in h["bash"] for h in cop["agentStop"])


def test_setup_twice_is_byte_identical(homes):
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj)
    files = [proj / r for r in _COMMITTED] + [
        proj / ".cage" / "bin" / "cage-run", proj / ".cage" / "bin" / "cage-run.cmd",
        proj / ".kiro" / "settings" / "mcp.json"]
    before = {f: f.read_bytes() for f in files}
    agents.install(proj)
    assert {f: f.read_bytes() for f in files} == before


def test_shim_not_reachable_by_cleanup_allowlist(homes, tmp_path):
    # The cleanup allowlist is closed over `.cage/state/` — `.cage/bin/` must be
    # structurally out of its reach even when the shim files are old.
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj)
    old = 10**9  # well past any retention window
    for f in (proj / ".cage" / "bin").iterdir():
        os.utime(f, (old, old))
    pol = policy.load(paths.Footprint(proj).policy)
    hits = cleanup.scan(proj, pol)
    assert not any(".cage/bin" in str(h["path"]).replace("\\", "/") for h in hits)
    assert (proj / ".cage" / "bin" / "cage-run").exists()


# ── shim runtime resolution (documented order, fail-open) ────────────────────

def _run_shim(shim: Path, args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["/bin/sh", str(shim), *args], env=env,
                          capture_output=True, text=True, timeout=30)


def _fake_env(tmp_path: Path, path_dirs: list[Path]) -> dict:
    # A hermetic env: controlled PATH + HOME, no VIRTUAL_ENV, no inherited installs.
    return {"PATH": os.pathsep.join(str(d) for d in path_dirs),
            "HOME": str(tmp_path / "fakehome")}


def _plant_fake_cage(at: Path, tag: str) -> None:
    at.parent.mkdir(parents=True, exist_ok=True)
    at.write_text(f'#!/bin/sh\necho "{tag} $@"\n', encoding="utf-8")
    at.chmod(0o755)


@posix_only
def test_shim_prefers_path_and_passes_args_through(tmp_path):
    shim = Path(runshim.write(tmp_path)["cage-run"])
    bindir = tmp_path / "fakepath"
    _plant_fake_cage(bindir / "cage", "PATH-CAGE")
    r = _run_shim(shim, ["import", "--agent", "codex"], _fake_env(tmp_path, [bindir]))
    assert r.returncode == 0
    assert r.stdout.strip() == "PATH-CAGE import --agent codex"  # args pass through


@posix_only
def test_shim_falls_back_to_local_bin_then_venv(tmp_path):
    shim = Path(runshim.write(tmp_path)["cage-run"])
    env = _fake_env(tmp_path, [tmp_path / "emptydir"])
    home = Path(env["HOME"])
    _plant_fake_cage(home / ".local" / "bin" / "cage", "LOCAL-BIN")
    r = _run_shim(shim, ["report"], env)
    assert (r.returncode, r.stdout.strip()) == (0, "LOCAL-BIN report")
    # remove ~/.local/bin — an active venv is next in the documented order
    (home / ".local" / "bin" / "cage").unlink()
    venv = tmp_path / "venv"
    _plant_fake_cage(venv / "bin" / "cage", "VENV-CAGE")
    env["VIRTUAL_ENV"] = str(venv)
    r = _run_shim(shim, ["report"], env)
    assert (r.returncode, r.stdout.strip()) == (0, "VENV-CAGE report")


@posix_only
def test_shim_absent_cage_exits_zero_silently(tmp_path):
    # The fail-open contract: a clone without cage = working agents, no noise.
    # PATH has no cage and no python3, HOME has no installs.
    shim = Path(runshim.write(tmp_path)["cage-run"])
    r = _run_shim(shim, ["import"], _fake_env(tmp_path, [tmp_path / "emptydir"]))
    assert r.returncode == 0
    assert r.stdout == "" and r.stderr == ""


@posix_only
def test_shim_python_module_fallback(tmp_path):
    # No cage binary anywhere, but a python3 that can import cage → python3 -m cage.
    shim = Path(runshim.write(tmp_path)["cage-run"])
    bindir = tmp_path / "pybin"
    bindir.mkdir()
    (bindir / "python3").symlink_to(sys.executable)
    env = _fake_env(tmp_path, [bindir])
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    r = _run_shim(shim, ["--version"], env)
    assert r.returncode == 0 and "cage" in r.stdout


@posix_only
def test_shim_write_sets_execute_bit_and_is_failopen_without_it(tmp_path):
    shim = Path(runshim.write(tmp_path)["cage-run"])
    assert shim.stat().st_mode & stat.S_IEXEC
    # a core.fileMode=false clone loses the bit — doctor runs it via `sh`, so the
    # resolution answer must not depend on the bit
    shim.chmod(shim.stat().st_mode & ~(stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH))
    r = _run_shim(shim, [], _fake_env(tmp_path, [tmp_path / "emptydir"]))
    assert r.returncode == 0


# ── doctor portability check ─────────────────────────────────────────────────

def _portability(root: Path) -> tuple[str, str]:
    return doctorcmd._portability(root)


def test_doctor_flags_planted_absolute_path(homes, monkeypatch):
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj, ("claude",))
    mcp = proj / ".mcp.json"
    data = cfgio.load_json(mcp)
    data["mcpServers"]["cage"]["command"] = "/Users/somedev/.local/bin/cage"  # legacy
    mcp.write_text(json.dumps(data), encoding="utf-8")
    level, detail = _portability(proj)
    assert level == "warn"
    assert ".mcp.json" in detail and "machine-absolute" in detail


def test_doctor_flags_missing_shim(homes):
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj, ("claude",))
    (proj / ".cage" / "bin" / "cage-run").unlink()
    level, detail = _portability(proj)
    assert level == "warn" and "shim is missing" in detail


@posix_only
def test_doctor_portability_clean_after_setup(homes, monkeypatch, tmp_path):
    # Deterministic resolution for the run check: plant a fake cage on PATH.
    bindir = tmp_path / "bin"
    _plant_fake_cage(bindir / "cage", "cage 9.9.9-test —")
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}")
    proj = homes / "proj"
    proj.mkdir()
    agents.install(proj)
    level, detail = _portability(proj)
    assert level == "ok"
    assert "portable" in detail and "shim resolves" in detail
    # the ONE exception is surfaced as advice, never silently shipped
    assert ".kiro/settings/mcp.json" in detail and ".gitignore" in detail


def test_doctor_portability_silent_when_nothing_wired(homes):
    proj = homes / "proj"
    proj.mkdir()
    level, detail = _portability(proj)
    assert level == "ok" and "nothing to check" in detail


def test_query_portable_wiring_answers():
    from cage import explain
    (hit,) = explain.match("portable-wiring")
    assert hit.id == "portable-wiring"
    body = explain.render(hit, {})
    assert "cage-run" in body and "exit 0" in body
    (by_words,) = explain.match("why no absolute paths in committed wiring")
    assert by_words.id == "portable-wiring"


def test_heal_migrates_path_and_verb_in_one_pass(homes, monkeypatch):
    """Portability and liveness are healed together: a v0.27 hook carries BOTH a
    machine-absolute path and a since-renamed verb, and one `cage setup` must fix
    both — a hook that is portable but dead is no better than one that is neither."""
    monkeypatch.setattr(paths, "cage_bin", lambda: "/old/machine/bin/cage")
    settings = homes / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": [
        {"type": "command",
         "command": "/old/machine/bin/cage import-claude --project ."}]}]}},
        indent=2), encoding="utf-8")
    agents.install(homes, ("claude",))
    body = settings.read_text(encoding="utf-8")
    assert "/old/machine/bin/cage" not in body      # portability healed
    assert "import-claude" not in body              # liveness healed
    assert "cage-run" in body and "import --agent claude" in body


def test_committed_wiring_names_only_live_verbs(homes):
    """The standing invariant, mechanised: nothing cage commits may name a verb the
    CLI rejects. This is the check that would have failed the v0.28.0 rename."""
    from cage import wiringscan
    agents.install(homes, agents.SURFACES)
    for rel, command in wiringscan.committed_artifacts(homes):
        assert not wiringscan.is_dead_cage_command(command), f"{rel}: {command}"
