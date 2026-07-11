"""The committed runtime-resolving shim: `.cage/bin/cage-run` (plan §5).

Wired hook/MCP entries used to embed the wiring machine's *absolute* cage path
(`paths.cage_bin()` at setup time). Several wired files are committed to git
(`.mcp.json`, `.vscode/mcp.json`, `.claude/settings.json`, `.codex/hooks.json`,
`.kiro/hooks/*.hook`, `.kiro/settings/mcp.json`) — so one developer's path
shipped to the whole team and every clone got broken wiring. The fix: committed
wiring references a **committed shim** that resolves cage *at runtime* on each
machine; only user-level (per-machine) configs keep an absolute path.

The shim's contract is cage's own fail-open law extended to wiring:

- identical bytes on every machine (nothing machine-specific inside — safe and
  intended to be committed; `.cage/.gitignore` excludes only ledger/out/state);
- resolution order (documented, mirrored by the Windows twin):
  1. `cage` on PATH (`command -v cage`)
  2. well-known installs: `~/.local/bin/cage` (pip --user / pipx default),
     `~/.local/pipx/venvs/cage/bin/cage`, an active `$VIRTUAL_ENV/bin/cage`
  3. `python3 -m cage` if the package is importable
  4. **exit 0 silently** — a clone without cage installed keeps working agents,
     no noise, no capture. Diagnosis lives in `cage doctor`, never the hook path.
- all args pass through (`cage-run import` ⇒ `cage import`).

`cage-run` is plain POSIX sh (no bash-isms); `cage-run.cmd` is the Windows twin
(`where cage` → `%USERPROFILE%` installs → `Scripts\\` venv → `py -m cage`) —
UNVERIFIED on a real Windows agent host, same label discipline as the Kiro
Windows layout in `paths.py`. Execute bit is set at write time, fail-open for
`core.fileMode=false` repos / filesystems that reject chmod.
"""
from __future__ import annotations

import stat
from pathlib import Path

# Repo-root-relative shim paths (POSIX separators — these strings are what the
# committed wiring embeds, so they must be identical on every OS).
SHIM_REL = ".cage/bin/cage-run"
SHIM_CMD_REL = ".cage/bin/cage-run.cmd"

_SH = """\
#!/bin/sh
# cage-run — cage-managed runtime resolver (committed; identical on every machine).
# Resolves the cage CLI at run time so no wired file carries an absolute path.
# cage absent => exit 0 silently (fail-open: agents keep working, no capture).
# See `cage query portable-wiring`. Regenerate with `cage setup`.
if command -v cage >/dev/null 2>&1; then exec cage "$@"; fi
for c in "$HOME/.local/bin/cage" "$HOME/.local/pipx/venvs/cage/bin/cage"; do
  if [ -x "$c" ]; then exec "$c" "$@"; fi
done
if [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/cage" ]; then
  exec "$VIRTUAL_ENV/bin/cage" "$@"
fi
if command -v python3 >/dev/null 2>&1 && python3 -c "import cage" >/dev/null 2>&1; then
  exec python3 -m cage "$@"
fi
exit 0
"""

_CMD = """\
@echo off
rem cage-run.cmd — cage-managed runtime resolver (committed; identical on every machine).
rem Windows twin of cage-run: same order, same fail-open exit 0 when cage is absent.
rem UNVERIFIED on a real Windows agent host (same label discipline as paths.py).
where cage >nul 2>nul
if %errorlevel%==0 (
  cage %*
  exit /b %errorlevel%
)
if exist "%USERPROFILE%\\.local\\bin\\cage.exe" (
  "%USERPROFILE%\\.local\\bin\\cage.exe" %*
  exit /b %errorlevel%
)
if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\\Scripts\\cage.exe" (
  "%VIRTUAL_ENV%\\Scripts\\cage.exe" %*
  exit /b %errorlevel%
)
py -3 -c "import cage" >nul 2>nul
if %errorlevel%==0 (
  py -3 -m cage %*
  exit /b %errorlevel%
)
exit /b 0
"""


def shim_path(root: Path) -> Path:
    return root / ".cage" / "bin" / "cage-run"


def write(root: Path) -> dict:
    """Write both shim files under ``root/.cage/bin/`` — byte-identical content on
    every machine, so `cage setup` twice (or on two machines) never produces a diff.
    Only rewrites when bytes differ (no mtime churn on re-setup). The execute bit is
    best-effort: a `core.fileMode=false` repo or a chmod-rejecting filesystem must
    never break setup (fail-open)."""
    bin_dir = root / ".cage" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, text in (("cage-run", _SH), ("cage-run.cmd", _CMD)):
        path = bin_dir / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8", newline="\n")
        try:
            path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass  # fileMode=false / FAT — the .cmd twin needs no bit; sh can still run it
        written[name] = str(path)
    return written


def selflocating_command(sub: str) -> str:
    """The committed hook command for hosts that provide neither a repo variable nor
    a guaranteed repo cwd — Codex (hook cwd is the *session* cwd, possibly a subdir;
    its own docs recommend resolving from the git root) and Kiro (hook cwd is
    undocumented, and Kiro's relative-path record is unreliable). POSIX shell:
    locate the repo root via git, exec the committed shim, and exit 0 when either
    is missing — fail-open, no noise in the agent's hook run."""
    return (f'r="$(git rev-parse --show-toplevel 2>/dev/null)" && '
            f'[ -x "$r/{SHIM_REL}" ] && exec "$r/{SHIM_REL}" {sub}; exit 0')


def is_shim_reference(command: str) -> bool:
    """Does a wired command string already reference the shim (any host's form —
    `$CLAUDE_PROJECT_DIR`, `${workspaceFolder}`, or plain relative)?"""
    return "cage-run" in (command or "")
