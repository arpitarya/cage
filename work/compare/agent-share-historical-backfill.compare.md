---
doc: compare — what cage says about the per-commit agent share of commits line-match cannot reach
status: PROPOSED — awaiting Arpit's accept or override
raised: 2026-08-14
decides: the historical arm of agent-vs-human v2 (P1); no OPEN-WORK item exists yet
---

# AGENT-SHARE-BACKFILL — the 100 commits line-match will never see

**VERDICT PROPOSED: B, derived at read time and quarantined — plus A for the
percentage.** A `declared` presence column read straight from the commit message, in
its own column, that can never become a share. **D is rejected on measured evidence**
and carries the only interesting reopen-trigger in this doc.

**The fork:** cage's forward path already works. `authorcapture.capture` matched
**40,470 of 47,819 added lines (84.6%)** across **66 commits** on its first real sweep.
But those 66 stop dead at **2026-07-16** — the vendor's ~30-day transcript deletion
boundary, named in [ADR-CLAUDE](../../docs/adr/0003_claude.md) §1. The other **100 of
166 commits** in this repo can never be line-matched, by any future code. That is not a
backlog to work through; it is the permanent shape of every repo cage is ever pointed
at after the fact.

## What is actually true today (measured 2026-08-14, this repo)

`git log` + `.cage/ledger/provenance.jsonl`, 166 commits, 2026-06-14 → 2026-08-14:

| signal | commits | reach | what it yields |
|---|---|---|---|
| line-match (`method="transcript"`) | **66** (39.8%) | 2026-07-16 → HEAD only | a real per-commit **share** |
| `Co-Authored-By:` trailer | **141** (85.0%) | first commit → HEAD, permanent | **presence + model name**, never a share |
| trailer with **no** provenance row | **82** | the whole pre-window past | the gap this doc is about |
| neither signal | **18** | — | genuinely `unknown` |

Two things in that table move the call, and neither is in the current prose:

- **The trailer carries a model, not just a flag.** Seven distinct strings across 141
  commits — `Claude Sonnet 5` (36), `Claude Opus 5 (1M context)` (30), `Claude Opus 4.8`
  (25), `Opus 4.8 (1M)` (21), `Fable 5` (17), `Opus 5` (9), `Sonnet 4.6` (3). A
  provenance row records `agent="claude-code"` and **no model at all**. On this axis the
  weaker signal is strictly richer than the stronger one.
- **The 18 blanks are not a random 11%.** Nine are a single day (2026-08-12), three are
  `Merge pull request` commits, two are GitHub web-UI edits. The trailer fails in
  *clusters*, which is exactly the failure mode a percentage must not smooth over.

## The options

### A — leave it `unknown`

Status quo. The four-bucket split renders `unknown` for all 100, and
`summarize_authorship` reports the unknown-rate first, as it already does.

- **For:** it is already correct. *"cage can never be more precise than its source"*
  ([ADR-LAWS](../../docs/adr/0001_laws.md)) plus the never-redistribute-unknown rule in
  ADR-CLAUDE §2 make this the only answer that is defensible without new evidence. Zero
  code, zero new trust rung, zero way to be wrong.
- **Against:** 60% of this repo's history — and 100% of any repo cage meets today —
  reads as a blank, while the commit message five lines above the blank says
  `Co-Authored-By: Claude Opus 5`. That is not honest absence; that is cage declining to
  read a source that is sitting in the object it is already opening.

### B — a `declared` column, derived at read time, never stored

`commitview` reads the trailer out of the commit message it already fetches, and renders
a fourth column beside the split: `declared: claude · opus-5` / `declared: —`. **No
provenance row is written.** No `method` rung is added.

- **For:** the trailer is re-derivable from git on every read, so storing it would
  duplicate a source cage can always re-open — the one-sink law's own argument. Because
  no row exists, `agent_lines` cannot absorb it and no arithmetic can turn a declaration
  into a share; the quarantine is **structural, not a naming convention**. Coverage goes
  39.8% → 85.0% on the question *"did an agent touch this?"* and it reaches the first
  commit. It also recovers the model string, which the strong path does not carry.
- **Against:** two columns now answer adjacent questions with incomparable units, and a
  reader will average them anyway. And the trailer is a **declaration, not a
  measurement** — forgeable by hand, droppable by one setting, and provably lossy: VS
  Code stamped `Co-authored-by: Copilot` on commits **with AI features disabled** from
  1.110 (Mar 2026) until the revert in 1.119 (May 2026)
  ([The Register](https://www.theregister.com/2026/05/04/microsoft_reverses_ai_credit_grab/),
  [vscode#314311](https://github.com/microsoft/vscode/issues/314311)), and GitLab drops
  the trailer from constituent commits on squash
  ([#593408](https://gitlab.com/gitlab-org/gitlab/-/work_items/593408)).

### C — bulk retroactive human attestation

`cage authorship origin <sha> --attest` already exists and already outranks every
inference — *"an attestation always wins — it is a person's assertion about their own
time, and no inference outranks it"* (`commitview._hours`).

- **For:** highest trust in the ladder, needs no new code, and it is the **only** path
  that can ever legitimately write `human` rather than `human~`. For a commit that
  actually matters — a release, a disputed change — it is the right answer and it is one
  command.
- **Against:** it does not scale to a backlog. 100 commits is 100 acts of recall about
  work up to two months old, and a mis-remembered attestation outranks a correct
  inference *by design*. Bulk-attesting is the one way to make the ledger's most trusted
  rung its least reliable one.

### D — infer from the diff (classifier, blame shape, formatting stylometry)

Score each historical commit's added lines with a detector and derive a share.

- **The real case, not a strawman:** this is the only option that yields an actual
  *percentage* for the pre-window past, which is what was asked for. Benchmark numbers
  look decisive — CoDet-M4 reports **98.65% F1** at function level
  ([arXiv 2503.13733](https://arxiv.org/html/2503.13733v2)); *"Whitespaces Don't Lie"*
  reports **ROC-AUC 0.995** from leading-space and blank-line ratios alone
  ([arXiv 2601.19264](https://arxiv.org/html/2601.19264)).
- **Against, and this is fatal.** Every one of those numbers is in-domain and synthetic.
  Under distribution shift the best binary detector in the 2M-example AICD benchmark
  scores **34.13 macro-F1 against a 45.73 random baseline — worse than guessing**
  ([arXiv 2602.02079](https://arxiv.org/html/2602.02079v1)). On **hybrid human-edited AI
  code** — which is precisely what a git commit contains — CoDet-M4 falls to **39.36
  F1**. Five commercial detectors measured on code sit at **0.49–0.61 accuracy**, with
  GPTZero's true-negative rate at **0.0016** — it flags essentially all human code as AI
  ([arXiv 2401.03676](https://arxiv.org/abs/2401.03676)). The whitespace result was never
  run on a production repository and never tested against a formatter; this repo runs
  one. And there is a **proven lower bound** on the false-accusation rate of any
  text-only one-shot detector ([arXiv 2603.20254](https://arxiv.org/abs/2603.20254)) —
  structural, not an engineering gap.
- The metadata-only version of D fails from the other side: the 180M-repo validated
  census recovered **28,154 of 850,157 true Claude Code commits — 3.3% recall, a 30×
  undercount** ([arXiv 2606.24429](https://arxiv.org/html/2606.24429v1)).

### E — archive raw transcripts before the vendor deletes them

Copy `~/.claude/projects/**/*.jsonl` into the ledger at import so the 30-day window stops
being a wall.

- **For:** it is the only option that makes the *future* window unbounded, and it is what
  every serious external system does — git-ai stores line attribution in
  `refs/notes/ai` because the agent's own report is the only trustworthy source
  ([git-ai](https://github.com/git-ai-project/git-ai): *"does not use AI or heuristics to
  'detect' AI code — the Agents report exactly which lines they wrote"*).
- **Against:** it violates **counts-never-content** head-on — a transcript is prompts,
  responses and whole file bodies, and the law's veto is numbered in ADR-LAWS. It also
  buys nothing here: provenance rows are permanent once written, so with regular
  `cage import` the forward coverage is already complete, and `doctor`'s
  `_CLAUDE_RETENTION_NUDGE_DAYS = 25` is the existing defence against an import gap.
  **E solves a problem cage does not have, at the cost of its founding law.**

## Matrix

| | A leave unknown | **B declared column** | C bulk attest | D infer | E archive |
|---|---|---|---|---|---|
| reaches pre-window history | — | **✔ 85%** | ✔ | ✔ | ✗ |
| yields a *share*, not a flag | ✗ | ✗ | ✗ | claimed | ✔ (future only) |
| can be wrong | never | in clusters, visibly | yes, and outranks truth | 34 F1 vs 45.7 random | no |
| recovers the model | ✗ | **✔ 7 strings** | ✗ | ✗ | ✔ |
| new storage | none | **none** | rows | rows | GBs of content |
| survives a law read | ✔ | ✔ | ✔ | ✗ precision law | ✗ counts-never-content |
| cost to build | 0 | ~1 read-time helper | 0 | large | large |

## Proposed verdict

**B for presence, A for the percentage. C stays per-sha and un-bulked. D and E rejected.**

1. **The share stays `unknown` for all 100 commits.** No option here produces a
   defensible percentage for the pre-window past, and inventing one to avoid a blank is
   the exact failure ADR-LAWS' precision rule exists to prevent.
2. **`declared` is read at render time and never written.** If it is ever tempting to
   persist it as `method="trailer"`, that is the signal the quarantine has failed —
   `PROVENANCE_METHOD_TRUST` gains no fourth rung.
3. **The column prints the model string**, because it is the one fact the trailer knows
   and the ledger does not.
4. **The footer states the trailer's failure mode in cluster terms**, not as a rate:
   *"declared is the commit's own claim — 18 commits here carry none, 9 of them from one
   day"*. A footnote that says "85% coverage" would smooth over the exact non-randomness
   that makes it untrustworthy.
5. **`coverage_note()` gains the historical clause** — today it names copilot and kiro as
   structurally uncoverable, and says nothing about the 30-day wall that bounds the one
   agent it does cover.

## Reopen-trigger

- **D reopens** on a published detector reporting **≥90% precision on hybrid
  human-edited AI code, measured on production repositories** (not synthetic benchmarks),
  with the formatter question tested. The current best on that exact cell is 39.36 F1;
  nothing short of that number moves this.
- **B's read-time rule reopens** if the trailer ever needs to be joined to something git
  cannot re-derive — a signed attestation, a session id. Convenience is not a trigger.
- **E reopens** only if a vendor ships an **edits-only export with no prompt or response
  bodies**. A retention-policy change alone is not enough; the law is about content, not
  about time.
- **The whole doc reopens** if `Assisted-by:` displaces `Co-Authored-By:` in this repo's
  own commits — the kernel mandates it and Fedora/OpenTelemetry/Rocky encourage it
  ([kernel](https://docs.kernel.org/process/coding-assistants.html),
  [Fedora](https://communityblog.fedoraproject.org/council-policy-proposal-policy-on-ai-assisted-contributions/)),
  and B's parser is spelling-specific.

## Grounding

Repo measurements are from `git log` over 166 commits and the 104 rows of
`.cage/ledger/provenance.jsonl`, all stamped `2026-08-14T16:40:25Z` — the first real
`authorcapture` sweep. The 84.6% agent share is `agent_lines ÷ added lines` over the 66
covered commits, deduped per sha (rows are per `(sha, agent, session)`, up to 27 on one
commit). The 85.2% verbatim rate is `kept ÷ suggested` — above the 68.7% recorded in
ADR-CLAUDE §2's reopen-trigger 2, so that trigger is further from firing, not closer.
