"""The ONE display-context implementation (plan Phases 1+2 — output honesty).

Two jobs, one home, so no view grows its own copy of the logic:

- :class:`Display` — the resolved presentation switches for a render call. Only
  ``all_columns`` remains (the fixed-shape escape hatch that undoes signal-gating for
  scripts): the ``usd`` switch and its flag/env/policy precedence went with the money
  subsystem (USAGE-ONLY, ADR 0011). There is one view now, so there is nothing to
  switch between.
- :class:`Footer` — the per-invocation collector for everything that renders
  below a table: footnotes (``≈``), data caveats (``·``), ⚠ blocks,
  signal-gating explanations, and advice lines (import age, policy drift).
  Lines dedupe (first occurrence wins) and render once, in a FIXED order:
  footnotes → caveats → warns → gating explanations → advice. A command
  invocation therefore speaks each note exactly once, at the bottom.

Display is presentation only, and CSV never gates or sees any of it
(`cage query csv-output`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: The ONLY rendering of "this figure does not exist for this row" — a recorded `0`
#: always means a measured zero. Since USAGE-ONLY (ADR 0011) the absences it marks are
#: unit absences (`units.ABSENT`: claude has no credits, kiro has no tokens on either
#: surface) and
#: structural ones (a credits-only chat has no token cells), never "couldn't price".
DASH = "—"


@dataclass(frozen=True)
class Display:
    """Resolved presentation switches, threaded through the render layer."""
    all_columns: bool = False


DEFAULT = Display()


def resolve(args, pol: dict) -> Display:
    """Resolved once at the CLI boundary. ``args`` is the argparse namespace; a missing
    attribute reads as "flag not given". ``pol`` is accepted and unused — the one
    policy-backed switch here was ``[display] usd`` (USAGE-ONLY, ADR 0011)."""
    return Display(all_columns=bool(getattr(args, "all_columns", False)))


@dataclass
class Footer:
    """Collects the below-the-table lines for one command invocation."""
    _footnotes: list[str] = field(default_factory=list)  # ≈ qualifications
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
