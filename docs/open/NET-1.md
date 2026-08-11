---
item: NET-1
lane: your hands
status: open · ungated
raised: 2026-07
---

# NET-1 — does graphify actually pay?

**The only open item that answers why cage exists.** Everything else is correctness work
on a tool whose payoff is still unmeasured. If this comes back negative, half the queue
is moot.

**Gate:** none. Its only gate (ID-ENTROPY) closed 2026-08-02.

## Protocol

- **n = 5 closed tasks per arm.** Arms: with-graphify / without.
- **Outcomes pre-committed before the runs** — write down what "pays" means first.
- Corpus **frozen**: `tinyshop` is never mutated. A new question gets a new named corpus
  alongside it; every result is labelled by the corpus that produced it.

Full protocol: [proposal](../proposals/net-positive-evidence-run.proposal.md).
Commands: [FIELD-RUNBOOK §5](../FIELD-RUNBOOK.md).

## The pre-committed branch

Still net-negative at n=5 ⇒ that is the trigger for
[larger-lab-corpus](../proposals/larger-lab-corpus.proposal.md) (tinyshop ~43 KB may
understate graphify) — **not** a reason to re-run until it turns positive.

## Binds this run

Record the **prompt count per cell as it runs** — D3/D4 are UNVERIFIED without it. F2's
copilot-VS-Code receipt limit is **UNTESTED**; never claim it confirmed.
