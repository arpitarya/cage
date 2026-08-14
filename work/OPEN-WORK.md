# OPEN-WORK — pending work, filed under the record that owns it

Every item sits under its owning ADR ([ownership map](../docs/adr/README.md)) — an item
with no record is a decision with nothing to hold it. **Needs Arpit:**
CONTINUOUS-CAPTURE · COVERAGE-STRIKE-2 · two hands-only probes (GFX-IDE-PATH-UNPROBED ·
COPILOT-JETBRAINS-UNPROBED).

## [ADR-LAWS](../docs/adr/0001_laws.md) — substrate

- **UNREAD-FACTS** — five facts are written and read by nothing: `route_key` reclaim
  (`savings.record` — confirmed dead, not just unlinked: `tests/test_canonical_ledger.py`'s
  own comment says the reclaim backstop is GONE, SURFACE-CUT) · `state/attest.jsonl` (every
  L1 hook — L1 benefit *(a)*, `attest.read`/`read_by_tool` have zero callers outside
  `attest.py`) · `scope` (§3.6.2 — `ledger.by_scope` has zero callers and no `--scope` flag
  exists anywhere in `cli.py`) · task `label`/`outcome` (`commitjoin`/`commitview` only test
  the field's *presence* as a task-closed gate, never surface the recorded value) ·
  `[capture] import_before_export` / `policy.import_before_export` (added 2026-08-15 by
  STUDY-CUT — its last surface was the fleet bundle export; kept because removing the key
  would orphan it in every project that has run `cage policy sync`). Per fact:
  earn a read surface (ADR-CLI) or stop writing it. **`project` (§3.7) dropped off this list,
  2026-08-15** — `importcmd.py`'s manifest-naming fallback (`b["project"]` when a session has
  no vendor title) now feeds `manifest.record_import`'s `session_name`, which
  `chats._title_map` reads, so the cwd basename can render as a chat title in `cage insights
  chats`. *(`[tools] order` was listed here wrongly — `explain.payload` reads it.)*
- **TASK-GRAIN-SPINE** — a metric row carries no `task`. Since P5 retired the claude/copilot
  `calls` writer — and KIRO-CALLS-LEG the kiro one — `taskcorr` and `hookcmd` correlate
  only consumer/custom rows, and any
  future task-grained view starts at zero. Both surfaces say so in place; a
  timestamp-proximity fallback is **forbidden**. Fix is a task grain on the metric kinds —
  a schema decision. Candidate: derive the window from `tasks.jsonl` (session + ts).

## [ADR-CLI](../docs/adr/0002_cli.md) — the surface

- **DOCGEN-DEAD-REF** — `cage/paths.py`'s `builtin_source_docs()` (and the comment above
  `_SOURCE_DOC_PATHS`) still call out `python -m tools.docgen --target policy` as the
  regeneration command for the bundled `[sources]` comment block — but `tools/docgen` no
  longer exists (absorbed into ADR-CLI in the hookless rebuild, GOLDENS-ORPHANED). Worse:
  `builtin_source_docs()` itself has no caller anywhere in `cage/` or `tests/` — it may be
  fully dead code, or the bundled-policy regeneration step it served may need a live
  replacement. Found sweeping `tools/docgen` citations while closing GOLDENS-ORPHANED
  (2026-08-15). Fix is either: confirm it's dead and delete it + the stale comment, or find/
  restore whatever now regenerates `data/cage.toml`'s `[sources]` block and repoint the
  comment at it.

- **CONTINUOUS-CAPTURE** — **Arpit's call.** `cage import` is manual-only (`watch`/`proxy`
  gone) and Claude Code sweeps transcripts at ~30 days, so a missed import is permanent
  loss. This record forbids a scheduler, so the only option on the table is printed
  guidance cage never installs.
- **ADR-CLI-PARSE-CHECK** — the Examples section's guarantee is *existence only*
  (`test_cli_reference.py`'s walker never calls `parse_args`), narrowed from a false
  "every line is checked to parse" claim during the ADR-correctness sweep (2026-08-15) —
  two examples were shipped missing a required positional and would have failed (they
  were `study start`/`study join`, both since removed with the fleet study — the *gap*
  is unchanged). A real parse-check is a separate gate to build, not a docs edit.

## [ADR-COPILOT](../docs/adr/0004_copilot.md)

- **COPILOT-JETBRAINS-UNPROBED** — hands-only, one command. The JetBrains plugin drives the
  local CLI, but the `events.jsonl` writer is gated on `getReverseCallHandler() === undefined`
  — over RPC it may write **no local file**. Run one Copilot agent edit from JetBrains, check
  `~/.copilot/session-state/*/events.jsonl`; `workspace.yaml`'s `client_name` names the
  surface. Pair with GFX-IDE-PATH-UNPROBED.

## [ADR-COVERAGE](../docs/adr/0008_coverage.md)

- **COVERAGE-STRIKE-2** — **Arpit's call.** The "two strikes → a gate" rule (CLAUDE.md) named
  a remedy after the second stale-cell incident: a generator derived from ADR-COVERAGE's own
  tables. A third incident (**COVERAGE-STRIKE-3**, `docs/adr/0008_coverage.md`'s copilot-CLI
  Chat title cell, fixed in the 2026-08-15 ADR correctness sweep) showed that remedy would
  **not** have caught it — the cell was wrong because a belief about the code went stale, not
  because arithmetic drifted, and a generator built on the same belief reproduces it.
  **Compare doc filed 2026-08-15:**
  [work/compare/coverage-strike-gate.compare.md](../work/compare/coverage-strike-gate.compare.md)
  — found that four of the five candidate registries are agent-level, not the agent×surface
  grain the tables render at, and STRIKE 3's own cell has no backing registry at all; proposed
  verdict **D, close the two-strikes counter**, with the cheap narrow generator (option B)
  shippable separately since it would have caught STRIKE 1. Awaiting Arpit's accept or
  override.

## [ADR-KIRO](../docs/adr/0005_kiro.md)

- **AUTHORSHIP-CODE-CATCHUP** — the record is ratified and says in its own §1 that three of
  its decisions are unbuilt; honest, but only until this closes. **(a)** `COVERAGE_GAPS` still
  carries the corrected-away structural claim for copilot and kiro — replace with *"no parser
  yet"* naming the store, keeping **copilot · cloud** as the one structural entry. **(b)**
  `coverage_note()` is silent on the ~30-day retention wall bounding the one agent it covers.
  **(c)** `commitview`'s `declared` column: read the trailer at render time, print agent +
  model, state the failure in cluster terms — **no provenance row, no `method` rung** (the
  quarantine is structural; persisting it is the signal it failed). Update this record in the
  same change. Doc half is done.
- **AUTHORSHIP-PARSERS** — optional, and the reason the gap strings matter. Four parsers,
  each moving one `COVERAGE_GAPS` entry, in reach order: **copilot · CLI** (`events.jsonl` →
  `tool.execution_start.arguments`, already open every sweep) → **kiro · IDE** (largest
  historical prize, nothing deletes it; scan for JSON containing `"executionId"`, never
  hardcode the hex dirs) → **kiro · CLI** (`data.sqlite3`, read-only) → **copilot · VS Code**
  (`chatSessions` first; `chatEditingSessions` self-deletes on stop, so it needs a cadence
  cage lacks — pairs with CONTINUOUS-CAPTURE). Ratified as an order, not as work.

## [ADR-GRAPHIFY](../docs/adr/0007_graphify.md)

- **GFX-IDE-PATH-UNPROBED** — hands-only, one probe. Whether an IDE-spawned terminal inherits
  the project's `bin/` (so the graphify shim actually resolves there) has never been measured
  (Arpit skipped it 2026-08-14); `docs/adr/0008_coverage.md` marks every IDE interceptor cell
  `‡ UNPROBED` on this account alone. Run one graphify query from a real IDE terminal (VS Code
  / Kiro / JetBrains) and check whether a receipt files. Pair with COPILOT-JETBRAINS-UNPROBED
  (ADR-COPILOT) — same class of probe, same machine visit could do both.
- **GFX-RECEIPTS-REAUDIT** — residual of the now-closed DOGFOOD-SHIM-STALE. `bin/graphify` /
  `bin/graphify.cmd` had drifted to the SURFACE-CUT-deleted data-group verb (last touched
  `b30e20e`), so every graphify run inside this repo fell through **unmetered** — a live
  candidate explanation for the zero-real-receipts finding in
  [regression/2026-07-22-finding-receipts-empty.md](regression/2026-07-22-finding-receipts-empty.md).
  Verified 2026-08-15: both shims now match `cage/data/shims/graphify{,.cmd}` byte-for-byte
  and are committed (`15cfbb4`), `cage doctor` reports `✔ wiring`. Re-run that audit to confirm
  real receipts file now that the metering gap is closed — the old zero is no longer trustworthy
  either way.

## How this file is maintained

Continuously, in the same change as the work. A completed item is **deleted, not ticked** —
legal only once [IMPLEMENTATION.md](IMPLEMENTATION.md) records it and evidence reaches
[regression/](regression/), residuals carried forward as their own lines. **Its own markers
are never evidence** — reconcile against git and the owning ADR. The header's checkable
claims are gated by `tests/test_queue_honesty.py`. Full law: [`../CLAUDE.md`](../CLAUDE.md)
*Documentation discipline*.
