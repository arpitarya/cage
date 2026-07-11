"""Code heuristics & invariants — the third audit layer (cage's numbers story).

Three layers, kept distinct so every number cage prints is reviewable in *one*
place per layer:

  · **Contract** — the closed enums ``UNITS`` / ``METHODS`` — live in
    ``schema.py`` (the substrate contract; do not move them here).
  · **Policy** — user-tunable economics (model prices, the human $/hr rate,
    default minutes, budgets, pipeline order, confidence overrides) — live in
    ``policy.toml`` (the only place economic numbers live).
  · **Constants** (this file) — heuristics & invariants that are *not* meant as
    user config but that must still be reviewable: the token divisor, the
    per-million price scale, the matrix ceiling, the provenance ranking, and the
    confidence *fallback*.

``DEFAULT_CONFIDENCE`` is a fallback only — ``human.py`` prefers the policy
``[human.confidence]`` block and drops to this constant just for an unset key.

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
# fallbacks (the DEFAULT_CONFIDENCE pattern): `policy.toml [cleanup] days` wins.
# 30 days comfortably outlives every consumer of the cleanable classes: a stale
# provenance buffer's transcript fallback already ran at SessionEnd, a deleted
# source log's cursor can never match again, and debug.log is observational only.
# The throttle keeps the piggybacked check (one stat per `cage import`) cheap.
CLEANUP_DEFAULT_DAYS = 30
CLEANUP_THROTTLE_HOURS = 24

# Authorship-provenance trust ranking (cage/originrecord.py) — a parallel ladder to
# METHOD_TRUST, for the *different* enum PROV_METHODS (schema.py): hooked (live
# PostToolUse capture) outranks transcript (parsed after the fact) outranks heuristic
# (inferred from git alone, no agent signal). Used to resolve which fragment wins when
# two provenance rows disagree on the same (sha, file) during notes union.
PROVENANCE_METHOD_TRUST = {"hooked": 2, "transcript": 1, "heuristic": 0}
PROVENANCE_CORROBORATION_BONUS = 0.2  # confidence bump when 2 independent paths agree

# `cage compare` min-n gate (roadmap P2). Below this many closed tasks a group
# renders "insufficient data (n=X < N)" and is excluded from every delta — the
# command explains, it never numbers. NOT a vibes number: with n<5 a single
# outlier task moves the median itself, and the IQR (quartiles) degenerates —
# so any smaller group reads as signal when it is noise. A blocking gate rather
# than a footnote because a wrong comparison is worse than none (the same rule
# credits/limits follow). Heuristic, not user economics ⇒ constants, not policy.
MIN_COMPARE_N = 5

# `cage estimate` min-n gate (roadmap P3) — same statistical rationale as
# MIN_COMPARE_N (a median/IQR band over fewer closed tasks is noise wearing a
# band), and the same blocking rule: below it the command explains, never
# numbers. Kept as its own name (not an alias) so the two gates can diverge if
# estimation proves to need deeper history than comparison.
MIN_ESTIMATE_N = 5

# Derived human-attention idle cap (plan §4.10, `cage/attention.py`). A turn-gap
# (previous assistant end → next human turn) is supervision time only up to a
# point: past it the user has plainly walked away (meeting, lunch, overnight),
# and summing raw gaps would bill idle hours as attention — the exact
# time-from-timestamps fallacy the human-baseline design bans for commit history
# (design §9 `cage calibrate`). 10 minutes is a deliberately conservative ceiling:
# long enough to cover reading a diff and composing the next prompt, short enough
# that an abandoned session contributes at most one cap per turn. Policy-preferred
# fallback (the DEFAULT_CONFIDENCE pattern): `policy.toml [human] idle_cap_minutes`
# wins; this constant covers an unset key. Changing either re-derives the minutes
# at read time — the ledger stores raw `gap_ms` and is never rewritten.
IDLE_CAP_MINUTES = 10
