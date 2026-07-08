"""Install cage's two local git hooks (plan §3.5) — never wired by `claudewire.py`
since these are git hooks, not Claude Code hooks.

- `post-commit`     → resolve this session's pending-edit buffer into a hooked
  provenance row against the just-made commit's sha (`hooks.post_commit`).
- `prepare-commit-msg` → stamp `Co-authored-by` / `Change-Origin` / `Agent-Session`
  trailers from the buffered rows (ergonomics only).

Both are bypassable (`git commit --no-verify` skips them like any git hook) and
idempotent: install() never overwrites a hook file it didn't create — it checks for
a cage marker line and leaves a foreign hook alone.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

from cage import paths

_MARKER = "# cage-managed-hook"


def _files() -> dict:
    # Resolved cage path — a GUI git client (IDE commit button) runs hooks with a
    # minimal PATH that omits ~/.local/bin, so a bare `cage` would not be found.
    c = paths.quoted_cage_bin()
    return {
        "post-commit": f"#!/bin/sh\n{_MARKER}\n{c} hook-post-commit\n",
        "prepare-commit-msg": f'#!/bin/sh\n{_MARKER}\n{c} hook-prepare-commit-msg "$1"\n',
    }


def _git_dir(root: Path) -> Path | None:
    d = root / ".git"
    return d if d.is_dir() else None  # worktrees/submodules (a `.git` file) skipped, fail-open


def install(root: Path) -> dict:
    """Write any of the two hook files that are absent or already cage-managed.
    A foreign (non-cage) hook at the same path is left untouched. Fail-open."""
    installed: list[str] = []
    skipped: list[str] = []
    git_dir = _git_dir(root)
    if git_dir is None:
        return {"installed": installed, "skipped": skipped, "reason": "no .git dir"}
    hooks_dir = git_dir / "hooks"
    try:
        hooks_dir.mkdir(parents=True, exist_ok=True)
        for name, content in _files().items():
            path = hooks_dir / name
            if path.exists() and _MARKER not in path.read_text(encoding="utf-8", errors="ignore"):
                skipped.append(name)  # a real, non-cage hook already lives here
                continue
            path.write_text(content, encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            installed.append(name)
    except OSError:
        pass
    return {"installed": installed, "skipped": skipped}


def status(root: Path) -> bool:
    git_dir = _git_dir(root)
    if git_dir is None:
        return False
    return any((git_dir / "hooks" / name).exists()
              and _MARKER in (git_dir / "hooks" / name).read_text(encoding="utf-8", errors="ignore")
              for name in _files())
