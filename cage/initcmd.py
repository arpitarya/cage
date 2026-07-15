"""`cage setup` — scaffold the `.cage/` footprint (policy + gitignored ledger)."""
from __future__ import annotations

from pathlib import Path

from cage import paths, policy

POINTER_START = "<!-- cage:start -->"
POINTER_END = "<!-- cage:end -->"
_POINTER = f"""{POINTER_START}
## Cage — LLM cost & savings ledger

This project meters LLM traffic into `.cage/` (a *flux*: $0, deterministic).

- Spend so far: `cage report` · per-tool savings: `cage insights attrib` · budget: `cage insights budget`
- The ledger carries token *counts*, never prompt text — PII-safe by construction.
- Edit prices / budgets / pipeline order in `.cage/policy.toml`.
{POINTER_END}"""


def run(root: Path, pointer: bool = True) -> dict:
    """Scaffold the `.cage/` footprint at ``root``. ``pointer=False`` skips writing the
    `CLAUDE.md` pointer — used by `cage setup --global`, which inits ``~/.cage`` and must
    never edit the user's home `CLAUDE.md`."""
    fp = paths.Footprint(root)
    fp.base.mkdir(parents=True, exist_ok=True)
    fp.ledger.mkdir(parents=True, exist_ok=True)
    if not fp.policy.exists():
        fp.policy.write_text(policy.default_toml(), encoding="utf-8")
    _gitignore(fp)
    claude_md = str(_claude_pointer(root)) if pointer else ""
    return {"footprint": str(fp.base), "policy": str(fp.policy),
            "ledger": str(fp.ledger), "claude_md": claude_md}


def _gitignore(fp: paths.Footprint) -> None:
    gi = fp.base / ".gitignore"
    fresh = not gi.exists()
    lines = (gi.read_text(encoding="utf-8").splitlines() if not fresh else
             ["# Append-only event log — machine-local, may carry holdings counts.",
              "# Point CAGE_LEDGER at elgar to keep even the counts private (plan §10).",
              "ledger/",
              "# Generated dashboards.",
              "out/"])
    # Heal older footprints: state/ holds machine-local hook buffers (pending edits,
    # session state) — never commit them. Idempotent on re-run.
    needs_state = "state/" not in lines
    if needs_state:
        lines += ["# Machine-local hook buffers (pending edits, session state).", "state/"]
    if fresh or needs_state:
        gi.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
