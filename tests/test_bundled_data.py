"""Bundled-data access through `paths.bundled_data()` (importlib.resources).

The migration off `Path(__file__).parent / "data"` is the zipapp prerequisite
(work/archive/v0.22-restricted-env.handoff.md): under a wheel/editable install the helper
must behave byte-identically to the old form; the zip side is exercised by
tests/test_zipapp.py over a real built cage.pyz.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from cage import adoptcmd, paths, policy

REPO_DATA = Path(__file__).resolve().parents[1] / "cage" / "data"


def test_bundled_data_is_the_package_data_dir():
    # Editable/wheel installs get a real filesystem Path — same target as before.
    assert str(paths.bundled_data()) == str(REPO_DATA)


def test_default_toml_is_the_bundled_file_verbatim():
    assert policy.default_toml() == (REPO_DATA / "cage.toml").read_text(encoding="utf-8")




def test_distribution_is_wheel_outside_a_zipapp():
    assert paths.distribution() == "wheel"


# NB: the skill-asset copy test was removed with the rendered skill/prompt/steering
# assets and `setupcmd`. `cage setup` now only scaffolds + wires MCP + the graphify
# shim (below).


def test_graphify_shim_copies_byte_identical_with_exec_bit(tmp_path, monkeypatch):
    """`_install_shim` now writes the twin PAIR (v0.38.0, docs/shim-contract.md) and
    returns the path of whichever twin this OS actually resolves — `graphify.cmd` on
    Windows, the extensionless `graphify` everywhere else. Both bundled copies must be
    byte-identical to what's on disk, whichever one the returned path names."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/graphify")
    dst = adoptcmd._install_shim(tmp_path)
    assert dst is not None
    shim = Path(dst)
    assert shim.name == paths.graphify_shim_name()
    for name in paths.GRAPHIFY_SHIMS:
        assert (shim.parent / name).read_bytes() == (REPO_DATA / "shims" / name).read_bytes()
    if os.name == "posix":
        assert shim.stat().st_mode & stat.S_IXUSR


def test_the_bundle_ships_no_price_table():
    """`data/prices.toml` is gone and `[prices]`/`[credits]`/`[billing]`/`[alias]` are
    not in the merged policy — cage measures usage, not cost (USAGE-ONLY, ADR 0011)."""
    from cage import paths, policy
    assert not (paths.bundled_data() / "prices.toml").is_file()
    pol = policy.load(None)
    for section in ("prices", "credits", "billing", "alias"):
        assert section not in pol, f"[{section}] is back in the bundled policy"
