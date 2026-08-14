"""Modeling what graphify is *going to* save (graphify-capture plan GC5) — three claims,
three tags, never blended, never summed into a measured total.

- **(a) history band** — the `insights estimate` pattern applied to graphify's own
  receipts: median + IQR of what past graphify savings actually were. `modeled`;
  **refuses below `MIN_ESTIMATE_N`** (a band over noise is worse than none); deterministic
  (same ledger ⇒ same band). The estimator never self-reports confidence — that is a
  measured hit-rate, exactly as `insights estimate`/`calibration` establish.
- **(b) day-one repo ceiling** — from the graph itself (`repoceiling.corpus_tokens`,
  the SAME computation the GC2 report-read counterfactual uses), no history, no LLM,
  deterministic: reading the whole source corpus (~N files ≈ X tokens) vs a compact
  graph answer (~Y tokens) bounds the per-question saving. A static `modeled` band with
  its derivation footnoted — the "is graphify worth installing here" number, available
  before a single query has run.
- **(c) verdict composition** — `insights verdict graphify` composes (a)/(b) as tagged
  inputs; it stays a pure composer and keeps its INSUFFICIENT-DATA refusal (`verdict.py`).

Law: a projection is a band, labelled, refusable — never a measured total.
"""
from __future__ import annotations

import statistics
from pathlib import Path

from cage import ledger
from cage.constants import MIN_ESTIMATE_N


def _dist(vals: list[float]) -> dict:
    if len(vals) < 2:  # unreachable at MIN_ESTIMATE_N ≥ 2; guards a lowered constant
        return {"median": vals[0], "q1": vals[0], "q3": vals[0]}
    q1, med, q3 = statistics.quantiles(vals, n=4, method="inclusive")
    return {"median": med, "q1": q1, "q3": q3}


def history_band(root: Path, pol: dict) -> dict:
    """(a) The per-query expected-saving band over graphify's recorded receipts (token
    `saved`). Refuses below `MIN_ESTIMATE_N`. `modeled` — history applied to an unrun
    query is a reconstruction, never an invoice."""
    saved = [float(r.get("saved", 0.0)) for r in ledger.receipts(root)
             if r.get("tool") == "graphify" and float(r.get("saved", 0.0)) > 0]
    n = len(saved)
    if n < MIN_ESTIMATE_N:
        return {"ok": False, "n": n, "min_n": MIN_ESTIMATE_N, "method": "modeled",
                "reason": (f"insufficient graphify history (n={n} < {MIN_ESTIMATE_N} "
                           "receipts) — refusing a band over noise")}
    return {"ok": True, "n": n, "min_n": MIN_ESTIMATE_N, "method": "modeled",
            "tokens": _dist(saved)}


def repo_ceiling(root: Path, cwd: Path | None = None) -> dict:
    """(b) The deterministic day-one ceiling from `graphify-out/graph.json`, **bounded by
    the graph's own community structure** (Phase A, 2026-07-29). A graph answer stands in
    for **one community** — the largest coherent concern a single architecture question
    can span — not the union of every file the graph touches, so the ceiling is the
    largest community's corpus (`ceiling_tokens`), with the median community as the
    typical case (`typical_tokens`) and the whole corpus kept only as unbounded context
    (`corpus_tokens`). No history, no clock — same graph + files ⇒ same band. `modeled`,
    derivation carried for the footnote.

    Fallback: a pre-community graph.json (no `community` field) can't be bounded, so it
    reports the whole corpus with ``bounded=False`` — loud, never silently decoration.
    ``ok=False`` when no graph / no resolvable files."""
    base = Path(cwd) if cwd is not None else Path.cwd()
    graph_json = base / "graphify-out" / "graph.json"
    if not graph_json.is_file():
        return {"ok": False, "method": "modeled",
                "reason": "no graphify-out/graph.json — build one (`graphify update .`) "
                          "for a day-one ceiling"}
    from cage import repoceiling
    roots = [base, base / "graphify-out" / ".."]
    cc = repoceiling.community_corpus(graph_json, roots)
    if cc.get("ok"):
        return {"ok": True, "method": "modeled", "bounded": True,
                "files": cc["whole_files"], "corpus_tokens": cc["whole_tokens"],
                "communities": cc["communities"], "ceiling_files": cc["largest_files"],
                "ceiling_tokens": cc["largest_tokens"], "typical_tokens": cc["typical_tokens"]}
    # fallback: pre-community graph — the whole corpus, labelled unbounded (not decoration)
    n_files, raw = repoceiling.corpus_tokens(graph_json, roots)
    if raw <= 0 or n_files <= 0:
        return {"ok": False, "method": "modeled",
                "reason": "graph.json resolved no source files on disk (drifted/moved?)"}
    return {"ok": True, "method": "modeled", "bounded": False,
            "files": n_files, "corpus_tokens": raw, "communities": 0,
            "ceiling_files": n_files, "ceiling_tokens": raw, "typical_tokens": raw}


def render_history_band(d: dict) -> str:
    from cage import render
    if not d["ok"]:
        return (f"graphify history band · {d['reason']}\n"
                f"  method: {d['method']} — run more graphify queries (they file receipts "
                "at import), then re-run.")
    t = d["tokens"]
    return "\n".join([
        "graphify history band · per-query GROSS saving from recorded receipts",
        f"  n = {d['n']} graphify receipts",
        f"  gross saved tokens: median {t['median']:,.0f} · IQR "
        f"{t['q1']:,.0f}–{t['q3']:,.0f}",
        f"  method: {d['method']} — history applied to an unrun query, never an invoice",
        "  confidence: none self-reported — a measured hit-rate is the accuracy",
        "  gross: the cost of running the query is not subtracted "
        "(`cage query gross-vs-net`)",
    ])


def ceiling_footer_line(d: dict) -> str:
    """A compact one-line form of the day-one ceiling for the `report` footer (G4,
    2026-07-29). ``""`` when unavailable (no graph / no resolvable files) so the footer
    stays silent in non-graphify projects. Modeled, in **tokens** (never blended into
    report's money-native total — it lives below the table), derivation pointed at
    `insights verdict graphify`. Pure: formats an already-computed dict, does no I/O."""
    if not d.get("ok"):
        return ""
    if not d.get("bounded", True):
        return (f"· graphify repo ceiling ≈ {d['ceiling_tokens']:,} GROSS tokens per "
                f"architecture question (modeled, UNBOUNDED — pre-community graph) — "
                f"`cage query graphify-coverage` for the derivation")
    return (f"· graphify repo ceiling ≈ {d['ceiling_tokens']:,} GROSS tokens per "
            f"architecture question (modeled, largest community; typical ≈ "
            f"{d['typical_tokens']:,}) — `cage query graphify-coverage` for the "
            f"derivation")


def render_repo_ceiling(d: dict) -> str:
    if not d["ok"]:
        return f"graphify repo ceiling · {d['reason']}"
    if not d.get("bounded", True):
        return "\n".join([
            "graphify repo ceiling · day-one bound from graph.json",
            f"  corpus: {d['files']:,} source files ≈ {d['corpus_tokens']:,} tokens "
            "(whole graph — no community structure to bound by)",
            f"  ceiling: ≈ {d['ceiling_tokens']:,} GROSS tokens per architecture question "
            "(UNBOUNDED upper bound — pre-community graph)",
            f"  method: {d['method']} — a static bound from the graph, not a measured saving",
            "  gross: the cost of running the query is not subtracted "
            "(`cage query gross-vs-net`)",
        ])
    return "\n".join([
        "graphify repo ceiling · day-one bound from graph.json",
        f"  full corpus: {d['files']:,} source files across {d['communities']:,} "
        f"communities ≈ {d['corpus_tokens']:,} tokens (context — no one question reads all)",
        f"  bounded ceiling: ≈ {d['ceiling_tokens']:,} GROSS tokens per architecture "
        f"question (largest community, {d['ceiling_files']:,} files) — typical ≈ "
        f"{d['typical_tokens']:,} tokens (median community)",
        f"  method: {d['method']} — a static bound from the graph's community structure, "
        "not a measured saving",
        "  gross: the cost of running the query is not subtracted "
        "(`cage query gross-vs-net`)",
    ])
