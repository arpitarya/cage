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
        "record_call/record_receipt append rows to:\n"
        "    {calls_path}\n    {receipts_path}\n    {tasks_path}\n"
        "  every read (report/attrib/matrix/budget/roi/human/trend) derives from\n"
        "  those three files at read time — nothing is ever rewritten in place.",
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
        "human-axis", ("tier-1", "tier-2", "agent-vs-human", "tool-vs-tool", "whole-task"),
        "the two axes cage measures savings on",
        "Tier-1 (human.py, matrix --human): agent vs human, the whole task — what\n"
        "  would a person have cost, in $ and hours, vs what the agent actually cost.\n"
        "  Tier-2 (attribution.py, matrix): tool vs tool, inside one agent run — what\n"
        "  did each tool in the pipeline save vs that tool being off.",
        ("cage/human.py", "cage/matrix.py"),
        "n/a — describes two measurement axes, not a number.",
        kind="concept", plan_ref="§4.6"),
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
)
