"""Per-project setup engine — the project-scaffold half of `cage setup` (plan §6).

Drives `cage setup --project-only` (and the project steps of the guided wizard).
Everything a consumer app needs to start metering, with no repo to clone — it all
ships in the `cage-flux` PyPI package:

  1. `cage setup`           — scaffold .cage/ (policy + gitignored ledger).
  2. agent wiring          — **opt-in**: wires only the surfaces named in `surfaces`
     (e.g. `--claude`). With no surface flag, no agent is wired — that is a separate,
     explicit step (`cage setup --wire-only <agent>`). One ledger, many surfaces.
  3. graphify interceptor  — drop bin/graphify (routes `graphify query…` through
     `cage interceptor graphify`) and add bin/ to the shell rc PATH (unless --no-graphify).

The interceptor ships as bundled package data — a **twin pair**, `data/shims/graphify`
(POSIX sh) and `data/shims/graphify.cmd` (Windows), copied verbatim. Both are installed
on every OS, mirroring `runshim.write`: the inactive twin is inert (never resolved, never
executed), and a `bin/` that is byte-identical on every machine is what lets a project
set up on macOS keep working when it is opened on Windows or under Git Bash. Their one
shared behaviour spec is docs/adr/0007_graphify.md. Every step is idempotent. Returns a dict
of what was done (for --json).
"""
from __future__ import annotations

import shutil
import stat
from pathlib import Path

from cage import agents, initcmd, paths

_PATH_MARK = "# cage adopt: graphify metering interceptor"


def _copy_shim(name: str, dst: Path) -> bool:
    """Copy bundled shim ``name`` onto ``dst`` if the bytes differ; True if written.
    Byte-compare first, exactly like `runshim.write` — a correct shim is left alone, so
    re-setup causes no mtime churn. The execute bit is best-effort and meaningless for
    the `.cmd`, but setting it costs nothing and keeps one code path."""
    import importlib.resources
    src = paths.bundled_data() / "shims" / name
    with importlib.resources.as_file(src) as real:
        if dst.exists() and dst.read_bytes() == real.read_bytes():
            return False
        shutil.copy2(real, dst)
    try:
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass  # fileMode=false / FAT — the .cmd needs no bit, and sh can still run the other
    return True


def _install_shim(root: Path) -> str | None:
    """Copy both bundled graphify interceptors into <root>/bin; return the path of the
    twin this OS resolves (the one worth printing)."""
    if not shutil.which("graphify"):
        return None
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in paths.GRAPHIFY_SHIMS:
        _copy_shim(name, bin_dir / name)
    return str(bin_dir / paths.graphify_shim_name())


def refresh_shim(root: Path) -> bool:
    """Bring an **already-installed** interceptor up to the bundled template; return
    whether anything changed.

    This is the heal for the F1 shim: the copy installed before v0.28.0 probes `cage
    graphify --help`, which now exits 1, so it silently execs the unmetered binary
    forever. Only ever refreshes an **existing** install — creating one from nothing
    stays `_install_shim`'s job (it gates on graphify being installed at all), so this
    never scaffolds into a project that opted out.

    Deliberately completes the pair: if *either* twin is present the project has already
    opted in, so a missing twin is written too. That is the migration path for a project
    scaffolded on POSIX before the `.cmd` existed and then opened on Windows — without
    it, `cage setup` there would report success while leaving PATH interception
    structurally absent. Fail-open: an unreadable/unwritable shim is not worth breaking
    `cage setup` over."""
    targets = paths.graphify_shims(root)
    if not any(p.exists() for p in targets):
        return False
    changed = False
    for dst in targets:
        try:
            changed |= _copy_shim(dst.name, dst)
        except OSError:
            continue
    return changed


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


def run(root: Path, *, graphify: bool = True, surfaces: tuple[str, ...] | None = None,
        hooks: bool = False, skills: bool = False) -> dict:
    """Set cage up in ``root``. Each key present only if that step ran.

    Agent wiring is opt-in: ``out["hooks"]`` appears only when ``surfaces`` names
    at least one agent. With no surface flag this scaffolds + (optionally) the
    graphify shim, but touches no agent config. ``hooks`` (`cage setup --hooks`) and
    ``skills`` (`--skills`) additionally wire the **L1** and **L3** layers — both off by
    default, because the floor must stay reachable by doing nothing."""
    info = initcmd.run(root)
    out: dict[str, object] = {"init": info["footprint"],
                              "migrated_config": info.get("migrated_config"),
                              "migrated_prices": info.get("migrated_prices")}
    if surfaces:
        out["hooks"] = agents.install(root, surfaces, hooks=hooks, skills=skills)
    if graphify:
        if shim := _install_shim(root):
            out["shim"] = shim
            if rc := _wire_path(root):
                out["path"] = rc
    return out
