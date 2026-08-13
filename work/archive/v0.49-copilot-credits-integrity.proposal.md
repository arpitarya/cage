---
doc: proposal — copilot credits: no lost deltas, one billing basis per shutdown
status: proposed
raised: 2026-08-02
owner: unclaimed (Opus tier when picked up — money-path semantics, substrate-adjacent)
---

# Proposal — COPILOT-CREDITS integrity: the two defects v0.44 shipped with

v0.44's capture is right about *what* a credit is; the CLI shutdown loop has two
defects in *where the delta lands*, plus two guard gaps downstream.

## Defect 1 — the delta is silently lost when the first-listed model went idle

`transcript.py` ~459–467: `if not (din or dout): continue` runs **before**
`credits=cred_delta if i == 0` — but `prev_cred` has already advanced.

So a resumed session whose shutdown 2 uses only model B (model A still index 0, zero
delta) drops the credit delta on the floor: no row carries it, `prev_cred` moved on,
no debug log. Undercounts billed spend permanently.

The same latent hole drops the legacy `premium` delta.

## Defect 2 — multi-model shutdowns double-count

`totalPremiumRequests` is computed by GitHub over **all** models in the shutdown, but
cage stamps the whole delta on row 0 while sibling rows price via the token rung.

The copilot total is then credits + tokens for the *same* consumption — which is
neither basis. The shipped fixture
(`tests/fixtures/transcripts/copilot/cli/expected.json`, rows 000/001) is exactly this
shape, so the v0.44 handoff's "totals correct" claim does not hold here.

## Guard gaps

- A cumulative counter that ever **decreases** (store rewrite, reset on resume) yields
  a negative `cred_delta` stored verbatim → negative dollars silently shrinking every
  USD total. Nothing clamps or flags; `NaN`/`Infinity` would also pass `json.loads`.
- `compare.py:129,160` still labels group totals **`measured`** though credit-priced
  dollars are `modeled` by the feature's own law — report and chats degrade via
  `creditprice.method_for`; compare does not. A configured rate reads as an invoice.

## Sketch

- **Delta placement:** stamp the shutdown's credit delta on a row the loop *actually
  emits* (deterministic pick — largest `tokens_in` delta, ties by model name), or emit
  a zero-token carrier row when every model idled. Never decided by dict order.
- **One basis per shutdown:** when a shutdown carries a credit delta, that shutdown's
  rows price by credits and **not** by tokens (mark siblings so the ladder skips rung
  2 for them) — or split the credit pro-rata by token delta. This is a genuine fork:
  reopen [copilot-pricing-basis.compare.md](../compare/copilot-pricing-basis.compare.md)
  for the call rather than deciding it inside a fix commit.
- **Clamp:** negative delta ⇒ treat as counter reset (delta = new cumulative value),
  log under `CAGE_DEBUG`; non-finite ⇒ drop the key (absent, never fabricated).
- **Method law:** thread `creditprice.method_for` through compare like report/chats.

## Evidence

Review: [review](../regression/2026-08-02-review-v0.37.0-to-v0.44.0.md)
§1.2, §1.6, §2.9. Defect 1 verified directly
against HEAD 2026-08-02. Real-store field semantics:
[research/2026-08-02-copilot-credit-fields-real-stores.md](../research/2026-08-02-copilot-credit-fields-real-stores.md).

## Trigger

Defects, filed as a proposal so the basis fork gets its compare-doc debate instead of
an inline call. Related queue items: **COPILOT-PREMIUM-DEAD** (the `premium` int is
part of defect 1's blast radius — decide its removal in the same program) and
**COPILOT-SIDECAR** (unchanged, still parked).
