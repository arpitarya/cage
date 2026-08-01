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

## State of play (2026-07-25, updated same day — pick up here on a model switch)

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

**Update 2026-08-01 (latest) — gross vs net savings (K+NET) is BUILT. Read this before
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
