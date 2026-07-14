---
name: cage
description: Show LLM spend, per-tool savings attribution, and budget from the Cage ledger ($0, deterministic). Trigger when the user asks what a session/project cost, what saved money, or whether they are over budget.
---

# /cage — read the LLM cost & savings ledger

Cage is a *flux*: a deterministic, $0 ledger of LLM token traffic and the savings
each tool in the stack produced. Use the `cage` MCP tools (or the `cage` CLI) to
answer cost / savings / budget questions from real recorded data.

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
- **human attention** ("how much of my time did the agent eat") — `cage human`
  (attested minutes vs `derived (turn-gaps, capped)` minutes on separate lines,
  never summed; both `estimated`). Attest the real figure with `cage outcome
  <task> --minutes N`; `cage calibration --human` measures the heuristic's
  accuracy. `compare`/`verdict`/`study report` print a total-cost line (agent $
  + human minutes × rate) — suppress with `--agent-only`.
- **pre-task estimate** ("what will this cost") — `cage estimate [--label W]` (a
  `modeled` median+IQR band from matching closed tasks; refuses thin history;
  `--record <task>` stamps it so `cage calibration` can measure the hit-rate later).
- **explain a call** — `cage why <call-id>`.
- **unpriced models / price upkeep** ("why is this $0" / a ⚠ UNPRICED line) —
  `cage prices unpriced` prints a ready-to-run fix line per model; find the real
  rate on the vendor's pricing page (cage never fetches), then paste the
  `cage prices set …` / `cage prices alias …` line. `cage prices sync` when
  `doctor` says the bundled prices are newer; `cage policy sync` when it says
  the bundled *policy defaults* are newer (new tunables since init — dry-run
  diff, `--apply` writes; customized values never touched). Derived views re-price
  immediately — the ledger is never rewritten. A ⚠ line about *tool receipts*
  means call-less token savings couldn't resolve a model: run the printed
  `cage prices route-tool <tool> --to <provider>/<model>` fix line (or run the
  tool in a metered session; `cage query receipt-pricing` explains the ladder).
  A `bundled prices are N days old` note (post-commit, doctor, or the report
  footer) means the bundle itself needs a newer cage release — advisory only,
  never a gate; `[prices] stale_days = 0` in policy opts out
  (`cage query prices-freshness` explains all three freshness signals).
- **fleet study** ("does the plugin pay off across our laptops") — `cage study
  join <phase>` per machine → `cage export --study` → analyst runs `cage import
  bundle*.zip` + `cage study report` (coverage first, then a paired-by-machine
  delta tagged `estimated`; opaque machine ids, never hostnames).
- **nothing captured?** — `cage doctor --paths` (read-only probe of every
  candidate log location per agent on this OS, with a why-line per miss), then
  `CAGE_DEBUG=1 cage import` + `cage debug`; `cage doctor --bundle` exports the
  whole diagnosis as one redacted archive.

Every command takes `--json` for machine-readable output.

**Reporting recipes** ("generate my cost report / a CSV / a summary"): the read
views also emit CSV — `--csv` streams to stdout, `--csv <path>` writes a file
(save it where the user asked; default `./cage-report-<view>-<since>.csv`).

- weekly spend — `cage report --csv --since 7d` (add `--by model` / `--by day`)
- per-tool savings — `cage attrib --csv` · ROI — `cage roi --csv`
- is tool X worth it — `cage verdict <tool>` and quote its verdict line verbatim
- fleet number — `cage study report --csv`
- estimate accuracy — `cage calibration --csv`

Summarization rules for any report you write from cage output: quote cage's
numbers **verbatim**; keep the method tags (`measured`/`modeled`/`estimated`)
and the ⚠ UNPRICED / observational caveats in the summary — they are columns in
every CSV, never drop them; never extrapolate or fill gaps — if cage refused
(INSUFFICIENT DATA / a min-n line), the summary says so instead of a number.
CSV is one-way reporting for spreadsheets; the re-importable fleet bundle is
`cage export --study` (jsonl) — never blur the two.

To meter this agent, run it under `cage proxy` (point its base URL at the proxy),
or `cage meter -- <cmd>` for a one-shot.

The ledger stores token **counts** only — never prompt bodies (PII-safe by
construction). If `cage report` returns nothing, say so rather than guessing.
