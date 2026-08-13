# 2026-07-24 — Field gate after the hook heal: is the Phase 4 evidence still valid?

A check triggered by this session's own change. The stale-wiring heal
(`2026-07-24-capture-log-hook-gap.md`) migrated the real machine's global Claude
hook to shim-relative form, which **narrows when the hook fires** — now only in
projects with their own local `cage setup`, versus the old absolute-path form that
fired everywhere. Phase 4 (delete the token-capture hooks) is gated on a field
comparison. So: did the heal skew the gate? And does the F6 finding move Phase 4?

## The gate, restated

Phase 4's pass criterion (`docs/phase2-field-gate.md`): over the **same work**,
`ids(hooks-off) ⊇ ids(hooks-on)` for every ledger kind — no row that **only** the
hook caught. Capture-on-read must add up to everything the real-time hook did, or the
hooks can't be deleted.

## Finding 1 — a *properly run* gate is unaffected by the heal

The gate spec mandates the hooks-on arm be a **stock `cage setup` install with hooks
firing** (§Procedure, Machine A). A deliberate `cage setup` writes the local shim, so
the shim exists, so the migrated hook **does** fire. A gate run as written is valid.

**The heal changes nothing for the intended procedure.** It only changes *ambient*
behaviour on machines that never ran a local setup.

## Finding 2 — the real risk: do NOT use ambient production data as the hooks-on arm

The tempting shortcut — "we already have the production machine's ledger, use it as
hooks-on" — is now **unsafe**, and silently so:

- Post-heal, the production hook fires only in locally-set-up projects.
- An ambient "hooks-on" ledger drawn from work in *un-set-up* projects is really a
  **hooks-off** ledger in disguise.
- Comparing two hooks-off ledgers makes `ids(hooks-on) − ids(hooks-off)` trivially
  empty — the gate **passes vacuously and proves nothing.**

This is a new false-pass mode the heal introduced. Mitigation — add one line to the
gate's honesty notes: *"and hooks genuinely on"* — verify the hooks-on arm is a
project where the shim exists and the hook is observed firing (a `capture.log` line
per turn once the F6-fix lands, or a hook-side `CAGE_DEBUG` trace until then).

## Finding 3 — the F6 gap is a free pre-check that *advances* Phase 4

The heal + F6 diagnosis created a natural experiment on real data:

- The hook wrote **1,674 `claude-code` rows** in a 6-hour window, bypassing
  `capture.log` (`2026-07-24-capture-log-hook-gap.md`).
- Claude Code **always writes its transcript**, and capture-on-read reads the
  transcript. So the question the gate asks is directly testable now: **does
  `importcmd.ensure_captured` reproduce those same 1,674 row ids from the
  transcript?**
- Run capture-on-read over the same span on a copy of the ledger root and compute
  `ids(hook-written) − ids(capture-on-read)`. Empty ⇒ real-machine evidence toward
  the gate's superset criterion, on live data, without waiting for a two-machine
  setup to accrue.

**Caveat, per the gate's own honesty note:** single-machine re-derivation *cannot
fully* prove the real-time hook added nothing (the transcript it reads was written
under hooks-on conditions). So this is a **strong pre-check, not a gate pass** — it
can *fail* Phase 4 cheaply (if rows are missing, the hook matters), but a clean result
still needs the two-machine confirmation before deletion. Use it to decide whether
Phase 4 is worth scheduling, not to skip the gate.

## Finding 4 — the F6 breadcrumb fix is Phase-4-coupled; keep it deferred

Extending the `capture.log` breadcrumb to the hook path (the deferred F6-fix) is
**wasted if Phase 4 deletes the hook.** Its value right now is the opposite of a fix:

- As **instrumentation for the gate** — a per-turn `capture.log` line is exactly how
  Finding 2's "hooks genuinely on" check would be verified. That argues for doing the
  breadcrumb fix *only if* Phase 4 is deferred long enough that the gate needs it.
- Sequencing: resolve Phase 4's direction (delete vs keep the hooks) **before**
  investing in the hook's breadcrumb. If kept, do the fix and use it for the gate; if
  deleted, the fix never happens.

## Actions (none are code in this note — it's an acceptance-analysis, like the gate)

1. **Amend `docs/phase2-field-gate.md`** honesty notes with "hooks genuinely on" —
   the ambient-data false-pass mode (Finding 2). *Propose; Arpit's call to apply.*
2. **Optional cheap pre-check** (Finding 3): capture-on-read vs the 1,674 hook rows on
   a ledger copy — a Sonnet task, `--no-import` reads, id-set diff only, never row
   bodies. Decides whether to schedule Phase 4.
3. **Hold the F6 breadcrumb fix** behind the Phase 4 direction (Finding 4).
4. Phase 3 (F3/F5/F7) is independent of all of the above — safe to run in parallel.

## Process note

Same discipline as the F1/F6 diagnoses: the one live side effect of the day's change
(the hook heal) is followed through to the thing it could quietly break (the blocked
phase's evidence), stated as a false-pass risk rather than assumed harmless.
