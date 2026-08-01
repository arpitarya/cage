# OPEN-WORK — the one plan of pending work

**Next:** **NET-1** — `insights compare`'s A/B answer is already there, n=1 vs a gate
of 5.
**Blocked:** the v0.36 release, on your standing no-commit directive.
**State:** v0.36 built, no tag. `meta`, HUMAN, K2, K3/K4, K+NET, BUD-V, SUITE, CLEAN,
SYNC-GUARD done. 3 items.
Suite: **962 pass / 0 fail**.

## Pending

| # | what | next action |
|---|---|---|
| **NET-1** | `insights compare` answers the A/B already — n=1, gate is 5 | **lab task, your hands** — no code |
| **HR1** | agent-vs-human measurement, **rebuilt from scratch** — a fresh design, not a revert | write a `proposals/` doc first |
| **H** | release v0.36 | blocked — your call to lift the no-commit directive |

**CLEAN closed 2026-08-01** — retention **30 → 90 days**; the auto sweep (piggybacked on
`cage import`) now only **warns** on stderr — count, reclaimable KB, the exact fix,
silent when nothing's eligible, throttled 24h — and never deletes; only `cage data
cleanup --apply` deletes, and it runs regardless of `[cleanup] enabled` (decided: an
explicit command is always honored, `enabled=false` only silences the automatic
reminder). New `[cleanup] warn` switch, default true, env `CAGE_CLEANUP_WARN`. Tool
savings (`ledger/savings/<tool>/`) get the never-per-tool invariant stated at
`cleanup.NEVER` and tested surviving `prune` at `days=0`. 956/0 ⇒ 961/0. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--cleanup-becomes-advisory-90d-default-warn-only-never-per-tool).
[Archived pair](archive/v0.36-cleanup-safety.handoff.md).

**SUITE closed 2026-08-01** — **G-SAV**: `savings.record()` was missing `ts` from its
signature; added and forwarded (kept `**_ignore` for the shim callers), plus a
kwarg-parity guard test. **BUD-V-TEST**: the five sync tests re-pointed from
`[budgets]` (opt-in, commented out by BUD-V) to `[quality] signal` — a table the
bundle actually ships. Same mechanics, different worked example. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--suite-green-g-sav-fixed-bud-v-test-re-pointed-9496--9560).

**SYNC-GUARD closed 2026-08-01** — **guard now, fixture later.** The pain was
*diagnosis*, not repair — 5 budget-unrelated failures with no obvious cause. The
borrowed table/key (`[quality] signal`) now lives in one constant in
`test_policysync.py` (re-point is a one-line edit) and a new guard test fails with the
exact fix if it's ever removed from the bundle. The synthetic-bundle refactor stays
filed with a trigger — a **third** removal: [proposal](proposals/policysync-synthetic-bundle.md).
961/0 ⇒ 962/0. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--sync-guard-name-the-sync-tests-borrowed-table-guard-its-removal).
[Archived prompt](archive/v0.36-sync-guard.prompt.md).

**HR1** — removed completely in v0.36, substrate included; nothing was kept, so this is
a fresh design. What existed: [archived handoff](archive/v0.36-human-removal.handoff.md).

**BUD-V closed 2026-08-01** — verified via `just test` on the dev machine (Python
3.14): the bundle change needs no code fix; `cage policy sync` does not try to re-add
`[budgets]` (an active table buckets as `project_own`, untouched). Goldens P5/P6a/P6b
re-blessed (only the in-sync key count moved, 11→8). Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--budget-ceilings-become-opt-in-bundle-only--verified-bud-v-closed).
**NET-1 needs no code** — `insights compare` is gated at `MIN_COMPARE_N = 5`.

**KIRO-CLI-SCOPE** (carried forward from K2) — kiro-CLI credits captured while the cwd
sits outside any project reach only a *machine-ledger* sweep. Nothing is lost (the store
is re-read), but a user who never runs a project-less `cage import` never sees them.
Revisit if that turns out to be common.

## Decisions open

1. ~~Corpus refresh cadence~~ — **decided 2026-08-01: the corpus is FROZEN.** `tinyshop`
   is never mutated; a new question gets a **new named corpus alongside** it and every
   result is labelled by the corpus that produced it. Old evidence stays valid forever.
   Whether tinyshop is too *small* is a separate, filed question:
   [proposal](proposals/larger-lab-corpus.md).
2. ~~Cost cap for paid legs~~ — **decided: opt-in via `cage.toml`**, bundle ships
   `[budgets]` commented out, no constant fallback. **Verified 2026-08-01 (BUD-V)** —
   see [IMPLEMENTATION.md](IMPLEMENTATION.md). Test-debt closed 2026-08-01 (SUITE,
   re-pointed at `[quality]`); the residual coupling is closed 2026-08-01 (`SYNC-GUARD`,
   above) — the synthetic-bundle fixture itself stays a parked
   [proposal](proposals/policysync-synthetic-bundle.md) behind a third-removal trigger.

## Binds the next lab run

- **F2's copilot-VS-Code receipt limit is UNTESTED** — never claim it confirmed.
- **Record the prompt count per cell as it runs** — D3/D4 are UNVERIFIED without it.

## How this file is maintained

Continuously; completed items **deleted, not ticked**; its own markers are never
evidence. Full law: [`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*.
Done work: [IMPLEMENTATION.md](IMPLEMENTATION.md) · evidence: [regression/](regression/).
