"""`cage query` — a deterministic, $0 explainer of cage's own math and mechanism
(handoff §2). The registry itself lives in `explain_data.py`; this module is the
engine: live-value interpolation, matching, and rendering.

Not a model Q&A: a curated registry of `Explanation` entries whose numbers are
read **live** from `policy` + `constants` (and, for concept entries, `paths` /
`agents` / the CLI parser) at render time, so an explanation can never drift from
the code. Matching is stdlib token-overlap — no embeddings, no network, no LLM
(mirrors `fux explain` / `graphify query` for family UX).

The whole point is self-verification: the printed rate *is* the policy rate, the
printed divisor *is* `constants.CHARS_PER_TOKEN`. Set `CAGE_HUMAN_RATE` and the
`human-cost` formula re-prices in place — proof the number isn't a literal.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import asdict
from pathlib import Path

from cage import agents, constants, paths, policy, schema
from cage.explain_data import REGISTRY
from cage.explain_types import Explanation

__all__ = ["Explanation", "REGISTRY", "match", "closest_ids", "payload",
           "render", "render_list"]


def _live(pol: dict) -> dict:
    """Current values pulled from policy + constants — the source of every number."""
    rate, src = policy.human_rate_source(pol)
    conf = {**constants.DEFAULT_CONFIDENCE, **policy.human_rates(pol).get("confidence", {})}
    foot = paths.Footprint(paths.find_project_root() or Path.cwd())
    return {
        "rate": f"{rate:g}", "rate_src": src,
        "chars_per_token": constants.CHARS_PER_TOKEN,
        "per_million": f"{constants.TOKENS_PER_MILLION:,}",
        "max_tools": constants.MAX_MATRIX_TOOLS,
        "min_compare_n": constants.MIN_COMPARE_N,
        "min_estimate_n": constants.MIN_ESTIMATE_N,
        "default_minutes": policy.human_rates(pol).get("default_minutes", 60),
        "order": " → ".join(policy.tool_order(pol)),
        "c_measured": conf.get("measured"), "c_estimated": conf.get("estimated"),
        "c_type": conf.get("type_table"), "c_default": conf.get("default"),
        "trust": " · ".join(f"{m} {n}" for m, n in constants.METHOD_TRUST.items()),
        "methods": " | ".join(schema.METHODS),
        # Show the month-partitioned shard glob (calls-YYYY-MM.jsonl), not the legacy
        # unpartitioned `calls.jsonl` — that single file no longer exists on a fresh
        # ledger, so interpolating it into the concept text misdescribed on-disk layout.
        "calls_path": str(foot.ledger / "calls-*.jsonl"),
        "receipts_path": str(foot.ledger / "receipts-*.jsonl"),
        "tasks_path": str(foot.tasks),
        "agent_surfaces": " · ".join(agents.SURFACES),
        "partition": constants.PARTITION_GRANULARITY,
        "warn_mb": f"{constants.LEDGER_WARN_BYTES / 1_000_000:.0f}",
        "n_subcommands": len(_subcommand_names()),
        "concept_ids": ", ".join(e.id for e in REGISTRY if e.kind == "concept" and e.id != "overview"),
        "ledger_env": "CAGE_LEDGER",
    }


def _subcommand_names() -> list[str]:
    """Registered top-level subcommands, read live from the parser (no literal list)."""
    from cage import cli  # local: cli → clicmds → explain would otherwise cycle

    for action in cli.build_parser()._subparsers._group_actions:  # type: ignore[attr-defined]
        if isinstance(action, argparse._SubParsersAction):
            return [n for n in action.choices if not n.startswith("hook-")]
    return []


_BY_ID = {e.id: e for e in REGISTRY}
_WORD = re.compile(r"[a-z0-9]+")


def _terms(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _score(query_terms: list[str], e: Explanation) -> int:
    """Token-overlap score: a full keyword/id hit is 2; a stem hit is 1.

    A stem hit is a shared ≥4-char prefix (e.g. ``calc`` ↔ ``calculated``) — strict
    enough that filler like ``a`` / ``is`` / ``what`` scores nothing, so a query with
    no real overlap correctly falls through to ``closest_ids`` rather than guessing.
    """
    idwords = {e.id, *_terms(e.id.replace("-", " "))}  # a hit on the id is strong intent
    kw = set(e.keywords) | idwords
    s = sum(3 if q in idwords else 2 for q in query_terms if q in kw)
    for q in query_terms:                # stem hit: a shared ≥4-char prefix
        if q in kw or len(q) < 4:
            continue
        on_id = any(len(k) >= 4 and (k.startswith(q) or q.startswith(k)) for k in idwords)
        on_kw = any(len(k) >= 4 and (k.startswith(q) or q.startswith(k)) for k in kw)
        s += 2 if on_id else (1 if on_kw else 0)  # an id-word stem still reads as intent
    return s


def match(query: str, *, top: int = 1) -> list[Explanation]:
    """Best-matching entries for a query (exact id wins outright). Deterministic."""
    q = query.strip()
    if q in _BY_ID:                      # exact topic id
        return [_BY_ID[q]]
    terms = _terms(q)
    ranked = sorted(REGISTRY, key=lambda e: (-_score(terms, e), REGISTRY.index(e)))
    hits = [e for e in ranked if _score(terms, e) > 0]
    return hits[:top]


def closest_ids(query: str, n: int = 5) -> list[str]:
    """When nothing matches: the n best-overlap ids to suggest (never a guess)."""
    terms = _terms(query)
    ranked = sorted(REGISTRY, key=lambda e: (-_score(terms, e), REGISTRY.index(e)))
    return [e.id for e in ranked[:n]]


def payload(e: Explanation, pol: dict) -> dict:
    """The structured form (`--json`) — formula interpolated with live values."""
    d = asdict(e)
    d["formula"] = e.formula.format(**_live(pol))
    return d


def render(e: Explanation, pol: dict) -> str:
    """The text render — same live numbers as `payload`. Concept entries skip the
    `method:` line (it doesn't apply) and add `see also:` + `plan:`."""
    body = e.formula.format(**_live(pol))
    if e.kind == "concept":
        lines = [f"{e.id} · {e.summary}", f"  {body}",
                 f"  code:     {' · '.join(e.code_refs)}",
                 f"  plan:     {e.plan_ref}"]
        return "\n".join(lines)
    lines = [f"{e.id} · {e.summary}", f"  formula:  {body}",
             f"  method:   {e.method_note}",
             f"  code:     {' · '.join(e.code_refs)}"]
    return "\n".join(lines)


def render_list(*, kind: str | None = None) -> str:
    """`--list` — every topic grouped by kind (calculation block, then concept)."""
    kinds = [kind] if kind else ["calculation", "concept"]
    blocks = []
    for k in kinds:
        rows = [e for e in REGISTRY if e.kind == k]
        if not rows:
            continue
        blocks.append(f"{k}:\n" + "\n".join(f"  {e.id:<22} {e.summary}" for e in rows))
    return "\n\n".join(blocks)
