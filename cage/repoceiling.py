"""The graph's own source-file corpus — one computation, used twice (graphify-capture
plan GC2 report-read counterfactual + GC5b day-one repo ceiling).

graphify writes `graphify-out/graph.json`, whose nodes carry a `source_file` (e.g.
`pkg/store.py`). That set of files IS the corpus a graph answer stands in for: reading
`GRAPH_REPORT.md` (or a `graphify query`) *instead of* scanning those files is the
saving. This module resolves that corpus deterministically — no history, no LLM, no
clock — so:

- **GC2 report-read** uses `corpus_tokens` as the counterfactual (`raw_alternative`) for
  a Read of the report/wiki;
- **GC5b day-one ceiling** uses the same `corpus_tokens` as the static upper bound
  ("an architecture question here avoids ~N files ≈ X tokens").

One implementation, cited by FORMULAS.md, so the two routes can never drift. Determinism:
same `graph.json` + same on-disk files ⇒ same numbers, always. Counts-never-content: only
file *sizes*/token counts are read; file bodies are summed to a token total, never stored.
Fail-open: a missing/malformed graph or an unresolvable file is skipped, never raised.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from cage.graphifymeter import toks


def source_files(graph_json_path: Path) -> list[str]:
    """The deduped, sorted list of `source_file` paths across the graph's nodes — the
    corpus a graph answer replaces. ``[]`` for a missing/malformed graph (fail-open)."""
    try:
        g = json.loads(graph_json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    nodes = g.get("nodes") if isinstance(g, dict) else None
    if not isinstance(nodes, list):
        return []
    seen: dict[str, None] = {}
    for n in nodes:
        if isinstance(n, dict):
            sf = n.get("source_file")
            if isinstance(sf, str) and sf.strip():
                seen[sf.strip()] = None
    return sorted(seen)


def _resolve(rel: str, roots) -> Path | None:
    for root in roots:
        cand = Path(root) / rel
        try:
            if cand.is_file():
                return cand
        except OSError:
            continue
    p = Path(rel)
    try:
        return p if p.is_file() else None
    except OSError:
        return None


def corpus_tokens(graph_json_path: Path, roots) -> tuple[int, int]:
    """``(files_resolved, tokens)`` — the number of corpus files present on disk and the
    summed `toks()` of their whole contents, resolved against ``roots`` (the repo the
    graph describes). Uses the SAME `toks` divisor as every graphify receipt, so the
    ceiling and a real query's counterfactual are on one scale. Files that don't resolve
    are skipped (import-time drift is acceptable within `modeled`); the count reflects
    what was actually measurable."""
    files = source_files(graph_json_path)
    resolved = 0
    total = 0
    for rel in files:
        cand = _resolve(rel, roots)
        if cand is None:
            continue
        try:
            total += toks(cand.read_text(encoding="utf-8", errors="ignore"))
            resolved += 1
        except OSError:
            continue
    return resolved, total


def community_corpus(graph_json_path: Path, roots) -> dict:
    """The **bounded** day-one ceiling (Phase A, 2026-07-29): the graph's own community
    structure caps `corpus_tokens` to the largest coherent concern a single architecture
    question can span, instead of the whole repo.

    Why: `corpus_tokens` sums *every* file the graph touches. On the 7-file golden
    workspace that reads as sane; on a real repo (cage's own graph: 249 files ≈ 552k
    tokens) the implied counterfactual — *"one architecture question would have read
    every file in the repo"* — is not credible, so the ceiling becomes decoration. A
    graph answer stands in for **one community** (the auth cluster, the CLI cluster), not
    the union of all of them; the honest upper bound is therefore the **largest**
    community's corpus, with the **median** community as the typical case.

    Groups each node's `source_file` by its `community` id, resolves+tokenizes each
    distinct file **once**, and returns::

        {"ok": True, "communities": N, "whole_files": F, "whole_tokens": T,
         "largest_files": lf, "largest_tokens": lt, "typical_tokens": mt}

    Determinism: same `graph.json` + same on-disk files ⇒ same grouping ⇒ same numbers
    (the community ids are read straight from the committed graph — cage never recomputes
    them). Fail-open: ``{"ok": False}`` when the graph is missing/malformed **or carries
    no `community` field** (a pre-community graph) — the caller falls back to the whole
    corpus, loudly labelled unbounded, never silently."""
    try:
        g = json.loads(graph_json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False}
    nodes = g.get("nodes") if isinstance(g, dict) else None
    if not isinstance(nodes, list):
        return {"ok": False}
    comm: dict[object, set[str]] = {}
    has_comm = False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        sf = n.get("source_file")
        if not (isinstance(sf, str) and sf.strip()):
            continue
        c = n.get("community")
        if c is not None:
            has_comm = True
        comm.setdefault(c, set()).add(sf.strip())
    if not has_comm:
        return {"ok": False}
    toks_by_file: dict[str, int] = {}
    for files in comm.values():
        for rel in files:
            if rel in toks_by_file:
                continue
            cand = _resolve(rel, roots)
            if cand is None:
                toks_by_file[rel] = 0
                continue
            try:
                toks_by_file[rel] = toks(cand.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                toks_by_file[rel] = 0
    per_comm: list[tuple[int, int]] = []          # (files_resolved, tokens) per community
    for c, files in comm.items():
        if c is None:
            continue
        resolved = [f for f in files if toks_by_file.get(f, 0) > 0]
        if resolved:
            per_comm.append((len(resolved), sum(toks_by_file[f] for f in resolved)))
    if not per_comm:
        return {"ok": False}
    whole_files = sum(1 for t in toks_by_file.values() if t > 0)
    whole_tokens = sum(toks_by_file.values())
    largest = max(per_comm, key=lambda ft: ft[1])
    typical = int(statistics.median(sorted(t for _, t in per_comm)))
    return {"ok": True, "communities": len(per_comm),
            "whole_files": whole_files, "whole_tokens": whole_tokens,
            "largest_files": largest[0], "largest_tokens": largest[1],
            "typical_tokens": typical}
