"""cage.pyz — every bundled-asset read exercised over a real built zipapp.

Builds one cage.pyz per session via `tools.buildpyz` (stdlib zipapp — the same
build path CI uses) and subprocesses it, so `importlib.resources` runs against a
zip Traversable, not a filesystem Path. The wheel side of the byte-identity
contract lives in tests/test_bundled_data.py; the full wheel↔pyz report-parity
check is dummyrepo scenario S13.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from cage import __version__
from tools import buildpyz

REPO_DATA = Path(__file__).resolve().parents[1] / "cage" / "data"


@pytest.fixture(scope="session")
def pyz(tmp_path_factory) -> Path:
    return buildpyz.build(tmp_path_factory.mktemp("pyz") / "cage.pyz")


def _run(pyz_path: Path, *args: str, cwd: Path, extra_env: dict | None = None):
    """Run the pyz hermetically: no PYTHONPATH (the zip's cage must win), no CAGE_*
    leakage, agent homes off the real ~/."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("CAGE_") and k != "PYTHONPATH"}
    home = cwd / "fake-homes"
    env.update({
        "PYTHONUTF8": "1",
        "CAGE_HOME": str(home / "cage-global"),
        "CLAUDE_CONFIG_DIR": str(home / "claude"),
        "COPILOT_HOME": str(home / "copilot"),
        "KIRO_HOME": str(home / "kiro"),
        "CAGE_VSCODE_USER": str(home / "vscode-user"),
    })
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(pyz_path), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          cwd=cwd, env=env, timeout=120)


def test_version_carries_the_zipapp_label(pyz, tmp_path):
    r = _run(pyz, "--version", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == f"cage {__version__} (zipapp)"


def test_init_writes_the_bundled_policy_from_the_zip(pyz, tmp_path):
    from cage import paths
    r = _run(pyz, "setup", "--project-only", "--no-graphify", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    written = (tmp_path / ".cage" / "cage.toml").read_text(encoding="utf-8")
    bundle = (REPO_DATA / "cage.toml").read_text(encoding="utf-8")
    # Directive A: setup writes the bundled policy but MATERIALIZES the active [sources]
    # table (env-dependent paths) in place of the inert comment block. So the body before
    # the sources marker is byte-identical to the bundle, EXCEPT for one stamped line:
    # the bundle carries no `[meta] cage_version` literal (policy._bundled derives it
    # live), so a freshly scaffolded project gets it stamped as a historical fact
    # (initcmd._stamp_cage_version) — the one place that value is ever written to disk.
    written_body = written.split(paths.SOURCES_START)[0]
    bundle_body = bundle.split(paths.SOURCES_START)[0]
    stamp = f'cage_version = "{__version__}"\n'
    assert stamp in written_body
    assert written_body.replace(stamp, "", 1) == bundle_body
    assert "[[sources.claude]]" in written and paths.SOURCES_START in written


def test_doctor_reports_zipapp_and_priced_policy(pyz, tmp_path):
    # The regression trap for the `.exists()` → `.is_file()` migration: a pyz that
    # silently loses the bundled prices would report 0 model prices here.
    assert _run(pyz, "setup", "--project-only", "--no-graphify", cwd=tmp_path).returncode == 0
    r = _run(pyz, "doctor", "--json", cwd=tmp_path)
    assert "(zipapp)" in r.stdout
    import json
    checks = {c["name"]: c for c in json.loads(r.stdout)["checks"]}
    assert checks["tool"]["level"] == "ok"
    assert "zipapp" in checks["tool"]["detail"]
    assert checks["policy"]["level"] == "ok"
    assert "0 model prices" not in checks["policy"]["detail"]


# NB: the skill-asset extraction test was removed with the rendered assets. The zipapp's
# bundled-data access (importlib.resources over the archive) is still exercised by the
# policy-loads and determinism checks around it.


def test_derived_view_is_deterministic_under_the_zip(pyz, tmp_path):
    assert _run(pyz, "setup", "--project-only", "--no-graphify", cwd=tmp_path).returncode == 0
    assert _run(pyz, "demo", cwd=tmp_path).returncode == 0
    first = _run(pyz, "report", cwd=tmp_path)
    second = _run(pyz, "report", cwd=tmp_path)
    assert first.returncode == 0, first.stderr
    assert first.stdout and first.stdout == second.stdout
