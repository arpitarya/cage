# Handoff: the ADR correctness sweep — make the ten records true, then gate the class

**One-liner:** A full audit of all ten live ADRs against code at `595cb05` found **20+ factual
errors across seven records**; this handoff fixes every one and adds the gate that would have
caught the countable half, because nothing in the suite reads an ADR's *claims*.

**Owner / executor:** Claude Code
**Model tier:** **Sonnet.** Every change below is decided and has an exact change map; the
diagnosis is already done. No substrate contract, no fail-open path, no deletion with
entanglements. The one item that *would* need Opus is deliberately **out of scope** (see below).
**Status:** Ready to build — P0 gates P2 and P4.
**Rides version:** v0.51.0 (unreleased; v0.50.0 current)
**Found by:** Cowork audit session, 2026-08-14. Ten records read against HEAD; three parallel
verification passes; every finding re-confirmed against the working tree before filing.

---

## ⚠️ Read this before you touch a file

**A concurrent session was mid-flight in this repo on 2026-08-14** and had staged work across
14 files, including `docs/adr/0002_cli.md` (+444 lines), `docs/adr/0005_kiro.md`, `CLAUDE.md`,
`work/OPEN-WORK.md`, and a new `tests/test_adr_output_blocks.py`. It **ratified and reversed
KIRO-CALLS-LEG**: kiro's `calls` leg is retired like claude's and copilot's, and
`tokens_generated.jsonl` is relocated into `ledger/kiro/` as `source="ide-log"`. That work landed
as **`22072bf` — "P7: v0.51.0 — docs, changelog, glossary, registry, and the pair archived"**.

**Every finding below was re-confirmed present at `22072bf`.** That session fixed exactly one
thing in this list — ADR-CLI's dead `cage task quality` row — and expanded ADR-CLI by 444 lines
without touching a single count. The rest stand.

Still, first action, before anything else:

1. `git log --oneline -5` and `git status --porcelain`. At the time of writing, `22072bf` was in
   and a further ~77 files were staged but not committed. **Do not start on a dirty tree you did
   not make.**
2. **Re-verify every line number in the change map below.** Quoted strings are the anchors; line
   numbers are hints from a moving tree.
3. If any row's quoted string is **already gone**, that finding was fixed — drop the row, say so
   in the commit, do not re-introduce it.

---

## Phase index

| # | phase | does | gate |
|---|---|---|---|
| **P0** | the counts gate | `tests/test_adr_counts.py` — three claims re-derived from code | **RED on purpose** until P2+P4 |
| **P1** | the three agent diagrams | ADR-CLAUDE · ADR-COPILOT · ADR-KIRO, mermaid **and** ASCII twin | twins agree; no dead box |
| **P2** | ADR-CLI | seven count/date errors, six of them self-contradictions | P0 assertions 2+3 green |
| **P3** | the other five records | COVERAGE · AUTHORSHIP · CONSUMERS · GRAPHIFY · LAWS · INTEGRITY | quoted strings gone |
| **P4** | the index and the stale comments | `adr/README.md` · `CLAUDE.md` · `DOC-REGISTRY.md` · 4 code docstrings | P0 assertion 1 green |

---

## Decisions locked (do not re-litigate)

| # | decision | why |
|---|---|---|
| D1 | The ADR-CLAUDE `join_table` box is **removed, not corrected** | Arpit, 2026-08-14. It is ADR-CONSUMERS' subject matter, and it hangs off a retired writer |
| D2 | Stale **code comments** are in scope; **behaviour** is not | A comment fix needs no test run; a behaviour fix needs the suite, and this box can't run it |
| D3 | The gate lands **first and red** | Two-strikes rule. Fixing the counts without it means the third sweep finds them again |
| D4 | The gate asserts **three** things, not "all counts" | A generator over prose was already rejected once (COVERAGE-STRIKE-2). Three computable claims beat one uncomputable ambition |
| D5 | Superseded measurements are **replaced, not annotated** | `1.979×` supersedes `exactly 2×`; `85.2%` supersedes `44.3%`. Both live in `work/regression/` |

---

## P0 — the counts gate (`tests/test_adr_counts.py`)

**Write it first. It must fail on the current tree** — that failure is the proof the rest of the
work landed, and a gate written after the fix asserts nothing.

Three assertions, each re-derived from code, none reading prose:

1. **The set size.** `docs/adr/README.md`'s frontmatter word and `CLAUDE.md`'s "The set is …"
   sentence must both equal `len(sorted(Path("docs/adr").glob("0*.md")))`. Parse the spelled
   number; the records are numbered, so the count is mechanical.
2. **ADR-CLI's per-group command counts.** Every `## \`cage <group>\` — N commands` heading must
   equal the leaf count for that group in `cli.build_parser()`. Same for the top-level
   group count and the total addressable-command count in §1 and the frontmatter.
3. **The MCP tool count.** ADR-CLI's `cage mcp` row and `CLAUDE.md`'s "MCP surface = N read
   tools" must both equal `len(mcpserver.TOOLS) - len(mcpserver.WRITE_TOOLS)`.

**What it deliberately does not check:** any count whose source is prose, a measurement, or a
table cell a human maintains. `tests/test_adr_output_blocks.py` (added by the concurrent session)
covers fenced output blocks; `tests/test_cli_reference.py` covers command and flag *existence*.
This one covers *arithmetic about the parser*. Say so in the module docstring, including what is
left uncovered — a gate that implies coverage it lacks is the failure this file exists to stop.

---

## P1 — the three agent diagrams

Each fix touches **both** the mermaid block and its hand-paired ASCII twin. The house rule is
exact agreement; a fix to one only is a new defect.

### ADR-CLAUDE (`0003_claude.md`) — delete the `join_table` box

| line | current | do |
|---|---|---|
| 53 | `C --> J["ledger.join_table<br/>receipt → call lookup<br/>+ rollback path"]` | **delete the node and its edge** |
| 68 | the `+--> ledger.join_table` branch in the ASCII twin | **delete** |

Why, so it is not re-added: the box hangs off `calls-YYYY-MM.jsonl`, whose claude writer **P5
retired** (`cage/importcmd.py:593`), and `join_table` + the rollback are **ADR-CONSUMERS'**
subject matter — `cage/metering.py:81` is where the dual write's `calls` row *is* the rollback
and the lookup key. The only in-repo caller is `cage/provenance.py:12`.

In the same edit, mark the surviving `parse_calls → calls-*.jsonl` branch as **history, not a
live writer** — a reader currently sees a running second writer that does not exist.
Lines 168, 288, 358, 360 in §2 discuss `join_table` in the retirement argument and are **correct
in context** — leave them; they read as the record of a decision, not a live flow.

### ADR-COPILOT (`0004_copilot.md`) — delete the `calls row` box

| line | current | do |
|---|---|---|
| 58 | `CS --> RC["calls row<br/>+ credits verbatim"]` | delete the node; move **`+ credits verbatim`** onto the `ledger/copilot/` node |
| 74 | `VS Code chatSessions (4 roots) ---------> calls row (+ credits verbatim)` | re-point at `ledger/copilot/ metric rows` |
| 75 | `~/.copilot/session-state/events.jsonl --> calls row, as a DELTA…` | re-point at `ledger/copilot/`; keep the DELTA wording |

Both arrows into that box are dead: `cage/importcmd.py:985` — *"P5: the transcript→`calls` leg is
gone."* Credits are **still captured verbatim** and that must survive the edit — they now ride the
metric row (`cage/transcript.py:1087`, `:1151`; `schema.make_copilot_metric(credits=…)`). The
`MM -->|"chat + cli-delta ONLY"| SP` spine arrow is correct; do not touch it.

### ADR-KIRO (`0005_kiro.md`) — credits is a projection, not a sibling

| line | current | do |
|---|---|---|
| 56 | `DB --> CR["credits row<br/>workspace-scoped · measured"]` | re-parent: `DB --> KM`, then `KM --> CR`, then `CR --> V` |
| 71 | `\|-- credits row -----------> workspace-scoped, tagged MEASURED --> insights chats` | same re-parenting in the twin |

After **P2 (v0.51)** the top-level credits shard is no longer written. `ledger.credits()` now
**projects** `ledger/kiro/`'s `cli-conv` rows (`cage/ledger.py:288`) and `cage/chats.py:259` reads
that. Drawing credits as a sibling of `ledger/kiro/` says `insights chats` bypasses the per-producer
directory, which is the opposite of what v0.51 did.

Leave `KM --> NS["token spine: NONE"]` alone — `SPEND_SOURCES["kiro"] = ()` is correct and
load-bearing. Whatever the concurrent session did to the `ide-log` box is theirs; **do not revert
it**, only re-parent the credits edge.

---

## P2 — ADR-CLI (`0002_cli.md`)

The worst record in the set: seven live errors, and **six are cases where the document
contradicts itself** rather than merely lagging the code. Verified against `cli.build_parser()`.

| line | claim | truth | evidence |
|---|---|---|---|
| 441 | "**9 read tools** + exactly one write tool" | **1** read (`cage_why`) + 1 write | `cage/mcpserver.py:37-61` |
| 106 | "the **four** real subparser groups (`insights`, `task`, `authorship`, `data`)" | **six**, and `data` was deleted in v0.50 | parser top-level has no `data` |
| 320 | "`cage task` — **3 commands**" | **2** (`outcome`, `time`) — its own table lists two | `cage task quality` went with ADR 0011 |
| 341 | "`cage authorship` — **5 commands**" | **4** — its own table lists four | parser |
| 23 | "four verbs …, **five groups** hold everything else" | **six** — its own mermaid (32) and ASCII (54) both say `SIX GROUPS` | §2 line 91 also says 6 |
| 24 | "all **twenty-seven**" | **28** — its own frontmatter, line 91 and line 463 all say 28 | parser has 28 leaves |
| 553 | "removed outright in **v0.51** with the money subsystem" | **v0.50** | `CHANGELOG.md:96, 205-210` |
| 243 | `--hooks` … "auto task-close, **budget blocking**" | `hookcmd.BLOCK` is gone; every event exits 0 | its own lines 446-448 say so |
| 467 | "every line below is **checked to parse**" | it is not — `_resolvable()` never calls `parse_args` | see below |

**Line 467 is a claimed guarantee that does not hold.**
`tests/test_cli_reference.py:177-195` walks subparser dispatch only, so a missing required
positional passes. The two shipped examples that proved it — `cage study start` and `cage study
join`, which failed with *"the following arguments are required: phase"* while the doc's own
table spelled them `start PHASE` / `join PHASE` — were removed with the fleet study in v0.51
(STUDY-CUT). **The defect is untouched by that**: the gate still checks existence only, so the
next example missing a positional ships just as silently. **Narrow the sentence to what the gate
actually checks** (every command and flag *exists*). Do not promise the parse check
unless you also add it — and if you add it, that is its own phase, not a docs edit.

**Also sweep the same two bugs out of `cage/verbmap.py`** — `:127` dates the cull v0.51, and
`:132-134`'s `human` body still directs at `cage task quality`. That is the F1 class in the very
module built to prevent it: a user typing the old verb is handed a second dead verb.

---

## P3 — the other five records

### ADR-COVERAGE (`0008_coverage.md`) — this is strike 3

| line | claim | truth |
|---|---|---|
| 97 | copilot-CLI **Chat title** = `N/A honest empty` | ✅ — `transcript.session_name_copilot_cli` reads the sibling `workspace.yaml`, wired at `importcmd.py:945-958`, `name:` present on 24 of 32 real session dirs |
| 317 | "disagree by **exactly 2×** … 43,973 vs 21,955" | **1.979×** (44,659 / 22,566) — the record's own basis was superseded by the same-sweep crosscheck |
| 312 | match rate "**44.3%** repo-wide" | **85.2%** — see ADR-AUTHORSHIP below; same stale figure, two records |
| 338 | "The four **⚠️** cells above are now build order" | they are **❌** since the legend split — line 99 of the same file says so |
| 275 | "**Four ✅ cells** depend on the interceptor" | matches no reading: the interceptor rows carry six ✅ each (96, 115); the cells with no store fallback are kiro-IDE's **two** |
| 31 | the four are AUTHORSHIP-PARSERS "**in that order**" | table order ≠ build order (copilot-CLI → kiro-IDE → kiro-CLI → copilot-VSCode) |

**Finding 97 is the one that matters.** The parser landed in P3 (`24cdd40`); this record was
edited **two commits later** in P5 (`b21df95`) and the cell was not touched. It is a ✅/N-A table
cell — precisely the mechanical half COVERAGE-STRIKE-2's option (a) proposed. **Record the strike
in the record itself**, and note that a prose generator would still not have caught it: the cell
was wrong because a *belief* was stale, and a generator derived from the same belief reproduces it.

Also: lines 96 and 115 mark the three IDE interceptor cells ✅ while lines 124-129 state those
cells are **UNPROBED**. By this record's own legend ✅ means *works*, and its own invariant is
*"a gap is closed by a probe, never by an argument."* **Change them to ‡ or ⚠️ with the stated
assumption** — do not close them by writing ✅.

### ADR-AUTHORSHIP (`0009_authorship.md`)

| line | claim | do |
|---|---|---|
| 141-143 | "persists five integers **and nothing else**" | `PROVENANCE_COUNT_FIELDS` holds **six** (`schema.py:54-55`) and the sentence then names six. Fix the number — **and delete "and nothing else"**, because a row also persists `files`, a list of repo-relative **paths** (`schema.py:798`) |
| — | `files` is unmentioned in the record that owns it | **Add it.** CLAUDE.md flags it as the deliberate widening over `tasks.jsonl`'s top-level-dirs-only. This is the record's widest PII surface and it is currently invisible here |
| 102 | "Measured at **44.3%** repo-wide" | **85.2%** — its own §2 Reference (`:249`) gives `kept ÷ suggested` = 85.2%. 44.3% is the superseded 2026-08-02 dogfood figure |
| 59, 68 | both twins name `provenance.jsonl` | `ledger/provenance/provenance-<month>.jsonl` since P3c (`paths.py:1165-1170`) — the record's own Storage note at `:190` says so |
| 90 | "the model that wrote it \| the commit message's own trailer, read at render time" | sits under **What we can say** with no not-built mark, while its neighbours at 91-93 are bolded **absent**. It is AUTHORSHIP-CODE-CATCHUP item (c) and no parser exists. **Mark it not-built inline** |

### ADR-CONSUMERS (`0006_consumer.md`)

Lines 48 and 67 — the *"Where they sit"* diagram pair still shows the **pre-P1 single write**
(`L --> CA["calls-YYYY-MM.jsonl"]`). P1 dual-writes: `metering.py:64-65` appends the `calls` row
**and** `_record_consumer_twin` into `ledger/consumer/`. The record's own §1 prose two paragraphs
above (`:30-34`) already says *"Your application got one in v0.51, at `ledger/consumer/`"* — the
section titled *Where they sit* shows one of the two places it sits. Both twins agree with each
other, so this is one stale pair, not a twin mismatch.

### ADR-GRAPHIFY (`0007_graphify.md`)

| line | claim | truth |
|---|---|---|
| 345 | D4: "**three** `findstr /C:` literals" | **four** — `graphify.cmd:56` and `:71`. The B3 marker table at 231-236 already lists four |
| 295-296, 347 | B7/D6: "**either** / **both** lines that forward `%*`" | **four** since arm 2 — `graphify.cmd:98, 116, 121, 127`. The behaviour claim still holds (`setlocal DisableDelayedExpansion` at `:86` precedes all four); only the count is wrong |

### ADR-LAWS (`0001_laws.md`)

Line 116-117 — *"MCP is the only surface cage wires."* `cage setup --hooks` (L1) and `--skills`
(L3) also wire surfaces. The law's substance — **no hook writes usage** — holds; the clause
overstates. Narrow it to *"MCP is the only surface cage wires by default"* or to the substance.

### ADR-INTEGRITY (`0010_integrity.md`)

| line | claim | truth |
|---|---|---|
| 151-152 | "plus **22,751** claude metric rows" | appears in no source. The crosscheck says 22,566 `request` rows; the live-ledger figure is **22,802** — which *this same record* uses 23 lines later at `:175` |
| 136 | "O(n) per row on a hot path over a **22k+** row ledger" | its own Reference says 66,320 + ~22.8k. Understates ~4× |
| 36, 49, 106 | `BY_DESIGN` rendered as "`cursors.json`, the logs" | five entries, including `state/hooks-seen.jsonl` (a dedupe store, not a log) and `state/graphify-usage.jsonl` (`integrity.py:78-79`) |
| 101 | "A lock miss marks the **segment** `unverified`" | the flag is set on the file **entry** and is sticky forever (`integrity.py:177`); the lock is taken once around the whole loop (`:147`), so one miss taints every tracked file. **Say that** — it also makes veto trigger 3's *"1 in 100 checkpointed segments"* uncomputable at that granularity |
| 3, 175 | `status: current as of 2026-08-15` | every other record says 2026-08-14; the P6 commit is `2026-08-15T01:08+05:30` = `2026-08-14T19:38Z`. Pick one convention for the set — **UTC** — and apply it |

**Lines 17-19 and 88 assert behaviour the code does not deliver** — see *Out of scope* below.
Leave the record's text alone; the code is what is wrong.

---

## P4 — the index and the stale comments

| file | line | fix |
|---|---|---|
| `docs/adr/README.md` | 2 | "**nine** maintained records" → **ten** (it lists ten) |
| `docs/adr/README.md` | 9-11 | the "one per thing cage meters, plus …" sentence enumerates four additions; there are five (LAWS · CLI · COVERAGE · AUTHORSHIP · INTEGRITY) |
| `docs/adr/README.md` | 79-80 | the *Cite by name* list omits ADR-LAWS · ADR-CLI · ADR-CONSUMERS · ADR-INTEGRITY |
| `CLAUDE.md` | 941 | "The set is **SEVEN** records" → **TEN**, and re-word the "one per thing cage meters plus two that bind them" tail |
| `CLAUDE.md` | 1227 | "MCP surface = **5 read tools**" → **1 read tool** (`cage_why`) + one write tool |
| `work/DOC-REGISTRY.md` | ADR rows | bump every row this change touches — each record's own `update-rule` frontmatter demands it, and the v0.51 edits already missed it |
| `cage/integrity.py` | 15, 133 | "`checkpoint()` … **and by `cage doctor`**" — it is not; sole caller is `importcmd.py:1516`. The ADR is right, this comment is the stale early-draft copy |
| `cage/savings.py` | 52 | docstring says `savings/<tool>/`; the write at `:59` routes to `ledger/<tool>/` (pre-P4 wording) |
| `cage/graphifytx.py` | 617 | references `insights calibration`, deleted in v0.50 |
| `cage/mcpserver.py` | 47-48 | `cage_task_outcome`'s description names compare/estimate/calibration, all deleted |
| `cage/graphifymeter.py` | 74 | cites "the ADR 0005 veto metric" **by number** — against the cite-by-name rule |

---

## Non-negotiables

1. **A mermaid edit and its ASCII twin land in the same diff.** Every diagram fix here touches two
   blocks. One alone is a new defect of exactly the class this sweep is closing.
2. **No archived record is cited as evidence.** Name it if the trail needs it; ground the claim in
   code, a live ADR, or `work/regression/`.
3. **P0 must be red before P2 and P4, and green after.** If you write the gate green on the first
   run, it is asserting the wrong thing.
4. **Every edited record's own `update-rule` fires** — bump its `work/DOC-REGISTRY.md` row in the
   same change, and update the `status:` line where the change makes it wrong.
5. **Do not "fix" a finding by deleting the claim.** A wrong count becomes the right count; a
   wrong cell becomes the right cell with its reason. An erased sentence loses the decision.
6. **Superseded numbers are replaced and the supersession is stated** — `1.979×` and `85.2%` both
   have a dated `work/regression/` source. Cite the live one.

---

## Explicitly out of scope

- **`doctorcmd.py:1140` passes the unresolved `root` to `_integrity(root)`** while every other
  ledger check uses `paths.resolve_root` (`:1103`), and `run`'s own docstring promises the
  active sink. A project-less user's global `altered-history` is invisible to `cage doctor`.
  **Verified by execution.** This is a behaviour fix on a diagnostic path, it needs the suite and
  an ADR-INTEGRITY update, and it should not ride a documentation diff. **File it as its own
  OPEN-WORK line under ADR-INTEGRITY.**
- **A parse-check for ADR-CLI's examples.** Named in P2 as the reason the guarantee is narrowed,
  not built here.
- **AUTHORSHIP-CODE-CATCHUP's three code items.** P3 marks item (c) as not-built in the record;
  it does not build any of them.
- **Anything the concurrent session owns.** Re-verify first; if it landed the fix, drop the row.

---

## Definition of done

- [ ] `tests/test_adr_counts.py` exists, was red on the pre-fix tree, and is green.
- [ ] Every quoted string in the change map is gone from the tree, or its row is documented as
      already-fixed by the concurrent session.
- [ ] `just test` green. Re-check `tests/test_cli_reference.py`, `test_adr_ownership.py`,
      `test_adr_output_blocks.py`, `test_output_spec.py` specifically.
- [ ] Every touched record's `status:` line and `work/DOC-REGISTRY.md` row are current.
- [ ] `work/IMPLEMENTATION.md` has the outcome entry; `work/WORKLOG.md` has the session entry.
- [ ] `work/OPEN-WORK.md` carries the two carried-forward items: the `doctorcmd` integrity-root
      defect, and the ADR-CLI parse-check gap.
- [ ] This pair archived to `work/archive/v0.51-adr-correctness-sweep.{handoff,prompt}.md` with
      the one-line archive header, and linked from the CHANGELOG entry's *Built from:*.

## Open questions for Arpit

1. **COVERAGE-STRIKE-2 is now strike 3.** Its own threshold ("found stale twice") is passed and
   the remedy it names would not have caught any of the three. Option (b) — *accept that this
   record's failure mode is prose, stop counting strikes toward a generator that cannot address
   it* — is the honest close. P3 records the strike; **it does not make that call.**
2. **Does the counts gate want a fourth assertion** over ADR-COVERAGE's two ✅/N-A tables (the
   COVERAGE-STRIKE-2 option (a) half)? It is small and it *would* have caught finding 97. Left
   out of P0 because it is a different record's decision, not this sweep's.
