---
item: KIRO-CLI-SCOPE
lane: parked
status: revisit only if it proves common
---

# KIRO-CLI-SCOPE — project-less kiro credits only reach a machine-ledger sweep

kiro-CLI credits captured while the cwd sits outside any project reach only a
*machine-ledger* sweep. **Nothing is lost** — the store is re-read — but a user who never
runs a project-less `cage import` never sees them.

Carried forward from K2. **No action until it turns out to be common.**

## Where this shape has already bitten once

It is the stated limit on the CREDITS-LEGACY-SPLIT count: that count read the *project*
ledger, so a project-less copilot-CLI shutdown is excluded from its zero.
[evidence](../regression/2026-08-11-credits-legacy-split-count.md). The same scoping
applies to copilot, not just kiro.
