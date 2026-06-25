"""Guided `cage setup` — init → project wiring → global skill, one step at a time.

Pure orchestration over the existing idempotent primitives (`adoptcmd` for
scaffold + per-project hook/MCP wiring + graphify shim, `setupcmd` for the global
/cage skill). No ledger logic lives here; the wizard is just a friendlier front
door to the granular modes (`cage init` / `cage setup --project-only` /
`cage setup --wire-only --<agent>` / `cage setup --<agent>`).

Two entry shapes, same steps:
  • interactive — `cage setup` in a terminal: pick an agent, then y/n each step.
  • flagged     — `cage setup --claude [--no-skill|--no-project|--no-graphify]`.
"""
from __future__ import annotations

from pathlib import Path

from cage import adoptcmd, agents, setupcmd


def prompt_yes_no(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        ans = input(f"{question} {suffix} ").strip().lower()
        if not ans:
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  please answer y or n.")


def prompt_choice(question: str, options: tuple[str, ...]) -> str:
    print(question)
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    while True:
        ans = input(f"choose 1-{len(options)} [1]: ").strip()
        if not ans:
            return options[0]
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            return options[int(ans) - 1]
        if ans in options:
            return ans
        print("  invalid choice.")


def interactive_plan() -> dict:
    """Walk the user through the steps and return a plan dict."""
    print("cage setup — guided onboarding (Ctrl-C to abort)\n")
    agent = prompt_choice("Which agent are you setting up?", agents.SURFACES)
    skill = prompt_yes_no(f"Install the global /cage skill for {agent}?", True)
    project = prompt_yes_no("Scaffold .cage/ here and wire this project's hooks + MCP?", True)
    graphify = prompt_yes_no("Install the graphify interceptor (bin/graphify + PATH)?", True)
    return {"agent": agent, "skill": skill, "project": project, "graphify": graphify}


def apply(root: Path, *, agent: str, skill: bool, project: bool,
          graphify: bool) -> list[str]:
    """Run the chosen steps for one agent; return human-readable log lines.

    `adopt` already bundles init + per-project wiring + the graphify shim, so we
    route project/graphify through it, then install the global skill on top."""
    log: list[str] = []
    if project or graphify:
        res = adoptcmd.run(root, graphify=graphify,
                           surfaces=(agent,) if project else None)
        log.append(f"✔ .cage/ ready → {res['init']}")
        if "hooks" in res:
            log.append(f"✔ {agent} metering + MCP wired in this project")
        if "shim" in res:
            log.append(f"✔ graphify interceptor → {res['shim']}")
            if res.get("path"):
                log.append(f"✔ bin/ added to PATH in {res['path']} — open a new shell")
        elif graphify:
            log.append("· graphify not installed — interceptor skipped")
    if skill:
        for asset, where in setupcmd.run((agent,)).items():
            log.append(f"✔ global skill {asset} → {where}")
    return log
