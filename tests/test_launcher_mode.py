"""Python-launcher wiring mode (docs/restricted-environments.md): opt-in wiring
that resolves cage through the interpreter only — nothing exe-shaped is probed or
executed on endpoints that block unknown executables (AppLocker/WDAC).

The exe-shape greps are the mode's contract: a launcher-mode file that mentions
`cage.exe`, probes `command -v cage` / `where cage`, or points at an install-dir
binary defeats the whole tier.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cage import agents, cfgio, cli, doctorcmd, metering, paths, policy, pricestoml, runshim

posix_only = pytest.mark.skipif(os.name != "posix", reason="sh shim — POSIX hosts")

# Nothing exe-shaped may appear in a launcher-mode wired file (handoff §9).
_EXE_SHAPES = ("cage.exe", "command -v cage", "where cage", ".local/bin/cage",
               ".local/pipx/venvs/cage")


@pytest.fixture
def homes(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude_home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex_home"))
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "copilot_home"))
    monkeypatch.setenv("KIRO_HOME", str(tmp_path / "kiro_home"))
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".git").mkdir()  # so the git commit hooks install too
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    return proj


def _wired_files(proj: Path, tmp_path: Path) -> dict[str, Path]:
    return {
        "shim": proj / ".cage" / "bin" / "cage-run",
        "shim.cmd": proj / ".cage" / "bin" / "cage-run.cmd",
        "copilot-hook": tmp_path / "copilot_home" / "hooks" / "cage.json",
        "codex-config": tmp_path / "codex_home" / "config.toml",
        "kiro-mcp": proj / ".kiro" / "settings" / "mcp.json",
        "post-commit": proj / ".git" / "hooks" / "post-commit",
        "prepare-commit-msg": proj / ".git" / "hooks" / "prepare-commit-msg",
    }


def test_setup_flag_persists_mode_and_writes_nothing_exe_shaped(homes, tmp_path, capsys):
    assert cli.main(["setup", "--wire-only", "--all", "--python-launcher"]) == 0
    out = capsys.readouterr().out
    assert "python-launcher" in out
    pol_text = (homes / ".cage" / "policy.toml").read_text(encoding="utf-8")
    assert "python_launcher = true" in pol_text
    assert policy.python_launcher(policy.load(paths.Footprint(homes).policy))
    for name, f in _wired_files(homes, tmp_path).items():
        text = f.read_text(encoding="utf-8")
        for shape in _EXE_SHAPES:
            assert shape not in text, f"exe shape {shape!r} leaked into {name}"
    # and the interpreter form is actually there
    assert runshim._PY_MARKER in (homes / ".cage" / "bin" / "cage-run").read_text(encoding="utf-8")
    cop = cfgio.load_json(tmp_path / "copilot_home" / "hooks" / "cage.json")["hooks"]
    entry = cop["agentStop"][0]
    assert entry["bash"] == "python3 -m cage import --agent copilot --since 7d"
    assert entry["powershell"] == "py -3 -m cage import --agent copilot --since 7d"
    codex = (tmp_path / "codex_home" / "config.toml").read_text(encoding="utf-8")
    if os.name == "nt":
        assert 'command = "py"' in codex and '"-3", "-m", "cage", "mcp"' in codex
    else:
        assert 'command = "python3"' in codex and '"-m", "cage", "mcp"' in codex
    kiro = cfgio.load_json(homes / ".kiro" / "settings" / "mcp.json")["mcpServers"]["cage"]
    assert kiro["command"] in ("python3", "py")
    assert "-m" in kiro["args"] and "cage" in kiro["args"]
    hook = (homes / ".git" / "hooks" / "post-commit").read_text(encoding="utf-8")
    assert "-m cage hook-post-commit" in hook


def test_flagless_rerun_preserves_the_mode_byte_identical(homes, tmp_path):
    assert cli.main(["setup", "--wire-only", "--all", "--python-launcher"]) == 0
    files = _wired_files(homes, tmp_path)
    before = {n: f.read_bytes() for n, f in files.items()}
    assert cli.main(["setup", "--wire-only", "--all"]) == 0  # no flag repeated
    assert {n: f.read_bytes() for n, f in files.items()} == before


def test_policy_flip_reverts_to_standard_on_rerun(homes, tmp_path):
    assert cli.main(["setup", "--wire-only", "--all", "--python-launcher"]) == 0
    pricestoml.set_wiring(homes, {"python_launcher": False})
    assert cli.main(["setup", "--wire-only", "--all"]) == 0
    sh = (homes / ".cage" / "bin" / "cage-run").read_text(encoding="utf-8")
    assert runshim._PY_MARKER not in sh
    assert "command -v cage" in sh  # the standard probe is back
    cop = cfgio.load_json(tmp_path / "copilot_home" / "hooks" / "cage.json")["hooks"]
    assert all(h["bash"].startswith("cage ") for h in cop["agentStop"])  # conftest pins bare `cage`


def test_mode_switch_leaves_exactly_one_copilot_import_entry(homes, tmp_path):
    # standard wiring first, then launcher — the stale absolute/bare form must
    # collapse, not accumulate (is_cage_import_command covers the -m cage form).
    agents.install(homes)
    assert cli.main(["setup", "--wire-only", "--all", "--python-launcher"]) == 0
    cop = cfgio.load_json(tmp_path / "copilot_home" / "hooks" / "cage.json")["hooks"]
    for event, arr in cop.items():
        cage_entries = [h for h in arr if "cage" in h.get("bash", "")]
        assert len(cage_entries) == 1, f"{event} accumulated entries: {arr}"
        assert cage_entries[0]["bash"].startswith("python3 -m cage ")


# ── shim runtime (same harness as test_portable_wiring) ─────────────────────

def _run_shim(shim: Path, args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["/bin/sh", str(shim), *args], env=env,
                          capture_output=True, text=True, timeout=30)


def _fake_env(tmp_path: Path, path_dirs: list[Path]) -> dict:
    return {"PATH": os.pathsep.join(str(d) for d in path_dirs),
            "HOME": str(tmp_path / "fakehome")}


def _plant_fake_cage(at: Path, tag: str) -> None:
    at.parent.mkdir(parents=True, exist_ok=True)
    at.write_text(f'#!/bin/sh\necho "{tag} $@"\n', encoding="utf-8")
    at.chmod(0o755)


def _plant_python3(tmp_path: Path) -> Path:
    bindir = tmp_path / "pybin"
    bindir.mkdir(exist_ok=True)
    (bindir / "python3").symlink_to(sys.executable)
    return bindir


@posix_only
def test_launcher_shim_execs_python_module_with_args(tmp_path):
    shim = Path(runshim.write(tmp_path, python_launcher=True)["cage-run"])
    env = _fake_env(tmp_path, [_plant_python3(tmp_path)])
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    r = _run_shim(shim, ["--version"], env)
    assert r.returncode == 0 and "cage" in r.stdout


@posix_only
def test_launcher_shim_never_runs_a_planted_cage(tmp_path):
    # A cage binary sits on PATH — the launcher shim must not touch it (that is
    # the whole point: the exe may exist but be execution-blocked).
    shim = Path(runshim.write(tmp_path, python_launcher=True)["cage-run"])
    bindir = tmp_path / "fakepath"
    _plant_fake_cage(bindir / "cage", "PATH-CAGE")
    r = _run_shim(shim, ["import"], _fake_env(tmp_path, [bindir]))
    assert r.returncode == 0
    assert "PATH-CAGE" not in r.stdout  # fail-open silence, no exe executed
    assert r.stdout == "" and r.stderr == ""


@posix_only
def test_launcher_shim_fail_open_without_python3(tmp_path):
    shim = Path(runshim.write(tmp_path, python_launcher=True)["cage-run"])
    r = _run_shim(shim, ["import"], _fake_env(tmp_path, [tmp_path / "emptydir"]))
    assert r.returncode == 0
    assert r.stdout == "" and r.stderr == ""


@posix_only
def test_cage_run_python_skips_exe_probe_on_the_standard_shim(tmp_path):
    # The no-rewire escape hatch: CAGE_RUN_PYTHON=1 on the STANDARD shim takes the
    # interpreter path even with a cage binary on PATH; unset keeps today's order.
    shim = Path(runshim.write(tmp_path)["cage-run"])
    bindir = tmp_path / "fakepath"
    _plant_fake_cage(bindir / "cage", "PATH-CAGE")
    env = _fake_env(tmp_path, [bindir, _plant_python3(tmp_path)])
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    r = _run_shim(shim, ["--version"], env)
    assert "PATH-CAGE" in r.stdout  # unset → standard order unchanged
    env["CAGE_RUN_PYTHON"] = "1"
    r = _run_shim(shim, ["--version"], env)
    assert r.returncode == 0
    assert "PATH-CAGE" not in r.stdout and "cage" in r.stdout


@posix_only
def test_cage_run_python_is_fail_open_without_python3(tmp_path):
    shim = Path(runshim.write(tmp_path)["cage-run"])
    bindir = tmp_path / "fakepath"
    _plant_fake_cage(bindir / "cage", "PATH-CAGE")
    env = _fake_env(tmp_path, [bindir])
    env["CAGE_RUN_PYTHON"] = "1"
    r = _run_shim(shim, ["import"], env)
    # python-only was requested but no python3 exists: exit 0 silently — never
    # fall back to the exe the endpoint may block.
    assert r.returncode == 0
    assert r.stdout == "" and r.stderr == ""


# ── doctor ───────────────────────────────────────────────────────────────────

@posix_only
def test_doctor_reports_python_launcher_mode(homes, tmp_path, monkeypatch):
    # Deterministic resolution for the shim-run probe: a python3 that imports cage.
    monkeypatch.setenv("PATH", f"{_plant_python3(tmp_path)}{os.pathsep}"
                               f"{os.environ.get('PATH', '')}")
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1]))
    assert cli.main(["setup", "--wire-only", "--claude", "--python-launcher"]) == 0
    level, detail = doctorcmd._portability(homes)
    assert level == "ok"
    assert "mode: python-launcher" in detail


def test_doctor_reports_standard_mode(homes):
    agents.install(homes, ("claude",))
    level, detail = doctorcmd._portability(homes)
    assert level == "ok"
    assert "mode: standard" in detail


def test_doctor_warns_on_policy_shim_drift(homes):
    from cage import initcmd
    initcmd.run(homes)
    agents.install(homes, ("claude",))  # standard shim on disk
    pricestoml.set_wiring(homes, {"python_launcher": True})  # policy flipped, no re-run
    level, detail = doctorcmd._portability(homes)
    assert level == "warn"
    assert "re-run `cage setup`" in detail


def test_doctor_check_names_unchanged(homes):
    # The mode rides the existing portability check — no new check name (the
    # tests/test_doctor.py name-set contract stays intact).
    from cage import initcmd
    initcmd.run(homes)
    names = [c["name"] for c in doctorcmd.run(homes)["checks"]]
    assert names == ["tool", "footprint", "policy", "pricing", "prices-meta", "prices-age", "policy-version",
                     "state", "hooks", "portability", "metering", "trace", "interceptor",
                     "ledger"]


def test_query_restricted_env_answers():
    from cage import explain
    (hit,) = explain.match("restricted-env")
    assert hit.id == "restricted-env"
    body = explain.render(hit, {})
    assert "python-launcher" in body and "cage.pyz" in body and "WDAC" in body


# ── command-form recognition (dedup/migration heuristic) ─────────────────────

def test_cage_command_tail_recognizes_interpreter_forms():
    assert paths.cage_command_tail("python3 -m cage import --agent copilot --since 7d") \
        == "import --agent copilot --since 7d"
    assert paths.cage_command_tail("py -3 -m cage mcp") == "mcp"
    assert paths.cage_command_tail("python3.12 -m cage report") == "report"
    assert paths.cage_command_tail("py -3 -m cage") == ""
    # foreign commands stay foreign
    assert paths.cage_command_tail("python3 -m notcage import") is None
    assert paths.cage_command_tail("python3 script.py import") is None
    assert paths.is_cage_import_command("python3 -m cage import --agent copilot --since 7d")
    # reresolve stays binary-only: never rewrites an interpreter form to an abs path
    assert paths.reresolve_cage_command("python3 -m cage hook-stop") is None
