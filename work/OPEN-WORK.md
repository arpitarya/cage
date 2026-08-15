# OPEN-WORK — pending work, filed under the record that owns it

Every item sits under its owning ADR ([ownership map](../docs/adr/README.md)) — an item
with no record is a decision with nothing to hold it. **Needs Arpit:**
CONTINUOUS-CAPTURE · COVERAGE-STRIKE-2 · two hands-only probes
(GFX-IDE-PATH-UNPROBED · COPILOT-JETBRAINS-UNPROBED).

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
  **Task `label`/`outcome` is also the subject of MATRIX-BUILD below** (ADR-MATRIX) — a
  ratified read surface for exactly this fact, not yet built.
- **TASK-GRAIN-SPINE** — a metric row carries no `task`. Since P5 retired the claude/copilot
  `calls` writer — and KIRO-CALLS-LEG the kiro one — `taskcorr` and `hookcmd` correlate
  only consumer/custom rows, and any
  future task-grained view starts at zero. Both surfaces say so in place; a
  timestamp-proximity fallback is **forbidden**. Fix is a task grain on the metric kinds —
  a schema decision. Candidate: derive the window from `tasks.jsonl` (session + ts).
  **Now has a second named consumer, 2026-08-15**: ADR-MATRIX's MATRIX-BUILD inherits
  this exact gap — shipped against today's ledger it renders the near-empty day-one
  state (0 joined tasks) for **claude and copilot**, same as `insights commits`' own
  golden fixture already does. **Not kiro** — kiro's calls never reach `ledger.spend()`
  at all (`ledger.ABSENT_SPINES`, a separate and permanent fact; see MATRIX-BUILD and
  TASK-AGENTS-FIELD-DEAD below) — closing this item does not touch kiro's gap. An
  earlier version of this line said "claude, copilot and kiro alike," which conflated
  the two; corrected 2026-08-15 same-day as the per-agent split itself.
- **TASK-AGENTS-FIELD-DEAD** — `tasks.jsonl`'s `agents` field (`tasks.record(agents=…)`,
  read back by `taskgroup.stats()` as `"agents": sorted(trow.get("agents") or [])`) has
  **no live writer**. All three real callers of `tasks.record()` omit `agents=`:
  `hookcmd._session_end` (has the agent in hand — it's a required hook argument — and
  still doesn't stamp it), `clicmds.close_task`, `clicmds.cmd_task_time`. So
  `taskgroup.stats()`'s own `"agents"` output is `[]` on every real task today. Found
  2026-08-15 while designing ADR-MATRIX's per-agent split, which routes around it by
  deriving agent attribution live from joined calls' own `agent` field instead
  (`agents.row_surface`, the same pattern `commitview.py` line 285 already uses for
  authorship) — so MATRIX-BUILD's claude/copilot tables do **not** block on this.
  **Upgraded same-day, 2026-08-15, after the kiro correction**: this field's fallback
  is now the *only* designed path for a closed kiro task to ever be labeled "kiro" in
  ADR-MATRIX instead of diluting its `unattributed` bucket — kiro's calls never reach
  `ledger.spend()` (`ledger.ABSENT_SPINES`), so kiro tasks always hit the
  zero-joined-calls branch that reads this field. Still not a hard MATRIX-BUILD
  blocker (the view ships and is honest without it — kiro tasks just count as
  `unattributed`), but no longer purely cosmetic either. Fix, if picked up: stamp
  `agents=[agent]` in the three call sites above — additive, no reader currently
  depends on the field being empty.

## [ADR-CLI](../docs/adr/0003_cli.md) — the surface

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

## [ADR-COPILOT](../docs/adr/0005_copilot.md)

- **COPILOT-JETBRAINS-UNPROBED** — hands-only, one command. The JetBrains plugin drives the
  local CLI, but the `events.jsonl` writer is gated on `getReverseCallHandler() === undefined`
  — over RPC it may write **no local file**. Run one Copilot agent edit from JetBrains, check
  `~/.copilot/session-state/*/events.jsonl`; `workspace.yaml`'s `client_name` names the
  surface. Pair with GFX-IDE-PATH-UNPROBED.

## [ADR-COVERAGE](../docs/adr/0002_coverage.md)

- **COVERAGE-STRIKE-2** — **Arpit's call.** The "two strikes → a gate" rule (CLAUDE.md) named
  a remedy after the second stale-cell incident: a generator derived from ADR-COVERAGE's own
  tables. A third incident (**COVERAGE-STRIKE-3**, `docs/adr/0002_coverage.md`'s copilot-CLI
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

## [ADR-KIRO](../docs/adr/0006_kiro.md)

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

## [ADR-LEDGER](../docs/adr/0015_ledger.md)

- **LEDGER-REVERSAL-VERIFY — closed 2026-08-15, same day.** ADR-LEDGER reverses
  ADR-KIRO's Kiro-IDE machine-ledger routing: every source now captures into the run's
  one active ledger, no exceptions. The code change (`paths.kiro_ledger`/`kiro_routed`
  collapsed to constants, `importcmd._kiro_leg`/`_drop_routed_kiro_state` deleted) was
  run against the **real** suite (not a sandboxed subset) — `1512 passed, 14 skipped`,
  the remaining failures all environment artifacts unrelated to this change (missing
  `README.md`/`tools/`/`.git` in the scratch copy the run happened in, and a `chmod`
  permission test that root's own write ignores). One real regression surfaced and was
  fixed in the same change: `_import_rollup` was reading kiro's collected rows into the
  `total` line (previously unreachable from a real project sweep — kiro's rows lived in
  a separate `collected` list via the now-deleted routed leg — reachable on every sweep
  once kiro joined the main loop). It now excludes kiro's rows unconditionally, per
  ADR-KIRO's "Kiro contributes no tokens to any total." Test files updated for the new
  routing: `test_kiro_routing.py`, `test_import_unified.py`, `test_kiro_metrics.py`,
  `test_capture_health.py`, `test_capture_log.py`, `test_capture_quality.py`,
  `test_manifest.py`, `test_platform_paths.py`, plus `test_adr_counts.py`'s `_WORDS`
  table (missing "fourteen"/"fifteen" — a pre-existing gap, unrelated to this change,
  fixed in passing since the ADR count bump exposed it).
- **LEDGER-READ-SURFACE** — unaffected by the reversal, still open: no `cage insights
  kiro` view or chats-view columns read `.cage/ledger/kiro/` (`ledger.kiro_metrics()`
  is capture-only). Tracked here rather than only in ADR-KIRO's Known gaps because the
  reversal makes the project-ledger copy of these rows more likely to be what a user
  actually wants to see next.

## [ADR-GRAPHIFY](../docs/adr/0008_graphify.md)

- **GFX-IDE-PATH-UNPROBED** — hands-only, one probe. Whether an IDE-spawned terminal inherits
  the project's `bin/` (so the graphify shim actually resolves there) has never been measured
  (Arpit skipped it 2026-08-14); `docs/adr/0002_coverage.md` marks every IDE interceptor cell
  `‡ UNPROBED` on this account alone. Run one graphify query from a real IDE terminal (VS Code
  / Kiro / JetBrains) and check whether a receipt files. Pair with COPILOT-JETBRAINS-UNPROBED
  (ADR-COPILOT) — same class of probe, same machine visit could do both.
- **GFX-RECEIPTS-REAUDIT** — narrowed to the real ledger only, 2026-08-15. The end-to-end
  path is now **measured working**: `tools/cigraphify`'s `intercept` check drives a bare
  `graphify query` through the shim on a real PATH and files **1 savings row, ~2,562
  tokens gross** (7/7 checks, macOS local). It had reported the opposite for two releases
  because the *checker* read the pre-P4 `ledger/savings/`, which P4 (v0.51) emptied — the
  receipt was always being written to `ledger/graphify/`. So neither the shim nor the
  interceptor is a candidate explanation for
  [regression/2026-07-22-finding-receipts-empty.md](regression/2026-07-22-finding-receipts-empty.md)
  any more. **What remains** is re-auditing this repo's own `~/.cage` for real receipts —
  the old zero is untrustworthy in both directions, and a CI sandbox passing does not
  establish that day-to-day runs here are metered.

## [ADR-CONFIG](../docs/adr/0012_config.md) — `cage.toml`

Ratified 2026-08-15, **none of it built**. Order matters: a strict read against an
incomplete shipped file is a trap, so the inventory items land before the strictness ones.

- **CONFIG-HIDDEN-KNOBS** — three live knobs with readers and env overrides appear nowhere
  in `data/cage.toml`: `[capture] on_read` (`policy.capture_on_read_enabled`),
  `[capture] read_throttle_secs`, `[wiring] python_launcher`. Ship all three. Blocks
  CONFIG-STRICT-READ.
- **CONFIG-DEAD-SECTIONS** — `[budgets]` (USD keys; `policy.budgets`'s only call site is one
  assertion in `tests/test_substrate.py`), `[quality]` and `[display]` ship with zero
  readers. Delete block + reader + `policy._SECTIONS` entry. Two surfaces still teach them:
  `explain_data`'s `[display] usd` entry and `doctorcmd`'s `· bundled prices
  {prices_version}` footer.
- **CONFIG-NO-DEFAULTS** — abolish the *"DEFAULT_CONFIDENCE policy-preferred fallback"*
  family in `constants.py` (six live members). One number, one home; a constant that exists
  to be overridden is a default in disguise. Blocks CONFIG-STRICT-READ.
- **CONFIG-STRICT-READ** — a missing key raises `CageError` at the read chokepoint;
  `cage setup` / `cage policy sync` backfill any key the running version knows and the file
  lacks. Errors only when backfill is impossible. Keeps upgrades non-breaking.
- **CONFIG-ENV-EVERY-KEY** — `CAGE_<SECTION>_<KEY>` for every key, tables included and
  **replace-only, never merged**; an alias map grandfathers the five ad-hoc names
  (`CAGE_CAPTURE`, `CAGE_DEBUG`, `CAGE_CLEANUP`, `CAGE_CLEANUP_WARN`,
  `CAGE_AUTHORSHIP_ESTIMATE`). `[meta]` is the one exempt section.
- **CONFIG-TOOLS-ORDER-CONST** — demote `[tools] order` to `constants`. `explain.payload`
  reads it live, so the pipeline explainer must interpolate the constant instead of the
  policy value. Carries ADR-CONFIG's only UNMEASURED veto: one real project with a
  non-default pipeline order reopens it.
- **CONFIG-GATE** — the config surface has no detector, which is why all of the above went
  unseen. Build one: every shipped section is read by `policy` · every key with a reader is
  shipped · every documented env var is consulted · every key names a section in
  ADR-CONFIG's pointer table. Without it the record is prose and the census repeats.
- **CONFIG-STALE-COMMENTS** — three `constants.py` comments still name the pre-rename
  `policy.toml` and the deleted `[prices] stale_days`.

## [ADR-MATRIX](../docs/adr/0014_matrix.md) — token cost across tool combinations

Ratified 2026-08-15, graduated from
[work/compare/tool-combination-matrix.compare.md](compare/tool-combination-matrix.compare.md)
(MATRIX-REVIVAL, verdict B accepted); per-agent split added same-day (Arpit); kiro's
token-basis corrected same-day (Arpit caught it). **Nothing built yet.**

- **MATRIX-BUILD** — `cage/matrixview.py` (new module) on `taskgroup.join`: per
  **(agent bucket, stack signature)**, `n` closed tasks · median/IQR of
  `tokens_in`+`tokens_out` · gross tokens saved from `ledger.receipts`. Renders as
  **two** independent token tables — claude, copilot — plus a fixed, unconditional
  no-data notice for **kiro** and an `unattributed` bucket for a task whose joined calls
  disagree on agent or name none; never one blended cross-agent table. **Kiro gets no
  token table at all, permanently** — `ledger.SPEND_SOURCES["kiro"] = ()`
  (`ledger.ABSENT_SPINES`) means `ledger.spend()`, what `taskgroup.join` is built on,
  contains zero Kiro rows by design (Kiro's on-disk store gives no summable count; its
  real usage is **credits**, read by `ledger.credits`, a different unit this tokens-only
  view does not touch). Agent bucket is **derived from joined calls' own `agent` field**
  (`agents.row_surface`, unanimous-only); falls back to `tasks.jsonl`'s dead `agents`
  field **only** when zero calls joined — the sole route by which a kiro task (which
  always hits that branch) could ever be counted as "kiro" instead of diluting
  `unattributed` — see TASK-AGENTS-FIELD-DEAD below, now a kiro-specific blocker, not
  just additive. Register `insights matrix` in `cage/cli.py` next to
  `chats`/`graphify`/`commits`, same flag set, plus `--agent claude|copilot|kiro` (kiro
  prints the fixed notice, not an error). No `prices` import, no `display`/`credits`
  context — tokens-only from line one. A tool with zero receipts (today: caveman)
  renders as an honestly-empty row in every table, never a faked or modeled number
  inside a measured one.
  **Blocked-in-practice by TASK-GRAIN-SPINE (ADR-LAWS) for claude/copilot only** —
  build it, but the two token tables ship rendering the near-empty day-one state (0
  joined tasks) until that item closes; a dedicated empty-state message (mirroring
  `insights chats`' empty-ledger block) is part of this item, not a follow-up. **Kiro's
  gap is separate and does NOT close with TASK-GRAIN-SPINE** — conflating the two was
  an error in this record's first per-agent draft, corrected same-day. **Even once
  TASK-GRAIN-SPINE closes, claude/copilot coverage stays uneven**: closing a task at
  all favors claude (full `session-start`/`tool`/`session-end` hook set) over copilot,
  where `agents.HOOK_GAPS` means auto-close reliably closes zero tasks and `cage task
  outcome` is the practical path. ADR-MATRIX §1/§2 record all of this.
- **MATRIX-DOC-DRIFT** — `docs/example/cli.md` still lists `cage insights matrix` as a
  live command (dead since SURFACE-CUT, 2026-08-14). MATRIX-BUILD makes the line true
  again; until then it is stale.

## How this file is maintained

Continuously, in the same change as the work. A completed item is **deleted, not ticked** —
legal only once [IMPLEMENTATION.md](IMPLEMENTATION.md) records it and evidence reaches
[regression/](regression/), residuals carried forward as their own lines. **Its own markers
are never evidence** — reconcile against git and the owning ADR. The header's checkable
claims are gated by `tests/test_queue_honesty.py`. Full law: [`../CLAUDE.md`](../CLAUDE.md)
*Documentation discipline*.
