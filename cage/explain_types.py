"""The `Explanation` shape shared by `explain.py` (engine) and `explain_data.py`
(registry) — split out so the data table doesn't need to import the engine."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Explanation:
    id: str                    # "human-cost", "marginal-attribution", "cost", …
    keywords: tuple[str, ...]  # match terms scored against the normalized query
    summary: str               # one line
    formula: str               # template; {placeholders} filled from live values
    code_refs: tuple[str, ...]
    method_note: str           # which method tag this produces & why
    kind: str = "calculation"  # "calculation" | "concept"
    plan_ref: str = ""         # docs/cage-plan.md § — required for concept entries
