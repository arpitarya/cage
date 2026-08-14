"""`cage query` — a deterministic, $0 explainer of cage's own math and mechanism
(handoff §2). The registry itself lives in `explain_data.py`; this module is the
engine: live-value interpolation, matching, and rendering.

Not a model Q&A: a curated registry of `Explanation` entries whose numbers are
read **live** from `policy` + `constants` (and, for concept entries, `paths` /
`agents` / the CLI parser) at render time, so an explanation can never drift from
the code. Matching is stdlib token-overlap — no embeddings, no network, no LLM
(mirrors `fux explain` / `graphify query` for family UX).

The whole point is self-verification: the printed divisor *is*
`constants.CHARS_PER_TOKEN` and the printed pipeline order *is* `policy.tool_order`
— proof the numbers aren't literals.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import asdict
from pathlib import Path

from cage import agents, constants, paths, policy, schema, usagelog
from cage.explain_data import REGISTRY
from cage.explain_types import Explanation

__all__ = ["Explanation", "REGISTRY", "match", "closest_ids", "payload",
           "render", "render_list"]


def _live(pol: dict) -> dict:
    """Current values pulled from policy + constants — the source of every number."""
    conf = dict(constants.DEFAULT_CONFIDENCE)
    foot = paths.Footprint(paths.find_project_root() or Path.cwd())
    return {
        "chars_per_token": constants.CHARS_PER_TOKEN,
        "per_million": f"{constants.TOKENS_PER_MILLION:,}",
        "max_tools": constants.MAX_MATRIX_TOOLS,
        "chats_default_rows": constants.CHATS_DEFAULT_ROWS,
        "graphify_chats_default_rows": constants.GRAPHIFY_CHATS_DEFAULT_ROWS,
        "commits_default_rows": constants.COMMITS_DEFAULT_ROWS,
        "min_match_chars": constants.MIN_MATCH_CHARS,
        # Live from the resolved policy, so a project that turned the estimator off or
        # widened the cap sees ITS values in the explanation, not the shipped default.
        "max_est_gap": policy.authorship_max_est_gap(pol),
        "estimate_hours": str(policy.authorship_estimate_hours(pol)).lower(),
        # `min_compare_n` was dropped from this table in v0.51 with the fleet study —
        # the `study-pairing` entry was its only consumer.
        "min_estimate_n": constants.MIN_ESTIMATE_N,
        "net_window_s": constants.NET_ATTRIB_WINDOW_S,
        "net_confidence": constants.NET_SAVED_CONFIDENCE,
        "order": " → ".join(policy.tool_order(pol)),
        "c_measured": conf.get("measured"), "c_estimated": conf.get("estimated"),
        "trust": " · ".join(f"{m} {n}" for m, n in constants.METHOD_TRUST.items()),
        "methods": " | ".join(schema.METHODS),
        # Show the month-partitioned shard glob (calls-YYYY-MM.jsonl), not the legacy
        # unpartitioned `calls.jsonl` — that single file no longer exists on a fresh
        # ledger, so interpolating it into the concept text misdescribed on-disk layout.
        "calls_path": str(foot.ledger / "calls-*.jsonl"),
        "receipts_path": str(foot.ledger / "receipts-*.jsonl"),
        "tasks_path": str(foot.tasks),
        "agent_surfaces": " · ".join(agents.SURFACES),
        # The machine ledger kiro's IDE rows route to (ADR 0006) — interpolated live from
        # the resolver, never a hard-coded `~/.cage`, so `CAGE_HOME` shows the truth.
        "global_base": str(paths.global_base()),
        "partition": constants.PARTITION_GRANULARITY,
        "warn_mb": f"{constants.LEDGER_WARN_BYTES / 1_000_000:.0f}",
        "n_subcommands": len(_subcommand_names()),
        "concept_ids": ", ".join(e.id for e in REGISTRY if e.kind == "concept" and e.id != "overview"),
        "ledger_env": "CAGE_LEDGER",
        "cleanup_days": policy.cleanup_days(pol),
        "cleanup_on": "on" if policy.cleanup_enabled(pol) else "off",
        "cleanup_warn_on": "on" if policy.cleanup_warn(pol) else "off",
        # policy sync (CLAUDE.md) — live version stamps, both sides
        "policy_version_bundled": str(policy.bundled_raw().get("meta", {})
                                      .get("policy_version") or "?"),
        "policy_version_project": str((policy.load_project_raw(foot.policy)
                                       if foot.policy.exists() else {})
                                      .get("meta", {}).get("policy_version")
                                      or "unknown (pre-0.25)"),
        # configurable import paths (plan Phase 4) — the live resolved candidate list
        "sources_live": _sources_live(pol),
        # the graphify interceptor twin pair (docs/adr/0007_graphify.md) — live from the one
        # enumeration `paths.py` owns, never a hard-coded "bin/graphify" literal
        "graphify_shim_posix": next(n for n in paths.GRAPHIFY_SHIMS if n == "graphify"),
        "graphify_shim_windows": next(n for n in paths.GRAPHIFY_SHIMS if n.endswith(".cmd")),
        "graphify_shim_here": paths.graphify_shim_name(),
        # the OTel GenAI semconv version `--otel` targets (work/archive/v0.39-otel-export.handoff.md) —
        # live from the one pinned constant, never a hard-coded literal in the text
        "semconv": constants.OTEL_SEMCONV_VERSION,
        "semconv_status": constants.OTEL_SEMCONV_STATUS,
        "semconv_source": constants.OTEL_SEMCONV_SOURCE,
        # the closed usage-row verdicts `insights adoption` reads (never re-derives) —
        # live from the one enumeration `usagelog.py` owns
        "outcomes": " · ".join(usagelog.OUTCOMES),
        # which agent surfaces can file a graphify savings receipt — live from the ONE
        # table `graphifytx.py` owns, the same one `cage doctor`'s graphify-coverage check
        # renders, so a gap can never be worded two different ways in two places.
        "coverage": _graphify_coverage_live(),
    }


def _graphify_coverage_live() -> str:
    """`graphifytx.GRAPHIFY_COVERAGE` as indented explainer lines."""
    from cage import graphifytx
    return "\n".join(f"    · {line}" for line in graphifytx.coverage_lines())


def _sources_live(pol: dict) -> str:
    """The resolved import candidates, one indented line each with provenance — the
    live values behind `cage query sources` (never a hard-coded example)."""
    res = paths.resolve_log_sources(pol)
    lines = [f"    · {s.agent:<10} [{s.provenance}] {s.path}" for s in res.sources]
    lines += [f"    · {a:<10} [disabled by policy]" for a in res.disabled]
    return "\n".join(lines) or "    (none resolved)"


def _subcommand_names() -> list[str]:
    """Every leaf view (an actual derived command), read live from the parser (no
    literal list). Descends into the Phase-3 command groups (insights/task/
    authorship/data) so their subcommands count as the views they are; the group
    name itself is not a view. `hook-*` plumbing is excluded."""
    from cage import cli  # local: cli → clicmds → explain would otherwise cycle

    out: list[str] = []

    def walk(parser) -> bool:  # returns True if the parser has nested subcommands
        subs = getattr(parser, "_subparsers", None)
        if subs is None:
            return False
        for action in subs._group_actions:  # type: ignore[attr-defined]
            if isinstance(action, argparse._SubParsersAction):
                for name, child in action.choices.items():
                    if name.startswith("hook-"):
                        continue
                    if not walk(child):  # a leaf → it's a view
                        out.append(name)
        return True

    walk(cli.build_parser())
    return out


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
