"""`cage init` — scaffold the `.cage/` footprint (policy + gitignored ledger)."""
from __future__ import annotations

from pathlib import Path

from cage import paths, policy

POINTER_START = "<!-- cage:start -->"
POINTER_END = "<!-- cage:end -->"
_POINTER = f"""{POINTER_START}
## Cage — LLM cost & savings ledger

This project meters LLM traffic into `.cage/` (a *flux*: $0, deterministic).

- Spend so far: `cage report` · per-tool savings: `cage attrib` · budget: `cage budget`
- The ledger carries token *counts*, never prompt text — PII-safe by construction.
- Edit prices / budgets / pipeline order in `.cage/policy.toml`.
{POINTER_END}"""


def run(root: Path) -> dict:
    fp = paths.Footprint(root)
    fp.base.mkdir(parents=True, exist_ok=True)
    fp.ledger.mkdir(parents=True, exist_ok=True)
    if not fp.policy.exists():
        fp.policy.write_text(policy.default_toml(), encoding="utf-8")
    _gitignore(fp)
    pointer = _claude_pointer(root)
    return {"footprint": str(fp.base), "policy": str(fp.policy),
            "ledger": str(fp.ledger), "claude_md": str(pointer)}


def _gitignore(fp: paths.Footprint) -> None:
    gi = fp.base / ".gitignore"
    if gi.exists():
        return
    gi.write_text("# Append-only event log — machine-local, may carry holdings counts.\n"
                  "# Point CAGE_LEDGER at elgar to keep even the counts private (plan §10).\n"
                  "ledger/\n"
                  "# Generated dashboards.\n"
                  "out/\n", encoding="utf-8")


def _claude_pointer(root: Path) -> Path:
    path = root / "CLAUDE.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# CLAUDE.md\n"
    if POINTER_START in text:
        head, _, rest = text.partition(POINTER_START)
        _, _, tail = rest.partition(POINTER_END)
        text = head + _POINTER + tail
    else:
        text = text.rstrip() + "\n\n" + _POINTER + "\n"
    path.write_text(text, encoding="utf-8")
    return path
