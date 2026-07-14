"""Local pricing-freshness signals (plan §3.3) — sync drift, bundle age, UNPRICED.

Cage never fetches a price (no network on any cage code path), so "are my
prices current?" is answered from **local evidence only**, by three signals:

1. **sync drift** — the project ``[meta]`` is older than the installed bundle's
   → the existing `cage prices sync` recommendation, verbatim.
2. **bundle age** — the bundle's own ``[meta] prices_date`` is more than
   ``stale_days`` old (policy ``[prices] stale_days``,
   ``constants.PRICES_STALE_DAYS`` fallback; ``0`` disables) → a faithfully
   synced project can still be confidently stale.
3. **UNPRICED presence** — calls or call-less token receipts billing $0 → the
   existing runnable fix hints, byte-for-byte.

One implementation, three surfaces (the csvout lesson): the git post-commit
hook, `cage doctor`, and the `cage report` footer all render lines from
:func:`freshness`. Determinism law: derived views pass ``today=None`` so the
age math anchors on the newest ledger ``ts`` (data-relative, clock-free —
same ledger + policy ⇒ same lines); the post-commit hook and doctor (a
write-path event and a diagnostic, where the clock is already allowed) pass
wall-clock today. Print-only everywhere — a freshness line never gates,
blocks, or exits non-zero.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import ledger, paths, policy, prices

_AGE_LINE = "bundled prices are {n} days old — check for a newer cage release"


def _parse_date(s: object) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def sync_line(root: Path) -> str | None:
    """Signal 1 — verbatim :func:`pricescmd.sync_recommendation` (one wording,
    one home). No project policy.toml at all ⇒ the bundle applies directly —
    nothing can be stale (the `prices list`/doctor rule). A pre-v0.19 project
    policy (no ``[meta]``) reads as older-than-bundle and fires the hint."""
    from cage import pricescmd  # deferred: CLI-layer module, keep import light
    foot = paths.Footprint(root)
    if not foot.policy.exists():
        return None
    meta = policy.load_project_raw(foot.policy).get("meta", {})
    return pricescmd.sync_recommendation(meta)


def age_line(pol: dict, anchor: _dt.date | None) -> str | None:
    """Signal 2 — the bundle's own age against ``anchor``. ``stale_days <= 0``
    disables (documented opt-out); no anchor (empty ledger on the data-relative
    path) or an unparseable ``[meta]`` date ⇒ no line — never a guess."""
    sd = policy.prices_stale_days(pol)
    if sd <= 0 or anchor is None:
        return None
    meta = policy.bundled_raw().get("meta", {})
    stamped = _parse_date(meta.get("prices_date") or meta.get("prices_version"))
    if stamped is None:
        return None
    n = (anchor - stamped).days
    if n <= sd:
        return None
    return _AGE_LINE.format(n=n)


def unpriced_lines(root: Path, pol: dict, calls: list[dict] | None = None,
                   receipts: list[dict] | None = None) -> list[str]:
    """Signal 3 — UNPRICED calls and call-less token receipts, rendered by the
    existing helpers byte-for-byte (`report.unpriced_line`,
    `receiptprice.unpriced_receipts_line`) — reused, never re-phrased."""
    from cage import receiptprice, report  # deferred: report imports this module
    calls = ledger.calls(root) if calls is None else calls
    receipt_rows = ledger.receipts(root) if receipts is None else receipts
    out: list[str] = []
    detail: dict[str, dict] = {}
    for c in calls:
        _, match, _ = prices.call_usd_match(pol, c)
        if match != "none":
            continue
        d = detail.setdefault(f"{c.get('provider') or '—'}/{c.get('model') or '—'}",
                              {"calls": 0, "tokens": 0})
        d["calls"] += 1
        d["tokens"] += c.get("tokens_in", 0) + c.get("tokens_out", 0)
    if detail:
        out.append(report.unpriced_line(dict(sorted(detail.items()))))
    by_id = {c.get("id"): c for c in calls}
    idx = receiptprice.build(calls, receipt_rows)  # once per view, never per receipt
    agg = {"receipts": 0, "tokens": 0, "tools": set()}
    for r in receipt_rows:
        if r.get("tool") == "human":  # Tier-1 axis — never a pricing gap (§4.10)
            continue
        if receiptprice.eligible(r, by_id) and receiptprice.resolve(r, idx, pol) is None:
            agg["receipts"] += 1
            agg["tokens"] += int(r.get("saved", 0.0))
            agg["tools"].add(r.get("tool", ""))
    if agg["receipts"]:
        out.append(receiptprice.unpriced_receipts_line(
            {**agg, "tools": sorted(agg["tools"])}))
    return out


def freshness(root: Path, pol: dict, *, today: _dt.date | None = None,
              include_unpriced: bool = True,
              rows: list[dict] | None = None) -> list[str]:
    """The three-signal check — zero-or-more actionable lines, ``[]`` when clean.

    ``today=None`` ⇒ data-relative anchor (newest ledger ``ts``) for derived
    views; a caller on a clock-allowed path passes today's date. ``rows`` lets
    a view that already loaded the calls (report) skip a second ledger scan.
    ``include_unpriced=False`` is for `render_report`, which prints the same
    UNPRICED lines natively — one home for the strings, no double-print."""
    calls = ledger.calls(root) if rows is None else rows
    if today is not None:
        anchor: _dt.date | None = today
    else:
        newest = ledger.newest_ts(calls)
        anchor = newest.date() if newest is not None else None
    out: list[str] = []
    if (s := sync_line(root)) is not None:
        out.append(s)
    if (a := age_line(pol, anchor)) is not None:
        out.append(a)
    if include_unpriced:
        out.extend(unpriced_lines(root, pol, calls=calls))
    return out
