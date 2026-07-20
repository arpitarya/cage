# Handoff: capture architecture — capture-on-read, canonical ledger, visible capture

**One-liner:** Make capture correct without hooks — every read lazily sweeps the log registry
into one canonical ledger, push (graphify/fux/proxy) and pull converge on that same ledger, and
capture becomes *visible* instead of silent.

**Owner / executor:** Claude Code
**Status:** Ready to build — **Phase 1 only.** Phase 2 is a separate, later release (see below).
**Design of record:** [docs/capture-architecture.plan.md](capture-architecture.plan.md) — read
it first; this handoff packages it, the plan carries the reasoning.

**Stress-tested:** Three passes. Two are recorded in the plan (§9 council on the sink mechanism
+ hook deletion; §11 audit). The third is new to this handoff and **blocked the original
single-release shape**:

> **You cannot delete the old capture path in the same release that adds the new one.**
> If capture-on-read ships with a bug *and* the token hooks are already gone, capture stops
> **entirely and silently** — precisely the failure this design exists to prevent. Both paths
> are idempotent (`hooks.append_new` dedupes by id), so running them together costs nothing but
> a redundant sweep. There is no upside to simultaneous deletion and a catastrophic downside.

→ **Phased. Phase 1 is additive; hooks are not touched. Phase 2 deletes them later, gated on
evidence from Phase 1 in the field.**

**What survived the earlier debates (do not re-litigate):**
- **Trigger = capture-on-read**, not hooks, not a scheduler. Arpit's call; "eventual is fine."
- **Sink = route by identity, never relocate.** VERIFIED by test: a graphify receipt pushed from
  a repo subdirectory *is* seen by a repo-root read, because `_resolve_root` walks up for
  `.cage/`. The "graphify gap" is a phantom in the normal case. Rejected: shim-exported
  `CAGE_BASE` (can't reach graphify's separate process), blind global→project union
  (over-attributes — `project` is a colliding *basename*), push-to-global (mixes tenants).
- **Hook deletion is symmetric or not at all** — cage serves any single agent or any
  combination, so a Claude-only "proof-of-life" warmer is out. All four or none → none (Phase 2).
- **Scope of "hooks" is token-capture lifecycle ONLY.** The provenance subsystem
  (`PostToolUse` → `post-commit` → `prepare-commit-msg`) is a **trust tier**, not latency —
  deleting it downgrades every commit's authorship from `hooked` to `transcript`. It stays.
- **Confirmation prints only on user-invoked surfaces**, never a library/proxy/hook request
  path. This is what keeps visible capture from breaking the fail-open-silent metering law.

**Residual risk to watch:** capture-on-read couples a read to a write path. Mitigated by
§6's suppression requirement (every determinism/golden test runs with it **off**), but this is
the thing most likely to cause a subtle test-flake. If goldens start flapping, suspect this first.

---

## 1. Context & background

Capture today has two mechanisms that don't converge and four hook systems that mostly don't
fire (per-agent reality table in the plan §1). Arpit's report: "kiro, copilot and claude hooks
aren't working properly." Rather than fix four divergent client hook systems, the design demotes
hooks to an optional optimization and makes **reads** responsible for capture — so correctness
never depends on a hook firing.

## 2. Definition of done

### Phase 1 (this handoff)

**Capture-on-read**
- [ ] A shared `ensure_captured(root, pol)` runs an incremental sweep before a read returns.
- [ ] Wired into: `cage report`, `cage insights *`, `cage doctor`, and **the MCP read tools**.
- [ ] **Throttled** — a `constants` window with a policy `[capture]` preferred-fallback (the
      `DEFAULT_CONFIDENCE` pattern). Back-to-back reads don't re-sweep.
- [ ] **Fail-open** — a capture error never blocks or alters a read.
- [ ] **Suppressible** — `CAGE_CAPTURE=0` and a `--no-import` flag both disable it.
- [ ] Warm cache (no new rows) ⇒ **byte-identical output** to today.

**Canonical ledger + routing key**
- [ ] A single `canonical_ledger()` resolver that push and pull both call — no direct
      `resolve_root` in a push path.
- [ ] A stable **non-PII project routing key** (hash of the resolved ledger-root path) stamped
      on pushed receipts. **Not** the basename.
- [ ] A read-time reclaim backstop filtered by **exact key match only** — never a blind union.

**Observability (plan §12)**
- [ ] graphify/fux wrapper prints one **stderr** line when a receipt lands (counts only).
- [ ] capture-on-read prints `· captured N new …` above a read; **silent when zero new**.
- [ ] MCP read responses carry the same summary as a structured field.
- [ ] `CAGE_DEBUG` logs **ledger-resolution decisions** (which ledger + why), every sweep, and
      every routing-key reclaim.
- [ ] `cage doctor` capture timeline: per-source, per-**mode** (pull/push) last-seen + counts.
- [ ] `--why-ledger` prints the resolution decision on demand.
- [ ] `CAGE_QUIET=1` / `--quiet` suppresses confirmations.

**Both**
- [ ] **The full test suite passes** (§9 — this is a hard gate, enumerated).
- [ ] Docs updated (§9.5).

### Phase 2 (LATER — separate release, do not build now)
- [ ] Remove Stop / SessionStart / SessionEnd / agentStop entries from all four agents.
- [ ] Keep: provenance hooks, git hooks, MCP servers, the proxy.
- [ ] Task-close story decided (explicit `cage outcome`, or import-derived boundaries).
- [ ] Gated on: Phase 1 in the field showing capture-on-read is capturing everything the hooks
      were.

## 3. Scope

**In scope (Phase 1):** `importcmd` (the shared `ensure_captured` + throttle), the read entry
points in `clicmds`/`mcpserver`, `metering`/`graphifymeter` (routing key + confirmation),
`schema` (the routing-key field), `debuglog` call sites, `doctorcmd` (timeline), `constants`.

**Out of scope — do not build:**
- **Any hook deletion or hook file edit.** That is Phase 2. Touching wiring in Phase 1 defeats
  the whole point of phasing.
- An OS scheduler. The "cage installs no scheduler" invariant **holds** — capture-on-read is
  what makes keeping it painless.
- A blind global→project union, a `CAGE_BASE` shim export, or push-to-global (all rejected, §9
  of the plan — reasons recorded).
- Printing on a library/proxy/hook request path.
- Any derived-view change. Capture-side only: report/attrib/matrix/roi numbers must be
  byte-identical for the same ledger.
- A background process. `tail`/`watch` stay opt-in foreground.

## 4. Current state

Repo: `/Users/arpitarya/my_programs/cage`. Read first:
- **[docs/capture-architecture.plan.md](capture-architecture.plan.md)** — the design of record.
- `cage/importcmd.py:108-140` (`_scan`), `:73-105` (cursors, `last_import`), `:372`
  (`_last_import` write — the throttle precedent), `:35` (the import lock).
- `cage/clicmds.py:55,67` — where reads are assembled and state is passed in.
- `cage/metering.py:42-70` — `record_call` / `record_receipt` / `_resolve_root` (the push path).
- `cage/graphifymeter.py:105-140` — the before/after receipt-id diff that already *knows* when a
  saving landed (the confirmation hook point).
- `cage/paths.py:104-165` — `find_project_root`, `global_base`, `resolve_root`,
  `active_ledger_source`.
- `cage/proxy.py:56-61` — the third capture mode (push via `record_call`).
- `cage/schema.py:27,43-73` — `make_call`/`make_receipt`, `scope`/`project` fields + PII guard.
- `cage/debuglog.py`, `cage/display.py:49-81` (`Footer`), `cage/doctorcmd.py`.

## 5. Technical approach (decided)

Per the plan §2–§3 and §12. The load-bearing points:

- **`ensure_captured` is one function**, called by every read entry point; it reuses the
  existing incremental sweep and cursors (a warm no-op is a `stat` per source file). It writes
  the **ledger** (append-only capture), never a derived artifact — so "same ledger + same policy
  ⇒ same tables" still holds.
- **Throttle via the existing `_last_import` cursor timestamp** — no new state file.
- **Routing key is additive and optional** — absent = the legacy contract, exactly like `scope`
  and `project`. It is **never part of any id**.
- **Confirmation is user-invoked-surface-only** (plan §12.1). The graphify line goes to
  **stderr** so it never corrupts graphify's parseable stdout.

## 6. Non-negotiables / constraints

- **$0 / stdlib only.** `dependencies = []`.
- **Fail-open on every write/capture path**; every new swallow site logs under `CAGE_DEBUG`
  (`tests/test_debug_coverage.py` enforces this — it is tested, not aspirational).
- **Determinism:** derived numbers stay a pure function of the ledger. **Every determinism and
  golden test must run with capture-on-read OFF against a fixed ledger.** Hard requirement.
- **PII:** counts / ids / paths only. Never a prompt body in a confirmation or a trace line.
  The routing key is a **hash**, not a path.
- **Four agents, always** — and any single agent or combination. No asymmetric per-agent
  behavior anywhere in this change.
- **`method` is sacred** — nothing here may make a projection read as `measured`.
- **CSV never gates** — no confirmation text in any CSV output.
- **Do not touch:** any hook file (Phase 2); the provenance/git-hook subsystem; `policysync`;
  the `NEVER` cleanup list; `pathprobe._why()` strings.

## 7. Dependencies & prerequisites

None external. Independent of the staged v0.29 `[sources]` work (composes cleanly) and of the
`capture-health` pair — but see §8: sequence capture-health **after** this, since capture-on-read
makes its `_health` data fresher.

## 8. Edge cases & risks

- **Concurrent reads** both triggering a sweep → the existing `_import_lock` (`importcmd.py:35`)
  must cover `ensure_captured`. Fail-open if the lock can't be taken (proceed unlocked, as today).
- **First read after a long gap** does the heavy sweep and is slow. Acceptable and honest — show
  the "captured N" line; never fake instantaneous.
- **A read inside a hook** (Phase 2 lands later, so hooks still fire) → double sweep, harmless
  by id-dedupe, but the throttle should absorb it.
- **`cage doctor` must still diagnose a broken capture** — doctor triggering a sweep could mask
  the very problem being diagnosed. Doctor's timeline must report the state **before** its own
  sweep, or clearly label it.
- **MCP read tools** run in an agent's request path — but they are *user/agent-invoked commands*,
  not a library meter, so confirmation is allowed as a structured field (never stray stdout that
  would corrupt the protocol). **Never print to stdout in the MCP server.**
- **Routing key on a global-ledger push** (no project) must be stable and not collide with a
  project key.

## 9. Testing & validation — THE FULL SUITE IS A HARD GATE

Arpit's explicit requirement: **the full testing suite must be executed**, not a subset. All of
the following must pass before this is reported done:

```bash
just test                          # python -m pytest -q  (791 passing — refresh the count if it moves)
python -m tools.dummyrepo          # scenario runner S1–S17 (real-CLI capture, PII, determinism, fleet)
python -m tools.docgen --check     # spec ← goldens · formulas/policy ← explain registry
python -m tools.skillgen --check   # rendered skill assets, no hand-edit drift
just demo                          # seeds §4.4 and must still reproduce the plan's tables
just lint                          # ruff if available
```

CI runs this across **3 OS × 3 Python versions** (`ubuntu/macos/windows` ×
`3.11/3.12/3.13`) — do not assume a green local run is sufficient; the OS-dependent paths in
this change (ledger resolution, path hashing) are exactly the class that breaks on Windows.

**Suites most likely to break — check them explicitly:**
- `tests/test_universal_capture.py` — the pull-capture contract this change extends.
- `tests/test_debug_coverage.py` — every new swallow site needs a `CAGE_DEBUG` log.
- `tests/test_output_spec.py` + `tests/fixtures/goldens/` — a new footer/confirmation line
  changes rendered output ⇒ **re-bless** (`CAGE_BLESS_GOLDENS=1 pytest tests/test_output_spec.py`)
  then `python -m tools.docgen --target spec`. Never hand-edit the spec blocks.
- `tests/test_capture_health.py` — interacts with the fresher `_health` data.
- `tests/test_portable_wiring.py`, `tests/test_launcher_mode.py` — must stay green; Phase 1
  touches no wiring, so a failure here means you went out of scope.
- `tools/dummyrepo` **S1** asserts all four agents wire and planted CLI logs import to exact
  rows — the canonical end-to-end capture proof.

**New tests required:**
- `tests/test_capture_on_read.py` — sweep runs before a read · throttle suppresses a second
  sweep · `CAGE_CAPTURE=0` and `--no-import` disable it · capture error ⇒ read still succeeds
  (fail-open) · **warm cache ⇒ byte-identical output to today** · concurrent reads don't
  double-append.
- `tests/test_canonical_ledger.py` — **the verify-first test, made permanent**: push a receipt
  from a repo subdirectory, assert a repo-root read sees it. Plus: routing key is stable,
  non-PII, absent-by-default (legacy byte-identity), and never part of an id. Reclaim matches
  **only** on exact key.
- `tests/test_capture_observability.py` — graphify confirmation goes to **stderr** not stdout ·
  zero-new-rows ⇒ silent · `CAGE_QUIET=1` suppresses · no content in any confirmation or trace ·
  **no confirmation text in any CSV** · MCP server never writes stray stdout.
- **Determinism guard:** derived views byte-identical with capture-on-read on (warm) vs off.

**Manual:** run `graphify query …` in a repo and confirm the stderr line appears in the agent's
tool result; `cage report` twice and confirm the second is silent (throttle + zero-new).

## 9.5 Documentation impact

- [x] **`docs/capture-architecture.plan.md`** — required: record the Phase 1/2 split decision.
- [x] **`docs/cli-output-spec.md`** — required and **generated**. Re-bless goldens, then
      `tools/docgen --target spec`.
- [x] **`docs/debugging-capture.md`** — required. The new confirmations, `--why-ledger`, the
      doctor timeline, and the `CAGE_DEBUG` ledger-resolution trace.
- [x] **`cage query capture`** + a new `capture-on-read` concept entry (`explain_data.py`) —
      required; docgen-gated.
- [x] **`CHANGELOG.md` + README "What's new"** — required, user-facing. Bump `__version__`;
      refresh the "N tests passing" count in README **and** CLAUDE.md.
- [x] **`CLAUDE.md`** — required, **PROPOSE ONLY**. The Meter/capture bullets change materially
      (capture-on-read becomes the primary path). Surface the diff for review; **never silently
      rewrite the steering file.**
- [x] **`docs/README.md` Active work** — add this pair; archive on the shipping release and link
      from the CHANGELOG ("Built from: …").
- [ ] **ADR** — N/A; the plan + this handoff are the decision record.

## 9.6 Fix vs REBUILD — what must not be retrofitted

Codebase audit against the new design. The rule: **anything whose shape encodes "hooks are the
capture path" must be rebuilt, not extended.** Bolting capture-on-read onto these would carry a
false model forward.

### REBUILD — do not retrofit

- **`hooks.append_new` → move to `ledger.py` (layering inversion).** `importcmd.py:245` calls it,
  and it is documented repo-wide as "the correctness backstop." But it lives in `hooks.py`, which
  is **Claude-specific** (`_AGENT = "claude"`). So the universal import path depends on one
  agent's hook module. Phase 2 cannot cleanly delete token hooks while `importcmd` imports from
  them. **Move the primitive to `ledger.py` (or `importcmd`) in Phase 1**, before anything else
  is built on it. Pure move + re-export shim; no behavior change.
- **`agents.backfill_status()` / `realtime_status()` + all 8 wire implementations → obsolete
  concepts.** Their docstrings are literally *"is a SessionStart-backfill capture hook wired?"*
  and *"is a real-time per-turn hook wired?"* Under the new design, backfill **is**
  capture-on-read and real-time **is** capture-on-read — these functions answer a question that
  no longer describes how cage captures. **The §12.4 doctor timeline must be built fresh from
  per-source/per-mode capture facts — NOT layered over these.** Retrofitting the timeline onto
  hook-wiring status would report "real-time: wired" for a path that no longer carries
  correctness. Deprecate them in Phase 1 (stop feeding new surfaces), delete in Phase 2.
- **`hooks.py` → split by subsystem before Phase 2 can touch it.** One Claude-only module
  currently mixes **four** concerns: token capture (`stop`, `session_end`'s `_capture_calls`),
  provenance (`post_tool_use`, `post_commit`, `prepare_commit_msg`,
  `_record_transcript_provenance`), task snapshots (`_snapshot_tasks`), and the cleanup
  chokepoint (below). Phase 2 deletes exactly one of those four. Split first, delete second —
  never a surgical edit inside the tangle.
- **`doctorcmd.py:105` "capture health: never imported — run `cage import`" → semantic rewrite,
  not a tweak.** Under capture-on-read, doctor sweeps *before* it renders, so this branch as
  written becomes **unreachable** — it can only fire when capture is disabled or the sweep
  failed. Its meaning changes from *"you haven't imported yet"* to *"capture is off or errored."*
  Rewrite the message accordingly. Leaving the old string is a lie the codebase tells forever.
  (This is the exact fallback chosen in the v0.30 capture-health work — it was correct under the
  old model and is wrong under this one.)

### ⚠️ NEW RISK — missed by the §11 audit: the cleanup chokepoint

`hooks.session_end` ends with `cleanup.maybe_run(root, pol)`, commented:

> *"Claude's real-time hooks bypass `importcmd.run`, so session close is this surface's cleanup
> chokepoint."*

So **state cleanup (plan §3.6.4) is chokepointed on the SessionEnd hook for Claude users.**
Phase 2 deleting SessionEnd would silently stop state pruning — a fifth subsystem tangled into
"the hooks," and it was not in §11.

Capture-on-read *fixes* this naturally (the sweep is `importcmd.run`, which already piggybacks
cleanup) — but it must be **explicit and tested**, not assumed. **Phase 2 DoD gains: prove
`cleanup.maybe_run` still fires for a Claude-only user after SessionEnd is removed.**

### FIX / EXTEND — structurally sound, safe to build on

- **`_scan` / `_ingest` / cursors / `_import_lock`** — the sweep core is agent-agnostic and
  already computes what capture-on-read and the `health` record need. Reuse as-is.
- **`importcmd.capture_health` + the triple gate (v0.30)** — semantics hold; capture-on-read
  simply makes its data fresher. No rebuild. Verify the throttle can't make `_health` look fresh
  while being stale.
- **`report.py` health rendering + `clicmds.py:56` threading** — already a pure function of
  passed-in state. This is the exact seam `ensure_captured` plugs into. Extend, don't touch.
- **`metering.record_call/record_receipt`** — add the routing key; no restructure needed.
- **`graphifymeter`'s before/after receipt-id diff** — already knows when a saving landed; it is
  the natural confirmation point. Extend.
- **`paths.resolve_root` / `find_project_root`** — verified correct (the subdir→root test
  passes). `canonical_ledger()` wraps it; it does not replace it.

### Sequencing consequence

Phase 1 gains two **prerequisite** refactors that must land *before* the new features, or the
new features get built on the old model:

1. Move `hooks.append_new` → `ledger.py`.
2. Stop feeding `backfill_status`/`realtime_status` into any new surface; build the doctor
   timeline from capture facts.

## 9.7 Phase 2 change-map (verified against the code — do not re-derive)

Produced by reading the full Phase 2 surface. Preserved here so the branch can be written later
against final decisions without redoing the analysis.

**Delete:** `hooks.stop` / `session_start` / `session_end` / `_capture_calls` / `_snapshot_tasks`
· `cli.py` parsers `hook-stop` / `hook-session-start` / `hook-session-end` ·
`agents.backfill_status` / `realtime_status` + all 8 wire-module implementations · the
token-hook writes in all four wire modules.

**Keep — the five entanglements to protect:**
1. `PostToolUse` — shares one config block with Stop/SessionEnd in `claudewire._simple()`.
2. The git provenance hooks — installed only under `if "claude" in out`.
3. The **cleanup chokepoint** — must be *proven* to survive via capture-on-read's
   `importcmd.run → cleanup.maybe_run`.
4. `codexwire.status()` — calls the to-be-deleted `backfill_status`.
5. `hooks.py` reduced to a **provenance-only** module.

**Migration:** each wire module's `install()` must *strip* previously-written token entries on
re-run (idempotent), not merely stop adding them.

**Tests:** rework `test_agents` / `test_portable_wiring` / `test_launcher_mode` + dummyrepo
S1/S2; add the DoD-required "cleanup still fires for a Claude-only user" and "provenance
survives" tests.

## 10. Decisions (resolved — do not re-litigate)

- **Doctor ordering → `cage doctor` NEVER sweeps.** Reverses this handoff's earlier §10
  recommendation. Precedent: `pathprobe.probe()` is documented *"read-only… never writes
  (cursors are read, not updated)"* — doctor's diagnostic layer is already architecturally
  read-only. A diagnostic that mutates what it diagnoses is a category error; sweeping would
  mask broken capture and make `cage doctor` produce different output on consecutive runs.
  Users are covered because report/insights/MCP all capture-on-read. **Phase 1 already
  complies** (`cmd_doctor` uses `root()`, not the capture helper) — verified, no change needed.
- **Test suppression → a dedicated internal gate, conftest OFF, new tests opt in.**
  Isolating homes is insufficient: the sweep would still run, still bump `_last_import`, which
  feeds the report footer's staleness advice (`report.py:381 → _last_import_line`) — goldens
  containing that line would drift. Reusing `CAGE_CAPTURE=0` in conftest would disable capture
  for existing import tests across the suite. The gate is **internal/test-only** — the
  user-facing story stays two switches (`CAGE_CAPTURE`, `--no-import`); `cage query capture`
  must not advertise it.
- **Routing key in CSV → row only, NOT in `RECEIPT_FIELDS`.** `scope`/`project` earn columns
  because they're analytically useful (you can group by them); a routing **hash** has none in a
  spreadsheet — it's reclaim plumbing. Adding a CSV column later is trivial; removing one breaks
  index-reading consumers. Expose it via `--why-ledger` / the debug trace if ever needed.
- **Task-close (Phase 2) → `outcome-only`.** The ledger is **append-only**: synthetic task rows,
  once written, are permanent — a guess cannot be un-written. Task rows feed the closed-task
  join → `compare`/`estimate`/`calibration`/`verdict`, all of which make **dollar claims**;
  a derived boundary would propagate a semantic guess into a cost figure. This does *not*
  inherit the `gap_ms` precedent: turn-gap attention measures something real (elapsed time),
  whereas a task boundary is a categorical assertion. `MIN_COMPARE_N`/`MIN_ESTIMATE_N` blocking
  to `INSUFFICIENT DATA` is the honest failure mode and is already built.
  **Reversible in the safe direction:** if tasks prove too sparse in the field, add
  import-derived later as an explicitly-tagged `estimated` layer that *loses to attestation*
  (the human-axis precedent). Starting derived and removing it later is the hard direction.
- **Transcript provenance fallback (Phase 2) → PRESERVE, re-homed onto the import path.**
  `_record_transcript_provenance` currently fires only from `session_end()`, which **does not
  fire under the VS Code extension** — so for VS Code users the fallback is already dead *and*
  `PostToolUse` doesn't fire either, meaning those sessions get no provenance at all. Re-homing
  it onto the import path is therefore a **strict improvement**, and it fixes the original
  complaint (broken hooks under VS Code). It is also the only option consistent with the design
  thesis — no capture path may depend on a hook firing — and with §11, which kept provenance
  precisely because it is a **trust tier**, not latency. Constraints: method stays `transcript`
  (trust 1, **never** promoted to `hooked`); dedupe by row id (`union_by_id`); fail-open and
  `CAGE_DEBUG`-logged.

**Still genuinely open:**

- **OPEN — the Phase 2 field gate (the only thing blocking the branch).** Phase 2 deletes the
  safety net; the whole reason for phasing was to not remove it until Phase 1 has proven itself
  in real use. Phase 1 is hours old. **Do not write the Phase 2 branch yet** — a ready-to-merge
  deletion branch creates pressure to merge before the evidence exists, which re-couples exactly
  what phasing decoupled. §9.7's change-map is the de-risking artifact; the code should be
  written later, against these decisions. **Gate:** Phase 1 running in the field long enough to
  show capture-on-read captures everything the hooks did (compare a hooks-on machine's ledger
  against a hooks-off one over the same work).
- **OPEN:** exact throttle default. Start conservative (~60s) and make it policy-tunable.
