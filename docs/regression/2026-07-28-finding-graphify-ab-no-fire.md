# Finding — graphify savings path works, but the A/B didn't fire through the agents

**Severity:** — · **Status:** ◻ OPEN (product-level; Phase 2 driver change) ·
**Surface:** graphify savings / agent behavior

| field | value |
|---|---|
| Observed in | [run-002](2026-07-28-validation-run-002.md) (V2/V4 graphify-ON cells) |

## What was seen

- **Savings path validated directly:** `cage data graphify -- <graphify> explain
  Transformer00` cited `pkg/big_module.py` and filed a real savings row —
  `raw_alternative=11,810 · actual=118 · saved=11,692 · method="modeled" ·
  confidence=0.6` into `savings/graphify/savings-2026-07.jsonl`. The capture
  mechanism is **live and correct**.
- **But V2/V4 (graphify ON) produced 0 savings rows.** `claude -p` / `copilot -p`
  answered the 3-sentence architecture question **without shelling out to
  graphify**, so the interceptor never fired.
- **Threshold honesty:** a graphify query over the *small* toy modules yields an
  answer larger than the cited files ⇒ `no-saving-to-claim` (correct). Only
  large-file citations (`big_module.py`) produce a saving. Expected, not a bug.

## Status

- **OPEN — product-level, not a cage defect.** The A/B is **agent-behavior
  dependent**: an agent that doesn't invoke graphify produces no interceptor hit,
  so A−B is 0 through no fault of the capture path.
- **Next (Phase 2):** the driver must either prompt explicitly for a graphify query
  or invoke graphify itself, so A−B is measured honestly rather than left to agent
  whim.
