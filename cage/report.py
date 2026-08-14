"""`cage report` — the ledger rollup: spend by agent / route / model / day (plan §7).

Any meter does this; it's the honest floor the rest of Cage builds on. Pure
aggregation over `calls.jsonl`, grouped on whichever dimension you ask for.
"""
from __future__ import annotations

from pathlib import Path

from cage import ledger, paths, policy, render, units
from cage.constants import TOKENS_PER_MILLION

DIMENSIONS = ("route", "agent", "model", "provider", "day", "task")
SAVINGS_DIMS = ("task", "agent")  # dims a receipt joins cleanly to (§3.1); others fuzzy


def _key(call: dict, dim: str) -> str:
    if dim == "day":
        return (call.get("ts") or "")[:10] or "—"
    return str(call.get(dim) or "—")


def _new_group() -> dict:
    # `credits` starts at None, not 0.0 — the absent-vs-recorded-zero distinction
    # every credits field in cage carries (REPORT-CREDITS, matching `chats.py`'s
    # `_new_bucket`). A group no `ledger.credits` row ever joined stays None and
    # renders `—`; one that joined a recorded `0.0` renders `0.00` — different facts.
    return {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cached_in": 0,
            "credits": None}


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
    return ledger.since(ledger.spend(root, since=since), since)


def _is_legacy_human(r: dict) -> bool:
    """A pre-0.36 Tier-1 row: the removed human axis's tool, or its removed unit.
    The ONE predicate every money view shares — see `_nonhuman_savings`."""
    return r.get("tool") == "human" or r.get("unit") == "minutes"


def _nonhuman_savings(all_calls: list[dict], receipts: list[dict], pol: dict,
                      scope: str | None = None):
    """Yield ``(receipt, call)`` per non-human receipt (already window-filtered).
    ``all_calls`` is the *unfiltered* join table so an in-window receipt can still find
    its (possibly older) call — that join is what attributes a saving to an agent.

    **Legacy Tier-1 rows are excluded, never counted.** The agent-vs-human axis was
    removed in v0.36, but ledgers are append-only: a pre-0.36 ``tool="human"`` receipt
    (and any ``unit="minutes"`` row) belongs to no surviving axis. Skipping it here is a
    *decision*, so it is COUNTED and footnoted (``legacy_human`` below) rather than
    silently dropped — `cage query savings-axis` explains it.

    The USD half of this generator — `convert.saved_usd` and the `receiptprice` ladder
    that priced a call-less token receipt — went with the money subsystem (USAGE-ONLY,
    ADR 0011). Savings are token-denominated and the join is unchanged.

    With ``scope`` set, only receipts in that top-level dir count (plan §3.6.2)."""
    by_id = {c.get("id"): c for c in all_calls}
    for r in ledger.by_scope(receipts, scope):
        if _is_legacy_human(r):
            continue
        yield r, by_id.get(r.get("call"), {})


def summarize(root: Path, pol: dict, dim: str = "route", since: str | None = None,
              scope: str | None = None, project: str | None = None,
              team: bool = False) -> dict:
    tc, tr = _team_rows(root, team)
    # The receipt-JOIN table (`_nonhuman_savings` line ~274 + freshness), never the sum
    # source — group totals come from `_grouping_calls` below, which reads `spend()` and
    # holds each row exactly once. `join_table` adds back the `calls` rows the cutover
    # superseded, so a receipt written with `call=<calls-row id>` still resolves to its
    # agent instead of silently falling into the unattributed bucket (METRICS-PRIMARY P4).
    raw_calls = tc if tc is not None else ledger.join_table(root)
    all_calls = ledger.by_project(raw_calls, project)
    windowed_receipts = (ledger.since(tr, since) if tr is not None
                         else ledger.since(read_receipts(root, pol, since=since), since))
    calls = ledger.by_project(ledger.by_scope(_grouping_calls(root, since, tc), scope), project)
    groups: dict[str, dict] = {}
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
        # A call row may carry the provider's own billed `credits` figure. It is summed
        # as a COUNT, never priced (USAGE-ONLY, ADR 0011), and the None sentinel is
        # preserved — absent and a recorded 0.0 are different billing facts.
        rec = c.get("credits")
        if rec is not None and not isinstance(rec, bool) and isinstance(rec, (int, float)):
            g["credits"] = (g["credits"] or 0.0) + float(rec)
    # REPORT-CREDITS: `ledger.credits` (kiro-CLI conversations — no call, no tokens)
    # folds into the SAME `groups` dict as calls, on the two dims where a credits row
    # has a clean, non-colliding key: `agent` (its own field) and the default `route`
    # view (a synthetic "credits" bucket — a credits row carries no `route` at all, and
    # bucketing it into the "—" catch-all would blend it with unrelated legacy rows).
    # Every other dim (model/provider/day/task) is deliberately untouched — a credits
    # row doesn't carry those fields cleanly, and CHATS-CREDITS already covers the
    # per-conversation view (`cage insights chats`). Never folded into `tokens_*`:
    # a group's `credits` is its own field, read only by its own column — and since
    # USAGE-ONLY (ADR 0011) it is a COUNT, never priced.
    if dim in ("route", "agent"):
        raw_credits = ledger.credits(root)
        credit_rows = ledger.by_project(ledger.by_scope(
            (ledger.since(ledger.credits(root, since=since), since)
             if since else raw_credits), scope), project)
        for cr in credit_rows:
            key = _key(cr, "agent") if dim == "agent" else "credits"
            g = groups.setdefault(key, _new_group())
            g.setdefault("agents", set()).add(cr.get("agent") or "lib")
            cr_val = cr.get("credits")
            if isinstance(cr_val, bool) or not isinstance(cr_val, (int, float)):
                continue
            g["credits"] = (g["credits"] or 0.0) + float(cr_val)
    # THE CROSS-AGENT CREDIT LAW (`units.summable`): a total is formed only when every
    # credit in view belongs to ONE agent. Copilot credits are GitHub's tokens×rates
    # figure and kiro credits are AWS credits — summing them would invent a unit. When
    # they span agents the total is `None` and the view says why, exactly as it does for
    # an agent that records no credits at all; a `0` is never substituted for either.
    _credit_agents = {a for g in groups.values() if g["credits"] is not None
                      for a in (g.get("agents") or [])}
    _credits_summable = units.summable(units.CREDITS, _credit_agents)
    total = {"calls": sum(g["calls"] for g in groups.values()),
             "tokens_in": sum(g["tokens_in"] for g in groups.values()),
             "tokens_out": sum(g["tokens_out"] for g in groups.values()),
             "cached_in": sum(g["cached_in"] for g in groups.values()),
             "credits": (sum(g["credits"] or 0.0 for g in groups.values())
                        if (_credits_summable
                            and any(g["credits"] is not None for g in groups.values()))
                        else None),
             "credits_agents": sorted(_credit_agents),
             "credits_summable": _credits_summable}
    if dim in SAVINGS_DIMS:  # second pass over receipts → gross saved tokens (§3.1)
        for r, call in _nonhuman_savings(all_calls, windowed_receipts, pol, scope):
            key = str(r.get("task") or "—") if dim == "task" else str(call.get("agent") or "—")
            g = groups.setdefault(key, _new_group())  # receipt-only group (e.g. "—" bucket)
            # Only a token-denominated receipt contributes tokens. A `ms`/`gco2` receipt
            # is still recorded and still readable per-task (`cage insights attrib`), but
            # cage converts nothing between units — in either direction.
            if r.get("unit", "tokens") == "tokens":
                g["saved_tokens"] = g.get("saved_tokens", 0) + int(r.get("saved", 0.0))
        for g in groups.values():
            g.setdefault("saved_tokens", 0)
        total["saved_tokens"] = sum(g["saved_tokens"] for g in groups.values())
    for g in groups.values():  # sets → sorted lists (JSON-safe payload, one structure)
        g["agents"] = sorted(g.get("agents") or [])
    # Policy-defaults drift, the one freshness signal that outlived the price file
    # (`freshness.py`). Opt-in for the caller; the report footer does not take it,
    # because policy drift changes no derived number.
    from cage import freshness
    fresh = freshness.freshness(root, pol)
    return {"dim": dim, "since": since, "project": project, "scope": scope,
            "groups": groups,
            "total": total, "freshness": fresh,
            "has_receipts": any(not _is_legacy_human(r)
                                for r in ledger.by_scope(windowed_receipts, scope)),
            "legacy_human": sum(1 for r in ledger.by_scope(windowed_receipts, scope)
                                if _is_legacy_human(r)),
            "kiro_input_only": bool(kiro["calls"] and kiro["tokens_in"]
                                    and not kiro["tokens_out"]),
            # K3: any kiro row in the view triggers the no-time/session/project limit —
            # a wider gate than `kiro_input_only`, because that limit holds even when
            # kiro does report output tokens.
            "kiro_rows": kiro["calls"],
            "any_calls": bool(raw_calls)}


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
    documented opt-out for an agent you don't use.

    The warning **names the patterns it tried** when the health record carries them
    (path-globs handoff §5): a "matched 0 files" that hides its glob cannot be acted on —
    the wrong-glob bug that produced this exact line cost twenty minutes precisely because
    the message never said what it was looking for. Older records with no ``pattern``
    render as before."""
    from cage import agents
    out: list[str] = []
    for a in agents.SURFACES:
        rec = (health or {}).get(a)
        if not isinstance(rec, dict):
            continue
        if rec.get("home") and rec.get("files", 0) == 0 and not rec.get("captured"):
            home_path = rec.get("home_path") or f"~/.{a}"
            src = rec.get("src") or "its log location"
            tried = f" (tried: {rec['pattern']})" if rec.get("pattern") else ""
            out.append(
                f"⚠ {a}: {home_path} exists but {src} matched 0 files{tried} — capture is off "
                f"for this agent.\n"
                f"  cage doctor --paths      (if you don't use {a}: "
                f"[sources.{a}] replace=true, paths=[] )")
    return out


def kiro_routed_line(root: Path, pol: dict | None = None, verb: str = "report") -> str:
    """The footer line explaining why a **project** report shows no kiro (ADR 0006): its
    IDE rows are a machine fact and live in the machine ledger. ``""`` when kiro is not
    routed away (the machine ledger's own report, or an explicit ``--ledger``), or when
    kiro isn't a configured source here — nothing to explain in either case.

    Silence would be the one unacceptable outcome: an agent that shows no rows is
    indistinguishable from an agent whose capture is broken, which is the failure cage
    exists to prevent. Impure (it resolves paths), so it is read at the CLI boundary and
    passed into the pure `render_report`, like `health` and `ceiling`. Deliberately does
    **not** read the machine ledger to count rows: a per-report cross-ledger read to
    decorate a footnote is not worth it, and the line is true either way.

    ``verb`` is the command the runnable fix should name, so the *one* phrasing can be
    reused by any view that shows no kiro (`cage insights chats` passes its own). It
    varies the fix line only — the explanation itself is never re-worded per view, the
    `savings.GROSS_NOTE` discipline."""
    from cage import paths
    sink = paths.kiro_routed(root)
    if sink is None:
        return ""
    try:
        if not any(s.agent == "kiro" for s in paths.resolve_log_sources(pol).sources):
            return ""
    except Exception:  # noqa: BLE001 — a broken [sources] table is reported elsewhere
        return ""
    return (f"· kiro is not counted here — its IDE log carries no project, so its rows "
            f"are a machine fact and live in {paths.Footprint(sink).base}\n"
            f"  (`cage query kiro-routing`; read them with "
            f"`cage --ledger {paths.Footprint(sink).base} {verb}`)")


def _kiro_limits_caveat(rep: dict) -> str:
    """The kiro HONEST-LIMIT line (K3, [finding](work/regression/2026-08-01-finding-kiro-rows-carry-no-time-session-project.md)),
    stated where a kiro number could be misread. Kiro's IDE log records **no per-turn
    timestamp, no session id and no project**: its `ts` is stamped at import, `session` is
    the constant ``"kiro"``, and `project` is absent. So kiro rows cannot be ordered,
    windowed, or attributed — and the `--since` case is called out by name, because a time
    window silently *includes or excludes* them by when the import ran rather than when the
    work happened, which is the reading that would be wrong rather than merely coarse."""
    if not rep.get("kiro_rows"):
        return ""
    if rep.get("kiro_input_only"):
        base = "· kiro: input-only log — tok out not recorded; its rows also carry"
    else:
        base = "· kiro: its rows carry"
    base += " no per-turn time, session or project (`cage query kiro-routing`)"
    if rep.get("since"):
        base += ("\n  ⚠ kiro rows are timestamped at IMPORT, not at the turn — this "
                 "window neither includes nor excludes them reliably")
    return base


def _surface_caveat(rep: dict) -> str:
    """The `--by surface` HONEST-LIMIT line (K4, [finding](work/regression/2026-08-01-finding-surface-attribution-is-agent-dependent.md)).

    Claude Code's CLI and its VS Code extension write the **same** store with no marker
    distinguishing them, so cage cannot know which surface produced a claude row. The empty
    cell means *the source does not say* — the alternative, defaulting to ``cli``, would
    invent a fact. Fires only on the surface view, and only when claude rows are actually
    in it: the misreading needs the blank cell to be on screen."""
    from cage import agents as _a
    if rep.get("dim") != "surface":
        return ""
    blank = rep["groups"].get("—") or rep["groups"].get("")
    # `row_surface`, not a literal: a claude row's `agent` field is `claude-code`, so a
    # bare `"claude" in agents` check would never fire on a real ledger — a caveat that
    # silently never prints is worse than none.
    if not (blank and "claude" in {_a.row_surface(x) for x in (blank.get("agents") or [])}):
        return ""
    return ("· blank surface = the source does not say, never \"cli\" — Claude Code's CLI "
            "and VS Code extension\n  share one store with no marker; only copilot's "
            "stores are genuinely separate")


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


def overview(root: Path, pol: dict, since: str | None = None) -> dict:
    """The bare-`cage` headline: calls / tokens used / gross tokens saved (§4)."""
    calls = ledger.since(ledger.spend(root, since=since), since)
    tokens = sum(c.get("tokens_in", 0) + c.get("tokens_out", 0) for c in calls)
    rcpts = ledger.since(read_receipts(root, pol, since=since), since)
    saved = sum(int(r.get("saved", 0.0))
                for r, _ in _nonhuman_savings(ledger.join_table(root), rcpts, pol)
                if r.get("unit", "tokens") == "tokens")
    return {"since": since, "empty": not calls, "calls": len(calls),
            "tokens": tokens, "saved_tokens": saved,
            "has_receipts": any(not _is_legacy_human(r) for r in rcpts)}


def _display_name(name: str, g: dict, dim: str) -> str:
    """A generic bucket name (`agent`, `—`) says which agent it came from when
    exactly one did — `agent (kiro)` reads; bare `agent` doesn't (spec R4)."""
    agents = g.get("agents") or []
    if dim == "model" and name in ("agent", "—") and len(agents) == 1:
        return f"{name} ({agents[0]})"
    return name


def _credits_cell(g: dict) -> str:
    """`—` when this group recorded no credits, else the 2dp sum — the same
    absent-vs-recorded-zero rule `chats.py`'s `_credits_cell` follows. Never a `0`
    stand-in for an agent that has no credit unit at all (`units.ABSENT`); the footer
    names that absence separately."""
    from cage.display import DASH
    return DASH if g.get("credits") is None else f"{g['credits']:,.2f}"


def _row(name: str, g: dict, savings_cols: bool, total: bool = False,
        has_credits: bool = False) -> list[str]:
    from cage.display import DASH
    # A credits-only group (calls == 0, REPORT-CREDITS) carries no token facts at
    # all — `—` there is *absence*, never a fabricated `0`. A group with real calls
    # renders its real counts even when it also carries credits (the rare mixed case).
    no_calls = not g["calls"]
    cells = [name, DASH if no_calls else render.tok(g["calls"]),
             DASH if no_calls else render.tok(g["tokens_in"]),
             DASH if no_calls else render.tok(g["tokens_out"])]
    if has_credits:
        cells.append(_credits_cell(g))
    if savings_cols:
        cells.append(render.tok(g.get("saved_tokens", 0)))
    return cells


def render_report(rep: dict, last_import: str | None = None, disp=None,
                  stale_hours: int | None = None, health: dict | None = None,
                  ceiling: dict | None = None, kiro_route: str = "") -> str:
    """The text report (spec §1, R1–R6): tokens and credits — the two units cage
    records (USAGE-ONLY, ADR 0011). Saved columns signal-gate on receipts-in-window
    (``disp.all_columns`` restores the full grid); footer lines dedupe into one
    fixed-order block (`display.Footer`). CSV is untouched by all of it.

    ``health`` is the per-agent capture-health record (`importcmd.capture_health`, read
    at the CLI boundary and passed in — this function stays a **pure** function of its
    args): a triple-gated "installed but capturing nothing" ⚠ per silent agent
    (:func:`capture_warnings`). Never enters CSV.

    ``kiro_route`` is the already-computed kiro-routing footer line
    (:func:`kiro_routed_line`, also read at the CLI boundary): why a *project* report shows
    no kiro at all (ADR 0006). Empty in every other case. Never enters CSV.

    ``ceiling`` is the already-computed graphify day-one repo ceiling
    (`graphifymodel.repo_ceiling`, also read at the CLI boundary so this stays pure) —
    G4: a **modeled**, token-native advisory line in the footer, silent in non-graphify
    projects, never blended into report's measured $ total. CSV never sees it."""
    from cage import display as _d
    disp = disp or _d.DEFAULT
    if not rep["groups"]:
        return _render_empty(rep)
    savings = "saved_tokens" in rep["total"]  # only task/agent attribute receipts (§3.1)
    savings_cols = savings and (rep.get("has_receipts", True) or disp.all_columns)
    # REPORT-CREDITS: the column exists only when this view actually joined a
    # `ledger.credits` row — an unrelated dim (model/provider/day/task) or a ledger
    # with no credits at all stays byte-identical to before this feature.
    # Driven by the GROUPS, not the total: a cross-agent credit set has `total` None by
    # law (`units.summable`) while every per-group cell is still correct and must render.
    has_credits = any(g.get("credits") is not None for g in rep["groups"].values())
    rows = [_row(_display_name(name, g, rep["dim"]), g, savings_cols,
                has_credits=has_credits)
            for name, g in sorted(rep["groups"].items(),
                                  key=lambda kv: (-(kv[1]["tokens_in"] + kv[1]["tokens_out"]),
                                                  -(kv[1]["credits"] or 0.0), kv[0]))
            # 0-call receipt-only buckets never render (Phase 1.3); a 0-call CREDITS
            # bucket does — it is the one thing this view exists to show.
            if g["calls"] or g["credits"] is not None]
    rows.append(_row("TOTAL", rep["total"], savings_cols, total=True,
                     has_credits=has_credits))
    head = [rep["dim"], "calls", "tok in", "tok out"]
    if has_credits:
        head.append("credits")
    if savings_cols:
        head.append("gross tok")  # K: gross, never bare "saved" (net-savings handoff)
    title = f"Ledger by {rep['dim']}"
    if rep.get("project"):
        title += f" · project {rep['project']}"
    if rep["since"]:
        title += f" · since {rep['since']}"
    out = f"{title}\n\n" + render.table(head, rows, rights=set(range(1, len(head))))
    foot = _d.Footer()
    # THE CROSS-AGENT CREDIT LAW (`units.py`): when the credits column spans more than
    # one agent there is no total to print — copilot credits are GitHub's tokens×rates
    # figure, kiro credits are AWS credits. Per-group cells stay (each is correct); the
    # TOTAL cell renders `—` via `_credits_cell` because `summarize` set it to None, and
    # this line says why rather than leaving a bare dash.
    if has_credits and not rep["total"].get("credits_summable", True):
        foot.caveat(units.cross_agent_note(rep["total"].get("credits_agents", [])))
    # The per-agent unit absences actually on screen, each in its own words — a vendor
    # law (claude has no credit unit) must not read like a missing file (kiro has no IDE
    # token store). Neither is ever rendered as a `0`.
    # Mapped through `agents.row_surface`: a group's `agents` holds the ROW value
    # (`claude-code`), while `units.ABSENT` is keyed by surface (`claude`).
    from cage import agents as _agents
    for _agent in sorted({_agents.row_surface(a) or a
                          for g in rep["groups"].values()
                          for a in (g.get("agents") or [])}):
        for _unit in units.UNITS:
            if (_reason := units.absent_reason(_agent, _unit)):
                foot.footnote(f"· {_agent} {_unit}: — ({_reason})")
    # K3/K4: the two HONEST-LIMITs, each stated where its number could be misread.
    if (kiro_caveat := _kiro_limits_caveat(rep)):
        foot.caveat(kiro_caveat)
    if (surf := _surface_caveat(rep)):
        foot.caveat(surf)
    if kiro_route:  # ADR 0006: why this project report has no kiro rows to caveat
        foot.caveat(kiro_route)
    if rep.get("legacy_human"):
        # The removal decision, made visible: these rows are excluded from every
        # money total rather than priced at a rate that no longer exists. Silence
        # here would be the one thing the removal was not allowed to do.
        foot.caveat(f"· {rep['legacy_human']} legacy human-axis receipt(s) excluded "
                    "from savings — the agent-vs-human axis was removed in v0.36 and "
                    "these rows belong to no surviving axis (`cage query savings-axis`)")
    if rep.get("project"):
        foot.caveat("· project view is exact for Claude only — Copilot/Kiro logs "
                    "carry no project, so their spend is excluded from this filter.")
    if savings_cols:  # K: what the gross column excludes, in the ONE shared phrasing
        from cage import savings as _savings
        foot.caveat(_savings.GROSS_NOTE)
    if savings and not rep.get("has_receipts", True):
        foot.gap("· no savings receipts in this window — wire a tool to measure savings\n"
                 "  (`cage query receipts` explains)")
    for w in capture_warnings(health):  # installed-but-capturing-nothing (docs/capture-health)
        foot.warn(w)
    if ceiling:  # G4: graphify day-one repo ceiling (modeled, token-native, footer-only)
        from cage import graphifymodel
        foot.advice(graphifymodel.ceiling_footer_line(ceiling))
    foot.advice(_last_import_line(last_import, stale_hours))
    for l in rep.get("freshness") or []:  # actionable-only — silent when clean (§3.3)
        foot.advice(f"· {l}")
    tail = foot.render()
    return f"{out}\n\n{tail}" if tail else out


def render_csv(rep: dict) -> str:
    """CSV over the same `summarize()` payload the text table renders — one
    structure, two renderers (they cannot disagree). Rows sort like the text view
    (usage-descending) + a TOTAL row.

    `method` column: **measured** throughout — every figure is a recorded count read
    back verbatim. The `modeled` degradation this used to carry existed because a
    configured credit rate was producing dollars cage could not check against an
    invoice; with no dollars there is no inference to grade down (USAGE-ONLY, ADR 0011).

    `gross_saved_tokens` is named for what it is — it excludes the tokens spent *using*
    the tool (`savings.GROSS_NOTE`). Column contract in docs/FORMULAS.md §2."""
    from cage import csvout
    savings = "saved_tokens" in rep["total"]
    # REPORT-CREDITS: the column exists only when this view joined a `ledger.credits`
    # row — an unaffected dim or a ledger with no credits stays byte-identical
    # (the same conditional-column pattern the savings pair already uses above).
    # Driven by the GROUPS, not the total: a cross-agent credit set has `total` None by
    # law (`units.summable`) while every per-group cell is still correct and must render.
    has_credits = any(g.get("credits") is not None for g in rep["groups"].values())
    head = [rep["dim"], "calls", "tokens_in", "tokens_out", "cached_in",
            *(("credits",) if has_credits else ()),
            *(("gross_saved_tokens",) if savings else ()), "method"]
    def cells(name, g):
        # A credits-only group (calls == 0) leaves calls/tokens_in/tokens_out/cached_in
        # EMPTY, never `0` — the same absence-vs-measured-zero rule the text view's `—`
        # follows (a `0` there would claim "we counted calls here and found none",
        # when in fact no call was ever possible for this row).
        no_calls = not g["calls"]
        row = [name, "" if no_calls else g["calls"], "" if no_calls else g["tokens_in"],
               "" if no_calls else g["tokens_out"], "" if no_calls else g["cached_in"]]
        if has_credits:
            row.append("" if g.get("credits") is None else round(g["credits"], 6))
        row += ((g.get("saved_tokens", 0),) if savings else ())
        row.append("measured")
        return row
    rows = [cells(name, g)
            for name, g in sorted(rep["groups"].items(),
                                  key=lambda kv: (-(kv[1]["tokens_in"] + kv[1]["tokens_out"]),
                                                  -(kv[1]["credits"] or 0.0), kv[0]))]
    rows.append(cells("TOTAL", rep["total"]))
    return csvout.table(head, rows)


def render_overview(o: dict, last_import: str | None = None, disp=None) -> str:
    """The bare-`cage` headline — tokens used and gross tokens saved. The saved half
    gates on receipts existing in the window."""
    from cage import display as _d
    disp = disp or _d.DEFAULT
    if o["empty"]:
        return _EMPTY
    win = f"({o['since']})" if o["since"] else "(all time)"
    head = f"{render.tok(o['tokens'])} tokens  ·  {o['calls']} calls   {win}"
    if o.get("has_receipts", True):
        head = (f"{render.tok(o['tokens'])} tokens  ·  gross saved "
                f"{render.tok(o['saved_tokens'])} tok  ·  {o['calls']} calls   {win}")
    drill = ("  drill:  cage report --by agent   ·   cage insights why <call>"
             "   ·   cage insights attrib --task <t>")
    out = f"{head}\n{drill}"
    foot = _d.Footer()
    if o.get("has_receipts", True):  # K: the gross exclusion, one phrasing
        from cage import savings as _savings
        foot.caveat(_savings.GROSS_NOTE)
    else:
        foot.gap("· no savings receipts in this window — wire a tool to measure savings\n"
                 "  (`cage query receipts` explains)")
    tail = foot.render()
    return f"{out}\n{tail}" if tail else out
