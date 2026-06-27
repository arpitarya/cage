"""Tiny monospaced-table + number formatting helpers (stdlib)."""
from __future__ import annotations

import datetime as _dt


def ago(ts: str) -> str:
    """Human "3m ago" for an ISO timestamp; fail-open to "". Used by `cage doctor`/`cage
    report` to surface "last import: N ago" (capture is pull-based, plan §3.7). A clock
    is read, but never inside a derived-from-ledger table — determinism holds."""
    try:
        when = _dt.datetime.fromisoformat(ts)
        now = _dt.datetime.now(when.tzinfo)
        secs = max(0, int((now - when).total_seconds()))
        if secs < 90:
            return f"{secs}s ago"
        if secs < 5400:
            return f"{secs // 60}m ago"
        if secs < 172800:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:  # noqa: BLE001 — display-only, never raise
        return ""


def usd(x: float) -> str:
    return f"${x:,.4f}"


def signed_usd(x: float) -> str:
    """Like ``usd`` but always carries an explicit sign (for a net win/loss column)."""
    return f"{'+' if x >= 0 else '-'}${abs(x):,.4f}"


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
