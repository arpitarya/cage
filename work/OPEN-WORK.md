# OPEN-WORK — the index of pending work

## In flight

- **LEDGER-RESTRUCTURE is in flight (2026-08-14)** — nine phases, one shape per producer,
  spec in [ledger-restructure.handoff.md](ledger-restructure.handoff.md). **PG shipped**
  (see below); P0–P7 remain.
- **SURFACE-CUT is BUILT (2026-08-14), suite green** — 14 modules, 15 handlers, 12 test
  files and 16 goldens deleted; MCP cut 6 tools → 2. Outcome recorded in
  [IMPLEMENTATION.md](IMPLEMENTATION.md); decision record in
  [surface-cut.decision.md](archive/v0.50-surface-cut.decision.md). The 15 shim tests it
  knowingly left red were closed by PG.

## Not mine — a concurrent session owns these

- **`docs/CLI.md` is being absorbed** (Arpit, 2026-08-14). Deleted from `docs/` by the
  session doing the ADR restructure; **left deleted deliberately** — Arpit is handling the
  fallout. Until its replacement lands, `tests/test_cli_reference.py::test_the_headline_count_matches_the_parser`
  fails and five live docs have a dangling link (`CLAUDE.md`, `README.md`,
  `docs/README.md`, this file's registry sibling, `work/compare/README.md`). The deleted
  copy was SURFACE-CUT-accurate (27 commands, the removed-verb table) and is recoverable
  from HEAD if the absorption is abandoned. **Do not "fix" this by re-pointing the
  citations** — that would pre-empt a decision that is not this queue's.

## Agent-closable

- **GFX-MODEL-ORPHAN** — `graphifymodel` has no reader. `repo_ceiling` (the bounded
  "worth installing here" band) and `history_band` are reachable only from `tests/` and the
  explain registry; both consumers — `insights verdict graphify` and `cage report`'s ceiling
  footer — were deleted. UNREAD-FACTS class, so the same decision applies: earn a read
  surface or retire the module. Worth noting before retiring it: it is the **only** surface
  that ever answered *"what would graphify save me here"* with no receipts on hand — the
  day-one question, currently unanswerable by any command. **PG (2026-08-14) confirmed it
  blocks nothing** and left the module untouched; `docs/FORMULAS.md` §2.10 now says out
  loud that nothing reads it, so the orphan is at least no longer described as live.

- **ADR-COVERAGE-GATE** — `tests/test_formulas_coverage.py` (v0.51) re-derives
  `docs/FORMULAS.md` §2.7's graphify matrix from `graphifytx.GRAPHIFY_COVERAGE`, closing
  ADR-COVERAGE's two-strikes trigger for that table. **It does not cover ADR-COVERAGE's own
  two graphify tables**, which still rely on review alone — the same drift, one doc over.
  Extending the same parse there is small; the full generator stays not-taken.

- **GFX-IDE-PATH-UNPROBED** — hands-only, Arpit's machine, and it is the one assumption
  this program records as an assumption. Interceptor coverage on the three **IDE** surfaces
  assumes an IDE-spawned terminal inherits the project's `bin/` on PATH; that was never
  measured (Arpit chose to skip the probe, 2026-08-14). ADR-COVERAGE marks those cells `‡`.
  One command closes it: run `graphify query …` in a Kiro IDE terminal and see whether a
  receipt lands. **If it does not, kiro-IDE has no capture route at all** and this
  program's scope changes. Pair with GFX-COV-FIELD in one sitting.

- **GFX-COV-FIELD** — hands-only, Arpit's machine: `cage import --rescan-graphify`, then
  `cage query graphify-coverage`, then `cage insights graphify`. Expect near-zero (0 real
  receipts at the 2026-07-22 audit; 0 graphify commands in 1,132 real VS Code terminal runs
  probed 2026-08-07) — **and the two-day interceptor outage means any figure for
  2026-08-12 → 08-14 is a known undercount**, not a measurement of adoption.

- **UNREAD-FACTS** — SURFACE-CUT left **six recorded-but-unreadable facts**: capture still
  writes them and no view reads them. `route_key` reclaim (writer `savings.record`) ·
  `state/attest.jsonl` (every L1 hook — this is L1 benefit *(a)* with no consumer) ·
  `scope` (§3.6.2) · `project` (§3.7) · task `label`/`outcome` · `[tools] order`
  (`policy.tool_order` now has no consumer at all). Each is a candidate read surface, not
  a bug — decide per fact whether it earns a view or the write should stop.

- **STATE-RETENTION** — `.cage/state/` has no pruning path. `cleanup.py` is kept and
  fully tested (`importcmd` + `doctor` import it), but the only manual trigger was
  `cage data cleanup`, deleted by SURFACE-CUT. `maybe_run` still warns with the count and
  reclaimable size and now says plainly that no command prunes them.

- **CONTINUOUS-CAPTURE** — `cage import` is manual-only: `watch` and `proxy` are gone.
  Claude Code sweeps transcripts at ~30 days by default, so a missed import is permanent
  loss. Capture-on-read still fires on every surviving read. Whether cage ships guidance
  (a cron line it prints but never installs — ADR 0002 forbids a scheduler) is Arpit's.

- **TASK-GRAIN-SPINE** — **re-scoped 2026-08-14, no longer a view defect**: SURFACE-CUT
  deleted all three affected views (`compare`/`estimate`/`calibration`), so nothing
  currently mis-reports. What survives is the **capture-schema gap** underneath: a metric
  row carries no `task` field, so any future task-grained view over claude/copilot spend
  starts from zero. The `taskgroup` window fallback cannot help — it builds windows from
  task-carrying calls and there are none. Candidate fix, unchanged: derive the window
  from `tasks.jsonl` (which carries session + ts). Pinned previously in
  `tests/test_compare.py`'s `_MODEL` comment; that file was deleted, so this line is now
  the only record of the seam.

- **LEDGER-SHAPE** — **Arpit, 2026-08-14:** every usage producer owns one directory under
  `ledger/`. Four asks, spec'd as P1-P4 of
  [ledger-restructure.handoff.md](ledger-restructure.handoff.md): a **consumer ledger**
  (`ledger/consumer/`, dual-write — **reverses ADR 0006**, ratified the same day) · kiro
  **credits** folded into `ledger/kiro/` (copilot needs nothing — it has no credit rows) ·
  **`imports.jsonl` → `state/`** plus name-lifting for all three agents · **`provenance.jsonl` →
  `ledger/provenance/`, month-partitioned** (reverses `paths.py`'s explicit *"provenance is
  intentionally never partitioned (buffer)"*) · **graphify savings → `ledger/graphify/`**. Nothing is moved on disk — every old path stays written-no-more and
  read-forever. Carries five open decisions (handoff §10.1, 10.3-10.6); **10.5 (the `ledger/`
  namespace collision between agents, consumers and tools) blocks P4** and **10.3 (whether
  kiro-CLI gains a spine) changes user-visible output**.

- **METRICS-DUAL-WRITE-END** — **decided 2026-08-14: `calls` capture for the three agents
  stops. Freeze lifted early by Arpit** (it read *"do not touch before 2026-09-13"*, one full
  transcript-retention window of cross-check; that window is knowingly forfeited). **Picked up**
  — folded into the six-phase [ledger-restructure.handoff.md](ledger-restructure.handoff.md) +
  [.prompt.md](ledger-restructure.prompt.md) as **P5**, not yet executed. Scope is the three agents'
  **transcript→calls ingest legs only**: the `calls` kind survives, because `ledger.spend()`'s
  calls loop is still the sole basis for `record_call` consumers, retired `codex`, proxy rows
  and `[sources.<name>]` custom tools. Handoff §0 (a pre-flight `calls`-vs-metric snapshot to
  `regression/`) is the mitigation for the lifted freeze and gates every later step.
  Carries one open decision — **OPEN QUESTION 10.1**, whether `_PARSERS` survives as the
  `[sources.<name>] format` custom-source contract; blocks only its own deletion.

- **AUTHORSHIP-CODE-CATCHUP** — [ADR-AUTHORSHIP](../docs/adr/0009_authorship.md) is
  ratified (Arpit, 2026-08-14) and **three of its decisions are not built**. The record
  says so in its own status line and §1, so it is honest, not stale — but it stays that way
  only until this closes. Exactly three changes, each small and independent:
  **(a)** `authorcapture.COVERAGE_GAPS` still carries the corrected-away structural claim
  for copilot and kiro — replace with *"no parser yet"* naming the store, and keep
  **copilot · cloud** as the one genuinely structural entry.
  **(b)** `coverage_note()` names only the per-agent gaps and is silent on the ~30-day
  retention wall that bounds the one agent it does cover — add the clause.
  **(c)** the `declared` column in `commitview`: read the trailer out of the commit message
  **at render time**, print agent + model string, footer states the failure in cluster
  terms (never a coverage rate). **Write no provenance row and add no `method` rung** —
  the quarantine is structural on purpose, and persisting it is the signal it failed.
  ADR-AUTHORSHIP is updated in the same change as any of the three (its own update-rule).
  Doc half is DONE: the record exists, ADR-CLAUDE's false sentence is recorded as
  corrected, ADR-COVERAGE's matrix row is fixed and its veto marked FIRED, ownership moved
  in `docs/adr/README.md` and `tests/test_adr_ownership.py`.

- **AUTHORSHIP-PARSERS** — the optional half, and the reason the gap strings matter. Four
  parsers would move an entry out of `COVERAGE_GAPS` each, in this order by reach per unit
  of work: **copilot · CLI** (`events.jsonl` → `tool.execution_start.arguments`; the file is
  already open every sweep) → **kiro · IDE** (the largest *historical* prize — nothing
  deletes it; scan for JSON containing `"executionId"`, do not hardcode the hex dir names)
  → **kiro · CLI** (`data.sqlite3`, open read-only) → **copilot · VS Code** (`chatSessions`
  first — `chatEditingSessions` is richer but self-deletes on session stop, so it needs a
  capture cadence cage does not have; pairs with **CONTINUOUS-CAPTURE**). Each lands in one
  parser and the gap table, nothing else. **Not started, and not required by the ADR** —
  the record ratifies the order, not the work.

- **COPILOT-JETBRAINS-UNPROBED** — hands-only, Arpit's machine, one command. Since
  2026-05 the JetBrains Copilot plugin drives the local CLI, but the CLI's `events.jsonl`
  writer is gated on `getReverseCallHandler() === undefined` — an IDE driving it over RPC
  would send events to the host and write **no local file**. Run one Copilot agent edit
  from JetBrains, then check `~/.copilot/session-state/*/events.jsonl` exists;
  `workspace.yaml`'s `client_name` distinguishes the surfaces. Same shape as
  **GFX-IDE-PATH-UNPROBED** — pair them in one sitting.

- **PLAN-BACKTICK-IMBALANCE** — `docs/PLAN.md` carries an **odd** number of backticks
  outside fenced blocks (1859, unchanged at HEAD — pre-existing, not introduced by the
  archive sweep). This is the exact failure recorded in CLAUDE.md's doc-gate trap: an
  unbalanced backtick makes every code-span scan downstream read the file wrong, which is
  how `_doc_flags` was silently emptied and an assertion passed vacuously. Nothing fails
  today, which is the problem — it is a gate that has quietly stopped seeing. One-line
  detector, worth adding to the doc gates: strip fenced blocks, count backticks per file,
  fail on odd. **Found 2026-08-14 while verifying the archive sweep**; the sweep itself
  left every touched file even.

## Arpit decides

- **`CLAUDE.md` diff for SURFACE-CUT — proposed, not applied**:
  [surface-cut.claude-md-diff.md](archive/v0.50-surface-cut.claude-md-diff.md). **24 lines are false**,
  two of them already stale before this change (the ADR restructure moved
  `docs/shim-contract.md` and every numeric ADR path). Two are *rules* naming deleted
  commands: the WORKLOG `Cost:` line and the dogfood snapshot allowlist.
- **Where does the SURFACE-CUT decision record live?** Written to
  [surface-cut.decision.md](archive/v0.50-surface-cut.decision.md) beside its archived pair. The ADR set
  became four per-agent records the same day, and this is cross-cutting, so it fits
  neither the live shape nor the frozen archive.

- **TEST-COUNT** — README's `$0` section and CLAUDE.md's `just test` comment still say
  **1571**, stale after SURFACE-CUT deleted 12 test files and stripped ~30. Needs one
  `just test` on the dev machine; no agent can measure it from Cowork (macOS venv).
- **PLAN-4-REWRITE** — PLAN §4 still calls `insights attrib` "the attribution engine (the
  part that's actually novel)" for a deleted command. SURFACE-CUT's handoff says that
  section needs **rewriting, not annotating**.

- **COVERAGE-STRIKE-2** — [ADR-COVERAGE](../docs/adr/0008_coverage.md)'s *deliberately not
  taken* generated matrix set its own threshold at *"this record is found stale twice"*.
  It has now been found stale twice (2026-08-14, both by reading sessions), so the
  threshold is met — **but the remedy it points at would have caught neither strike.** Both
  failures were in the prose a generator flattens, and one was a wrong *mark* (⚠️ where
  nothing worked), which a generator derived from the same wrong belief reproduces
  faithfully. Two ways out, and it is a call, not a task: **(a)** extend
  `tests/test_formulas_coverage.py` to this record's two ✅/N/A tables — the mechanical half
  that *would* have caught STRIKE 1 — and leave the prose to review; or **(b)** accept that
  this record's failure mode is prose, stop counting strikes toward a generator that cannot
  address it, and say so in the record so the counter stops reading as a debt. Filed
  2026-08-14 (COVERAGE-LEGEND).

## How this file is maintained

Continuously. A new item is one line here, the moment it's known; detail goes inline
or into a handoff/prompt pair in `work/` root. A completed item is **deleted, not
ticked** — legal only once [IMPLEMENTATION.md](IMPLEMENTATION.md) records its outcome
and any evidence reaches [regression/](../work/regression/), with residual limits
carried forward as their own lines. **Its own markers are never evidence** — reconcile
against git. The header's checkable claims are gated by `tests/test_queue_honesty.py`.
Full law: [`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*.
