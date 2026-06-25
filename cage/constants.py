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
# `claude-opus-*` can never borrow a `claude-sonnet-*` price. A match must share at
# least this many leading segments (brand + tier, e.g. `claude` + `sonnet`); the
# longest shared prefix wins, ties break on the lexicographically smallest key
# (a total, stable order — never dict-insertion order). Heuristic, not contract or
# economics ⇒ it lives here, not in schema.py or policy.toml.
MODEL_FAMILY_MIN_SEGMENTS = 2

# Authorship-provenance trust ranking (cage/originrecord.py) — a parallel ladder to
# METHOD_TRUST, for the *different* enum PROV_METHODS (schema.py): hooked (live
# PostToolUse capture) outranks transcript (parsed after the fact) outranks heuristic
# (inferred from git alone, no agent signal). Used to resolve which fragment wins when
# two provenance rows disagree on the same (sha, file) during notes union.
PROVENANCE_METHOD_TRUST = {"hooked": 2, "transcript": 1, "heuristic": 0}
PROVENANCE_CORROBORATION_BONUS = 0.2  # confidence bump when 2 independent paths agree
