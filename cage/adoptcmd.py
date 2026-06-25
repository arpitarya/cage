"""Per-project setup engine — the project-scaffold half of `cage setup` (plan §6).

Drives `cage setup --project-only` (and the project steps of the guided wizard).
Everything a consumer app needs to start metering, with no repo to clone — it all
ships in the `cage-flux` PyPI package:

  1. `cage init`           — scaffold .cage/ (policy + gitignored ledger).
  2. agent wiring          — **opt-in**: wires only the surfaces named in `surfaces`
     (e.g. `--claude`). With no surface flag, no agent is wired — that is a separate,
     explicit step (`cage setup --wire-only <agent>`). One ledger, many surfaces.
  3. graphify interceptor  — drop bin/graphify (routes `graphify query…` through
     `cage graphify`) and add bin/ to the shell rc PATH (unless --no-graphify).

The interceptor shim ships as bundled package data (`data/shims/graphify`), copied
verbatim. Every step is idempotent. Returns a dict of what was done (for --json).
"""
from __future__ import annotations

import shutil
import stat
from pathlib import Path

from cage import agents, initcmd, paths

_PATH_MARK = "# cage adopt: graphify metering interceptor"


def _install_shim(root: Path) -> str | None:
    """Copy the bundled graphify interceptor into <root>/bin; return its path."""
    if not shutil.which("graphify"):
        return None
    src = paths.bundled_data_dir() / "shims" / "graphify"
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    dst = bin_dir / "graphify"
    shutil.copy2(src, dst)
    dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(dst)


def _wire_path(root: Path) -> str | None:
    """Append `export PATH=<root>/bin:$PATH` to the shell rc once. Returns rc path."""
    import os

    bin_dir = root / "bin"
    rc = Path.home() / (".bashrc" if "bash" in os.environ.get("SHELL", "") else ".zshrc")
    line = f'export PATH="{bin_dir}:$PATH"  {_PATH_MARK}'
    existing = rc.read_text() if rc.exists() else ""
    if _PATH_MARK in existing:
        return None  # already wired — idempotent
    with rc.open("a") as fh:
        fh.write(f"\n{line}\n")
    return str(rc)


def run(root: Path, *, graphify: bool = True,
        surfaces: tuple[str, ...] | None = None) -> dict:
    """Set cage up in ``root``. Each key present only if that step ran.

    Agent wiring is opt-in: ``out["hooks"]`` appears only when ``surfaces`` names
    at least one agent. With no surface flag this scaffolds + (optionally) the
    graphify shim, but touches no agent config."""
    out: dict[str, object] = {"init": initcmd.run(root)["footprint"]}
    if surfaces:
        out["hooks"] = agents.install(root, surfaces)
    if graphify:
        if shim := _install_shim(root):
            out["shim"] = shim
            if rc := _wire_path(root):
                out["path"] = rc
    return out
