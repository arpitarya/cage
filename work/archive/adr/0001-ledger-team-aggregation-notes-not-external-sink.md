# ADR 0001 — Team ledger aggregation via `refs/notes`, not an external sink

- **Status:** Accepted (v0.9.0, plan §3.6.3)
- **Date:** 2026-06-25
- **Deciders:** Arpit (ratifier), Claude Code (executor)

## Context

Each developer's Cage ledger (`.cage/ledger/`) is gitignored and machine-local — correctly,
because committing per-developer per-task spend into permanent, shared, undeletable git
*history* is a productivity-surveillance surface even with counts-only bodies. But teams
want a repo-wide cost/ROI number, which nothing combines today.

The obvious "enterprise" answer is an external collector: each machine POSTs rows to an
S3 bucket / time-series DB / OpenTelemetry collector, and a dashboard reads the union.

## Decision

**Team aggregation uses a single `refs/notes/cage-ledger` git ref, not an external sink.**

- Each machine's `.cage/ledger/` is the local buffer; `cage ledger-sync` unions local
  call/receipt rows into the ref **by row id** (`mergeutil.union_by_id`), the same pure
  merge-by-id law §3.5 already uses for provenance. Two machines only ever *add*
  globally-unique ulids, never edit a shared line — union-by-id is a CRDT for append-only
  logs, so there is no merge conflict.
- **CI is the sole writer** (`CAGE_NOTES_WRITE=1`); a dev machine's `ledger-sync` defaults
  to a dry-run print — identical discipline to `notes-sync`.
- Rows live in one note on the repo's **empty-tree object** (a universal, deterministic
  anchor; ledger rows have no commit to attach to).
- The default rollup dimension is `scope`, **never per-developer identity** — the shared
  artifact is a cost ledger, not a monitoring dataset. Per-person attribution is a
  deferred opt-in (`# v2:` marker), not shipped.

## Consequences

- Keeps the `$0` / stdlib-only / no-infra wedge intact: no new dependency, no service, no
  credentials, no object store. Just `git` (already required).
- The aggregate travels with the repo on clone — zero setup, which is the adoption path
  that actually gets run.
- `report`/`attrib --team` read the merged ref and **fall back to local** when it's
  empty/missing (fail-open, report-only — never a build gate).

## Veto condition (when to revisit)

If call/receipt volume per repo genuinely exceeds what git notes should hold —
**single-digit GB/yr is fine; 100s of GB is not** — revisit with an `export` shard to an
out-of-repo store. **Only then, and only with a named volume number.** Until that number
exists, the external-sink idea stays rejected; the place to add it is a new `export`
command, leaving the notes path as the default.

## Related decision — write-path size block (deliberately not taken)

The ledger-size warning (§3.6.4) is **warn-only on the read/derive path**: a derive never
refuses (the flux invariant). This ADR records that a *write-path* hard block — refusing
to append once a shard/volume crosses a quota — was **considered and not taken in v0.9.0**,
but is *not* dogmatically rejected. Precedent exists (`[budgets] on_exceed = warn|block`),
and the CI-runner-with-a-disk-quota case is real. It belongs to the writer, as its own
decision with its own threshold semantics — not bundled into the read-path warning. Left
as a future ADR, not a `# v2:` half-build.
