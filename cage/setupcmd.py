"""`cage setup` — install the /cage assets for a chosen agent (plan §6, §9.6).

Asset copy, per agent (per-project hook/MCP wiring is `cage hooks install`). The
target agent is **explicit** — `cage setup` installs only the surfaces it is asked
for, never all four by default. Two scopes, same assets:

  scope=global (default — one machine-wide copy, every repo sees it):
    claude  → ~/.claude/skills/cage/            (slash-command skill)
    codex   → ~/.codex/skills/cage/             (slash-command skill)
    copilot → <vscode-user>/prompts/cage.prompt.md   (reusable Copilot prompt)
    kiro    → ~/.kiro/steering/cage.md           (user steering doc)

  scope=project (committed with the repo — the team gets it, nothing machine-wide):
    claude  → <root>/.claude/skills/cage/
    codex   → <root>/.codex/skills/cage/         (Codex scans repo .codex/skills, issue #21907)
    copilot → <root>/.github/prompts/cage.prompt.md
    kiro    → <root>/.kiro/steering/cage.md

Idempotent. Global paths are env-overridable (CAGE_VSCODE_USER, KIRO_HOME, …).
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


def _skill_base(name: str, project: bool, root: Path | None) -> Path:
    """Skill-dir parent for a skills agent (claude/codex): repo `.<name>` vs home."""
    if project:
        return root / f".{name}"  # .claude / .codex at the repo root
    return paths.claude_home() if name == "claude" else paths.codex_home()


def run(surfaces: tuple[str, ...] | None = None, *, scope: str = "global",
        root: Path | None = None) -> dict:
    """Install the assets for ``surfaces`` (default: all four).

    ``scope="project"`` writes the assets into the repo at ``root`` (committed,
    team-shared) instead of the machine-wide home. The CLI layer requires an
    explicit choice; ``None`` (all four) is kept for callers that want every agent."""
    project = scope == "project"
    if project and root is None:
        raise ValueError("project scope needs a root")
    picked = surfaces or SURFACES
    data = paths.bundled_data_dir()
    out: dict[str, str] = {}

    for skill, prompt, steer in _ASSETS:
        for name in ("claude", "codex"):
            if name in picked:
                dst = _skill_base(name, project, root) / "skills" / skill
                _copy_skill(data / "skills" / skill, dst)
                out[f"{name}:{skill}"] = str(dst)

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
