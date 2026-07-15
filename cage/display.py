"""The ONE display-context implementation (plan Phases 1+2 — output honesty).

Two jobs, one home, so no view grows its own copy of the logic:

- :class:`Display` — the resolved presentation switches for a render call:
  ``usd`` (tokens are the default; dollars are the interpretation you ask for —
  plan Phase 2.5) and ``all_columns`` (the fixed-shape escape hatch that undoes
  signal-gating for scripts). Resolution precedence: per-invocation flag > env
  ``CAGE_USD`` > policy ``[display] usd`` (`policy.display_usd`).
- :class:`Footer` — the per-invocation collector for everything that renders
  below a table: pricing footnotes (``≈``), data caveats (``·``), ⚠ blocks,
  signal-gating explanations, and advice lines (import age, price freshness).
  Lines dedupe (first occurrence wins) and render once, in a FIXED order:
  footnotes → caveats → warns → gating explanations → advice. A command
  invocation therefore speaks each note exactly once, at the bottom.

Display is presentation only — pricing always computes underneath (budget
guards, UNPRICED detection, verdict inputs), and the money-native views
(budget/roi/verdict/compare/estimate) never consult it. CSV never gates and
never sees any of this (`cage query csv-output`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

DASH = "—"  # the ONLY rendering of "couldn't price" — $0.0000 always means a real zero


@dataclass(frozen=True)
class Display:
    """Resolved presentation switches, threaded through the render layer."""
    usd: bool = False
    all_columns: bool = False


DEFAULT = Display()


def resolve(args, pol: dict) -> Display:
    """Flag > env > policy, resolved once at the CLI boundary. ``args`` is the
    argparse namespace; a missing attribute reads as "flag not given"."""
    from cage import policy
    flag = getattr(args, "usd", False)
    return Display(usd=bool(flag) or policy.display_usd(pol),
                   all_columns=bool(getattr(args, "all_columns", False)))


@dataclass
class Footer:
    """Collects the below-the-table lines for one command invocation."""
    _footnotes: list[str] = field(default_factory=list)  # ≈ pricing approximations
    _caveats: list[str] = field(default_factory=list)    # · data-fidelity notes
    _warns: list[str] = field(default_factory=list)      # ⚠ blocks (may be multi-line)
    _gaps: list[str] = field(default_factory=list)       # · signal-gating explanations
    _advice: list[str] = field(default_factory=list)     # · actionable staleness advice

    def footnote(self, line: str) -> None:
        self._add(self._footnotes, line)

    def caveat(self, line: str) -> None:
        self._add(self._caveats, line)

    def warn(self, block: str) -> None:
        self._add(self._warns, block)

    def gap(self, line: str) -> None:
        self._add(self._gaps, line)

    def advice(self, line: str) -> None:
        self._add(self._advice, line)

    @staticmethod
    def _add(bucket: list[str], line: str) -> None:
        if line and line not in bucket:  # dedupe: one voice per note, first phrasing wins
            bucket.append(line)

    def render(self) -> str:
        """The footer block ("" when nothing to say): deduped lines in fixed
        order, LF-joined. Callers append it after one blank line."""
        return "\n".join([*self._footnotes, *self._caveats, *self._warns,
                          *self._gaps, *self._advice])
