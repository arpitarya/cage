"""`cage setup` — install the /cage assets for a chosen agent (plan §6, §9.6).

Asset copy, per agent (per-project hook/MCP wiring is `cage hooks install`). The
target agent is **explicit** — `cage setup` installs only the surfaces it is asked
for, never all three by default. Two scopes, same assets:

  scope=global (default — one machine-wide copy, every repo sees it):
    claude  → ~/.claude/skills/cage/            (slash-command skill)
    copilot → <vscode-user>/prompts/cage.prompt.md   (reusable Copilot prompt)
    kiro    → ~/.kiro/steering/cage.md           (user steering doc)

  scope=project (committed with the repo — the team gets it, nothing machine-wide):
    claude  → <root>/.claude/skills/cage/
    copilot → <root>/.github/prompts/cage.prompt.md
    kiro    → <root>/.kiro/steering/cage.md

Idempotent. Global paths are env-overridable (CAGE_VSCODE_USER, KIRO_HOME, …).
"""
from __future__ import annotations

import importlib.resources
import shutil
from pathlib import Path

from cage import paths
from cage.agents import SURFACES


# src is a bundled-data Traversable (a plain Path under a wheel, a zip entry under
# cage.pyz) — as_file materializes each asset so copy2 always sees a real file.
def _copy_skill(src, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file():
            with importlib.resources.as_file(f) as real:
                shutil.copy2(real, dst / f.name)


def _copy_file(src, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with importlib.resources.as_file(src) as real:
        shutil.copy2(real, dst)


# Each tuple: (skill dir under data/skills, prompt file stem, steering file stem).
# `cage` reads the ledger; `cage-doctor` verifies the setup. Both ship to all agents.
_ASSETS = (("cage", "cage", "cage"), ("cage-doctor", "cage-doctor", "cage-doctor"))


def _skill_base(project: bool, root: Path | None) -> Path:
    """Skill-dir parent for the claude skills agent: repo `.claude` vs home."""
    if project:
        return root / ".claude"
    return paths.claude_home()


def run(surfaces: tuple[str, ...] | None = None, *, scope: str = "global",
        root: Path | None = None) -> dict:
    """Install the assets for ``surfaces`` (default: all three).

    ``scope="project"`` writes the assets into the repo at ``root`` (committed,
    team-shared) instead of the machine-wide home. The CLI layer requires an
    explicit choice; ``None`` (all three) is kept for callers that want every agent."""
    project = scope == "project"
    if project and root is None:
        raise ValueError("project scope needs a root")
    picked = surfaces or SURFACES
    data = paths.bundled_data()
    out: dict[str, str] = {}

    for skill, prompt, steer in _ASSETS:
        if "claude" in picked:
            dst = _skill_base(project, root) / "skills" / skill
            _copy_skill(data / "skills" / skill, dst)
            out[f"claude:{skill}"] = str(dst)

        if "copilot" in picked:
            base = (root / ".github") if project else paths.vscode_user_dir()
            copilot = base / "prompts" / f"{prompt}.prompt.md"
            _copy_file(data / "prompts" / f"{prompt}.prompt.md", copilot)
            out[f"copilot:{prompt}"] = str(copilot)

        if "kiro" in picked:
            steer_dir = (root / ".kiro") if project else paths.kiro_home()
            kiro = steer_dir / "steering" / f"{steer}.md"
            _copy_file(data / "steering" / f"{steer}.md", kiro)
            out[f"kiro:{steer}"] = str(kiro)
    return out
