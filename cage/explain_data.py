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
        "saved", ("saved", "savings", "reduction", "shrink", "avoided"),
        "the tokens a tool kept out of the prompt (GROSS)",
        "saved = raw_alternative − actual   (in the receipt's own unit — usually tokens)\n"
        "  GROSS: the tokens spent USING the tool — the invoking turn, the context a\n"
        "  hook injected — are NOT subtracted. `cage query gross-vs-net` explains.",
        ("cage/savings.py", "cage/graphifychat.py", "cage/schema.py"),
        "inherits the receipt's method — measured only if the tool truly measured it."),
    Explanation(
        "gross-vs-net", ("gross", "net", "cost-of-use", "net-saved", "attributable",
                         "over-claim", "excluded", "using", "adjacent", "window"),
        "why `saved` is GROSS, and why cage no longer reports a net",
        "gross = raw_alternative − actual     (the avoided read — excludes USING the tool)\n"
        "  The tokens a tool costs to use — the turn that invoked it, the context a hook\n"
        "  injected — are NOT subtracted. So a large `saved` and a session that consumed\n"
        "  more tokens overall are BOTH true, and cage prints the caveat every time.\n"
        "\n"
        "  There is no net figure any more (USAGE-ONLY, ADR 0011). The task-level net\n"
        "  priced every in-window call to a common unit, which was a dollar computation;\n"
        "  per-query netting was never possible at all, because a shim receipt carries a\n"
        "  task but no call. Cage reports gross only, and says so, rather than reporting\n"
        "  a net it cannot substantiate.",
        ("cage/savings.py", "cage/graphifychat.py", "cage/graphifytx.py"),
        "gross inherits the receipt's own method — modeled for a counterfactual, and\n"
        "  never upgraded to measured by being printed next to recorded tokens."),
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
        ("cage/constants.py", "cage/schema.py", "cage/savings.py"),
        "method is sacred — a projection never reads as measured (cage's core honesty rule)."),
    Explanation(
        "capture-troubleshooting",
        ("capture", "captured", "capturing", "nothing", "missing", "empty",
         "troubleshoot", "troubleshooting", "why-no-rows", "probe",
         "windows", "location", "log-location"),
        "why is nothing being captured — the three-step diagnosis",
        "0. cage tells you first: when an agent's home exists but its log matched 0\n"
        "     files and it has never captured a row, `cage doctor` prints a\n"
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
        ("cage/pathprobe.py", "cage/doctorcmd.py", "cage/doctorbundle.py", "cage/capturelog.py"),
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
        "  read at compute time (budgets, pipeline order, capture\n"
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
        ("cage/importcmd.py", "cage/paths.py", "cage/chats.py"),
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
        "  new writes target dated files (ADR-LAWS).",
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
        ("cage/metering.py", "cage/transcript.py", "cage/importcmd.py", "cage/mcpserver.py"),
        "n/a — describes a mechanism, not a number.",
        kind="concept", plan_ref="§5"),
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
        "  the outside (e.g. `cage interceptor graphify -- graphify query …`) without that tool\n"
        "  knowing cage exists — the receipt is filed by cage's wrapper, not the tool.\n"
        "  Units: a receipt is denominated in its OWN unit (tokens, ms, gco2) and\n"
        "  cage converts nothing between them. Since USAGE-ONLY (ADR 0011) there is\n"
        "  no currency to convert INTO either.",
        ("cage/schema.py", "cage/graphifymeter.py", "cage/savings.py"),
        "n/a — describes two receipt-filing strategies, not a number.",
        kind="concept", plan_ref="§4.5"),
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
        ("cage/paths.py", "cage/importcmd.py", "cage/transcript.py", "cage/chats.py"),
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
        "  footnote on `cage insights chats` — never silently folded into a total, never\n"
        "  priced. Rows are append-only and are never rewritten.",
        ("cage/commitview.py", "cage/origin.py", "cage/chats.py"),
        "n/a — describes the measurement axis, not a number.",
        kind="concept", plan_ref="§4.6"),
    Explanation(
        "determinism", ("reproducible", "byte-identical", "same-ledger", "offline"),
        "why the same ledger always renders the same tables",
        "derived views ({n_subcommands} subcommands) contain no clock read, no RNG,\n"
        "  and no model call — the only inputs are the ledger rows and the policy file.\n"
        "  Same ledger + same policy ⇒ byte-identical output; ids carry the only entropy,\n"
        "  and only at write time.",
        ("cage/ledger.py", "cage/chats.py"),
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
        "  routing + behaviour in cage.toml (pipeline order, budgets, capture) ·\n"
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
        "  team: REMOVED in v0.50 (SURFACE-CUT). The ledger-sync verb pushed rows into\n"
        "  refs/notes/cage-ledger, and the --team flags that read them went with the\n"
        "  rollup views — a write path with no reader. Provenance notes are unaffected.\n"
        "  rolled up by scope, never per-person. Size warning: one stderr line past\n"
        "  ~{warn_mb} MB (policy [ledger] warn_mb overrides) — warn-only, never blocks.",
        ("cage/ledger.py", "cage/mergeutil.py", "cage/constants.py"),
        "n/a — describes the on-disk layout + aggregation, not a number.",
        kind="concept", plan_ref="§3.6"),
    Explanation(
        "policy-versioning", ("policy-versioning", "meta", "policy-version",
                              "bundle-newer", "sync-recommendation"),
        "how cage knows your project config is behind the bundle ([meta] + policy sync)",
        "the bundled defaults carry [meta] policy_version {policy_version_bundled};\n"
        "  `cage setup` stamps the project cage.toml with the bundle it derived from\n"
        "  (this project: {policy_version_project}). `cage doctor` compares the two — a\n"
        "  newer bundle prints one recommendation line to run `cage policy sync`, never\n"
        "  auto-applied.\n"
        "\n"
        "  The parallel prices_version counter is GONE (USAGE-ONLY, ADR 0011) along with\n"
        "  the price table it tracked. `policy_version` is deliberately NOT the release\n"
        "  version: it is a content counter, and bumping it per release would tell every\n"
        "  project its defaults were stale when nothing changed.",
        ("cage/policysync.py", "cage/data/cage.toml [meta]", "cage/doctorcmd.py"),
        "measured — a comparison of two recorded stamps, no inference."),
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
        "  nothing ever\n"
        "  auto-applies either sync.",
        ("cage/policysync.py", "cage/tomledit.py", "cage/data/cage.toml [meta]"),
        "n/a — describes the upgrade verb; it never changes a derived number.",
        kind="concept", plan_ref="§3.10"),
    Explanation(
        "copilot-metrics", ("copilot-metrics", "chats-ledger", "modeltotals",
                            "session-credits", "nano-aiu", "sidecar", "debuglog",
                            "otel", "agent-traces", "five-stores", "per-chat-metrics"),
        "the .cage/ledger/copilot/ kind: per-chat Copilot usage, verbatim, from five stores",
        "A capture-only sibling to `calls` — never widens that schema, never priced,\n"
        "  never read by any derived view today. One row per (source, session, surface,\n"
        "  request, call) key, from whichever of five on-disk stores the machine has:\n"
        "    chat      VS Code chatSessions — per-request tokens + copilotCredits +\n"
        "              sessionCopilotCredits + modelTotals (durable, ungated)\n"
        "    cli       Copilot CLI session-state — per-shutdown CUMULATIVE totals,\n"
        "              never delta'd (dodges the calls-parser delta-loss bug by\n"
        "              construction)\n"
        "    sidecar   agentHostUsage — per-model-call, real routed model, gated\n"
        "    debuglog  copilot-chat debug-logs — per-request, no cached tokens, gated\n"
        "    otel      agent-traces.db (SQLite, read-only) — per-model-call, cached\n"
        "              tokens, gated\n"
        "  `ledger.copilot_metrics()` collapses last-write-wins per key, winner = max\n"
        "  (tokens_in+tokens_out, credits or -1, id) — a grown chatSessions request or a\n"
        "  resumed CLI session appends a FRESH row (id folds the row's own values), the\n"
        "  reader resolves the latest state. session_credits / a CLI row's cumulative\n"
        "  totals are NEVER summed across a session's rows.\n"
        "  Counts-never-content: debuglog/otel are whitelist reads (the SAME lines/tables\n"
        "  carry prompt bodies right next to the numbers) — only the named fields are\n"
        "  ever read. Absence ≠ zero for credits/session_credits/nano_aiu (None-sentinel,\n"
        "  the `make_call.credits` law, generalized).",
        ("cage/schema.py", "cage/ledger.py", "cage/transcript.py", "cage/importcmd.py"),
        "n/a — capture-only, no computed number; every field is recorded verbatim.",
        kind="concept", plan_ref="§3.11"),
    Explanation(
        "kiro-metrics", ("kiro-metrics", "chats-ledger", "devdata", "cli-conv",
                        "cli-turn", "upgrade-watch", "tokens-generated", "kiro-cli",
                        "three-grains", "per-chat-metrics"),
        "the .cage/ledger/kiro/ kind: per-chat Kiro usage, store-verbatim, at three grains",
        "A capture-only sibling to `calls`/`credits` — never widens either, never\n"
        "  priced, never read by any derived view today. One row per\n"
        "  (source, session, turn, row_ref) key, from whichever Kiro store the machine\n"
        "  has:\n"
        "    ide       IDE devdata.sqlite `tokens_generated` — per LLM call, the SAME\n"
        "              counter `calls` already reads from the jsonl twin, plus a\n"
        "              `timestamp` and a cursorable `id` the jsonl never carried\n"
        "    cli-conv  CLI SQLite store, per conversation — credits (usage_info sum),\n"
        "              context%, turn count; cumulative-verbatim, like `credits` rows\n"
        "    cli-turn  same store, per history[] turn — populated timing/size/tool-use\n"
        "              fields, PLUS the token slots that are NULL on every real store\n"
        "              probed so far (the upgrade-watch: filled only when non-NULL,\n"
        "              never estimated — chars÷4/cumulative/chunk-count are BANNED as\n"
        "              token facts; `chunks` stays a chunk count, never `tokens_out`)\n"
        "  Routing inherits ADR 0006, never re-decided: `ide` rows ride the routed kiro\n"
        "  sink (`_kiro_leg`, machine ledger); `cli-conv`/`cli-turn` rows ride the same\n"
        "  workspace scoping the `credits` leg already resolves.\n"
        "  `ledger.kiro_metrics()` collapses last-write-wins per key, winner = max\n"
        "  (turns, tokens_in+tokens_out, id) — a grown CLI conversation appends a FRESH\n"
        "  row (id folds the row's own values), the reader resolves the latest state.\n"
        "  A conversation's own growth rows are NEVER summed.\n"
        "  Counts-never-content: the CLI parser reads only `request_metadata`/\n"
        "  `user_turn_metadata`/`model_info` keys, never `history[].user`/`.assistant`/\n"
        "  `content` — the same whitelist `_kiro_cli_credit_row` already honors. The IDE\n"
        "  parser SELECTs four explicit columns only, never `SELECT *`. Absence ≠ zero\n"
        "  for `credits` (None-sentinel, the `make_call.credits` law, generalized).\n"
        "  Cache tokens and per-chat IDE credits are absent from every kiro row here\n"
        "  because no on-disk Kiro store persists them at all — only the wire protocol\n"
        "  does (proxy-only, out of scope; work/research/2026-08-13-kiro-per-chat-usage-\n"
        "  fetch-spec.md).",
        ("cage/schema.py", "cage/ledger.py", "cage/transcript.py", "cage/importcmd.py"),
        "n/a — capture-only, no computed number; every field is recorded verbatim.",
        kind="concept", plan_ref="§3.12"),
    Explanation(
        "claude-metrics", ("claude-metrics", "chats-ledger", "dedup-law",
                          "session-fileset", "requestid", "message-id", "cache-ttl",
                          "ephemeral", "thinking-tokens", "server-tool-use",
                          "sidechain", "subagent", "per-chat-metrics"),
        "the .cage/ledger/claude/ kind: per-chat Claude usage, correctly folded",
        "A capture-only sibling to `calls` — never widens that schema, never priced,\n"
        "  never read by any derived view today. One row per chat (`session`), folded\n"
        "  from the ONE transcript store both the CLI and VS Code extension share.\n"
        "  THE DEDUP LAW (this kind's whole reason to exist): one API response writes\n"
        "  1-5 assistant rows — same `requestId`+`message.id`, distinct `uuid`, a full\n"
        "  copy of `usage` each — folded last-per-key at capture, so `raw_rows` (seen)\n"
        "  vs `requests` (folded) IS the inflation evidence, captured correctly. Chat\n"
        "  key = the row's own `sessionId`, so a subagent transcript\n"
        "  (`<sessionId>/subagents/agent-*.jsonl`) joins its PARENT chat and splits into\n"
        "  `sidechain_tokens_in/out` rather than landing in a phantom chat.\n"
        "  `importcmd._claude_session_filesets` regroups a sweep's changed files into\n"
        "  WHOLE session filesets first — a subagent-only change still re-reads the\n"
        "  main file too, so the emitted row is never a partial total.\n"
        "  `ledger.claude_metrics()` collapses last-write-wins per `session`, winner =\n"
        "  max (requests, tokens_in+tokens_out, id) — a grown chat appends a FRESH row\n"
        "  (id folds the row's own values), the reader resolves the latest state. A\n"
        "  chat's own growth rows are NEVER summed.\n"
        "  Dodged, then OUTLIVED, two calls-path defects (CLAUDE-DEDUP,\n"
        "  CLAUDE-SUBAGENT-KEY). v0.51 retired the transcript->calls leg entirely, so\n"
        "  neither defect can reach a built-in claude number any more. `parse_calls` is\n"
        "  KEPT and untouched — it is the `[sources.<name>] format` custom-source\n"
        "  contract, and a source declaring `format = \"claude\"` still inherits both\n"
        "  (ADR-CONSUMERS says so). Fixing them on the way out was forbidden: the\n"
        "  measurement has to outlive the code.\n"
        "  No credits field at all — no credit unit exists for\n"
        "  Claude Code anywhere on disk. Counts-never-content: only the assistant-row\n"
        "  envelope + `message.usage` are ever read.",
        ("cage/schema.py", "cage/ledger.py", "cage/transcript.py", "cage/importcmd.py"),
        "n/a — capture-only, no computed number; every field is recorded verbatim.",
        kind="concept", plan_ref="§3.13"),
    Explanation(
        "cleanup", ("cleanup", "state-dir", "prune", "stale", "retention", "warn",
                    "debug-log-growth", "cursors", "pending-buffers"),
        "what state cleanup may touch — and what it never may",
        "a CLOSED allowlist over .cage/state/ only: aged debug.log / capture.log /\n"
        "  hooks-seen.jsonl rows, stale pending-* provenance buffers, cursors whose\n"
        "  source log is gone (safe: the next import re-reads and id-dedupe absorbs\n"
        "  it), *.tmp. (hooks-seen.jsonl is a legacy file cleaned on real machines —\n"
        "  cage no longer writes hooks.) Never — by construction, not convention:\n"
        "  ledger/ (tool savings included — a per-tool cleanup class must never be\n"
        "  added, savings are unrecoverable), cage.toml, limits.json, and the two\n"
        "  files the removed fleet study left behind (machine.json, study.jsonl —\n"
        "  nothing writes them since v0.51, and nothing may delete them either).\n"
        "  Window: [cleanup]\n"
        "  days = {cleanup_days}. Deletion only ever happens via an\n"
        "  explicit prune. NOTE: the manual verb was deleted in v0.50, so nothing\n"
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
        "display", ("display", "usd", "--usd", "dollars", "tokens-default",
                    "token-view", "dollar-view", "signal-gating", "gating",
                    "all-columns", "hide", "columns", "why-no-cost-column",
                    "where-are-dollars"),
        "tokens by default, dollars opt-in, and signal-gated columns",
        "tokens are the measurement; dollars are an interpretation you ask for\n"
        "  the `cage insights` views\n"
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
        ("cage/display.py", "cage/chats.py", "cage/commitview.py", "cage.toml [display]"),
        "n/a — a presentation rule; every dollar that does render keeps its method tag.",
        kind="concept", plan_ref="output-and-simplification.plan.md Phase 2"),
    Explanation(
        "csv-output", ("csv", "csv-output", "spreadsheet", "excel", "pivot",
                       "pivot-table", "flat-table", "reporting-format",
                       "report-csv", "one-way"),
        "the CSV reporting surface: which views, the column law, csv-vs-bundle",
        "`--csv` on insights chats · graphify · commits · commit, and on\n"
        "  authorship summary — stdout by default (pipe-friendly),\n"
        "  `--csv <path>` writes a file. Raw-row export was removed in v0.50; the\n"
        "  calls|receipts|tasks` (flat ledger rows for pivot tables; the ledger's\n"
        "  own PII surface — counts and ids, never content). MCP mirrors it: a\n"
        "  `format: csv` param on the report/attrib/roi tools.\n"
        "  Laws: one shared data structure per view feeds the text table AND the\n"
        "  CSV — same numbers by construction, never computed twice; method/match\n"
        "  tags are COLUMNS (a spreadsheet can tell measured from estimated), and\n"
        "  refusals/caveats/UNPRICED counts survive into the rows; stdlib `csv`,\n"
        "  RFC-4180 quoting, LF line endings pinned on every OS (deterministic:\n"
        "  same ledger + policy ⇒ byte-identical CSV). The column contracts live in\n"
        "  `csvout.py` itself (one render_csv beside each render_*). CSV is one-way\n"
        "  REPORTING and never an import source. It was once the contrast to the\n"
        "  re-importable fleet bundle; that bundle went with the whole fleet study in\n"
        "  v0.51, so CSV is now simply the only export shape cage has.",
        ("cage/csvout.py", "cage/chats.py", "cage/commitview.py", "cage/viewexport.py"),
        "n/a — describes an output format; every row still carries its own method tag.",
        kind="concept", plan_ref="§3.9"),
    Explanation(
        "view-export", ("export", "view-export", "artifact", "output-dir", "stamp",
                        "generated-at", "timestamp", "as-of", "run-stamp",
                        "save-report", "write-report"),
        "--export: every report/insight as a dated artifact, and where a clock may live",
        "`--export` on every `cage insights` view writes the\n"
        "  rendered view to disk. Bare ⇒ <ledger>/.cage/output/<view>-<stamp>/ holding\n"
        "  EVERY format that view has (text · csv where it owns a render_csv · json).\n"
        "  A path with a known suffix (.txt/.md/.csv/.json) ⇒ exactly that file in\n"
        "  exactly that format; any other path ⇒ a per-run folder under it, so two\n"
        "  runs of one view can never clobber each other. Asking for a format a view\n"
        "  cannot produce is a refusal, never an empty file — an empty CSV reads as\n"
        "  'no rows'.\n"
        "  The determinism split, and it is the whole design: every ARTIFACT carries a\n"
        "  generated-at metadata block with no flag to suppress it (a file outlives its\n"
        "  terminal — a number with no as-of is unreadable), while STDOUT stays\n"
        "  clock-free unless you pass `--stamp`. So a view prints byte-identically\n"
        "  with and without `--export`, and the golden/floor suites keep pinning a\n"
        "  surface no clock can perturb. The stamp is metadata about the run, NEVER an\n"
        "  input to a cell: delete every stamp and no derived figure moves.\n"
        "  One block, three renderings — `# cage: k=v` lines for text and csv, a `cage`\n"
        "  object for json — never re-worded per format. It names the view, the stamp,\n"
        "  the cage version, the ledger read, and the DATA filters (--since/--by/--agent\n"
        "  …); presentation switches (--usd/--all) stay out, because they change how a\n"
        "  number looks and not what it means. CAGE_RUN_STAMP pins the clock for a\n"
        "  byte-reproducible artifact.\n"
        "  `--csv`/`--json` are unchanged on stdout AND to a path: a `--csv PATH` is a\n"
        "  stream redirected to a file, `--export` is an artifact, and only the artifact\n"
        "  grows the block. `.cage/output/` is deliberately NOT `.cage/out/` (that one\n"
        "  was the deleted local server's docroot — kept separate so a future one is safe), and no\n"
        "  cleanup class prunes it — cage never deletes an artifact it wrote.",
        ("cage/viewexport.py", "cage/runstamp.py", "cage/cliutil.py", "cage/cli.py"),
        "n/a — metadata about a run; it never enters a cell, so no method tag changes.",
        kind="concept", plan_ref="work/compare/view-export-and-run-stamp.compare.md"),
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
        "one behaviour contract, two implementations (docs/adr/0007_graphify.md): the\n"
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
        "  marker set (`cage interceptor graphify`, the SURFACE-CUT-era `cage data\n"
        "  graphify`, its pre-rename bare form with no group word,\n"
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
        "  `cage query restricted-env` and work/restricted-environments.md.",
        ("cage/paths.py", "cage/adoptcmd.py", "cage/pathshim.py", "cage/wiringscan.py",
         "cage/doctorcmd.py", "cage/data/shims/graphify", "cage/data/shims/graphify.cmd"),
        "n/a — describes a wiring mechanism, not a number.",
        kind="concept", plan_ref="§5"),
    Explanation(
        "graphify-coverage", ("graphify-coverage", "coverage", "which-agents", "surfaces",
                              "rescan-graphify", "backfill", "kiro-graphify",
                              "vscode-graphify", "graphify-gap", "truncated"),
        "which agent surfaces can file a graphify savings receipt, and why the rest can't",
        "a graphify saving is filed from whatever store an agent actually writes, so\n"
        "  coverage is a property of THAT STORE, not of cage. Per surface:\n"
        "{coverage}\n"
        "  WHY THIS IS PRINTED AT ALL: a zero is ambiguous, and the ambiguity is\n"
        "  expensive. An agent with no graphify savings might never have run graphify —\n"
        "  or cage might have had no route for its store. Through v0.46 the second was\n"
        "  true for copilot VS Code (skipped on an assumption that its chatSessions log\n"
        "  carried no tool result — measured FALSE on 2026-08-07) and for kiro (no route\n"
        "  existed at all), and nothing said so out loud.\n"
        "  A `CANNOT file` row is a MEASURED structural limit of somebody else's store,\n"
        "  never a to-do and never a guess. It is not a fault in your installation, and\n"
        "  it is the reason that surface is honestly absent rather than silently zero.\n"
        "  TRUNCATION REFUSES, IT DOES NOT ESTIMATE: kiro caps a tool's stdout at ~2000\n"
        "  tokens and appends its own marker. A truncated answer under-counts `actual`,\n"
        "  which would INFLATE the modeled saving — so a truncated run files nothing.\n"
        "  Expect kiro query receipts to be sparse for that reason; its fs_read\n"
        "  report-reads need no result body and are unaffected.\n"
        "  BACKFILL: the import cursor skips an unchanged log, which is right for calls\n"
        "  and wrong for savings — a route that ships after a session was ingested can\n"
        "  never see it again. `cage import --rescan-graphify` re-runs detection over\n"
        "  every matched log, ignoring the cursor. Detection only (no call/credit\n"
        "  re-ingest), idempotent by receipt id.\n"
        "  THE SAME BLINDNESS BIT THE METRICS LEDGERS (METRICS-CURSOR-BLIND, 2026-08-14):\n"
        "  the per-agent metric kinds under ledger/ (claude, copilot, kiro) ride the same\n"
        "  cursor-filtered file list, so every store ingested before those routes shipped\n"
        "  was skipped forever — measured at\n"
        "  102 copilot and 56 kiro rows on disk with zero captured. `cage import\n"
        "  --rescan-metrics` is that backfill: metrics only, idempotent by row id, and it\n"
        "  advances NO cursor, so backfilling one kind can never blind another.",
        ("cage/graphifytx.py", "cage/importcmd.py", "cage/transcript.py",
         "cage/doctorcmd.py", "work/archive/adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md",
         "work/research/2026-08-07-graphify-store-evidence.md"),
        "n/a — describes which routes exist, not a number.",
        kind="concept", plan_ref="§4.5"),
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
        kind="concept", plan_ref="archive/v0.36-graphify-capture.plan.md GC0–GC5"),
    Explanation(
        "chats-view", ("chats", "chat", "per-chat", "conversation", "conversations",
                       "session-title", "titled", "titles", "detail-view",
                       "insights-chats"),
        "`cage insights chats`: one row per chat, titled where the store has a title",
        "GROUPED off the ledger alone, by (agent, surface, session) — the same bucket\n"
        "  key the import manifest uses. Sums tokens_in/cached_in/cache_write_in/\n"
        "  tokens_out/credits per bucket; reprices per call (UNPRICED counted, never\n"
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
        "  the literal id.\n"
        "  KIRO-CLI conversations render too (CHATS-CREDITS): they are ledger.credits\n"
        "  rows, no tokens_in/out and no call at all, read alongside calls and kept in\n"
        "  their own bucket (never blended with a call bucket). calls and all four\n"
        "  token cells render `—` (text) / empty (CSV); credits is filled; cost prices\n"
        "  only through the configured [billing.kiro] usd_per_credit rate — unset stays\n"
        "  `—`, a configured 0.0 is a real $0.0000. Rank gains a second key so a\n"
        "  credits-only chat sorts below any token-bearing one, by credits among peers.\n"
        "  No manifest title exists for kiro-CLI yet, so its label is the session id.\n"
        "  THE agent% COLUMN: of the evidenced lines in files THIS CHAT TOUCHED, the\n"
        "  share that matched the agent's own proposals —\n"
        "    agent% = agent_lines / (agent_lines + residual_lines)\n"
        "  summed over the provenance rows sharing this chat's (agent, session). It is\n"
        "  NOT a share of the chat's work: lines in files no session proposed are\n"
        "  commit-scoped (`unattributed`, see `cage query agent-authorship`) and sit\n"
        "  outside this denominator entirely. That is scope, not redistribution.\n"
        "  READ, NEVER RE-DERIVED: no matcher and no git call runs at render — the\n"
        "  counts are whatever capture recorded, so this view can never disagree with\n"
        "  the commit view about the same lines.\n"
        "  IT REFUSES THREE WAYS, and `—` NEVER MEANS 0%:\n"
        "    coverage      copilot/kiro cannot be line-matched at all (their stores\n"
        "                  hold no edit text) — the reason is named, not a 0%\n"
        "    no evidence   no provenance row joined, or none carrying a matchable\n"
        "                  line: not committed yet, or committed in another repo /\n"
        "                  ledger root. 'Nothing landed' is not 'the agent wrote\n"
        "                  nothing'\n"
        "    pre-upgrade   rows predating the residual count are excluded from BOTH\n"
        "                  sums and counted in a footnote; they are frozen by the\n"
        "                  idempotency key and are never backfilled\n"
        "  A MEASURED 0% still renders 0% — which is exactly why the dash is never\n"
        "  spent on absence of evidence.\n"
        "  TWO STATED LIMITS. A provenance row carries no surface, so a session split\n"
        "  across surfaces attaches its counts to every one of those rows — footnoted,\n"
        "  because they are not independent evidence. And per chat there is no diff to\n"
        "  clamp against the way the commit view clamps per sha, so two chats that\n"
        "  proposed the same landed file EACH count its lines on both sides: for any\n"
        "  single sha the commit view stays the arbiter.\n"
        "  A SECOND CARVE-OUT, on the first one's terms: agent% reads provenance.jsonl\n"
        "  (counts only). Deleting that file moves ZERO pre-existing cell — only the\n"
        "  authorship cells fall to `—`. No USD, no rate, no minutes ever touches it;\n"
        "  agent% never combines with cost (the v0.36 law).\n"
        "  LOCAL-ONLY BY CONSTRUCTION: no --team, no manifest data ever leaves this\n"
        "  machine.",
        ("cage/chats.py", "cage/manifest.py", "cage/importcmd.py",
         "cage/authorcapture.py"),
        "cost cells follow call_usd_match's tag exactly like `report` — measured when a\n"
        "  real price row matched, self when a provider's own est_cost_usd stood in,\n"
        "  none (UNPRICED) otherwise. No method tag on the grouping/ranking itself —\n"
        "  those are counts and a sort, not a claim about how a number was priced.",
        kind="concept", plan_ref="archive/v0.42-chats-view.proposal.md"),
    Explanation(
        "graphify-chats", ("graphify-chats", "insights-graphify", "gfx-uses",
                           "without-graphify", "graphify-saved", "per-chat-graphify",
                           "saved-percent"),
        "`cage insights graphify`: one row per chat — recorded tokens, the modeled "
        "without-graphify counterfactual, and the GROSS saved share",
        "REUSES chats.summarize verbatim for the chat universe (title, agent, surface,\n"
        "  session, token sums) and joins ledger.savings rows (tool=graphify) onto it\n"
        "  by SESSION ALONE — a savings row carries no agent field at all.\n"
        "    tokens  = tokens_in + tokens_out          (the WITH-graphify world; None\n"
        "                                                for a kiro-CLI credit chat —\n"
        "                                                no token counts at all)\n"
        "    without = tokens + Σsaved                 (the MODELED counterfactual;\n"
        "                                                never clamped — a negative\n"
        "                                                saved can push it below tokens)\n"
        "    saved%  = 100 × Σsaved / without           (None when tokens is None or\n"
        "                                                without <= 0)\n"
        "  `tokens` is a real fact independent of graphify use — only the graphify-\n"
        "  derived cells (gfx uses / without gfx / saved / saved%) dash for a chat with\n"
        "  ZERO receipts, and only under --all-chats (the default view excludes such\n"
        "  chats entirely). A chat WITH receipts whose saved sums to a real 0 renders\n"
        "  0%, never a dash — no receipts at all is a different claim from a measured\n"
        "  zero, the absence-vs-recorded-zero law every view in this registry follows.\n"
        "  GROSS THROUGHOUT: per-chat NET is not computable (netsaved's attributable-\n"
        "  cost rule needs a call-level tool-use mark this ledger doesn't carry), so\n"
        "  this view is explicitly GROSS and says so on every render.\n"
        "  method/confidence per chat are the WORST CASE across its joined receipts —\n"
        "  least-trusted method wins, confidence is the min (the exact\n"
        "  attribution.receipts_by_tool aggregation, inlined).\n"
        "  TWO TALLIES NEVER REDISTRIBUTE into a chat row, footnoted apart:\n"
        "  unassignable (the native shim's honest-empty session=\"\", GC3) and\n"
        "  unmatched (a savings session joining no chat bucket at all).\n"
        "  Which agent surfaces can file a graphify receipt at all is a DIFFERENT\n"
        "  question — see `cage query graphify-coverage`.\n"
        "  Tokens-only — no --usd on this view (the v0.36 no-blend law). Top\n"
        "  {graphify_chats_default_rows} rows by saved desc, --all lifts it (footnoted,\n"
        "  never silent); CSV is always untruncated and never filters by receipts.",
        ("cage/graphifychat.py", "cage/chats.py", "cage/graphifytx.py",
         "cage/graphifytx.py"),
        "modeled throughout — every graphify receipt is modeled or estimated, never\n"
        "  measured; the per-chat aggregate carries the worst case among its receipts.",
        kind="concept", plan_ref="work/archive/v0.49-graphify-chats.handoff.md"),
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
        "  finding is the v1 mistake (work/regression/2026-08-02-p1-authorship-dogfood.md).\n"
        "  SUGGESTED vs KEPT: suggested = kept + kept_modified + dropped, exactly. Counts,\n"
        "  never an acceptance percentage — the enum is the resolution the source supports.\n"
        "  RESIDUAL_LINES is the sixth count and the ONE written at zero: matchable added\n"
        "  lines in the row's OWN landed files minus its agent_lines, floored at 0. It is\n"
        "  what `cage insights chats`' agent% column divides by, re-keyed per session\n"
        "  instead of per sha (of evidenced lines in files that chat touched — never a\n"
        "  share of the chat's work). Presence of the key is the version gate: absent\n"
        "  means the row predates the count and renders `—` forever (frozen rows are\n"
        "  never backfilled), while a recorded 0 is the real finding that everything\n"
        "  matchable matched the agent. Omitting it at 0 would make those two\n"
        "  indistinguishable — the same absent-vs-zero law as credits' None sentinel.\n"
        "  COST BOUND: every rendered row costs one `git show --numstat` SUBPROCESS, so\n"
        "  the list view READS only the newest {commits_default_rows} commits and footnotes\n"
        "  the rest as NOT READ (the total row covers what was read). --all reads every\n"
        "  commit; --csv/--json are never capped; `commit <sha>` is never capped at any\n"
        "  age. A default relative --since was rejected — it would put a wall clock in\n"
        "  the default path, so the same ledger would render differently next month.\n"
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
        kind="concept", plan_ref="../work/archive/adr/0008-line-match-authorship-counts-persisted-content-transient.md"),
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
        "  the outcome store, which holds only ok/redo. Stamping 'ok' would inflate\n"
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
