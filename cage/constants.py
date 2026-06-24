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
