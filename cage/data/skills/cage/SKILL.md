---
name: cage
description: Show LLM spend, per-tool savings attribution, and budget from the Cage ledger ($0, deterministic). Trigger when the user asks what a session/project cost, what saved money, or whether they are over budget.
---

# /cage — read the LLM cost & savings ledger

Cage is a *flux*: a deterministic, $0 ledger of LLM token traffic and the savings
each tool in the stack produced. Use the `cage` CLI (or the `cage` MCP tools if
wired) to answer cost/savings/budget questions from real recorded data — never guess.

## How to respond

1. Run the command that matches the ask and show its output verbatim (it is a
   pre-formatted table):
   - **"what did this cost / spend so far"** → `cage report` (add `--by model`,
     `--by day`, or `--since 7d` as appropriate).
   - **"what saved me money / which tool helped"** → `cage attrib` (per-tool
     marginal savings) or `cage roi` (saved $ vs each tool's own cost).
   - **"what would X have cost / is the stack worth it"** → `cage matrix`.
   - **"am I over budget"** → `cage budget`.
   - **"explain this call"** → `cage why <call-id>`.
2. Every command takes `--json` for machine-readable output.
3. If `cage report` is empty, metering isn't recording yet — point the user at
   `cage setup --wire-only` (Claude Code/Codex) or `cage meter -- <cmd>` (any agent).

## Don't

- Don't invent numbers. If the ledger has no data, say so.
- Don't read prompt bodies from the ledger — it stores token counts only.
