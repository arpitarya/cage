@@FRONTMATTER@@

@@HEADER@@

@@INTRO@@

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
- **fleet study** ("does the plugin pay off across our laptops") — `cage study
  join <phase>` per machine → `cage export --study` → analyst runs `cage import
  bundle*.zip` + `cage study report` (coverage first, then a paired-by-machine
  delta tagged `estimated`; opaque machine ids, never hostnames).
- **nothing captured?** — `cage doctor --paths` (read-only probe of every
  candidate log location per agent on this OS, with a why-line per miss), then
  `CAGE_DEBUG=1 cage import` + `cage debug`; `cage doctor --bundle` exports the
  whole diagnosis as one redacted archive.

Every command takes `--json` for machine-readable output.

@@METER@@

The ledger stores token **counts** only — never prompt bodies (PII-safe by
construction). If `cage report` returns nothing, say so rather than guessing.
