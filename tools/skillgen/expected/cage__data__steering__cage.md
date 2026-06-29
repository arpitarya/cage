---
inclusion: always
---

# Cage — LLM cost & savings ledger

This workspace meters LLM traffic into `.cage/` (a *flux*: $0, deterministic). For
spend / savings / budget questions, use the `cage` MCP tools (or the `cage` CLI) —
read the recorded ledger.

Run the command that matches the ask and show its output **verbatim** — it is a
pre-formatted table. Never invent a number.

- **spend** ("what did this cost") — `cage report` (add `--by model`, `--by day`,
  or `--since 7d`).
- **savings** ("what saved money / which tool helped") — `cage attrib` (per-tool
  marginal) · `cage roi` (saved $ vs each tool's own cost).
- **counterfactual** ("what would X have cost") — `cage matrix`.
- **budget** ("am I over budget") — `cage budget`.
- **explain a call** — `cage why <call-id>`.

Every command takes `--json` for machine-readable output.

To meter Kiro's calls, run under `cage proxy` (point the model base URL at it), or
`cage meter -- <cmd>` for a one-shot.

The ledger stores token **counts** only — never prompt bodies (PII-safe by
construction). If `cage report` returns nothing, say so rather than guessing.
