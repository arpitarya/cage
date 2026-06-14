---
inclusion: always
---
# Cage — LLM cost & savings ledger

This workspace meters LLM traffic into `.cage/` (a *flux*: $0, deterministic).
For spend / savings / budget questions, use the `cage` MCP tools (or the `cage`
CLI) — read the recorded ledger, never guess.

- **spend:** `cage report` · **savings:** `cage attrib` / `cage roi`
- **counterfactual:** `cage matrix` · **budget:** `cage budget`
- **meter Kiro's calls:** run under `cage proxy` (point the model base URL at it),
  or `cage meter -- <cmd>` for a one-shot.

The ledger stores token **counts** only — never prompt bodies or holdings.
