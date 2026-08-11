---
item: COPILOT-SIDECAR
lane: parked · gated on trigger R3
status: deferred half of COPILOT-CREDITS — parked, not lost
---

# COPILOT-SIDECAR — the per-call cache and the real routed model

`agentHostUsage/<session>.jsonl` carries two things cage currently cannot see:

- per-call `cacheReadTokens` — without it the vscode `cached` column is **honestly
  empty**, not wrong;
- the **real routed model** behind `copilot/auto`.

It is debug-gated and deleted with its session, which is why it was deferred rather than
built.

**Gate:** trigger R3 of
[compare/copilot-pricing-basis.compare.md](../compare/copilot-pricing-basis.compare.md).

## One correction that keeps resurfacing

The old OPEN-WORK phrasing said `elapsedMs` → `gap_ms`. **That half is VOID, not
pending** — `gap_ms` was removed with the human axis in v0.36. Do not reintroduce it; the
amputation was deliberate and needs a proposal to revisit.

Related, and unaffected by the 2026-08-11 credits closures:
[archived proposal](../archive/v0.49-copilot-credits-integrity.proposal.md).
