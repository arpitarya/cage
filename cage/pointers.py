"""The shared "consult Cage for spend" pointer block, embedded into agent instruction /
steering files (Copilot's `copilot-instructions.md`, Kiro's `steering/cage.md`).

Per-agent *wiring* lives in one file per agent — `claudewire.py`, `codexwire.py`,
`copilotwire.py`, `kirowire.py`; a new agent gets its own `<agent>wire.py`. This module
only holds the cross-agent pointer text those wire files share.
"""
from __future__ import annotations

START, END = "<!-- cage:start -->", "<!-- cage:end -->"
POINTER = """## Cage — LLM cost & savings ledger

This project meters LLM traffic into `.cage/` (a *flux*: $0, deterministic).
- For spend / savings questions, prefer the `cage` MCP tools (`cage_report`,
  `cage_attrib`, `cage_budget`) over guessing.
- To meter this agent's own calls, run it under `cage meter -- <cmd>` or point its
  base URL at `cage proxy`.
- The ledger stores token *counts* only — never prompt bodies."""
