# Phase 2 field gate — the measurable pass criterion

Phase 2 of the capture-architecture rework deletes the token-capture hooks
(`capture-architecture.plan.md`; change-map in `capture-architecture.handoff.md` §9.7).
It is deliberately **not** written yet: Phase 1 (capture-on-read, additive — no hook
touched) shipped in **v0.31.0**, and the hooks are the safety net we refuse to remove
until Phase 1 has *proven in the field* that a read captures everything a hook did.

The gate in the handoff (§10, "Still genuinely open") was prose:

> Phase 1 running in the field long enough to show capture-on-read captures everything
> the hooks did (compare a hooks-on machine's ledger against a hooks-off one over the
> same work).

This file turns that into a concrete, ready-to-run comparison so the waiting period is
measurable. **It is a procedure, not a runner** — nothing here is Phase 2 code, and
running it is not part of this change.

## What "captures everything the hooks did" means, precisely

Two ledgers are built over the **same span of real work**:

- **Hooks-on** — the current v0.31.0 default: the token-capture hooks fire in real time
  *and* capture-on-read sweeps on every read. This is the safety-net baseline.
- **Hooks-off** — capture-on-read as the *sole* path: the hooks never fire, so the only
  thing writing the ledger is `importcmd.ensure_captured` ([cage/importcmd.py](../cage/importcmd.py))
  running lazily before each read.

Every ledger row (calls, receipts, tasks) carries a stable `id`. Compare the two ledgers
**by row id**, with exactly the semantics `mergeutil.union_by_id`
([cage/mergeutil.py](../cage/mergeutil.py)) already uses everywhere else in cage — a row
is identified by its `id`, id-keyed, first-by-id wins on collision.

**Pass criterion — superset, not equality:**

> `ids(hooks-off) ⊇ ids(hooks-on)` for every ledger kind.
> i.e. the set difference `ids(hooks-on) − ids(hooks-off)` is **empty**.

There must be **no row that only the hooks caught**. The reverse direction is allowed and
expected to be empty in practice, but is not a failure: capture-on-read seeing a row the
hook missed only argues *for* deletion. Equality is the likely real-world outcome; the
gate asserts the weaker, correct thing — the hooks add nothing capture-on-read doesn't
already have.

Compare **id sets only** — never row bodies. Two rows with the same id are the same
metering event by construction (append-only ids don't legitimately collide, per
`union_by_id`); field values like an import timestamp will differ between ledgers and are
not part of the gate.

## The env switches

All standing (whole-process) unless noted; flag/env precedence is as documented in
`cage/policy.py`:

| Switch | Effect | Used for |
| --- | --- | --- |
| `CAGE_CAPTURE=0` | pauses **all** capture (hooks *and* on-read) — `policy.capture_enabled` | not used by the gate; the kill-switch for everything |
| `CAGE_CAPTURE_ON_READ=0` | turns off **only** capture-on-read — `policy.capture_on_read_enabled` (default on) | leave **unset/on** for the hooks-off ledger — it is the whole point |
| `--no-import` | suppresses the sweep for a **single** read | read a ledger *without* mutating it while comparing |

For the **hooks-off ledger**, capture-on-read must be **on** (`CAGE_CAPTURE_ON_READ`
unset or `=1`) and the hooks simply must not be installed/firing — that is the
configuration Phase 2 makes permanent.

## Procedure

Do the comparison across two machines (or two ledger roots) over the same work window —
per `capture-architecture.handoff.md` §10, the honest form is *a hooks-on machine vs a
hooks-off machine over the same work*, because re-deriving one ledger from the other on a
single machine can't prove the real-time hook added nothing.

1. **Pick the span.** A fixed window of genuine agent work (a day, a feature) exercising
   the agents whose hooks Phase 2 deletes.
2. **Machine A — hooks-on:** stock v0.31.0 install (`cage setup`), hooks firing, defaults.
3. **Machine B — hooks-off:** hooks **not** installed, `CAGE_CAPTURE_ON_READ` on (default).
   Reads alone drive capture via `ensure_captured`.
4. **Do the same work** on both over the span.
5. **Freeze both ledgers with a final read**, then read each **without further mutation**
   using `--no-import`, so the comparison sees a stable ledger:
   ```
   cage data export --no-import --format json   # or read ledger/*.jsonl directly
   ```
6. **Compare id sets per kind** (calls, receipts, tasks): assemble `ids(A)` and `ids(B)`
   and check `ids(A) − ids(B) == ∅`. Any id in that difference is a row the hook caught
   and capture-on-read did **not** — a gate failure, and each one must be understood
   before Phase 2 proceeds (which agent, which log, why the read missed it).

## Honesty notes (read before trusting a green result)

- **Same work, genuinely.** Divergent work between the two machines makes the id sets
  incomparable — the gate assumes the *only* difference is the capture path.
- **No invented threshold.** The design specifies a **superset**, full stop — not
  "≥ 99% of rows." A single hook-only row is a failure to investigate, not a rounding
  error to wave through.
- **Throttle awareness.** Capture-on-read is throttled (~60s, `_last_import`), so freeze
  with a final unthrottled read (or wait out the throttle) before comparing — a row not
  yet swept is a timing artifact, not a miss. Re-read to confirm before calling a
  difference real.
- **This is a gate, not a runner.** Do not add a comparison command to `cage/**` for
  this — Phase 2's change-map (§9.7) is the code artifact; this file is the acceptance
  test the field must pass first.
