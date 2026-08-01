# ADR 0005 — graphify receipt ids are session-inclusive; cross-route dedupe is a content-key deferral, not id-collision

- **Status:** Accepted (unreleased, graphify-capture plan GC3)
- **Date:** 2026-07-28
- **Deciders:** Arpit (ratifier), Opus (executor)

## Context

- graphify savings can now be captured by **four routes**: the PATH shim, graphify's
  native receipt shim, the GC2 **transcript** detector, and GC2 **report-reads**.
- Two routes can see the *same* run: the shim files live at query time; `cage import`
  later re-detects that same `graphify query` in the transcript. Filed twice, the
  saving inflates — the one thing savings must never do.
- The naive fix — a content-derived, **session-excluded** id so the two routes collide
  and `union_by_id` collapses them — **misattributes**: the identical query run in
  sessions A and B would share one id, so A absorbs the whole saving and B reads zero.
  Per-session attribution is a requirement, not a nicety.
- The other naive fix — a session-inclusive id and nothing else — **fails cross-route
  dedupe**: the shim genuinely cannot know the agent's session (it runs as a Bash
  subprocess with no session env var), so its id and the transcript's never match, and
  the same run is filed twice.
- Root cause of the disagreement: the shim was stamping a **cwd basename in a field
  that claims to be a session** — a fabricated value that guaranteed the mismatch.

## Decision

**The receipt id includes `session`; cross-route convergence is the existing content-key
deferral, extended to the transcript route; and the shim stamps its session honest-empty.**

- **id = `s_` + sha1(`session | op | args_hash | answer_hash`)** (`graphifymeter.receipt_id`).
  Session-inclusive ⇒ the same query in two sessions is two receipts (per-session
  attribution). Re-import of one transcript reproduces the id exactly ⇒ `union_by_id`
  collapses re-imports with zero derived-row growth.
- **Cross-route dedupe is a deferral, not id-collision.** Before filing, the transcript
  route computes the shim's **session-empty** id (`receipt_id("", op, args_hash,
  answer_hash)`) and defers if it is already in the ledger — the exact mechanism that
  already dedupes the native shim (snapshot-before, defer-if-present). Ordering makes it
  unidirectional and sufficient: the shim files synchronously at query time, `cage
  import` always strictly later, so the shim always files first and the transcript always
  defers to it.
- **The shim stamps `session=""`** — an honest absence (cage's standing pattern), never a
  cwd basename. That empty-session id is exactly what the transcript recomputes to defer.
- **`args_hash`/`answer_hash` are route-independent** (`content_signature`): the binary
  spelling (`argv[0]`) is dropped and the answer text is stripped before hashing, so
  `graphify query X`, `/venv/bin/graphify query X`, and the transcript-parsed command
  all sign identically.

## Consequences

- Per-session graphify attribution is exact; the two GC3 acceptance tests both pass —
  (1) same query, two sessions ⇒ two receipts; (2) same query, shim+transcript, one
  session ⇒ one receipt.
- `savings_id` becomes an additive optional kwarg on `make_savings`/`savings.record` (the
  `call_id`/`credit_id`/`row_id` precedent) — no new row field, no enum change. Dedupe
  lives *in the id*, so `union_by_id` carries it everywhere for free: local ledger,
  `refs/notes` merge, and fleet-bundle import all inherit it, instead of each needing its
  own content-key check that one of them will eventually forget.
- **Residual double-count risk:** if the transcript truncates a very long tool result,
  its `answer_hash` differs from the shim's, the deferral misses, and the run is counted
  twice. This is bounded (only truncated long results) and is the exact metric the veto
  condition names.

## Alternatives rejected

- **Content-only id (session excluded).** Collapses the same query across sessions into
  one receipt — confidently-wrong per-session attribution. A slightly-low total is
  tolerable; a wrong per-session number is not. Rejected.
- **Session-inclusive id with no deferral.** The shim can't know the session, so its id
  never matches the transcript's; the same run files twice. Rejected.
- **A separate `tool="graphify-report"` for report-reads to force a distinct row.**
  Fragments graphify's attribution and drops report-reads out of the GC5 history band;
  the weaker inference is better expressed as `op="report-read"` + lower confidence +
  a footnote (still `tool="graphify"`). Rejected.

## Reference

- graphify-capture plan §4 (GC3) and the handoff's decision 2. The native-shim deferral
  this generalizes is documented in `graphifymeter.py`'s module docstring (v0.22.1
  finding #35) — a field-proven mechanism, not a new invention.
- Worked precedent for deterministic-id injection: `schema.make_call(call_id=…)`,
  `make_credit(credit_id=…)`, `make_provenance(row_id=…)`.

## Veto condition (when to revisit)

1. **Falsifiable trigger — the measured double-count rate.**
   - **The metric, named precisely.** Over runs captured by **both** the shim and the
     transcript, `dc = (both-route runs that filed TWO receipts) / (both-route runs)` —
     the share where the deferral *missed*. A deferral *hit* is already counted
     (`counts["deferred"]`); a *miss* is the complement that must be measured against it.
   - **The threshold + sample gate.** **Revisit `answer_hash` iff `dc > 1.0%` measured
     over at least `N = MIN_COMPARE_N` (=5) both-route runs** — below that N the rate is
     noise wearing a percentage (the same min-n discipline as `compare`/`estimate`), so a
     smaller sample **never** reopens the veto, however high its rate. Only the measured
     number, at or above the gate, reopens it — never an argument.
   - **Where the measurement comes from — and the honest gap.** ⚠️ **This rate is NOT yet
     instrumented.** Today a deferral hit increments `counts["deferred"]`, but a *miss*
     silently files a second receipt with nothing tallying it — so `dc` currently **cannot
     be produced**, and the veto is therefore not yet reopenable-by-measurement (a veto you
     can't compute is aspirational, which is exactly what G2 flags). **To arm it:** the
     both-route population and the miss count must be surfaced — the natural home is
     `insights calibration` (the measured-accuracy surface) reading a duplicate-detection
     pass over graphify receipts (same `(op, args_hash)` across the empty-session and a
     real-session id = a miss). **Filed as an OPEN-WORK follow-up (G2, 2026-07-29); build
     nothing here.** Until it ships, `dc` is UNMEASURED, not assumed-zero.
   - The eventual change lands in `graphifymeter.content_signature` only (e.g. key
     `answer_hash` on the cited-file signature, which survives truncation); the id shape
     and the deferral mechanism stay.
2. **Contingent vs. invariant.**
   - *Contingent (auto-revisits on evidence):* the `answer_hash` derivation (trigger 1);
     and the shim's `session=""` — if a future client exposes its session id to Bash
     subprocesses (as an env var), the shim SHOULD stamp the real session and the two
     routes' ids would then match directly, making the deferral redundant (but harmless).
   - *Invariant (moves only by reversing this ADR):* **session is in the id** (per-session
     attribution is a product value, not a tuning knob); and **dedupe lives in the id**,
     not in a per-consumer content-key check.
3. **Deliberately not taken — fixed at source, not papered over.** The shim's old
   fabricated session (a cwd basename in a session field) was **not** kept and worked
   around; it was fixed at the source by stamping `""`. Leaving it and special-casing the
   basename in the deferral was the tempting, wrong shortcut — it would have re-encoded a
   lie the rest of the system then has to know about. If a real session id ever becomes
   available to the shim (the contingent case above), that is the *only* value that
   should replace the empty string — never a cwd basename again.
