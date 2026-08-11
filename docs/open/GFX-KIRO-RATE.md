---
item: GFX-KIRO-RATE
lane: your hands · trigger, not a task
status: parked on accumulating usage
raised: 2026-08-07
---

# GFX-KIRO-RATE — how often does kiro's stdout cap refuse a real graphify query?

**n = 2 today** (1 filed, 1 refused) — enough to prove both branches execute, **not**
enough to be a rate. [kiro field run](../regression/2026-08-07-gfx-cov-kiro-field-run.md).

**Why it matters:** [ADR 0009](../adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md)'s
veto reopens the design **below a 10% file rate**. If typical `query` output sits above
kiro's ~2000-token cap, *report-read-only may be the honest kiro answer* — a legitimate
outcome, not a defeat.

## Why this cannot be forced

It needs **accumulated ordinary kiro-cli graphify usage**. Scripting it produces a rate
for synthetic queries, which answers a different question. This is a **trigger waiting on
evidence, not a task** — treat it as such.

**No code change until the number exists.** Re-run the field script in the kiro run
report, publish the rate to [regression/](../regression/), then decide.

Commands: [FIELD-RUNBOOK §3](../FIELD-RUNBOOK.md).
