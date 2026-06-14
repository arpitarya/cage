"""`cage setup` — install the /cage skill into the agent homes (plan §6, §9.6).

Copies the bundled skill to ~/.claude/skills/cage/ and ~/.codex/skills/cage/ so the
slash command is available everywhere. Idempotent. Per-project hook/MCP wiring is
`cage hooks install`; this is the one-time global asset copy.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from cage import paths


def _copy_skill(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, dst / f.name)


def run() -> dict:
    skill_src = paths.bundled_data_dir() / "skills" / "cage"
    out = {}
    for home in (paths.claude_home(), paths.codex_home()):
        dst = home / "skills" / "cage"
        _copy_skill(skill_src, dst)
        out[home.name] = str(dst)
    return out
