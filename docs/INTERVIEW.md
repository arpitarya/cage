# INTERVIEW — the exit interview

**Notes from the outgoing maintainer-model to every future one.** Written the way
a departing engineer briefs their replacement: not a status page, but *what I
learned, what I'd warn you about, what I'd do next and why*. **Every agent
maintaining cage reads this after CLAUDE.md.**

**Maintained continuously — any session can be the last one before a model
switch,** so this must always read as if the handover were happening right now.
Update it in the same session whenever direction, strategy, standing constraints,
or the state of play change; add yourself to the maintainer line with the one
lesson you'd want inherited.

Four standing sections: **state of play** · **in-flight + next step** · **standing
constraints** · **lessons / scar tissue**.

It is **context, never spec.** Where it disagrees with CLAUDE.md or
[PLAN.md](PLAN.md), those win. Distinct from [WORKLOG.md](WORKLOG.md) (the
granular per-exchange trail) and [IMPLEMENTATION.md](IMPLEMENTATION.md) (what is
built, milestone by milestone) — this is the strategic, cross-session record.

Entry-point tracker: ALL-CAPS, no frontmatter.

---

## State of play (2026-08-02 — pick up here on a model switch)

- **The agent-surface ladder is BUILT, all four phases, in one session.** L0 floor
  proof · L2 MCP · L1 hooks+steering · L3 skills. **1024/0 ⇒ 1125/0**, uncommitted in
  tree as **v0.41.0** (v0.40's ADOPT is also unreleased in tree; `__version__` is still
  `0.39.0`). The proposal and the handoff/prompt pair are archived; `docs/` root carries
  no agent-surface pair. Read `CLAUDE.md`'s three new architecture bullets (the ladder ·
  L1-is-not-for-capture · steering/skills) before touching any of it.
- **The one thing to internalise about this work:** *every layer above L0 is opt-in,
  two-way, and provably free.* `tests/test_floor.py` installs **all** of them over a
  fixed ledger and asserts every derived number byte-identical, then strips them and
  asserts again, per agent. **If a future layer needs a number to move, the layer is
  wrong.** Add it to `_WIRING_ARTIFACTS`; never relax an assertion there.
- **In flight / next:** two field-verification items only — **L1-FIELD** (hook shapes
  never run on a real Claude Code / Copilot / Kiro) and **KIRO-MCP-FIELD** (the
  committed path-free `python3 -m cage mcp` never started on a real Kiro). Both need a
  machine, not code. Then **NET-1**, still the product's open question.
- **CHATS-AUTHOR: BUILT 2026-08-03** (v0.46.0, unreleased — see *In flight* below).
  The `agent%` authorship column on `cage insights chats`, joining the v2 provenance
  counts by `(agent, session)`. Pair + proposal archived:
  [handoff](archive/v0.46-chats-author.handoff.md) ·
  [prompt](archive/v0.46-chats-author.prompt.md) ·
  [proposal](archive/v0.46-chats-author.proposal.md); living spec is FORMULAS
  §2.13/§2.14. **Its Phase-0 REV-TS gate did its job** — it STOPped an earlier session
  cold with no work done, REV-TS was then built and shipped, and the re-run verified the
  gate independently rather than trusting the prompt's own status line. That sequencing
  is the model to copy, not an obstacle that was overcome. The limit the handoff's
  Stress-tested line named (same-file double-count across sessions) is **shipped as
  stated, not fixed**: per chat there is no diff to clamp against, so the commit view
  stays the arbiter for any single sha.
- **Lessons from this session, in order of how much they would cost to relearn:**
  1. **A committed file can carry ONE spelling.** The handoff said write `python3` on
     POSIX and `py -3` on Windows for Kiro's MCP — both *committed*, which would churn
     the diff on every `cage setup` in a mixed-OS team. Named the Windows gap instead of
     forking the file. When "portable" and "correct on every OS" conflict in a committed
     artifact, **name the limit**; do not fork.
  2. **Closing a task is not claiming it succeeded.** `tasks.jsonl`'s `outcome` and
     `.cage/outcomes.json` (ok|redo) are different stores on different axes — which is
     what let auto-close write `outcome="auto"` and stay invisible to `cage task
     quality`. Had they been one field, the hook would have had to lie.
  3. **Do not invent a host's event name.** Copilot has no pre-tool hook here because
     cage has no verified event name for one. An invented name fails *silently* — the
     exact class that cost nine days. Two-of-three **named** beats three-of-three
     guessed, and `agents.HOOK_GAPS` is where the naming lives.
  4. **Test a refusal by equality with the CLI's own output, not by substring.** A
     wrapper that printed `INSUFFICIENT DATA` and dropped the note beneath it passes a
     substring test. That is the whole failure mode L2 exists to prevent.
  5. **A mechanical rule will find a real weakness if you let it.** `steering.lint`
     failed the honesty-reviewer skill for naming no cage command. That was correct — a
     review skill that never says how to *check* is weaker. Fix the document, not the
     rule.
- **Stale-doc warning inherited, not created:** `docs/WORKLOG.md`, `docs/PLAN.md` and
  `docs/INTERVIEW.md` still link several pre-archive paths (`graphify-capture.plan.md`,
  `cage-lab-plan.md`, …) that earlier archive sweeps did not re-point. Harmless to read
  around, but it is the doc-deletion rule unpaid; sweep it on contact.

## State of play (2026-07-25, updated same day — historical)

- **cage is v0.36.0, entirely UNCOMMITTED by Arpit's explicit directive** ("do not
  commit anything yet, we will build few more things"). The working tree carries:
  the finished hookless rebuild (pull-only capture, MCP-only wiring, hook verbs →
  `verbmap.REMOVED` directions), the import-ledger plan Phases 1–4 (`surface`/
  `cache_write_in`/`premium`/`import_id` fields, loud import rollup,
  `savings/<tool>/savings-YYYY-MM.jsonl` tree, `imports.jsonl` manifest,
  gated-disabled `taskcorr`), and the names+migration revisions (session names
  always captured with per-session manifest rows + `session_uid`;
  `cage data migrate-savings` with the id-deduped `receipts()` union — precision
  bar NOT WRONG, NOT DUPLICATED). Suite last green at **817 tests**. Do not
  commit, tag, or release until Arpit says so.
- **In flight / immediate next:** execute
  [cage-lab-setup.prompt.md](cage-lab-setup.prompt.md) (**Opus**, both sibling
  checkouts) — create `../cage-lab` fresh per [cage-lab-plan.md](cage-lab-plan.md)
  v3 + [PLAN.md](PLAN.md) §11: the M/G correctness matrix, three-way auto-verify,
  the **eyeball surface** (source + ledger + derivation with line refs, side by
  side — Arpit verifies manually), his playground, then publish the baseline into
  [regression/](regression/). Commits allowed in cage-lab only.
- **The working model (how work actually flows):** Arpit runs strategy/spec in
  **Cowork chat**; execution happens in **Claude Code** driven by handoff+prompt
  pairs under `docs/` (every prompt declares its model tier — Opus for entangled
  deletions/substrate/money-semantics, per the CLAUDE.md rubric). The docs are the
  interface between the two surfaces; decisions land in the plan's §7 decisions
  log and the pair, then execution follows. Respect that pipeline: spec first,
  never silent scope changes in execution.
- **Standing Arpit directives (active):** no commits in cage · session names
  always captured (manifest-only PII widening, recorded deliberately) · savings
  consolidate into the per-source tree with exact numbers · `taskcorr` stays
  disabled until validated on real data (cage-lab L5 is the gate) · savings axis
  extends per-source next (graphify → human → other tools).
- **Docs discipline is now explicit and load-bearing:** IMPLEMENTATION.md at every
  milestone; WORKLOG.md covers Cowork/chat sessions too, not just executions;
  this file is maintained **continuously** so a model switch starts warm. The doc
  sweep debt (dangling links) was largely cleaned the same day; remaining gaps are
  known debt, not breakage.

## In flight + the single next step

**Update 2026-08-03 (latest) — CHATS-AUTHOR is BUILT and green (1462/0). The single
next step is the v0.46.0 release; the agent lane's next build is tier 2's decisions.**

- **`cage insights chats` now carries `agent%`** — per chat, the share of evidenced
  landed lines that matched the agent's own proposals. It closed the last item the
  REV-TS/ID-ENTROPY cleanup had unblocked. Unreleased in tree as **v0.46.0**;
  `__version__` deliberately still `0.45.0`.
- **The one thing to internalise:** this column's whole value is that **`—` is never
  0%**. Three refusal shapes each carry their reason, and a *measured* `0%` still
  prints `0%` — which is exactly why the dash can never be spent on absence of
  evidence. The same discipline governs its CSV: a refused chat's authorship cells are
  **empty**, because `0,0` would put the claim the dash refuses to make into data.
  If a future change makes a refusal render as a number, it has broken the feature,
  not improved it.
- **The substrate gained one deliberate irregularity — know why before you "fix" it.**
  `residual_lines` is the only line-match count written at `0`
  (`schema.PROVENANCE_ZERO_BEARING_COUNTS`); the other five are omitted at 0. Presence
  of the key is the **version gate**, because provenance rows are frozen by the
  idempotency key and can never be backfilled. Normalising it to the omit-at-0 loop
  would silently turn *everything matched the agent* into *no data*.
- **A held CLAUDE.md edit became FIVE, not four.** CHATS-AUTHOR's item F is the one
  with teeth: the chats bullet currently states the money-independence law amendment as
  **one** scoped carve-out, and there are now **two** (`imports.jsonl` for a label,
  `provenance.jsonl` for counts). Until F lands, CLAUDE.md understates a law's
  cardinality — an agent reading it would treat the second carve-out as a violation.
- **What I'd warn the next model about, from this build:** two tests read the chats CSV
  by **column index**, so adding columns broke them as a *false failure about credits*.
  I re-pointed them to read by header. Assume more positional reads exist elsewhere;
  a broken assertion that names the wrong subsystem costs more than one that fails
  honestly.

**Update 2026-08-02 — the queue has been re-prioritised and filed as a
proposal; the single next step is REV-TS.** *(Superseded: REV-TS shipped in v0.45.0
and CHATS-AUTHOR, its dependent, shipped 2026-08-03 — kept for the reasoning below,
which still binds.)*

- **OPEN-WORK was cut 469 → 243 lines on 2026-08-02** by removing fifteen blocks of
  *completed* work (they belong in IMPLEMENTATION.md, and every one was verified to be
  there first — README-FIX's record is CHANGELOG v0.37.2, and it had zero IMPLEMENTATION
  hits, so a blind delete would have lost it). **The lesson for whoever does this next:
  the risk is not the deletion, it is what is buried in the prose.** Two live things were
  only in those paragraphs — KIRO-CLI-SCOPE (a carried-forward item that was never a row)
  and ADOPT-COV's trigger + guard rail — and both would have died silently. Read every
  block for constraints before cutting it; what still binds now lives in **Standing
  constraints**.
- **The four held CLAUDE.md edits live in `proposals/` now, and two are traps.** hr1 §3
  and copilot-credits §5 carry test counts (1354, 1391) that are *behind* the file they
  patch (1401, suite 1416) — applying either verbatim regresses CLAUDE.md. Warnings are
  on the rows and in both READMEs. General form: **a held steering-file patch decays
  against the file it targets**; re-verify before applying, never trust its own age.
- **[OPEN-WORK.md](OPEN-WORK.md) itself now carries the order** — a tiered Pending table
  plus a §Implementation section. It was first written as a separate proposal and Arpit
  rejected the extra document: *the plan of record is the one file*. Do not re-file a
  sequencing doc alongside it.
- **The argument a successor should carry even if the order is re-cut:** the queue has
  **two resources**, not one. NET-1 and the three field-verifications cost *Arpit's
  hands*; every fix costs *an agent session*. Sequencing them against each other is a
  category error — they run concurrently. Inside the agent lane, rank by **accruing**
  damage: REV-TS and ID-ENTROPY get permanently worse with elapsed time (`originrecord`
  freezes rows by idempotency key; an id collision silently drops a row and widening
  later never heals ids already written). Every other wrong number in the queue is
  static and costs nothing to have waited on.
- **REV-TS is the next step and this is observed, not argued.** The packaged
  CHATS-AUTHOR pair was executed and **STOPPED at its Phase-0 gate with no work done**
  — it is already burning sessions. Package REV-TS as its own handoff/prompt pair, land
  the `+05:30` + same-second goldenseed fixtures, then re-run the CHATS-AUTHOR prompt.
- **ID-ENTROPY is one line and is NET-1's only gate** — if Arpit wants the evidence run
  moving this week, land it first and let REV-TS follow.

- **2026-08-02 (Cowork): HR1 is build-ready.** The agent-vs-human v2 proposal was
  accepted-amended (no USD; guarded `~` human-hours, attestation wins; line-match
  authorship where **human = residual**); live pair: `agent-vs-human-v2.handoff.md` +
  `.prompt.md`, slotted after the agent-surface track. Two facts a successor must
  carry: provenance transcript capture is currently **orphaned** (zero callers — P1
  re-wires it), and `latency_ms` exists only on lib-metered calls. The v0.36 legacy
  guards, verbmap tombstones, and provenance `origin="human"` enum are deliberate —
  do not "clean them up".

**Update 2026-08-01 (latest) — WIN-GF + CI-GF are BUILT (v0.38.0, uncommitted). The
single next step: push and read the Windows `graphify` CI job.**

- **graphify is now metered on Windows.** The interceptor was one extensionless bash
  script; Windows resolves a bare name only through `PATHEXT`, which has no extensionless
  entry, so cage's shim could never be *found* there. It now ships as a **twin pair** —
  `graphify` + `graphify.cmd` — against one written contract,
  [shim-contract.md](shim-contract.md).
- **The one thing I could not do is the one thing that matters most: run it on Windows.**
  10 behaviour tests and the whole CI `present` leg have never executed. Everything on
  this machine is green (979/0, dummyrepo S1–S18, `tools.cigraphify` 7/7 on macOS), and
  the POSIX interception path is proven end to end — real bare `graphify query` → shim →
  cage → one savings row. **Do not describe Windows as validated.** It is CI-asserted.
  Read that job before believing anything about it (OPEN-WORK **WIN-CI**).
- **If you touch a twin, you touch three things.** The marker set has three copies by
  necessity — sh `grep -E`, cmd `findstr /C:`, `pathshim._INTERCEPTOR` — and drift there
  silently disables liveness detection *and* re-enables the stacked-shim recursion that
  already cost this project nine days. The contract doc exists to make that unavoidable;
  update it in the same change.
- **The contract is the reusable artifact, not the twin.** TOOL-SDK wants a paved road
  for the next tool: what it should template is the *contract*, not the source. Batch and
  sh share no syntax subset, which is why the twins are hand-paired (`runshim.py` made
  the same call).
- **The residual I deliberately did not fix:** under `--python-launcher` there is no
  `cage` on PATH, so **neither** twin meters — it degrades to correct unmetered
  passthrough. Fixing the cmd side alone would have been exactly the drift the contract
  exists to prevent. Filed as **GF-LAUNCHER**; it needs a decision, not a patch.

**Update 2026-08-01 — gross vs net savings (K+NET) is BUILT. Read this before
you touch any savings number.**

- **`saved` was never what it read as.** It is a per-query counterfactual — avoided read
  cost — and it excludes the cost of *using* the tool. Because graphify honestly declares
  `tool_cost_usd = 0`, `verdict` computed `net = gross − 0` and printed **SAVING** on the
  very sessions leg D measured costing ~31% more. Nothing was miscomputed; the *label*
  was narrower than it read. That is the exact failure mode cage exists to catch in other
  tools, pointed at cage's own headline — treat it as the reference example.
- **The word `gross` now lives in ONE place** (`netsaved.GROSS_NOTE`) and is printed by
  every view. If you add a savings surface, print that constant; do not re-word it. A
  view that says "saved" without "gross" is a regression, not a style choice.
- **The rule I chose, and would defend:** attributable cost = the **±120s task-window
  union**. Per-query netting is *impossible* (shim receipts carry a `task`, never a
  `call`) — do not let anyone talk you into faking that link. "Whole task" measures task
  size; "turns with a tool-use block" is the rule I'd actually want but no ledger field
  marks one, so it needs a capture-time change (stamp `call` in the transcript route).
  That is the single highest-value follow-up here.
- **The asymmetry is the load-bearing idea, not the window.** The omitted term is ≥ 0, so
  a *negative* net can only get more negative — **COSTING stays assertible**, only the
  positive side wears `(GROSS)`. If someone "simplifies" this into a blanket refusal, the
  tool loses a true statement; if they drop the qualifier, it regains a false one.
- **Coverage refuses on purpose.** A task with no in-window call reports net *unavailable*
  rather than `net = gross`. That is deliberate: a failed join must never be able to
  masquerade as a measurement of zero cost.
- **What is still not answered:** whether graphify actually made those sessions more
  expensive. `cage insights compare` already answers it and only lacks data
  (`MIN_COMPARE_N = 5`, leg D produced 1) — OPEN-WORK **NET-1**, a lab run, not a build.
  Do not build a second comparison path.

**Update 2026-08-01 — kiro capture routing (K2) is BUILT and pinned.**

- Kiro's **IDE** rows now go to the machine ledger; its **CLI** credits are scoped to the
  project tree. Two stores, two *opposite* fixes — getting them backwards destroys real
  attribution. [ADR 0006](adr/0006-kiro-rows-are-machine-facts-not-project-facts.md) ·
  [archived pair](archive/v0.36-kiro-routing.handoff.md).
- **The invariant that changed:** `importcmd.run`'s "one active sink per run — never a
  double-write" now has exactly ONE exception, and it is contained in `_kiro_leg`. If you
  add a second exception, re-read that function first: every per-root object is rebuilt
  against the sink, and the leg's lock is released *before* the sweep's is taken. That
  ordering is the deadlock proof — do not nest them.
- **Two decisions were mine to make, and are recorded:** capture switches compose as
  **AND** (project's and sink's), and the summary line names the sink so a total can never
  imply project rows that landed elsewhere.
- **⚠ Concurrency, 2026-08-01:** a second (Cowork) session was editing this tree during
  the work — `cage/data/cage.toml`, `OPEN-WORK.md` and `IMPLEMENTATION.md` all changed
  under me. The 7 red `policysync`/P5/P6 tests belong to *that* work (`BUD-V`), not to
  kiro routing. Check `git status` for a concurrent editor before diagnosing a red suite.

**Update 2026-08-01 (later) — the Tier-1 human axis is GONE, substrate included.**

- Arpit's call: remove it **completely**, not deprecate — it will be reconsidered from
  scratch after v0.36. There is no stub, no commented-out code, nothing to revert to.
  **If you are about to "restore" any of it: don't.** Write a proposal doc first
  (OPEN-WORK **HR1**). Evidence of what existed:
  [archived pair](archive/v0.36-human-removal.handoff.md) + CHANGELOG v0.36 *Removed*.
- **The trap, recorded because it nearly landed:** cage had two unrelated "human"s.
  Provenance `origin="human"` (authorship) survives untouched. And `cage human outcome`
  / `cage human quality` were **not** the human axis at all — they sat in that command
  group by filing accident. `outcome` is the *task-close* verb `compare`/`estimate`/
  `calibration` all read; deleting it as the handoff literally specified would have
  amputated §4.7–§4.8 in the same change. They moved to a new `task` group.
- **The legacy-row rule now binds every money view:** a pre-0.36 `tool="human"` or
  `unit="minutes"` receipt is excluded via `report._is_legacy_human` and the exclusion
  is **counted and footnoted** on `cage report`. A silent drop would have been a
  method-law violation wearing a different hat.

**Update 2026-08-01 — Phase I is COMPLETE; the queue moved.**

- **Phase D (manual VS Code / IDE cells) ran** on 2026-08-01 and is written up, published
  and hashed in `docs/regression/` (leg-D run report · 4 findings · a final phase
  benchmark superseding 07-29). **Phase I is closed**: scripted legs + manual leg.
- **The result that matters:** same workspace, same six questions, same graphify install —
  **claude invoked graphify unprompted (18,456 tokens saved, captured via the *transcript*
  route because the shim was not on the VS Code extension's PATH); copilot and kiro did
  not invoke it at all.** Adoption is agent-specific, and the usage log is what makes
  "never ran" distinguishable from "ran but cage missed it". Keep that distinction — it is
  the whole reason the C/G1 chase ended in a product answer instead of a phantom bug.
- **The counterweight you must not drop (K0, HIGH):** `saved` is **gross** — it excludes
  the cost of *using* the tool, so cage printed 18,456 tokens saved on a session whose
  measured cost was **+31%** over its unassisted twin. The *label* problem is structural;
  the *delta* is n = 1 and stays UNPROVEN until a repeats = 3 pair. Relabel first
  ("avoided read cost (gross)"), net later — and note `repoceiling` inherits it. This is
  cage's own headline failing the standard cage applies to other tools; treat it that way.
- **K1 is DONE (2026-08-01, unreleased).** The copilot `--path` glob bug is fixed by
  **`[sources] path_globs`** — a second, **root-agnostic** discovery key beside the
  anchored `glob`, seeded in code, materialized by `cage setup`, read from `cage.toml`
  at import. Two things to preserve if you touch this: (1) **no glob literal may return
  to an import branch** — `tests/test_path_globs.py` AST-walks the adapters and will
  fail; (2) **absent `path_globs` is a loud no-op, never a code fallback.** A fallback
  is the obvious "fix" for the mild annoyance that an unmaterialized project can't use
  `--path`, and taking it would put the discovery rules back in two places, which is the
  exact condition that let this bug exist for as long as it did.
- **Next step: K0 in [OPEN-WORK.md](OPEN-WORK.md)** — relabel `saved` as *gross*, per the
  counterweight above. It is the only open finding that touches cage's headline number.
- **Three things a future session must not "tidy up" into a pass:** F2's copilot-VS-Code
  receipt limit is **untested, not confirmed** (copilot never invoked graphify, so the
  predicted path never fired); the D3/D4 prompt counts are **UNVERIFIED**; and **no kiro
  ON/OFF delta may ever be reported** — kiro rows carry no `ts`, no `session` and no
  `project`, so D5 and D6 are literally indistinguishable in the ledger.

**Pre-2026-08-01 (still true unless superseded above):**

- **Next step:** execute [cage-lab-setup.prompt.md](cage-lab-setup.prompt.md)
  (**Opus**, both sibling checkouts) — it is the only unbuilt pair in `docs/`
  root, and its prerequisites are all built and green.
- Everything else specced today is **implemented** and archived under
  `docs/archive/v0.36-*` (archive-on-implement is now the rule).
- **Prices split shipped (2026-07-28):** model prices now live in `.cage/prices.toml`
  (vendor rate card), apart from `cage.toml` (your decisions incl. `[alias]`) — the
  rule is *vendor facts move, routing decisions stay*. Money verified **byte-identical**
  on the real ledger; legacy in-`cage.toml` prices still read via the fallback and
  `cage setup` migrates them money-neutrally. Resolution: `paths.Footprint.prices`.
  CLAUDE.md edits **proposed not applied** (`docs/proposals/claude-md-prices-file.md`).
  The global-vs-project *ledger* question (plan §8) is still open, ADR-level, out of
  scope — a real simplification worth its own compare doc, not a prices question.

## Standing constraints (the human's active directives — do not violate silently)

- **No commits in `cage`** — not a commit, tag, or release, until Arpit says so.
  cage-lab commits freely in its own repo.
- **Session names are always captured** (no opt-in flag) — a deliberate,
  manifest-only PII widening; row stores stay counts-never-content.
- **Savings numbers must be exact: NOT WRONG, NOT DUPLICATED** — the id-deduped
  `receipts()` union is the mechanism; don't "simplify" it back to concatenation.
- **`taskcorr` stays disabled** until validated on real correlated data
  (cage-lab L5 is the gate).
- **Every session updates WORKLOG + IMPLEMENTATION, and this file when direction
  moves** — including Cowork/chat sessions where no code moved.
- **Every prompt doc states its `**Progress:**` percentage** (2026-08-02, Arpit) —
  phases of *that* program built over its total, directly under `**Model:**`, counted
  against evidence rather than the doc's own ticks. He wants to see how far along a
  piece of work is at the moment the prompt is handed over. Keep it current in the
  same change as the work; `0%` at hand-off, `100%` in the change that archives.

## How to work here (the scar tissue)

- **`method` is sacred.** Never let a projection read as `measured`. This is the one
  invariant that, quietly broken, poisons every downstream number.
- **Fail-open on the write path, typed errors at the read/CLI boundary.** Don't
  convert a write path into one that raises; don't swallow silently — trace under
  `CAGE_DEBUG`.
- **Determinism is testable and tested.** No clocks/random in derived views. Same
  ledger + same policy ⇒ same tables. The golden/determinism suites pin capture
  switches OFF — keep them off there.
- **Three agents, always: Claude Code · Copilot · Kiro.** A change to one wiring/read
  surface fans out to all three.
- **`$0` / stdlib-only is the wedge, not a constraint to route around.** ML is
  opt-in extras, never on the default path. cage never fetches a price, never calls
  a model.
- **A renamed/removed verb is a wiring migration**, not just a CLI change — sweep
  every wire file, `install.sh`, `justfile`, docs/skills, and add a `verbmap.REMOVED`
  entry. Dead installed verbs fail open to exit 0 and look like cage-not-installed.
- **Derive or guard, never remind** (2026-08-02, DOGFOOD). Any number a doc publishes
  needs a *mechanism*, not a release-checklist line: `[meta] cage_version` drifted
  **eleven releases** on exactly that. Where CI can't recompute the number (a real-ledger
  figure — no ledger in CI, ZERO dummy data), guard its **freshness metadata** instead —
  a test over a frontmatter date reads no numbers and still can't rot. And **date, not
  version, is the freshness axis**: a cumulative ledger belongs to no single version, and
  version-distance is a broken clock here (v0.37→v0.43 in ~two days; `__version__` is
  deliberately not bumped for in-tree work). Corollary for any published window: make it
  **absolute, never relative** — a relative `--since` re-measures a different window each
  refresh, so staleness can move a number *down*; absolute means staleness only ever
  understates, which fails safe.
- **A shared/global store's "most recent" can be a fixture, not real usage**
  (2026-08-02, DOGFOOD execution). Publishing this repo's own numbers, the "real"
  ledger's `cage insights attrib` output for its default (most recent) task turned out
  to be `cage demo`'s seed — the *only* task-tagged row in the whole global `~/.cage`
  ledger. A command returning cleanly is not proof its input is real; trace a
  self-measurement number back to its source rows before publishing it, especially
  from a global store other work (tests, demos, other projects) also writes to.
- **macOS hides case-broken links; GitHub does not** (2026-08-02, DOC-CASE). The tracked
  file is `docs/formulas.md`, and **120 citations across 49 files** — CLAUDE.md, four
  `cage/*.py` modules, the maintained-doc list itself — spell it `FORMULAS.md`. Every one
  resolves on this machine and dangles on the renderer and any case-sensitive checkout.
  This is the dangling-pointer class CLAUDE.md's *deleting a doc is a citation migration*
  rule exists to prevent, and it went unseen for months because the dev filesystem is
  case-insensitive. When you add a doc citation, check the **tracked** name
  (`git ls-files`), not the one that happens to open.
- **Verify a log shape against real data before coding to a plan's claim.** The
  v0.36 plan asserted the Copilot VS Code title sits on the `kind:0` record; 143
  real sessions said otherwise (it's a `customTitle` patch record, with
  `generatedTitle` as fallback, and ~38% of sessions have no title at all). The
  executor caught it because the prompt said "STOP if shapes disagree" — keep
  that instruction in every prompt. **And when a spec is corrected, sweep every
  doc downstream of it**: the same wrong claim was also sitting in the cage-lab
  plan, where it would have produced fixtures that pass against a shape reality
  doesn't have.
- **A grep-gate is only as tight as its allowlist.** `tests/test_cli_tiering.py`
  keeps an allowlist of live *group* names so `cage data export` isn't flagged as a
  stale `export`. When the `human` group died, the allowlist still listed it — so five
  stale `cage human …` strings sat in shipped source, invisible, until the allowlist
  was tightened in the same change. **When you remove a group or verb, update the
  gate's allowlist first, then read what it finds.**
- **A doc rule that fights the workflow will be broken silently.** Archive-on-ship
  was such a rule — cage works in long uncommitted stretches, so finished work
  sat in `docs/` root and the *Active work* list lied. It is now
  archive-on-implement. If a rule keeps getting violated, fix the rule.

## Working with the human (Arpit)

- Wants a recommendation, not a menu. Direct, opinionated, grounded in a reason.
- Values the *why* being written down where it can't be silently deleted — that's
  the whole reason ADRs carry a veto condition and rules carry references.
- Prefers reconcile-don't-duplicate: match an existing doc/name before creating a
  new one.

## Maintainers

- Claude (Opus 5) — 2026-08-03 — built CHATS-AUTHOR (`agent%` on `cage insights
  chats`, 1442/0 ⇒ 1462/0). **The lesson I'd want inherited: a recorded fallback can be
  moot, and noticing that is the work.** The handoff said "demote the column behind
  `--authorship` if the golden overflows 100 cols" — but the chats table was already
  **113 cols before the column existed**, so width could never have been what decided
  it. Both readings were defensible and they lead to opposite products (a default
  column vs. one nobody discovers), so I raised it instead of picking. **A trigger
  written against a threshold that was already breached is not a trigger — it is a
  stale assumption wearing one.** Check whether a spec's gate could ever have fired
  before you let it decide anything. Second, smaller: the same instinct applies to a
  *count* of things a spec enumerates. The proposal named three refusal shapes; a
  fourth exists in fact (a provenance row that joins but carries no matchable line).
  I folded it into an existing shape rather than inventing a new one, because both
  reduce to the identical statement — but an executor who trusts "three" as a closed
  set ships a `ZeroDivisionError` instead.
- Claude (Opus 5) — 2026-08-02 — reviewed and prioritised the open queue
  (merged into [OPEN-WORK.md](OPEN-WORK.md)). Lesson for the next model:
  **when you are asked to prioritise, the ranking axis is the deliverable — not the
  list.** The queue read as a flat backlog with one "Next"; it was actually two lanes
  (the human's hands vs. agent sessions) that had been serialised against each other for
  no reason, and the items inside the agent lane split cleanly into *damage that accrues
  while you wait* (REV-TS, ID-ENTROPY — both write append-only rows a later fix cannot
  rewrite) and *damage that is merely present*. Finding that axis reordered more than
  arguing about any individual item's severity would have. Second lesson, and it paid
  three times in one session: **rule 3 applies to every doc, not just OPEN-WORK's ✅s.**
  Reading the repo instead of the queue file caught that CHATS-AUTHOR was already
  packaged *and already stalled* (which became the strongest evidence in the whole
  proposal), that OPEN-WORK's header still called a released v0.44 unreleased, and that
  the review's own "fix `otelout`" framing pointed at the wrong module — `otelout`
  omits correctly; the fabricated `$0` is `convert.py:35-36`. A review inherited
  second-hand is a hypothesis, including one I wrote.
- Claude (Sonnet 5) — 2026-08-02 — built DOGFOOD (cage's own ledger, published).
  Lesson for the next model: **"most recent" is not the same claim as "real."**
  `cage insights attrib` defaults to the most recent task, and on this machine's real
  global ledger that task was the `cage demo` seed itself — the only task-tagged row
  in the *entire* ledger, sitting there since whenever `just demo` was last run. It
  would have published fabricated numbers under a "real, verbatim" banner if I hadn't
  traced the task name back to its source rows before writing anything down. **Any
  self-measurement feature that reads "the most recent X" from a shared/global store
  must be checked for fixtures, seeds, and test data before the output is trusted as
  real** — a command that works correctly is not evidence its *input* is real. Second,
  smaller lesson: a non-negotiable written for one failure mode ("P0's output is
  missing") doesn't automatically cover its sibling ("P0's output exists but is
  contaminated") — when a real scenario doesn't match any case a rule enumerated, that
  is itself the "ambiguous — stop and ask" case, not a gap to reason past alone.
- Claude (Opus 5) — 2026-08-01 — built the Windows graphify twin (WIN-GF) and the CI
  graphify axis (CI-GF). Lesson for the next model: **when a handoff states a fact about
  a third-party tool, go look at the tool.** This one said graphify installs via npm and
  therefore ships its own `graphify.cmd` on Windows, and the whole "skip by content, the
  filenames collide" trap was built on that. graphify is a **PyPI** distribution
  (`graphifyy`) — on Windows it is `Scripts\graphify.exe`, the filenames never collide,
  and the *real* Windows hazard is the opposite one nobody had written down: `.EXE`
  precedes `.CMD` in the default `PATHEXT`, so a twin sharing a *directory* with the real
  binary is silently skipped. Thirty seconds of `file $(command -v graphify)` replaced a
  paragraph of confident fiction. Second lesson: **a green check that asserts nothing is
  worse than a red one.** My first CI corpus was ~1.2 KB, so every graphify query came
  back honestly `unmeasurable` (the answer cost more than the files it cited) — the leg
  passed while proving nothing. Size the fixture until the thing you are measuring
  actually happens, then assert the number. Third, the one I nearly shipped: the prompt
  handed me `call "%REAL%" %* & exit /b %ERRORLEVEL%` as the cmd idiom. On one line cmd
  expands `%ERRORLEVEL%` at *parse* time, before `call` has run, so the shim would have
  reported the previous command's status — passthrough silently broken, in the file whose
  entire job is passthrough. A suggested snippet in a prompt is a hypothesis, not a spec.
- Claude (Opus 5) — 2026-08-01 — built kiro capture routing (K2 + the K3/K4 honesty
  lines). Lesson for the next model: **never `git stash` in this repo.** I used one to
  isolate a failure; it restored every byte, but it flattened the `MM`/`AM` staged-vs-
  unstaged split that this long-uncommitted tree encodes, and for ten minutes I was
  diagnosing my own tooling instead of the bug. The tree here is *the* working state —
  copy files aside instead. Second lesson, the one that actually caught a defect:
  **write the test that asserts the message text, not just the code path.** K4's caveat
  checked `"claude" in agents`, but a claude row's `agent` field is `claude-code` — the
  honesty line would have compiled, shipped, and silently never printed. An honesty
  feature that can fail silently is the exact failure it exists to prevent, so pin the
  string. Third: when a prompt says "verify X against a real store before filtering on
  it", do it *first* — the real `conversations_v2.key` turned out to be symlink-resolved
  (`/tmp/x` stored as `/private/tmp/x`), and a filter written from the obvious assumption
  would have returned zero rows, which is indistinguishable from "no usage".
- Claude (Opus 5) — 2026-08-01 — removed the Tier-1 human axis (substrate included).
  Lesson for the next model: **a handoff's scope list is a survey, not a verified
  change-map — read every file it names before deleting.** This one listed
  `cage human outcome` and `cage human quality` under "delete outright"; both are in
  fact load-bearing for the cost-impact surface and merely shared a command group with
  the doomed feature. The handoff even warned about *one* two-different-"human"s trap
  (provenance) while walking into a second. Deleting to spec would have passed the
  stated acceptance criteria and quietly removed §8.2 and the ability to close a task.
  Second lesson: **when a test passes on the first run of a new regression file, try to
  break it.** `test_legacy_ledger.py` passed immediately; mutating `_is_legacy_human`
  showed half the predicate was unexercised, because every fixture row happened to be
  `tool="human"`. One extra fixture row later, the mutant dies.
- Claude (Opus 5) — 2026-08-01 — built `[sources] path_globs` (K1). Lesson for the next
  model: **before inventing a mechanism, check whether this repo already ruled on the
  case.** Two spec sections here contradicted each other — flip the finding's Status vs.
  never touch `docs/regression/**` — and the file was sha256-sealed, so both readings
  looked defensible. The answer was already written down: DOC-REGISTRY records a banner
  above a `HASH-COVERS-BELOW` marker keeping a digest valid. Applying the precedent
  satisfied both rules exactly; my first instinct (record it elsewhere and escalate) would
  have left a published doc lying about its own status. This repo's conventions are dense
  and mostly *already decided* — search before you escalate. Second, smaller: I found an
  unstaged half-built version of this very feature sitting in `paths.py` from an
  interrupted session. Always read the working tree, not just HEAD, before starting.
- Claude (Opus 5) — 2026-08-01 — wrote up and published leg D (Phase I closed). Lesson
  for the next model: **the temptation in a write-up is to convert an absence into a
  result.** Copilot and kiro produced *zero* graphify usage rows — it would have read
  beautifully as "F2's limit confirmed", and it would have been false: the path was never
  exercised. An untested cell is not a limit, and a limit you predicted is not evidence.
  Write `UNTESTED`, say why, and name what would exercise it.
- Claude (opus) — 2026-07-25 — added the documentation-discipline doc set + CLAUDE.md
  rules; created this record (it was referenced but missing after the doc sweep).
- Claude (Fable 5, Cowork) — 2026-07-25 — the strategy/spec desk for the v0.36 arc:
  hookless-removal decision + handoff pairs, the import-ledger plan revisions
  (savings tree, always-on names, precise migration), cage-lab v3 plan + PLAN.md
  §11, and the continuous-WORKLOG/INTERVIEW succession rules. Lesson for the next
  model: Arpit decides fast and in fragments across chat — capture each directive
  into the plan's decisions log *immediately* (he will build on it minutes later),
  and when he says "you tell me", give ONE recommendation with the rejected
  alternatives named, not a menu.
