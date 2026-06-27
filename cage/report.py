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


def _team_rows(root: Path, team: bool):
    """`(calls, receipts)` from the merged `refs/notes/cage-ledger` ref when ``--team``
    and it's non-empty, else ``(None, None)`` ⇒ read the local ledger (plan §3.6.3).
    Fail-open: an empty/missing ref degrades to local, never an error."""
    if team:
        from cage import ledgersync
        t = ledgersync.read_team(root)
        if t is not None:
            return t["calls"], t["receipts"]
    return None, None


def _grouping_calls(root: Path, since: str | None, team_calls):
    """Window-filtered calls for the rollup. Local path keeps the partition shard-skip
    (`ledger.calls(..., since=...)`); team rows are a plain list filtered by `ledger.since`."""
    if team_calls is not None:
        return ledger.since(team_calls, since)
    return ledger.since(ledger.calls(root, since=since), since)


def _nonhuman_savings(all_calls: list[dict], receipts: list[dict], pol: dict,
                      scope: str | None = None):
    """Yield ``(receipt, call, saved_usd)`` for each non-human receipt (already window-
    filtered). ``all_calls`` is the *unfiltered* join table so an in-window receipt can
    still find its (possibly older) call.

    Tier-1 ``tool="human"`` receipts are a *different axis* (`cage human`); counting
    them here would double-count and mix axes — skip them, matching `roi.by_tool` (§4.4).
    USD comes only through the one unit→USD dispatch (`convert.saved_usd`). With ``scope``
    set, only receipts in that top-level dir count (plan §3.6.2).
    """
    by_id = {c.get("id"): c for c in all_calls}
    for r in ledger.by_scope(receipts, scope):
        if r.get("tool") == "human":
            continue
        call = by_id.get(r.get("call"), {})
        yield r, call, convert.saved_usd(r, call, pol)


def summarize(root: Path, pol: dict, dim: str = "route", since: str | None = None,
              scope: str | None = None, project: str | None = None,
              team: bool = False) -> dict:
    tc, tr = _team_rows(root, team)
    all_calls = ledger.by_project(tc if tc is not None else ledger.calls(root), project)
    windowed_receipts = (ledger.since(tr, since) if tr is not None
                         else ledger.since(ledger.receipts(root, since=since), since))
    calls = ledger.by_project(ledger.by_scope(_grouping_calls(root, since, tc), scope), project)
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
        for r, call, saved in _nonhuman_savings(all_calls, windowed_receipts, pol, scope):
            key = str(r.get("task") or "—") if dim == "task" else str(call.get("agent") or "—")
            g = groups.setdefault(key, _new_group())  # receipt-only group (e.g. "—" bucket)
            g["saved_usd"] = g.get("saved_usd", 0.0) + saved
            total_saved += saved
        for g in groups.values():
            g.setdefault("saved_usd", 0.0)
            g["net_usd"] = g["saved_usd"] - g["usd"]
        total["saved_usd"] = total_saved
        total["net_usd"] = total_saved - total["usd"]
    return {"dim": dim, "since": since, "project": project, "groups": groups,
            "total": total, "unpriced": sorted(unpriced), "family": family}


def _last_import_line(last_import: str | None) -> str:
    """The pull-based capture staleness nudge (plan §3.7). Capture only happens on
    `cage import`/`cage watch`/your own cron — nothing runs in the background — so surface
    when the ledger was last refreshed and nudge if it never has been."""
    if not last_import:
        return ("· no import recorded yet — capture is pull-based: run `cage import` "
                "(or `cage watch`) to meter your agents.")
    rel = render.ago(last_import)
    return f"· last import: {rel} — `cage import` to refresh." if rel else ""


def overview(root: Path, pol: dict, since: str | None = None) -> dict:
    """The bare-`cage` headline: spent / saved / net / tokens over the window (§4)."""
    calls = ledger.since(ledger.calls(root, since=since), since)
    spent = sum(prices.call_usd(pol, c) for c in calls)
    tokens = sum(c.get("tokens_in", 0) + c.get("tokens_out", 0) for c in calls)
    saved = sum(s for _, _, s in _nonhuman_savings(
        ledger.calls(root), ledger.since(ledger.receipts(root, since=since), since), pol))
    return {"since": since, "empty": not calls, "calls": len(calls),
            "spent_usd": spent, "saved_usd": saved, "net_usd": saved - spent,
            "tokens": tokens}


def _row(name: str, g: dict, savings: bool) -> list[str]:
    cells = [name, render.tok(g["calls"]), render.tok(g["tokens_in"]),
             render.tok(g["tokens_out"]), render.usd(g["usd"])]
    if savings:
        cells += [render.usd(g["saved_usd"]), render.signed_usd(g["net_usd"])]
    return cells


def render_report(rep: dict, last_import: str | None = None) -> str:
    if not rep["groups"]:
        nudge = _last_import_line(last_import)
        base = "cage: no calls recorded yet — meter some traffic first."
        return f"{base}\n{nudge}" if nudge else base
    savings = "saved_usd" in rep["total"]  # only task/agent attribute receipts (§3.1)
    rows = [_row(name, g, savings)
            for name, g in sorted(rep["groups"].items(), key=lambda kv: -kv[1]["usd"])]
    rows.append(_row("TOTAL", rep["total"], savings))
    head = [rep["dim"], "calls", "tok in", "tok out", "cost"]
    rights = {1, 2, 3, 4}
    if savings:
        head += ["saved", "net"]
        rights |= {5, 6}
    title = f"Ledger by {rep['dim']}"
    if rep.get("project"):
        title += f" · project {rep['project']}"
    if rep["since"]:
        title += f" (since {rep['since']})"
    out = f"{title}\n\n" + render.table(head, rows, rights=rights)
    if rep.get("project"):
        out += ("\n\n· project view is exact for Claude only — Copilot/Kiro/Codex logs "
                "carry no project, so their spend is excluded from this filter.")
    if rep.get("family"):
        approx = ", ".join(f"{m} → {k}" for m, k in sorted(rep["family"].items()))
        out += f"\n\n≈ priced by family (approximate — no exact price row): {approx}"
    if rep.get("unpriced"):
        out += ("\n\n⚠ UNPRICED — counted as $0; add a price row to policy.toml: "
                + ", ".join(rep["unpriced"]))
    line = _last_import_line(last_import)
    if line:
        out += f"\n\n{line}"
    return out


def render_overview(o: dict, last_import: str | None = None) -> str:
    if o["empty"]:
        nudge = _last_import_line(last_import)
        base = "cage: no calls recorded yet — meter some traffic first."
        return f"{base}\n{nudge}" if nudge else base
    win = f"({o['since']})" if o["since"] else "(all time)"
    head = (f"spent {render.usd(o['spent_usd'])}  ·  saved {render.usd(o['saved_usd'])}"
            f"  ·  net {render.signed_usd(o['net_usd'])}  ·  {render.tok(o['tokens'])} tokens"
            f"   {win}")
    drill = ("  drill:  cage report --by agent   ·   cage why <call>"
             "   ·   cage attrib --task <t>")
    return f"{head}\n{drill}"
