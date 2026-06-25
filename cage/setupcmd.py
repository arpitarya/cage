"""`cage setup` — install a global /cage asset into a chosen agent home (plan §6, §9.6).

One-time global asset copy, per agent (per-project hook/MCP wiring is
`cage hooks install`). The target agent is **explicit** — `cage setup` installs only
the surfaces it is asked for, never all four by default:

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
from cage.agents import SURFACES


def _copy_skill(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, dst / f.name)


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


# Each tuple: (skill dir under data/skills, prompt file stem, steering file stem).
# `cage` reads the ledger; `cage-doctor` verifies the setup. Both ship to all agents.
_ASSETS = (("cage", "cage", "cage"), ("cage-doctor", "cage-doctor", "cage-doctor"))


def run(surfaces: tuple[str, ...] | None = None) -> dict:
    """Install the global assets for ``surfaces`` (default: all four).

    The CLI layer requires an explicit choice; ``None`` (all four) is kept for
    callers that genuinely want every agent."""
    picked = surfaces or SURFACES
    data = paths.bundled_data_dir()
    out: dict[str, str] = {}

    for skill, prompt, steer in _ASSETS:
        for name, home in (("claude", paths.claude_home()), ("codex", paths.codex_home())):
            if name in picked:
                dst = home / "skills" / skill
                _copy_skill(data / "skills" / skill, dst)
                out[f"{name}:{skill}"] = str(dst)

        if "copilot" in picked:
            copilot = paths.vscode_user_dir() / "prompts" / f"{prompt}.prompt.md"
            _copy_file(data / "prompts" / f"{prompt}.prompt.md", copilot)
            out[f"copilot:{prompt}"] = str(copilot)

        if "kiro" in picked:
            kiro = paths.kiro_home() / "steering" / f"{steer}.md"
            _copy_file(data / "steering" / f"{steer}.md", kiro)
            out[f"kiro:{steer}"] = str(kiro)
    return out
