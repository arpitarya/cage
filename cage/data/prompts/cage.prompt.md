---
description: Read LLM spend & per-tool savings from the Cage ledger ($0, deterministic)
---
# Cage — LLM cost & savings

Answer cost / savings / budget questions from the recorded **Cage** ledger using
the `cage` MCP tools (or the `cage` CLI) — never guess a number.

- **spend:** `cage report` (add `--by model` / `--by day` / `--since 7d`)
- **savings:** `cage attrib` (per-tool) · `cage roi` (saved $ vs each tool's cost)
- **counterfactual:** `cage matrix` · **budget:** `cage budget`
- **meter this agent:** run it under `cage proxy` (point its base URL at the proxy),
  or `cage meter -- <cmd>` for a one-shot.

The ledger stores token **counts** only — never prompt bodies. If it is empty,
metering isn't recording yet; say so rather than inventing figures.
