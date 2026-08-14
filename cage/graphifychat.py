"""`cage insights graphify` — one row per chat: recorded tokens (the with-graphify
world), the modeled without-graphify counterfactual, and the GROSS saved share
(graphify-chats handoff, `work/archive/v0.49-graphify-chats.handoff.md`).

Reuses `chats.summarize` verbatim for the chat universe (title, normalized agent +
surface, session, token sums, `from_credits` marks) and joins `ledger.savings` rows
onto it by `session` alone — a savings row carries no agent field at all. Every
figure here is GROSS (`savings.GROSS_NOTE`): per-chat NET is not computable
(netsaved's attributable-cost rule needs a call-level tool-use mark this ledger
doesn't carry).

Two tallies never fold into a chat row, footnoted instead: `unassignable` (the
native shim's honest-empty `session=""`, GC3) and `unmatched` (a savings session
joining no chat bucket at all — a different ledger root, a deleted call, etc).
"""
from __future__ import annotations

from pathlib import Path

from cage import chats, ledger
from cage.chats import KIRO_IDE_LABEL, _short
from cage.constants import GRAPHIFY_CHATS_DEFAULT_ROWS, METHOD_TRUST

_NO_SESSION = "(no session)"


def summarize(root: Path, pol: dict, since: str | None = None,
             agent: str | None = None, tool: str = "graphify") -> dict:
    """The one data structure every renderer consumes — deterministic and
    **untruncated**: ranking/bounding is a render-time concern (`--all`)."""
    base = chats.summarize(root, pol, since=since, agent=agent)
    sav_all = ledger.savings(root, since=since)
    sav = [r for r in ledger.since(sav_all, since) if r.get("tool") == tool]

    by_session: dict[str, list[dict]] = {}
    unassignable = {"receipts": 0, "saved": 0.0}
    for r in sav:
        session = r.get("session") or ""
        if not session:
            unassignable["receipts"] += 1
            unassignable["saved"] += r.get("saved", 0.0)
            continue
        by_session.setdefault(session, []).append(r)

    # A session shared by more than one chat bucket (a surface split — savings rows
    # carry no surface, so the join can't tell them apart) attaches to every one of
    # those rows, footnoted at render — the `auth_split` precedent (`chats.py`).
    per_session_count: dict[str, int] = {}
    for r in base["rows"]:
        per_session_count[r["session"]] = per_session_count.get(r["session"], 0) + 1

    rows: list[dict] = []
    joined_sessions: set[str] = set()
    for r in base["rows"]:
        session = r["session"]
        group = by_session.get(session, [])
        if group:
            joined_sessions.add(session)
        receipts = len(group)
        saved = sum(x.get("saved", 0.0) for x in group)
        raw_alternative = sum(x.get("raw_alternative", 0.0) for x in group)
        actual = sum(x.get("actual", 0.0) for x in group)
        # Worst-case method/confidence across this chat's receipts — the exact
        # `attribution.receipts_by_tool` aggregation, inlined (handoff §4).
        method, confidence = "", None
        for x in group:
            m = x.get("method", "modeled")
            if not method or METHOD_TRUST.get(m, 1) < METHOD_TRUST.get(method, 1):
                method = m
            c = x.get("confidence", 1.0)
            confidence = c if confidence is None else min(confidence, c)
        tokens = None if r.get("from_credits") else r["tokens_in"] + r["tokens_out"]
        without = None if tokens is None else tokens + saved
        pct = (100.0 * saved / without) if (without is not None and without > 0) else None
        rows.append({
            "agent": r["agent"], "surface": r["surface"], "session": session,
            "title": r["title"], "named": r["named"],
            "from_credits": bool(r.get("from_credits")),
            "receipts": receipts, "saved": round(saved, 6),
            "raw_alternative": round(raw_alternative, 6), "actual": round(actual, 6),
            "method": method, "confidence": confidence,
            "tokens": tokens, "without": without, "pct": pct,
            "has_gfx": receipts > 0,
            "gfx_split": receipts > 0 and per_session_count.get(session, 0) > 1,
        })

    unmatched_sessions = set(by_session) - joined_sessions
    unmatched = {
        "receipts": sum(len(by_session[s]) for s in unmatched_sessions),
        "saved": sum(x.get("saved", 0.0) for s in unmatched_sessions
                    for x in by_session[s]),
    }
    return {"since": since, "agent": agent, "rows": rows,
            "unassignable": unassignable, "unmatched": unmatched,
            "any_savings": bool(sav)}


# ── rendering ────────────────────────────────────────────────────────────────

_HINT = ("next: cage query graphify-coverage   which agent surfaces can file a receipt\n"
        "      cage doctor                    check capture is wired and healthy\n"
        "      cage insights attrib          per-tool gross token savings")


def _render_empty(data: dict, all_chats: bool, kiro_route: str = "") -> str:
    """The empty view. **Diagnoses, never guesses**: `any_savings` decides whether
    this is "graphify never filed a receipt" (point at coverage/doctor/roi) or "the
    receipts exist, this view/filter just isn't showing them"."""
    filters = []
    if data.get("since"):
        filters.append(f"since {data['since']}")
    if data.get("agent") and data["agent"] != "all":
        filters.append(f"agent '{data['agent']}'")
    label = " · ".join(filters)

    if not data.get("any_savings"):
        head = (f"No graphify savings for {label} — and the filter is not the reason:"
                if filters else "No graphify savings recorded yet.")
        lines = [head]
        if kiro_route:
            lines += ["", kiro_route]
        lines += ["", _HINT]
        return "\n".join(lines)
    if filters:
        return (f"No graphify chats match {label} — the filter is empty, "
                "not the ledger.\n\n"
                "next: cage insights graphify                the unfiltered view")
    if not all_chats:
        return ("No chat has a graphify receipt yet — every chat is shown with "
                "--all-chats.\n\n"
                "next: cage insights graphify --all-chats   every chat (gfx cells `—`)")
    return ("Graphify savings exist but none joined a chat in this ledger (every "
            "receipt is unassignable or unmatched).\n\n"
            "next: cage insights chats                  the plain chat view")


def _label(r: dict) -> str:
    if r["named"] or r["title"] in (KIRO_IDE_LABEL, _NO_SESSION):
        return r["title"]
    return _short(r["title"])  # an untitled fallback is the raw session id — shorten it


def _row_cells(r: dict) -> list[str]:
    from cage import render
    from cage.display import DASH
    uses = render.tok(r["receipts"]) if r["has_gfx"] else DASH
    tokens_cell = DASH if r["from_credits"] else render.tok(r["tokens"])
    if r["from_credits"] or not r["has_gfx"]:
        without_cell, pct_cell = DASH, DASH
    else:
        without_cell = render.tok(r["without"])
        pct_cell = f"{round(r['pct'])}%" if r["pct"] is not None else DASH
    saved_cell = render.tok(r["saved"]) if r["has_gfx"] else DASH
    return [_label(r), r["agent"], r["surface"] or "—", uses, tokens_cell,
            without_cell, saved_cell, pct_cell]


def _worst_case(shown: list[dict]) -> tuple[str, float]:
    have = [r for r in shown if r["has_gfx"]]
    method, confidence = "", 1.0
    for r in have:
        if not method or METHOD_TRUST.get(r["method"], 1) < METHOD_TRUST.get(method, 1):
            method = r["method"]
        confidence = min(confidence, r["confidence"])
    return method or "modeled", confidence


def render_view(data: dict, show_all: bool = False, all_chats: bool = False,
               kiro_route: str = "") -> str:
    """The text table. Default rows are receipt-bearing chats only (`--all-chats`
    lifts it); rank `(-saved, session)`; top-20, `--all` lifts the cut."""
    from cage import render, savings

    rows = data["rows"]
    shown_rows = rows if all_chats else [r for r in rows if r["has_gfx"]]
    if not shown_rows:
        return _render_empty(data, all_chats, kiro_route)
    shown_rows = sorted(shown_rows, key=lambda r: (-r["saved"], r["session"]))
    limit = None if show_all else GRAPHIFY_CHATS_DEFAULT_ROWS
    shown = shown_rows if limit is None else shown_rows[:limit]
    cut = 0 if limit is None else max(0, len(shown_rows) - limit)

    head = ["chat", "agent", "surface", "gfx uses", "tokens", "without gfx",
            "saved", "saved%"]
    rights = set(range(3, len(head)))
    table_rows = [_row_cells(r) for r in shown]

    title = "Graphify per-chat usage & GROSS saving"
    if data.get("agent") and data["agent"] != "all":
        title += f" · agent {data['agent']}"
    if data.get("since"):
        title += f" · since {data['since']}"
    out = f"{title}\n\n" + render.table(head, table_rows, rights=rights)

    from cage import display as _d
    foot = _d.Footer()
    if cut:
        foot.gap(f"· {cut} more chat(s) — --all to show")
    foot.footnote(savings.GROSS_NOTE)
    foot.footnote("· tokens is the chat's recorded tokens_in + tokens_out — the "
                 "WITH-graphify world (cached/cache-write excluded); without gfx = "
                 "tokens + Σsaved is the MODELED without-graphify counterfactual — "
                 "it mixes a graphifymeter.toks estimate against metered tokens, so "
                 "saved% is modeled throughout (`cage query graphify-chats`)")
    if any(r["has_gfx"] for r in shown):
        m, c = _worst_case(shown)
        foot.footnote(f"· method: {m} (confidence {c:.2f}, worst case across the "
                      "receipts shown)")
    if any(r["from_credits"] for r in shown):
        foot.caveat("· kiro CLI reports credits only — its store carries no token "
                    "counts, so tokens/without gfx/saved% are '—' here (saved still "
                    "shown; `cage query copilot-credits`)")
    if any(r["gfx_split"] for r in shown):
        foot.caveat("· a savings row carries no surface, so a session split across "
                    "surfaces attaches its receipts to every one of those rows — "
                    "those rows are not independent evidence")
    if any(r["agent"] == "kiro" for r in shown):
        from cage import graphifytx
        for line in graphifytx.coverage_lines():
            foot.gap(f"· {line}")
    ua = data["unassignable"]
    if ua["receipts"]:
        foot.gap(f"· {ua['receipts']} graphify receipt(s) unassignable — the native "
                 f"shim's honest-empty session (Σsaved {render.tok(ua['saved'])} tok, "
                 "never redistributed into a chat row)")
    um = data["unmatched"]
    if um["receipts"]:
        foot.gap(f"· {um['receipts']} graphify receipt(s) unmatched — session joins "
                 f"no chat row (Σsaved {render.tok(um['saved'])} tok, never "
                 "redistributed)")
    if kiro_route:
        foot.caveat(kiro_route)
    tail = foot.render()
    return f"{out}\n\n{tail}" if tail else out


def render_csv(data: dict) -> str:
    """CSV over the same rows the text view groups — **untruncated, no `has_gfx`
    filter** (CSV never gates). Column contract: `docs/FORMULAS.md` § graphify-chats."""
    from cage import csvout
    head = ["chat", "agent", "surface", "session", "receipts", "tokens",
            "without_graphify", "saved", "raw_alternative", "actual", "pct",
            "method", "confidence"]
    rows = []
    for r in data["rows"]:
        has, cred = r["has_gfx"], r["from_credits"]
        rows.append([
            r["title"], r["agent"], r["surface"], r["session"],
            r["receipts"] if has else None,
            None if cred else r["tokens"],
            None if (cred or not has) else r["without"],
            r["saved"] if has else None,
            r["raw_alternative"] if has else None,
            r["actual"] if has else None,
            r["pct"] if (has and not cred and r["pct"] is not None) else None,
            r["method"] if has else None,
            r["confidence"] if has else None,
        ])
    return csvout.table(head, rows)
