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
- **the one-line answer** ("is tool X worth keeping") — `cage verdict <tool>`
  (SAVING / COSTING / INSUFFICIENT DATA, composed from existing views, every
  input method-tagged).
- **counterfactual** ("what would X have cost") — `cage matrix`.
- **measured stack comparison** ("did tasks with the tool actually cost less") —
  `cage compare` (closed tasks grouped by observed stack; n · median · IQR, delta
  tagged `estimated` — observational, refuses tiny groups).
- **budget** ("am I over budget") — `cage budget`.
- **pre-task estimate** ("what will this cost") — `cage estimate [--label W]` (a
  `modeled` median+IQR band from matching closed tasks; refuses thin history;
  `--record <task>` stamps it so `cage calibration` can measure the hit-rate later).
- **explain a call** — `cage why <call-id>`.
- **fleet study** ("does the plugin pay off across our laptops") — `cage study
  join <phase>` per machine → `cage export --study` → analyst runs `cage import
  bundle*.zip` + `cage study report` (coverage first, then a paired-by-machine
  delta tagged `estimated`; opaque machine ids, never hostnames).

Every command takes `--json` for machine-readable output.

If the ledger has no data, metering isn't recording yet — point the user at
`cage setup --wire-only` (Claude Code / Codex) or `cage meter -- <cmd>` (any agent).

The ledger stores token **counts** only — never prompt bodies (PII-safe by
construction). If `cage report` returns nothing, say so rather than guessing.
