# CLI output spec — golden outputs per command, per state

**Status:** LIVE BEHAVIOR (plan Phases 1+2 shipped — output honesty). Every
code block below is **generated from the golden test fixtures** in
`tests/fixtures/goldens/` (asserted by `tests/test_output_spec.py` over seeded
ledgers), so the documented output and the tested output are one artifact and
cannot disagree. Regenerate after an intentional rendering change:

```sh
CAGE_BLESS_GOLDENS=1 python -m pytest tests/test_output_spec.py
python -m tools.docgen --target spec        # rewrites the blocks below
```

CI runs `python -m tools.docgen --check` — a shipped output change without a
regenerated spec fails the build (the skillgen pattern; rule recorded in
CLAUDE.md). Blocks *without* a `golden:` anchor (the Phase-3 `insights` group
listing and `study join`) are illustrative: the former documents an unshipped
regrouping, the latter's wiring + doctor output is machine-dependent by design
(it gets shape assertions instead of a byte golden).

Rules the outputs encode: tokens are the default, dollars opt-in (`--usd` /
`[display] usd`) · unpriced = `—` never `$0.0000` · saved/net columns only when
receipts exist (`--all-columns` restores) · refusals speak, in one voice,
instead of miming answers · every hint is runnable · footnotes/⚠/advice lines
are gated, deduped, and live at the bottom in fixed order.

---

## 1 · `cage report`

**R1 — DEFAULT: tokens only (dollars wait to be asked for)**

<!-- golden: R1 -->
```
$ cage report --by agent
Ledger by agent

agent    calls     tok in  tok out  saved tok
-------  -----  ---------  -------  ---------
copilot      4  1,968,011   96,212    100,000
claude       2    912,400   61,200    160,000
kiro         2    699,122        0          0
TOTAL        8  3,579,533  157,412    311,340

· kiro: input-only log — tok out not recorded
· 2 calls unpriced — matters when you view $ (`--usd`; cage prices unpriced)
```

No dollar columns, no pricing footnotes — tokens are the measurement. The
single muted unpriced line keeps the fix discoverable before dollars are ever
requested. `saved tok` still signal-gates (absent when no receipts), and the
kiro input-only caveat renders once, in token terms.

**R2 — `--usd` (or `[display] usd = true`): the dollar view**

<!-- golden: R2 -->
```
$ cage report --by agent --usd
Ledger by agent · usd

agent    calls     tok in  tok out                   cost    saved        net
-------  -----  ---------  -------  ---------------------  -------  ---------
copilot      4  1,968,011   96,212                $6.6783  $0.3000   -$6.3783
claude       2    912,400   61,200                $3.6552  $0.4800   -$3.1752
kiro         2    699,122        0                $2.0974  $0.0000   -$2.0974
TOTAL        8  3,579,533  157,412  $12.4308 (+ unpriced)  $0.9340  -$11.4968

≈ priced by family (approximate — no exact price row):
  copilot/claude-sonnet-4.6 → claude-sonnet-4-6
≈ graphify priced at task model (anthropic/claude-sonnet-4-6)
· kiro: input-only log — cost understated
⚠ 2 calls (164,353 tokens) UNPRICED — totals understated
  fix: cage prices alias - 'copilot/auto' --to <provider>/<model>   # route the router pseudo-model explicitly
```

Pricing footnotes (family approximation, the ladder rung) live here, where
dollars are shown, as does the full ⚠ UNPRICED block with one runnable fix per
unpriced model. saved/net still signal-gate. A negative net with real receipts
renders unconditionally — that is the product.

**R3 — `--usd` with no receipts (both rules compose)**

<!-- golden: R3 -->
```
$ cage report --by agent --usd
Ledger by agent · usd

agent    calls     tok in  tok out      cost
-------  -----  ---------  -------  --------
copilot      1  1,968,011   96,212   $7.3472
claude       1    912,400   61,200   $3.6552
TOTAL        2  2,880,411  157,412  $11.0024

≈ priced by family (approximate — no exact price row):
  copilot/claude-sonnet-4.6 → claude-sonnet-4-6
· no savings receipts in this window — wire a tool to measure savings
  (`cage query receipts` explains)
```

**R4 — `--usd --by model` with unpriced rows (cells say `—`, the TOTAL says the gap)**

<!-- golden: R4 -->
```
$ cage report --by model --usd
Ledger by model · usd

model                      calls     tok in  tok out                   cost
-------------------------  -----  ---------  -------  ---------------------
copilot/claude-sonnet-4.6      2  1,818,314   81,556                $6.6783
claude-sonnet-4-6              2    912,400   61,200                $3.6552
agent (kiro)                   2    699,122        0                $2.0974
copilot/auto                   2    149,697   14,656                      —
TOTAL                          8  3,579,533  157,412  $12.4308 (+ unpriced)

≈ priced by family (approximate — no exact price row):
  copilot/claude-sonnet-4.6 → claude-sonnet-4-6
· kiro: input-only log — cost understated
⚠ 2 calls (164,353 tokens) UNPRICED — totals understated
  fix: cage prices alias - 'copilot/auto' --to <provider>/<model>   # route the router pseudo-model explicitly
```

A group whose every call refused to price renders `—`, never `$0.0000`; the
TOTAL carries `(+ unpriced)`. A generic model bucket (kiro's coarse log stamps
`agent`) names its agent. The 0-call receipt-only bucket never renders as a
row — its saving still counts in TOTAL.

**R5 — empty ledger**

<!-- golden: R5 -->
```
$ cage report
No calls recorded yet.

next: cage import        pull every agent's usage into the ledger
      cage doctor        check capture is wired and healthy
```

An empty *slice* of a non-empty ledger names the active filters instead
(`No calls match scope 'web' — the filter is empty, not the ledger.`).

**R6 — stale advice (gated: appears only when actionable, always last)**

<!-- golden: R6 -->
```
$ cage report --by agent
Ledger by agent

agent   calls   tok in  tok out  saved tok
------  -----  -------  -------  ---------
claude      1  912,400   61,200     80,000
TOTAL       1  912,400   61,200     80,000

· last import: 3d ago — `cage import` to refresh
· bundled prices are 61 days old — check for a newer cage release
  (`cage query prices-freshness` explains)
```

The `last import` line renders only past the staleness gate (policy
`[capture] import_stale_hours`, default 24h); the bundle-age line is
data-relative (anchored on the newest ledger `ts`, never the wall clock).

**R7 — capture health: installed but capturing nothing**

<!-- golden: R7 -->
```
$ cage report --by agent
Ledger by agent

agent    calls     tok in  tok out
-------  -----  ---------  -------
copilot      1  1,968,011   96,212
claude       1    912,400   61,200
TOTAL        2  2,880,411  157,412

⚠ kiro: ~/.kiro exists but ~/.kiro/sessions matched 0 files — capture is off for this agent.
  cage doctor --paths      (if you don't use kiro: [sources.kiro] replace=true, paths=[] )
· no savings receipts in this window — wire a tool to measure savings
  (`cage query receipts` explains)
```

The **capture-health ⚠** (docs/capture-health.md) is triple-gated: it fires for an
agent only when its home marker exists **and** its log matched 0 files at the last
import **and** it has never contributed a row to the ledger. That third clause makes
it self-silencing — one captured row and it never warns again — so it only ever names
an agent that is genuinely capturing nothing. The verdict is recorded at import
(`cursors.json["_health"]`) and rendered from that cache; `cage report` stays a pure
function of its inputs. `cage doctor` surfaces the same line. Opt out of an agent you
don't use with the documented `[sources.<agent>] replace=true, paths=[]` stanza.

---

## 2 · `cage insights …` (Phase 3 — not yet shipped; today's verbs shown per block)

**I1 — bare group (ILLUSTRATIVE — ships with the Phase 3 CLI tiering)**

```
$ cage insights
insights — derived views over the ledger (all $0, deterministic)

  attrib       what each tool saved (marginal, by pipeline order)
  matrix       counterfactual grid: every tool on/off combination
  roi          savings vs each tool's own cost
  verdict      one answer: is <tool> paying for itself?
  compare      observed task cost by tool stack
  estimate     predicted cost band for a labeled task
  calibration  how accurate estimates and heuristics have been
  trend        saved $ and hours over time
  why          which calls cost the most, and why
  forecast     month-end spend projection
  regression   cost-per-call drift alarm
  recommend    cheapest tool combination, from your own history
```

**I2 — `verdict graphify`, SAVING**

<!-- golden: I2 -->
```
$ cage insights verdict graphify
VERDICT: graphify is SAVING ≈ $1.3714/mo net (modeled)

inputs (each with its own method tag):
  · marginal saving (attrib): task 't_v4': 80,000 tok · $0.2400 (modeled)
  · roi: saved $0.9600 − own cost $0.0000 = net +$0.9600 over 4 receipt(s) (modeled)
  · trend (agent-vs-human, ledger-wide): INSUFFICIENT DATA — fewer than 2 weekly buckets on the human axis
  · cost drift (regression): stable (+0%) (measured)
  · redo-rate (quality): INSUFFICIENT DATA — no task outcomes recorded
  · break-even: each receipt nets +$0.2400 on average — net-positive from the first receipt (derived from roi)

total cost: agent $1.6800 + human — (no attested minutes and no turn-gap data in scope; only logs with per-turn timestamps carry gap_ms)

verdict composes existing views only — it computes no new statistics;
a missing input reads INSUFFICIENT DATA, never an approximation.
```

**I3 — `verdict graphify`, COSTING (the negative net renders, always)**

<!-- golden: I3 -->
```
$ cage insights verdict graphify
VERDICT: graphify is COSTING ≈ $2.1429/mo net (modeled)

inputs (each with its own method tag):
  · marginal saving (attrib): task 't_n2': 50,000 tok · $0.1500 (modeled)
  · roi: saved $0.3000 − own cost $0.8000 = net -$0.5000 over 2 receipt(s) (modeled)
  · trend (agent-vs-human, ledger-wide): INSUFFICIENT DATA — fewer than 2 weekly buckets on the human axis
  · cost drift (regression): INSUFFICIENT DATA — not enough history on both sides of the window
  · redo-rate (quality): INSUFFICIENT DATA — no task outcomes recorded
  · break-even: each receipt nets -$0.2500 on average — no receipt volume reaches break-even at current costs (derived from roi)

total cost: agent $0.4200 + human — (no attested minutes and no turn-gap data in scope; only logs with per-turn timestamps carry gap_ms)

verdict composes existing views only — it computes no new statistics;
a missing input reads INSUFFICIENT DATA, never an approximation.
```

**I4 — `verdict <tool>`, INSUFFICIENT DATA**

<!-- golden: I4 -->
```
$ cage insights verdict fux
VERDICT: INSUFFICIENT DATA — no receipts recorded for 'fux'.

A verdict composes recorded receipts; teach the tool to emit them (`cage query receipts`), then re-run.

total cost: agent $12.4308 + human — (no attested minutes and no turn-gap data in scope; only logs with per-turn timestamps carry gap_ms)
```

**I5 — `compare`, groups + one refusal**

<!-- golden: I5 -->
```
$ cage insights compare --label docfix --agent-only
Stack comparison · closed tasks · measured group totals (tokens = in+out per task)

stack         n                   median tok        IQR tok  median $            IQR $
------------  -  ---------------------------  -------------  --------  ---------------
agent-only    5                       14,200  13,300–15,100   $0.0606  $0.0579–$0.0633
fux+graphify  2  insufficient data (n=2 < 5)
graphify      5                        6,900    6,300–7,500   $0.0339  $0.0321–$0.0357

Δ graphify vs agent-only: -7,300 tok · -$0.0267 per task (median, estimated)
  ⚠ observed difference across different tasks — not a controlled experiment; stacks are per-task observed receipt sets, not configured pipelines
```

**I6 — `estimate --label docfix`, band, then refusal case**

<!-- golden: I6a -->
```
$ cage insights estimate --label docfix
Estimate · label=docfix

  n = 12 matching closed tasks
  tokens: median 7,800 · IQR 6,150–13,525
  usd:    median $0.0366 · IQR $0.0316–$0.0586
  method: modeled — history applied to an unrun task, never an invoice
  confidence: none self-reported — `cage insights calibration` measures the hit-rate
```

<!-- golden: I6b -->
```
$ cage insights estimate --label refactor
Estimate · label=refactor

insufficient history (n=3 < 5 matching closed tasks) — refusing to print a band over noise
close more matching tasks (`cage human outcome <task>`) or widen the keys.
```

**I7 — `matrix`, DEFAULT: token grid (always renders)**

<!-- golden: I7 -->
```
$ cage insights matrix --task t_9f31
Counterfactual matrix · task t_9f31

graphify  input tok  source
--------  ---------  --------
✗            22,171  modeled
✓             1,660  measured

full stack vs all-off: ✓ smaller (22,171 → 1,660 tok)
```

**I8 — `matrix --usd`: cost column added, or explained in one line**

<!-- golden: I8a -->
```
$ cage insights matrix --task t_9f31 --usd
Counterfactual matrix · task t_9f31 · base model anthropic/claude-sonnet-4-6

graphify  input tok     cost  source
--------  ---------  -------  --------
✗            22,171  $0.0665  modeled
✓             1,660  $0.0050  measured

full stack vs all-off: ✓ cheaper ($0.0665 → $0.0050)
```

<!-- golden: I8b -->
```
$ cage insights matrix --usd
Counterfactual matrix · task None

graphify  input tok  source
--------  ---------  --------
✗            22,171  modeled
✓             1,660  measured

full stack vs all-off: ✓ smaller (22,171 → 1,660 tok)
· cost column unavailable — no priceable model (no task join, no route)
  fix: cage prices route-tool graphify --to <provider>/<model>
```

The token grid never refuses; only the *dollar interpretation* explains its
absence. This replaces the earlier full-view INSUFFICIENT DATA for matrix.
`--human` implies `--usd` (the anchor row and vs-human columns are dollars).

---

## 3 · `cage prices …`

**P1 — `list` (origins, meta, routes, gated recommendation)**

<!-- golden: P1 -->
```
$ cage prices list
prices — bundled 2026-07-14 (cage 0.25.0) · project 2026-07-14 (<project>/.cage/policy.toml)

provider   model               in $/M  out $/M  cache $/M  origin  wins
---------  ------------------  ------  -------  ---------  ------  -------
anthropic  claude-3-5-haiku       0.8        4       0.08  both    project
anthropic  claude-3-5-sonnet        3       15        0.3  both    project
anthropic  claude-3-7-sonnet        3       15        0.3  both    project
anthropic  claude-3-haiku        0.25     1.25      0.025  both    project
anthropic  claude-3-opus           15       75        1.5  both    project
anthropic  claude-3-sonnet          3       15        0.3  both    project
anthropic  claude-fable-5          10       50          1  both    project
anthropic  claude-haiku-3-5       0.8        4       0.08  both    project
anthropic  claude-haiku-4-5         1        5        0.1  both    project
anthropic  claude-mythos-5         10       50          1  both    project
anthropic  claude-opus-4           15       75        1.5  both    project
anthropic  claude-opus-4-1         15       75        1.5  both    project
anthropic  claude-opus-4-5          5       25        0.5  both    project
anthropic  claude-opus-4-6          5       25        0.5  both    project
anthropic  claude-opus-4-7          5       25        0.5  both    project
anthropic  claude-opus-4-8          5       25        0.5  both    project
anthropic  claude-sonnet-4          3       15        0.3  both    project
anthropic  claude-sonnet-4-5        3       15        0.3  both    project
anthropic  claude-sonnet-4-6        3       15        0.3  both    project
anthropic  claude-sonnet-5          3       15        0.3  both    project
kiro       agent                    3       15        0.3  both    project
openai     codex-mini-latest      1.5        6      0.375  both    project
openai     gpt-4.1                  2        8        0.5  both    project
openai     gpt-4.1-mini           0.4      1.6        0.1  both    project
openai     gpt-4.1-nano           0.1      0.4      0.025  both    project
openai     gpt-4o                 2.5       10       1.25  both    project
openai     gpt-4o-mini           0.15      0.6      0.075  both    project
openai     gpt-5                 1.25       10      0.125  both    project
openai     gpt-5-codex           1.25       10      0.125  both    project
openai     gpt-5-mini            0.25        2      0.025  both    project
openai     gpt-5-nano            0.05      0.4      0.005  both    project
openai     gpt-5-pro               15      120         15  both    project
openai     gpt-5.1               1.25       10      0.125  both    project
openai     gpt-5.1-codex         1.25       10      0.125  both    project
openai     gpt-5.1-codex-max     1.25       10      0.125  both    project
openai     gpt-5.1-codex-mini    0.25        2      0.025  both    project
openai     gpt-5.2               1.75       14      0.175  both    project
openai     gpt-5.2-codex         1.75       14      0.175  both    project
openai     gpt-5.3-codex          2.5       10       0.25  both    project
openai     gpt-5.4                2.5       15       0.25  both    project
openai     gpt-5.4-mini          0.75      4.5      0.075  both    project
openai     gpt-5.4-nano           0.2     1.25       0.02  both    project
openai     gpt-5.4-pro             30      180         30  both    project
openai     gpt-5.5                  5       30        0.5  both    project
openai     gpt-5.5-pro             30      180         30  both    project
openai     gpt-5.6-luna             1        6        0.1  both    project
openai     gpt-5.6-sol              5       30        0.5  both    project
openai     gpt-5.6-terra          2.5       15       0.25  both    project
openai     o3                       2        8        0.5  both    project
openai     o3-mini                1.1      4.4       0.55  both    project
openai     o4-mini                1.1      4.4      0.275  both    project

aliases (explicit routing — renders as an alias footnote, never exact):
  —/copilot/auto → anthropic/claude-sonnet-4-6

tool routes ([tools.<tool>] price_at — prices call-less token receipts):
  graphify → anthropic/claude-sonnet-4-6
```

**P2 — `unpriced`, findings vs clean**

<!-- golden: P2a -->
```
$ cage prices unpriced
  —/copilot/auto   2 calls   164,353 tokens
    fix: cage prices alias - 'copilot/auto' --to <provider>/<model>   # route the router pseudo-model explicitly

⚠ 2 calls (164,353 tokens) billing $0 — totals understated until priced.
cage never fetches prices (no network) — check the vendor's pricing page, fill in the line, run it. `cage query unpriced` explains.
```

<!-- golden: P2b -->
```
$ cage prices unpriced
✔ every recorded call prices — nothing is billing $0.
```

**P3 — `set` / `route-tool` writes (before/after, idempotent)**

<!-- golden: P3a -->
```
$ cage prices set anthropic claude-sonnet-4.6 --input 3.00 --output 15.00 --cache-read 0.30
✔ [prices.anthropic."claude-sonnet-4.6"] written to the cage-managed block — <project>/.cage/policy.toml
  before: (none)
  after:  input=3 output=15 cache_read=0.3
  derived views re-price immediately — the ledger is never rewritten. (Self-costed rows and receipts keep their stored figures.)
```

<!-- golden: P3b -->
```
$ cage prices route-tool graphify --to anthropic/claude-sonnet-4-6
✔ [tools.graphify] written to the cage-managed block — <project>/.cage/policy.toml
  before: —
  after:  price_at = "anthropic/claude-sonnet-4-6"
  call-less token receipts from this tool now price via rung 1 (`cage query receipt-pricing`).
  derived views re-price immediately — the ledger is never rewritten. (Self-costed rows and receipts keep their stored figures.)
```

**P4 — `sync`, dry-run → apply → already-synced**

<!-- golden: P4a -->
```
$ cage prices sync
prices sync — bundled 2026-07-14 vs project 2020-01-01

· 51 project rows equal to the bundle — in sync

dry-run (house pattern) — `--update` applies bundled values to rows you confirm with --yes; customized rows are never clobbered.
· bundled prices are newer (2026-07-14 > 2020-01-01) — run 'cage prices sync'
```

<!-- golden: P4b -->
```
$ cage prices sync --update
prices sync — bundled 2026-07-14 vs project 2020-01-01

· 51 project rows equal to the bundle — in sync

✔ [meta] restamped to bundled 2026-07-14
```

<!-- golden: P4c -->
```
$ cage prices sync
prices sync — bundled 2026-07-14 vs project 2026-07-14

· 51 project rows equal to the bundle — in sync

✔ nothing to do — project prices match the installed bundle.
```

---

## 4 · `cage study …`

**S1/S2 — `join` / `start` / `stop` (ILLUSTRATIVE — join wires agents and runs
doctor, whose output is machine-dependent by design; shape-asserted in
`tests/test_output_spec.py` instead of byte-pinned)**

```
$ cage study join baseline
✔ enrolled: machine m_4c2a91f0e6b7d3a8 · phase 'baseline' started · wired: claude, codex, copilot, kiro
[ doctor check lines for this machine ]

$ cage study start plugin
✔ phase 'plugin' started (machine m_4c2a91f0e6b7d3a8) — rows from now on are assigned to it by their own timestamps

$ cage study stop
✔ phase stopped — rows after this marker are unphased until the next start
```

**S3 — `report`, healthy**

<!-- golden: S3 -->
```
$ cage study report --agent-only
Fleet study · phases: baseline → plugin

coverage (days with rows — gaps kill studies, so they print first):
  machine m_01aa000000000000
    baseline     5 day(s) · agents: claude · ⚠ gap days: 2026-07-06
    plugin       5 day(s) · agents: claude
  machine m_02aa000000000000
    baseline     5 day(s) · agents: claude · ⚠ gap days: 2026-07-06
    plugin       5 day(s) · agents: claude
  machine m_03aa000000000000
    baseline     5 day(s) · agents: claude · ⚠ gap days: 2026-07-06
    plugin       5 day(s) · agents: claude
  machine m_04aa000000000000
    baseline     5 day(s) · agents: claude · ⚠ gap days: 2026-07-06
    plugin       5 day(s) · agents: claude
  machine m_05aa000000000000
    baseline     5 day(s) · agents: claude · ⚠ gap days: 2026-07-06
    plugin       5 day(s) · agents: claude
  machine m_06aa000000000000
    baseline     5 day(s) · agents: claude
    plugin       MISSING — no rows in this phase

paired-by-machine delta (plugin − baseline, median of per-machine deltas, n=5 machines):
  -94,000 tok/day · -$0.3540/day per machine (estimated)
  ⚠ observed across different weeks with different work mixes — recorded phase intent, not a randomized experiment

pooled machine-days per phase (measured):
  baseline     n=30 days · median 245,000 tok · $0.9750 (IQR $0.9300–$1.0200)
  plugin       n=25 days · median 146,000 tok · $0.6060 (IQR $0.5880–$0.6240)
```

**S4 — `report`, refusal**

<!-- golden: S4 -->
```
$ cage study report --agent-only
Fleet study · phases: baseline → plugin

coverage (days with rows — gaps kill studies, so they print first):
  machine m_01aa000000000000
    baseline     5 day(s) · agents: claude · ⚠ gap days: 2026-07-06
    plugin       5 day(s) · agents: claude
  machine m_02aa000000000000
    baseline     5 day(s) · agents: claude · ⚠ gap days: 2026-07-06
    plugin       5 day(s) · agents: claude
  machine m_03aa000000000000
    baseline     5 day(s) · agents: claude · ⚠ gap days: 2026-07-06
    plugin       5 day(s) · agents: claude
  machine m_04aa000000000000
    baseline     5 day(s) · agents: claude
    plugin       MISSING — no rows in this phase

paired delta: insufficient machines with both phases (n=3 < 5) — the command explains, it never numbers.

pooled machine-days per phase (measured):
  baseline     n=20 days · median 235,000 tok · $0.9450 (IQR $0.9225–$0.9675)
  plugin       n=15 days · median 140,000 tok · $0.5880 (IQR $0.5700–$0.6060)
```

---

## 5 · `cage policy …`

**P5 — `diff` (dry-run categorized)**

<!-- golden: P5 -->
```
$ cage policy diff
policy sync — bundled v0.26.0 vs project v0.19.0

· 29 project keys equal to the bundle — in sync

pricing tables — delegated to `cage prices sync`:
  prices sync — bundled 2026-07-14 vs project 2026-07-14
  
  · 51 project rows equal to the bundle — in sync
  
  ✔ nothing to do — project prices match the installed bundle.

dry-run — `--apply` writes adds/updates and stamps [meta] policy_version; customized values are never modified, orphans never deleted.
· bundled policy defaults are newer (v0.26.0 > v0.19.0) — run 'cage policy sync'
```

**P6 — `sync --apply` and steady state**

<!-- golden: P6a -->
```
$ cage policy sync --apply
policy sync — bundled v0.26.0 vs project v0.19.0

· 29 project keys equal to the bundle — in sync

pricing tables — delegated to `cage prices sync`:
  prices sync — bundled 2026-07-14 vs project 2026-07-14
  
  · 51 project rows equal to the bundle — in sync
  
  ✔ nothing to do — project prices match the installed bundle.

✔ [meta] policy_version stamped v0.26.0
```

<!-- golden: P6b -->
```
$ cage policy sync
policy sync — bundled v0.26.0 vs project v0.26.0

· 29 project keys equal to the bundle — in sync

pricing tables — delegated to `cage prices sync`:
  prices sync — bundled 2026-07-14 vs project 2026-07-14
  
  · 51 project rows equal to the bundle — in sync
  
  ✔ nothing to do — project prices match the installed bundle.

✔ nothing to do — project policy matches the installed bundle.
```

---

## 6 · bare `cage` (the overview headline)

**O1 — DEFAULT: tokens**

<!-- golden: O1 -->
```
3,736,945 tokens  ·  8 calls   (all time)
  drill:  cage report --by agent   ·   cage insights why <call>   ·   cage insights attrib --task <t>
· 2 calls unpriced — matters when you view $ (`--usd`; cage prices unpriced)
```

**O2 — `--usd` (or `[display] usd = true`)**

<!-- golden: O2 -->
```
$ cage --usd
spent $12.4308  ·  saved $0.9340  ·  net -$11.4968  ·  3,736,945 tokens   (all time)
  drill:  cage report --by agent   ·   cage insights why <call>   ·   cage insights attrib --task <t>
⚠ 2 calls (164,353 tokens) UNPRICED — totals understated; run 'cage prices unpriced' (`cage query unpriced` explains)
```

---

## Cross-cutting rules the outputs obey (tested once, everywhere)

1. **Tokens default, dollars opt-in:** `report`, `matrix`, and the bare `cage`
   headline render tokens only until `--usd` (or `[display] usd = true`) asks
   for currency; pricing footnotes and the full ⚠ block belong to the `--usd`
   view — the token view carries at most one muted unpriced pointer.
   Money-native views (`budget`, `roi`, `verdict`, `compare`, `estimate`)
   always show dollars.
2. `—` is the only rendering of "couldn't price"; `$0.0000` always means a
   real zero. A net over a dashed cost is itself `—`.
3. A dollar figure never appears without a method context (footnote, tag, or
   source column) somewhere on screen.
4. Every ⚠/fix line is copy-paste runnable.
5. Refusals name the gate (`MIN_*`), the have-vs-need, and the next action;
   the matrix token grid never refuses — only its cost column explains
   absence (I8).
6. Advice lines (import age, price freshness) render at most once, at the
   bottom, only when actionable.
7. Signal-gating drops columns; `--all-columns` restores; CSV never gates
   and always carries the full schema including dollars.
8. Negative nets with real receipts render unconditionally (I3).
