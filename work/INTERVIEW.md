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
the [ADR set](../docs/adr/README.md), those win. Distinct from [WORKLOG.md](WORKLOG.md) (the
granular per-exchange trail) and [IMPLEMENTATION.md](IMPLEMENTATION.md) (what is
built, milestone by milestone) — this is the strategic, cross-session record.

Entry-point tracker: ALL-CAPS, no frontmatter.

---

## State of play (2026-08-15 — pick up here on a model switch)

- **ADR-CONFIG exists and nothing it decides is built (2026-08-15).** `cage.toml` had run
  since the `policy.toml` rename with **no owning record**, and its five modules sat on
  `test_adr_ownership.py`'s `NO_RECORD` list — where placement is an explicit claim that a
  module encodes no decision. A drift census falsified that claim in three ways at once:
  three live knobs ship in no file, three shipped sections have no reader, and two surfaces
  still teach deleted config. **The lesson is the structural one, not the list**: none of it
  failed and no test could have seen it, because `test_cli_reference` gates commands and a
  config key is not a command. The whole config surface is ungated — CONFIG-GATE in
  OPEN-WORK is the item that matters most; the other seven are its consequences.
  **Read [ADR-CONFIG](../docs/adr/0012_config.md) as a target, never as a description of
  today's file.** The sharpest ratified call is `[tools] order` demoted to a constant: it
  is the one place cage learned an ordering it cannot observe, and it carries the record's
  only UNMEASURED veto — one real project with a non-default pipeline order reopens it.

- **`docs/PLAN.md` is gone (2026-08-14/15, Arpit's instruction) — the ADR set is the
  design of record now.** Its `plan §X` addressing scheme, which ~60 source files cited,
  was repointed record by record; three anchors with no live successor were stripped
  rather than pointed somewhere plausible. **If you find a `plan §` citation, it belongs
  to an archived plan (import-ledger, prices-toml), not to a live doc — name it, never
  cite it.** The deletion itself was pending on Arpit's machine at hand-off: the Cowork
  bridge cannot delete files and left a stale `.git/index.lock`.

- **STUDY-CUT (2026-08-15): the P5 fleet study is deleted whole, and it rides the same
  unreleased v0.51.** Six verbs, `study.py`, `machine.py`, phase markers, the opaque
  per-machine id, the zip bundle and its `cage import BUNDLE` merge — *and* the additive
  **`machine` row field** four writers stamped. Cage no longer aggregates across machines
  by any route. **Inherit two things from how it was scoped.** First: the ask was "remove
  cage study from cli", and the honest default under SURFACE-CUT was the CLI group alone —
  I asked Arpit rather than assuming, and he chose the subsystem. Second, and the part
  worth keeping: SURFACE-CUT was *not* overridden. A "writer" reachable only through the
  verbs you are deleting is dead code, not a recorded fact; the rule bites on writers that
  survive the cut. The one real writer here (`machine.stamp`) went too, and that is named
  as a substrate change in CLAUDE.md rather than buried in a docs diff. **What was
  deliberately NOT tidied:** `machine.json`/`study.jsonl` stay undeletable in
  `cleanup.NEVER`, `[capture] import_before_export` stays as an unread key (UNREAD-FACTS
  is now five facts), and `MIN_COMPARE_N` stays because ADR-GRAPHIFY's veto cites the
  number. Each has its reason at the definition site — do not "clean these up".
- **v0.51 is BUILT and unreleased: LEDGER-RESTRUCTURE, nine phases, 1521 green.** Every
  producer owns exactly one directory under `ledger/` — `claude/` `copilot/` `kiro/` ·
  `consumer/` · `graphify/` `fux/` `compress/` `responsecache/` · `provenance/`. The
  claude/copilot transcript→`calls` writer is **retired**. A tamper-evidence chain ships as
  [ADR-INTEGRITY](../docs/adr/0010_integrity.md), the tenth live record.
- **THE RULE THAT MADE THIS SAFE, and inherit it: nothing on disk was ever moved.** Every
  migration is *stop writing here, start writing there, **read both forever***.
  `calls-*.jsonl`, `credits-*.jsonl`, `savings/<tool>/`, `ledger/imports.jsonl` and
  `ledger/provenance.jsonl` all still resolve. **`calls` can never be fully retired** —
  retired-agent rows (codex) have no other home.
- **KIRO-CALLS-LEG is SETTLED (Arpit, 2026-08-15) — and the way he settled it is the
  lesson worth inheriting.** The spec said retire all three legs; P5 kept kiro's because
  kiro IDE has no metric twin, so retiring it would have ended that surface's capture
  rather than de-duplicating it. Offered ratify-or-reverse, Arpit took **neither**: *"retire
  it and capture the data in `ledger/kiro`."* The leg is gone — no built-in leg writes a
  `calls` row now — and `tokens_generated.jsonl` is read into the kiro-metrics ledger as
  `source="ide-log"` instead.
  **Inherit the shape of that call, not just its outcome:** the deviation was framed as a
  binary, and both options were worse than the third. Keeping the leg preserved capture at
  the cost of a permanent exception; reversing it satisfied the spec at the cost of real
  data. Relocating satisfied both, and the exception got *better* on the way through — as
  `calls` rows these were spend every total had to exclude BY NAME (`ABSENT_SPINES`, a rule
  someone has to keep remembering); as metrics rows they are capture-only **by kind**. When
  a queue item reads *ratify or reverse*, check whether the thing the deviation was
  protecting can be protected somewhere better.
- **The one measurement that can never be retaken.** `METRICS-DUAL-WRITE-END`'s freeze was
  lifted early, so P0's
  [cross-check](regression/2026-08-14-calls-vs-metric-crosscheck.md) is the sole record of
  what the two writers disagreed by: **1.979× on rows, 1.881× on tokens** for claude, and a
  **zero** skip-rule delta for kiro credits. Claude Code sweeps transcripts at ~30 days.
  Treat that file as irreplaceable evidence, not as a report.
- **If you are about to "clean up" a legacy path, don't.** Deleting a reader is a separate
  decision from stopping its writer (the SURFACE-CUT rule), and every legacy file here is
  load-bearing for someone's history.

## State of play (2026-08-14 — historical)

- **The ADR set is ONE RECORD PER METERED THING PLUS [ADR-LAWS](../docs/adr/0001_laws.md),
  and you cite them BY NAME.** Read ADR-LAWS §1 first — it holds the five laws (pull-only ·
  one sink · append-only · counts-never-content · usage-never-cost), each with its
  ratification and a numbered veto, and **every other record assumes them and restates
  none**. A per-agent record that restates a law is a bug, not redundancy.
  [ADR-CLAUDE](../docs/adr/0004_claude.md) · [ADR-COPILOT](../docs/adr/0005_copilot.md) ·
  [ADR-KIRO](../docs/adr/0006_kiro.md) · [ADR-GRAPHIFY](../docs/adr/0008_graphify.md).
  **Never write "ADR 0003"** — the numbers belong to the eleven superseded records now in
  [work/archive/adr/](archive/adr/README.md), which are **history and never current spec**.
  Each live record has **§1 for humans** (one screen, a Mermaid diagram and a hand-paired
  ASCII twin) and **§2 for agents**.
- **`docs/shim-contract.md`, `claude-capture.md`, `copilot-capture.md` and
  `kiro-capture.md` are GONE (2026-08-14), absorbed whole.** The interceptor behaviour
  contract — B1–B8, B8a, D1–D8, the anti-recursion proof — is **ADR-GRAPHIFY §2** and
  nowhere else. A capture change now updates one document, not two; that was the point.
  The originals sit in `work/archive/_removed-2026-08-14/` only because the Cowork bridge
  cannot delete files.
- **⚠ If `git status` looks like two changesets interleaved, it is.** On 2026-08-14 a
  second session relocated this session's new `docs/adr/archive/` and `git add`-ed its
  deletions into the SURFACE-CUT staged set, then left `.git/index.lock` held. The
  concurrent-session hazard is not theoretical in this repo: **check `git status` and
  `.git/index.lock` before you start**, and re-stage before you commit anything.

- **Cage no longer measures money, and this is the biggest thing to internalise before
  you touch anything.** USAGE-ONLY deleted the whole money subsystem: 15 modules
  (~2,457 lines), 11 CLI commands, 4 MCP read tools, the `--usd` view, the bundled rate
  card, and the `[prices]`/`[credits]`/`[billing]`/`[alias]` config sections. Cage
  reports **tokens and credits** — the units the vendors themselves record — and
  converts between nothing. Read
  [ADR 0011](archive/adr/0011-cage-measures-usage-not-cost.md) before proposing anything
  that produces a currency figure; it has a numbered veto condition, and "a user could
  configure their own rate" is already in *deliberately not taken*.
- **The spend cutover is retired.** `ledger.spend()` partitions by **agent**, not time.
  ADR 0010 still stands on *why the metric ledgers are the source*; its cutover half is
  superseded.
- **Suite: 1571 passed / 11 skipped.** Down from 1842 because ~270 assertions tested
  money. `tests/test_usage_only.py` is the new regression pin (23 invariants, incl. an
  AST scan that fails if a currency identifier or a rendered `$N` reappears anywhere).
- **Three lessons from this build, each of which cost real time:**
  1. **A "money module" is often money *plus* something load-bearing.** `quality.py`
     held the outcome store — the write half of the only MCP mutation cage has.
     `pricestoml.py` held the generic comment-preserving TOML writer that
     `cage policy sync` needs. Both would have been silent amputations. **Before
     deleting a module, list what would break that has nothing to do with the reason
     you are deleting it.**
  2. **The literal reading of a handoff can be the wrong one, and it is cheap to
     check.** §5.1 said "`spend()` = the three metric ledgers". Implementing it
     literally: 195 test failures, and it would have silently zeroed **373 real `codex`
     rows** plus all library/proxy traffic. Two throwaway implementations and two suite
     runs settled it in ten minutes. **Measure the blast radius before arguing about
     the wording.**
  3. **Fixtures encode the old architecture, and they fail *quietly*.** Retiring the
     cutover meant every test seeding `calls` rows for claude/copilot was seeding an
     empty ledger — assertions that pinned nothing rather than assertions that failed.
     The fix is one shared `metric_twin` helper in `conftest.py`; the lesson is that a
     basis change is a fixture migration, and the tests will not tell you politely.
- **Known gap, filed not hidden: TASK-GRAIN-SPINE.** Metric rows carry no `task`, so
  `compare`/`estimate`/`calibration` read **zero** for claude and copilot. Same cause
  collapses `report --by route` to `chat` for those agents. It is the top of OPEN-WORK.
- **Two things need Arpit** (in OPEN-WORK's *Arpit decides*): whether this deletion gets
  its own version — it currently sits under the unreleased v0.49.1 changelog heading with
  `__version__` untouched — and a read of the repositioned README.

---

## State of play (2026-08-13 — historical)

- **`docs/` vs `work/` split moved further: doc-registry, research, regression,
  dogfood, compare, cage-lab, and archive now live under root `work/`, not `docs/`.**
  Arpit's instruction (Cowork session), continuing the 2026-08-12 WORK-DIR move.
  `docs/` now holds only: `PLAN.md`, `CLI.md`, `FORMULAS.md`, `GLOSSARY.md`,
  `README.md`, the three `*-capture.md` one-pagers, `doc-size-discipline.md`,
  `../docs/adr/0008_graphify.md`, `restricted-environments.md`, `adr/`, `architecture-flow.mermaid`,
  `assets/`, `example/`. **New handoff/prompt pairs are now specced directly into
  `work/` root**, not `docs/` root — CLAUDE.md's *Handoff/prompt docs have a
  lifecycle* rule was rewritten for this; see the Standing constraints bullet below.
  Every LIVE cross-reference (in both directions) was swept and `test_doc_links.py`
  re-verified green by direct import (no `pytest` in this sandbox — no network to
  install it). Full account: `work/WORKLOG.md`'s 2026-08-13 WORK-DIR-CONT entry.

## State of play (2026-08-12 late — historical)

- **THE QUEUE IS EMPTY BECAUSE ARPIT CLOSED IT, NOT BECAUSE IT WAS WORKED.** On
  2026-08-12 he instructed that all open items and all parked proposals be archived
  wholesale. Sixteen docs moved to `work/archive/v0.49-*`, **none of them built**;
  `docs/open/` and `docs/proposals/` no longer exist. `OPEN-WORK.md` now records what was
  closed and what each closure left unresolved. **Do not read the empty queue as
  progress** — read the closure table.
- **The one closure that is a defect, not an idea: SHIM-TOOL-DEPS.** With no `grep`
  resolvable on PATH the shipped POSIX graphify twin selects *itself* as the real binary
  and re-execs forever — a reproduced 120-second hang, pre-existing in every released
  version, closed **unfixed**. A hang is the worst failure shape a fail-open path can
  have. If you touch the twins, read
  [archive/v0.49-shim-tool-deps.item.md](../work/archive/v0.49-shim-tool-deps.item.md) first.
- **`CONSTRAINTS.md` was archived, and its rules were NOT migrated into CLAUDE.md.** It
  was never open work; it moved because its directory was emptied. Most of it is enforced
  mechanically and survives (`tests/test_floor.py`, `agents.SURFACES`, `wiringscan`,
  `attest.LIMIT`), but five constraints now live on prose alone in an archive file —
  named in that file's header. **If you find yourself about to mutate `tinyshop`, or to
  soften copilot's "unverified on a real Copilot" text, that is why nothing stopped you.**
- **NET-1 was closed unrun, so cage still has no evidence that any tool nets positive.**
  `insights compare` remains gated at `MIN_COMPARE_N = 5` with 1 produced. Every
  correctness feature in this repo still rests on an unmeasured payoff.
- **What I'd warn you about, and it is procedural:** two environment faults bit this
  session and both are structural to the Cowork device bridge, not one-offs. A
  **concurrent session** wrote five docs mid-run (back up before you edit — mtimes are
  your only detector), and a `git status` through the bridge leaves `.git/index.lock`
  behind that **the bridge cannot delete**, jamming git for every process in the repo.
  Use `git --no-optional-locks status`, and do file moves with plain `mv`.

## State of play (2026-08-12 earlier — historical)

- **The agent lane is empty again, and this time it is empty *because it was measured*,
  not because it was worked through.** Of eleven queue items, **nine are structurally
  unbuildable by an agent** — five need a real Copilot/Kiro/second repo or accumulated
  real usage, four sit on triggers that have not fired. The four that were buildable are
  done. **1639/0/11 ⇒ 1650/0/11.**
- **Two decisions are waiting on Arpit and nothing should proceed past them:** the
  `CLAUDE.md` *Documentation discipline* correction (proposed as a diff, **never
  applied** — steering files are not silently rewritten) and the 9-commit split for the
  **65 staged files / 8 unpushed commits**. Still `__version__` `0.48.0`, v0.49 in tree,
  unreleased. Nothing was pushed or tagged.
- **The header of `docs/OPEN-WORK.md` is now test-gated** (`tests/test_queue_honesty.py`)
  — the last uninstrumented drift surface in the repo. It checks only *durable* claims
  (version · tag · clean-and-pushed) and deliberately ignores counts, and it **skips**
  rather than fails when git ground truth is unavailable.
- **The thing to internalise from this session, and it generalises past this repo: a test
  that builds both sides of a join with one side's code proves nothing.** L1's attested
  table read zero for nine days behind a green suite, because every test fabricated its
  usage row with `usagelog.args_hash(<tail>)` — the *attestation's* convention. The one
  producer that disagreed (the shim route, folding in an absolute machine-specific
  `argv[0]`) was never exercised. When you test a join, make at least one side come from
  the real producer.
- **Its twin, for prose gates: falsify the real file, don't reason about the regex.** The
  queue gate passed all its own fixtures while reading **nothing** from the real header —
  twice. A past-tense clause fused to a live claim across `.**`, and a matcher wanting
  bare `HEAD == origin/main` when this repo writes `` `HEAD` is `origin/main` ``. Neither
  was visible from a green result. Both surfaced the instant the real file was mutated.
- **What I'd warn you about:** the pressure on a diagnosis phase is to end with a fix that
  *looks* like it closed the thing. P2's fix closes **one of three** causes, and the other
  two are named in the finding, the changelog, and the queue item rather than smoothed
  over. All three real attestations are piped, so the table on the dev ledger will still
  read zero — **the honest version of "fixed" here is "necessary, not sufficient."**
- **A smaller warning, same family:** the handoff's own "47 staged files" was already
  wrong when written (65). That is why the gate this session built refuses to check
  counts — a number that is true only at the instant of writing is not a claim worth
  gating, it is a claim worth not making.

## State of play (2026-08-11 late — historical)

- **The agent lane is EMPTY.** All seven items that made up tiers 2 and 3 of
  `OPEN-WORK.md` were decided and built in one session: COMMITS-WINDOW ·
  COPILOT-PREMIUM-DEAD · REV-CREDITS defect 2 · OTEL-SEMCONV-PIN · CLI-GAPS(b) ·
  STEERING-EDITS · DOC-LINK-CHECK. **1616/0 ⇒ 1639/0.** In tree as **v0.49, unreleased**;
  `__version__` is still `0.48.0`, the CHANGELOG entry **is** written, and the release
  needs Arpit's go (the GitHub release IS the PyPI trigger).
- **Two of them are reader-facing breaks and must not be released quietly:**
  `--otel` now emits `gen_ai.provider.name` instead of `gen_ai.system` (renamed upstream
  in semconv v1.37.0), and `cage insights chats` lost its `premium` column. Both are in
  the changelog with the migration; neither moves a stored number.
- **The one thing to internalise from this session:** *a recommendation written from
  partial evidence is not a decision.* OTEL-SEMCONV-PIN's own research doc recommended
  "re-point the pin at the GenAI repo's versioning" — and when I went to do it, that repo
  turned out to have **no tagged release at all**. The option was impossible as written.
  What shipped instead states what `1.42.0` *means* rather than citing a number nobody
  could check. **Re-verify the premise of a recommendation before executing it**, even
  when the recommendation is cage's own and was written eight days ago.
- **The rule that decided the hardest call:** REV-CREDITS defect 2 had two candidate
  fixes and the standing law picked one. Splitting a group credit pro-rata by token share
  is *arithmetically* fine and **forbidden** — credits are never derived from tokens in
  either direction. So the fix had to be a **recorded structural fact** (`billed_with`),
  not a computation. When two fixes both work, check which one invents a number.
- **`CLAUDE.md` is no longer behind the code.** All six held steering edits are applied,
  and two landed *amended* by decisions taken the same day. The proposal that held them
  recorded its own best lesson on the way out: **a held patch decays against its target**
  — its `just test` number went 1401 → 1441 → 1462 → 1639 while it waited, which is why
  it became a rule instead of a number.
- **What I'd warn you about:** `docs/OPEN-WORK.md`'s §Implementation described two items
  as pending that were **already built at HEAD**. That is the fourth wrong marker in that
  file in a week. It is an excellent queue and a poor oracle — read the code.

## State of play (2026-08-11 — the agent-lane sweep, historical)

- **The agent-lane sweep is CLOSED — all six phases, 1542/0 ⇒ 1616/0, zero goldens
  re-blessed.** Pair archived to `work/archive/v0.49-agent-lane-sweep.{handoff,prompt}.md`.
  In tree as **v0.49, unreleased**; `__version__` is still `0.48.0` and the CHANGELOG
  entry is not written — that is the next step, and it needs Arpit's go (the GitHub
  release IS the PyPI trigger).
- **One thing is waiting on you and nothing else is:** **COMMITS-WINDOW**
  ([compare](../work/compare/commits-view-cost-bound.compare.md)). `cage insights commits` runs
  one `git show` per commit in the *whole* history to print 20 rows (measured 6.4s /
  123 commits). The obvious fix — a default `--since` — is wrong, and that is the whole
  doc: a **relative** default puts a wall clock in the default path, so the same ledger
  renders differently next month. Recommendation: option B, bound the *read* by the row
  cap. **Do not let a later session take option A quietly.**
- **The one thing to internalise from this sweep:** *the tracker was wrong about its own
  premises in eight places, and the handoff that corrected it was still wrong in four
  more.* A sixth crash site the proposal never listed; a second quoted-path defect
  (git's disambiguating tab) that survives the fix the handoff prescribed; a third
  C-quoting site stamping a mangled `scope` into the ledger; and an
  "assert this interaction" instruction pointing at a branch that is **unreachable**
  from its caller. **Verify the defect before you fix it, every time — and when the
  verification disagrees with the spec, that finding is the deliverable.** Every fix
  here was mutation-checked precisely because green-on-arrival proves nothing: several
  of these defects had passing tests that asserted the wrong layer.
- **A refactor's leftovers are not inert.** Two of the three views v0.48.0's `--export`
  scope line missed were missed for the *same* reason — a hand-rolled `csv_dest` branch
  sitting ahead of `emit`, the exact duplication the chokepoint was built to delete. It
  bit again mid-change: my first wiring of `study report` silently produced an artifact
  with no CSV *for a view that owns a `render_csv`*. When you centralise something,
  the files that did not get converted quietly opt out of everything you add later.
- **The design call worth inheriting:** commit shas are now stored **full** and displayed
  **abbreviated** (`SHORT_SHA_DISPLAY`). The evidence that the split is right is that
  **no golden moved** — `full[:7]` is exactly the `%h` the tables already printed. When a
  precision change and a display contract seem to collide, check whether they are
  actually the same axis before trading one away.

### Before the sweep

- **v0.48.0 is RELEASED** (tagged, on `origin`, GitHub release `2026-08-10T18:55Z`,
  `cage-flux 0.48.0` on PyPI, `HEAD == origin/main`). The section below said *unreleased
  in tree* for a full day after it shipped, and so did `OPEN-WORK.md`'s header and the
  agent-lane-sweep handoff's entire P0 STOP gate. **Never restate a release claim from
  prose here** — `git ls-remote --tags origin`, `gh release view`, PyPI.
- **The agent-lane sweep is under way** ([handoff](../work/archive/v0.49-agent-lane-sweep.handoff.md) ·
  [prompt](../work/archive/v0.49-agent-lane-sweep.prompt.md), 29%). **P0 needed no work** (above); **P1
  CIGF-HERMETIC is closed** — `tools/cigraphify` now seeds `project/.cage` so
  `find_project_root` short-circuits inside the sandbox, and the `present` leg ran
  **7/7 on a developer machine for the first time** with the real `~/.cage`/`~/bin`
  proven byte-identical by a before/after shasum manifest. Suite **1542 ⇒ 1545**.
- **Suite counts here were wrong too:** the real baseline was **1542**, not the 1541
  this file, `README.md` and `CLAUDE.md` all carried. Corrected everywhere.
- **Next:** P2 — REV-HARDEN P3 wiring hygiene (Opus; five items, 5a before 5b, and
  kiro's hook gets a *named gap*, never a twin).

## State of play (2026-08-10 — historical, and wrong about the release)

- **v0.48.0 sits unreleased in tree** (`__version__ = "0.48.0"`, suite **1541/0**). It
  adds the **artifact surface**: `--export`/`--stamp` on `cage report` and all 16
  `cage insights` views (`cage/viewexport.py` + `cage/runstamp.py`), and fixes
  `cage insights chats --agent kiro` blaming the filter for an architectural fact.
  Read CLAUDE.md's new **View export + the run stamp** bullet before touching either.
- **The one thing to internalise about this work:** *a wall clock is allowed on a read
  surface only because it can never reach a number, and stdout proves it.*
  `tests/test_view_export.py::test_export_never_changes_stdout` asserts stdout is
  byte-identical with and without `--export`, across six views. That is the same shape
  as `tests/test_floor.py`'s bargain for the agent-surface ladder, and it binds the same
  way: **if a future export feature needs stdout to move, the feature is wrong.** The
  stamp is mandatory in a *file* (it outlives its terminal) and opt-in on a *terminal*.
- **Next:** release v0.48.0 through the GitHub-release trigger (never publish from
  local). Then the queue is unchanged: **NET-1** in your hands, tier 2's three decisions
  in the agent lane, and the field-verification items that need a real machine.

## State of play (2026-08-02 — historical)

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
  [handoff](../work/archive/v0.46-chats-author.handoff.md) ·
  [prompt](../work/archive/v0.46-chats-author.prompt.md) ·
  [proposal](../work/archive/v0.46-chats-author.proposal.md); living spec is FORMULAS
  §2.13/§2.14. **Its Phase-0 REV-TS gate did its job** — it STOPped an earlier session
  cold with no work done, REV-TS was then built and shipped, and the re-run verified the
  gate independently rather than trusting the prompt's own status line. That sequencing
  is the model to copy, not an obstacle that was overcome. The limit the handoff's
  Stress-tested line named (same-file double-count across sessions) is **shipped as
  stated, not fixed**: per chat there is no diff to clamp against, so the commit view
  stays the arbiter for any single sha.
- **GFX-COV is BUILT, all five phases, 2026-08-07 (v0.47.0, 1462/0 => 1498/0).** graphify
  savings now file from copilot **VS Code** and kiro **CLI** as well as claude and
  copilot-CLI; `cage import --rescan-graphify` backfills sessions the cursor already ate;
  kiro **IDE** is a named gap in doctor + `cage query graphify-coverage`. Pair archived
  (`work/archive/v0.47-*`), evidence in
  [research/2026-08-07-graphify-store-evidence.md](../work/research/2026-08-07-graphify-store-evidence.md),
  carve-out in [ADR 0009](archive/adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md).
- **The one thing to internalise about it: the blocking P0 gate paid for itself on the
  first phase.** The pair's central premise - "F2: copilot's chatSessions carries the
  command but no tool result" - was **false**, and had been for as long as the skip
  existed. 1,132 real `run_in_terminal` parts carry the command, a per-command `cwd`, and
  the output. Nobody had looked; the skip cited a finding that was never a measurement.
  **If you inherit a capture gap justified by a store's shape, go read the store.**
- **Two refusals in that work are load-bearing and must not be "fixed" into coverage.**
  (a) kiro caps tool stdout at ~2000 tokens, so a long graphify answer files **nothing** -
  a truncated answer under-counts `actual` and would *inflate* the saving; a lower
  confidence would dress up a number wrong in a known direction. Its column looking thin
  is the guard working. (b) The VS Code truncation guard deliberately matches **no marker
  string**: all 23 `truncat` hits across the corpus were the command's own rust-clippy
  output, so a substring guard refuses good receipts and catches no real elision. Both are
  decisions backed by counts, recorded in ADR 0009's veto and in the research doc.
- **Still open (GFX-COV-FIELD, needs a machine not a session):** no real graphify run has
  ever been observed in a VS Code Copilot chat - the route is built on structural evidence
  and its fixture is labelled SHAPE-VERIFIED / CONTENT-SYNTHETIC - and kiro's refusal rate
  against real usage is unmeasured. It joins L1-FIELD and KIRO-MCP-FIELD in the human lane.
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
  [cage-lab-setup.prompt.md](../work/archive/v0.36-cage-lab-setup.prompt.md) (**Opus**, both sibling
  checkouts) — create `../cage-lab` fresh per [cage-lab-plan.md](../work/archive/v0.36-cage-lab.plan.md)
  v3 + the plan's §11 (deleted 2026-08-14 — named, not cited): the M/G correctness matrix, three-way auto-verify,
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

**Update 2026-08-14 (Cowork, latest) — CLI-OUTPUT: ADR-CLI now shows what the commands
print, and the fences needed their own gate.** § *What the output looks like* carries 15
blocks — every printing view. **7 are GATED**: byte-exact bodies of goldens
`tests/test_output_spec.py` already asserts, so ADR-CLI and that test are now one artifact
with two readers. **8 are CAPTURED**: real stdout, ungated body, and each says so on the
page (**ADR-OUTPUT-GOLDENS** in the queue). **Inherit the reason a new gate existed at
all:** `test_cli_reference.py` calls `_strip_fences` before its dead-verb scan — correctly,
a diagram is an illustration — which made a fenced output block the one place in the
record where a deleted verb could live forever unchallenged. `tests/test_adr_output_blocks.py`
resolves every block's `$ cage …` line against the live parser. **That test has never been
run under pytest** (the Cowork mount has none); its assertions were executed by hand, 0
failures, but fold it into the next suite run before trusting it.

**Three defects fell out of pasting real output, and the pattern is worth more than any
of them: the doc gates read docs, never stdout.** **DOCTOR-DEAD-VERBS** — `cage doctor`
*prints* two v0.50-deleted verbs as live guidance; `verbmap` catches them when typed and
nothing catches them when printed. **DOGFOOD-SHIM-STALE** — this repo's committed
`bin/graphify` still execs the deleted verb, so **cage has not been metering its own
graphify runs since SURFACE-CUT**; the shipped template is correct, so it is stale
committed wiring, and it is a live candidate explanation for the 0-real-receipts finding
that was measured *in this repo*. Run `cage setup --wire-only` before the next audit.
**GOLDENS-ORPHANED** — 16 of 27 goldens are read by nothing and render removed surfaces,
and `test_output_spec.py`'s docstring still points at `docs/cli-output-spec.md` and
`tools/docgen`, **both gone**. Also noticed, unfixed: `work/IMPLEMENTATION.md` opens an
*Entry format* fence at line 9 that is never closed until line 570, so the entire build
log renders as one code block.


**Update 2026-08-14 (Cowork, latest) — AGENT-SHARE-BACKFILL is ACCEPTED and the ADR set
is now NINE records.** [ADR-AUTHORSHIP](../docs/adr/0009_authorship.md) was carved out of
ADR-CLAUDE and owns `authorcapture` · `linematch` · `commitjoin` · `provenance` ·
`origin*` · `notessync` · `verifycmd` (moved in the README table **and**
`tests/test_adr_ownership.py`; `transcript`/`importcmd` gained it as another claimant).
**Read its status line before you touch anything** — three decisions are ratified and
**not built**: the `COVERAGE_GAPS` strings, `coverage_note()`'s retention clause, and the
`declared` column. That is **AUTHORSHIP-CODE-CATCHUP**, and the record says out loud that
it is unbuilt so it reads as honest rather than stale. Do **not** implement `declared` by
writing a provenance row or a fourth `method` rung — the read-time quarantine is
structural on purpose. Two corrections landed alongside: ADR-CLAUDE's *"Claude is the only
agent whose store carries the text of a proposed edit"* is recorded as **CORRECTED, not
deleted**, and ADR-COVERAGE's authorship matrix row was false on four cells. **The lesson
worth carrying past this change:** ADR-COVERAGE's numbered veto on that row had *already
fired* and nobody noticed, because it was phrased as an event to await (*"a vendor exposes
edit text"*) when it was really a condition that was already true — **write a veto as a
condition to check.**

**Update 2026-08-14 (Cowork, COVERAGE-LEGEND) — the mark itself was carrying two claims,
and this is the half of the above lesson that survives longest.** ADR-COVERAGE now reads
**N/A** = *not applicable, nothing to build* (a vendor's limit, the platform's, or cage's
own refusal to fabricate) and **❌** = *not built, but could be* — the signal is in a store
cage already opens every sweep and no code reads it. Before the split, one cross meant both
*"Claude Code records no credit unit anywhere on disk"* and *"nobody has written the
copilot edit parser yet"*, and **that is how a backlog item starts reading as a law**. The
practical test when you edit a cell: *which act closes this — a probe, or a parser?* A
probe means N/A, a parser means ❌, and moving a cell between them **reassigns the gap's
owner** (vendor ⇄ cage), which is why the record's update-rule now names it explicitly.
After re-deriving all four matrices from the five code tables, **the only ❌ anywhere in the
record are the four authorship parser cells** (`AUTHORSHIP-PARSERS`) — usage capture,
graphify and operational state carry none, and being able to see that in one glance is the
whole return on the split. Two things were found while doing it: those four cells were
marked ⚠️ (*works with a stated limit*) while **nothing worked on any of them**, and the
legend still introduced ⛔ as a live mark after v0.51 had flipped every ⛔ cell to ✅. Both
are the record contradicting its own tables, caught by reading — which is **STRIKE 2**
against the parked generated matrix, filed as **COVERAGE-STRIKE-2** under *Arpit decides*
with the awkward part stated: a generator would have caught **neither** strike, because
both lived in prose and one was a wrong mark a generator would have reproduced faithfully.

**Update 2026-08-14 (Cowork) — the breadth arm of AGENT-SHARE-BACKFILL, and a defect
worth knowing before you touch `authorcapture`.** Agent-vs-human covers **claude only**
(`authorcapture.AGENT = "claude-code"`) — expected. **The recorded reason is wrong.**
`COVERAGE_GAPS` calls copilot and kiro *structural* exclusions; both stores carry edit
text, and two of them are files `importcmd` **already opens every sweep**: copilot CLI
`events.jsonl` (`tool.execution_start.arguments`, plus a required
`PermissionRequestWrite.diff`) and VS Code `chatSessions/*.jsonl`
(`IChatTextEditGroup.edits`). Kiro IDE execution logs carry `input.originalContent` *and*
`input.modifiedContent`. **ADR-CLAUDE §2's "Claude is the only agent whose store carries
the text of a proposed edit" is false as written** — filed as
**AUTHORSHIP-GAPS-MISSTATED**, text correction first and agent-closable. Two facts that
reorder the parsers: **kiro IDE has no retention policy**, so it reaches further back than
claude's ~30-day wall ever can, and **kiro writes no commit trailer and sets no git
identity**, so content matching is its only possible route. Only **copilot · cloud coding
agent** is honestly structural. Evidence with per-row confidence: `compare/agent-share-historical-backfill.compare.md` *Amendment*.

**Update 2026-08-14 (Cowork, latest) — a second item is now awaiting Arpit's verdict:
AGENT-SHARE-BACKFILL.** `authorcapture`'s first real sweep (all 104 provenance rows
stamped `2026-08-14T16:40:25Z`) covers **66 of 166 commits** and stops at **2026-07-16**
— the vendor's ~30-day transcript wall. The other 100 commits **can never be
line-matched by any future code**, and that is the permanent shape of every repo cage is
pointed at after the fact, not a backlog. Measured on the covered 66: agent share
**84.6%** of added lines, verbatim rate **85.2%** (`kept ÷ suggested`) — *above*
ADR-CLAUDE §2 reopen-trigger 2's 68.7%, so that trigger moved further from firing.
Fork, matrix and proposed verdict are in
[compare/agent-share-historical-backfill.compare.md](compare/agent-share-historical-backfill.compare.md):
**B for presence + A for the percentage** — the share stays `unknown`, and a `declared`
column is read from the commit trailer at render time and **never stored**, so no
`method="trailer"` rung exists and no arithmetic can promote a declaration into a share.
**Do not "improve" this by persisting it** — the quarantine is structural on purpose.
Inferring the share from the diff was rejected on measured evidence (best detector
out-of-domain **34.13 macro-F1 vs a 45.73 random baseline**; **39.36 F1** on hybrid
human-edited AI code, which is what a commit contains); archiving raw transcripts was
rejected on counts-never-content. Two facts worth carrying: `Co-Authored-By` reaches
**141 of 166** commits and carries a **model string** the provenance row does not, and
the **18 commits with no signal at all cluster** (9 on 2026-08-12 alone).

**Update 2026-08-14 (latest) — SURFACE-CUT is BUILT.** 14 modules, 15 handlers, MCP
6 tools → 2; the pair is archived at
[v0.50-surface-cut.handoff.md](archive/v0.50-surface-cut.handoff.md) ·
[prompt](archive/v0.50-surface-cut.prompt.md) and the reasoning is in
[surface-cut.decision.md](archive/v0.50-surface-cut.decision.md). **Read the decision record before
touching any read surface.** TASK-GRAIN-SPINE did partly close itself, as predicted — the
three affected views are gone — but the *capture-schema* half survives and is re-scoped in
OPEN-WORK.

**The single next step is Arpit's: SHIM-DEAD-VERB.** 15 tests are red and every one is the
graphify interceptor probing `cage data graphify`, a verb this change deleted. Leaving it
was Arpit's explicit decision, not an oversight, and it is safe (contract B5/B6 make an
installed shim fail its probe and pass straight through, unmetered). Closing it means
either removing the interceptor — a 9-module cascade plus both twins and ADR-GRAPHIFY §2 —
or giving it a live verb to probe. **Do not "fix" the tests instead.**

Also outstanding for Arpit: where the decision record belongs under the new per-agent ADR
structure, whether this ships as its own version, and the `CLAUDE.md` diff (proposed, not
applied). And read the six **recorded-but-unread facts** in the decision record — the cut
removed readers without removing writers, and each one is a standing choice.

**Update 2026-08-12 — historical. Nothing was in flight and there was no queue left. The
single next step is Arpit's: unjam git (`rm -f .git/index.lock`), delete the emptied
`docs/open/`, `docs/proposals/` and `_to_delete/`, run `just test`, and decide whether
SHIM-TOOL-DEPS genuinely stays closed — it is the only closure that is a live measured
defect rather than an unstarted idea.**

**The section below is the pre-closure picture and is retained as history.** Everything it
calls queued was archived unbuilt on 2026-08-12; `OPEN-WORK.md`'s closure table is the
authority on what each item left behind.

**Update 2026-08-11 — historical.**

- The agent lane has **no queued work**. The only item a future session could pick up
  unprompted is **CREDITS-LEGACY-SPLIT**, and it is blocked on a *measurement*, not a
  decision: how many multi-model copilot-CLI shutdown groups exist on a real ledger?
  Defect 2's fix is forward-only (rows are append-only; `append_new` dedupes on the
  deterministic id), so pre-2026-08-11 rows still price on two bases. **Do not rewrite
  the ledger to fix this** — get the count first, then pick between stating the limit, a
  read-side detector, and a one-off migration verb.
- Everything else left in `OPEN-WORK.md` is **Arpit's hands**: NET-1 (unblocked, n=5 per
  arm) and five field verifications that need a real machine — L1-FIELD's Copilot/Kiro
  legs, KIRO-MCP-FIELD, HR-FIELD, ADOPT-COV, GFX-KIRO-RATE.
- Tier 5 is parked **with triggers**, and the triggers are the point: GF-LAUNCHER,
  TOOL-SDK, KIRO-CLI-SCOPE, OUTPUT-GROWTH, COPILOT-SIDECAR. OUTPUT-GROWTH in particular
  reopens **only with a named size number from a real machine** — never re-argued from
  first principles.

**Update 2026-08-03 — CHATS-AUTHOR is BUILT and green (1462/0). (historical)**

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
  [../docs/adr/0008_graphify.md](../docs/adr/0008_graphify.md).
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
  attribution. [ADR 0006](archive/adr/0006-kiro-rows-are-machine-facts-not-project-facts.md) ·
  [archived pair](../work/archive/v0.36-kiro-routing.handoff.md).
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
  [archived pair](../work/archive/v0.36-human-removal.handoff.md) + CHANGELOG v0.36 *Removed*.
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
  and hashed in `work/regression/` (leg-D run report · 4 findings · a final phase
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

- **Next step:** execute [cage-lab-setup.prompt.md](../work/archive/v0.36-cage-lab-setup.prompt.md)
  (**Opus**, both sibling checkouts) — it is the only unbuilt pair in `docs/`
  root, and its prerequisites are all built and green.
- Everything else specced today is **implemented** and archived under
  `work/archive/v0.36-*` (archive-on-implement is now the rule).
- **Prices split shipped (2026-07-28):** model prices now live in `.cage/prices.toml`
  (vendor rate card), apart from `cage.toml` (your decisions incl. `[alias]`) — the
  rule is *vendor facts move, routing decisions stay*. Money verified **byte-identical**
  on the real ledger; legacy in-`cage.toml` prices still read via the fallback and
  `cage setup` migrates them money-neutrally. Resolution: `paths.Footprint.prices`.
  CLAUDE.md edits **proposed not applied** (`docs/proposals/claude-md-prices-file.md`).
  The global-vs-project *ledger* question (plan §8) is still open, ADR-level, out of
  scope — a real simplification worth its own compare doc, not a prices question.

## Standing constraints (the human's active directives — do not violate silently)

- **ARCHIVED DOCUMENTS ARE NAMED, NEVER CITED** (Arpit, 2026-08-14). Nothing under
  `work/archive/` or `docs/archive/` may back a claim — those files may have been edited,
  rewritten or overwritten since archiving, and nothing verifies otherwise. **Name** an
  archived record so the trail stays followable; **never link it as evidence.** Ground a
  claim in the code, a live ADR, `work/regression/` (measured) or `work/research/`
  (sourced) — and if nothing live grounds it, **say the claim is ungrounded** rather than
  pointing at history, because an archive link reads as checked when it is not. The one
  carve-out is narration: WORKLOG/IMPLEMENTATION/INTERVIEW record what happened. Full rule
  in CLAUDE.md *Documentation discipline*; all eight live ADRs were swept clean 2026-08-14
  and the archived-to-live map is `work/archive/adr/README.md`. **Repoint, don't delink** —
  every archived record has a live successor.

- **~~No commits in `cage`~~ — LIFTED (confirmed 2026-08-08).** This sat here as an
  *active* constraint through v0.44–v0.46.1, all of which were committed, tagged and
  released — the line was stale for four releases and a reader had no way to tell.
  Releases now follow CLAUDE.md's flow (bump + changelog → push `main` → tag →
  `gh release create`, which **is** the PyPI publish trigger). Kept as a struck-through
  line, not deleted, because the lesson is the point: **a standing constraint that the
  work has already routed around is worse than no constraint** — it makes every other
  line here less trustworthy. If a constraint stops binding, strike it the same day.
- **Session names are always captured** (no opt-in flag) — a deliberate,
  manifest-only PII widening; row stores stay counts-never-content.
- **Savings numbers must be exact: NOT WRONG, NOT DUPLICATED** — the id-deduped
  `receipts()` union is the mechanism; don't "simplify" it back to concatenation.
- **`taskcorr` stays disabled** until validated on real correlated data
  (cage-lab L5 is the gate).
- **Every session updates WORKLOG + IMPLEMENTATION, and this file when direction
  moves** — including Cowork/chat sessions where no code moved.
- **New handoff/prompt pairs are created in `work/` root, not `docs/` root**
  (2026-08-13, Arpit) — archived to `work/archive/vX.Y-<feature>.{handoff,prompt}.md`
  on implement, same as before. `docs/` root now carries no loose pairs by
  convention, same as `work/` did under the old rule.
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
  **Closed mechanically 2026-08-11** (`tests/test_doc_links.py`) — and the *policy* is the
  transferable part, not the walker. A naive gate was red on **155** links, ~140 of them
  correct history: `archive/`/`regression/`/WORKLOG/CHANGELOG entries citing pairs that
  gained a `vX.Y-` prefix **when they were archived**. Editing a dated record to keep a
  link green would falsify the record. So the corpus splits — **live fails, history is
  exempt and counted** — and the count is asserted, because a silently-shrinking corpus
  is how "we check links" becomes "we check some links and nobody remembers which".
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

- Claude (Opus 5, Cowork) — 2026-08-14 — added ADR-CLI's output section and its gate.
  **The lesson I'd want inherited: before writing the artifact you were asked for, look
  for the one that already exists.** The ask was "add CLI output examples"; the repo
  already held 27 byte-exact goldens, 11 of them still asserted every test run, orphaned
  when their doc and their regenerator were deleted out from under them. Writing fresh
  output would have produced a second, weaker source of truth beside a stronger one —
  the drift the record was built to prevent, introduced by the act of documenting.
  Second: **when you paste a program's output into a doc, you are importing its bugs at
  doc strength.** Two dead verbs in `cage doctor`'s stdout and a dead verb in this repo's
  own graphify shim were invisible until real output sat on the page next to a gate;
  abridging past a defect and filing it is honest, reproducing it silently is not.
  Third: **a gate that skips something must say what it skips.** `_strip_fences` is right
  to skip fences and wrong to be the only word on them — the fix was a second gate reading
  what the first one drops, not a relaxation of either.

- Claude (Opus 5) — 2026-08-12 (late) — executed the wholesale queue closure on Arpit's
  instruction: 16 docs archived unbuilt, `docs/open/` and `docs/proposals/` removed,
  citations migrated across CLAUDE.md, six DOC-REGISTRY rows and seven docs.
  **The lesson I'd want inherited: when the instruction is to close work rather than do
  it, the archive header is the entire deliverable.** Sixteen files moved is mechanical;
  what stops the closure from becoming amnesia is that each header says *never built* and
  names what is still unresolved — so SHIM-TOOL-DEPS reads as a reproduced hang rather
  than a tidy idea, and CONSTRAINTS.md reads as *rules archived, not lifted*. An archive
  that only says "moved" converts a decision into a silent loss. Second, and it is the
  reason I stopped and asked before moving anything: **archiving unbuilt work records a
  decision, not an outcome**, and the two need different headers — the repo's own lifecycle
  rule already said so for declined proposals, and applying it was the difference between
  an honest sweep and sixteen files pretending to be graduations. Third, dully but
  expensively: **surface an environment fault the moment you cause it.** My own
  `git status` jammed `.git/index.lock` for every process in the repo, including a
  concurrent session's; saying so immediately cost one message, and saying it at the end
  would have cost Arpit a debugging session.
- Claude (Opus 5) — 2026-08-11 (late) — emptied the queue: seven held decisions taken and
  built (1616/0 ⇒ 1639/0), tiers 2 and 3 of OPEN-WORK deleted.
  **The lesson I'd want inherited: when two fixes both work, take the one that does not
  invent a number.** REV-CREDITS defect 2 could have been closed by splitting a group
  credit pro-rata across its rows by token share — arithmetically clean, and forbidden,
  because it derives credits from tokens. The fix that shipped records a *structural
  fact* (`billed_with`) instead and lets the pricing ladder read it. Second, and it cost
  me a rewrite: **re-verify the premise of a recommendation before executing it, even
  cage's own.** The OTel research doc recommended re-pointing the pin at the GenAI repo's
  versioning; that repo has no tagged release, so the recommended option did not exist. A
  recommendation written from partial evidence is not a decision. Third, cheerfully:
  **a decision doc pays for itself at execution time.** Five of these seven were decided
  in minutes because someone had already written the options, the matrix and the reopen
  trigger — the expensive part had been done, deliberately, before it was needed.
- Claude (Opus 5) — 2026-08-11 — ran the agent-lane sweep (six phases, 1542/0 ⇒ 1616/0).
  **The lesson I'd want inherited: a spec's *defect list* deserves the same suspicion as
  a spec's *fix list*.** This handoff had already re-verified the tracker and corrected it
  in eight places — and it was still incomplete in four more, every one found by
  reproducing the defect before touching it rather than by reading. The two that would
  have cost the most are the ones that *survive the prescribed fix*: a path with a space
  stays broken after `core.quotePath=false` because git appends a disambiguating tab, and
  `claudewire`'s sixth crash site only becomes reachable **once you correctly preserve
  foreign entries** — so fixing the five listed sites moves the crash instead of closing
  it. Second: **when a fix needs a number to move, stop.** A default `--since` on
  `insights commits` is the obvious cost fix and it broke two goldens; the goldens were
  right and the fix was wrong, so it became a compare doc rather than a commit. Third,
  the cheerful one: **the display/data split is usually available.** Full shas looked
  like they had to churn every commit table, until "precision in the data, brevity in the
  display" made the whole change golden-neutral.
- Claude (Opus 5) — 2026-08-10 — built the artifact surface (`--export`/`--stamp`) and
  fixed the chats structural-empty message (1503/0 ⇒ 1541/0). **The lesson I'd want
  inherited: when a new feature collides with a law here, the answer is almost never to
  bend the law or to drop the feature — it is to find the axis the law was actually
  about.** "No clocks in derived views" is about *numbers*, not about the absence of any
  clock anywhere; once that was named, a mandatory stamp in files and a clock-free
  stdout stopped being a compromise and became the design, with a test that is stronger
  than the comment would have been. I would have reached that faster by asking what the
  law protects before asking whether the feature fits it. Second, from the chats fix:
  **an early `return` on a refusal path is where honest output goes to die.** The kiro
  routing explanation was *computed and then thrown away* three lines from where it
  would have printed — the success path had it, the empty path did not, and the empty
  path is exactly the one where a reader most needs it. Check that every refusal carries
  what its success twin carries. Third, smaller: a message can be **true and misleading
  at the same time** ("the filter is empty, not the ledger" — both clauses correct,
  the implication wrong), and that is the hardest class of wrong output to notice
  because nothing about it looks like a bug.
- Claude (Opus 5) - 2026-08-07 - built GFX-COV (graphify savings for copilot-VSCode +
  kiro-CLI, 1462/0 => 1498/0). **The lesson I'd want inherited: a spec's stated *reason* for
  a gap is a claim, and claims about someone else's on-disk format are the cheapest of all
  to falsify.** The whole pair was written around F2 - "chatSessions carries the command
  but no tool result" - and ten minutes of reading 157 real files showed the store carries
  the command, a per-command cwd, *and* the output through two carriers. The gate the pair
  imposed on itself is the only reason that surfaced before the code was written to work
  around a limit that did not exist. Second, and it cut the other way: **the same probe
  that removed one guard justified another.** I went looking for VS Code's truncation
  marker to build the handoff's guard and found that all 23 candidate hits in 1,132 parts
  were rust clippy's `cast_possible_truncation` in the command's *own* output - so the
  handoff's substring guard would have refused good receipts while catching nothing. Not
  building it was the finding. Third: **check the ADR number before you write the ADR.**
  Mine was 0009, not 0008 - and the real 0008 had already ratified *counts persisted,
  content transient*, more strictly than I was about to re-argue it. Citing it instead of
  restating it made the record shorter and stronger. Fourth, smaller: the pair's own
  documentation-impact section named two CLAUDE.md sentences as going stale; **neither
  existed in the form it claimed** (one is absent entirely, the other is about *call*
  metering and is still true). The real gap was the opposite - CLAUDE.md never stated
  graphify coverage at all, which is precisely why two-of-three could stay dark unnoticed.
  Verify a doc-impact list against the file, not against the list.
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
  never touch `work/regression/**` — and the file was sha256-sealed, so both readings
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
