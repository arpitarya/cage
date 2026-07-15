# Design — the human baseline axis (`cage human show`)

**Status:** **implemented** (2026-06-19) — all 10 §6 criteria green, `cage demo`
unchanged, docs synced, no new dependency. See §8 checklist.
**Scope:** add an *agent-vs-human* counterfactual to cage without forking the
substrate. Reuse the receipt model, the price arithmetic, and the matrix engine.
**Constraints inherited (non-negotiable):** `$0` / stdlib-only, deterministic
derived views, fail-open on the write path, `method` is sacred (no estimate may
render as `measured`), modules small and single-purpose.

---

## 0. Why — the one real gap

The spec asked for three things. Two already ship:

| Ask | Already in cage |
|-----|-----------------|
| graphify with/without · fux with/without | `matrix.py` — the 2ⁿ on/off permutation table, costed at the task's model |
| independent per item **and** all permutations/combinations | `attribution.py` (independent marginal per tool) + `matrix.py` (every combo) |
| per-tool $ ROI net of the tool's own cost | `roi.py` |
| meter claude / codex / copilot / kiro + Claude SDK + any LLM in Orff | `agents.py`, `metering.py`, the `cage_meter` adapter |
| installable package · terminal · HTML | `pyproject.toml` · `render.py` · `serve.py` |

The genuinely missing thing is **point 1: how much an AI agent saves vs a human
doing the same task.** Today cage's only "alternative" is the *all-tools-off token
baseline* — a tool-vs-tool comparison on the agent path. There is no notion of
*"what a person would have cost in time and money for this task."* That is a
different counterfactual axis (human labor, priced in minutes→money), and it is
what this design adds.

**Design principle applied:** model `human` as **one more baseline layer in the
same ledger**, not a parallel subsystem. A human receipt is just a receipt whose
`tool` is `"human"`. Everything downstream (matrix, roi, report) then lights up
with no new math — the substrate already carries `raw_alternative`, `actual`,
`saved`, `method`, `confidence`.

> The four design questions this doc opened with have been debated and resolved
> in §9. The decisions are threaded through the sections below; §9 carries the
> reasoning. Summary: **(A)** add a `minutes` unit *and* centralize the unit→USD
> conversion; **(B)** commit illustrative blended rates + optional
> `CAGE_HUMAN_RATE` env override with visible provenance; **(C)** task-type table
> default + confidence laddering by mode; **(D)** `roi` stays strictly tool-only;
> **(E)** commit/outcome data lives in a new `tasks.jsonl`, not receipt `meta`;
> **(F)** store top-level changed dirs, not full paths.
>
> **§5b** adds the tracking the objective needs beyond cost: **time-saving as a
> co-equal metric**, a **commit-aware task record** (git auto-collected, fail-open),
> and **`cage insights trend`** turning timestamps into a cost+time savings time-series.

---

## 1. The two tiers (and why human is not a token-saving tool)

A task has two independent kinds of saving. Keep them distinct or the numbers lie:

- **Tier 1 — whole-task: human vs agent.** "Would a person have done this, and at
  what cost?" Priced in money (via minutes × rate). This is the new axis.
- **Tier 2 — within the agent path: tool vs tool.** graphify / fux / router /
  compressor / cache shrinking input tokens. This is the *existing* matrix.

Human is **not** a token-saving layer in the 2ⁿ matrix. Combinations like
"human + fux" are nonsense — fux only saves once you've decided to run the agent.
So the human counterfactual sits **above** the agent stack as a single anchor, and
every agent-path combination is annotated with its delta *vs* that anchor. This
gives "all the meaningful combinations" — `{human}` against `{agent + any subset
of tools}` — without fabricating impossible ones and without a 2ⁿ⁺¹ blow-up.

```
  human (no agent)                                  $H        ← Tier-1 anchor
  ────────────────────────────────────────────────────
  agent, all tools OFF                              $a₀   (saves $H−$a₀ vs human)
  agent + graphify                                  $a₁   (saves $H−$a₁ vs human)
  agent + graphify + fux                            $a₂   (saves …)
  …  (the existing 2ⁿ token permutations)           …
  agent, full stack                                 $aₙ   (saves the most)
```

---

## 2. Substrate change (minimal, additive)

### 2.1 One new unit

`schema.py`:
```
UNITS = ("tokens", "usd", "ms", "gco2", "minutes")   # + "minutes"
```
`minutes` lets a human receipt record *time* as the ground-truth input and have
cage convert to money deterministically at a configured rate — the audit trail
keeps the human estimate, not just a dollar figure someone typed.

No new fields. A human receipt reuses the existing shape:

```jsonc
{
  "tool": "human",
  "unit": "minutes",            // or "usd" for a directly-quoted cost
  "raw_alternative": 90,        // 90 human-minutes (the no-agent path)
  "actual": 0,                  // human alternative was not performed
  "method": "estimated",        // a guess; "measured" only for a real timesheet
  "confidence": 0.6,
  "call": "c_…",                // the agent run this is the alternative to
  "task": "add-broker-csv",
  "meta": { "task_type": "feature", "rate_usd_per_hr": 80, "agent": "claude" }
}
```

`saved` stays derived (`raw_alternative - actual`); for a `minutes` receipt that
is "minutes saved", converted to money by the resolver in §3. `actual = 0` is
deliberate: the human work didn't happen — the agent's measured task cost is read
from the **call ledger**, not stored on the human receipt, so the two can never
silently disagree (same discipline as `saved` being derived).

**Why a unit and not USD-in-`meta` (decision A).** The alternative — store
`unit="usd"` with the dollar figure computed at record time — would bake a *policy
number* (the rate) into an append-only ledger row, going stale the moment the rate
changes. That is precisely the staleness cage exists to avoid: a call stores
`est_cost_usd` but authoritative cost is *re-derived* from tokens × policy price in
every view. Tokens are the ground-truth quantity; cost derives. **Minutes are the
ground-truth quantity for human labor; cost must likewise derive.** Storing minutes
keeps the invariant "same ledger + same policy ⇒ same tables" intact across a rate
change. The cost of the new unit is that it is the *only* unit converted via a
human rate rather than a model price — handled by §2.3.

### 2.3 Centralize unit→USD conversion (the refactor that makes `minutes` safe)

Today the "what is this receipt worth in USD" dispatch is **duplicated and
implicit**: `roi._saved_usd` and `attribution.attribute` each branch `unit=="usd"`
→ passthrough, `else` → treat as tokens and cost at model price. A `minutes`
receipt would be silently mis-costed as tokens by that `else`. Rather than patch
two call sites, introduce one helper and route every read surface through it:

```
# convert.py (new, ≤40 lines)
def saved_usd(receipt: dict, call: dict, pol: dict) -> float:
    unit = receipt.get("unit", "tokens")
    if unit == "usd":      return float(receipt["saved"])
    if unit == "tokens":   return prices.input_cost_usd(pol, call.get("provider",""),
                                                        call.get("model",""), int(receipt["saved"]))
    if unit == "minutes":  return human.minutes_to_usd(receipt, pol)   # human rate
    return 0.0   # ms / gco2 are not money — never counted as savings $
```

`roi` and `human` both call `convert.saved_usd`; `attribution` keeps its existing
token/usd handling but is refactored onto the same helper so there is exactly one
place unit semantics live. Adding the new unit thus *removes* duplication instead
of adding a third copy of the branch — net simplification.

### 2.2 `method` discipline (sacred)

A human cost is `estimated` by default — it is a guess about counterfactual labor.
It may be `measured` **only** when the caller asserts a real observed figure (an
actual timesheet / a quoted contractor invoice). It is **never** `modeled`
(`modeled` is reserved for reconstructed token cells in the matrix). The matrix's
existing trust-downgrade rule then does the right thing automatically: any cell
leaning on an `estimated` human anchor is itself `estimated`.

---

## 3. Pricing — all three input modes, one resolver

Per your call ("the one that makes most sense, maybe all"), support **all three**,
resolved by a single deterministic precedence chain. New module
`human.py` (≤100 lines), one public function:

```
def human_alternative_usd(receipt: dict, pol: dict) -> tuple[float, str]:
    """Return (usd, method) for a human receipt by the precedence chain below."""
```

**Precedence (first match wins):**

1. **Explicit USD on the receipt** — `unit == "usd"`: use `raw_alternative`
   directly. `method` as recorded (`measured` if it's a real quote, else
   `estimated`). *Most flexible, least automatic.*
2. **Per-receipt minutes** — `unit == "minutes"` with a rate available
   (`meta.rate_usd_per_hr`, else policy default): `usd = minutes/60 × rate`.
   `method = "estimated"` unless the caller marked it `measured`.
3. **Task-type table** — receipt carries `meta.task_type` but no minutes: look up
   `[human.tasks.<type>]` → `{minutes, rate}` from policy. `method = "estimated"`.
4. **Global default** — none of the above: `[human].default_minutes ×
   [human].rate_usd_per_hr`. `method = "estimated"`, low confidence.

**Default mode (decision C): the task-type table (mode 3)** — you classify a task
once (`feature` / `refactor` / `bugfix` / `research` / `review`) and never
re-estimate, while modes 1–2 stay available for a precise override. This is the
ergonomic sweet spot for a daily-driver ledger: cage's whole thesis is *passive,
cheap capture or it doesn't get recorded*, and requiring per-task minute estimates
would starve the ledger of data.

**The honesty guard — confidence laddering.** A flat type table emits suspiciously
uniform round numbers (every "feature" = 120 min), and cage's entire value is
*defensible* numbers. So the resolver stamps `confidence` by how the figure was
obtained, and every read surface shows it — round estimates then *visibly* read as
low-credibility instead of masquerading as precise:

| Mode | `method` | `confidence` |
|------|----------|--------------|
| 1 — explicit USD, caller asserts a real quote/timesheet | `measured` | 0.9 |
| 1/2 — explicit USD or minutes, but an estimate | `estimated` | 0.7 |
| 3 — task-type table lookup | `estimated` | 0.5 |
| 4 — global default fallback | `estimated` | 0.3 |

(Confidence values live in policy under `[human.confidence]` so they are tunable,
not hard-coded.)

### 3.1 `policy.toml` additions

```toml
# Human-labor baseline (Tier-1 counterfactual). The only place human numbers live.
[human]
rate_usd_per_hr = 80        # blended default rate
default_minutes = 60        # fallback when a task has no type and no minutes
currency = "USD"

# Optional per-task-type lookup (mode 3 — the recommended default path).
# One subtable per type — valid TOML; parses to the dict the resolver expects.
[human.tasks.feature]
minutes = 120
rate_usd_per_hr = 90

[human.tasks.bugfix]
minutes = 45
rate_usd_per_hr = 80

[human.tasks.refactor]
minutes = 90
rate_usd_per_hr = 90

[human.tasks.research]
minutes = 180
rate_usd_per_hr = 70

[human.tasks.review]
minutes = 30
rate_usd_per_hr = 100
```

`policy.load` already merges project-over-bundled per section; add `"human"` to
its merge list so a project `policy.toml` can override rates without copying the
table. Keep all numbers in policy — never hard-code a rate in code.

### 3.2 Rate provenance — committed default + env escape hatch (decision B)

Vault/env-backing the *read path* itself is rejected: it would break "same ledger
+ same policy ⇒ same tables," push a network call into a deterministic view, and
risk a dependency — all three violate cage law. Rates therefore live in policy.
The bundled `[human]` table ships **illustrative blended estimates** (rounded,
market-style — like the bundled model prices), safe to commit.

For the fintech sensitivity (a checked-in `policy.toml` with a team's *real*
internal rate is an info leak), add one optional escape hatch read at derive time:

```
CAGE_HUMAN_RATE=120 cage human show          # supersedes [human].rate_usd_per_hr
```

It is stdlib (`os.environ`), zero-dependency, and stays deterministic because env
is an *explicit config input*, not a clock or RNG — `(ledger, policy, env) ⇒
tables` is reproducible. To keep it auditable rather than a hidden input, **`cage
human` prints its rate provenance** in the header:

```
Agent vs human · 14 tasks · rate source: env ($120/hr)   ← or "policy ($80/hr)"
```

A comp-sensitive team thus leaves the committed value illustrative and injects the
real rate via a CI/shell secret, with the source visible in every report.

---

## 4. Read surfaces

### 4.1 New command — `cage human show` (point 1, directly)

Per-agent rollup: for each metered agent (`claude` / `codex` / `copilot` / `kiro`
/ `lib`), total human-alternative cost vs total measured agent cost, net saved,
and saved-per-successful-task (reusing the existing `task_ok` quality signal so
the comparison is honest — a task the agent botched and a human had to redo is not
a saving).

```
Agent vs human · 14 tasks · since 2026-06-01 · rate source: policy ($80/hr)

agent     tasks   human $    agent $    saved $   saved hrs   conf   method
claude       9    $1,140.00    $4.12    $1,135.88     13.2     0.51   estimated
codex        3      $260.00    $1.55      $258.45      3.1     0.50   estimated
copilot      2      $130.00    $0.88      $129.12      1.6     0.50   estimated
TOTAL       14    $1,530.00    $6.55    $1,523.45     17.9     0.51
```

(`saved hrs` is the §5b.1 time metric — co-equal with `saved $`, both derived from
the same human baseline; it can go negative when the agent ran longer than the
human estimate, which is the honesty check.)

The `conf` column is the confidence-weighted average (§3 ladder), so a column of
0.5s is a visible signal that these totals rest on the task-type table, not on
measured timesheets — exactly the honesty guard decision C calls for.

Flags: `--since`, `--task <id>` (single task detail), `--agent <name>` (filter),
`--json` (machine-readable, per design-for-the-agent-as-user), `--html` (writes a
standalone page; see §4.3).

### 4.2 `matrix` overlay — `cage insights matrix <task> --human`

Render the existing 2ⁿ token table, then prepend the **human anchor row** and add
two columns to every agent row: `vs human $` and `vs human %`. The anchor's
`source` column reads `estimated`/`measured` per the resolver; agent rows keep
their existing `measured`/`modeled`/`estimated` tag. Without `--human` the matrix
is byte-for-byte unchanged (no regression to the `demo` §4.4 tables).

### 4.3 HTML

`serve.py` gains a "Agent vs human" panel (the §4.1 table + a bar of human-$ vs
agent-$ per agent). `cage human show --html <path>` and `cage insights matrix … --html <path>`
emit the same content as a standalone, dependency-free HTML file (inline CSS, no
CDN) — matches cage's existing zero-dependency render discipline so the file
opens anywhere and can be attached to a report.

### 4.4 What does *not* change

- **`attrib`** stays tool-only (marginal per-tool *within* the agent path).
  Putting the whole-task human baseline in a per-tool marginal table would
  conflate the two tiers. Human lives in `cage human show` + the matrix overlay.
- **`roi`** stays **strictly tool-only — no `--include-human` flag** (decision D).
  "Agent vs human" is a *join of calls (agent cost) with human receipts*, a
  different computation from roi's receipts-only, net-of-own-cost, per-tool math —
  and it is exactly what `cage human show` already does. A flag would duplicate that
  logic inside roi and blur the two-tier model. `cage human show` *is* the human-ROI
  view; the HTML dashboard (§4.3) composes the roi panel and the human panel
  side by side rather than merging the two computations.

---

## 5. Recording human receipts (how the number gets in)

Three entry points, mirroring the three input modes:

1. **CLI** — `cage human record --task <id> --type feature` (uses the task-type
   table), or `--minutes 90 [--rate 90]`, or `--usd 150`. Writes one
   `tool="human"` receipt via `ledger.append` (fail-open).
2. **Outcome flow** — extend the existing `cage human outcome` so logging a task's
   result can attach a human estimate in the same step (one habit, not two).
3. **Library** — `cage.record_human(task=…, minutes=…|usd=…|task_type=…)` for
   Orff to call from `LLMGateway` when it closes out a task, fail-open like
   `cage_meter`.

Determinism note: the receipt stores the *input* (minutes/type/rate); the
USD is derived at read time by `human.py` from current policy. Re-pricing the
backlog after a rate change is then just a policy edit — no ledger rewrite.

---

## 5b. Enrichment — time-saving, commits & dates

The objective is **cost saving *and* time saving**, tracked over time and anchored
to real artifacts. cage already nails cost and already carries dates (`ts` on every
row, `report` by-day, `--since`). This section closes the other two: time as a
co-equal metric, and a commit-aware task record.

### 5b.1 Time-saving as a co-equal metric

Every surface that prints *saved $* also prints *saved time*. Two clocks:

- **`human_minutes`** — the avoided human labor, straight from the §3 resolver.
- **`agent_active_minutes`** — what the agent run actually took: the task's
  call-span wall-clock (`last_call_ts − first_call_ts`), floored by
  `Σ latency_ms / 60000`. This is supervision time and is irreducibly fuzzy, so
  it is tagged **`estimated`** and never sold as measured.

`time_saved = human_minutes − agent_active_minutes`. A task where the agent thrashed
for an hour on a 5-minute fix correctly shows *negative* time saved — the metric
must be able to embarrass the agent or it isn't honest.

### 5b.2 The task record — `tasks.jsonl` (decision E: new file, not `meta`)

Today `task` is only a foreign-key string; nothing describes the task itself. Add a
third append-only ledger file, one row per task (last-write-wins by `id` at derive
time), referenced by calls and receipts that already carry `task`:

```jsonc
{
  "id": "add-broker-csv",
  "ts": "2026-06-19T10:22:00Z",
  "type": "feature",              // feeds the §3 task-type rate + confidence
  "outcome": "ok",                // absorbs `cage human outcome` / the task_ok signal
  "commit": "a1b9f3c",            // SHA only — never the message
  "branch": "feat/broker-csv",
  "files_changed": 4,
  "insertions": 212,
  "deletions": 38,
  "started_ts": "2026-06-19T10:05:00Z",
  "ended_ts":   "2026-06-19T10:22:00Z",
  "agents": ["claude"]
}
```

**Auto-collection, deterministic & fail-open.** At task close (the existing
SessionEnd hook / `cage human outcome`), snapshot git via plain shell —
`git rev-parse --short HEAD`, `git rev-parse --abbrev-ref HEAD`,
`git diff --shortstat`. No repo, no git, detached state → omit those fields, never
raise (write-path fail-open, like `ledger.append`). No network, no LLM — satisfies
the determinism rule.

**PII / fintech stance (carried over from "prompt bodies are never a field").**
Store the **SHA and numeric diff stats only**. Do **not** store the commit
*message* (free text — unbounded risk class), the **author name/email** (PII), or
file *contents*. File paths: store the **count** by default.

> **Decision F (open, low-stakes).** Also store top-level changed dirs (e.g.
> `["app/brokers", "docs"]`) for per-area savings, or count only? *Rec: top-level
> dirs only — useful for "where does the agent save most," low leak risk. Full
> paths: no.*

### 5b.3 Diff-informed human estimate (raises confidence)

The task record makes the human estimate more defensible: scale the type-table
minutes by diff size instead of using a flat per-type constant —
`est_minutes = base[type] × size_factor(insertions + deletions)`. This slots into
the §3 precedence chain **above** the flat type table (a sized estimate beats a
constant) at **confidence 0.6**:

| Mode | confidence |
|------|-----------|
| explicit USD / minutes (measured) | 0.9 |
| explicit minutes (estimated) | 0.7 |
| **diff-sized type estimate** | **0.6** |
| flat type-table lookup | 0.5 |
| global default | 0.3 |

### 5b.4 `cage insights trend` — dates become a savings time-series

```
cage insights trend [--by week|month] [--metric cost|time|both] [--since …] [--json] [--html]

Savings trend · by week · since 2026-05-01

week        agent $   human $ saved   $ saved   time saved   tasks
2026-W18      $2.10      $480.00      $477.90     9.4 h         5
2026-W19      $3.55      $610.00      $606.45    12.1 h         7
2026-W20      $1.90      $300.00      $298.10     5.8 h         3
```

Pure derive over `ts` (no new entropy), reusing `report`'s bucketing. Also a
`serve.py` panel so the dashboard shows the trend line for cost and time saved.

### 5b.5 What is deliberately NOT tracked (the discipline guard)

Commit messages, diff/code content, author identity, per-file blame, and
speculative scores (complexity, sentiment, "difficulty"). Each is either a PII /
free-text risk or a field with no consumer yet. Add when a real read surface needs
it — not on spec. This keeps the substrate small and auditable.

---

## 5c. Passive attention minutes (derived) — plan §4.10 extension

**Status: implemented (2026-07-11).** The axis above prices what a human *would
have* cost; this section closes total cost's other half: what the agent **costs
in human time** — supervision minutes, derived passively from the session logs
cage already imports. It *extends* the §3 ladder (a new lowest rung under the
attested modes), never bypasses it.

### 5c.1 Capture — `gap_ms` on the call row

At import, where a transcript carries per-turn timestamps, each call row gains an
additive optional `gap_ms`: the wall-clock between the previous assistant turn's
end and the human turn that led to this call. Timestamps/counts only; the field
never enters an id; absence is the legacy contract. Per-agent availability is a
documented fact (`transcript.py`, fixtures README): **claude yes;
codex/copilot/kiro no** — their pinned formats lack a usable timestamp pair, so
their rows omit the field. **Never fabricate.** Tool-result / meta / sidechain
records are machine turns and never gap.

### 5c.2 Derivation — read-time only, one module

`attention.py` is the single place gap math lives (no view computes gaps
itself): `minutes = Σ min(gap_ms, idle_cap)`. The idle cap (policy
`[human] idle_cap_minutes`, `constants.IDLE_CAP_MINUTES` fallback, default 10)
guards against the same time-from-timestamps fallacy §9's `cage calibrate`
bans for commit history: a long gap is walked-away time, not supervision.
Changing the cap re-derives; the ledger is never rewritten.

### 5c.3 Method honesty — attested beats derived, never summed

Derived minutes are always **`estimated`**, labelled `derived (turn-gaps,
capped)`. Attested minutes — `cage human record --minutes`, or the friction-drop
`cage human outcome <task> --minutes N` (same fail-open, idempotent receipt path) —
rank above derived in the precedence ladder; for a given task **attested wins
and derived renders as reference — the two are never summed.** The extended
confidence intuition: attested modes keep their §3 rungs; the derived heuristic
sits below them all and *never self-reports confidence* — its accuracy is
measured (§5c.4).

### 5c.4 Calibration — the manual axis grades the heuristic

`cage insights calibration --human`: over tasks with BOTH attested and derived minutes,
report the derived/attested ratio distribution (median + IQR) — the measured
accuracy of the heuristic, `method: measured` (an observed frequency of recorded
signals). Below `MIN_ESTIMATE_N` such tasks it refuses. This mirrors the
estimate/calibration pattern (plan §4.8): estimate passively, attest the truth,
let the measured gap be the confidence.

### 5c.5 Views

`cage human show` / `cage insights trend` show attested and derived as **separate blocks**
(absence of gap data is an explicit line, not silence). `cage insights compare`,
`cage insights verdict`, `cage study report` gain one total-cost line — agent $ + human
minutes × rate, tagged with the human component's method — suppressed by
`--agent-only`. `matrix --human` is unchanged: baseline receipts answer "what
would a person instead have cost", a different question from "what did this
agent run cost in my time".

### 5c.6 The watcher guard (deliberately NOT built)

No editor plugins, activity trackers, keystroke or focus monitoring — transcript
timestamps only. This is a product line in the §5b.5 spirit: anything
watcher-shaped is a different (surveillance) product, not a cage feature.

---

## 6. Acceptance criteria (how we'll know it's done)

A change is done only when all of these hold and the docs in §8 are updated.

1. `schema.make_receipt(unit="minutes", …)` validates; an unknown unit still
   raises. `saved` remains derived.
2. `human.human_alternative_usd` returns the right `(usd, method, confidence)` for
   each of the four precedence branches — one test per branch, asserting exact
   figures and the confidence ladder (0.9 / 0.7 / 0.5 / 0.3).
2a. `convert.saved_usd` returns identical USD for a `usd`, `tokens`, and `minutes`
   receipt of equal value, and `0.0` for `ms`/`gco2`; `roi` and `attribution`
   produce byte-identical output before and after being routed through it
   (pure refactor — snapshot test).
2b. `CAGE_HUMAN_RATE` supersedes the policy rate; `cage human show` header prints
   `rate source: env ($N/hr)` when set and `policy ($N/hr)` when not; the same
   `(ledger, policy, env)` triple yields identical tables (determinism preserved).
3. `cage human show` totals reconcile: `Σ saved == Σ human_$ − Σ agent_$` for the
   filtered window; `--json` emits the same numbers as the table.
4. `cage insights matrix <task> --human` shows the anchor as the most expensive row, every
   agent row's `vs human %` is internally consistent, and the run-without-`--human`
   output is **identical** to today (snapshot test against `demo`).
5. A human receipt with no minutes/type/usd falls back to the global default and
   is tagged `estimated` with reduced confidence — never `measured`.
6. Re-running `human-record` for the same `(task, call)` is idempotent-safe (no
   double count) — match the transcript-replay guarantee.
7. Money/PII: rates are the only new numbers and live in `policy.toml`; no human
   *name*, comp record, or PII enters a receipt or an error string. The task
   record stores SHA + diff *counts* only — never commit message, author, or paths
   beyond top-level dirs.
8. `$0`: `human.py` / `convert.py` / `tasks.py` import stdlib + `cage.*` only; no
   new dependency. Git is shelled out to, fail-open, never imported as a library.
9. Time-saving: `cage human show` and `cage insights trend` show `saved hrs`; a task whose
   `agent_active_minutes` exceeds `human_minutes` reports **negative** time saved
   (asserted by a test) — the metric can embarrass the agent.
10. Task record: git auto-collection is fail-open — a non-repo / no-git / detached
    HEAD omits the git fields and never raises; `tasks.jsonl` last-write-wins by
    `id`; re-closing a task is idempotent.

---

## 7. Module + CLI footprint (what we'll touch)

| File | Change |
|------|--------|
| `cage/schema.py` | add `"minutes"` to `UNITS` (1 line) |
| `cage/convert.py` | **new** — single unit→USD dispatcher (≤40 lines, decision A) |
| `cage/human.py` | **new** — resolver (precedence + confidence ladder) + per-agent rollup (≤100 lines) |
| `cage/roi.py` · `cage/attribution.py` | route through `convert.saved_usd` (remove duplicated unit branch) |
| `cage/policy.py` | add `"human"` to merge sections; `human_rates()`; `CAGE_HUMAN_RATE` env override |
| `cage/data/policy.toml` | add `[human]`, `[human.tasks.*]`, `[human.confidence]` |
| `cage/tasks.py` | **new** — `tasks.jsonl` read/write + fail-open git snapshot (§5b.2) |
| `cage/trend.py` | **new** — cost+time time-series by week/month (§5b.4) |
| `cage/matrix.py` | optional human anchor row + `vs human` columns behind a flag |
| `cage/render.py` | tables for `cage human show` / `cage insights trend` (reuse `render.table`) |
| `cage/serve.py` | "Agent vs human" + "Savings trend" panels + standalone `--html` writer |
| `cage/hooks.py` · `clicmds.py` | snapshot git into `tasks.jsonl` at task close (SessionEnd / `cage human outcome`) |
| `cage/cli.py` + `clicmds.py` | `human`, `human-record`, `trend` subcommands; `matrix --human`; `--html` |
| `tests/` | the 10 criteria in §6 |

Estimated as a one-sprint, well-bounded delegation once this spec is approved:
clear inputs → outputs, every acceptance criterion is a test.

---

## 8. Doc-sync checklist (cage rule: code change ⇒ doc change, same session)

- [x] `docs/cage-plan.md` — added §4.6 "Tier-1: the human baseline" beside the §4.4
  matrix (two-tier model + precedence chain + the two clocks), §3.4 for the
  `tasks.jsonl` substrate addition, and the new CLI lines in §7.
- [x] `README.md` — added `cage human show` / `human-record` / `matrix --human` / `trend`
  to the command list, a Tier-1 section, and the one-line summary (cost **and** time
  saved, anchored to commits). Test count refreshed.
- [x] `docs/agents.md` — noted that Orff records human estimates via `record_human`.
- [x] `CLAUDE.md` — added `convert.py`/`human.py`/`humanview.py`/`tasks.py`/`trend.py`
  to the architecture map; `[human]` policy section, `CAGE_HUMAN_RATE` override,
  `tasks.jsonl`, and that human cost is `estimated` by default.
- [x] This file — status flipped to *implemented* (see header).

---

## 9. Decisions — debated & resolved

All four are settled; implementation is unblocked. Reasoning kept so the *why*
survives (capture-intent principle).

### A. `minutes` unit vs USD-in-`meta` → **add `minutes` + centralize conversion**

The pro-`minutes` case that wins isn't re-pricing (rare, low value) — it's the
substrate invariant: cage stores ground-truth *quantities* and **derives** money
from policy in every view (tokens → cost; `est_cost_usd` is only a hint). Baking a
rate-derived USD into an append-only row breaks that and goes stale on a rate
change. Minutes is the physical quantity for human labor, so it earns a unit. Its
one real cost — being the only unit converted via a human rate, not a model price —
is neutralized by §2.3: centralize the unit→USD dispatch (today duplicated in
`roi` and `attribution`) into one `convert.saved_usd`. The new unit becomes the
forcing function for a refactor that *removes* duplication. Net win.

### B. Commit rates vs Vault → **commit blended defaults + optional env override**

Vault/env-backing the read path is rejected outright: it breaks "same ledger +
policy ⇒ same tables," forces a network call into a deterministic view, and risks
a dependency — three violations of cage law. Rates live in policy; the bundled
default ships rounded, market-style blended estimates (non-secret, like bundled
model prices). The fintech leak risk (real internal rates in a checked-in file) is
handled by one optional `CAGE_HUMAN_RATE` env override (stdlib, zero-dep), read at
derive time, with its provenance printed in the `cage human show` header so it is
auditable rather than hidden. Determinism holds: env is explicit config, not
entropy.

### C. Default input mode → **task-type table + confidence laddering**

Per-task minutes is more accurate but high-friction, and cage lives or dies on
*passive, cheap* capture — friction starves the ledger. The task-type table is the
zero-friction floor. Its weakness (uniform round numbers that look more precise
than they are) is met head-on by laddering `confidence` by mode (0.9 → 0.3) and
surfacing it in every view, so type-table figures *read* as the low-credibility
estimates they are. Honest and adoptable.

### D. `roi --include-human` → **no flag; roi stays strictly tool-only**

Stronger than "defer." "Agent vs human" is a join of *calls* (agent cost) with
*human receipts* — a different computation from roi's receipts-only, per-tool,
net-of-own-cost math, and precisely what `cage human show` is. A flag would duplicate
that logic and blur the two-tier model (§1). `cage human show` is the human-ROI view;
the dashboard composes the two panels rather than merging the two computations.

### E. Commit/task data in `meta` vs a new file → **new `tasks.jsonl`**

Cramming commit + diff + outcome into receipt `meta` duplicates task-level facts
across every receipt of a task and has no home for `outcome`. A task is a
first-class entity that calls and receipts already reference by id but nothing
describes. The cost is a third ledger file (contract change → plan §3), justified
because it also absorbs the existing `outcome` signal and powers the diff-informed
confidence bump (§5b.3) and `cage insights trend`. Auto-collected from git, fail-open. The
discipline guard (§5b.5) keeps it from sprawling.

### F. Top-level changed dirs vs path count only → **top-level dirs** (low-stakes)

Per-area savings ("the agent saves most in `app/brokers`") is worth the small
surface; full paths are not. SHA + counts + top-level dirs, nothing finer.

### Still genuinely open (non-blocking, post-MVP)

- **Auto-classifying `task_type`** from transcript signals (files touched, lines
  changed) to drop the one manual step — but only as an explicitly `estimated`,
  low-confidence heuristic. Spike later; don't gate the MVP on it.
- **`gco2` human comparison** (carbon of a human-hour vs an agent run) — the
  substrate already supports it; defer until there's a consumer.
- **`cage calibrate` — repo-grounded human effort from existing commits.** Mine
  the repo's git history once to make the human baseline empirical instead of a
  flat guess. **Hard constraint (the trap): use commit history for the *size*
  signal, never the *time* signal.** Inter-commit wall-clock is nights / meetings
  / idle, not effort — turning it into minutes is a known estimation fallacy and
  would inflate savings. What's honestly extractable:
  - the **diff-size distribution per type** (`git log --numstat`, deterministic,
    `$0`, no LLM) → seed `[human.tasks.*]` size baselines / §5b.3's `size_factor`
    so estimates fit *this* codebase, not a global default;
  - if **measured anchors** exist (a few tasks with real timesheets/minutes), fit
    `size → minutes` from those points and interpolate across the backlog — a
    legitimate measured→estimated extrapolation.
  Output is `estimated`; confidence ~0.4 from size-distribution alone, rising
  toward 0.6+ when anchored by measured points (fits the §3 ladder). PII guard:
  ingest sizes / dates / types only — **never author name or email**. Spike as a
  one-shot calibration command; do not gate the MVP.

---

## 10. Evidence base — why a human baseline is defensible (and why it's `estimated`)

The literature *both* supports the baseline and explains why it must be a tunable
estimate, not a measured fact. That epistemic shape is what the design encodes
(per-org rates, `method="estimated"`, confidence ladder, time-saved allowed to go
negative). Summary of what each strand justifies:

**The default rate is empirically anchored.** US BLS median software-developer wage
≈ $132.7k/yr ≈ $64/hr; a standard 25–30% load for payroll/benefits/overhead lands a
fully-loaded ≈ **$80/hr** — exactly `[human].rate_usd_per_hr = 80` (§3.1). The money
half of the baseline rests on wage data, not a guess.
→ BLS Occupational Outlook, Software Developers:
https://www.bls.gov/ooh/computer-and-information-technology/software-developers.htm

**Time-savings is real but context-dependent — which is why §5b.1 allows negative
saving.** The GitHub Copilot RCT (Peng et al., 2023) found the AI group **55.8%
faster** on a greenfield task (95% CI 21–89%); an ANZ Bank study ≈42%. But METR's
2025 RCT found **experienced** devs on large (~1M LOC) mature repos were **19%
slower** with AI — the strongest evidence that `human_minutes − agent_active_minutes`
genuinely goes negative on familiar, complex codebases and must be able to embarrass
the agent.
→ Peng et al. 2023: https://arxiv.org/pdf/2302.06590
→ METR 2025: https://arxiv.org/abs/2507.09089 ·
  https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/

**Self-reported savings are unreliable — which is why we ladder confidence and tag
`estimated`.** In the METR study devs forecast +24% and *post-hoc* still estimated
+20%, against an actual −19% — a ~39-point perception gap. A confident single number
would inherit that bias; surfacing `conf` and `method="estimated"` is the guard.
→ METR 2025 (above); "Dear Diary" workplace RCT: https://arxiv.org/pdf/2410.18334

**Effort-from-repos is an established method, but commit *timestamps* are dirty —
which is the §9 `cage calibrate` guard.** Estimating effort from version-control
activity is a real MSR field, yet the same literature documents that Git timestamps
are frequently unreliable. Hence: calibrate from commit *size* distributions, never
inter-commit *time*.
→ Robles et al., *Empirical Software Engineering* 2022:
  https://dl.acm.org/doi/abs/10.1007/s10664-022-10166-x
→ OpenStack MSR case study: https://dl.acm.org/doi/10.1145/2597073.2597107
→ Contribution Rate Imputation (2024): https://arxiv.org/pdf/2410.09285

**Honest limitation.** No source yields a validated "task-type → minutes" table;
software effort estimation has been hard and context-dependent for decades (COCOMO,
function points, story points are all acknowledged proxies). The §3.1 task-type
table is therefore a *defensible convention to be calibrated per repo*, not a
measured law — which is precisely the role the design assigns it.
