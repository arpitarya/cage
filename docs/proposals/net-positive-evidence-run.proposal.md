---
doc: proposal — the net-positive evidence run (NET-1)
status: proposed
raised: 2026-08-01
owner: Arpit's hands (no code)
---

# Proposal — NET-1: the run that answers "does graphify pay for itself?"

**Cage has never measured a tool netting positive.** `insights compare` is built and
gated at `MIN_COMPARE_N = 5` closed tasks per arm; leg D produced 1. This run produces
the missing 8 closed tasks. **No code changes.**

## Protocol

- **Where:** cage-lab, `workspace-on` / `workspace-off`, frozen `tinyshop` corpus,
  `.venv` + proven PATH, `on_read = false`, per-workspace `--path`-scoped imports —
  the standing lab laws, unchanged.
- **What is a task:** one closed task record per lab question (`cage task outcome` at
  each close — the join is task-id-first). 5 per arm; the same 5 questions in both
  arms, one agent (claude — the only one that adopts, per leg D).
- **Record the prompt count per cell as it runs** (the D3/D4 lesson, standing).
- **Then:** `cage insights compare` — group totals `measured`, delta `estimated`,
  observational caveat on. Publish to `regression/` dated, whatever the sign.

## Outcomes, pre-committed

| result | meaning | follow-up |
|---|---|---|
| ON arm cheaper | first measured net-positive evidence | README evidence line updates |
| ON arm still dearer | corroborates leg D at n=5 | [larger-lab-corpus](larger-lab-corpus.proposal.md) becomes the live question |
| gate unmet (task-join failures) | a capture bug worth more than the answer | file the finding |

**Pre-committing the interpretation is the point** — no post-hoc reading. Cost:
one lab session + scripted-leg tokens (leg I ran $5.29/70 prompts).
