"""Tiny monospaced-table + number formatting helpers (stdlib)."""
from __future__ import annotations

import datetime as _dt


def cmd(tail: str) -> str:
    """The canonical ``cage <tail>`` spelling for an emitted hint string. Every
    runtime hint that names a cage subcommand routes through here (plan Phase 3 §5),
    so the CLI verb map has one indirection point instead of scattered string
    literals — and the `cage <old-verb>` grep gate stays meaningful. ``tail`` is the
    post-`cage ` invocation, e.g. ``cmd("insights attrib")`` → ``"cage insights attrib"``."""
    return f"cage {tail}"


def scheduler_hint() -> str:
    """The OS-appropriate example line for user-owned capture automation — printed,
    never installed (cage law: no launchd/systemd/cron/schtasks registration)."""
    import os as _os
    if _os.name == "nt":
        return ('schtasks /create /tn cage-import /tr "cage import" /sc hourly')
    return "0 * * * * cage import"


def ago(ts: str) -> str:
    """Human "3m ago" for an ISO timestamp; fail-open to "". Used by `cage doctor`/`cage
    report` to surface "last import: N ago" (capture is pull-based, plan §3.7). A clock
    is read, but never inside a derived-from-ledger table — determinism holds. The floor
    is "just now", never per-second ("0s ago" → "2s ago" made back-to-back runs of the
    same view byte-different, which is exactly what the determinism sweeps compare)."""
    try:
        when = _dt.datetime.fromisoformat(ts)
        now = _dt.datetime.now(when.tzinfo)
        secs = max(0, int((now - when).total_seconds()))
        if secs < 90:
            return "just now"
        if secs < 5400:
            return f"{secs // 60}m ago"
        if secs < 172800:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:  # noqa: BLE001 — display-only, never raise
        return ""


def age_seconds(ts: str) -> int | None:
    """Whole seconds since an ISO timestamp; fail-open to ``None``. The clock
    carve-out behind :func:`ago` (advice text, never a derived-from-ledger
    figure) — used to *gate* the "last import: N ago" advice line the same way
    `ago` words it (plan Phase 1.6)."""
    try:
        when = _dt.datetime.fromisoformat(ts)
        now = _dt.datetime.now(when.tzinfo)
        return max(0, int((now - when).total_seconds()))
    except Exception:  # noqa: BLE001 — display-only, never raise
        return None


def envelope(command: str, data) -> dict:
    """The versioned ``cage.v1`` machine envelope (introduced for ``cage data limits --json``;
    a wider rollout is a separate packet). ``generatedAt`` is wall-clock *metadata*, never
    a derived-from-ledger figure, so the ``data`` payload stays deterministic (same ledger
    + policy ⇒ same ``data``)."""
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {"schemaVersion": "cage.v1", "generatedAt": now, "command": command, "data": data}


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
