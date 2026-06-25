"""`cage report` — the ledger rollup: spend by agent / route / model / day (plan §7).

Any meter does this; it's the honest floor the rest of Cage builds on. Pure
aggregation over `calls.jsonl`, grouped on whichever dimension you ask for.
"""
from __future__ import annotations

from pathlib import Path

from cage import convert, ledger, prices, render

DIMENSIONS = ("route", "agent", "model", "provider", "day", "task")
SAVINGS_DIMS = ("task", "agent")  # dims a receipt joins cleanly to (§3.1); others fuzzy


def _key(call: dict, dim: str) -> str:
    if dim == "day":
        return (call.get("ts") or "")[:10] or "—"
    return str(call.get(dim) or "—")


def _new_group() -> dict:
    return {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cached_in": 0, "usd": 0.0}


def _nonhuman_savings(root: Path, pol: dict, since: str | None):
    """Yield ``(receipt, call, saved_usd)`` for each non-human receipt in the window.

    Tier-1 ``tool="human"`` receipts are a *different axis* (`cage human`); counting
    them here would double-count and mix axes — skip them, matching `roi.by_tool` (§4.4).
    USD comes only through the one unit→USD dispatch (`convert.saved_usd`).
    """
    by_id = {c.get("id"): c for c in ledger.calls(root)}
    for r in ledger.since(ledger.receipts(root), since):
        if r.get("tool") == "human":
            continue
        call = by_id.get(r.get("call"), {})
        yield r, call, convert.saved_usd(r, call, pol)


def summarize(root: Path, pol: dict, dim: str = "route",
              since: str | None = None) -> dict:
    calls = ledger.since(ledger.calls(root), since)
    groups: dict[str, dict] = {}
    unpriced: set[str] = set()       # provider/model that billed $0 with no price row
    family: dict[str, str] = {}      # model → matched key (approximate, no exact row)
    for c in calls:
        g = groups.setdefault(_key(c, dim), _new_group())
        g["calls"] += 1
        g["tokens_in"] += c.get("tokens_in", 0)
        g["tokens_out"] += c.get("tokens_out", 0)
        g["cached_in"] += c.get("cached_in", 0)
        usd, match, key = prices.call_usd_match(pol, c)
        g["usd"] += usd
        if match == "none":
            unpriced.add(f"{c.get('provider') or '—'}/{c.get('model') or '—'}")
        elif match == "family":
            family[c.get("model") or "—"] = key or "—"
    total = {"calls": sum(g["calls"] for g in groups.values()),
             "usd": sum(g["usd"] for g in groups.values()),
             "tokens_in": sum(g["tokens_in"] for g in groups.values()),
             "tokens_out": sum(g["tokens_out"] for g in groups.values())}
    if dim in SAVINGS_DIMS:  # second pass over receipts → saved + net (§3.1)
        total_saved = 0.0
        for r, call, saved in _nonhuman_savings(root, pol, since):
            key = str(r.get("task") or "—") if dim == "task" else str(call.get("agent") or "—")
            g = groups.setdefault(key, _new_group())  # receipt-only group (e.g. "—" bucket)
            g["saved_usd"] = g.get("saved_usd", 0.0) + saved
            total_saved += saved
        for g in groups.values():
            g.setdefault("saved_usd", 0.0)
            g["net_usd"] = g["saved_usd"] - g["usd"]
        total["saved_usd"] = total_saved
        total["net_usd"] = total_saved - total["usd"]
    return {"dim": dim, "since": since, "groups": groups, "total": total,
            "unpriced": sorted(unpriced), "family": family}


def overview(root: Path, pol: dict, since: str | None = None) -> dict:
    """The bare-`cage` headline: spent / saved / net / tokens over the window (§4)."""
    calls = ledger.since(ledger.calls(root), since)
    spent = sum(prices.call_usd(pol, c) for c in calls)
    tokens = sum(c.get("tokens_in", 0) + c.get("tokens_out", 0) for c in calls)
    saved = sum(s for _, _, s in _nonhuman_savings(root, pol, since))
    return {"since": since, "empty": not calls, "calls": len(calls),
            "spent_usd": spent, "saved_usd": saved, "net_usd": saved - spent,
            "tokens": tokens}


def _row(name: str, g: dict, savings: bool) -> list[str]:
    cells = [name, render.tok(g["calls"]), render.tok(g["tokens_in"]),
             render.tok(g["tokens_out"]), render.usd(g["usd"])]
    if savings:
        cells += [render.usd(g["saved_usd"]), render.signed_usd(g["net_usd"])]
    return cells


def render_report(rep: dict) -> str:
    if not rep["groups"]:
        return "cage: no calls recorded yet — meter some traffic first."
    savings = "saved_usd" in rep["total"]  # only task/agent attribute receipts (§3.1)
    rows = [_row(name, g, savings)
            for name, g in sorted(rep["groups"].items(), key=lambda kv: -kv[1]["usd"])]
    rows.append(_row("TOTAL", rep["total"], savings))
    head = [rep["dim"], "calls", "tok in", "tok out", "cost"]
    rights = {1, 2, 3, 4}
    if savings:
        head += ["saved", "net"]
        rights |= {5, 6}
    title = f"Ledger by {rep['dim']}" + (f" (since {rep['since']})" if rep["since"] else "")
    out = f"{title}\n\n" + render.table(head, rows, rights=rights)
    if rep.get("family"):
        approx = ", ".join(f"{m} → {k}" for m, k in sorted(rep["family"].items()))
        out += f"\n\n≈ priced by family (approximate — no exact price row): {approx}"
    if rep.get("unpriced"):
        out += ("\n\n⚠ UNPRICED — counted as $0; add a price row to policy.toml: "
                + ", ".join(rep["unpriced"]))
    return out


def render_overview(o: dict) -> str:
    if o["empty"]:
        return "cage: no calls recorded yet — meter some traffic first."
    win = f"({o['since']})" if o["since"] else "(all time)"
    head = (f"spent {render.usd(o['spent_usd'])}  ·  saved {render.usd(o['saved_usd'])}"
            f"  ·  net {render.signed_usd(o['net_usd'])}  ·  {render.tok(o['tokens'])} tokens"
            f"   {win}")
    drill = ("  drill:  cage report --by agent   ·   cage why <call>"
             "   ·   cage attrib --task <t>")
    return f"{head}\n{drill}"
