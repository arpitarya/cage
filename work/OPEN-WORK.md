# OPEN-WORK — the index of pending work

## In flight

- **SURFACE-CUT is BUILT (2026-08-14), suite green except the shim** — 14 modules, 15
  handlers, 12 test files and 16 goldens deleted; MCP cut 6 tools → 2. Outcome recorded
  in [IMPLEMENTATION.md](IMPLEMENTATION.md); decision record in
  [surface-cut.decision.md](archive/v0.50-surface-cut.decision.md). **15 tests remain red, all shim**
  (see SHIM-DEAD-VERB below) — that was Arpit's explicit call, not an oversight.

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

- **SHIM-DEAD-VERB** — `bin/graphify` + `bin/graphify.cmd` probe `cage data graphify`,
  deleted by SURFACE-CUT. **15 tests red** (`test_pathshim` ×8, `test_win_graphify_shim`
  ×5, `test_wiringscan` ×1, `test_gf_launcher_arm2` ×1). No user breakage: contract B5
  gates metering behind a capability probe and B6 requires passthrough, so an installed
  shim fails the probe and `exec`s the real binary unmetered. Graphify savings still land
  via the transcript/store routes at `cage import`. Arpit chose 2026-08-14 to leave the
  subsystem untouched this build; closing it means either removing the interceptor
  (9 modules + both twins + ADR-GRAPHIFY §2) or giving it a live verb to probe.

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

## How this file is maintained

Continuously. A new item is one line here, the moment it's known; detail goes inline
or into a handoff/prompt pair in `work/` root. A completed item is **deleted, not
ticked** — legal only once [IMPLEMENTATION.md](IMPLEMENTATION.md) records its outcome
and any evidence reaches [regression/](../work/regression/), with residual limits
carried forward as their own lines. **Its own markers are never evidence** — reconcile
against git. The header's checkable claims are gated by `tests/test_queue_honesty.py`.
Full law: [`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*.
