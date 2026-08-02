"""Code heuristics & invariants — the third audit layer (cage's numbers story).

Three layers, kept distinct so every number cage prints is reviewable in *one*
place per layer:

  · **Contract** — the closed enums ``UNITS`` / ``METHODS`` — live in
    ``schema.py`` (the substrate contract; do not move them here).
  · **Policy** — user-tunable economics (model prices,
    default minutes, budgets, pipeline order, confidence overrides) — live in
    ``policy.toml`` (the only place economic numbers live).
  · **Constants** (this file) — heuristics & invariants that are *not* meant as
    user config but that must still be reviewable: the token divisor, the
    per-million price scale, the matrix ceiling, the provenance ranking, and the
    confidence *fallback*.

``DEFAULT_CONFIDENCE`` is a fallback ladder only — a row carrying its own
``confidence`` always wins over it.

NB: the third-party shims (``fux/cage_receipt.py`` and the graphify ``bin`` shim)
keep their own local ``len(text) / 4`` because they are zero-dependency and
cannot import cage; that copy is an *intentional* duplicate of
``CHARS_PER_TOKEN`` and must track it.
"""
from __future__ import annotations

CHARS_PER_TOKEN = 4              # deterministic token heuristic (≈ OpenAI/Anthropic avg)
TOKENS_PER_MILLION = 1_000_000   # price rows are quoted per-million tokens
MAX_MATRIX_TOOLS = 12            # 2^12 = 4096-row ceiling on one task's permutations
METHOD_TRUST = {"measured": 2, "modeled": 1, "estimated": 0}  # provenance ranking
DEFAULT_CONFIDENCE = {"measured": 0.9, "estimated": 0.7,      # fallback ladder when
                      "type_table": 0.5, "default": 0.3}      # policy omits a key
GRAPHIFY_RECEIPT_CONFIDENCE = 0.6  # a graphify receipt is modeled, never measured
# A *report-read* receipt (graphify-capture GC2) — the agent read GRAPH_REPORT.md/wiki/**
# instead of scanning source files — is a weaker inference than a `graphify query` whose
# answer cites exact files: it can't prove the agent WOULD have read those N files. So it
# is deliberately lower-confidence, still `modeled`, and footnoted apart from query
# receipts (never conflated). Reviewable heuristic ⇒ constants, not policy.
#
# ⚠️ UNVALIDATED (OPEN-WORK G.1, 2026-07-29): the 0.3 is a *guess*, not a tuned figure.
# It has never been scored against measured outcomes — `insights calibration` needs
# report-read receipts with recorded task outcomes to compute an actual hit-rate, and
# none exist yet. Until it does, 0.3 is a placeholder that surfaces its own weakness in
# the footnote; do NOT tune it by intuition (that would launder a guess into a number).
GRAPHIFY_REPORT_READ_CONFIDENCE = 0.3  # UNVALIDATED — see note above (G.1)
SINCE_WINDOW_DAYS = {"h": 1 / 24, "d": 1, "w": 7}  # `24h` / `7d` / `2w` → days

# Ledger partition granularity (plan §3.6.1). Writers append to `calls-YYYY-MM.jsonl`
# (same for receipts/tasks); readers glob + concatenate. Reviewable here (third audit
# layer), not user-config — month is the only supported granularity. Determinism: the
# shard a row lands in derives from the row's own `ts`, never a write-time clock.
PARTITION_GRANULARITY = "month"

# Ledger-size warning threshold (plan §3.6.4 (d)). NOT a vibes number: a stamped
# call/receipt row serializes to ~290 B (measured: call 314 / receipt 264 B), and the
# plan's heavy-agent figure is 1–2k call rows/day. So a heavy *monthly* shard ≈
# 2000×30×290 B ≈ 17 MB and a heavy solo *year* ≈ 210 MB. The threshold is a multiple
# of a monthly shard (≈ 24 healthy months ≈ 2 heavy solo-years), so a power user never
# trips it inside a sane retention window — it flags a genuinely unbounded ledger, not
# heavy use. Tied to the partition mechanic, not a magic MB. Policy `[ledger] warn_mb`
# overrides; this is the fallback (the DEFAULT_CONFIDENCE policy-preferred pattern).
# The read/derive path is WARN-ONLY — the flux invariant is that a derive never
# refuses. A write-path block (cf. budgets `on_exceed = warn|block`, the CI disk-quota
# case) is a separate decision, deliberately not taken here; see the ADR.
LEDGER_ROW_BYTES = 290              # measured avg serialized JSONL row (call 314 / receipt 264 B)
LEDGER_HEAVY_ROWS_PER_DAY = 2000   # plan §3.6: a heavy agent user emits 1–2k call rows/day
LEDGER_WARN_MONTHS = 24            # warn only past ~2 years of un-pruned monthly shards
LEDGER_WARN_BYTES = LEDGER_WARN_MONTHS * 30 * LEDGER_HEAVY_ROWS_PER_DAY * LEDGER_ROW_BYTES

# Model-price family fallback (policy.price_match). Claude Code stamps full dated
# model ids (`claude-sonnet-4-5-20250929`); policies key short aliases
# (`claude-sonnet-4-6`). When an id has no exact price row, fall back to the
# same-provider row sharing the most leading hyphen-delimited *segments* — so
# `claude-sonnet-4-5-20250929` prices off a `claude-sonnet-4-…` row, while
# `claude-opus-*` can never borrow a `claude-sonnet-*` price. Before segmenting,
# both sides normalize: a known router prefix is stripped, `.` becomes `-` (Copilot
# stamps `claude-sonnet-4.6`, Anthropic ids are dashed), and trailing effort-tier
# segments drop (vendors bill every effort tier at the same per-token rate —
# verified against both pricing pages 2026-07-11; a tier billed differently would
# get its own explicit row instead). A match must share at least this many leading
# segments (brand + tier, e.g. `claude` + `sonnet`); the longest shared prefix
# wins, ties break on the lexicographically smallest key (a total, stable order —
# never dict-insertion order). A normalized match always renders `family`, never
# `exact` — method law. Heuristic, not contract or economics ⇒ it lives here, not
# in schema.py or policy.toml.
MODEL_FAMILY_MIN_SEGMENTS = 2
MODEL_EFFORT_SUFFIXES = frozenset({"low", "medium", "high", "max"})
# Router prefixes stripped before family matching — a CLOSED list, never "any
# `<x>/` prefix" (an unknown router must stay loudly UNPRICED, plan §3.3). Copilot's
# VS Code store stamps modelId `copilot/claude-opus-4.6`; the bare router id
# `copilot/auto` strips to `auto` which matches nothing — route it with an explicit
# `[alias]` row (`cage prices alias`), never a silent default.
MODEL_ROUTE_PREFIXES = ("copilot/",)

# State-dir cleanup (plan §3.6.4 remedy, `cage/cleanup.py`). Policy-preferred
# fallbacks (the DEFAULT_CONFIDENCE pattern): `cage.toml [cleanup] days` wins.
# 90 days: 30 proved tighter than a real usage gap (a project untouched for a
# month is common, not exceptional), and the auto path only ever warns now — it
# never deletes — so a longer default costs nothing but a slightly later reminder.
# The throttle keeps the piggybacked check (one stat per `cage import`) cheap.
CLEANUP_DEFAULT_DAYS = 90
CLEANUP_THROTTLE_HOURS = 24

# Bundled-prices staleness threshold (plan §3.3, `cage/freshness.py`). Vendor
# list prices historically shift a few times a year, and cage never fetches a
# rate — the bundle is only as fresh as its last build-time research pass
# (`[meta] prices_date`). 45 days is deliberately wider than a normal release
# cadence (a routinely-maintained bundle never nags) but narrow enough that a
# half-year-stale table can't hide behind silence. Past it, the freshness check
# prints "bundled prices are N days old — check for a newer cage release" on
# post-commit / doctor / the report footer. Policy-preferred fallback (the
# DEFAULT_CONFIDENCE pattern): `policy.toml [prices] stale_days` wins; `0`
# disables the age signal entirely (documented opt-out). Derived views compare
# against the newest ledger `ts`, never the wall clock — determinism law.
PRICES_STALE_DAYS = 45

# Last-import staleness gate (plan Phase 1.6, `cage/report.py`). The report footer's
# "last import: N ago" line is advice, not a banner — it renders only when the
# recorded last import is older than this many hours. 24h matches the pull-based
# capture story (a daily `cage import` cron is the documented hands-off setup, so a
# ledger refreshed within a day has nothing to advise about). Policy-preferred
# fallback (the DEFAULT_CONFIDENCE pattern): `policy.toml [capture]
# import_stale_hours` wins; `0` restores the always-on line. The age is read from
# the same wall clock `render.ago` already uses — advice text, never a
# derived-from-ledger figure, the one documented clock carve-out.
IMPORT_STALE_HOURS = 24

# Capture-on-read throttle (capture-architecture Phase 1, `cage/importcmd.py`). Every
# read that matters (report / insights / MCP read tools) lazily sweeps the log registry
# before it answers, so capture is guaranteed fresh the instant before any number is
# shown — no hook, no scheduler. Back-to-back reads must not re-sweep, so the sweep is
# throttled on the `_last_import` cursor timestamp (no new state file): a read within
# this window of the last capture is a no-op. 60s is deliberately short — long enough to
# absorb a burst of reads in one interaction, short enough that a read a minute later
# recaptures. Policy-preferred fallback (the DEFAULT_CONFIDENCE pattern):
# `policy.toml [capture] read_throttle_secs` wins; `0` disables the throttle (every read
# sweeps). The capture-on-read behavior itself is gated by `[capture] on_read` /
# `CAGE_CAPTURE_ON_READ` (default on) and, like all capture, by `[capture] enabled` /
# `CAGE_CAPTURE`; the determinism suite pins it OFF so derived views stay a pure function
# of a fixed ledger.
CAPTURE_ON_READ_THROTTLE_SECS = 60

# Authorship-provenance trust ranking (cage/originrecord.py) — a parallel ladder to
# METHOD_TRUST, for the *different* enum PROV_METHODS (schema.py): hooked (live
# PostToolUse capture) outranks transcript (parsed after the fact) outranks heuristic
# (inferred from git alone, no agent signal). Used to resolve which fragment wins when
# two provenance rows disagree on the same (sha, file) during notes union.
PROVENANCE_METHOD_TRUST = {"hooked": 2, "transcript": 1, "heuristic": 0}
PROVENANCE_CORROBORATION_BONUS = 0.2  # confidence bump when 2 independent paths agree

# `cage insights compare` min-n gate (roadmap P2). Below this many closed tasks a group
# renders "insufficient data (n=X < N)" and is excluded from every delta — the
# command explains, it never numbers. NOT a vibes number: with n<5 a single
# outlier task moves the median itself, and the IQR (quartiles) degenerates —
# so any smaller group reads as signal when it is noise. A blocking gate rather
# than a footnote because a wrong comparison is worse than none (the same rule
# credits/limits follow). Heuristic, not user economics ⇒ constants, not policy.
MIN_COMPARE_N = 5

# `cage insights estimate` min-n gate (roadmap P3) — same statistical rationale as
# MIN_COMPARE_N (a median/IQR band over fewer closed tasks is noise wearing a
# band), and the same blocking rule: below it the command explains, never
# numbers. Kept as its own name (not an alias) so the two gates can diverge if
# estimation proves to need deeper history than comparison.
MIN_ESTIMATE_N = 5

# `cage`'s task-correlation backfill min-n gate (import-ledger plan §4 / Phase 4). The
# correlation adopts an import-sourced call (session + ts, no task id) into a closed
# task by the `taskgroup` session-window join — a heuristic, so below this many
# correlated calls the pass **blocks** (returns nothing) rather than tag noise as task
# attribution. Its own name (like the other two gates) so it can diverge. The pass is
# also disabled by default (`policy.task_correlation_enabled`) until validated on real
# correlated data (handoff §3) — the gate is the second guard, not the first.
MIN_TASK_CORRELATION_N = 5

# Confidence of a correlated `task` tag — always `estimated` (a session/time-window
# heuristic, never measured or modeled). Deliberately low: it is the softest signal in
# the ledger, a best-effort join, never ground truth.
TASK_CORRELATION_CONFIDENCE = 0.5

# The NET-3 attributable-cost window (net-savings handoff, 2026-08-01). A savings
# receipt is **call-less** — the graphify/fux shims file a `task` but never a `call` —
# so the cost of *using* a tool can only be joined to recorded calls by time. A call
# counts as attributable when its `ts` falls within this many seconds **either side** of
# any of that tool's receipts on the same task.
#
# Symmetric, not forward-only, because both adjacent turns are genuinely cost-of-use:
# the turn that *invoked* the tool precedes the receipt (the agent's Bash/Read call),
# and the turn that *consumed* its output follows it (the injected context, paid on the
# next request). Union per task — a call adjacent to two receipts is counted once, so
# the subtrahend can never be inflated by receipt volume.
#
# 120s is a turn-adjacency bound, not a duration estimate: it is wide enough to survive
# a slow tool round-trip and narrow enough that an unrelated turn later in the same task
# never enters. A heuristic, not user economics ⇒ constants, not policy.
NET_ATTRIB_WINDOW_S = 120

# Confidence of a task-level **net** saving. Below `GRAPHIFY_RECEIPT_CONFIDENCE` (0.6)
# by construction: net inherits gross's modeled counterfactual *and* adds a time-window
# join on top of it, so it can never be more credible than the gross it derives from.
# Not tuned against outcomes — it is an ordering claim (net < gross), not a measurement.
NET_SAVED_CONFIDENCE = 0.4

# OTel GenAI semantic-convention version cage's `--otel` export targets
# (`cage/otelout.py`, docs/archive/v0.39-otel-export.handoff.md). **The convention is pre-stable**:
# as of this version the `gen_ai.*` attributes live in a dedicated repo, carry no 1.0,
# and names can still change between releases. Cage's determinism law — same ledger +
# policy ⇒ same output — means cage never silently follows upstream: this is the ONE
# pinned target, stamped in every emitted document's `cage.meta` block, exactly like
# `[meta] prices_version`. Bumping it is a deliberate, changelog'd change, never a
# silent drift with an upstream release.
OTEL_SEMCONV_VERSION = "1.42.0"
OTEL_SEMCONV_STATUS = "pre-stable"

