"""`cage watch` — an optional foreground poll loop (plan §3.7).

Capture is pull-based and cage installs **no** OS scheduler (no launchd/systemd/cron/
schtasks, no `cage scheduler` command). For users who want a running loop they control,
`cage watch` re-imports every interval until Ctrl-C — a plain stdlib `sleep` poll, no
filesystem-watch dependency. It registers nothing and stops with the terminal; the
heaviest thing cage ever runs. Hands-off automation, if wanted, is the user's own cron
line calling `cage import` — documented, never installed by cage.
"""
from __future__ import annotations

import time
from pathlib import Path

from cage import importcmd


def _cycle(root: Path, agent: str, args) -> list[str]:
    """One import sweep. Factored out so a single cycle is unit-testable without the loop."""
    return importcmd.run(root, agent, args)


def run(root: Path, args) -> int:
    interval = max(1, getattr(args, "interval", 60))
    agent = getattr(args, "agent", "all")
    print(f"cage watch: importing {agent} every {interval}s — Ctrl-C to stop. "
          "(No OS job registered; stops with this terminal.)")
    try:
        while True:
            for line in _cycle(root, agent, args):
                print(line)
            time.sleep(interval)
    except KeyboardInterrupt:  # clean exit — leaves nothing registered
        print("\ncage watch: stopped.")
        return 0
