"""`cage setup` — install a global /cage asset into every agent home (plan §6, §9.6).

One-time global asset copy, symmetric across all four agents (per-project hook/MCP
wiring is `cage hooks install`):

  claude  → ~/.claude/skills/cage/        (slash-command skill)
  codex   → ~/.codex/skills/cage/         (slash-command skill)
  copilot → <vscode-user>/prompts/cage.prompt.md   (reusable Copilot prompt)
  kiro    → ~/.kiro/steering/cage.md       (user steering doc)

Idempotent. Paths are env-overridable (CAGE_VSCODE_USER, KIRO_HOME, …).
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


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def run() -> dict:
    data = paths.bundled_data_dir()
    skill = data / "skills" / "cage"
    out: dict[str, str] = {}

    for name, home in (("claude", paths.claude_home()), ("codex", paths.codex_home())):
        dst = home / "skills" / "cage"
        _copy_skill(skill, dst)
        out[name] = str(dst)

    copilot = paths.vscode_user_dir() / "prompts" / "cage.prompt.md"
    _copy_file(data / "prompts" / "cage.prompt.md", copilot)
    out["copilot"] = str(copilot)

    kiro = paths.kiro_home() / "steering" / "cage.md"
    _copy_file(data / "steering" / "cage.md", kiro)
    out["kiro"] = str(kiro)
    return out
