"""`cage report` — the ledger rollup: spend by agent / route / model / day (plan §7).

Any meter does this; it's the honest floor the rest of Cage builds on. Pure
aggregation over `calls.jsonl`, grouped on whichever dimension you ask for.
"""
from __future__ import annotations

from pathlib import Path

from cage import convert, ledger, paths, prices, render

DIMENSIONS = ("route", "agent", "model", "provider", "day", "task")
SAVINGS_DIMS = ("task", "agent")  # dims a receipt joins cleanly to (§3.1); others fuzzy


def _key(call: dict, dim: str) -> str:
    if dim == "day":
        return (call.get("ts") or "")[:10] or "—"
    return str(call.get(dim) or "—")


def _new_group() -> dict:
    # unpriced_* ride in the same pass as the totals (one structure feeds text AND
    # csv — plan §3.9): the text view warns from `unpriced_detail`; the CSV shows
    # the same gap per group so a spreadsheet can't publish an understated total.
    return {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cached_in": 0, "usd": 0.0,
            "unpriced_calls": 0, "unpriced_tokens": 0}


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


def read_receipts(root: Path, pol: dict, since: str | None = None) -> list[dict]:
    """Receipts for a read, with the **routing-key reclaim backstop** folded in
    (capture-architecture §3.1b, §9.6). A pushed graphify/fux saving can land in the
    global ``~/.cage`` when the tool ran *outside* this project's tree; a project read
    then reclaims it — but **only** the global receipts whose ``route_key`` *exactly*
    equals this project's key (`paths.routing_key`), merged by row id. Never a blind
    global→project union (two repos sharing a basename would over-attribute). Skipped
    entirely — byte-identical to the legacy read — when this read already *is* the global
    ledger or a ``--ledger``/``CAGE_BASE`` override (push and pull then share one sink, so
    nothing can strand). Fail-open: an unreadable global ledger degrades to local only."""
    local = ledger.receipts(root, since=since)
    try:
        import os
        if os.environ.get("CAGE_BASE"):
            return local  # explicit override — one shared sink, nothing to reclaim
        gbase = paths.global_home()
        if paths.Footprint(root).base.resolve() == paths.Footprint(gbase).base.resolve():
            return local  # this read already IS the global ledger
        key = paths.routing_key(root)
        extra = [r for r in ledger.receipts(gbase, since=since)
                 if r.get("route_key") == key]
        if not extra:
            return local
        from cage import debuglog, mergeutil
        merged = mergeutil.union_by_id(local, extra)
        debuglog.event(root, pol=pol, event="reclaim", route_key=key,
                       reclaimed=len(merged) - len(local),
                       source=str(paths.Footprint(gbase).base))
        return merged
    except Exception as e:  # fail-open: reclaim is a backstop, never blocks a read
        from cage import debuglog
        debuglog.exception(root, "report.reclaim", e, pol=pol)
        return local


def _grouping_calls(root: Path, since: str | None, team_calls):
    """Window-filtered calls for the rollup. Local path keeps the partition shard-skip
    (`ledger.calls(..., since=...)`); team rows are a plain list filtered by `ledger.since`."""
    if team_calls is not None:
        return ledger.since(team_calls, since)
    return ledger.since(ledger.calls(root, since=since), since)


def _nonhuman_savings(all_calls: list[dict], receipts: list[dict], pol: dict,
                      scope: str | None = None):
    """Yield ``(receipt, call, saved_usd, rung, model_key)`` per non-human receipt
    (already window-filtered). ``all_calls`` is the *unfiltered* join table so an
    in-window receipt can still find its (possibly older) call.

    Tier-1 ``tool="human"`` receipts are a *different axis* (`cage human show`); counting
    them here would double-count and mix axes — skip them, matching `roi.by_tool` (§4.4).
    USD comes only through the one unit→USD dispatch (`convert.saved_usd`); a call-less
    token receipt prices via the resolution ladder (`receiptprice`, plan §4.5) —
    ``rung`` names its path (``"unpriced"`` when rung 3 refused; ``""`` off-ladder)
    and ``model_key`` the resolved ``provider/model`` (`""` off-ladder or refused).
    With ``scope`` set, only receipts in that top-level dir count (plan §3.6.2).
    """
    from cage import receiptprice
    by_id = {c.get("id"): c for c in all_calls}
    idx = receiptprice.build(all_calls, receipts)  # once per view, never per receipt
    for r in ledger.by_scope(receipts, scope):
        if r.get("tool") == "human":
            continue
        call = by_id.get(r.get("call"), {})
        if receiptprice.eligible(r, by_id):
            res = receiptprice.resolve(r, idx, pol)
            yield (r, call, (res[0] if res else 0.0),
                   (res[1] if res else "unpriced"), (res[2] if res else ""))
        else:
            yield r, call, convert.saved_usd(r, call, pol), "", ""


def summarize(root: Path, pol: dict, dim: str = "route", since: str | None = None,
              scope: str | None = None, project: str | None = None,
              team: bool = False) -> dict:
    tc, tr = _team_rows(root, team)
    raw_calls = tc if tc is not None else ledger.calls(root)
    all_calls = ledger.by_project(raw_calls, project)
    windowed_receipts = (ledger.since(tr, since) if tr is not None
                         else ledger.since(read_receipts(root, pol, since=since), since))
    calls = ledger.by_project(ledger.by_scope(_grouping_calls(root, since, tc), scope), project)
    groups: dict[str, dict] = {}
    unpriced: dict[str, dict] = {}   # provider/model that billed $0 → calls/tokens
    family: dict[str, str] = {}      # model → matched key (approximate, no exact row)
    alias: dict[str, str] = {}       # model → routed prov/model (explicit [alias] row)
    kiro = {"calls": 0, "tokens_in": 0, "tokens_out": 0}  # input-only-log caveat (Phase 1.5)
    for c in calls:
        g = groups.setdefault(_key(c, dim), _new_group())
        g["calls"] += 1
        g["tokens_in"] += c.get("tokens_in", 0)
        g["tokens_out"] += c.get("tokens_out", 0)
        g["cached_in"] += c.get("cached_in", 0)
        g.setdefault("agents", set()).add(c.get("agent") or "lib")
        if c.get("agent") == "kiro":
            kiro["calls"] += 1
            kiro["tokens_in"] += c.get("tokens_in", 0)
            kiro["tokens_out"] += c.get("tokens_out", 0)
        usd, match, key = prices.call_usd_match(pol, c)
        g["usd"] += usd
        if match == "none":
            u = unpriced.setdefault(f"{c.get('provider') or '—'}/{c.get('model') or '—'}",
                                    {"calls": 0, "tokens": 0,
                                     "provider": c.get("provider") or "",
                                     "model": c.get("model") or ""})
            u["calls"] += 1
            u["tokens"] += c.get("tokens_in", 0) + c.get("tokens_out", 0)
            g["unpriced_calls"] += 1
            g["unpriced_tokens"] += c.get("tokens_in", 0) + c.get("tokens_out", 0)
        elif match == "family":
            family[c.get("model") or "—"] = key or "—"
        elif match == "alias":
            alias[c.get("model") or "—"] = key or "—"
    total = {"calls": sum(g["calls"] for g in groups.values()),
             "usd": sum(g["usd"] for g in groups.values()),
             "tokens_in": sum(g["tokens_in"] for g in groups.values()),
             "tokens_out": sum(g["tokens_out"] for g in groups.values()),
             "cached_in": sum(g["cached_in"] for g in groups.values()),
             "unpriced_calls": sum(g["unpriced_calls"] for g in groups.values()),
             "unpriced_tokens": sum(g["unpriced_tokens"] for g in groups.values())}
    unpriced_receipts = {"receipts": 0, "tokens": 0, "tools": set()}  # rung-3 refusals (§4.5)
    rung_models: set[tuple[str, str, str]] = set()  # (rung, tool, model) → usd-view footnotes
    if dim in SAVINGS_DIMS:  # second pass over receipts → saved + net (§3.1)
        total_saved = 0.0
        for r, call, saved, rung, model_key in _nonhuman_savings(
                all_calls, windowed_receipts, pol, scope):
            key = str(r.get("task") or "—") if dim == "task" else str(call.get("agent") or "—")
            g = groups.setdefault(key, _new_group())  # receipt-only group (e.g. "—" bucket)
            g["saved_usd"] = g.get("saved_usd", 0.0) + saved
            if r.get("unit", "tokens") == "tokens":  # tokens measure regardless of pricing
                g["saved_tokens"] = g.get("saved_tokens", 0) + int(r.get("saved", 0.0))
            total_saved += saved
            if rung == "unpriced":
                g["unpriced_saved_tokens"] = (g.get("unpriced_saved_tokens", 0)
                                              + int(r.get("saved", 0.0)))
                unpriced_receipts["receipts"] += 1
                unpriced_receipts["tokens"] += int(r.get("saved", 0.0))
                unpriced_receipts["tools"].add(r.get("tool", ""))
            elif model_key:
                rung_models.add((rung, r.get("tool", ""), model_key))
        for g in groups.values():
            g.setdefault("saved_usd", 0.0)
            g.setdefault("saved_tokens", 0)
            g.setdefault("unpriced_saved_tokens", 0)
            g["net_usd"] = g["saved_usd"] - g["usd"]
        total["saved_usd"] = total_saved
        total["net_usd"] = total_saved - total["usd"]
        total["saved_tokens"] = sum(g["saved_tokens"] for g in groups.values())
        total["unpriced_saved_tokens"] = sum(g["unpriced_saved_tokens"] for g in groups.values())
    unpriced_receipts["tools"] = sorted(unpriced_receipts["tools"])
    for g in groups.values():  # sets → sorted lists (JSON-safe payload, one structure)
        g["agents"] = sorted(g.get("agents") or [])
    # Pricing-freshness footer lines (plan §3.3): data-relative (today=None ⇒
    # anchored on the newest ledger ts, never the wall clock — derived views stay
    # deterministic), over the same team-aware rows the table renders. UNPRICED is
    # excluded here because render_report prints those exact lines natively.
    from cage import freshness
    fresh = freshness.freshness(root, pol, include_unpriced=False, rows=all_calls)
    return {"dim": dim, "since": since, "project": project, "scope": scope,
            "groups": groups,
            "total": total, "unpriced": sorted(unpriced), "family": family,
            "alias": alias, "unpriced_detail": dict(sorted(unpriced.items())),
            "unpriced_receipts": unpriced_receipts, "freshness": fresh,
            "rung_models": sorted(rung_models),
            "has_receipts": any(r.get("tool") != "human"
                                for r in ledger.by_scope(windowed_receipts, scope)),
            "kiro_input_only": bool(kiro["calls"] and kiro["tokens_in"]
                                    and not kiro["tokens_out"]),
            "any_calls": bool(raw_calls)}


def unpriced_line(detail: dict) -> str:
    """The one-line UNPRICED warning every read surface prints the same way
    (report/compare/study): a fleet analyst must see the gap before publishing a
    total. ``detail`` is ``{key: {"calls": n, "tokens": n}}``."""
    calls = sum(d["calls"] for d in detail.values())
    tokens = sum(d["tokens"] for d in detail.values())
    return (f"⚠ {calls} calls ({render.tok(tokens)} tokens) UNPRICED — totals "
            f"understated; run 'cage prices unpriced' (`cage query unpriced` explains)")


def _last_import_line(last_import: str | None, stale_hours: int | None = None) -> str:
    """The pull-based capture staleness nudge (plan §3.7), now **staleness-gated**
    (plan Phase 1.6): it's advice, not a banner, so it renders only when the last
    import is older than ``stale_hours`` (policy `[capture] import_stale_hours`,
    `constants.IMPORT_STALE_HOURS` fallback; ``0`` restores always-on). Never
    imported at all stays ungated — that state is always actionable."""
    if not last_import:
        return ("· no import recorded yet — capture is pull-based: run `cage import` "
                "(or `cage data watch`) to meter your agents.")
    if stale_hours is None:
        from cage.constants import IMPORT_STALE_HOURS
        stale_hours = IMPORT_STALE_HOURS
    secs = render.age_seconds(last_import)
    if secs is None or (stale_hours > 0 and secs < stale_hours * 3600):
        return ""
    rel = render.ago(last_import)
    return f"· last import: {rel} — `cage import` to refresh" if rel else ""


def capture_warnings(health: dict | None) -> list[str]:
    """The triple-gated "installed but capturing nothing" warnings (docs/capture-health):
    warn for an agent only when its home marker exists **and** it matched 0 files at the
    last import **and** it has never contributed a row to the ledger. Clause 3 makes the
    warning self-silencing — one captured row and it can never fire again. **Pure**: reads
    only the passed-in ``_health`` record (`importcmd.capture_health`), never the
    filesystem — so `render_report`/`cage doctor` share one verdict. One ⚠ block per gated
    agent, in SURFACES order, each carrying a runnable fix (`cage doctor --paths`) and the
    documented opt-out for an agent you don't use."""
    from cage import agents
    out: list[str] = []
    for a in agents.SURFACES:
        rec = (health or {}).get(a)
        if not isinstance(rec, dict):
            continue
        if rec.get("home") and rec.get("files", 0) == 0 and not rec.get("captured"):
            home_path = rec.get("home_path") or f"~/.{a}"
            src = rec.get("src") or "its log location"
            out.append(
                f"⚠ {a}: {home_path} exists but {src} matched 0 files — capture is off "
                f"for this agent.\n"
                f"  cage doctor --paths      (if you don't use {a}: "
                f"[sources.{a}] replace=true, paths=[] )")
    return out


_EMPTY = """No calls recorded yet.

next: cage import        pull every agent's usage into the ledger
      cage doctor        check capture is wired and healthy"""


def _render_empty(rep: dict) -> str:
    """The no-rows rendering: a truly empty ledger gets the onboarding next-steps
    (spec R5); an empty *slice* of a non-empty ledger names the active filters
    instead — the filter is empty, not the ledger (papercut rider, plan §5.3)."""
    filters = []
    if rep.get("scope"):
        filters.append(f"scope '{rep['scope']}'")
    if rep.get("project"):
        filters.append(f"project '{rep['project']}'")
    if rep.get("since"):
        filters.append(f"since {rep['since']}")
    if rep.get("any_calls") and filters:
        return (f"No calls match {' · '.join(filters)} — the filter is empty, "
                "not the ledger.\n\n"
                "next: cage report                 the unfiltered view\n"
                "      cage report --by agent      where the rows are")
    return _EMPTY


def _unpriced_block(detail: dict) -> str:
    """The `--usd` view's ⚠ UNPRICED block (spec R4): counts headline + one
    **runnable** fix line per unpriced provider/model (the one fix-line builder,
    `pricescmd.fix_line` — reused, never re-phrased). ``detail`` rows lacking the
    provider/model split (legacy payloads) fall back to the `cage prices
    unpriced` pointer."""
    from cage import pricescmd
    calls = sum(d["calls"] for d in detail.values())
    tokens = sum(d["tokens"] for d in detail.values())
    head = f"⚠ {calls} calls ({render.tok(tokens)} tokens) UNPRICED — totals understated"
    fixes = []
    for d in detail.values():
        if "provider" in d or "model" in d:
            fixes.append(f"  fix: {pricescmd.fix_line(d.get('provider', ''), d.get('model', ''))}")
        else:
            fixes.append("  run: cage prices unpriced   # per-model fix lines")
    return "\n".join([head, *dict.fromkeys(fixes)])


def overview(root: Path, pol: dict, since: str | None = None) -> dict:
    """The bare-`cage` headline: spent / saved / net / tokens over the window (§4)."""
    calls = ledger.since(ledger.calls(root, since=since), since)
    spent, unpriced_calls, unpriced_tokens = 0.0, 0, 0
    for c in calls:
        usd, match, _ = prices.call_usd_match(pol, c)
        spent += usd
        if match == "none":
            unpriced_calls += 1
            unpriced_tokens += c.get("tokens_in", 0) + c.get("tokens_out", 0)
    tokens = sum(c.get("tokens_in", 0) + c.get("tokens_out", 0) for c in calls)
    rcpts = ledger.since(read_receipts(root, pol, since=since), since)
    saved = sum(s for _, _, s, _, _ in _nonhuman_savings(ledger.calls(root), rcpts, pol))
    return {"since": since, "empty": not calls, "calls": len(calls),
            "spent_usd": spent, "saved_usd": saved, "net_usd": saved - spent,
            "tokens": tokens, "unpriced_calls": unpriced_calls,
            "unpriced_tokens": unpriced_tokens,
            "has_receipts": any(r.get("tool") != "human" for r in rcpts)}


def _cost_cell(g: dict, total: bool = False) -> str:
    """`—` is the only rendering of "couldn't price" — a group whose every call
    refused to price shows the dash, never `$0.0000` (a self-costed est fallback
    keeps its real figure). A TOTAL over a partial gap says so inline."""
    from cage.display import DASH
    if g.get("unpriced_calls") and g["unpriced_calls"] == g["calls"] and not g["usd"]:
        return DASH
    cell = render.usd(g["usd"])
    if total and g.get("unpriced_calls"):
        cell += " (+ unpriced)"
    return cell


def _saved_cells(g: dict, cost_dashed: bool) -> list[str]:
    """saved/net cells: a group whose only savings signal refused to price is a
    `—`, never a `$0.0000` that reads as "measured nothing" — and net is
    unknowable whenever the cost itself couldn't price."""
    from cage.display import DASH
    if g.get("unpriced_saved_tokens") and not g.get("saved_usd"):
        return [DASH, DASH]
    saved = render.usd(g["saved_usd"])
    return [saved, DASH if cost_dashed else render.signed_usd(g["net_usd"])]


def _display_name(name: str, g: dict, dim: str) -> str:
    """A generic bucket name (`agent`, `—`) says which agent it came from when
    exactly one did — `agent (kiro)` reads; bare `agent` doesn't (spec R4)."""
    agents = g.get("agents") or []
    if dim == "model" and name in ("agent", "—") and len(agents) == 1:
        return f"{name} ({agents[0]})"
    return name


def _row(name: str, g: dict, savings_cols: bool, usd_view: bool, total: bool = False) -> list[str]:
    cells = [name, render.tok(g["calls"]), render.tok(g["tokens_in"]),
             render.tok(g["tokens_out"])]
    if not usd_view and savings_cols:
        cells.append(render.tok(g.get("saved_tokens", 0)))
    if usd_view:
        cost = _cost_cell(g, total=total)
        cells.append(cost)
        if savings_cols:
            from cage.display import DASH
            cells += _saved_cells(g, cost_dashed=cost == DASH)
    return cells


def render_report(rep: dict, last_import: str | None = None, disp=None,
                  stale_hours: int | None = None, health: dict | None = None) -> str:
    """The text report (spec §1, R1–R6): tokens by default, dollars on ``disp.usd``
    (plan Phase 2.5); saved columns signal-gate on receipts-in-window
    (``disp.all_columns`` restores the full grid); pricing footnotes and the full
    ⚠ block belong to the `--usd` view; footer lines dedupe into one
    fixed-order block (`display.Footer`). CSV is untouched by all of it.

    ``health`` is the per-agent capture-health record (`importcmd.capture_health`, read
    at the CLI boundary and passed in — this function stays a **pure** function of its
    args): a triple-gated "installed but capturing nothing" ⚠ per silent agent
    (:func:`capture_warnings`). Never enters CSV."""
    from cage import display as _d
    disp = disp or _d.DEFAULT
    if not rep["groups"]:
        return _render_empty(rep)
    savings = "saved_usd" in rep["total"]  # only task/agent attribute receipts (§3.1)
    savings_cols = savings and (rep.get("has_receipts", True) or disp.all_columns)
    rows = [_row(_display_name(name, g, rep["dim"]), g, savings_cols, disp.usd)
            for name, g in sorted(rep["groups"].items(), key=lambda kv: -kv[1]["usd"])
            if g["calls"]]  # 0-call receipt-only buckets never render (Phase 1.3)
    rows.append(_row("TOTAL", rep["total"], savings_cols, disp.usd, total=True))
    head = [rep["dim"], "calls", "tok in", "tok out"]
    if not disp.usd and savings_cols:
        head.append("saved tok")
    if disp.usd:
        head.append("cost")
        if savings_cols:
            head += ["saved", "net"]
    title = f"Ledger by {rep['dim']}"
    if rep.get("project"):
        title += f" · project {rep['project']}"
    if rep["since"]:
        title += f" · since {rep['since']}"
    if disp.usd:
        title += " · usd"
    out = f"{title}\n\n" + render.table(head, rows, rights=set(range(1, len(head))))
    foot = _d.Footer()
    if disp.usd:
        from cage import receiptprice
        if rep.get("family"):
            foot.footnote("≈ priced by family (approximate — no exact price row):\n"
                          + "\n".join(f"  {m} → {k}"
                                      for m, k in sorted(rep["family"].items())))
        if rep.get("alias"):
            foot.footnote("≈ priced by alias (explicit routing — policy [alias]):\n"
                          + "\n".join(f"  {m} → {k}"
                                      for m, k in sorted(rep["alias"].items())))
        for rung, tool, key in rep.get("rung_models", []):
            foot.footnote(receiptprice.footnote(rung, tool, key))
    if rep.get("kiro_input_only"):
        foot.caveat("· kiro: input-only log — cost understated" if disp.usd
                    else "· kiro: input-only log — tok out not recorded")
    if rep.get("project"):
        foot.caveat("· project view is exact for Claude only — Copilot/Kiro/Codex logs "
                    "carry no project, so their spend is excluded from this filter.")
    if disp.usd:
        from cage import receiptprice
        if rep.get("unpriced_detail"):
            foot.warn(_unpriced_block(rep["unpriced_detail"]))
        if rep.get("unpriced_receipts", {}).get("receipts"):
            foot.warn(receiptprice.unpriced_receipts_line(rep["unpriced_receipts"]))
    if savings and not rep.get("has_receipts", True):
        foot.gap("· no savings receipts in this window — wire a tool to measure savings\n"
                 "  (`cage query receipts` explains)")
    if not disp.usd and rep["total"].get("unpriced_calls"):
        n = rep["total"]["unpriced_calls"]
        foot.gap(f"· {n} call{'s' if n != 1 else ''} unpriced — matters when you "
                 f"view $ (`--usd`; cage prices unpriced)")
    for w in capture_warnings(health):  # installed-but-capturing-nothing (docs/capture-health)
        foot.warn(w)
    foot.advice(_last_import_line(last_import, stale_hours))
    for l in rep.get("freshness") or []:  # actionable-only — silent when clean (§3.3)
        if l.startswith("bundled prices are"):
            foot.advice(f"· {l}\n  (`cage query prices-freshness` explains)")
        else:
            foot.advice(f"· {l}")
    tail = foot.render()
    return f"{out}\n\n{tail}" if tail else out


def render_csv(rep: dict) -> str:
    """CSV over the same `summarize()` payload the text table renders — one
    structure, two renderers (they cannot disagree). Rows sort like the text view
    (spend-descending) + a TOTAL row. Raw numbers, not $-formatted strings; the
    per-group UNPRICED gap keeps the understatement visible in a spreadsheet.
    `method` column: measured — recorded tokens repriced at derive time (the
    `repricing` query entry); spend is never a projection. Column contract in
    docs/csv-output.md."""
    from cage import csvout
    savings = "saved_usd" in rep["total"]
    head = [rep["dim"], "calls", "tokens_in", "tokens_out", "cached_in", "cost_usd",
            *(("saved_usd", "net_usd") if savings else ()),
            "unpriced_calls", "unpriced_tokens", "method"]
    def cells(name, g):
        return [name, g["calls"], g["tokens_in"], g["tokens_out"], g["cached_in"],
                round(g["usd"], 6),
                *((round(g["saved_usd"], 6), round(g["net_usd"], 6)) if savings else ()),
                g["unpriced_calls"], g["unpriced_tokens"], "measured"]
    rows = [cells(name, g)
            for name, g in sorted(rep["groups"].items(), key=lambda kv: -kv[1]["usd"])]
    rows.append(cells("TOTAL", rep["total"]))
    return csvout.table(head, rows)


def render_overview(o: dict, last_import: str | None = None, disp=None) -> str:
    """The bare-`cage` headline — same display rules as the report (handoff §10:
    tokens by default, `--usd`/`[display] usd` for currency; saved/net gate on
    receipts existing in the window)."""
    from cage import display as _d
    disp = disp or _d.DEFAULT
    if o["empty"]:
        return _EMPTY
    win = f"({o['since']})" if o["since"] else "(all time)"
    if not disp.usd:
        head = f"{render.tok(o['tokens'])} tokens  ·  {o['calls']} calls   {win}"
    elif o.get("has_receipts", True):
        head = (f"spent {render.usd(o['spent_usd'])}  ·  saved {render.usd(o['saved_usd'])}"
                f"  ·  net {render.signed_usd(o['net_usd'])}  ·  {render.tok(o['tokens'])} tokens"
                f"   {win}")
    else:
        head = (f"spent {render.usd(o['spent_usd'])}  ·  {render.tok(o['tokens'])} tokens"
                f"   {win}")
    drill = ("  drill:  cage report --by agent   ·   cage insights why <call>"
             "   ·   cage insights attrib --task <t>")
    out = f"{head}\n{drill}"
    foot = _d.Footer()
    if o.get("unpriced_calls"):
        if disp.usd:
            foot.warn(unpriced_line({"_": {"calls": o["unpriced_calls"],
                                           "tokens": o["unpriced_tokens"]}}))
        else:
            n = o["unpriced_calls"]
            foot.gap(f"· {n} call{'s' if n != 1 else ''} unpriced — matters when you "
                     f"view $ (`--usd`; cage prices unpriced)")
    if disp.usd and not o.get("has_receipts", True):
        foot.gap("· no savings receipts in this window — wire a tool to measure savings\n"
                 "  (`cage query receipts` explains)")
    tail = foot.render()
    return f"{out}\n{tail}" if tail else out
