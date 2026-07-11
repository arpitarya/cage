"""Bundled-data access through `paths.bundled_data()` (importlib.resources).

The migration off `Path(__file__).parent / "data"` is the zipapp prerequisite
(docs/archive/v0.22-restricted-env.handoff.md): under a wheel/editable install the helper
must behave byte-identically to the old form; the zip side is exercised by
tests/test_zipapp.py over a real built cage.pyz.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from cage import adoptcmd, paths, policy, setupcmd

REPO_DATA = Path(__file__).resolve().parents[1] / "cage" / "data"


def test_bundled_data_is_the_package_data_dir():
    # Editable/wheel installs get a real filesystem Path — same target as before.
    assert str(paths.bundled_data()) == str(REPO_DATA)


def test_default_toml_is_the_bundled_file_verbatim():
    assert policy.default_toml() == (REPO_DATA / "policy.toml").read_text(encoding="utf-8")


def test_bundled_policy_loads_with_prices():
    pol = policy._bundled()
    assert pol.get("prices"), "bundled policy must carry price tables"
    assert "anthropic" in pol["prices"]


def test_distribution_is_wheel_outside_a_zipapp():
    assert paths.distribution() == "wheel"


def test_setup_copies_skill_files_byte_identical(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude_home"))
    setupcmd.run(("claude",))
    for skill in ("cage", "cage-doctor"):
        src_dir = REPO_DATA / "skills" / skill
        dst_dir = tmp_path / "claude_home" / "skills" / skill
        copied = sorted(p.name for p in dst_dir.iterdir())
        expected = sorted(p.name for p in src_dir.iterdir() if p.is_file())
        assert copied == expected
        for name in copied:
            assert (dst_dir / name).read_bytes() == (src_dir / name).read_bytes()


def test_graphify_shim_copies_byte_identical_with_exec_bit(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/graphify")
    dst = adoptcmd._install_shim(tmp_path)
    assert dst is not None
    shim = Path(dst)
    assert shim.read_bytes() == (REPO_DATA / "shims" / "graphify").read_bytes()
    if os.name == "posix":
        assert shim.stat().st_mode & stat.S_IXUSR
