"""Path resolution for the per-project `.cage/` footprint + agent homes (plan §3, §5)."""
from __future__ import annotations

import os
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from ``start`` to the dir containing a ``.cage/`` footprint."""
    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / ".cage").is_dir():
            return parent
    return None


def bundled_data_dir() -> Path:
    """Seed data shipped with the cage package (default policy + skill assets)."""
    return Path(__file__).parent / "data"


def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


class Footprint:
    """The per-project ``.cage/`` layout (plan §3).

    The ledger carries token *counts*, never prompt bodies — PII-safe by
    construction (plan §10). For Orff, point ``CAGE_LEDGER`` at elgar so even the
    counts live in the private store.
    """

    def __init__(self, root: Path):
        self.root = root
        self.base = root / ".cage"

    @property
    def ledger(self) -> Path:
        return Path(os.environ.get("CAGE_LEDGER", self.base / "ledger"))

    @property
    def calls(self) -> Path:
        return self.ledger / "calls.jsonl"

    @property
    def receipts(self) -> Path:
        return self.ledger / "receipts.jsonl"

    @property
    def policy(self) -> Path:
        return self.base / "policy.toml"

    @property
    def out(self) -> Path:
        return self.base / "out"

    def out_file(self, name: str) -> Path:
        self.out.mkdir(parents=True, exist_ok=True)
        return self.out / name
