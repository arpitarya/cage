# Plan: output honesty & readability · signal-gated dollars · CLI tiering · [sources] · backlog sweep

**Status:** plan of record for the next work cycle — each phase below graduates
to its own `<feature>.handoff.md` + `.prompt.md` pair (docs lifecycle) before
implementation. Driven by field output from a real second project
(wealth-management-hub, cage v0.23 against a v0.19-era policy).

**Golden mockups:** [docs/cli-output-spec.md](cli-output-spec.md) shows the
target output for report / insights / prices / study / policy across every
state (healthy, no-signal, tokens-only, unpriced, refusal, empty) — the
Phase 1–3 handoff pairs implement against it and golden tests pin it.
**Doc lifecycle for the spec (binding on the Phase 1–3 pairs):** (1) every
mockup becomes a golden test over a seeded ledger; (2) the spec's code blocks
are regenerated FROM those golden fixtures (build-time renderer + `--check`
CI drift gate — one artifact, docs and tests can't disagree); (3) the same
change flips the spec's status line to "live behavior" and links it from the
README beside the CSV column contracts; (4) from then on the CLAUDE.md rule
holds: a shipped output change without a spec update is a release bug.

**Field evidence this plan answers:** `saved $0.0000 / net -$16.11` rendered in
a project with zero receipts · `copilot/auto` calls shown as `$0.0000` (reads
"free", means "unpriceable") · matrix printing `$0.0000 → $0.0000` with
`task None · unpriced model` · an empty `-` agent row · ~45 top-level
subcommands for a tool whose daily loop is five · agent log paths configurable
only via env vars.

---

## Phase 1 — Output honesty & readability (report/matrix/attrib surfaces)

The debate's key finding: the worst output problems are *ambiguity*, not
clutter — `$0.0000` conflates "free" with "couldn't price".

1. **Unpriced renders `—`, never `$0.0000`** — in every table cell (report,
   `--by model/agent`, matrix, roi). The ⚠ UNPRICED block keeps the counts and
   runnable hints; the cell itself stops impersonating a price. CSV keeps an
   explicit empty-with-`priced_via=none` (never the string `—` in data).
2. **Matrix refuses instead of miming** — no priceable model / no task join ⇒
   `INSUFFICIENT DATA — no priceable model for counterfactual cells; see cage
   query receipt-pricing` (the min-n refusal voice), not a $0→$0 table.
3. **Empty-bucket rows dropped** — the `-` agent row with 0 calls (and any
   0-call bucket) never renders; tested.
4. **Footnote & hint dedupe** — one family-pricing footnote, one ⚠ block, one
   freshness/import note per command invocation, in a fixed order at the
   bottom; no repetition between sections of the same command.
5. **Kiro fidelity caveat** — when kiro rows show tokens-in but zero
   tokens-out (the coarse log), the report footnotes `kiro: input-only log —
   cost understated` once. Honesty, not noise: only when kiro rows exist.
6. **`last import: N ago`** line becomes staleness-gated (only when older than
   a threshold, policy-preferred constant) — it's advice, not a banner.

*Byte-identity caveat:* this phase deliberately changes rendered text — golden
tests update with it; CSV column contracts unchanged except `priced_via`
semantics already shipped. Determinism law untouched.

## Phase 2 — Signal-gated dollars (the "optional $" ask, done honestly)

Decided rule: **columns appear when their signal exists, and never otherwise.**

1. `saved`/`net` columns render only when ≥1 receipt exists in the reporting
   window; otherwise the table is spend-only plus one line: `no savings
   receipts in this window — wire a tool (cage query receipts) to measure
   savings`. A spend-only project stops seeing all-zero saved columns and
   alarming `net -$X` that just restates cost.
2. **Hard line (non-negotiable): a negative net with real receipts is never
   suppressed, smoothed, or hidden.** The metric that can embarrass a tool is
   the product. This phase removes *unmeasured* noise, not unwelcome results.
3. Same gating for the human total-cost line (already `--agent-only`-guarded)
   and trend's saved-hours (renders only when attention/attested data exists —
   already mostly true; audit and test).
4. `--all-columns` escape hatch forces the full grid for scripts that want
   fixed shape; CSV always emits the full column set (machine consumers get
   stable schemas; gating is a *text-view* affordance).
5. **Tokens are the default; dollars are opt-in (decided, supersedes the
   earlier toggle direction):** `cage report` and `cage insights matrix`
   render **tokens-only by default** — tokens are the measurement, dollars
   are an interpretation you ask for. `--usd` on the invocation (or
   `[display] usd = true` in policy for always-on; flag > env > policy) adds
   the dollar columns. Consequences handled: pricing footnotes (family
   approximation, the full UNPRICED ⚠ block) render only in the `--usd`
   view — the token default carries at most one muted line (`· 22 calls
   unpriced — matters when you view $; cage prices unpriced`); the matrix
   token grid always renders, and `--usd` either adds the cost column or
   appends one line explaining why it can't (`cost column unavailable — no
   priceable model; fix: cage prices route-tool …`) instead of refusing the
   whole view. **Money-native views keep dollars unconditionally** —
   `budget`, `roi`, `verdict`, `compare`, `estimate`, `trend`'s $ series are
   dollar questions; asked without prices they refuse per the existing law.
   Pricing always computes underneath (budget guards, UNPRICED detection,
   verdict) regardless of display. CSV unaffected — full schema, always.
   Signal-gating (2.1) composes: gating decides whether saved/net have
   meaning; the default decides that even meaningful dollars wait to be
   asked for.

## Phase 3 — CLI tiering & consolidation (fewer doors, same rooms)

Debate verdict: tier and group, don't amputate — capture/diagnostic surface
stays; the *help surface* shrinks to the daily loop.

1. **Tier 1 (bare `cage --help`):** `report`, `import`, `setup`, `doctor`,
   `query` + group names. Everything answers in ≤ one screen.
2. **`init` merges into `setup` (decided):** `cage init` disappears as a
   top-level verb; `cage setup` always ensures `.cage/` exists first (it
   already scaffolds via `--project-only` — this makes scaffolding
   unconditional step one). One front door for "make this project metered".
   `setup --global` keeps seeding `~/.cage`.
3. **Groups:** existing `prices`/`study`/`policy` pattern extended —
   `cage insights <attrib|matrix|roi|verdict|budget|compare|estimate|calibration|
   trend|why|forecast|regression|recommend>` · `cage human <show|record|
   outcome|quality>` (absorbs `human-record`, `outcome`, `quality`) ·
   `cage authorship <origin|verify|notes-sync|ledger-sync>` ·
   `cage data <export|cleanup|limits|watch|serve|proxy|meter|graphify>`.
   `hook-*` verbs vanish from help (plumbing; still callable — wired files
   reference them); so do `mcp` (spawned by wired configs), `debug`
   (diagnostic), and `demo` (README-referenced) — top-level and callable, just
   off the front door. `graphify` stays a hidden `data` subcommand (interceptor
   seam), omitted from the help index like `hook-*`.
   **(Amended at implementation time, human-authorized: `budget` joined
   `insights`; `authorship` added as a group for the who-wrote-what surface;
   `quality` landed as `human quality`; `mcp`/`debug`/`demo` stay hidden
   top-level. The mock below is updated to match.)**
4. **Clean break, no aliases (decided — pre-1.0):** old top-level verbs are
   REMOVED, not aliased. Superseded verbs deleted outright (`init`,
   `import-codex`, `import-claude`, `human-record`, standalone
   `outcome`/`quality`). The CHANGELOG carries a full old→new mapping table;
   an unknown old verb errors with the mapping hint (`error: 'attrib' is now
   'cage insights attrib'`) for one release — an error with directions, not
   an alias. skillgen regenerates every skill/prompt/steering asset and the
   MCP surface in the same change, so agents never see the old names.
   **Data-compat fence:** "remove old code" never includes readers of
   recorded data — legacy unpartitioned ledger files, pre-`gap_ms`/`machine`
   rows, and old bundle formats keep parsing until an explicit migration
   story ships. Code doors may break before 1.0; recorded ledgers may not.
5. **Scope fence:** zero behavior changes beyond the verb map — this phase
   moves doors. Any temptation to "improve while moving" is out of scope by
   construction.
6. OPEN QUESTION for the handoff: `cage` bare (no args) currently prints the
   overview — keep as the sixth tier-1 surface? Default: yes, unchanged.

**What the CLI looks like after Phase 3:**

```
$ cage --help
cage — measure what your AI agents spend, prove what your tools save

daily:
  report      where the spend went (tokens; add $ views via [display])
  import      pull every agent's usage into the ledger
  setup       make this project (or --global) metered — scaffold + wire
  doctor      is capture healthy? (--paths shows every probed location)
  query       ask cage how any number or mechanism works

groups (run any group name for its commands):
  insights    attrib · matrix · roi · verdict · budget · compare · estimate ·
              calibration · trend · why · forecast · regression · recommend
  human       show · record · outcome · quality
  authorship  origin · verify · notes-sync · ledger-sync
  prices      list · unpriced · set · alias · route-tool · sync
  study       join · start · stop · report · id
  policy      diff · sync
  data        export · cleanup · limits · watch · serve · proxy · meter

$ cage report --since 7d          # the daily number
$ cage insights verdict graphify  # is this tool paying for itself?
$ cage human record 12m           # attest human time on the open task
$ cage study join baseline        # enroll this laptop in the fleet study
$ cage prices route-tool graphify --to copilot/claude-sonnet-4.6
```

Five daily doors + seven groups on the front; everything else one group deep,
grouped by the question being asked. (`mcp`/`debug`/`demo` and `hook-*` stay
callable but off the front door.)

## Phase 4 — `[sources]` in policy.toml (configurable import paths)

1. New policy table, one or more paths per agent, additive:
   `[sources.claude] paths = ["~/custom/claude-logs"]` · also arbitrary
   extra tools: `[sources.<name>] paths=[...], format="claude|codex|copilot|kiro"`
   (reuse an existing parser by declared format — new formats stay out of
   scope).
2. **Precedence:** env override > policy `[sources]` > built-in registry
   (`paths.agent_log_sources()`); merged, not replaced, unless
   `replace = true` per table.
3. `cage doctor --paths` names each candidate's provenance
   (`built-in | policy | env`); the probe report is the debugging surface.
4. **Portability guard:** `[sources]` is machine-specific by nature —
   `~`-expansion supported; doctor's portability check warns when a
   *committed project* policy carries absolute machine paths in `[sources]`
   (advice: put them in the global `~/.cage/policy.toml`).
5. `policy sync` (pending pair) treats `[sources]` as user-owned (never
   added/updated from bundle — the bundle ships none).

## Phase 5 — Backlog sweep (from the full history of this collaboration)

In priority order; small items batch into one "papercuts" pair:

1. **Pending pairs first (already specced):** `prices-route-tool`
   (+ fold in: **matrix as a ladder consumer** — the v0.23 gap the field
   output exposed, and the **auto-resolution investigation** below) →
   `pricing-freshness` → `policy-sync`.
2. **`copilot/auto` — capture the resolved model, don't alias the guess
   (investigate-first):** inspect the real captured copilot session log: if
   the response/event carries the model id that `auto` actually resolved to
   (most logs do), the parser prefers it and `auto` largely disappears from
   the ledger at capture time — measured truth beating a routed guess. Rows
   already imported as `auto` stay as recorded (ledger never rewritten) and
   keep pricing via the alias; the alias remains only for logs that genuinely
   never name the resolved model. If the log truly carries nothing, document
   that and the alias stands. Rider on the route-tool pair.
3. **Papercuts pair:** empty-agent row (Phase 1.3 if not landed sooner) ·
   `--scope` empty-slice message (finding #11, old) · copilot/auto bundled
   alias *example* comment audit.
4. **Field validation debt (needs humans/machines, not code):** Windows
   manual checklist on a real Windows laptop · WDAC/AppLocker endpoint run of
   the restricted-env checklist · replace any fixture whose upstream format
   drifts.
5. **Calibration-gated future work (wait for data):** label-stratified paired
   deltas in `study report` · per-label estimate bands · rung-2 after-ts
   revisit — all blocked on `cage calibration` accumulating enough attested
   samples to justify them; revisit when `calibration` clears its min-n on
   real usage.
6. **Formula surfaces — one registry, three renderings (small, high-leverage):**
   the explain registry (`explain_data.py` calculation entries) becomes the
   single source for THREE synchronized surfaces: (a) `cage query` (live, on
   box — already true); (b) **`docs/formulas.md`, the formula catalogue** —
   exists today (README-linked, indexed in docs/README.md), maintained
   manually under the CLAUDE.md rule ("a shipped formula change without a
   catalogue update is a release bug"), to be **generator-rendered** from the
   registry with a `--check` CI drift gate (the skillgen pattern) so the rule
   becomes mechanical instead of remembered; (c) formula comments in the
   bundled policy.toml beside each knob (`# usd = minutes / 60 × rate` above
   `[human] rate`), same generator, carried into project policies by `policy
   sync`'s normal add path. Decided boundaries: formulas are NEVER editable
   config (an expression evaluator breaks the method-tag trust story and the
   $0 posture), and honesty rails stay constants (`MIN_COMPARE_N`,
   `MIN_ESTIMATE_N`, `CHARS_PER_TOKEN` are not knobs — a threshold you can
   lower is a refusal you can silence). Rider on the papercuts pair or the
   output-honesty pair, whichever lands first.
7. **Query-pattern packaging** (`docs/query-pattern.md` + `querykit.py`) —
   parked until an outside-the-family consumer exists; no action.

## Sequencing

`prices-route-tool` (+matrix rider) → `pricing-freshness` → `policy-sync` →
**Phase 1+2 as one pair** (`output-honesty.handoff.md` — they touch the same
render code; one review) → **Phase 3 as its own pair** (biggest churn,
own release) → **Phase 4 pair** → papercuts pair. Each phase ships per the
docs lifecycle: pair in `docs/` root while active, archived on release with a
CHANGELOG link.

## Laws this plan must not bend (restated because Phase 2 walks near one)

Method tags sacred · negative nets with real signal always shown · unpriced is
`—` + ⚠, never $0 and never hidden · determinism (all gating decided by ledger
content, never clock) · CSV schemas stable even where text views gate ·
fail-open capture untouched by all five phases · no network · $0/stdlib.
