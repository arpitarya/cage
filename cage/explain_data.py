"""`cage query`'s registry — the `Explanation` entries themselves (handoff §1, §2).

Pure data: every formula/body is a template whose `{placeholders}` are filled by
`explain._live(pol)` at render time. Split out of `explain.py` to keep the engine
(matching, rendering, payload) small; this file is a table, not logic.
"""
from __future__ import annotations

from cage.explain_types import Explanation

# ── the registry — fixed order is the tie-break; numbers live in `formula` ──────
REGISTRY: tuple[Explanation, ...] = (
    Explanation(
        "cost", ("cost", "price", "dollar", "usd", "value", "calculated", "spend",
                 "recompute", "est_cost", "billed", "charge"),
        "what a recorded call costs in USD",
        "usd = (input·in_price + cached·cache_read + output·out_price) / {per_million}\n"
        "  recompute from tokens × policy when the model is priced; else fall back to\n"
        "  the stored est_cost_usd (a provider cage can't tokenize). Derive-time only —\n"
        "  the ledger is never rewritten.",
        ("cage/prices.py", "cage/policy.py", "policy.toml [prices]"),
        "measured — it costs the call that actually ran, from its recorded tokens."),
    Explanation(
        "saved", ("saved", "savings", "reduction", "shrink", "avoided"),
        "the tokens/USD a tool kept out of the prompt",
        "saved = raw_alternative − actual   (USD via the call's model price)",
        ("cage/convert.py", "cage/attribution.py"),
        "inherits the receipt's method — measured only if the tool truly measured it."),
    Explanation(
        "marginal-attribution", ("marginal", "attribution", "attribute", "attrib",
                                 "per-tool", "fixed", "order", "overlap", "credit",
                                 "pipeline"),
        "how per-tool savings sum to the total with no double-count",
        "walk tools in policy order ({order}); each receipt is its marginal saving\n"
        "  given the tools upstream of it, so Σ(marginals) = total, no overlap.",
        ("cage/attribution.py", "cage/matrix.py", "policy.toml [tools.order]"),
        "per-row method = the least-trusted receipt for that tool (honest worst-case)."),
    Explanation(
        "matrix", ("matrix", "counterfactual", "permutation", "stack",
                   "combination", "scenario"),
        "the 2ⁿ what-would-each-stack-cost table",
        "enumerate 2^n on/off tool permutations (n ≤ {max_tools}); input tokens =\n"
        "  base + Σ(actual if on else raw_alternative), costed at the task's model.",
        ("cage/matrix.py", "cage/constants.py"),
        "only the configuration actually run is measured; every other cell is modeled\n"
        "  (estimated if it leans on an estimated receipt) — no projection is an invoice."),
    Explanation(
        "compare-delta", ("compare", "comparison", "delta", "group", "grouped",
                          "median", "iqr", "observational", "a/b", "ab",
                          "baseline", "agent-only", "cheaper"),
        "how `cage compare` contrasts closed-task groups by observed stack",
        "group closed tasks by stack signature (joined receipt tools; task-id join,\n"
        "  session-window fallback); per group report n · median · IQR of measured\n"
        "  tokens + USD; delta = median(stack) − median(agent-only), same non-stack\n"
        "  keys. Groups below n = {min_compare_n} render a refusal, never a number.",
        ("cage/compare.py", "cage/taskgroup.py", "cage/constants.py"),
        "group totals are measured (recorded tokens, derive-time repricing); the delta\n"
        "  is estimated — different tasks, nothing randomized, an observed difference\n"
        "  and never a causal claim (the caveat renders on every output)."),
    Explanation(
        "estimate-band", ("estimate", "estimated-cost", "band", "predict", "forecast-task",
                          "pre-task", "upfront", "before", "how-much-will"),
        "how `cage estimate` bands an unrun task's cost",
        "band = median + IQR of measured totals over closed tasks matching the exact\n"
        "  keys (scope / label / agent) — no similarity scoring, no ML. Below\n"
        "  n = {min_estimate_n} matching tasks the command refuses. --record stamps\n"
        "  est_tokens/est_usd/est_n + the token band bounds onto the open task row.",
        ("cage/estimate.py", "cage/taskgroup.py", "cage/constants.py"),
        "modeled — history applied to a task that hasn't run is a reconstruction,\n"
        "  never an invoice; its empirical confidence is `cage calibration`'s hit-rate."),
    Explanation(
        "calibration-hit-rate", ("calibration", "calibrate", "hit-rate", "hit", "landed",
                                 "accuracy", "ratio", "in-band", "reliable"),
        "how estimate reliability is measured after the fact",
        "over closed tasks with recorded estimates: ratio = actual_tokens / est_tokens\n"
        "  (median + IQR), and hit-rate = share of actuals inside the est band recorded\n"
        "  at estimate time. Open / zero-actual / band-less tasks are skipped with a\n"
        "  visible count.",
        ("cage/calibration.py", "cage/estimate.py", "cage/taskgroup.py"),
        "measured — an observed frequency of recorded estimates vs recorded actuals;\n"
        "  this rate *is* the estimator's confidence level (it never self-reports one)."),
    Explanation(
        "verdict-composition", ("verdict", "saving-or-costing", "worth-it", "keep",
                                "drop", "net", "break-even", "breakeven", "compose"),
        "how `cage verdict <tool>` reaches SAVING / COSTING / INSUFFICIENT DATA",
        "a pure composer — no new statistics: net = roi.saved − roi.own_cost over the\n"
        "  window (verdict = its sign); marginal saving from attribution's latest task;\n"
        "  direction from trend; drift from regression; redo-rate from quality;\n"
        "  break-even = net / receipts. ≈$/mo scales net by the receipts' own time-span\n"
        "  (≥7 days, no clock). Missing input ⇒ INSUFFICIENT DATA, never an approximation.",
        ("cage/verdict.py", "cage/roi.py", "cage/attribution.py", "cage/regression.py"),
        "the headline is modeled (it inherits the receipts' modeled savings); every\n"
        "  input line renders its own tag — measured drift/redo, estimated trend."),
    Explanation(
        "study-pairing", ("study", "fleet", "machines", "laptops", "paired", "pairing",
                          "phase", "enrollment", "bundle", "week-over-week"),
        "how the fleet study pairs machines and computes its delta",
        "phases are recorded markers (`cage study start/stop`), resolved per machine\n"
        "  against that machine's own clock; the sample unit is the machine-day.\n"
        "  paired delta = median over machines of (phase-B median daily − phase-A\n"
        "  median daily), controlling between-machine variance; below\n"
        "  {min_compare_n} machines with both phases the delta refuses. Coverage\n"
        "  (days + gaps) always prints first. Machine ids are opaque random tokens —\n"
        "  never a hostname.",
        ("cage/study.py", "cage/machine.py", "cage/constants.py"),
        "per-machine-day totals are measured; the paired delta is estimated —\n"
        "  recorded phase intent across different weeks, never a randomized experiment."),
    Explanation(
        "human-cost", ("human", "person", "salary", "labor", "wage", "people",
                       "engineer", "manually", "cost-a-human", "alternative"),
        "how a human alternative is priced",
        "usd = minutes / 60 × rate     (rate = ${rate}/hr, source: {rate_src})\n"
        "  chain: explicit usd > per-receipt minutes > task-type table > global default\n"
        "  confidence: measured {c_measured} · estimated {c_estimated} · "
        "type-table {c_type} · default {c_default}",
        ("cage/human.py", "cage/convert.py", "policy.toml [human]"),
        "estimated — a labor guess; never 'measured' unless a real timesheet/quote."),
    Explanation(
        "attention-minutes", ("attention", "gap", "gaps", "turn-gap", "gap_ms", "idle",
                              "supervision", "derived-minutes", "babysit", "watching",
                              "human-minutes", "how-are-human-minutes-derived"),
        "how human-attention minutes are derived from turn gaps",
        "minutes = Σ min(gap_ms, idle cap) / 60000    (cap = {idle_cap} min; policy\n"
        "  [human] idle_cap_minutes wins, constants.IDLE_CAP_MINUTES is the fallback)\n"
        "  gap_ms = wall-clock between the previous assistant turn's end and the human\n"
        "  turn that led to the call — stamped at import only where the log carries\n"
        "  per-turn timestamps (claude today; codex/copilot/kiro lack the signal ⇒ no\n"
        "  field, never fabricated). Read-time derive: changing the cap re-prices the\n"
        "  backlog, the ledger is never rewritten. Attested minutes (`human-record`,\n"
        "  `cage outcome --minutes`) beat derived for a task — never summed;\n"
        "  `cage calibration --human` measures the heuristic's derived/attested ratio.",
        ("cage/attention.py", "cage/transcript.py", "policy.toml [human]"),
        "estimated, always — labelled 'derived (turn-gaps, capped)'; only attested\n"
        "  minutes can ever read differently, and only as a real timesheet ('measured')."),
    Explanation(
        "time-saved", ("time", "hours", "minutes", "time-saved", "hours-saved", "clock"),
        "the hours an agent saved a human (can go negative)",
        "saved_minutes = human_minutes − agent_active_minutes\n"
        "  (negative when the agent took longer than a person would have — honest).",
        ("cage/humanview.py", "cage/trend.py", "cage/human.py"),
        "estimated — the human leg is a labor estimate; the metric can embarrass the agent."),
    Explanation(
        "roi", ("roi", "return", "worth", "tool-cost", "latency", "investment"),
        "saved $ per tool vs that tool's own cost + latency",
        "per tool: Σ saved_usd  vs  Σ meta.tool_cost_usd  and  Σ meta.added_latency_ms\n"
        "  (a deterministic tool saves at $0 of its own cost).",
        ("cage/roi.py", "cage/convert.py"),
        "inherits each receipt's method; the saved-$ side is only as trusted as its receipts."),
    Explanation(
        "token-heuristic", ("token", "tokens", "chars", "divisor", "heuristic",
                            "tokenize", "tokenizer", "approx"),
        "how text is turned into a token count",
        "tokens ≈ round(len(text) / {chars_per_token})   (deterministic, no tokenizer)",
        ("cage/constants.py", "cage/compress.py", "cage/graphifymeter.py"),
        "a heuristic — receipts built on it are modeled/estimated, never measured."),
    Explanation(
        "confidence", ("confidence", "ladder", "credibility", "trust", "credible"),
        "how credible a figure is, on a 0–1 ladder",
        "measured {c_measured} · estimated {c_estimated} · "
        "type-table {c_type} · default {c_default}\n"
        "  policy [human.confidence] wins; constants.DEFAULT_CONFIDENCE is the fallback.",
        ("cage/human.py", "cage/constants.py", "policy.toml [human.confidence]"),
        "orthogonal to method: a low confidence flags a round guess, not a wrong tag."),
    Explanation(
        "method-tags", ("method", "measured", "modeled", "estimated", "provenance",
                        "tag", "sacred"),
        "the three provenance tags and their ranking",
        "trust rank: {trust}\n"
        "  measured = an actual invoice/run · modeled = reconstructed · estimated = a guess.",
        ("cage/constants.py", "cage/schema.py", "cage/matrix.py"),
        "method is sacred — a projection never reads as measured (cage's core honesty rule)."),
    Explanation(
        "trend", ("trend", "over-time", "weekly", "monthly", "drift", "history"),
        "cost + time savings bucketed over time",
        "group receipts/calls by week or month; show saved $ and saved hours per bucket.",
        ("cage/trend.py", "cage/human.py"),
        "carries each bucket's underlying receipt methods; the time leg is estimated."),
    Explanation(
        "budget", ("budget", "ceiling", "cap", "session", "daily", "exceed", "limit"),
        "session/day spend vs the policy ceilings",
        "Σ call_usd over the window vs [budgets] session_usd / daily_usd; on_exceed = warn|block.",
        ("cage/budget.py", "cage/prices.py", "policy.toml [budgets]"),
        "measured — totals real recorded calls; the ceiling is policy, not a guess."),

    # ── concept entries — how cage itself works, not how a value is computed ───
    Explanation(
        "capture-troubleshooting",
        ("capture", "captured", "capturing", "nothing", "missing", "empty",
         "troubleshoot", "troubleshooting", "why-no-rows", "probe",
         "windows", "location", "log-location"),
        "why is nothing being captured — the three-step diagnosis",
        "1. `cage doctor --paths` — read-only probe of every candidate log location\n"
        "     per agent on this OS: found/missing, files matched, parseable rows,\n"
        "     cursor state, and a why-line per miss (wrong layout, cursor already\n"
        "     imported, unparseable format). Env overrides and any UNVERIFIED-LAYOUT\n"
        "     candidates are labeled.\n"
        "  2. `CAGE_DEBUG=1 cage import` — the same probes stream to debug.log as\n"
        "     metadata-only events, plus per-file parse/append/dedupe detail\n"
        "     (`cage debug` to read them).\n"
        "  3. `cage doctor --bundle` — exports both (plus cursors, versions, policy\n"
        "     provenance) as one redacted archive to attach to a bug report; the\n"
        "     home prefix is rendered as `~`, contents are counts-never-content.",
        ("cage/pathprobe.py", "cage/debuglog.py", "cage/doctorbundle.py"),
        "n/a — a diagnostic runbook, not a number.",
        kind="concept", plan_ref="§3.7"),
    Explanation(
        "overview", ("overview", "works", "introduction", "explain", "how-cage-works"),
        "the front door: cage's one-way data flow + its laws",
        "record_call / record_receipt → append-only {calls_path} / {receipts_path} →\n"
        "  every view ({n_subcommands} subcommands) derives from that log, $0, no model.\n"
        "  wired into every agent surface: {agent_surfaces}.\n"
        "  laws: append-only · fail-open metering · method is sacred · deterministic.\n"
        "  see also: {concept_ids}",
        ("cage/ledger.py", "cage/cli.py", "cage/agents.py"),
        "n/a — this entry explains the system, not a single number.",
        kind="concept", plan_ref="§1"),
    Explanation(
        "data-flow", ("data-flow", "dataflow", "pipeline", "flow", "ledger",
                      "append-only", "jsonl", "record"),
        "the one-way path from a call to a derived table",
        "record_call/record_receipt append rows to {partition}-partitioned shards of:\n"
        "    {calls_path}\n    {receipts_path}\n    {tasks_path}\n"
        "  i.e. calls-YYYY-MM.jsonl etc., named from each row's ts. Every read\n"
        "  (report/attrib/matrix/budget/roi/human/trend) globs the shards (+ any legacy\n"
        "  single file) and derives at read time — nothing is ever rewritten in place;\n"
        "  new writes target dated files (plan §3.6.1).",
        ("cage/ledger.py", "cage/paths.py"),
        "n/a — describes the pipeline shape, not a number.",
        kind="concept", plan_ref="§3"),
    Explanation(
        "metering", ("metering", "meter", "surface", "library", "proxy",
                     "transcript", "fail-open", "instrument"),
        "the four ways a call gets recorded, and why none can break a request",
        "surfaces: library (metering.py context manager) · proxy (usageparse.py,\n"
        "  any client you point a base URL at) · transcript (transcript.py, Claude\n"
        "  Code/Codex session logs) · MCP (mcpserver.py, read-only).\n"
        "  reliable default for the transcript agents is SessionStart-backfill: import\n"
        "  the previous session on the next start (the transcript is always on disk).\n"
        "  SessionEnd is best-effort — it doesn't fire on a kill/crash/idle session;\n"
        "  running both is safe because cage import dedupes by call id.\n"
        "  fail-open: a metering error is swallowed, never raised into the request path.",
        ("cage/metering.py", "cage/proxy.py", "cage/transcript.py", "cage/mcpserver.py"),
        "n/a — describes a mechanism, not a number.",
        kind="concept", plan_ref="§5"),
    Explanation(
        "attribution", ("differentiator", "shapley", "fixed-order"),
        "why per-tool savings sum to the total with no overlap",
        "tools are walked in one fixed policy order ({order}); each tool's marginal\n"
        "  saving is computed given only the tools upstream of it, so the marginals\n"
        "  sum exactly to the total — no double-count, no negotiation between tools.\n"
        "  Shapley-style fair-division is deferred to an optional audit mode, not the\n"
        "  default, because fixed-order is $0 and reproducible; Shapley is combinatorial.",
        ("cage/attribution.py", "policy.toml [tools.order]"),
        "n/a — describes the attribution mechanism, not a single number.",
        kind="concept", plan_ref="§4.2"),
    Explanation(
        "matrix-concept", ("permutation", "counterfactual", "2^n", "every-cell"),
        "the 2ⁿ what-would-each-stack-cost table, and what's real in it",
        "every on/off permutation of up to {max_tools} tools is enumerated, but only\n"
        "  the cell matching what actually ran is method=measured — every other cell\n"
        "  is a reconstruction (modeled, or estimated if it leans on an estimated\n"
        "  receipt). A matrix cell is never an invoice.",
        ("cage/matrix.py", "cage/constants.py"),
        "n/a — describes the matrix's honesty rule, not a number.",
        kind="concept", plan_ref="§4.4"),
    Explanation(
        "method-law", ("provenance", "invoice", "sacred", "honesty"),
        "the law behind the three provenance tags",
        "tags: {methods}. measured = an actual invoice/run · modeled = reconstructed\n"
        "  from real receipts · estimated = a guess. The law: no derived/projected\n"
        "  figure may ever be tagged measured — that tag is reserved for a call or\n"
        "  receipt that truly happened. (For the trust ranking and ordering between\n"
        "  tags, see `method-tags`.)",
        ("cage/schema.py", "cage/constants.py"),
        "n/a — this entry is itself the definition of method, not an instance of it.",
        kind="concept", plan_ref="§4.3"),
    Explanation(
        "receipts", ("shim", "adapter", "in-tool", "external-adapter", "claim"),
        "the two ways a tool's savings claim reaches the ledger",
        "in-tool shim: the tool itself (e.g. fux) emits a receipt as it runs, so the\n"
        "  claim is first-party. External adapter: cage meters a third-party tool from\n"
        "  the outside (e.g. `cage graphify -- graphify query …`) without that tool\n"
        "  knowing cage exists — the receipt is filed by cage's wrapper, not the tool.",
        ("cage/schema.py", "cage/graphifymeter.py"),
        "n/a — describes two receipt-filing strategies, not a number.",
        kind="concept", plan_ref="§4.5"),
    Explanation(
        "human-axis", ("tier-1", "tier-2", "agent-vs-human", "tool-vs-tool", "whole-task",
                       "attested", "derived-attention"),
        "the two axes cage measures savings on",
        "Tier-1 (human.py, matrix --human): agent vs human, the whole task — what\n"
        "  would a person have cost, in $ and hours, vs what the agent actually cost.\n"
        "  Tier-2 (attribution.py, matrix): tool vs tool, inside one agent run — what\n"
        "  did each tool in the pipeline save vs that tool being off.\n"
        "  The Tier-1 axis also tracks what the agent COSTS in human time (plan §4.10):\n"
        "  attested minutes (`human-record`, `cage outcome --minutes N`) are ground\n"
        "  truth; derived minutes (turn-gaps capped at {idle_cap} min, attention.py)\n"
        "  are the passive estimate. Attested beats derived per task — never summed;\n"
        "  `cage calibration --human` measures the heuristic against the attested\n"
        "  ground truth (see `attention-minutes` for the formula).",
        ("cage/human.py", "cage/matrix.py", "cage/attention.py"),
        "n/a — describes two measurement axes, not a number.",
        kind="concept", plan_ref="§4.6, §4.10"),
    Explanation(
        "determinism", ("reproducible", "byte-identical", "same-ledger", "offline"),
        "why the same ledger always renders the same tables",
        "derived views ({n_subcommands} subcommands) contain no clock read, no RNG,\n"
        "  and no model call — the only inputs are the ledger rows and the policy file.\n"
        "  Same ledger + same policy ⇒ byte-identical output; ids carry the only entropy,\n"
        "  and only at write time.",
        ("cage/ledger.py", "cage/attribution.py"),
        "n/a — describes a system invariant, not a number.",
        kind="concept", plan_ref="§1"),
    Explanation(
        "pii-safety", ("pii", "privacy", "private", "prompt-body", "sensitive",
                       "cage_ledger", "redact"),
        "why the ledger is safe to keep even on a sensitive project",
        "rows carry token *counts*, never prompt bodies — PII-safe by construction;\n"
        "  there is no field a prompt's text could land in. Point {ledger_env} at a\n"
        "  private store to move even the counts off the project's own disk.",
        ("cage/paths.py", "cage/schema.py"),
        "n/a — describes a privacy guarantee, not a number.",
        kind="concept", plan_ref="§10"),
    Explanation(
        "numbers-layers", ("numbers-layers", "three-layers", "contract-vs-policy",
                           "constants-vs-policy", "audit-layer"),
        "the three places cage keeps its numbers, never mixed",
        "contract = the closed enums in schema.py ({methods}) · policy = user\n"
        "  economics in policy.toml (prices, human rate, budgets, pipeline order) ·\n"
        "  constants = code heuristics that must stay reviewable but aren't config\n"
        "  (chars-per-token, the matrix ceiling, the method trust ranking, the\n"
        "  confidence fallback) — see constants.py.",
        ("cage/schema.py", "cage/constants.py", "policy.toml"),
        "n/a — describes where numbers live, not a number itself.",
        kind="concept", plan_ref="§3.3"),
    Explanation(
        "ledger-scale", ("partition", "shard", "month", "scope", "monorepo", "team",
                         "ledger-sync", "aggregate", "notes-ledger", "scale"),
        "how the ledger survives heavy / multi-dev / monorepo use",
        "partitions: each log is split into {partition}ly shards (calls-YYYY-MM.jsonl,\n"
        "  same for receipts/tasks), named from each row's own ts — readers glob +\n"
        "  concatenate, and --since skips whole below-cutoff months.\n"
        "  scope: calls/receipts carry an optional top-level changed dir (same PII guard\n"
        "  as tasks); report/attrib/budget/matrix --scope <dir> slice one component.\n"
        "  team: cage ledger-sync unions local rows into refs/notes/cage-ledger by row\n"
        "  id (CI-sole-writer, like notes-sync); report/attrib --team read the merge,\n"
        "  rolled up by scope, never per-person. Size warning: one stderr line past\n"
        "  ~{warn_mb} MB (policy [ledger] warn_mb overrides) — warn-only, never blocks.",
        ("cage/ledger.py", "cage/ledgersync.py", "cage/mergeutil.py", "cage/constants.py"),
        "n/a — describes the on-disk layout + aggregation, not a number.",
        kind="concept", plan_ref="§3.6"),
    Explanation(
        "pricing-match", ("pricing-match", "match-kind", "exact", "family", "alias",
                          "self", "resolve", "price-row", "matched", "footnote"),
        "how a call's model resolves to a price row (exact → alias → family → self → none)",
        "resolution order over this policy's {n_price_rows} price rows:\n"
        "  exact — the raw (provider, model) key has its own row: an invoice.\n"
        "  alias — an explicit [alias] route (router pseudo-models like copilot/auto);\n"
        "    explicit routing beats every heuristic, and a dangling alias is none,\n"
        "    never a fallback guess.\n"
        "  family — the same-provider row sharing the most leading segments after\n"
        "    normalization (route prefixes {route_prefixes} strip · '.' folds to '-' ·\n"
        "    effort tiers {effort_suffixes} drop); needs ≥ {family_min_segments} shared\n"
        "    segments, so opus never borrows a sonnet price. Renders with a footnote —\n"
        "    a normalized match is never allowed to read as exact (method law).\n"
        "  self — no row, but the provider self-reported est_cost_usd at record time.\n"
        "  none — UNPRICED: a genuine $0 that must surface, never hide in a total.",
        ("cage/policy.py", "cage/prices.py", "cage/constants.py"),
        "measured for exact; alias/family are approximations and carry their footnote."),
    Explanation(
        "unpriced", ("unpriced", "zero", "0", "billing", "missing-price",
                     "counted-as-0", "understated", "no-price-row"),
        "what an UNPRICED $0 means and how to fix it",
        "a call whose model matched none bills $0 — the totals are understated and\n"
        "  every read surface says so out loud rather than hiding it (a wrong number\n"
        "  is worse than none). Fix workflow: `cage prices unpriced` lists each\n"
        "  offending (provider, model) with call count, token volume, and a\n"
        "  ready-to-run fix line; find the real rate on the vendor's pricing page\n"
        "  (cage never fetches — no network on any cage code path), then\n"
        "  `cage prices set <provider> <model> --input … --output …` or, for a\n"
        "  router pseudo-model, `cage prices alias`. Caveat: self-costed rows\n"
        "  (stored est_cost_usd) and receipts keep their recorded values.",
        ("cage/pricescmd.py", "cage/report.py", "cage/prices.py"),
        "n/a — the $0 is the absence of a number; fixing it makes the totals honest."),
    Explanation(
        "repricing", ("repricing", "reprice", "retroactive", "derive-time",
                      "recompute", "price-change", "fleet-reprice", "back-price"),
        "why fixing a price re-prices history without touching the ledger",
        "pricing is derive-time: report/budget/compare/study recompute every call\n"
        "  as tokens × the *current* policy row on each run — the ledger stores\n"
        "  counts, not conclusions, and is never rewritten. So an analyst fixing\n"
        "  policy.toml re-prices every imported bundle row retroactively: same\n"
        "  ledger + same policy ⇒ same tables; new policy ⇒ honestly new tables.\n"
        "  Exceptions that do NOT re-derive: self-costed calls (their stored\n"
        "  est_cost_usd was the provider's own figure) and receipts' recorded values.",
        ("cage/prices.py", "cage/convert.py", "cage/ledger.py"),
        "measured — recomputed from each call's recorded tokens at today's policy."),
    Explanation(
        "prices-cli", ("prices-cli", "prices", "price-command", "set-price",
                       "alias-command", "sync", "price-research", "vendor-page"),
        "the `cage prices` verbs and the research workflow behind them",
        "cage prices unpriced — what's billing $0, with a ready-to-run fix line each.\n"
        "  cage prices set <provider> <model> --input <$/Mtok> --output <$/Mtok>\n"
        "    [--cache-read <$/Mtok>] — idempotent insert-or-update of a project row.\n"
        "  cage prices alias - copilot/auto --to anthropic/claude-sonnet-4-6 — route a\n"
        "    router pseudo-model ('-' is the empty provider such rows stamp).\n"
        "  cage prices list — every visible row, bundled vs project, which wins.\n"
        "  cage prices sync — diff vs the installed bundle (dry-run; --update + --yes).\n"
        "  Research: cage never fetches a price — check the vendor's pricing page (or\n"
        "  search \"<vendor> <model> API pricing\"), then paste the fix line. Writes land\n"
        "  in the project policy.toml ({prices_version_project}); the bundled table\n"
        "  ({prices_version_bundled}) is read-only at runtime. Derived views re-price\n"
        "  immediately — the ledger is never rewritten.",
        ("cage/pricescmd.py", "cage/pricestoml.py", "policy.toml [prices]"),
        "n/a — describes the command surface, not a number.",
        kind="concept", plan_ref="§3.3"),
    Explanation(
        "effort-tiers", ("effort-tiers", "effort", "reasoning-effort", "high", "tier",
                         "suffix", "punctuation", "dotted", "normalization"),
        "why claude-sonnet-4.6 and …-high price at the base row",
        "reasoning-effort tiers change token *consumption* (already measured per\n"
        "  call), not the per-token unit price — verified against both vendors'\n"
        "  pricing pages 2026-07-11. So family matching normalizes before comparing:\n"
        "  route prefixes ({route_prefixes}) strip, '.' folds to '-' (Copilot stamps\n"
        "  claude-sonnet-4.6; Anthropic rows are dashed), and trailing effort\n"
        "  segments ({effort_suffixes}) drop. A tier variant prices at its base row\n"
        "  with the family footnote — never rendered exact. If a vendor ever bills a\n"
        "  tier at a genuinely different per-token rate, that tier gets its own\n"
        "  explicit row instead — normalization must never erase a real price.",
        ("cage/policy.py", "cage/constants.py"),
        "n/a — describes name normalization, not a number.",
        kind="concept", plan_ref="§3.3"),
    Explanation(
        "policy-versioning", ("policy-versioning", "meta", "prices-version",
                              "stale-prices", "bundle-newer", "sync-recommendation"),
        "how cage knows your price table is stale ([meta] + prices sync)",
        "the bundled policy carries [meta] prices_version {prices_version_bundled};\n"
        "  `cage init` (and the first `cage prices set`) stamp the project copy with\n"
        "  the bundle it derived from (this project: {prices_version_project}).\n"
        "  `cage doctor` and `cage prices list` compare the two — a newer bundle\n"
        "  prints one recommendation line to run `cage prices sync`, never\n"
        "  auto-applied. sync classifies each row: in-sync (equal), customized\n"
        "  (cage-managed/marked — never clobbered), or drift (provenance unknown —\n"
        "  cage can't reconstruct which old bundle a row came from, so it lists the\n"
        "  diff and applies only rows you confirm per --yes).",
        ("cage/pricescmd.py", "cage/data/policy.toml [meta]", "cage/doctorcmd.py"),
        "n/a — describes version bookkeeping, not a number.",
        kind="concept", plan_ref="§3.3"),
    Explanation(
        "copilot-pricing", ("copilot-pricing", "copilot", "premium-request", "credits",
                            "subscription", "seat", "auto", "router"),
        "how Copilot-served models price (and why copilot/auto stays unpriced)",
        "Copilot's VS Code store stamps modelIds like copilot/claude-opus-4.6 with\n"
        "  the provider inferred from the name (→ anthropic), so Copilot-served\n"
        "  Claude family-prices at the Anthropic API rows after route-prefix\n"
        "  normalization. That approximates seat/subscription billing — but it is\n"
        "  also GitHub's own metering basis: since 2026-06-01 Copilot bills\n"
        "  usage-based AI Credits from token consumption at listed API rates\n"
        "  (github.blog, retrieved 2026-07-11). The [credits] layer is a separate\n"
        "  axis (plan-quota multipliers, estimated, off by default) — never blurred\n"
        "  into per-token prices, and Kiro/Copilot credits are never derived from\n"
        "  tokens. The bare router id copilot/auto matches nothing by design: route\n"
        "  it explicitly (`cage prices alias - copilot/auto --to …`) — a router\n"
        "  priced silently would be a wrong number.",
        ("cage/transcript.py", "cage/credits.py", "cage/data/policy.toml"),
        "n/a — describes a billing approximation and its provenance.",
        kind="concept", plan_ref="§3.3, §3.8"),
    Explanation(
        "cleanup", ("cleanup", "state-dir", "prune", "stale", "retention",
                    "debug-log-growth", "cursors", "pending-buffers"),
        "what `cage cleanup` may touch — and what it never may",
        "a CLOSED allowlist over .cage/state/ only: aged debug.log / hooks-seen.jsonl\n"
        "  rows, stale pending-* provenance buffers, cursors whose source log is gone\n"
        "  (safe: the next import re-reads and id-dedupe absorbs it), *.tmp. Never —\n"
        "  by construction, not convention: ledger/, policy.toml, the machine id\n"
        "  (fleet pairing breaks without it), study.jsonl, limits.json. Window:\n"
        "  [cleanup] days = {cleanup_days} (currently {cleanup_on}; env CAGE_CLEANUP\n"
        "  overrides). Auto path piggybacks on `cage import`/hook sweeps, throttled\n"
        "  and fail-open (cage installs no scheduler); manual `cage cleanup` is a\n"
        "  dry-run until --apply. State files are never read by derived views, so\n"
        "  cleanup cannot change a single reported number.",
        ("cage/cleanup.py", "cage/policy.py", "policy.toml [cleanup]"),
        "n/a — describes state maintenance, not a number.",
        kind="concept", plan_ref="§3.6.4"),
    Explanation(
        "import-before-export", ("import-before-export", "export-sweep", "no-import",
                                 "self-refreshing", "snapshot", "bundle-freshness"),
        "why `cage export` imports first (and how to get a frozen snapshot)",
        "export runs the all-agent import sweep before emitting/bundling, so a\n"
        "  capture-only machine (hooks don't fire under a VS Code extension) still\n"
        "  ships a complete bundle — one `cage export --study` is enough. Currently\n"
        "  {import_before_export}. Precedence: the --no-import flag wins per\n"
        "  invocation > env CAGE_CAPTURE=0 (pauses all capture, sweep included) >\n"
        "  policy [capture] import_before_export. The sweep is fail-open — a broken\n"
        "  parser warns and export proceeds with the pre-sweep ledger — and the\n"
        "  study bundle's manifest records whether it ran and how many rows it added\n"
        "  (counts only), so the analyst can tell self-refreshed from snapshot.",
        ("cage/exportcmd.py", "cage/study.py", "policy.toml [capture]"),
        "n/a — describes capture freshness, not a number.",
        kind="concept", plan_ref="§3.7"),
    Explanation(
        # NB: no "cage-run"/"workspacefolder" keywords — their "cage"/"work" stems
        # would steal generic "how does cage work"-style queries from `overview`.
        "portable-wiring", ("portable-wiring", "portable", "shim", "absolute-path",
                            "clone", "teammate", "committed", "broken-wiring",
                            "team-share", "gitignore"),
        "why committed wiring references .cage/bin/cage-run, never an absolute path",
        "wired files that are committed to git (.claude/settings.json, .mcp.json,\n"
        "  .vscode/mcp.json, .codex/hooks.json, .kiro/hooks/*.kiro.hook) used to embed\n"
        "  the wiring machine's absolute cage path — one dev's filesystem shipped to\n"
        "  the team, breaking every clone. They now reference the committed shim\n"
        "  .cage/bin/cage-run (identical bytes on every machine), which resolves cage\n"
        "  at RUNTIME: cage on PATH → ~/.local/bin / pipx / active $VIRTUAL_ENV →\n"
        "  python3 -m cage → exit 0 silently. cage absent ⇒ working agents, no noise,\n"
        "  no capture (fail-open extended to wiring; `cage doctor` diagnoses, never\n"
        "  the hook path). Per host: Claude hooks use the documented\n"
        "  $CLAUDE_PROJECT_DIR placeholder; .mcp.json uses ${{CLAUDE_PROJECT_DIR:-.}}\n"
        "  expansion; .vscode/mcp.json uses ${{workspaceFolder}}; codex/kiro hooks\n"
        "  self-locate via git rev-parse (their hosts guarantee neither variable nor\n"
        "  cwd). User-level files (~/.copilot/hooks, ~/.codex/config.toml MCP,\n"
        "  .git/hooks) stay absolute — per-machine by nature, never cloned. The ONE\n"
        "  exception: .kiro/settings/mcp.json must stay absolute (Kiro spawns MCP\n"
        "  servers from its install dir, no workspace variable) — gitignore it.\n"
        "  Re-running `cage setup` migrates legacy absolute entries and prints what\n"
        "  moved; `cage doctor` has a portability check.",
        ("cage/runshim.py", "cage/claudewire.py", "cage/codexwire.py",
         "cage/kirowire.py", "cage/doctorcmd.py"),
        "n/a — describes the wiring mechanism, not a number.",
        kind="concept", plan_ref="§5"),
)
