# 2026-08-14 — `calls` vs the metric ledgers: the cross-check taken at the cut

**Take-away:** claude's two writers disagree by **1.979×** on rows and **1.881×** on
input tokens, measured on one sweep over one store. Kiro's `credits` shard and its
`cli-conv` metric rows are **1:1 with identical values** — the P2 migration has an exact
parity baseline. `codex` holds **373** rows that only `calls` can ever carry.

**Why it was taken now.** `METRICS-DUAL-WRITE-END` froze the dual-write to 2026-09-13 so
this comparison could be made later. Arpit lifted the freeze early on 2026-08-14 to let
the ledger restructure proceed, and this snapshot is **the entire mitigation**: Claude
Code sweeps its transcripts at roughly 30 days, so once P5 stops the `calls` writer the
measurement can never be repeated. It is evidence, not spec.

---

## Method

Two bases, because they answer different questions.

| basis | what it is | what it is good for |
|---|---|---|
| **A · same-sweep** | one `cage import` into an empty scratch ledger (`CAGE_BASE`), real stores, both writers in the same run | the writer-vs-writer ratio, with coverage held constant |
| **B · the live ledger** | `~/.cage` as it stands, accumulated since 2026-02 | the populations a migration must carry (codex, pre-dual-write history) |

Basis A is the one to quote for a ratio. Basis B's claude figure is confounded: the
metric ledger only starts **2026-08-02**, while `calls` reaches back to **2026-06-21**,
so the two cover different windows.

Neither basis wrote to `~/.cage`. The scratch run used the live `cage.toml` verbatim.

---

## A · same-sweep, one import over the real stores

### claude

| | rows | tokens in | tokens out | sessions |
|---|---:|---:|---:|---:|
| `calls` | 44,659 | 11,167,459,577 | 42,845,812 | 271 |
| `ledger/claude/` `request` | 22,566 | 5,939,348,359 | 19,025,917 | 185 |
| `ledger/claude/` `transcript` | 185 | 5,939,348,359 | 19,025,917 | 185 |

- **`calls` / `request` = 1.9790.** Close to the 2.00× the handoff expected and **not
  equal to it** — recorded as found. `request` is the spine (`SPEND_SOURCES["claude"]`).
- **The token inflation is smaller than the row inflation: 1.881× on `tokens_in`.** Worth
  separating, because a duplicate assistant row repeats a *cumulative* count rather than
  adding an independent one, so rows and tokens were never going to inflate in step.
- **`transcript` and `request` sum to the byte-identical token totals** — the per-chat row
  is exactly the fold of its per-request rows, so the two grains must never be added.
  241.4 is `calls`/`transcript` and is a **grain artefact, not a defect**: it is the mean
  turns per chat, printed here only so nobody later mistakes it for a second ratio.
- **Session counts differ, 271 vs 185.** The metric writer folds subagent sessions into
  their parent (`sessionId`); the calls writer does not (CLAUDE-SUBAGENT-KEY).

### copilot

| | rows | tokens in | tokens out |
|---|---:|---:|---:|
| `calls` | 83 | 3,158,365 | 38,400 |
| `chat` (VS Code) | 57 | 2,302,366 | 28,883 |
| `cli` (cumulative) | 27 | 1,118,228 | 12,902 |
| `cli-delta` | 26 | 855,999 | 9,517 |

`cli` is cumulative and excluded from spend by `CUMULATIVE_SOURCES`; `chat` + `cli-delta`
= 83 rows, exactly the `calls` count. **Copilot's two writers already agree row-for-row.**

### kiro

| | rows |
|---|---:|
| `calls` (IDE `tokens_generated.jsonl`) | 28 |
| `cli-turn` | 5 |
| `cli-conv` | 3 |

Different stores answering different questions, not a disagreement: `calls` here is the
IDE log (1,576 in / **0 out** — the unsummable one `ABSENT_SPINES` names), and the
`cli-*` rows come from the CLI's SQLite store. No ratio is meaningful.

---

## The P2 parity baseline — kiro `credits` vs `cli-conv`

**Exact, on both halves.**

| check | result |
|---|---|
| `credits` rows / `cli-conv` rows | 3 / 3 |
| credit sessions ⊆ cli-conv sessions | **yes** |
| cli-conv sessions carrying no credit row | **0** |
| `credits`, `context_pct`, `turns` per shared session | **identical values** |

Both are scoped to the project tree (`paths.kiro_cli_workspace`), which is why 3 of the
store's 20 conversations were read.

**The skip-rule difference is real in the code and empty in practice.** The handoff names
it as P2's crux: `_kiro_cli_credit_row` drops a conversation when credits ≤ 0 **and**
context ≤ 0, while `cli-conv` emits whenever `usage_info` is present. Measured directly
over **all 20** conversations, unscoped:

- 20 carry `usage_info` → `cli-conv` would emit 20
- 20 have credits > 0 or context > 0 → the credits rule would emit 20
- **delta: 0**

So `cli-conv` is a superset by construction and an equal set on this store. **n = 20, one
machine** — that bounds the claim; it does not license deleting the skip rule, which
still guards a case this store happens not to contain.

**One drift worth naming:** the live ledger's 2026-07 credit rows carry
`method="estimated"`; rows written by today's parser carry `method="measured"`. P2 must
preserve `measured` and must not rewrite the older rows.

---

## B · the live ledger — the populations a migration must carry

66,320 `calls` rows across six monthly shards (2026-02 → 2026-08).

| agent | rows | window |
|---|---:|---|
| claude-code | 65,837 | 2026-06-21 → 2026-08-14 |
| **codex** | **373** | 2026-05-10 → 2026-07-11 |
| copilot | 82 | 2026-02-14 → 2026-08-01 |
| kiro | 28 | 2026-07-23 → 2026-08-01 |

- **codex is the population that pins the reader open.** 373 rows, provider `openai`,
  route `chat`. Codex was removed in v0.33 and no metric ledger exists or ever will for
  it, so `calls` and `ledger.calls` are **permanent**. P5 stops a writer; it never deletes
  a shard.
- **No consumer rows exist at all** — zero `lib`/proxy rows. P1's `ledger/consumer/`
  starts empty here, so a real-ledger regression cannot prove its read path; a test must.
- **52,449 claude rows in 352 sessions predate the metric ledger** (before 2026-08-02).
  Those sessions have no metric twin and never will.
- **`scope` is stamped on 0 of 66,320 rows** and `credits` on none — two of the six
  UNREAD-FACTS are not merely unread, they are unwritten in practice.
- The live ledger holds `credits-2026-07.jsonl` (17 rows) with **no** `ledger/kiro/`
  directory: the metric writer post-dates those rows. Reading both forever is not
  optional.

---

## What this constrains

1. **P1** — codex's 373 rows resolve only through `calls`. Dual-write, never a cutover.
2. **P2** — parity is 1:1 with identical values; any drift after the change is a defect.
3. **P5** — retiring the claude writer removes ~1.98 rows for every row the spine keeps.
   Nothing downstream may treat that as a loss of *spend*: the tokens were double-counted.
4. **Anything comparing pre- and post-2026-08-02 claude figures** is comparing two
   different writers. The dual-write window is 2026-08-02 → 2026-08-14, and that is all
   the overlap that will ever exist.

## Reproduction

```bash
SC=$(mktemp -d)/cage; mkdir -p "$SC"; cp ~/.cage/cage.toml "$SC/"
CAGE_BASE="$SC" cage import          # both writers, one sweep, real stores
```

Counts above are row counts of the resulting shards. The unscoped skip-rule delta was
measured by reading `conversations_v2` read-only and applying both predicates in Python.

**Sibling probe:** [research/2026-08-14-chat-title-store-probes.md](../research/2026-08-14-chat-title-store-probes.md)
— P0.2, the store probes for P3b's name lifting.
