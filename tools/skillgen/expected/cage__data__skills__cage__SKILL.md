---
name: cage
description: Show LLM spend, per-tool savings attribution, and budget from the Cage ledger ($0, deterministic). Trigger when the user asks what a session/project cost, what saved money, or whether they are over budget.
---

# /cage — read the LLM cost & savings ledger

Cage is a *flux*: a deterministic, $0 ledger of LLM token traffic and the savings
each tool in the stack produced. Use the `cage` CLI (or the `cage` MCP tools if
wired) to answer cost / savings / budget questions from real recorded data.

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

If the ledger has no data, metering isn't recording yet — point the user at
`cage setup --wire-only` (Claude Code / Codex) or `cage meter -- <cmd>` (any agent).

The ledger stores token **counts** only — never prompt bodies (PII-safe by
construction). If `cage report` returns nothing, say so rather than guessing.
