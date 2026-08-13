"""`cage report` — the ledger rollup: spend by agent / route / model / day (plan §7).

Any meter does this; it's the honest floor the rest of Cage builds on. Pure
aggregation over `calls.jsonl`, grouped on whichever dimension you ask for.
"""
from __future__ import annotations

from pathlib import Path

from cage import convert, creditprice, ledger, paths, policy, prices, render
from cage.constants import TOKENS_PER_MILLION

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
    # `credits` starts at None, not 0.0 — the absent-vs-recorded-zero distinction
    # every credits field in cage carries (REPORT-CREDITS, matching `chats.py`'s
    # `_new_bucket`). A group no `ledger.credits` row ever joined stays None and
    # renders `—`; one that joined a recorded `0.0` renders `0.00` — different facts.
    return {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cached_in": 0, "usd": 0.0,
            "cache_usd": 0.0, "unpriced_calls": 0, "unpriced_tokens": 0,
            "credits": None, "credits_usd": 0.0, "credits_rated": False}


def _cache_read_usd(pol: dict, provider: str, model: str, cached_in: int) -> float:
    """F5 (docs/regression/2026-07-22-capture-report.md): the cache-read-billed
    slice of a call's cost alone — `cached_in` tokens at the model's real
    `cache_read` per-million rate, never a hardcoded discount fraction, so the
    split stays correct if pricing changes. A component of `prices.call_cost_usd`'s
    total, split out here (report-only concern) rather than growing `prices.py`
    past its stated ≤50-line budget. Meaningful only for a call that priced through
    a real row (exact/alias/family) — a `self`-priced or unpriced call has no
    token-level cache split to report."""
    p = policy.price(pol, provider, model)
    return round(cached_in * p["cache_read"] / TOKENS_PER_MILLION, 6)


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


def _is_legacy_human(r: dict) -> bool:
    """A pre-0.36 Tier-1 row: the removed human axis's tool, or its removed unit.
    The ONE predicate every money view shares — see `_nonhuman_savings`."""
    return r.get("tool") == "human" or r.get("unit") == "minutes"


def _nonhuman_savings(all_calls: list[dict], receipts: list[dict], pol: dict,
                      scope: str | None = None):
    """Yield ``(receipt, call, saved_usd, rung, model_key)`` per non-human receipt
    (already window-filtered). ``all_calls`` is the *unfiltered* join table so an
    in-window receipt can still find its (possibly older) call.

    **Legacy Tier-1 rows are excluded, never priced.** The agent-vs-human axis was
    removed in v0.36, but ledgers are append-only: a pre-0.36 ``tool="human"`` receipt
    (and any ``unit="minutes"`` row) has no USD route left. Skipping it here is a
    *decision*, so it is COUNTED and footnoted (``legacy_human`` below) rather than
    silently dropped from a total — `cage query savings-axis` explains it.
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
        if _is_legacy_human(r):
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
    # COPILOT-CREDITS: the two-basis split behind the totals. A total that sums a
    # credits-priced and a token-priced cell must SAY so (verdict C rule 4 — the axes
    # are never blended silently), and credits recorded with no rate to price them must
    # surface as a count rather than vanish into the UNPRICED bucket unexplained.
    # Tallied PER AGENT, then reduced. The split footnote is a claim about one agent's
    # rows ("copilot priced on two bases"), so the token side must count only that
    # agent's token-priced calls — a global tally would attribute claude's spend to
    # copilot's basis split, which is how the first version of this read.
    cred_by_agent: dict[str, dict] = {}
    cred = {"unrated_calls": 0, "unrated_total": 0.0,    # recorded, but no rate
            "unrated_agents": set(),
            "unpriced_with_credits": 0}                  # rung-3 rows that DO carry credits
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
        # A credits-priced row has NO token-level cache split to report: its dollar did
        # not come from the price table at all, so attributing a slice of it to
        # `cache_read` would describe a total that was never token-derived.
        if match not in ("none", "self", creditprice.MATCH):
            g["cache_usd"] += _cache_read_usd(pol, c.get("provider") or "",
                                              c.get("model") or "", c.get("cached_in", 0))
        ca = cred_by_agent.setdefault(c.get("agent") or "—",
                                      {"calls": 0, "total": 0.0, "usd": 0.0,
                                       "token_calls": 0, "token_usd": 0.0})
        if match == creditprice.MATCH:
            ca["calls"] += 1
            ca["total"] += creditprice.recorded(c) or 0.0
            ca["usd"] += usd
        else:
            if match != "none":
                ca["token_calls"] += 1
                ca["token_usd"] += usd
            if creditprice.unrated(pol, c):
                cred["unrated_calls"] += 1
                cred["unrated_total"] += creditprice.recorded(c) or 0.0
                cred["unrated_agents"].add(c.get("agent") or "")
                if match == "none":
                    cred["unpriced_with_credits"] += 1
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
    # REPORT-CREDITS: `ledger.credits` (kiro-CLI conversations — no call, no tokens)
    # folds into the SAME `groups` dict as calls, on the two dims where a credits row
    # has a clean, non-colliding key: `agent` (its own field) and the default `route`
    # view (a synthetic "credits" bucket — a credits row carries no `route` at all, and
    # bucketing it into the "—" catch-all would blend it with unrelated legacy rows).
    # Every other dim (model/provider/day/task) is deliberately untouched — a credits
    # row doesn't carry those fields cleanly, and CHATS-CREDITS already covers the
    # per-conversation view (`cage insights chats`). Never folded into `usd`/`tokens_*`:
    # a group's `credits` is its own field, read only by its own column.
    unrated_agents: set[str] = set()
    unrated_calls_n = 0
    unrated_total = 0.0
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
            rate = creditprice.rate_for(pol, cr)
            if rate is not None:
                g["credits_usd"] += round(float(cr_val) * rate, 6)
                g["credits_rated"] = True
            else:
                unrated_calls_n += 1
                unrated_total += float(cr_val)
                unrated_agents.add(cr.get("agent") or "")
    total = {"calls": sum(g["calls"] for g in groups.values()),
             "usd": sum(g["usd"] for g in groups.values()),
             "tokens_in": sum(g["tokens_in"] for g in groups.values()),
             "tokens_out": sum(g["tokens_out"] for g in groups.values()),
             "cached_in": sum(g["cached_in"] for g in groups.values()),
             "cache_usd": sum(g["cache_usd"] for g in groups.values()),
             "unpriced_calls": sum(g["unpriced_calls"] for g in groups.values()),
             "unpriced_tokens": sum(g["unpriced_tokens"] for g in groups.values()),
             "credits": (sum(g["credits"] or 0.0 for g in groups.values())
                        if any(g["credits"] is not None for g in groups.values())
                        else None),
             "credits_usd": sum(g["credits_usd"] for g in groups.values()),
             # Whether ANY group's credits actually priced — the TOTAL row's own cost
             # cell reads this flag (never `credits_usd > 0`, which can't tell a real
             # priced `$0.0000` from "nothing priced" — the same absence-vs-zero rule
             # every credits figure in cage carries).
             "credits_rated": any(g["credits_rated"] for g in groups.values())}
    unrated_credits = {"calls": unrated_calls_n, "total": unrated_total,
                       "agents": sorted(unrated_agents - {""})}
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
            # Net is against the FULL spend, including a rated credits dollar — the
            # same sum `_cost_cell` shows, so "net vs spend" can never overstate a
            # saving by silently excluding money the cost column already counts.
            g["net_usd"] = g["saved_usd"] - g["usd"] - (g["credits_usd"] if g["credits_rated"] else 0.0)
        total["saved_usd"] = total_saved
        total["net_usd"] = (total_saved - total["usd"]
                            - (total["credits_usd"] if total["credits_rated"] else 0.0))
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
    cred["unrated_agents"] = sorted(a for a in cred["unrated_agents"] if a)
    # An agent earns the mixed-basis footnote only if ITS OWN rows split across both
    # rungs; one agent priced by credits and a different one by tokens is not a mixed
    # basis, it is two agents. `calls`/`usd` stay as the view-wide credits totals the
    # CSV method tag and the doctor line read.
    cred["by_agent"] = {a: v for a, v in sorted(cred_by_agent.items())
                        if v["calls"] and v["token_calls"]}
    cred["calls"] = sum(v["calls"] for v in cred_by_agent.values())
    cred["usd"] = sum(v["usd"] for v in cred_by_agent.values())
    cred["total"] = sum(v["total"] for v in cred_by_agent.values())
    return {"dim": dim, "since": since, "project": project, "scope": scope,
            "groups": groups, "credits": cred,
            # `ledger_credits_unrated`: the REPORT-CREDITS rate-unset advisory — distinct
            # from `credits` above (the pre-existing per-call COPILOT-CREDITS ladder dict).
            "ledger_credits_unrated": unrated_credits,
            "total": total, "unpriced": sorted(unpriced), "family": family,
            "alias": alias, "unpriced_detail": dict(sorted(unpriced.items())),
            "unpriced_receipts": unpriced_receipts, "freshness": fresh,
            "rung_models": sorted(rung_models),
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
    `netsaved.GROSS_NOTE` discipline."""
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


def _kiro_limits_caveat(rep: dict, usd: bool) -> str:
    """The kiro HONEST-LIMIT line (K3, [finding](docs/regression/2026-08-01-finding-kiro-rows-carry-no-time-session-project.md)),
    stated where a kiro number could be misread. Kiro's IDE log records **no per-turn
    timestamp, no session id and no project**: its `ts` is stamped at import, `session` is
    the constant ``"kiro"``, and `project` is absent. So kiro rows cannot be ordered,
    windowed, or attributed — and the `--since` case is called out by name, because a time
    window silently *includes or excludes* them by when the import ran rather than when the
    work happened, which is the reading that would be wrong rather than merely coarse."""
    if not rep.get("kiro_rows"):
        return ""
    if rep.get("kiro_input_only"):
        base = ("· kiro: input-only log — cost understated" if usd
                else "· kiro: input-only log — tok out not recorded")
        base += "; its rows also carry"
    else:
        base = "· kiro: its rows carry"
    base += " no per-turn time, session or project (`cage query kiro-routing`)"
    if rep.get("since"):
        base += ("\n  ⚠ kiro rows are timestamped at IMPORT, not at the turn — this "
                 "window neither includes nor excludes them reliably")
    return base


def _surface_caveat(rep: dict) -> str:
    """The `--by surface` HONEST-LIMIT line (K4, [finding](docs/regression/2026-08-01-finding-surface-attribution-is-agent-dependent.md)).

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


def _unpriced_block(detail: dict, credits: dict | None = None) -> str:
    """The `--usd` view's ⚠ UNPRICED block (spec R4): counts headline + one
    **runnable** fix line per unpriced provider/model (the one fix-line builder,
    `pricescmd.fix_line` — reused, never re-phrased). ``detail`` rows lacking the
    provider/model split (legacy payloads) fall back to the `cage prices
    unpriced` pointer.

    ``credits`` adds the SECOND fix line when some of these unpriced rows carry a
    recorded credit (COPILOT-CREDITS): those rows need no price-table row at all —
    they need a rate — and offering only the alias fix would send a reader to solve
    the harder problem. The line states how many of the unpriced rows it would fix,
    so it never over-claims to cover the whole block."""
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
    lines = [head, *dict.fromkeys(fixes)]
    n = (credits or {}).get("unpriced_with_credits", 0)
    if n:
        lines.append(f"  or:  {creditprice.rate_hint((credits or {}).get('unrated_agents', []))}"
                     f" — {n} of these rows carry recorded credits")
    return "\n".join(lines)


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
            "has_receipts": any(not _is_legacy_human(r) for r in rcpts)}


def _cost_cell(g: dict, total: bool = False) -> str:
    """`—` is the only rendering of "couldn't price" — a group whose every call
    refused to price shows the dash, never `$0.0000` (a self-costed est fallback
    keeps its real figure). A TOTAL over a partial gap says so inline.

    A **credits-only** group (`calls == 0`, REPORT-CREDITS) has no token-priced cost
    at all — its cell prices only through the credits rate (`—` when unrated, a real
    `$0.0000` when a configured `0.0` rate priced it). A group whose calls *and*
    credits rows share one bucket (rare — an agent whose real calls and its
    call-less credits conversations landed in the same root) **sums both** rather
    than silently dropping the credits side — a total that quietly omitted a rated
    dollar would understate spend, the one thing this cell must never do. The
    caller states the split (`render_report`'s total-spans-two-bases footnote)
    whenever both sides are non-zero, so the sum is never presented as one basis."""
    from cage.display import DASH
    credits_usd = g["credits_usd"] if g.get("credits_rated") else 0.0
    if not g["calls"]:
        if g.get("credits") is not None:
            return render.usd(credits_usd) if g.get("credits_rated") else DASH
        return DASH
    if (g.get("unpriced_calls") and g["unpriced_calls"] == g["calls"]
            and not g["usd"] and not credits_usd):
        return DASH
    cell = render.usd(g["usd"] + credits_usd)
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


def _credits_cell(g: dict) -> str:
    """`—` when this group joined no `ledger.credits` row, else the 2dp sum — the
    same absent-vs-recorded-zero rule `chats.py`'s `_credits_cell` follows."""
    from cage.display import DASH
    return DASH if g.get("credits") is None else creditprice.fmt(g["credits"])


def _row(name: str, g: dict, savings_cols: bool, usd_view: bool, total: bool = False,
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
    if not usd_view and savings_cols:
        cells.append(render.tok(g.get("saved_tokens", 0)))
    if usd_view:
        cost = _cost_cell(g, total=total)
        cells.append(cost)
        if savings_cols:
            cells += _saved_cells(g, cost_dashed=cost == DASH)
    return cells


def render_report(rep: dict, last_import: str | None = None, disp=None,
                  stale_hours: int | None = None, health: dict | None = None,
                  ceiling: dict | None = None, kiro_route: str = "") -> str:
    """The text report (spec §1, R1–R6): tokens by default, dollars on ``disp.usd``
    (plan Phase 2.5); saved columns signal-gate on receipts-in-window
    (``disp.all_columns`` restores the full grid); pricing footnotes and the full
    ⚠ block belong to the `--usd` view; footer lines dedupe into one
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
    savings = "saved_usd" in rep["total"]  # only task/agent attribute receipts (§3.1)
    savings_cols = savings and (rep.get("has_receipts", True) or disp.all_columns)
    # REPORT-CREDITS: the column exists only when this view actually joined a
    # `ledger.credits` row — an unrelated dim (model/provider/day/task) or a ledger
    # with no credits at all stays byte-identical to before this feature.
    has_credits = rep["total"].get("credits") is not None
    rows = [_row(_display_name(name, g, rep["dim"]), g, savings_cols, disp.usd,
                has_credits=has_credits)
            for name, g in sorted(rep["groups"].items(), key=lambda kv: -kv[1]["usd"])
            # 0-call receipt-only buckets never render (Phase 1.3); a 0-call CREDITS
            # bucket does — it is the one thing this view exists to show.
            if g["calls"] or g["credits"] is not None]
    rows.append(_row("TOTAL", rep["total"], savings_cols, disp.usd, total=True,
                     has_credits=has_credits))
    head = [rep["dim"], "calls", "tok in", "tok out"]
    if has_credits:
        head.append("credits")
    if not disp.usd and savings_cols:
        head.append("gross tok")  # K: gross, never bare "saved" (net-savings handoff)
    if disp.usd:
        head.append("cost")
        if savings_cols:
            head += ["gross", "net vs spend"]
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
        # COPILOT-CREDITS: a total spanning both pricing bases names the split, and
        # credits with no rate render as a COUNT — never silently as a dollar, never
        # silently as nothing.
        cr = rep.get("credits") or {}
        for agent, v in (cr.get("by_agent") or {}).items():
            foot.footnote(creditprice.split_footnote(
                agent, v["calls"], v["total"], v["usd"], v["token_calls"], v["token_usd"]))
        if cr.get("unrated_calls"):
            foot.gap(creditprice.unrated_line(cr["unrated_calls"], cr["unrated_total"],
                                              cr.get("unrated_agents", [])))
        # REPORT-CREDITS: the rate-unset advisory for `ledger.credits` rows — a
        # DIFFERENT population from `cr` above (calls that carry a `credits` field,
        # COPILOT-CREDITS). These are call-less conversations, so the line says
        # "conversation(s)", never "call(s)" — a credits row was never a call.
        lcu = rep.get("ledger_credits_unrated") or {}
        if lcu.get("calls"):
            n = lcu["calls"]
            foot.gap(f"· {n} conversation{'s' if n != 1 else ''} carry recorded credits "
                     f"({creditprice.fmt(lcu['total'])} cr) — not priced; "
                     f"{creditprice.rate_hint(lcu.get('agents', []))}")
        # REPORT-CREDITS: a `cost`/TOTAL cell can now sum a token-priced dollar and a
        # rate-priced credits dollar (`_cost_cell`, never silently dropping the
        # credits side — the one thing a total must not do). Whenever both sides are
        # non-zero the split is named, the same discipline `creditprice.split_footnote`
        # already applies to the copilot per-call ladder above.
        if rep["total"].get("credits_rated") and rep["total"]["usd"]:
            foot.footnote(f"· total spans two pricing bases: {render.usd(rep['total']['usd'])} "
                          f"from token-priced calls + {render.usd(rep['total']['credits_usd'])} "
                          "from credits×rate (`cage query copilot-credits`)")
        t = rep["total"]
        # F5 (docs/regression/2026-07-22-capture-report.md): a headline like
        # "8.2B tokens, $7,046" reads as alarming when it's almost entirely
        # prefix-cache re-reads billed at a discount. One line, real numbers —
        # no other report structure changes.
        if t.get("tokens_in"):
            cache_tok_pct = render.pct(t.get("cached_in", 0), t["tokens_in"])
            cache_usd_pct = render.pct(t.get("cache_usd", 0.0), t["usd"]) if t["usd"] else "—"
            foot.caveat(f"· cache: {cache_tok_pct} of input tokens were cache reads, "
                        f"{cache_usd_pct} of cost ({render.usd(t.get('cache_usd', 0.0))} "
                        f"of {render.usd(t['usd'])})")
    # K3/K4: the two HONEST-LIMITs, each stated where its number could be misread.
    if (kiro_caveat := _kiro_limits_caveat(rep, disp.usd)):
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
                    "these rows have no price route (`cage query savings-axis`)")
    if rep.get("project"):
        foot.caveat("· project view is exact for Claude only — Copilot/Kiro logs "
                    "carry no project, so their spend is excluded from this filter.")
    if disp.usd:
        from cage import receiptprice
        if rep.get("unpriced_detail"):
            foot.warn(_unpriced_block(rep["unpriced_detail"], rep.get("credits")))
        if rep.get("unpriced_receipts", {}).get("receipts"):
            foot.warn(receiptprice.unpriced_receipts_line(rep["unpriced_receipts"]))
    if savings_cols:  # K: what the gross column excludes, in the ONE shared phrasing
        from cage import netsaved
        foot.caveat(netsaved.GROSS_NOTE + "\n  net vs spend = gross − this window's "
                    "spend, not net of the tools' cost of use.")
    if savings and not rep.get("has_receipts", True):
        foot.gap("· no savings receipts in this window — wire a tool to measure savings\n"
                 "  (`cage query receipts` explains)")
    if not disp.usd and rep["total"].get("unpriced_calls"):
        n = rep["total"]["unpriced_calls"]
        foot.gap(f"· {n} call{'s' if n != 1 else ''} unpriced — matters when you "
                 f"view $ (`--usd`; cage prices unpriced)")
    for w in capture_warnings(health):  # installed-but-capturing-nothing (docs/capture-health)
        foot.warn(w)
    if ceiling:  # G4: graphify day-one repo ceiling (modeled, token-native, footer-only)
        from cage import graphifymodel
        foot.advice(graphifymodel.ceiling_footer_line(ceiling))
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
    `repricing` query entry); spend is never a projection. The savings columns are
    named for what they are — `gross_saved_usd` excludes the cost of *using* the tool,
    and `net_vs_spend_usd` nets it against this window's spend, not against that cost
    (net-savings handoff, K). Column contract in docs/FORMULAS.md §2."""
    from cage import csvout
    savings = "saved_usd" in rep["total"]
    # REPORT-CREDITS: the column exists only when this view joined a `ledger.credits`
    # row — an unaffected dim or a ledger with no credits stays byte-identical
    # (the same conditional-column pattern the savings pair already uses above).
    has_credits = rep["total"].get("credits") is not None
    head = [rep["dim"], "calls", "tokens_in", "tokens_out", "cached_in",
            *(("credits",) if has_credits else ()), "cost_usd",
            *(("gross_saved_usd", "net_vs_spend_usd") if savings else ()),
            "unpriced_calls", "unpriced_tokens", "method"]
    # Method law: `measured` is only true while every priced cell came from tokens ×
    # price table. A credits-priced row (either basis — a call carrying its own
    # `credits` field, COPILOT-CREDITS, or a call-less `ledger.credits` conversation,
    # REPORT-CREDITS) makes the view's dollars partly a function of a configured rate,
    # so the whole view degrades to `modeled` (`creditprice.method_for`). This is
    # view-level, not per-group: the CSV's `cost_usd` rows share one basis statement,
    # and a per-group tag would let a reader sum `measured` rows into a total that isn't.
    credits_priced = (rep.get("credits", {}).get("calls", 0)
                      + sum(1 for g in rep["groups"].values() if g.get("credits_rated")))
    method = creditprice.method_for({creditprice.CREDITS: credits_priced})
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
        # `cost_usd` sums the token-priced and rate-priced credits dollars — the same
        # never-silently-drop-a-rated-dollar rule `_cost_cell` follows. Empty (not a
        # fabricated `0`) only when NEITHER side ever priced this row.
        rated_usd = g["credits_usd"] if g.get("credits_rated") else 0.0
        if no_calls and g.get("credits") is not None and not g.get("credits_rated"):
            row.append("")
        else:
            row.append(round(g["usd"] + rated_usd, 6))
        row += ((round(g["saved_usd"], 6), round(g["net_usd"], 6)) if savings else ())
        row += [g["unpriced_calls"], g["unpriced_tokens"], method]
        return row
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
        head = (f"spent {render.usd(o['spent_usd'])}  ·  gross saved "
                f"{render.usd(o['saved_usd'])}"
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
    if disp.usd and o.get("has_receipts", True):  # K: the gross exclusion, one phrasing
        from cage import netsaved
        foot.caveat(netsaved.GROSS_NOTE)
    if disp.usd and not o.get("has_receipts", True):
        foot.gap("· no savings receipts in this window — wire a tool to measure savings\n"
                 "  (`cage query receipts` explains)")
    tail = foot.render()
    return f"{out}\n{tail}" if tail else out
