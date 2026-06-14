"""Tiny monospaced-table + number formatting helpers (stdlib, ≤50 lines)."""
from __future__ import annotations


def usd(x: float) -> str:
    return f"${x:,.4f}"


def tok(n: float) -> str:
    return f"{int(round(n)):,}"


def pct(part: float, whole: float) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "—"


def table(headers: list[str], rows: list[list[str]], rights: set[int] | None = None) -> str:
    """Align columns; indices in ``rights`` are right-justified (numbers)."""
    rights = rights or set()
    cols = list(zip(*([headers, *rows]))) if rows else [[h] for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]

    def fmt(cells: list[str]) -> str:
        out = []
        for i, c in enumerate(cells):
            c = str(c)
            out.append(c.rjust(widths[i]) if i in rights else c.ljust(widths[i]))
        return "  ".join(out).rstrip()

    sep = "  ".join("-" * w for w in widths)
    return "\n".join([fmt(headers), sep, *(fmt(r) for r in rows)])
