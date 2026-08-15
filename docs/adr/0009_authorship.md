---
adr: authorship
status: RATIFIED 2026-08-14 (Arpit) · **decisions accepted, three of them NOT YET BUILT** —
  the `COVERAGE_GAPS` strings still assert the corrected-away structural claim, `coverage_note()`
  does not name the retention wall, and the `declared` column does not exist. What IS built —
  the claude line-match path, the four buckets, the provenance buffer and notes distribution ·
  **2026-08-15 — the shape the four missing parsers should take is now specified (§2), on
  Arpit's explicit instruction to design ahead of building — still NOT built** · **2026-08-15
  — §1's flow diagram (+ ASCII twin) redrawn to a three-lane fan-in (claude built · copilot
  and kiro designed, not built) instead of one collapsed "agent stores" box**
audience: §1 humans (skim) · §2 agents (build)
update-rule: ANY change to authorship — a new agent parser, the matcher, the min-content gate, a provenance field, a rendered bucket, or a `COVERAGE_GAPS` entry — updates this doc in the same change, and bumps its DOC-REGISTRY row
---

# ADR-AUTHORSHIP — the agent is measured, the human is what is left over

> The five laws in [ADR-LAWS](0001_laws.md) bind this record already and are **not**
> restated here. Cite this record in prose as its NAME, never by number.
>
> **This record was carved out of [ADR-CLAUDE](0004_claude.md) on 2026-08-14** and is the
> reason: authorship is cross-agent, and holding its decisions inside one agent's record
> encoded the very claim this record exists to correct.

---

## §1 · For humans

**In one line:** cage measures what the **agent** wrote by matching the agent's own
proposed lines against the commit, counts only — and never measures the human at all.

> **What is built, said plainly.** The claude line-match path, the four buckets, the
> provenance buffer and the notes distribution all run today. The `declared` column
> decided below **does not exist yet**, and the two corrected gap strings are still the
> old text in code. A record that reads as shipped when it is not is the defect class this
> project has already paid for — so this line stays until the code catches up.

The one thing worth knowing: a person's share is **never observed**, only left over. It
prints as `human~` and the tilde is the point. Lines nothing proposed print as
`unattributed`, and a commit cage cannot speak to prints as `unknown` — three different
absences, never one rounded to zero.

### For the meeting

- We can say *"an agent wrote N of the M lines this commit added"* for commits inside the
  window where the agent's own record still exists. Not a guess — a **verbatim line
  match** against what the agent proposed.
- **The window is the vendor's, not ours.** Claude Code deletes its transcripts after
  ~30 days, so commits older than that can never be matched — by this code or any future
  code. Regular capture is the entire defence.
- **We never infer authorship from the code itself.** No classifier, no style detector, no
  "this looks AI-written". The measured accuracy of that whole family is at or below
  guessing on exactly the kind of code a commit contains — the numbers are in §2.
- **Today only Claude Code has a parser. That is a gap, not a law.** Copilot's and Kiro's
  stores *do* carry the text of a proposed edit; nobody has written the reader yet. The
  shape each of the four missing readers should take is specified below (§2, 2026-08-15) —
  still unbuilt.

### The flow

```mermaid
flowchart LR
    subgraph built["Built"]
        C["claude · cli + ide<br/>~/.claude/projects<br/>native line blocks"]
    end
    subgraph designed["Designed 2026-08-15, NOT built<br/>— signal exists, no reader yet"]
        CP["copilot · cli + vscode<br/>events.jsonl · chatSessions"]
        K["kiro · ide + cli<br/>globalStorage · data.sqlite3"]
    end
    C --> N
    CP --> N
    K --> N
    N["parse_edits / diff normalizer<br/>→ one shape: {file, ts, lines, context}"] --> M["linematch<br/>bodies live in memory<br/>for one import"]
    G["git · the commit's<br/>added lines"] --> M
    M --> R["provenance.jsonl<br/>five counts, no bodies,<br/>no hashes"]
    R --> V["commitview<br/>agent · human~ ·<br/>unattributed · unknown"]
    T["git · the commit message"] -.->|"read at render<br/>never stored"| V
```

<details><summary>Same diagram, ASCII</summary>

```text
  BUILT
    claude . cli+ide (~/.claude/projects, native lines)  --+
                                                             \
  DESIGNED 2026-08-15, NOT built -- signal exists              parse_edits /        linematch          provenance.jsonl
    copilot . cli+vscode (events.jsonl, chatSessions)    ---+->diff normalizer --> (bodies in   -----> (five counts,
    kiro . ide+cli (globalStorage, data.sqlite3)          --+  -> one shape:        memory for          no bodies,
                                                                {file,ts,lines,      one import)         no hashes)
                                                                 context}               ^                    |
                                                                                         |                    v
                                                                            git . the commit's          commitview
                                                                              added lines               agent | human~ |
                                                                                                      unattributed | unknown
                                                                                                                ^
                                                                                          git . the commit message
                                                                                          read at render, never stored
```
</details>

### What we can say, and how much to trust it

| number | where it comes from | trust |
|---|---|---|
| lines an agent wrote in a commit | verbatim match of the agent's proposed lines against the commit's added lines | derived by cage |
| which files an agent proposed in | the agent's own edit records | vendor-recorded |
| the model that wrote it | the commit message's own trailer, read at render time | the commit's claim, not a measurement |
| **the human's share** | — | **absent by design: never measured, only the residual** |
| **any commit older than the vendor's window** | — | **absent: the source is deleted, and no later code can recover it** |
| **copilot and kiro** | — | **absent: no parser yet — their stores do carry edit text** |

### What we can't say, and why

- **A percentage for a commit outside the window.** The agent's record is gone; nothing
  can reconstruct it. This is the vendor's retention policy, not a cage gap.
- **That a human wrote anything.** The automated path may only ever produce `human~` or
  `unattributed`. A bare `human` requires a person to assert it.
- **A clean 100%.** Repeated edits to one file depress the match rate, because only the
  final state is committed. Measured at 44.3% repo-wide. That is the honest shape.
- **Anything about copilot's cloud coding agent.** Its logs are web-only with no read API
  — the one surface here that is structurally out of reach rather than merely unbuilt.

---

## §2 · For agents

### Context

- **Authorship has two arms and they fail differently.** The *historical* arm is bounded
  by vendor retention and is closed by decision; the *breadth* arm is bounded by how many
  parsers exist and is closed by work. Conflating them produced the defect below.
- **THE DEFECT THIS RECORD CORRECTS.** `authorcapture.COVERAGE_GAPS` stated copilot
  (*"its stores record usage and prompts, not the text of an edit"*) and kiro (*"its usage
  log records token counts only, with no tool-input payload"*) as **structural**
  exclusions, and ADR-CLAUDE §2 said *"Claude is the only agent whose store carries the
  text of a proposed edit."* All three were false. Two of the contradicting stores are
  files `importcmd` **already opens every sweep** for tokens and credits.
- **[ADR-COVERAGE](0002_coverage.md)'s own numbered veto had already fired** — *"a vendor
  exposes edit text for copilot or kiro ⇒ `COVERAGE_GAPS` loses that entry"* — and nobody
  noticed, because the trigger was written as a future vendor event when the text had been
  there all along. A veto phrased as *"when they ship it"* cannot fire on *"they already did."*
- **Retention inverts the obvious priority.** Claude, the only agent with a parser, has the
  **worst** historical reach of the three (~30 days, vendor-enforced). Kiro's IDE keeps its
  execution logs with no retention policy at all. A kiro parser would reach further back
  than the claude one ever can.
- **The metadata route does not exist for every agent.** Claude Code stamps a trailer by
  default; Copilot's VS Code default flipped on in 1.117 and back off in 1.119, having
  stamped commits with AI features *disabled* for two months; **kiro writes no trailer and
  sets no git identity at all.** For kiro, content matching is the only route that can ever
  work — there is no declaration to fall back to.

### Decision

**Authorship is measured on the agent only, in counts, with the human as a labelled
residual. Where the agent's record is gone, the share stays `unknown` — it is never
inferred from the code. Where a parser is merely unbuilt, the gap says so.**

- **Counts, never content.** Authorship persists five integers and nothing else
  (`schema.PROVENANCE_COUNT_FIELDS`): `suggested`, `kept`, `kept_modified`, `dropped`,
  `agent_lines`, plus a zero-bearing `residual_lines`. **No line body, and no line hash** —
  a hash is a membership oracle over the source. Bodies exist in process memory for the
  length of one import.
- **Commit *i* owns `(ts_{i-1}, ts_i]`**, upper bound inclusive; resolution is never
  against `HEAD`. Work after the newest commit is left unrecorded this sweep and picked up
  exactly once by the next import after its commit exists.
- **`human` is never written without an attestation.** The automated path produces only
  `human~` (files the session proposed in) or `unattributed` (files it did not). Unknown is
  first-class and is **never redistributed** to make a split total 100%.
- **The pre-window past stays `unknown`.** No option produces a defensible percentage
  there; inventing one to avoid a blank is precisely what the precision principle forbids.
- **The commit trailer is read at render time and NEVER stored.** It renders as its own
  `declared` column carrying the agent and the model string. `PROVENANCE_METHOD_TRUST`
  gains **no fourth rung** — persisting it as a `trailer` method is the signal this
  quarantine has failed. The trailer is re-derivable from git on every read, so storing it
  would duplicate a source cage can always reopen.
- **The `declared` footer states the failure in cluster terms, never as a coverage rate.**
  A trailer fails in clumps, and a *"85% coverage"* footnote smooths over exactly the
  non-randomness that makes it untrustworthy.
- **A gap entry says which store and why it is unread.** *"No parser yet"* with the store
  named — never a structural claim cage has not tested. Only **copilot · cloud coding
  agent** is genuinely structural.
- **Build order for the missing parsers, by reach per unit of work**: copilot · CLI (the
  file is already open every sweep) → kiro · IDE (the largest historical prize, nothing
  deletes it) → kiro · CLI (open the SQLite read-only) → copilot · VS Code. Each lands as
  one entry leaving `COVERAGE_GAPS` and nothing else.
- **Reading diffs is a separate permission** — `[authorship] capture` / `CAGE_AUTHORSHIP`,
  distinct from `[capture] enabled`.

### Consequences

- **The agent share can only be under-counted.** Inflation would require a human to type a
  ≥4-character line byte-identical to an agent proposal, in a file that same session
  proposed in, in that same commit. The safe direction is the one it fails in.
- **Coverage of any repo cage is pointed at is a rolling window, not a backlog.** A repo
  adopted today has a permanently `unknown` past. That is a property to state on the
  surface, not a debt to work off.
- **`commitview` now renders two adjacent questions in incomparable units** — a measured
  share and a self-declared presence. Readers will try to average them; the footer exists
  to stop that, and the columns must never be summed.
- **ADR-CLAUDE keeps the claude *parser* and loses the authorship *decisions*.** A copilot
  authorship parser no longer forces an edit to the claude record — which was the concrete
  absurdity the old ownership produced.
- **This record owns `COVERAGE_GAPS`'s contents**; ADR-COVERAGE keeps the cross-cutting
  rule the five gap tables obey, exactly as its README row already says.

> **⟲ Storage note (P3c, v0.51) — the authorship buffer is month-partitioned.**
> `ledger/provenance.jsonl` became `ledger/provenance/provenance-<month>.jsonl`, chosen
> from each **row's own `ts`** (never a write-time clock — authorship capture is routinely
> backdated, since it attributes commits rather than the present). This **reverses**
> `paths.shard()`'s explicit *"`provenance` is intentionally never partitioned (buffer)"*
> and PLAN §3.6.1's matching exemption; both record the reversal rather than dropping the
> sentence. The premise was right and the conclusion did not follow: **nothing flushes the
> buffer**, so it grew without bound and every read scanned it end to end.
>
> **Nothing about the record itself changed** — same schema, same enums, same
> counts-never-content guarantee, same CI-sole-writer distribution to
> `refs/notes/cage-provenance`, and `cage authorship verify` still always exits 0. The
> legacy file is **read forever and never rewritten**: frozen rows are never backfilled,
> which `residual_lines`' absent-vs-recorded-`0` version gate for `agent%` depends on.
>
> **All five readers span shards**, and they were enumerated rather than assumed:
> `ledger.provenance` · `originrecord.read_all`/`for_sha` · `chats.py`'s `agent%` ·
> `doctorbundle` (which reads the path **directly** and would have under-reported in a
> diagnostic bundle) · `notessync` (which merges by row id, so a partial read re-pushes or
> silently drops rows in the canonical note). A missed shard here does not raise or warn —
> **`agent%` reads counts rather than re-deriving them, so it surfaces as a different
> percentage**, which is why each reader has its own test.

> **⟲ Parser design (2026-08-15, ratified — NOT built) — the shape the four missing
> readers should take.** The build order (copilot · CLI → kiro · IDE → kiro · CLI →
> copilot · VS Code) was already decided; this fixes *how* each one works, so a future
> session builds against a design rather than inventing one per parser.
>
> **The pipeline downstream of the parser is unchanged.** `authorcapture._bucket_edits`/
> `_uncovered`, `linematch.match_commit` and `originrecord.record_transcript` already
> consume one shape — `{session, file, ts, cwd, lines, context}`, exactly what
> `transcript.parse_edits` produces — and know nothing about claude specifically. A new
> source is a new function returning that same shape; `authorcapture.py`'s hard-coded
> `AGENT = "claude-code"` becomes a short `(agent, source_fn)` list, one entry per store,
> each removing itself from `COVERAGE_GAPS` on landing.
>
> **Two shapes of source data, one normalizer.** Claude's `Edit`/`MultiEdit` blocks
> already carry `new_string`/`old_string` as native line lists — today's `lines`/
> `context` read straight off them (`_proposed_lines`/`_context_lines`). None of the
> four missing stores work that way: kiro IDE's `actions[type=replace]`
> (`input.originalContent` → `input.modifiedContent`), kiro CLI's `fs_write`
> (`file_text` for a whole-file write, or `old_str`→`new_str` for a patch) and copilot
> VS Code's `chatEditingSessions` blob pair (`contents/<originalHash>` →
> `contents/<currentHash>`) are all **whole-file or whole-block before/after pairs**,
> with no native "lines proposed" list. Their `lines`/`context` are derived by a line
> diff (`difflib`) computed **transiently, inside the parser, and discarded the moment
> counts are produced** — one shared normalizer, not one per parser, on the same
> "normalization is ONE function applied to both sides" rule `linematch.normalize`
> already states for matching. Copilot CLI is the open question: whether it needs this
> normalizer or already carries a native line list is undecided until the first live
> capture of its write-tool event (still unconfirmed — see Reference).
>
> **Copilot CLI** — a sibling reader to `graphifytx.detect_and_file_copilot`, same store
> (`~/.copilot/session-state/<id>/events.jsonl`), same mechanics: `tool.execution_start`/
> `tool.execution_complete` paired by `data.toolCallId`, cwd from `session.start`'s
> `data.context.cwd` — field names verified live on Copilot CLI 1.0.65 for the `bash`
> tool, reused here filtered on the write tool instead. `ts` is the event's own
> timestamp, never import time, matching the rule `parse_edits` already states for
> placing an edit inside a commit's window.
>
> **Kiro IDE** — scan `globalStorage/kiro.kiroagent/**/*` for JSON containing
> `"executionId"`; never hard-code the hex directory names, which are per-install. Read
> `actions[]` where `actionType=="replace"`, diff `input.originalContent` →
> `input.modifiedContent`. No retention policy is the reach prize and the risk in the
> same fact — real installs report 8.2–38GB of accumulation — so the reader must stream
> one action at a time and discard each body immediately after diffing, never buffer a
> directory's contents, and needs its own cursor entry keyed **per blob file**
> (mirroring `_authorship`'s `[size, mtime, covered]` shape), not per top-level hex
> directory, since the files inside those directories are what change.
>
> **Kiro CLI** — a sibling to `transcript._kiro_cli_tool_runs`, **not a reuse of it**:
> the same read-only `sqlite3.connect(...mode=ro&immutable=1...)` access and the same
> `_under(key, workspace)` cwd-tree scoping `parse_kiro_cli_credits`/
> `parse_kiro_cli_tool_runs` already establish against `conversations_v2`, but filtered
> on `fs_write`-shaped `ToolUse` entries instead of `execute_bash` ones, reading
> `path`/`file_text` (a whole-file write) or `old_str`/`new_str` (a patch) into the same
> diff normalizer as kiro IDE. The store is already open every sweep for credits; this
> read is additive, not a new connection.
>
> **Copilot VS Code** — read `chatSessions/*.jsonl`'s `IChatTextEditGroup.edits` /
> `toolInvocationSerialized.toolSpecificData.rawInput` for the per-turn signal, but the
> before/after bodies live in `chatEditingSessions/state.json` →
> `contents/<originalHash|currentHash>`, and that store **self-deletes on
> `clearState()` at session stop**. This is the one surface where the existing cursor
> strategy — leave a file "uncovered" until its edits land in a commit, re-read next
> sweep — does not hold: by the time a commit lands, the source may already be gone.
> Correctness here depends on capture cadence, not just on the parser existing, which is
> why this item already pairs with **CONTINUOUS-CAPTURE** (`work/OPEN-WORK.md`,
> ADR-CLI). A parser that is technically correct but reads too late silently
> under-counts the same way an unmatched commit does today, with no signal it happened.
>
> **What this does not change.** `[authorship] capture` / `CAGE_AUTHORSHIP` gates all
> four readers identically to the claude one — reading a diff is reading code, the same
> permission question regardless of which store holds it. The matcher, the min-content
> gate, the four buckets, the counts and the fail-open discipline are untouched; only the
> parser layer grows.

### Alternatives rejected

- **Infer the share from the diff** (classifier, blame shape, whitespace stylometry). The
  benchmark numbers are decisive and irrelevant: 98.65% F1 in-domain, ROC-AUC 0.995 from
  leading-space and blank-line ratios. Out-of-domain the best binary detector scores
  **34.13 macro-F1 against a 45.73 random baseline — worse than guessing**, and **39.36 F1
  on hybrid human-edited AI code**, which is exactly what a commit contains. Five
  commercial detectors on code sit at 0.49–0.61 accuracy, one with a true-negative rate of
  0.0016. There is a proven lower bound on the false-accusation rate of any one-shot text
  detector. **Lost on measurement, not on taste.**
- **Infer from metadata alone** (bot accounts, trailers, config-file presence). A validated
  180M-repo census recovered 28,154 of 850,157 true agent commits — **3.3% recall, a 30×
  undercount**. High precision, unusable recall.
- **Archive raw transcripts** so the vendor's window stops being a wall. Violates
  counts-never-content — a transcript is prompts, responses and whole file bodies — and
  buys nothing cage lacks: provenance rows are permanent once written, so forward coverage
  is already complete with regular capture.
- **Bulk retroactive attestation** of the unmatched past. An attestation outranks every
  inference *by design*, so bulk-attesting months-old recall makes the most trusted rung
  the least reliable. Attestation stays per-sha and deliberate.
- **Persist the trailer as a fourth `method` rung.** It would place a *declaration* on the
  same ladder as a *measurement*, where one arithmetic slip promotes it into a share. The
  read-time rule makes the quarantine structural rather than a naming convention.
- **A `declared` coverage percentage in the footer.** Rejected because the signal fails in
  clusters; a rate implies the failures are spread.

### Reference

Measured on this repo 2026-08-14 — 166 commits, 2026-06-14 → 2026-08-14, from `git log`
and the 104 rows of the provenance buffer, all stamped `2026-08-14T16:40:25Z`
(the first real `authorcapture` sweep):

| finding | number |
|---|---|
| commits line-matched | **66 of 166** (39.8%) |
| oldest matched commit | **2026-07-16** — the vendor's ~30-day wall, not a code limit |
| agent share of added lines, on those 66 | **40,470 / 47,819 = 84.6%** |
| verbatim rate, `kept ÷ suggested` | **85.2%** — *above* ADR-CLAUDE's 68.7% matcher trigger |
| commits carrying a `Co-Authored-By` trailer | **141 of 166** (85.0%), back to the first commit |
| distinct model strings in those trailers | **7** — a provenance row records no model at all |
| commits with neither signal | **18**, of which **9 fall on one day** — the cluster finding |

Two counting traps, recorded because both were hit while producing the table above:
provenance rows are per `(sha, agent, session)` and reach **27 rows on one commit**, so
summing `lines_added` across rows triple-counts a commit's diff — dedupe per sha. And the
added-line denominator includes generated files; a share quoted without naming its
denominator is not reproducible.

Store evidence for the breadth arm, with its confidence stated per row rather than
averaged, is in `work/compare/agent-share-historical-backfill.compare.md` *Amendment*:
VS Code's before/after blob store confirmed at source; copilot CLI confirmed from the
schema shipped in its own package but **not yet from a live file**; kiro from two
independent third-party parsers, never from AWS.

The 2026-08-15 parser design grounds each store's read mechanics in code already
shipped for a different question, not invented fresh: `graphifytx.
detect_and_file_copilot` (copilot CLI's `tool.execution_start`/`_complete` pairing by
`toolCallId`, verified against a live Copilot CLI 1.0.65 store) and `transcript.
_kiro_cli_tool_runs`/`parse_kiro_cli_credits` (kiro CLI's read-only `conversations_v2`
access and `_under`-based cwd-tree scoping, ratified as the tool-run carve-out) are the
existing precedent for *how to read the store*; only the tool-call filter and the
extracted fields differ for authorship. An external pass the same day (git-ai's
`git_ai_standard_v3.0.0` spec, `refs/notes/ai`) independently converged on the same
substrate choice (git notes, per-commit truth) while storing line *ranges* rather than
cage's counts-only shape — one rung less conservative than this record's own
counts-never-content law permits.

### Veto condition (when to revisit)

**1 — Falsifiable triggers, numbered, each landing somewhere named.**

1. **Inferring the share from the diff** reopens on a published detector reporting **≥90%
   precision on hybrid human-edited AI code, measured on production repositories** with the
   formatter question tested. The current best on that exact cell is 39.36 F1. A benchmark
   score on synthetic data does not move this, and neither does an argument.
2. **The `declared` read-time rule** reopens only if the trailer must join to something git
   cannot re-derive — a signed attestation, a session id. Convenience is not a trigger.
3. **Archiving transcripts** reopens only if a vendor ships an **edits-only export with no
   prompt or response bodies**. A retention-policy change alone is not enough: the law is
   about content, not about time.
4. **The build order** reopens if Claude Code's `cleanupPeriodDays` default rises above
   **90 days** — the retention inversion is the entire argument for placing kiro second.
5. **The trailer parser** reopens if `Assisted-by:` displaces `Co-Authored-By:` in this
   repo's own commits; the parser is spelling-specific and the kernel already mandates the
   other spelling. Trigger: any commit here carrying the new spelling.
6. **A gap entry returns to structural** only with a probe cited. It never reverts to an
   unsourced claim — the failure this record was written to correct.
7. **The diff-to-edit normalizer** (kiro IDE, kiro CLI, copilot VS Code) reopens only if
   a vendor is confirmed to expose a native line-list block instead of a whole-file
   before/after pair — that source then skips the normalizer entirely, exactly as claude
   does today. A store must be read live to fire this; an argument does not.
8. **Copilot CLI's parser shape** (native lines vs. the shared diff normalizer) stays
   undecided until the first live capture of `events.jsonl`'s write-tool event — still
   unconfirmed per this record's own Reference section, and unchanged by the 2026-08-15
   external research pass. Reopens on that one capture, not before.

**2 — Contingent vs. invariant.**

- **Contingent (auto-revisits on evidence):** every `COVERAGE_GAPS` entry; the build
  order; the matcher and its `MIN_MATCH_CHARS` gate (both still triggered from ADR-CLAUDE,
  and both landing in `linematch.match_file` alone); the diff-to-edit normalizer's
  applicability per store; copilot CLI's exact parser shape (trigger 8).
- **Invariant (moves only by ratified reversal of this record):** the human is never
  measured, only residual · unknown is never redistributed · no line body and no line hash
  is ever persisted · a declaration is never placed on the measurement ladder.

**3 — Deliberately not taken.**

- **A `declared` column for agents other than claude**, though the data supports it today.
  Copilot's trailer default moved twice in three releases and false-positived for two
  months; rendering it now would bank a signal whose meaning is still moving. Threshold:
  two consecutive VS Code releases with a stable default.
- **Signing the provenance note** (`git notes --ref` + GPG) before treating it as
  audit-grade, already flagged in `notessync`. Threshold: the first time a note crosses a
  trust boundary — a second machine, or CI consuming it as evidence rather than as a view.
- **Recomputing ADR-COVERAGE's matrix from the code tables.** Nothing does, so drift
  between that record and `COVERAGE_GAPS` is caught by review alone. That was how the
  defect above survived; naming it here is the interim mitigation, not a fix.
- **A per-store `AUTHORSHIP_PARSERS` registry object, built now.** One live source
  (claude) plus a hard-coded second does not yet prove the right abstraction boundary —
  the same reasoning ADR-GRAPHIFY gives for its own hand-paired twin pair ("templating
  stays off the table until a third interceptor exists and shares a syntax family with
  an existing one"). Decide the registry shape when copilot · CLI, the second source,
  actually lands — not before. Threshold: two live sources.
