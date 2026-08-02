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
        ("cage/prices.py", "cage/policy.py", "cage.toml [prices]"),
        "measured — it costs the call that actually ran, from its recorded tokens."),
    Explanation(
        "saved", ("saved", "savings", "reduction", "shrink", "avoided"),
        "the tokens/USD a tool kept out of the prompt (GROSS)",
        "saved = raw_alternative − actual   (USD via the call's model price)\n"
        "  GROSS: the cost of USING the tool — the invoking turn, the context a hook\n"
        "  injected — is NOT subtracted. `cage query gross-vs-net` for the net.",
        ("cage/convert.py", "cage/attribution.py", "cage/netsaved.py"),
        "inherits the receipt's method — measured only if the tool truly measured it."),
    Explanation(
        "gross-vs-net", ("gross", "net", "cost-of-use", "net-saved", "attributable",
                         "over-claim", "excluded", "using", "adjacent", "window"),
        "why `saved` is gross, and how the task-level net subtracts the cost of use",
        "gross    = raw_alternative − actual          (the avoided read — excludes using it)\n"
        "  cost of use = Σ call_usd(c) over the DISTINCT calls joined to the receipt's task\n"
        "                whose ts lies within ±{net_window_s}s of ANY of that tool's receipts\n"
        "                on that task (union per task — an adjacent call counts once)\n"
        "  net      = gross − cost of use     (covered tasks only; confidence {net_confidence})\n"
        "  A task with no in-window call is UNCOVERED: net says unavailable, never = gross.\n"
        "  Per-query netting is impossible — shim receipts carry a task but no call.",
        ("cage/netsaved.py", "cage/verdict.py", "cage/constants.py"),
        "gross is modeled (a counterfactual); the subtrahend is measured (recorded tokens\n"
        "  repriced); net is modeled at its own, lower confidence — it stacks a time-window\n"
        "  join on top of gross's counterfactual, so it can never be the more credible of the two."),
    Explanation(
        "marginal-attribution", ("marginal", "attribution", "attribute", "attrib",
                                 "per-tool", "fixed", "order", "overlap", "credit",
                                 "pipeline"),
        "how per-tool savings sum to the total with no double-count",
        "walk tools in policy order ({order}); each receipt is its marginal saving\n"
        "  given the tools upstream of it, so Σ(marginals) = total, no overlap.",
        ("cage/attribution.py", "cage/matrix.py", "cage.toml [tools.order]"),
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
        "how `cage insights compare` contrasts closed-task groups by observed stack",
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
        "how `cage insights estimate` bands an unrun task's cost",
        "band = median + IQR of measured totals over closed tasks matching the exact\n"
        "  keys (scope / label / agent) — no similarity scoring, no ML. Below\n"
        "  n = {min_estimate_n} matching tasks the command refuses. --record stamps\n"
        "  est_tokens/est_usd/est_n + the token band bounds onto the open task row.",
        ("cage/estimate.py", "cage/taskgroup.py", "cage/constants.py"),
        "modeled — history applied to a task that hasn't run is a reconstruction,\n"
        "  never an invoice; its empirical confidence is `cage insights calibration`'s hit-rate."),
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
        "how `cage insights verdict <tool>` reaches SAVING / COSTING / INSUFFICIENT DATA",
        "a pure composer — no new statistics: net = roi.gross − roi.own_cost over the\n"
        "  window (verdict = its sign); marginal saving from attribution's latest task;\n"
        "  drift from regression; redo-rate from quality;\n"
        "  break-even = net / receipts. ≈$/mo scales net by the receipts' own time-span\n"
        "  (≥7 days, no clock). Missing input ⇒ INSUFFICIENT DATA, never an approximation.\n"
        "  NET-2: the cost of USING the tool is excluded unless `netsaved` covers every\n"
        "  receipt in the window. That term is ≥ 0, so COSTING stays safe to assert but a\n"
        "  non-negative net reads SAVING (GROSS) / BREAK-EVEN (GROSS), naming the exclusion.",
        ("cage/verdict.py", "cage/roi.py", "cage/netsaved.py", "cage/regression.py"),
        "the headline is modeled (it inherits the receipts' modeled savings); every\n"
        "  input line renders its own tag — measured drift, measured redo-rate."),
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
        "roi", ("roi", "return", "worth", "tool-cost", "latency", "investment"),
        "GROSS saved $ per tool vs that tool's own cost + latency",
        "per tool: Σ gross_saved_usd  vs  Σ meta.tool_cost_usd  and  Σ meta.added_latency_ms\n"
        "  net of own cost = gross − own cost (a deterministic tool declares $0 own cost —\n"
        "  which is NOT the same as free: the cost of USING it is in neither column).",
        ("cage/roi.py", "cage/convert.py", "cage/netsaved.py"),
        "inherits each receipt's method; the gross-$ side is only as trusted as its receipts."),
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
        "measured {c_measured} · estimated {c_estimated}\n"
        "  constants.DEFAULT_CONFIDENCE is the ladder; a receipt may carry its own.",
        ("cage/constants.py", "cage/origin.py", "cage/schema.py"),
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
        "budget", ("budget", "ceiling", "cap", "session", "daily", "exceed", "limit"),
        "session/day spend vs the policy ceilings",
        "Σ call_usd over the window vs [budgets] session_usd / daily_usd; on_exceed = warn|block.",
        ("cage/budget.py", "cage/prices.py", "cage.toml [budgets]"),
        "measured — totals real recorded calls; the ceiling is policy, not a guess."),

    # ── concept entries — how cage itself works, not how a value is computed ───
    Explanation(
        "capture-troubleshooting",
        ("capture", "captured", "capturing", "nothing", "missing", "empty",
         "troubleshoot", "troubleshooting", "why-no-rows", "probe",
         "windows", "location", "log-location"),
        "why is nothing being captured — the three-step diagnosis",
        "0. cage tells you first: when an agent's home exists but its log matched 0\n"
        "     files and it has never captured a row, `cage report`/`cage doctor` print a\n"
        "     triple-gated ⚠ 'capture is off for this agent' (self-silencing — one row\n"
        "     and it never fires again; opt out an unused agent with [sources.<agent>]\n"
        "     replace=true, paths=[]). The verdict is recorded at import into\n"
        "     cursors.json[_health], never a live probe on the read path.\n"
        "  1. `state/capture.log` — always-on, never gated on CAGE_DEBUG: one line per\n"
        "     agent per real import run (files_seen/rows_new/rows_total/src), the\n"
        "     standing proof capture ran at all. Pruned by the capture-log cleanup class.\n"
        "  2. `cage doctor --paths` — read-only probe of every candidate log location\n"
        "     per agent on this OS: found/missing, files matched, parseable rows,\n"
        "     cursor state, and a why-line per miss (wrong layout, cursor already\n"
        "     imported, unparseable format). Env overrides and any UNVERIFIED-LAYOUT\n"
        "     candidates are labeled.\n"
        "  3. `CAGE_DEBUG=1 cage import` — the same probes stream to debug.log as\n"
        "     metadata-only events, plus per-file parse/append/dedupe detail and, at\n"
        "     every receipt push/skip site, produced/skip_reason (`cage debug` to read).\n"
        "  4. `cage doctor --bundle` — exports capture.log + debug.log (plus cursors,\n"
        "     versions, policy provenance) as one redacted archive to attach to a bug\n"
        "     report; the home prefix is rendered as `~`, contents are counts-never-content.",
        ("cage/pathprobe.py", "cage/report.py", "cage/doctorbundle.py", "cage/capturelog.py"),
        "n/a — a diagnostic runbook, not a number.",
        kind="concept", plan_ref="§3.7"),
    Explanation(
        "sources",
        ("sources", "source", "import-path", "import-paths", "log-path",
         "custom-tool", "custom", "network-home", "nonstandard", "config-paths"),
        "add or replace the log locations cage imports from ([sources] in cage.toml)",
        "[sources] adds candidate import paths beyond the built-in registry — for a\n"
        "  nonstandard install, a network home, or a side-by-side log copy. Additive\n"
        "  by default (empty/absent [sources] = the built-in registry, byte-identical).\n"
        "    [sources.<agent>] paths = [\"~/alt/logs\", ...]   # one of the three agents\n"
        "    [sources.<agent>] glob  = \"usage-*.ndjson\"      # optional; absent ⇒ format default\n"
        "    [sources.<agent>] path_globs = [\"**/usage-*.ndjson\"]  # `--path` only (`cage query path-globs`)\n"
        "    [sources.<agent>] replace = true                 # ignore that agent's built-ins\n"
        "                                                     #   (empty paths ⇒ disabled)\n"
        "    [sources.<agent>] surface = \"cli\"                # cli|vscode|ide; restamps imported rows\n"
        "    [[sources.<agent>]] path = \"~/x\", glob = \"...\", surface = \"cli\"  # array form: per entry\n"
        "    [sources.<name>]  paths = [...], format = \"claude|copilot|kiro\"\n"
        "                                                     # a custom tool; rows stamp agent=<name>\n"
        "  Precedence: env home override > policy > built-in. ~ and $VARs expand; a glob\n"
        "  char (*?[) in a `path` is rejected (put it in `glob =`); empty glob=\"\" is an error.\n"
        "  `surface` (optional) stamps which client wrote the rows — set it for a non-IDE\n"
        "  store the parser would otherwise mislabel (a Kiro CLI log defaults to `ide`);\n"
        "  an out-of-set value is ignored (a `problems` entry), absent ⇒ the parser's value.\n"
        "  Capture-side only — no derived view changes.\n"
        "  Verify with `cage doctor --paths` (glob + provenance column: built-in|env|policy).\n"
        "  A committed project policy with a machine-absolute path warns — prefer\n"
        "  ~/.cage/cage.toml or a ~/… path. `policy sync` never touches [sources]; the\n"
        "  bundle ships the defaults as a COMMENT block (cage:sources-start), inert.\n"
        "  current sources:\n{sources_live}",
        ("cage/paths.py", "cage/importcmd.py", "cage/pathprobe.py"),
        "n/a — describes a capture-config mechanism, not a number.",
        kind="concept", plan_ref="output-and-simplification.plan.md Phase 4"),
    Explanation(
        "path-globs",
        ("path-globs", "path_globs", "path-glob", "import-path-flag", "path-flag",
         "root-agnostic", "anchored-glob", "two-globs", "chatsessions"),
        "why `--path` uses `path_globs`, not the anchored `[sources] glob`",
        "a [sources] entry carries TWO patterns, doing two different jobs:\n"
        "    glob        ANCHORED to that entry's `path` — drives every normal import\n"
        "    path_globs  ROOT-AGNOSTIC (**/…) — read ONLY by `cage import --path`\n"
        "                and `--project`, where the location is one YOU name\n"
        "  Why two: `--path` replaces the root, and an anchored pattern cannot survive\n"
        "  that. `*/chatSessions/*.jsonl` matches nothing when you point --path AT a\n"
        "  chatSessions directory — reusing `glob` would relocate the bug, not fix it.\n"
        "  (That was the real fault: copilot's --path branch hardcoded */events.jsonl,\n"
        "  the CLI shape only, so it could never reach the VS Code chatSessions store\n"
        "  even though the parser handles both.)\n"
        "  Directive A applies: code holds the SEED, `cage setup` MATERIALIZES it into\n"
        "  cage.toml, and import reads cage.toml. There is NO code fallback — an\n"
        "  unmaterialized project gets a loud no-op naming `cage setup --sync-sources`,\n"
        "  because a fallback would put the patterns back in two places.\n"
        "  Rules: `replace = true` replaces path_globs along with paths/glob (same\n"
        "  table, same semantics); extra entries union theirs in declaration order;\n"
        "  overlapping patterns never scan a file twice; a custom tool has none\n"
        "  (--path never reaches one); the zero-match warning NAMES the patterns tried.\n"
        "  copilot's seed names both shapes explicitly (**/events.jsonl,\n"
        "  **/chatSessions/*.jsonl) so a foreign .jsonl under your --path is never\n"
        "  matched — safe by construction, not by it happening to parse to zero rows.\n"
        "  Verify with `cage doctor --paths` (it flags a table with no path_globs).",
        ("cage/paths.py", "cage/importcmd.py"),
        "n/a — describes a capture-config mechanism, not a number.",
        kind="concept", plan_ref="path-globs.handoff.md §5"),
    Explanation(
        "config-file",
        ("config-file", "config", "toml", "policy-toml", "rename", "filename",
         "fallback", "migrate-config"),
        "which config file cage reads, and the policy.toml → cage.toml rename",
        "the project config is `.cage/cage.toml` — user-economics the derived views\n"
        "  read at compute time (prices, budgets, pipeline order, capture\n"
        "  switches). It was `policy.toml` through v0.35; the rename is NON-breaking:\n"
        "    · a lone legacy `policy.toml` is still READ (fallback) and MIGRATED to\n"
        "      `cage.toml` on the next `cage setup` (idempotent, never destructive);\n"
        "    · with BOTH on disk, `cage.toml` wins — `cage doctor` names the ignored\n"
        "      `policy.toml`, and a one-line stderr warning fires at load;\n"
        "    · the resolved name lives in ONE place (`paths.Footprint.policy`); writers\n"
        "      and `cleanup` follow it (cleanup never touches either name).\n"
        "  the bundled default (`data/cage.toml`) is read-only at runtime.",
        ("cage/paths.py", "cage/initcmd.py", "cage/cleanup.py"),
        "n/a — describes the config-file contract, not a number.",
        kind="concept", plan_ref="config-surfaces-and-rename.handoff.md"),
    Explanation(
        "prices-file",
        ("prices-file", "prices-toml", "prices.toml", "vendor-prices", "rate-card",
         "split", "credits", "where-prices-live"),
        "which file holds model prices, and why they split out of cage.toml",
        "model prices are a VENDOR rate card — researched at build time, shipped in the\n"
        "  bundle, replaced wholesale by `cage prices sync`. Your policy (budgets,\n"
        "  pipeline order, sources, and ROUTING decisions — [alias],\n"
        "  [tools.<tool>] price_at) is hand-edited and preserved. Opposite lifecycles,\n"
        "  so they live in separate files: **vendor facts move, routing decisions stay**.\n"
        "    · `.cage/prices.toml` holds every [prices.<provider>.<model>] row, [credits],\n"
        "      and the [meta] prices_version/prices_date counters (project {prices_version_project}).\n"
        "    · `.cage/cage.toml` keeps everything else — including [alias] and tool routes,\n"
        "      and [meta] cage_version/policy_version.\n"
        "  Resolution mirrors the cage.toml rename (one place, `paths.Footprint.prices`):\n"
        "    · a legacy project with prices still inline in `cage.toml` is READ untouched\n"
        "      (fallback) and MIGRATED to `prices.toml` on the next `cage setup` —\n"
        "      money-neutral (rows equal to the bundle drop, customizations become\n"
        "      overrides), idempotent, never destructive;\n"
        "    · with BOTH carrying prices, `prices.toml` wins — `cage doctor` names the\n"
        "      ignored in-cage.toml block and a one-line stderr warning fires at load;\n"
        "    · `cage prices set`/`sync` write `prices.toml`; `alias`/`route-tool` write\n"
        "      `cage.toml`; `policy.load` still returns ONE merged dict, so the money\n"
        "      resolves identically either way. `cleanup` protects both files.",
        ("cage/paths.py", "cage/policy.py", "cage/initcmd.py"),
        "n/a — describes the prices-file contract, not a number.",
        kind="concept", plan_ref="prices-toml.plan.md §3"),
    Explanation(
        "capture-on-read",
        ("capture-on-read", "on-read", "lazy", "sweep", "read-sweep", "hookless",
         "canonical", "routing", "route-key", "reclaim", "why-ledger", "no-import",
         "quiet", "captured", "throttle"),
        "how a read captures first — the hookless primary path",
        "Every read that matters (report / insights / the MCP read tools) lazily runs the\n"
        "  incremental import sweep BEFORE it answers, so a number is never staler than the\n"
        "  instant it's shown — no hook, no scheduler, no daemon. Cursors make a warm no-op\n"
        "  a stat per source file; the sweep is throttled on the `_last_import` cursor\n"
        "  (policy [capture] read_throttle_secs, ~60s fallback), so back-to-back reads don't\n"
        "  re-sweep. When new rows land, a dim `· captured N new … since last read` line\n"
        "  prints to STDERR (never stdout — a --json/--csv stream stays pure); zero new ⇒\n"
        "  silent. The MCP read tools return the same summary as a structured field.\n"
        "  Push (graphify/fux/proxy) and pull both resolve ONE canonical ledger\n"
        "  (`paths.canonical_ledger`), and a pushed receipt carries a non-PII routing key\n"
        "  (a hash of the resolved ledger-root path, never a basename) so a project read\n"
        "  can reclaim a stray saving by EXACT key — never a blind union.\n"
        "  Suppress: --no-import (this read), CAGE_CAPTURE_ON_READ=0 (standing, the\n"
        "  determinism switch), or CAGE_CAPTURE=0 (all capture). Silence the line with\n"
        "  --quiet / CAGE_QUIET=1. Diagnose with --why-ledger (which ledger + why + key),\n"
        "  `cage doctor` (per-source, per-mode pull/push timeline — doctor never sweeps),\n"
        "  and CAGE_DEBUG=1 (ledger-resolution decisions, every sweep, every reclaim).\n"
        "  Fail-open: a capture error is traced, never blocks the read. Determinism holds —\n"
        "  it changes WHEN rows arrive, never how a number is computed; the golden/\n"
        "  determinism suites run with it off against a fixed ledger.",
        ("cage/importcmd.py", "cage/paths.py", "cage/report.py"),
        "n/a — describes the capture trigger, not a number.",
        kind="concept", plan_ref="capture-architecture.plan.md §2, §3, §12"),
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
        "  (report/attrib/matrix/budget/roi) globs the shards (+ any legacy\n"
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
        "  Code / Copilot / Kiro session logs) · MCP (mcpserver.py, read-only).\n"
        "  the transcript agents capture pull-based: `cage import` (and capture-on-\n"
        "  read) sweep the on-disk session logs — no hooks, so nothing depends on which\n"
        "  client wrote the log; re-imports dedupe by call id.\n"
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
        ("cage/attribution.py", "cage.toml [tools.order]"),
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
        "  the outside (e.g. `cage data graphify -- graphify query …`) without that tool\n"
        "  knowing cage exists — the receipt is filed by cage's wrapper, not the tool.\n"
        "  Dollars: a receipt linked to a call prices at that call's model; a\n"
        "  call-less token receipt prices via the resolution ladder — see\n"
        "  `receipt-pricing` (price_at → task-model → UNPRICED).",
        ("cage/schema.py", "cage/graphifymeter.py", "cage/receiptprice.py"),
        "n/a — describes two receipt-filing strategies, not a number.",
        kind="concept", plan_ref="§4.5"),
    Explanation(
        "migrate-savings", ("migrate-savings", "migrate", "migration", "consolidate",
                            "union", "dedupe", "duplicate", "savings-tree"),
        "how `cage data migrate-savings` moves graphify savings without changing a number",
        "graphify savings used to land in the shared receipts.jsonl; they now belong in\n"
        "  the savings/graphify/ tree. `cage data migrate-savings` (dry-run by default,\n"
        "  --apply to execute) COPIES each historical tool=\"graphify\" receipt into the\n"
        "  tree, keeping its ORIGINAL id and sharding by its OWN ts. receipts.jsonl is\n"
        "  never rewritten (append-only law — the only ledger mutation is append).\n"
        "  Precision is read-side: `ledger.receipts()` is an id-deduped UNION of both\n"
        "  stores (tree wins on a duplicate id — ids carry the only entropy, so identity\n"
        "  dedupe is exact). So a row now present in both stores counts exactly once: a\n"
        "  re-run is a no-op, a half-completed migration still reads correct totals, and\n"
        "  attrib/report/roi are byte-identical before and after. --apply refuses when the\n"
        "  two stores disagree on a shared id's saved value — the totals can't reconcile,\n"
        "  so it stops rather than guess. graphify only; human/fux stay in receipts.jsonl.",
        ("cage/migratecmd.py", "cage/ledger.py", "cage/mergeutil.py"),
        "n/a — describes why the migrated number stays exact, not a number.",
        kind="concept", plan_ref="§3"),
    Explanation(
        "kiro-routing", ("kiro", "kiro-ide", "kiro-cli", "machine-ledger", "double-count",
                         "why-no-kiro", "tokens-generated", "conversations-v2",
                         "machine-fact", "adr-0006", "credits-scope"),
        "why kiro's rows land in the machine ledger, and what they can't tell you",
        "kiro has TWO stores with OPPOSITE properties, so they get opposite treatment:\n"
        "  · IDE (tokens_generated.jsonl) — ONE global append-only file with no project,\n"
        "    no session and no per-turn timestamp. Every ledger that imported it read the\n"
        "    same turns, so a per-project kiro cost was never a fact. These rows are a\n"
        "    MACHINE fact and are written to the global ledger only ({global_base}), so\n"
        "    one copy exists per machine and double-counting is impossible by\n"
        "    construction. A project report says so rather than showing nothing.\n"
        "  · CLI (conversations_v2, SQLite) — keyed by the cwd it ran in, with a real\n"
        "    conversation id and timestamp. That IS project-attributable, so it gets the\n"
        "    opposite fix: scoped to the project's directory tree and stamped with\n"
        "    `project`. Routing it to the machine ledger would destroy real attribution.\n"
        "  An explicit --ledger/CAGE_BASE always wins for both — cage never routes around\n"
        "  a sink you named.\n"
        "  THE LIMITS, stated plainly: an IDE row's `ts` is stamped at IMPORT, `session` is\n"
        "  the constant \"kiro\", `project` is absent and `tokens_out` is usually 0. So kiro\n"
        "  rows cannot be ordered, windowed or attributed, and no kiro ON/OFF token delta\n"
        "  may ever be reported. Cage can never be more precise than its source.\n"
        "  Already-recorded rows are never rewritten (append-only): a project ledger that\n"
        "  collected duplicated kiro rows before v0.36 keeps them, and gains no new ones.",
        ("cage/paths.py", "cage/importcmd.py", "cage/transcript.py", "cage/report.py"),
        "n/a — describes where rows are stored and what they can't say, not a number.",
        kind="concept", plan_ref="§3.7 · ADR 0006"),
    Explanation(
        "savings-axis", ("tier-1", "tier-2", "agent-vs-human", "human", "human-axis",
                         "tool-vs-tool", "whole-task", "attested", "derived-attention",
                         "minutes", "human-cost", "hours-saved", "removed"),
        "the axis cage measures savings on (and the human axis it no longer does)",
        "cage measures ONE savings axis: tool vs tool, inside one agent run\n"
        "  (attribution.py / matrix.py) — what did each tool in the pipeline save\n"
        "  versus that tool being off, marginal-by-fixed-order.\n"
        "  The Tier-1 agent-vs-human axis (the `human` verb group, $/hr rates,\n"
        "  attested and turn-gap-derived minutes) was REMOVED in v0.36, substrate\n"
        "  included: calls no longer carry a turn gap, `minutes` is not a unit.\n"
        "  Legacy ledgers still read: a pre-0.36 `tool=\"human\"` receipt (or any\n"
        "  `unit=\"minutes\"` row) is EXCLUDED from every money view and counted in a\n"
        "  footnote on `cage report` — never silently folded into a total, never\n"
        "  priced. Rows are append-only and are never rewritten.",
        ("cage/attribution.py", "cage/matrix.py", "cage/report.py"),
        "n/a — describes the measurement axis, not a number.",
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
        "  economics in cage.toml (prices, budgets, pipeline order) ·\n"
        "  constants = code heuristics that must stay reviewable but aren't config\n"
        "  (chars-per-token, the matrix ceiling, the method trust ranking, the\n"
        "  confidence fallback) — see constants.py.",
        ("cage/schema.py", "cage/constants.py", "cage.toml"),
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
        "  team: cage authorship ledger-sync unions local rows into refs/notes/cage-ledger by row\n"
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
                     "counted-as-0", "understated", "no-price-row", "dash",
                     "em-dash", "—"),
        "what an UNPRICED cell means and how to fix it",
        "a call whose model matched none bills $0 — the totals are understated and\n"
        "  every read surface says so out loud rather than hiding it (a wrong number\n"
        "  is worse than none). In text tables the cell renders `—` (the ONLY\n"
        "  meaning of the dash: couldn't price; `$0.0000` is always a real zero),\n"
        "  the TOTAL carries `(+ unpriced)`, and the full ⚠ block renders in the\n"
        "  `--usd` view (the token default carries one muted pointer). CSV keeps an\n"
        "  explicit empty + priced_via=none — the glyph never enters data.\n"
        "  Fix workflow: `cage prices unpriced` lists each\n"
        "  offending (provider, model) with call count, token volume, and a\n"
        "  ready-to-run fix line; find the real rate on the vendor's pricing page\n"
        "  (cage never fetches — no network on any cage code path), then\n"
        "  `cage prices set <provider> <model> --input … --output …` or, for a\n"
        "  router pseudo-model, `cage prices alias`. Caveat: self-costed rows\n"
        "  (stored est_cost_usd) and receipts keep their recorded values.\n"
        "  Tool receipts refuse the same way: a call-less token receipt no ladder\n"
        "  rung prices prints its own ⚠ line with a runnable fix —\n"
        "  {unpriced_hint}\n"
        "  (see `receipt-pricing` for the ladder).",
        ("cage/pricescmd.py", "cage/report.py", "cage/prices.py"),
        "n/a — the $0 is the absence of a number; fixing it makes the totals honest."),
    Explanation(
        "receipt-pricing", ("ladder", "call-less", "price_at", "tool-receipt",
                            "task-model", "dominant", "rung", "graphify-dollars"),
        "how a call-less token receipt resolves to dollars (the pricing ladder)",
        "a token receipt with no resolvable call (graphify/fux shims — the saved\n"
        "  tokens belong to future calls the shim can't know) prices by a\n"
        "  deterministic ladder, resolved at derive time (never written back):\n"
        "  1. price_at — explicit routing: [tools.<tool>] price_at = \"provider/model\",\n"
        "     written by `cage prices route-tool <tool> --to <provider>/<model>`\n"
        "     (this policy: {tool_routes}). A dangling route is UNPRICED, never a\n"
        "     fall-through — the dangling-alias rule.\n"
        "  2. task-model — the dominant model of the calls joined to the receipt's\n"
        "     task (task-id calls + session-window adoptions): max Σ tokens_in,\n"
        "     ties → call count → lexicographic provider/model (a total order).\n"
        "  3. refusal — UNPRICED, loudly: {unpriced_hint}.\n"
        "  The USD keeps the receipt's own method; the rung is footnoted in\n"
        "  roi/attrib text and a `priced_via` CSV column. Receipts with a\n"
        "  resolvable call never enter the ladder (their path is unchanged).",
        ("cage/receiptprice.py", "cage/convert.py", "cage/roi.py"),
        "inherits the receipt's method (modeled, never measured); the rung is "
        "always visible."),
    Explanation(
        "repricing", ("repricing", "reprice", "retroactive", "derive-time",
                      "recompute", "price-change", "fleet-reprice", "back-price"),
        "why fixing a price re-prices history without touching the ledger",
        "pricing is derive-time: report/budget/compare/study recompute every call\n"
        "  as tokens × the *current* policy row on each run — the ledger stores\n"
        "  counts, not conclusions, and is never rewritten. So an analyst fixing\n"
        "  cage.toml re-prices every imported bundle row retroactively: same\n"
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
        "  cage prices route-tool <tool> --to <provider>/<model> — price a tool's\n"
        "    call-less token receipts (rung 1 of `receipt-pricing`; --remove deletes;\n"
        "    a dangling target writes with a warning, unlike alias's refusal).\n"
        "  cage prices list — every visible row, bundled vs project, which wins.\n"
        "  cage prices sync — diff vs the installed bundle (dry-run; --update + --yes).\n"
        "  Research: cage never fetches a price — check the vendor's pricing page (or\n"
        "  search \"<vendor> <model> API pricing\"), then paste the fix line. `set`/`sync`\n"
        "  write the project prices.toml ({prices_version_project}); alias/route-tool\n"
        "  write cage.toml (routing decisions — see `prices-file`). The bundled table\n"
        "  ({prices_version_bundled}) is read-only at runtime. Derived views re-price\n"
        "  immediately — the ledger is never rewritten.",
        ("cage/pricescmd.py", "cage/pricestoml.py", "prices.toml [prices]"),
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
        "the bundled prices carry [meta] prices_version {prices_version_bundled};\n"
        "  `cage setup` (and the first `cage prices set`) stamp the project prices.toml\n"
        "  with the bundle it derived from (this project: {prices_version_project}).\n"
        "  `cage doctor` and `cage prices list` compare the two — a newer bundle\n"
        "  prints one recommendation line to run `cage prices sync`, never\n"
        "  auto-applied. sync classifies each row: in-sync (equal), customized\n"
        "  (cage-managed/marked — never clobbered), or drift (provenance unknown —\n"
        "  cage can't reconstruct which old bundle a row came from, so it lists the\n"
        "  diff and applies only rows you confirm per --yes).",
        ("cage/pricescmd.py", "cage/data/prices.toml [meta]", "cage/doctorcmd.py"),
        "n/a — describes version bookkeeping, not a number.",
        kind="concept", plan_ref="§3.3"),
    Explanation(
        "policy-sync", ("policy-sync", "policy-upgrade", "policy-diff", "tunables",
                        "sync-categories", "neutrality", "policy-defaults",
                        "add-update-keep-orphan"),
        "upgrading an old project cage.toml to the installed bundle's defaults",
        "`cage policy sync` (dry-run; `cage policy diff` is the same view) compares\n"
        "  the project cage.toml against the installed bundle's non-pricing\n"
        "  defaults (bundled policy_version {policy_version_bundled}, this project:\n"
        "  {policy_version_project}) and buckets every key: **add** (in the bundle,\n"
        "  missing here — --apply writes it with one provenance comment), **update**\n"
        "  (equal to a recorded *old* default whose bundled value changed — refreshed),\n"
        "  **keep** (customized — marked/cage-managed, or differing where no default\n"
        "  ever changed: your edit, never touched), **orphan** (the bundle dropped it\n"
        "  — warned, never deleted). Not reconstructable (pre-policy_version file +\n"
        "  a changed default) → listed, applied only per --yes. Neutrality invariant:\n"
        "  on a zero-customization project, --apply changes no derived view by one\n"
        "  byte — adds only pin defaults policy.load was already merging in. Pricing\n"
        "  tables delegate to `cage prices sync` (one merge brain); nothing ever\n"
        "  auto-applies either sync.",
        ("cage/policysync.py", "cage/pricestoml.py", "cage/data/cage.toml [meta]"),
        "n/a — describes the upgrade verb; it never changes a derived number.",
        kind="concept", plan_ref="§3.10"),
    Explanation(
        "prices-freshness", ("prices-freshness", "freshness", "stale", "staleness",
                             "stale-days", "prices-date", "age", "outdated"),
        "the three local freshness signals behind the pricing staleness note",
        "cage never fetches a price, so \"are my prices current?\" is answered from\n"
        "  local evidence only — three signals, one implementation (freshness.py):\n"
        "  1. sync drift — project [meta] older than the installed bundle\n"
        "     (project {prices_version_project} vs bundled {prices_version_bundled})\n"
        "     → the `cage prices sync` recommendation, verbatim.\n"
        "  2. bundle age — the bundle's own prices_date ({prices_date_bundled}) is\n"
        "     more than stale_days (now: {prices_stale_days}; policy [prices]\n"
        "     stale_days, 0 disables) old → \"check for a newer cage release\": a\n"
        "     faithfully synced project can still be confidently stale.\n"
        "  3. UNPRICED presence — calls or call-less token receipts billing $0 →\n"
        "     the existing runnable hints ({unpriced_hint}).\n"
        "  Two surfaces render the same lines: `cage doctor` (always shown) and the\n"
        "  `cage report` footer (actionable-only). Clocks: the report footer anchors\n"
        "  age on the newest ledger ts (data-relative — derived views stay\n"
        "  deterministic); doctor may use today.",
        ("cage/freshness.py", "cage/doctorcmd.py"),
        "n/a — describes the check; the ⚠/· lines it prints are advisory, never a gate.",
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
        "  tokens. The bare router id copilot/auto matches no price row by design —\n"
        "  a router priced silently would be a wrong number — so it resolves one of\n"
        "  two other ways: a recorded billed credit prices it exactly (rung 1, see\n"
        "  `cage query copilot-credits`), or you route it explicitly\n"
        "  (`cage prices alias - copilot/auto --to …`). Neither guesses.",
        ("cage/transcript.py", "cage/policy.py", "cage/creditprice.py",
         "cage/data/cage.toml"),
        "n/a — describes a billing approximation and its provenance.",
        kind="concept", plan_ref="§3.3, §3.8"),
    Explanation(
        "copilot-credits", ("copilot-credits", "credits", "billed", "usd-per-credit",
                            "billing", "ladder", "rung", "copilot-auto", "priced-via",
                            "credits-rate", "token-table", "mixed-basis"),
        "how a copilot row picks its price: the credits → tokens → UNPRICED ladder",
        "Copilot persists the credits GitHub itself billed — per request in VS\n"
        "  Code's chatSessions store (copilotCredits), per shutdown in the CLI's\n"
        "  totalPremiumRequests. Cage records that figure VERBATIM as the call\n"
        "  field `credits` and resolves each copilot dollar by a 3-rung ladder,\n"
        "  one rung per row, at the single pricing choke point:\n"
        "    1. credits × [billing.<agent>] usd_per_credit  — when the row carries\n"
        "       a recorded credit AND you configured a rate. Tag: modeled.\n"
        "    2. tokens × price table  — the usual exact/alias/family matching.\n"
        "    3. UNPRICED  — loud, counted, with runnable fix lines.\n"
        "  Rung 1 goes first because since 2026-06-01 a credit IS GitHub's own\n"
        "  tokens×rates computation, made with what cage cannot see: which model\n"
        "  copilot/auto actually routed to, and GitHub's current rates. So it\n"
        "  prices copilot/auto exactly, with no price-table row at all.\n"
        "  Method law: rung 1 is modeled, never measured — the credit COUNT is a\n"
        "  recorded fact, but the DOLLAR is that count times a rate you set, which\n"
        "  cage cannot check against an invoice. No rate configured ⇒ rung 1 is\n"
        "  skipped and credits render as a COUNT, never a dollar.\n"
        "  Credits are never derived from tokens, in either direction: an absent\n"
        "  credit stays absent (it falls through to rung 2), and a recorded 0.0 is\n"
        "  a REAL zero that prices at $0.0000 — a different fact from absence.\n"
        "  A total spanning both bases is footnoted with the split (never blended\n"
        "  silently); CSV names the winning basis per row in `priced_via`\n"
        "  (credits-rate | token-table | mixed).",
        ("cage/creditprice.py", "cage/prices.py", "cage/schema.py",
         "cage/transcript.py", "cage/policy.py"),
        "rung 1: usd = credits × [billing.<agent>] usd_per_credit  (modeled)",
        kind="concept", plan_ref="§3.1, §3.3"),
    Explanation(
        "cleanup", ("cleanup", "state-dir", "prune", "stale", "retention", "warn",
                    "debug-log-growth", "cursors", "pending-buffers"),
        "what `cage data cleanup` may touch — and what it never may",
        "a CLOSED allowlist over .cage/state/ only: aged debug.log / capture.log /\n"
        "  hooks-seen.jsonl rows, stale pending-* provenance buffers, cursors whose\n"
        "  source log is gone (safe: the next import re-reads and id-dedupe absorbs\n"
        "  it), *.tmp. (hooks-seen.jsonl is a legacy file cleaned on real machines —\n"
        "  cage no longer writes hooks.) Never — by construction, not convention:\n"
        "  ledger/ (tool savings included — a per-tool cleanup class must never be\n"
        "  added, savings are unrecoverable), cage.toml, the machine id (fleet\n"
        "  pairing breaks without it), study.jsonl, limits.json. Window: [cleanup]\n"
        "  days = {cleanup_days}. Deletion only ever happens via an\n"
        "  explicit `cage data cleanup --apply`, which runs regardless of [cleanup]\n"
        "  enabled — an explicitly-typed command is always honored. The auto path\n"
        "  (piggybacked on `cage import`/read sweeps, throttled, fail-open — cage\n"
        "  installs no scheduler) only ever WARNS on stderr, silent when nothing is\n"
        "  eligible, never deletes: gated by [cleanup] enabled (currently\n"
        "  {cleanup_on}; env CAGE_CLEANUP — off means no automatic anything, not even\n"
        "  the reminder) and, when enabled, by [cleanup] warn (currently\n"
        "  {cleanup_warn_on}; env CAGE_CLEANUP_WARN). State files are never read by\n"
        "  derived views, so cleanup cannot change a single reported number.",
        ("cage/cleanup.py", "cage/policy.py", "cage.toml [cleanup]"),
        "n/a — describes state maintenance, not a number.",
        kind="concept", plan_ref="§3.6.4"),
    Explanation(
        "import-before-export", ("import-before-export", "export-sweep", "no-import",
                                 "self-refreshing", "snapshot", "bundle-freshness"),
        "why `cage data export` imports first (and how to get a frozen snapshot)",
        "export runs the all-agent import sweep before emitting/bundling, so a\n"
        "  machine that never ran an explicit `cage import` still ships a complete\n"
        "  bundle (capture is pull-only) — one `cage data export --study` is enough. Currently\n"
        "  {import_before_export}. Precedence: the --no-import flag wins per\n"
        "  invocation > env CAGE_CAPTURE=0 (pauses all capture, sweep included) >\n"
        "  policy [capture] import_before_export. The sweep is fail-open — a broken\n"
        "  parser warns and export proceeds with the pre-sweep ledger — and the\n"
        "  study bundle's manifest records whether it ran and how many rows it added\n"
        "  (counts only), so the analyst can tell self-refreshed from snapshot.",
        ("cage/exportcmd.py", "cage/study.py", "cage.toml [capture]"),
        "n/a — describes capture freshness, not a number.",
        kind="concept", plan_ref="§3.7"),
    Explanation(
        "display", ("display", "usd", "--usd", "dollars", "tokens-default",
                    "token-view", "dollar-view", "signal-gating", "gating",
                    "all-columns", "hide", "columns", "why-no-cost-column",
                    "where-are-dollars"),
        "tokens by default, dollars opt-in, and signal-gated columns",
        "tokens are the measurement; dollars are an interpretation you ask for\n"
        "  (plan Phase 2.5). `cage report`, `cage insights matrix`, and the bare `cage`\n"
        "  headline render tokens-only until `--usd` asks for currency — or set\n"
        "  `[display] usd = true` for always-on (precedence: flag > env CAGE_USD >\n"
        "  policy). Pricing footnotes and the full ⚠ UNPRICED block belong to the\n"
        "  `--usd` view; the token view carries one muted unpriced pointer.\n"
        "  Signal-gating composes: saved/net (and saved-tok) columns render only\n"
        "  when ≥1 receipt exists in the window — otherwise one line explains, and\n"
        "  `--all-columns` restores the fixed shape for scripts. Hard line: a\n"
        "  negative net with real receipts is never suppressed. Display-only —\n"
        "  pricing always computes underneath (budget guards, UNPRICED detection),\n"
        "  money-native views (budget/roi/verdict/compare/estimate) always show\n"
        "  dollars, and CSV never gates (full schema, always).",
        ("cage/display.py", "cage/report.py", "cage/matrix.py", "cage.toml [display]"),
        "n/a — a presentation rule; every dollar that does render keeps its method tag.",
        kind="concept", plan_ref="output-and-simplification.plan.md Phase 2"),
    Explanation(
        "csv-output", ("csv", "csv-output", "spreadsheet", "excel", "pivot",
                       "pivot-table", "flat-table", "reporting-format",
                       "report-csv", "one-way"),
        "the CSV reporting surface: which views, the column law, csv-vs-bundle",
        "`--csv` on report · attrib · roi · compare · study report · calibration\n"
        "  — stdout by default (pipe-friendly),\n"
        "  `--csv <path>` writes a file. Raw rows: `cage data export --csv\n"
        "  calls|receipts|tasks` (flat ledger rows for pivot tables; the ledger's\n"
        "  own PII surface — counts and ids, never content). MCP mirrors it: a\n"
        "  `format: csv` param on the report/attrib/roi tools.\n"
        "  Laws: one shared data structure per view feeds the text table AND the\n"
        "  CSV — same numbers by construction, never computed twice; method/match\n"
        "  tags are COLUMNS (a spreadsheet can tell measured from estimated), and\n"
        "  refusals/caveats/UNPRICED counts survive into the rows; stdlib `csv`,\n"
        "  RFC-4180 quoting, LF line endings pinned on every OS (deterministic:\n"
        "  same ledger + policy ⇒ byte-identical CSV). The column contracts live in\n"
        "  `csvout.py` itself (one render_csv beside each render_*). Two export kinds,\n"
        "  never blurred: CSV is one-way\n"
        "  REPORTING and never an import source; the fleet bundle (`cage data export\n"
        "  --study`) stays jsonl — lossless, merge-by-id, re-importable.",
        ("cage/csvout.py", "cage/exportcmd.py", "cage/report.py", "cage/mcpserver.py"),
        "n/a — describes an output format; every row still carries its own method tag.",
        kind="concept", plan_ref="§3.9"),
    Explanation(
        # NB: no "cage-run"/"workspacefolder" keywords — their "cage"/"work" stems
        # would steal generic "how does cage work"-style queries from `overview`.
        "portable-wiring", ("portable-wiring", "portable", "shim", "absolute-path",
                            "clone", "teammate", "committed", "broken-wiring",
                            "team-share", "gitignore"),
        "why committed wiring references .cage/bin/cage-run, never an absolute path",
        "the committed MCP wiring (.mcp.json, .vscode/mcp.json) used to embed\n"
        "  the wiring machine's absolute cage path — one dev's filesystem shipped to\n"
        "  the team, breaking every clone. They now reference the committed shim\n"
        "  .cage/bin/cage-run (identical bytes on every machine), which resolves cage\n"
        "  at RUNTIME: cage on PATH → ~/.local/bin / pipx / active $VIRTUAL_ENV →\n"
        "  python3 -m cage → exit 0 silently. cage absent ⇒ a working (unmetered)\n"
        "  editor, no noise (fail-open extended to wiring; `cage doctor` diagnoses).\n"
        "  Per host: .mcp.json uses the documented ${{CLAUDE_PROJECT_DIR:-.}}\n"
        "  expansion; .vscode/mcp.json uses ${{workspaceFolder}}. Kiro resolves\n"
        "  NEITHER (it spawns MCP servers from its install dir and substitutes no\n"
        "  variables), so .kiro/settings/mcp.json used to be the ONE exception and\n"
        "  had to be gitignored. It no longer is: it carries no path AT ALL —\n"
        "  `python3 -m cage mcp`, resolved through PATH like any interpreter — so it\n"
        "  is byte-identical everywhere and COMMITTED like the other two. The price,\n"
        "  named not buried: it depends on WHICH python3 resolves, so `cage doctor`'s\n"
        "  kiro-mcp check asks that interpreter to import cage and says so if it\n"
        "  can't. On Windows `python3` is often absent — doctor names that too, and\n"
        "  `cage setup --python-launcher` writes the `py -3` form for that machine.\n"
        "  Re-running `cage setup` migrates legacy absolute entries and prints what\n"
        "  moved; `cage doctor` has a portability check and names the wiring mode.\n"
        "  Opt-in python-launcher mode (`cage setup --python-launcher`, persisted as\n"
        "  [wiring] python_launcher = true) makes the shim + user-level wiring resolve\n"
        "  through the interpreter only — nothing exe-shaped probed or executed;\n"
        "  CAGE_RUN_PYTHON=1 is the runtime-only override on the standard shim. See\n"
        "  `cage query restricted-env`.",
        ("cage/runshim.py", "cage/claudewire.py",
         "cage/kirowire.py", "cage/doctorcmd.py"),
        "n/a — describes the wiring mechanism, not a number.",
        kind="concept", plan_ref="§5"),
    Explanation(
        # NB: keywords avoid generic stems ("wiring", "setup", "verb") that would
        # steal queries from `overview`/`portable-wiring` — same discipline as above.
        "stale-wiring", ("stale-wiring", "stale", "orphaned", "dead-verb", "liveness",
                         "renamed", "silently", "unmetered", "interceptor",
                         "false-ok", "heal", "shadowed", "path-winning", "bypass",
                         "hook-bypass"),
        "how cage detects and heals an installed artifact whose verb no longer exists",
        "a wiring artifact written before a verb was renamed still names the OLD\n"
        "  verb, so it exits 1 — and because hook/shim output goes nowhere and both\n"
        "  shims fail open to exit 0, a dead verb is indistinguishable from cage not\n"
        "  being installed. That silently disabled capture for 9 days while doctor\n"
        "  reported OK, because the interceptor check tested existence + PATH, not\n"
        "  liveness.\n"
        "  DETECTION (`cage/wiringscan.py`, read-only — nothing is ever executed):\n"
        "  every installed artifact's command tail is resolved to its verb and\n"
        "  checked against the LIVE PARSER (cli.build_parser()), which is the same\n"
        "  code the CLI runs and therefore ground truth for 'will this exit 1'.\n"
        "  verbmap.REMOVED is NOT the detector — it only supplies the replacement\n"
        "  tail. The distinction matters: a verb deleted outright rather than renamed\n"
        "  is dead and absent from REMOVED, so a grep against it would miss the\n"
        "  artifact entirely. User-level files are scanned too (~/.copilot/hooks,\n"
        "  .git/hooks) — the real failures were user-level, and these hold\n"
        "  pre-removal hook leftovers cage no longer writes.\n"
        "  HEALING: `cage setup` rewrites a dead verb to its current form via\n"
        "  verbmap.REMOVED, alongside the absolute-path→shim migration it already\n"
        "  does, and refreshes a stale bin/graphify interceptor. Idempotent; foreign\n"
        "  (non-cage) hooks are never touched; a dead verb with no known replacement\n"
        "  is reported, never guessed at.\n"
        "  Severity: a dead WIRED command is a failure (capture is silently off).\n"
        "  See `cage doctor` — the wiring check names each fault and its fix.\n"
        "  THE PATH-WINNING INTERCEPTOR (cage/pathshim.py): the graphify shim that\n"
        "  actually RUNS is whichever `graphify` PATH resolves first, which can live\n"
        "  in a DIFFERENT project's bin/ — outside every root cage scans. That is how\n"
        "  a dead adopt-era shim ran unmetered for nine days while doctor, run in\n"
        "  cage, reported OK. So cage resolves graphify the way the shell does (walk\n"
        "  PATH, first executable wins) and classifies that one file: live · dead (a\n"
        "  cage interceptor naming a removed verb — a doctor FAILURE, capture is\n"
        "  silently off) · shadowed (this root has a shim but a different file wins —\n"
        "  advisory, names BOTH paths) · foreign (not cage-written — reported, never\n"
        "  touched; metering is off by absence, a different message from a dead shim).\n"
        "  HEALING THAT WINNER: `cage setup` refreshes it only when it is dead AND\n"
        "  sits in a cage-managed root (a <root>/bin/graphify beside a <root>/.cage/).\n"
        "  Outside one, cage NEVER writes — doctor names the file and prints the fix.\n"
        "  THE HOOK BYPASS (cage/hookbypass.py): the mirror image — an agent hook that\n"
        "  invokes graphify by ABSOLUTE PATH never traverses PATH at all, so the\n"
        "  interceptor cannot see it, and a hook is not a Bash tool call so the\n"
        "  transcript route cannot either. Both capture routes are blind. This is\n"
        "  ADVISORY, never a failure: graphify works as designed and cage merely\n"
        "  cannot observe that path — savings from an explicit `graphify query` are\n"
        "  unaffected. With --strict (or GRAPHIFY_HOOK_STRICT) the read hook DENIES\n"
        "  the first raw read, so the avoided read is a real saving unmeterable by any\n"
        "  current route, and the wording escalates. The hook is never modified.",
        ("cage/wiringscan.py", "cage/pathshim.py", "cage/hookbypass.py",
         "cage/doctorcmd.py", "cage/verbmap.py", "cage/paths.py"),
        "n/a — describes a detection + repair mechanism, not a number.",
        kind="concept", plan_ref="§5"),
    Explanation(
        # NB: keywords avoid the bare "wiring"/"interceptor" stems already owned by
        # `stale-wiring` — this entry is specifically about the TWIN PAIR, not the
        # general dead-verb detector.
        "graphify-shims", ("graphify-shims", "twin", "twins", "graphify.cmd",
                           "pathext", "cmd-twin", "windows-graphify",
                           "windows-interceptor", "shim-contract", "call-not-exec"),
        "why the graphify interceptor is TWO files, and what each one can't do",
        "one behaviour contract, two implementations (docs/shim-contract.md): the\n"
        "  extensionless POSIX `bin/{graphify_shim_posix}` and the Windows\n"
        "  `bin/{graphify_shim_windows}`. Windows resolves a bare `graphify` ONLY\n"
        "  through PATHEXT, which has no extensionless entry — so on Windows only the\n"
        "  .cmd twin can ever run, and the .cmd is a no-op file everywhere else. This\n"
        "  OS resolves: bin/{graphify_shim_here}. Both twins install on every OS\n"
        "  regardless (`cage setup`, `adoptcmd.refresh_shim`) — a committed bin/ must\n"
        "  be byte-identical across machines, so a project scaffolded on one OS keeps\n"
        "  working when opened on another (ADR 0007).\n"
        "  A ROOT CARRYING ONLY THE WRONG TWIN is a doctor FAILURE, not a green tick —\n"
        "  existence + PATH + live verbs is not enough if this OS structurally cannot\n"
        "  resolve the file (the F1 lesson, applied to a second OS).\n"
        "  IDENTITY IS CONTENT, NEVER FILENAME: each twin self-identifies via the same\n"
        "  marker set (`cage data graphify`, its pre-rename bare form with no `data`,\n"
        "  or the header string \"graphify metering interceptor\") so neither twin can\n"
        "  ever select the OTHER as the real binary — recursion is impossible by four\n"
        "  independent mechanisms (content skip, PATHEXT/extensionless structural\n"
        "  blindness, the CAGE_GRAPHIFY_SHIM re-entry guard, a bounded walk).\n"
        "  WHERE THE TWINS DIVERGE (documented, never hidden): cmd has no `exec`, so\n"
        "  the real binary runs as a CHILD process (`call` + `exit /b` on its own\n"
        "  line — a one-line `& exit /b %ERRORLEVEL%` reports the WRONG exit code,\n"
        "  because %ERRORLEVEL% expands at parse time before `call` runs); Ctrl-C on\n"
        "  the cmd twin prompts `Terminate batch job (Y/N)?`; `.EXE` precedes `.CMD`\n"
        "  in the default PATHEXT, so resolution is directory-major/extension-minor —\n"
        "  the twin must never share a DIRECTORY with the real graphify.exe, though on\n"
        "  Windows it never shares a FILENAME (graphify installs from PyPI as\n"
        "  Scripts\\graphify.exe, not npm).\n"
        "  THE KNOWN GAP (GF-LAUNCHER, both twins): under `--python-launcher` there is\n"
        "  no `cage` command on PATH for the capability probe to find, so NEITHER twin\n"
        "  meters — correct passthrough, silently unmetered. `cage doctor`'s\n"
        "  launcher-gap check says so when it sees both switches at once. See\n"
        "  `cage query restricted-env` and docs/restricted-environments.md.",
        ("cage/paths.py", "cage/adoptcmd.py", "cage/pathshim.py", "cage/wiringscan.py",
         "cage/doctorcmd.py", "cage/data/shims/graphify", "cage/data/shims/graphify.cmd"),
        "n/a — describes a wiring mechanism, not a number.",
        kind="concept", plan_ref="§5"),
    Explanation(
        # NB: keywords avoid the bare "wiring"/"stale"/"dead" stems already owned by
        # `stale-wiring` — this entry is about the ITEMIZED VIEW, not the detection.
        "wiring-inventory", ("wiring-inventory", "inventory", "installed-artifact",
                             "partially-wired", "not-wired", "fully-wired"),
        "what `cage doctor --wiring` lists and how it decides fully/partially/not wired",
        "a browsable itemization of every artifact `cage setup` writes, grouped by\n"
        "  scope (project vs global/user) and agent (claude/copilot/kiro — always\n"
        "  `agents.SURFACES`, never a hand-written list). It renders wiringscan's\n"
        "  enumeration + liveness (see `stale-wiring`) — it does not fork them.\n"
        "  STATUS per row: current (a live verb) · dead (a wiring command names a\n"
        "  removed verb) · foreign (a non-cage artifact at a cage location — shown,\n"
        "  never judged, e.g. a git post-commit hook without the cage marker).\n"
        "  PER-AGENT VERDICT: needs healing (any dead command for that agent — takes\n"
        "  priority) > not wired (nothing present — purely informational, never a\n"
        "  warning) > partially wired (some but not all of the agent's REQUIRED\n"
        "  pieces present — names what's missing) > fully wired. Each agent's only\n"
        "  wired surface now is its MCP entry — all three committed and machine-\n"
        "  independent since kiro's went path-free (`portable-wiring`), so there is no\n"
        "  longer a gitignore exception to exclude from 'Required'.\n"
        "  Pre-removal hook/skill leftovers surface as separate leftover/dead rows,\n"
        "  never as part of an agent's expected set.\n"
        "  No per-artifact VERSION is shown — artifacts are stampless, so a\n"
        "  fabricated version would be worse than none; the version footer (running\n"
        "  cage, bundled [meta], project [meta]) is the honest answer instead.\n"
        "  Read-only and side-effect-free: nothing is ever executed or healed\n"
        "  (`cage setup` heals); `--json` carries the same status taxonomy.",
        ("cage/wiringscan.py", "cage/doctorcmd.py", "cage/agents.py"),
        "n/a — describes a diagnostic view, not a number.",
        kind="concept", plan_ref="§5"),
    Explanation(
        # NB: keywords avoid generic stems ("setup", "wiring") that would steal
        # queries from `overview`/`portable-wiring` — same discipline as above.
        "restricted-env", ("restricted-env", "restricted", "locked-down", "lockdown",
                           "applocker", "wdac", "zipapp", "pyz", "python-launcher",
                           "no-exe", "blocked", "enterprise", "finance", "mirror",
                           "airgap", "offline"),
        "running cage where exes are blocked or pip is unavailable",
        "three tiers. 1) python-launcher wiring\n"
        "  mode: `cage setup --python-launcher` persists [wiring] python_launcher =\n"
        "  true and (re)writes the shim + user-level wiring to resolve cage through\n"
        "  the interpreter only (python3 -m cage / py -3 -m cage) — nothing\n"
        "  exe-shaped is probed or executed, for AppLocker/WDAC endpoints that block\n"
        "  unknown exes; committed files are unchanged (they reference the shim; the\n"
        "  shim IS the mode); same fail-open exit-0 contract; plain re-runs preserve\n"
        "  the mode; `cage doctor` names it. CAGE_RUN_PYTHON=1 is the no-rewire\n"
        "  runtime override on the standard shim. 2) cage.pyz: a CI-built stdlib\n"
        "  zipapp attached to every GitHub release beside SHA256SUMS — one file, no\n"
        "  pip, run `py cage.pyz import/export/report` through the approved\n"
        "  interpreter; `--version`/doctor label the run `(zipapp)`; derived views\n"
        "  are byte-identical to a wheel install over the same ledger. Shims never\n"
        "  embed a pyz path (machine-specific); the pyz story is pull-based capture,\n"
        "  run explicitly. 3) internal mirror: dependencies =\n"
        "  [] and OIDC trusted publishing are the review answers. Honest caveat:\n"
        "  WDAC can also constrain script hosts — check your policy; doctor cannot\n"
        "  detect a blocked interpreter.",
        ("cage/runshim.py", "cage/paths.py", "tools/buildpyz.py",
         ".github/workflows/publish.yml"),
        "n/a — describes distribution/wiring tiers, not a number.",
        kind="concept", plan_ref="§5"),
    Explanation(
        "graphify-capture", ("graphify", "usage-row", "usage", "report-read",
                             "repo-ceiling", "ceiling", "transcript-detection",
                             "invocation-less", "forward-model"),
        "how cage sees graphify use it can't miss, and models graphify's future savings",
        "Every existing route (PATH/native shim, hook) is invocation-gated, so it\n"
        "  misses the invocation-less saving: the agent READS graphify-out/GRAPH_REPORT.md\n"
        "  instead of scanning files. Four fixes: (GC1) a usage row per run in\n"
        "  state/graphify-usage.jsonl — {{op, args_hash, exit, ms, outcome}}, never priced,\n"
        "  never in a money view — so doctor can say 'graphify ran N×, R receipts'. (GC2)\n"
        "  at `cage import`, detect graphify in CLAUDE transcripts: a Bash\n"
        "  `graphify query|explain` (anchored on command position — `grep graphify`\n"
        "  never matches) reuses the shim's counterfactual on the in-transcript result\n"
        "  → modeled receipt; a Read of the report/wiki → a distinct, lower-confidence\n"
        "  report-read receipt (op=report-read, 0.3 — UNVALIDATED, a placeholder not yet\n"
        "  scored by `insights calibration`), footnoted apart, never conflated.\n"
        "  copilot/kiro are HONEST-LIMIT (GC0). (GC3, ADR 0005) deterministic ids\n"
        "  s_=sha1(session|op|args_hash|answer_hash) keep per-session attribution; the\n"
        "  shim+transcript converge via a content-key DEFERRAL, not id-collision, so one\n"
        "  query files exactly one receipt. (GC5) a forward model: a history band\n"
        "  (median+IQR, refuses < 5) and a deterministic day-one repo ceiling from\n"
        "  graph.json — BOUNDED to the largest community's corpus (a graph answer stands\n"
        "  in for one concern, not every file; the whole-corpus sum over-claims on a real\n"
        "  repo) — both modeled bands, composed into `insights verdict graphify`,\n"
        "  never a measured total.",
        ("cage/graphifytx.py", "cage/graphifymodel.py", "cage/repoceiling.py",
         "cage/usagelog.py", "cage/graphifymeter.py"),
        "usage rows carry NO method (diagnostic); receipts + forward model are modeled,\n"
        "  never measured — report-reads visibly weaker than query receipts.",
        kind="concept", plan_ref="archive/v0.36-graphify-capture.plan.md GC0–GC5 (pending: OPEN-WORK.md)"),
    Explanation(
        "otel-export", ("otel", "opentelemetry", "otel-export", "genai", "gen_ai",
                        "semconv", "semantic-convention", "langfuse", "helicone",
                        "otlp", "vendor", "pre-stable"),
        "`cage data export --otel`: calls as gen_ai.* attributes, savings cage-namespaced",
        "one-way REPORTING JSON, exactly like --csv (never an import source; --study\n"
        "  stays jsonl): calls → gen_ai.system / gen_ai.request.model /\n"
        "  gen_ai.usage.input_tokens / output_tokens, plus\n"
        "  gen_ai.client.operation.duration (seconds) when latency_ms is known —\n"
        "  omitted, never zero, when it isn't. Receipts/savings have NO GenAI\n"
        "  equivalent: cage-namespaced under cage.savings[].cage.* (cage.saved is\n"
        "  GROSS, cage.saved_usd prices via the same receiptprice ladder every other\n"
        "  view uses and is omitted — never $0 — on an UNPRICED refusal or a non-money\n"
        "  unit). No gen_ai.* name is ever invented. **The GenAI conventions are\n"
        "  PRE-STABLE** ({semconv}, {semconv_status}) — names can still change\n"
        "  upstream, so cage pins the targeted version in one constant and stamps it\n"
        "  in every document's cage.meta block; a spec bump is a deliberate,\n"
        "  changelog'd change, never silent drift.",
        ("cage/otelout.py", "cage/exportcmd.py", "cage/constants.py"),
        "cage.method survives on every savings row — a modeled/estimated figure can\n"
        "  never arrive at a vendor looking measured; calls are the ledger's own\n"
        "  ground truth.",
        kind="concept", plan_ref="archive/v0.39-otel-export.handoff.md"),
    Explanation(
        "tool-adoption", ("adoption", "adopt", "invoked", "invocation", "usage",
                          "breadcrumb", "never-invoked", "agent-unknown", "uptake",
                          "do-agents-use", "insights-adoption"),
        "`cage insights adoption`: which agents actually invoke the tools you wired",
        "TWO HALVES, never blended into one number, because they have different\n"
        "  precision:\n"
        "  A · invocations — straight off the usage breadcrumb (state/, diagnostic).\n"
        "    Exact, no join, and AGENT-BLIND: a usage row is\n"
        "    `ts · op · args_hash · exit · ms · outcome · route` and carries no agent\n"
        "    field at all. Outcomes are READ from the recorded `outcome`\n"
        "    ({outcomes})\n"
        "    — 'ran and cage filed nothing' is a written verdict, never re-derived\n"
        "    from the receipts.\n"
        "  B · per-agent — a savings row joined to a call's agent, by linked `call`\n"
        "    id first, else by a `session` that exactly one agent's calls carry. A\n"
        "    shim/native savings row stamps an EMPTY session ON PURPOSE (the\n"
        "    interceptor is a subprocess; it genuinely cannot know which agent spawned\n"
        "    it), so those rows are agent-unknown BY CONSTRUCTION — never an 'other'\n"
        "    bucket, never attributed by timestamp proximity. When nothing is\n"
        "    attributable the half still renders, as an explicit refusal: suppressing\n"
        "    it would make 'cage cannot attribute these' read like 'cage has no\n"
        "    per-agent answer'.\n"
        "  'Never invoked' is phrased NO EVIDENCE OF INVOCATION — a run cage never saw\n"
        "  looks identical to one that never happened.\n"
        "  NO CURRENCY ANYWHERE: usage rows stay diagnostic-only (never priced, never\n"
        "  read by a money view, pinned byte-identical); this view only counts them.\n"
        "  Surface is deliberately not a dimension — claude's CLI and VS Code share one\n"
        "  store, so splitting by it would invent a fact.",
        ("cage/adoption.py", "cage/usagelog.py", "cage/graphifymeter.py"),
        "no method tag: these are COUNTS of recorded rows, not an estimate — the only\n"
        "  claims are 'this many rows exist' and 'this many join to an agent'.",
        kind="concept", plan_ref="archive/v0.40-insights-adoption.proposal.md"),
    Explanation(
        "chats-view", ("chats", "chat", "per-chat", "conversation", "conversations",
                       "session-title", "titled", "titles", "detail-view",
                       "insights-chats"),
        "`cage insights chats`: one row per chat, titled where the store has a title",
        "GROUPED off the ledger alone, by (agent, surface, session) — the same bucket\n"
        "  key the import manifest uses. Sums tokens_in/cached_in/cache_write_in/\n"
        "  tokens_out/premium per bucket; reprices per call (UNPRICED counted, never\n"
        "  a silent $0). Top {chats_default_rows} rows by tokens_in desc, --all lifts it\n"
        "  (the cut is footnoted — no silent caps).\n"
        "  THE ONE CARVE-OUT: a title is joined from imports.jsonl for a DISPLAY LABEL\n"
        "  ONLY — manifest.py's own contract stays 'never read by a money view' with\n"
        "  this one scoped exception. No name in the manifest ⇒ the session id, never a\n"
        "  fabricated title. Pinned: deleting imports.jsonl changes ZERO numeric cells.\n"
        "  Two honesty limits, stated not fixed: a renamed chat keeps its stale title\n"
        "  until it produces a new row (the manifest only appends on capture), and a\n"
        "  pre-manifest (legacy) session has no name row at all.\n"
        "  KIRO-IDE stamps a constant session id, so every run already collapses into\n"
        "  ONE row by construction, labelled 'kiro (no session identity)' rather than\n"
        "  the literal id; kiro-CLI conversations are recorded as CREDITS, a different\n"
        "  row shape with no tokens_in/out, so they carry no calls and do not appear\n"
        "  here at all (out of scope for v1).\n"
        "  LOCAL-ONLY BY CONSTRUCTION: no --team, no manifest data ever leaves this\n"
        "  machine.",
        ("cage/chats.py", "cage/manifest.py", "cage/importcmd.py"),
        "cost cells follow call_usd_match's tag exactly like `report` — measured when a\n"
        "  real price row matched, self when a provider's own est_cost_usd stood in,\n"
        "  none (UNPRICED) otherwise. No method tag on the grouping/ranking itself —\n"
        "  those are counts and a sort, not a claim about how a number was priced.",
        kind="concept", plan_ref="archive/v0.42-chats-view.proposal.md"),
    Explanation(
        "agent-authorship", ("authorship", "agent-vs-human", "human", "who wrote",
                             "commits", "commit", "line-match", "suggested", "kept",
                             "residual", "unattributed", "provenance", "hours",
                             "attested", "split"),
        "`cage insights commits` / `commit <sha>`: who wrote a commit, and how cage knows",
        "NEVER OBSERVE THE HUMAN — observe the agent precisely; the human is what is\n"
        "  left. A Claude transcript records the exact text an Edit/Write/MultiEdit/\n"
        "  NotebookEdit block PROPOSED. At import that text is compared, TRANSIENTLY IN\n"
        "  MEMORY, against the added lines of the commit whose window contains the edit.\n"
        "  Only counts are written: no line body, and no line HASH (a hash is a\n"
        "  membership oracle over your source).\n"
        "  WINDOWS, NEVER HEAD: commit i owns (ts_{{i-1}}, ts_i], upper bound inclusive.\n"
        "  Work after the newest commit is left UNRECORDED this sweep and picked up\n"
        "  exactly once by the next import — guessing a commit that does not exist yet\n"
        "  would be wrong forever.\n"
        "  ONE UTC NORMAL FORM: git renders a commit date in the COMMITTER'S OWN offset\n"
        "  (…+05:30), while a call stamps …SSZ and a transcript turn …SS.mmmZ — so every\n"
        "  bound and probe is normalized to YYYY-MM-DDTHH:MM:SSZ (sub-seconds TRUNCATED,\n"
        "  never rounded) before any comparison. Seconds, not milliseconds: `%cI` has no\n"
        "  sub-second, so finer precision would push an edit made inside the commit's own\n"
        "  second out of it and break the inclusive bound above. Bounds normalize at\n"
        "  construction, so a window holding a raw git string cannot be built.\n"
        "  FOUR LINE BUCKETS, none of them redistributed:\n"
        "    agent   matched an agent's recorded proposal            (direct evidence)\n"
        "    human~  added in a file that session DID propose,\n"
        "            matching nothing — a real human tweak            (ESTIMATED residual)\n"
        "    unattr  added in a file NO session proposed: a person, a vendored tree, or\n"
        "            generated output — cage has no evidence either way and says so\n"
        "    unkn    below the {min_match_chars}-char content gate, or a binary file    (structural)\n"
        "  The 4th bucket exists because a single `human` bucket printed 76.6% on cage's\n"
        "  own repo, 89% of it ONE commit of generated JSON. A residual presented as a\n"
        "  finding is the v1 mistake (docs/regression/2026-08-02-p1-authorship-dogfood.md).\n"
        "  SUGGESTED vs KEPT: suggested = kept + kept_modified + dropped, exactly. Counts,\n"
        "  never an acceptance percentage — the enum is the resolution the source supports.\n"
        "  HOURS, three visibly distinct tiers: * attested (`cage task time`) ALWAYS wins ·\n"
        "  ~ estimated = wall-clock − agent turn-span, floored at 0, refused past\n"
        "  [authorship] max_est_gap ({max_est_gap}) and refused outright when no agent span\n"
        "  joined (that would just be the commit gap) · — otherwise, reason named.\n"
        "  NO USD, NO RATE, NO VALUATION anywhere on these surfaces — the v1 veto, kept.\n"
        "  COVERAGE IS PER-AGENT AND STATED: claude only. Copilot's stores record usage\n"
        "  and prompts but not the text of an edit; kiro's log records token counts with\n"
        "  no tool-input payload. They render `—` with the reason, never 0%.\n"
        "  CONSENT: [authorship] capture / CAGE_AUTHORSHIP is its own switch — this is the\n"
        "  one path that reads your diffs, and that is a different permission from\n"
        "  metering spend.",
        ("cage/linematch.py", "cage/authorcapture.py", "cage/commitjoin.py",
         "cage/commitview.py", "cage.toml [authorship]"),
        "agent lines are read from the recorded provenance row (never re-matched at\n"
        "  render time — a second matcher could disagree with the one that wrote it);\n"
        "  human~ is ESTIMATED by construction — 'not the agent' is the observation, so\n"
        "  the label says so, and an unmarked `human` is reachable ONLY by attestation.\n"
        "  Tokens are measured; placing a call on a commit is modeled (task-id join\n"
        "  first, commit-window fallback). unknown is shown, never redistributed.",
        kind="concept", plan_ref="adr/0008-line-match-authorship-counts-persisted-content-transient.md"),
    Explanation(
        "agent-layers", ("layers", "ladder", "l0", "l1", "l2", "l3", "opt-in",
                         "hooks-optional", "attestation", "attest", "steering",
                         "hookless", "floor", "auto-close"),
        "the four-layer agent surface: what each layer adds, and what happens without it",
        "FOUR LAYERS, each optional above the first, each strictly additive:\n"
        "  L0 HOOKLESS — the floor, and NOT optional: pull capture (`cage import`,\n"
        "    capture-on-read), the PATH interceptor, every CLI view. This is cage.\n"
        "  L1 HOOKS + STEERING (`cage setup --hooks`) — NOT for capture, which already\n"
        "    works without it. It exists for the two things pull capture structurally\n"
        "    cannot do: (a) AGENT IDENTITY, because a hook runs inside the agent and\n"
        "    can state which one fired it as a fact instead of inferring it, and\n"
        "    (b) AUTO TASK-CLOSE on the session boundary, which unblocks compare /\n"
        "    estimate / calibration — all starved because nobody closes tasks. It also\n"
        "    gives `budget.check` its first real caller: with [budgets] on_exceed =\n"
        "    'block', a hook can stop a paid call BEFORE it happens.\n"
        "  L2 MCP — the agent pulls cage's views mid-session, refusals included.\n"
        "  L3 SKILLS — procedural knowledge: when to ask, and how to relay an answer\n"
        "    without smoothing it.\n"
        "  THE BINDING RULE: L0 must work perfectly, alone, forever. Adding or removing\n"
        "  any layer above it changes NO number — asserted in tests/test_floor.py, in\n"
        "  both directions, per agent. If a layer needed a number to move, the layer\n"
        "  would be wrong, not the number.\n"
        "  AUTO-CLOSE NEVER CLAIMS SUCCESS: a session ending is not a job well done, so\n"
        "  the hook writes outcome='auto' — closed for cost comparison, INVISIBLE to\n"
        "  `cage task quality`, which counts only ok/redo. Stamping 'ok' would inflate\n"
        "  the success rate of every session that merely finished.\n"
        "  HOOKS ARE CLI-ONLY — they do not fire under a VS Code extension, so every\n"
        "  L1-derived fact is a CLI-session fact and says so wherever it is shown.\n"
        "  Per-agent capability is one table (`agents.HOOK_EVENTS`) and every gap is\n"
        "  NAMED in output (`agents.HOOK_GAPS`): kiro has no session-start trigger, so\n"
        "  its single agentStop hook attests the agent but DECLINES to auto-close a\n"
        "  task — closing the most recent one would be attribution by proximity.",
        ("cage/hookcmd.py", "cage/attest.py", "cage/steering.py", "cage/agents.py"),
        "n/a — describes the layer contract, not a number. That is the point: no layer\n"
        "  above L0 may move one.",
        kind="concept", plan_ref="archive/v0.41-agent-surface-layers.proposal.md"),
)
