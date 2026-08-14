# OPEN-WORK — pending work, filed under the record that owns it

Every item sits under its owning ADR ([ownership map](../docs/adr/README.md)) — an item
with no record is a decision with nothing to hold it. **Needs Arpit:**
CONTINUOUS-CAPTURE · COVERAGE-STRIKE-2 · three hands-only probes (GFX-IDE-PATH-UNPROBED ·
GFX-COV-FIELD · COPILOT-JETBRAINS-UNPROBED).

## [ADR-LAWS](../docs/adr/0001_laws.md) — substrate

- **UNREAD-FACTS** — five facts are written and read by nothing: `route_key` reclaim
  (`savings.record`) · `state/attest.jsonl` (every L1 hook — L1 benefit *(a)*, no consumer) ·
  `scope` (§3.6.2) · `project` (§3.7) · task `label`/`outcome`. Per fact: earn a read surface
  (ADR-CLI) or stop writing it. *(`[tools] order` was listed here wrongly — `explain.payload`
  reads it.)*
- **TASK-GRAIN-SPINE** — a metric row carries no `task`. Since P5 retired the claude/copilot
  `calls` writer — and KIRO-CALLS-LEG the kiro one — `taskcorr` and `hookcmd` correlate
  only consumer/custom rows, and any
  future task-grained view starts at zero. Both surfaces say so in place; a
  timestamp-proximity fallback is **forbidden**. Fix is a task grain on the metric kinds —
  a schema decision. Candidate: derive the window from `tasks.jsonl` (session + ts).

## [ADR-CLI](../docs/adr/0002_cli.md) — the surface

- **ADR-OUTPUT-GOLDENS** — ADR-CLI now carries rendered output for all 15 printing views,
  but only **7 are GATED** (byte-exact against `tests/fixtures/goldens/`). The other 8 —
  bare `cage`, `import`, `setup --status`, `doctor`, `query`, `insights graphify`,
  `insights why`, `authorship origin` — are CAPTURED: real stdout with an **ungated body**,
  so a renderer change rots them silently. Fix is a seed + golden per view in
  `tests/goldenseed.py`, then flip the block's class marker.
  **`cage doctor` is the one permanent exception** — it probes the local filesystem, so a
  byte golden over it would assert a fact about the reader's machine (the same call
  `test_output_spec.py` already makes for `cage study join`).
- **DOCTOR-DEAD-VERBS** — `cage doctor`'s `metering` and `timeline` checks print two verbs
  deleted in v0.50 (the `data` group's export and watch) as live guidance. `verbmap` catches
  a dead verb when it is *typed*; nothing catches one that cage itself *prints*. The F1 class
  in a new costume — the reference gate scans docs, not stdout. Found while pasting real
  doctor output into ADR-CLI (2026-08-14); that block is abridged past the lines rather than
  documenting a bug as a contract.
- **GOLDENS-ORPHANED** — 16 of the 27 files in `tests/fixtures/goldens/` are read by nothing
  and render removed surfaces (`I2.txt` shows `insights verdict graphify` with USD).
  `tests/test_output_spec.py`'s docstring still points at `docs/cli-output-spec.md` and
  `python -m tools.docgen --target spec`; **both are gone** — the spec doc was absorbed and
  `tools/docgen` no longer exists, so half the documented re-bless path is dead
  (`CAGE_BLESS_GOLDENS=1` still works). Delete the dead goldens and repoint that docstring at
  ADR-CLI + `tests/test_adr_output_blocks.py`, or restore a docgen that writes the ADR's
  output blocks from the goldens.

- **STATE-RETENTION** — `.cage/state/` has no prune path: SURFACE-CUT deleted the only
  trigger (`cage data cleanup`). `cleanup.py` is kept and tested (`importcmd` + `doctor`
  import it) and `maybe_run` now warns that no command prunes. Needs a verb, or a
  recorded no.
- **CONTINUOUS-CAPTURE** — **Arpit's call.** `cage import` is manual-only (`watch`/`proxy`
  gone) and Claude Code sweeps transcripts at ~30 days, so a missed import is permanent
  loss. This record forbids a scheduler, so the only option on the table is printed
  guidance cage never installs.
- **PLAN-4-REWRITE** — PLAN §4 still calls the deleted `insights attrib` *"the attribution
  engine (the part that's actually novel)"*. Rewrite the section, do not annotate it.

## [ADR-COPILOT](../docs/adr/0004_copilot.md)

- **COPILOT-JETBRAINS-UNPROBED** — hands-only, one command. The JetBrains plugin drives the
  local CLI, but the `events.jsonl` writer is gated on `getReverseCallHandler() === undefined`
  — over RPC it may write **no local file**. Run one Copilot agent edit from JetBrains, check
  `~/.copilot/session-state/*/events.jsonl`; `workspace.yaml`'s `client_name` names the
  surface. Pair with GFX-IDE-PATH-UNPROBED.

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

- **DOGFOOD-SHIM-STALE** — **healed in the working tree, uncommitted.** `bin/graphify` and
  `bin/graphify.cmd` had drifted to the SURFACE-CUT-deleted data-group verb (last touched
  `b30e20e`), so every graphify run inside the cage repo fell through UNMETERED; both files
  now match `cage/data/shims/graphify{,.cmd}` byte-for-byte and `cage doctor` reports
  `✔ wiring`. **The shipped template was never wrong** — this was stale committed dogfood
  wiring. Two residuals keep this item open: the fix is **staged, not committed**, and the
  metering gap it caused is a live candidate explanation for the 0-real-receipts finding,
  which was measured *in this repo* — re-run that audit before trusting the old number.

## No ADR — doc discipline (CLAUDE.md)

- **DOC-BACKTICK-GATE** *(was PLAN-BACKTICK-IMBALANCE)* — the file the imbalance was
  measured in is deleted (`docs/PLAN.md`, 2026-08-14), so the original evidence is gone
  and nothing was ever recorded as fixing it — which is the argument for the gate. An unbalanced
  backtick makes every downstream code-span scan misread the file (how `_doc_flags` was
  silently emptied and an assertion passed vacuously), and nothing fails today. One-line
  detector: strip fences, count backticks, fail on odd.

## How this file is maintained

Continuously, in the same change as the work. A completed item is **deleted, not ticked** —
legal only once [IMPLEMENTATION.md](IMPLEMENTATION.md) records it and evidence reaches
[regression/](regression/), residuals carried forward as their own lines. **Its own markers
are never evidence** — reconcile against git and the owning ADR. The header's checkable
claims are gated by `tests/test_queue_honesty.py`. Full law: [`../CLAUDE.md`](../CLAUDE.md)
*Documentation discipline*.
