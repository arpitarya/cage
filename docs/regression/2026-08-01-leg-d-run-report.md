# Run report — leg D, the manual VS Code / IDE cells — 2026-08-01

**Immutable.** One run, one report. The numbers below are the lab ledgers as captured;
the sidecar hash pins them. Findings and the phase benchmark are separate artifacts and
are never merged into this file. No later status is recorded here — a defect's current
status lives in its finding doc.

**Artifact type:** run report (leg D of Phase I). Scope: cells **D1–D6**, driven by hand
in VS Code / Kiro. Complements — does not replace — the scripted-leg
[2026-07-29 run report](2026-07-29-run-report.md), which covered the two CLI cells.

---

## Headline

**Same workspace, same six questions, same graphify install — claude invoked graphify
unprompted (2 queries, 18,456 tokens saved, captured via the *transcript* route);
copilot and kiro did not invoke it at all.**

- **Adoption is agent-specific**, and cage **measured** it rather than assuming it: the
  usage log distinguishes *"never ran"* from *"ran but cage missed it"*. copilot and kiro
  produced **zero usage rows**, so the answer is "never ran" — not a capture gap.
- Token capture itself passed in every cell that has a source capable of being checked:
  claude exact to the token, copilot exact, kiro within its own credit-derived limit.
- **Two limits belong to the sources, not to cage:** claude's CLI and VS Code share one
  store (so `surface` is unknowable), and kiro's log carries no time, session or project
  (so **the kiro A/B is not reconstructible from the ledger** — no kiro ON/OFF delta may
  ever be reported).
- **One real code bug found:** `cage import --agent copilot --path` can never reach the
  VS Code chat store (hardcoded CLI glob).
- **And the counterweight, which belongs in the same breath as the headline:** the same
  paired arms show the **graphify-ON session cost more than the OFF session** (+31% by the
  per-session est cost) while cage printed a saving. `saved` is a **gross** per-query
  counterfactual — it excludes the cost of *using* the tool. **n = 1: UNPROVEN, a signal,
  not a measurement.** See *[the paired D1↔D2 observation](#the-paired-d1d2-observation--the-on-arm-cost-more)*
  below and [the finding](2026-08-01-finding-saved-is-gross.md).

---

## Provenance

| | |
|---|---|
| Driven | by hand, 2026-08-01, 10:33–11:31 IST (05:03–06:01 UTC) |
| cage | **0.36.0**, installed `-e ../cage` from local source — a **declared deviation** from cage-lab's black-box rule (a release is pending; recorded in `cage-lab/SETUP.md`) |
| graphifyy | **0.9.30**, pinned PyPI wheel |
| python (lab `.venv`) | 3.14.2 |
| capture-on-read | `on_read = false` in both workspace policies — every row in this report came from an **explicit** `cage import`, never an implicit read-time sweep |
| ledgers | per-workspace: `cage-lab/workspace-off/.cage/` and `cage-lab/workspace-on/.cage/` — imports scoped per workspace |
| evidence | the cell records written live during the run: `cage-lab/reports/cells/D{1..6}-*.md`, plus the operator's `FINDING-gross-vs-net-savings.md` filed from the paired arms |

### Launch method + pre-flight PATH (per D.0 — without these a VS Code cell is not evidence)

| cell | agent surface | launch method | pre-flight `command -v graphify` |
|---|---|---|---|
| D1 | claude · VS Code extension | `source .venv/bin/activate && code workspace-off` (activated shell) | `cage-lab/.venv/bin/graphify` — the **real binary, no interceptor** (correct for the OFF arm) |
| D2 | claude · VS Code extension | activated shell, `workspace-on` | interceptor present in `workspace-on/bin`, but **not on the extension subprocess PATH** — see D2 |
| D3–D4 | copilot · VS Code extension | VS Code chat, `workspace-off` / `workspace-on` | n/a for capture; graphify never invoked (D4) |
| D5–D6 | kiro · IDE | Kiro IDE, `workspace-off` / `workspace-on` | n/a for capture; graphify never invoked (D6) |

Cited: `D1-claude-vscode-off.md` (Provenance), `D2-claude-vscode-on.md` (Why this matters).

---

## Cells at a glance

| cell | agent · surface · graphify | verdict | rows | headline number |
|---|---|---|---|---|
| **D1** | claude · VS Code · OFF | **PASS** (1 HONEST-LIMIT: `surface`) | 30 calls | 1,288,664 in / 8,000 out — **exact** vs source log |
| **D2** | claude · VS Code · ON | **PASS** — the leg's most important cell | 41 calls · 2 receipts | **18,456 tokens saved**, both via `route: transcript` |
| **D3** | copilot · VS Code · OFF | **PASS** (2 HONEST-LIMITs, both copilot's) | 5 calls | `surface = vscode` ✅ · `copilot/auto` ⇒ UNPRICED |
| **D4** | copilot · VS Code · ON | **PASS (capture)** · graphify did **not** fire | 4 calls · 0 receipts | receipts 3 → 3, usage rows 3 → 3 (unchanged) |
| **D5** | kiro · IDE · OFF | **HONEST-LIMIT** — deeper than documented | 22 rows | no `ts`, no `session`, no `project` |
| **D6** | kiro · IDE · ON | **capture PASS** (within kiro's limits) · graphify did **not** fire | 28 rows | receipts 3 → 3, usage rows 3 → 3 (unchanged) |

---

## D1 — claude · VS Code · graphify OFF · **PASS**

- Session `49e6b647-4698-4183-bb52-28f6107cc959` · 30 calls · `claude-haiku-4-5-20251001`
  · 05:03:30–05:05:44 UTC.
- **Three-way reconcile exact:** source log 30 rows / 1,288,664 in / 8,000 out = ledger
  30 rows / 1,288,664 in / 8,000 out (cached 1,206,526).
- `project = workspace-off` on **every** row. Import row: `unpriced_rows = 0`,
  est $0.242783.
- Re-import idempotent: second import = **0 calls, 0 files**.
- Excluded from the cell: an earlier 10-call probe session
  `4e92b04f-f83e-449b-955d-33bb241df4cc` (341,143 in / 4,062 out, 05:00:45–05:01:04 UTC,
  ~19 s) that predates D1. It is present in the workspace-off ledger and is **not**
  counted as D1 data.
- **HONEST-LIMIT — `surface` is empty, not `vscode`.** Claude Code's CLI and VS Code
  extension write the **same store** with no distinguishing marker, so cage cannot know
  which surface produced a row. Not a defect and not fixable on cage's side. **What does
  work:** `project` is correct on every row, so **per-workspace attribution holds where
  per-surface does not.**

Cited: `D1-claude-vscode-off.md`; `workspace-off/.cage/ledger/calls-2026-08.jsonl`,
`ledger/imports.jsonl`.

## D2 — claude · VS Code · graphify ON · **PASS** (the leg's most important cell)

Session `cf3d26d7-2d95-4094-a318-cd78e5e27630` · 41 calls · 1,667,521 in / 14,204 out
(cached 1,577,032) · 05:15:23–05:17:00 UTC · `unpriced_rows = 0`, est $0.319212.

**The three answers, recorded separately (never collapsed):**

| question | answer |
|---|---|
| (a) did the hook / steering fire? | **yes** — the agent ran `graphify query` **twice**, unprompted |
| (b) did graphify actually run a query? | **yes** — 2 queries, distinct `args_hash` (`758ed490…`, `05e0266f…`) |
| (c) did cage see it? | **yes** — 2 receipts + 2 usage rows, both `route: transcript` |

| receipt | ts (UTC) | raw_alt | actual | saved | route |
|---|---|---|---|---|---|
| `s_fd2ed1b6…` | 03:37:53 | 10,784 | 1,582 | 9,202 | shim — **setup, pre-D2** (not D2 data) |
| `s_e7403cea…` | 05:17:23 | 10,784 | 1,556 | **9,228** | transcript |
| `s_7c4c3646…` | 05:17:23 | 10,784 | 1,556 | **9,228** | transcript |

- **D2 = 18,456 tokens saved** (27,658 in the ledger − 9,202 from setup). `modeled`,
  confidence 0.6. **This is a *gross* figure** — read it alongside
  [the paired D1↔D2 observation](#the-paired-d1d2-observation--the-on-arm-cost-more), where
  the same session's est cost is +31% over the OFF arm.
- **Two receipts, not one, is correct.** The queries carry different `args_hash` values —
  distinct queries that happened to produce identically-sized answers (both truncated at
  the same ~2,000-token budget). Dedupe did **not** collapse them.
- **The transcript route is what made the savings visible.** The VS Code extension's
  subprocess did not carry `workspace-on/bin` on PATH, so the interceptor shim never ran —
  exactly what §B predicted. With only the PATH shim, **both savings would have been
  invisible.** This is the live vindication of the transcript route (GC2) for VS Code.
- **Route blind spots are complementary** (product observation, not a defect in this
  cell): the shim receipt carries `task = workspace-on` but an empty `session`; the
  transcript receipts carry the real `session` but an empty `task`. **Neither route
  carries both**, which limits joins across routes.
- `saved $` renders `—` / UNPRICED: a call-less token receipt with no priced model in the
  ladder. Loud, not silent — the intended behaviour.
- usage rows ≥ receipts: **3 = 3**. Same `surface` HONEST-LIMIT as D1.

Cited: `D2-claude-vscode-on.md`;
`workspace-on/.cage/ledger/savings/graphify/savings-2026-08.jsonl`,
`state/graphify-usage.jsonl`.

## D3 — copilot · VS Code · graphify OFF · **PASS** (2 HONEST-LIMITs, both copilot's)

Session `2608807a-aae0-42ff-8c81-9ab2ed7d2453` · 5 calls · 158,125 in / 1,254 out ·
05:20:43–05:21:27 UTC.

| observation | verdict |
|---|---|
| `surface = vscode` | ✅ **the check claude cannot pass** — copilot's CLI and VS Code stores are genuinely separate |
| model `copilot/auto` | **HONEST-LIMIT** — a router alias ⇒ `unpriced_rows = 5`. Refusing to price a model it cannot resolve is **correct behaviour**, not a defect |
| `cached_in = 0` on every row | **HONEST-LIMIT** — copilot's VS Code store does not report cache reads |

**Per-surface attribution works for one of the three agents.**

**⚠️ Product bug found here** — `cage import --agent copilot --path` cannot reach the
VS Code store; the `--path` branch hardcodes the CLI glob `*/events.jsonl`
([`importcmd.py:477`](../../cage/importcmd.py#L477)), while claude's equivalent uses
`**/*.jsonl` ([`importcmd.py:312`](../../cage/importcmd.py#L312)). Full write-up:
[finding — copilot `--path` glob](2026-08-01-finding-copilot-path-glob.md).

**Workaround used** (and the correct mechanism): a `[sources.copilot]` override in the
workspace `cage.toml` with `replace = true`, an explicit `paths = [ … workspaceStorage/<id> ]`,
`glob = "chatSessions/*.jsonl"` and `surface = "vscode"`.

**⚠️ UNVERIFIED — prompt count not recorded.** 5 rows against a 7-turn script. This report
**does not** conclude that copilot logs per request, and **does not** conclude that turns
went missing. The prompt count was not written down at run time; it is an **open question
for the next run**, not a result.

Cited: `D3-copilot-vscode-off.md`; `workspace-off/.cage/ledger/imports.jsonl`.

## D4 — copilot · VS Code · graphify ON · **PASS (capture)** · graphify did **not** fire

Session `8b40eed0-2131-4050-ae17-d5123821828e` · 4 calls · 139,302 in / 1,690 out ·
05:32:02–05:32:44 UTC · `surface = vscode` · `copilot/auto` ⇒ `unpriced_rows = 4`.

| | before D4 | after D4 |
|---|---|---|
| graphify receipts | 3 | **3** |
| graphify usage rows | 3 | **3** |

**No usage row, no receipt — graphify was never invoked.** This is an **adoption**
finding, not a capture limit.

**F2's predicted limit was never exercised.** The prediction was a *usage row without a
receipt* (copilot's VS Code log carries the tool command but not the result, so no
counterfactual can be sized). That never happened, because copilot never ran graphify at
all. **F2's copilot-vscode limit therefore remains untested — it was not confirmed by
this run**, and the benchmark says so.

**⚠️ UNVERIFIED — prompt count not recorded** (4 rows against a 7-turn script). Same open
question as D3.

Cited: `D4-copilot-vscode-on.md`; `workspace-on/.cage/ledger/imports.jsonl`.

## D5 — kiro · IDE · graphify OFF · **HONEST-LIMIT** (deeper than the plan documented)

22 kiro rows in the `workspace-off` ledger · 887 tokens in · 0 out · imported 05:56:04 UTC.
Approximately 6 belong to D5; **the rest predate the lab and cannot be separated.**

| field | value | consequence |
|---|---|---|
| `ts` | **identical on all 22 rows** (`2026-08-01T05:56:04Z`) — stamped at *import* time | no ordering, no windowing, no per-cell separation |
| `session` | `"kiro"` — a synthetic constant | no session attribution |
| `project` | absent | no workspace attribution |
| `model` | `"agent"` — synthetic | fails check 4, **on kiro's side** |
| `tokens_out` | 0 | input-only log |

- **The limit is bigger than "estimated tokens."** The plan recorded kiro's limit as
  *credit-derived `estimated` input, `tokens_out = 0`*. True but incomplete: kiro rows
  carry **no time, no session and no project**, which removes them from every per-cell,
  per-arm and per-question analysis cage performs.
- **Therefore the kiro A/B cannot be reconstructed from the ledger.** Not "hard to
  separate" — D5 and D6 rows are *literally indistinguishable*. Only the operator's notes
  record that two arms happened. **A kiro ON/OFF delta would be a fabrication.**
- The rising token progression across the rows (13 → 182) is **consistent with** one
  accumulating conversation — but that is an inference from the numbers, **not** something
  the log states.
- **The cell's one clean pass:** re-import idempotent — **0 calls, 0 files**. Despite the
  read-time `ts`, kiro row ids are content-derived and stable; the volatile timestamp does
  **not** duplicate on re-import.
- Surface `ide` correct. Pricing: `unpriced_rows = 0`; the import row totals est
  $0.002661 — i.e. **$0.00 at display precision**, no invented cost.

Cited: `D5-kiro-ide-off.md`. Full write-up:
[finding — kiro rows carry no time/session/project](2026-08-01-finding-kiro-rows-carry-no-time-session-project.md).

## D6 — kiro · IDE · graphify ON · **capture PASS** (within kiro's limits) · graphify did **not** fire

28 kiro rows in the `workspace-on` ledger · 1,576 tokens in · 0 out · imported
06:01:04 UTC · `unpriced_rows = 0`, est $0.004728.

| | before D6 | after D6 |
|---|---|---|
| graphify receipts | 3 | **3** |
| graphify usage rows | 3 | **3** |

- **No usage row, no receipt — kiro never invoked graphify**, despite
  `graphify kiro install` having written `.kiro/skills/graphify/` + steering into this
  workspace. Adoption, not capture.
- **The ~6 rows attributed to D6 are an operator observation, not a ledger fact** — they
  are the count difference between the 05:56 and 06:01 imports. The ledger itself cannot
  separate them.
- **⚠️ Kiro rows double-count across ledgers.** `workspace-off` holds 22 kiro rows,
  `workspace-on` 28 — and **22 of the 28 are the same turns**, because kiro's single
  global log is re-read by every ledger that imports it. Within a ledger dedupe is correct
  (re-import = 0 new). **The two lab ledgers must never be summed for kiro.** Full
  write-up:
  [finding — kiro double-count across ledgers](2026-08-01-finding-kiro-rows-double-count-across-ledgers.md).

Cited: `D6-kiro-ide-on.md`; `workspace-on/.cage/ledger/imports.jsonl`.

---

## The paired D1↔D2 observation — the ON arm cost more

D1 and D2 are the only true paired arms in this leg: same agent, same surface, same
workspace fixture, same six questions, same model — **graphify the only variable.** Both
sets of rows are this run's own data, so the comparison belongs in this report.

| | D1 OFF | D2 ON | delta |
|---|---|---|---|
| calls | 30 | 41 | **+11 (+37%)** |
| tokens in | 1,288,664 | 1,667,521 | **+378,857 (+29%)** |
| — cached read | 1,206,526 | 1,577,032 | +370,506 |
| — cache write | 81,872 | 90,119 | +8,247 |
| — fresh input | 266 | 370 | +104 |
| tokens out | 8,000 | 14,204 | **+6,204 (+78%)** |
| est. cost (per-session `imports.jsonl` row) | **$0.242783** | **$0.319212** | **+$0.076429 (+31%)** |

**Cage recorded 18,456 tokens saved for D2. Both figures are true** — they measure
different things. `saved` is a **per-query counterfactual** (*the files this answer cites
would have cost 10,784 tokens; the answer cost 1,556*); it does **not** subtract the cost
of **using** graphify: the query turn, the tool round-trip, the hook's injected context,
or a re-read provoked by a truncated answer.

**Verdict: UNPROVEN — a signal, not a measurement.**

- **n = 1.** The manual cells ran once each; the repeats = 3 rule exists for exactly this
  comparison. This report does **not** conclude that graphify made the session more
  expensive.
- ~95% of the input is cache reads (~10× cheaper than fresh input), so the raw token delta
  overstates the harm — **dollars are the right lens**, and there the gap is +31%.
- Run-to-run agent non-determinism across two separate sessions is unbounded; some of the
  +11 calls may be variance.

Full argument, the proposed fixes (relabel now / net later), and the correction to the
cell record's apportioned cost row: **[finding — `saved` is
GROSS](2026-08-01-finding-saved-is-gross.md)**.

**Correction stated, not silently applied:** the cell record
(`cage-lab/reports/cells/FINDING-gross-vs-net-savings.md`) apportioned D1's cost from a
two-session total (≈$0.28, ≈+14%). No apportionment is needed — `imports.jsonl` carries a
**per-session** row for D1 (30 rows, `est_cost_usd 0.242783`), measured by the same code
path as D2's `0.319212`. The measured delta is **+31%**. Every token split in the cell
record reconciles to the ledger exactly; only the cost row is superseded, and the
correction strengthens the finding.

## The cross-agent result

Same workspace, same six questions, same graphify install:

| agent | invoked graphify unprompted? | evidence |
|---|---|---|
| **claude** (D2) | **yes — twice** | 2 transcript receipts, 2 usage rows, 18,456 tokens saved |
| copilot (D4) | **no** | 0 usage rows, 0 receipts |
| kiro (D6) | **no** | 0 usage rows, 0 receipts |

This matches the scripted legs exactly (copilot plain = 0, forced = 23 —
[2026-07-29 run report](2026-07-29-run-report.md)) and extends the same result to a
second surface and to a third agent. **Adoption is agent-specific, and it is not a cage
defect.** The usage log is what makes the distinction measurable.

---

## Deviations recorded (honestly)

1. **The first D1 import landed in the global `~/.cage`.** It was run from the lab root,
   which has no `.cage/`, so cage resolved to the global ledger and wrote **42 rows**
   there before the import was redone in the workspace ledger. Those rows are genuine
   usage — nothing was corrupted — but the lab's *"`~/.cage` untouched"* property was
   broken once, in setup. Recorded, not dropped. **Lesson applied for D2–D6:** always run
   `cage import` from **inside** the workspace directory.
2. **`workspace-off` was contaminated twice by machine-wide sweeps** (operator note) and
   **wiped before D1 and before D3**. The ledger analysed in this report is the post-wipe
   state; its totals (67 call rows) are consistent with the per-cell imports recorded in
   `imports.jsonl` and show no machine-wide contamination.
3. **cage installed from local source (`-e ../cage`)** rather than a shipped wheel — a
   declared deviation from cage-lab's black-box rule while a release is pending.

## What is UNVERIFIED in this run (open questions, not results)

- **D3/D4 prompt counts.** 5 and 4 ledger rows against a 7-turn script, with the actual
  prompt count unrecorded. **UNVERIFIED.** Neither "copilot logs per request" nor "turns
  went missing" is asserted here. The next run must record the prompt count per cell at
  run time.
- **F2's copilot-VS-Code receipt limit.** Never exercised — copilot never invoked
  graphify. **Untested, not confirmed.**
- **The kiro ON/OFF delta.** Not reconstructible from the ledger; no delta is reported.
- **Whether graphify made the D2 session more expensive.** The +31% cost delta is **n = 1**
  — UNPROVEN. What would settle it: the ON/OFF pair at **repeats = 3** on the
  graphify-sensitive questions, reported as a range. (The *label* problem — `saved` being
  gross — is structural and does not depend on n.)

## Checks — the D.2 bar, per cell

| # | check | D1 | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|---|---|
| 1 | captured at all | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 2 | tokens exact vs log | ✅ | ✅ | ✅ | ✅ | ⚠️ credit-derived (FINAL) | ⚠️ credit-derived (FINAL) |
| 3 | surface correct | ⚠️ empty (shared store) | ⚠️ empty | ✅ `vscode` | ✅ `vscode` | ✅ `ide` | ✅ `ide` |
| 4 | session + model real | ✅ | ✅ | ⚠️ `copilot/auto` router alias | ⚠️ same | ⚠️ synthetic `kiro`/`agent` | ⚠️ same |
| 5 | zero UNPRICED | ✅ | ✅ | ⚠️ 5 UNPRICED (router alias) | ⚠️ 4 UNPRICED (router alias) | ✅ | ✅ |
| 6 | three ON answers recorded separately | n/a | ✅ | n/a | ✅ | n/a | ✅ |
| 7 | route matches pre-flight | n/a | ✅ transcript (shim not on the extension PATH) | n/a | n/a (never ran) | n/a | n/a (never ran) |
| 8 | usage rows ≥ receipts | n/a | ✅ 3 = 3 | n/a | ✅ 0 = 0 | n/a | ✅ 0 = 0 |
| 9 | re-import idempotent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 11 | `~/.cage` untouched | ⚠️ broken once in setup (deviation 1) | ✅ | ✅ | ✅ | ✅ | ✅ |
| 12 | no machine-wide contamination | ✅ | ✅ | ✅ | ✅ | ⚠️ pre-lab kiro rows inseparable | ⚠️ same + cross-ledger double-count |

Check 5 on D3/D4: the I.4 bar says **zero UNPRICED**, and D3/D4 do not meet it — 5 and 4
rows respectively. The cause is a **source limit**, not a cage defect: `copilot/auto` is a
router alias, and refusing to price a model it cannot resolve is the correct behaviour
(cells D3/D4 score it that way, and this report does not overrule them). It is recorded
as a ⚠️, not a ✅, because the bar is genuinely unmet and it stays a live user-action item
([F4 — unpriced `copilot/auto`](2026-07-22-finding-unpriced-copilot-auto.md)).

---

## Ledger totals as published (both lab ledgers)

| ledger | agent | rows | tokens_in | tokens_out |
|---|---|---|---|---|
| `workspace-off` | claude-code | 40 (30 D1 + 10 pre-D1 probe) | 1,629,807 | 12,062 |
| `workspace-off` | copilot | 5 | 158,125 | 1,254 |
| `workspace-off` | kiro | 22 | 887 | 0 |
| `workspace-on` | claude-code | 41 | 1,667,521 | 14,204 |
| `workspace-on` | copilot | 4 | 139,302 | 1,690 |
| `workspace-on` | kiro | 28 | 1,576 | 0 |

**Do not sum the two kiro rows** — 22 of the 28 are the same turns (see D6).

Files: `cage-lab/workspace-{off,on}/.cage/ledger/calls-2026-08.jsonl`,
`ledger/imports.jsonl`, `ledger/savings/graphify/savings-2026-08.jsonl`,
`state/graphify-usage.jsonl`. Cell records: `cage-lab/reports/cells/D{1..6}-*.md` +
`FINDING-gross-vs-net-savings.md`. A hashed snapshot of every ledger file above is
committed at `cage-lab/reports/evidence/leg-d/` (with `MANIFEST.sha256`) — the lab is
disposable, the evidence is not.
