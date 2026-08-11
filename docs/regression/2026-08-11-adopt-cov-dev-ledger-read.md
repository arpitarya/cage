# ADOPT-COV — half B read on the real dev ledger (2026-08-11)

**Half B is real, and it is not single-agent.** `cage insights adoption` on this repo's
own ledger attributes **7 of 9 savings rows (78%)** across **two** agents. The queue's
standing description of this view — "on the dev ledger the shim route has produced
*zero* rows", "3 of 6 by session" — is **stale**. Read the numbers below, not that text.

## What the tool actually printed

**A · invocations** (exact, agent-blind)

| op | runs | receipt | non-measured |
|---|---|---|---|
| `query` | 5 | 5 | 0 |
| `explain` | 2 | 2 | 0 |
| — | 1 | 0 | 1 |

| route | runs | receipt | non-measured |
|---|---|---|---|
| transcript | 6 | 6 | 0 |
| **shim** | **2** | 1 | 1 |

**B · per-agent attribution**

| agent | tool | rows | joined via |
|---|---|---|---|
| claude | graphify | 6 | session |
| copilot | graphify | 1 | session |

Coverage: **7 of 9 (78%)**. 8 runs carry no attestation.

## The three findings

1. **The shim route is no longer zero — it is 2 runs.** The premise under which
   ADOPT-COV was filed ("the view has never been exercised against the path most real
   invocations take") no longer holds. It has been exercised, twice, and one of the two
   produced a receipt.

2. **The shim route's unattributability is STRUCTURAL, and the tool already says so.**
   Verbatim: *"agent-unknown: 1 graphify row(s) carry no call and no session — the
   interceptor runs as a subprocess and cannot know which agent spawned it (structural,
   not a capture gap)."* This is the finding the queue item pre-committed to reporting.
   It is reported, in output, unprompted. **No fix is owed** — and adding an `agent`
   field to usage rows remains a capture change needing its own proposal, exactly as
   filed.

3. **The L1-attested table is EMPTY** — "by agent — attested by an L1 hook" printed zero
   rows, while the session-join produced seven. So attestation contributes **nothing** to
   coverage today; the 78% is entirely session-join. That is the live gap, and it belongs
   to **L1-FIELD**, not to ADOPT-COV.

## What remains of ADOPT-COV

The lab-cell run through the PATH interceptor for each of three agents was the *means*
to this answer, not the answer. The answer arrived from real usage. What is left is
narrower and is L1-FIELD's: **why does the attested table read zero when
`.cage/state/attest.jsonl` is non-empty?** Filed there.
