"""`cage insights chats` — one row per chat, titled where the store has a title
(proposal `docs/archive/v0.42-chats-view.proposal.md`, handoff
`docs/archive/v0.42-chats-view.handoff.md`).

The differentiating question no cost dashboard answers per-*chat*: which conversation
spent the tokens, and (where the store carries a title) what was it about? The
substrate already carries everything numeric — `session`, `agent`, `surface`,
`tokens_in`, `tokens_out`, `cached_in`, `cache_write_in`, `premium` are all call-row
fields (plan §3.1) — so this is pure derive, no substrate change.

**Mechanism (the proposal's five steps, binding):**

1. Read the ledger's calls (`ledger.calls`, `--since` month-partition skip like
   `report`), dropping legacy-human rows (`report._is_legacy_human` — counted,
   footnoted; calls never actually carry `tool`/`unit`, so this only fires against a
   hand-crafted legacy row, but the predicate is applied uniformly with every other
   money view rather than assumed absent).
2. Group by `(agent, surface, session)` — the same bucket key
   `importcmd._write_manifest` uses. Sum tokens/cached/cache-write/premium; reprice
   per call via `prices.call_usd_match` (UNPRICED counted per row, never $0).
3. Label — join `session → session_name` from `imports.jsonl`, **labels only** (the
   one carve-out `manifest.py`'s docstring now documents). No name ⇒ the session id.
   Kiro-IDE stamps a constant `session="kiro"`, so every kiro-IDE run already
   collapses into ONE bucket by construction; its label is the honest
   `"kiro (no session identity)"`, never the literal id.
4. Rank & bound — `tokens_in` desc, then session id (deterministic). Top-20
   (`constants.CHATS_DEFAULT_ROWS`) by default; the cut count is footnoted
   (no-silent-caps law), `--all` lifts it. Ranking/truncation is a render-time
   concern — `summarize()` returns every row so `--all` can never perturb a number.
5. Render — text via `display.Display`/`Footer` (`--usd` adds the cost column; tokens
   are the default view); `--csv` from the same rows, untruncated (CSV never gates).

**Known honesty limits, stated not fixed** (proposal): a manifest row is written only
when a sweep *appends* rows for that session, so a chat renamed after its last new
call keeps its stale title. Legacy (pre-manifest) sessions have no name row at all —
id display, never backfilled. Kiro-CLI conversations are recorded as *credits*
(`ledger.credits`), a different row shape with no `tokens_in`/`tokens_out` — they
carry no calls at all, so they do not appear here (out of scope for v1, same as
Copilot's uncaptured cached/credits columns — COPILOT-CREDITS owns those).

**Local-only by construction:** no `--team`, no manifest data leaves this machine.
"""
from __future__ import annotations

from pathlib import Path

from cage import agents as _agents
from cage import ledger, manifest, prices, report
from cage.constants import CHATS_DEFAULT_ROWS

KIRO_IDE_LABEL = "kiro (no session identity)"
_NO_SESSION = "(no session)"


def _title_map(root: Path) -> dict[tuple[str, str], str]:
    """`(agent, session) -> session_name`, last-write-wins across `imports.jsonl`'s
    append-only rows — the ONE money-independent carve-out (`manifest.py`'s
    docstring). A row with no name contributes nothing, so the caller's session-id
    fallback stands; fail-open (a missing/corrupt manifest is `manifest.read`'s own
    concern — this just sees fewer/no names)."""
    names: dict[tuple[str, str], str] = {}
    for row in manifest.read(root):
        if row.get("kind") != "import":
            continue
        name = row.get("session_name")
        if not name:
            continue
        names[(row.get("agent", ""), row.get("session", ""))] = name
    return names


def _bucket_key(c: dict) -> tuple[str, str, str]:
    a = _agents.row_surface(c.get("agent")) or c.get("agent") or "?"
    return a, c.get("surface", ""), c.get("session", "")


def _new_bucket() -> dict:
    return {"calls": 0, "tokens_in": 0, "cached_in": 0, "cache_write_in": 0,
            "tokens_out": 0, "premium": 0, "cost": 0.0, "unpriced_calls": 0,
            "unpriced_tokens": 0}


def summarize(root: Path, pol: dict, since: str | None = None,
             agent: str | None = None) -> dict:
    """The one data structure every renderer consumes (the same-numbers-by-
    construction rule) — deterministic, and **untruncated**: ranking/bounding is a
    render-time concern (`--all`) so it can never perturb a numeric cell."""
    raw_calls = ledger.calls(root)
    calls = ledger.since(ledger.calls(root, since=since), since) if since else raw_calls
    names = _title_map(root)
    buckets: dict[tuple[str, str, str], dict] = {}
    legacy_human = 0
    for c in calls:
        if report._is_legacy_human(c):
            legacy_human += 1
            continue
        b = buckets.setdefault(_bucket_key(c), _new_bucket())
        b["calls"] += 1
        b["tokens_in"] += c.get("tokens_in", 0)
        b["cached_in"] += c.get("cached_in", 0)
        b["cache_write_in"] += c.get("cache_write_in", 0)
        b["tokens_out"] += c.get("tokens_out", 0)
        b["premium"] += c.get("premium", 0)
        usd, match, _ = prices.call_usd_match(pol, c)
        if match == "none":
            b["unpriced_calls"] += 1
            b["unpriced_tokens"] += c.get("tokens_in", 0) + c.get("tokens_out", 0)
        else:
            b["cost"] += usd

    rows: list[dict] = []
    for (a, surf, session), b in buckets.items():
        if a == "kiro" and surf == "ide":
            title, named = KIRO_IDE_LABEL, False
        else:
            name = names.get((a, session))
            title, named = (name or session or _NO_SESSION), bool(name)
        rows.append({"agent": a, "surface": surf, "session": session,
                     "title": title, "named": named, **b})
    if agent and agent != "all":
        rows = [r for r in rows if r["agent"] == agent]
    rows.sort(key=lambda r: (-r["tokens_in"], r["session"]))

    return {"since": since, "agent": agent, "rows": rows,
            "legacy_human": legacy_human,
            "unpriced_calls": sum(r["unpriced_calls"] for r in rows),
            "unpriced_tokens": sum(r["unpriced_tokens"] for r in rows),
            "any_calls": bool(raw_calls)}


# ── rendering ────────────────────────────────────────────────────────────────

_EMPTY = """No chats recorded yet.

next: cage import        pull every agent's usage into the ledger
      cage doctor        check capture is wired and healthy"""


def _render_empty(data: dict) -> str:
    filters = []
    if data.get("since"):
        filters.append(f"since {data['since']}")
    if data.get("agent") and data["agent"] != "all":
        filters.append(f"agent '{data['agent']}'")
    if data.get("any_calls") and filters:
        return (f"No chats match {' · '.join(filters)} — the filter is empty, "
                "not the ledger.\n\n"
                "next: cage insights chats                 the unfiltered view")
    return _EMPTY


def _short(session: str) -> str:
    return session if len(session) <= 12 else session[:12] + "…"


def _label(r: dict) -> str:
    if r["named"] or r["title"] in (KIRO_IDE_LABEL, _NO_SESSION):
        return r["title"]
    return _short(r["title"])  # an untitled fallback is the raw session id — shorten it


def _cost_cell(b: dict) -> str:
    from cage import render
    from cage.display import DASH
    if b["unpriced_calls"] and b["unpriced_calls"] == b["calls"] and not b["cost"]:
        return DASH
    cell = render.usd(b["cost"])
    if b["unpriced_calls"]:
        cell += f" (+{b['unpriced_calls']} unpriced)"
    return cell


def render_chats(data: dict, disp=None, show_all: bool = False,
                 kiro_route: str = "") -> str:
    """The text table (spec: tokens by default, `--usd` adds cost). ``kiro_route`` is
    the already-computed `report.kiro_routed_line` (read at the CLI boundary, like
    `report.render_report`) — why a project view shows no kiro-IDE rows (ADR 0006)."""
    from cage import display as _d
    from cage import render
    disp = disp or _d.DEFAULT
    rows = data["rows"]
    if not rows:
        return _render_empty(data)
    limit = None if show_all else CHATS_DEFAULT_ROWS
    shown = rows if limit is None else rows[:limit]
    cut = 0 if limit is None else max(0, len(rows) - limit)

    head = ["chat", "agent", "surface", "calls", "tokens_in", "cached_in",
            "cache_write", "tokens_out", "premium"]
    if disp.usd:
        head.append("cost")
    rights = set(range(3, len(head)))

    table_rows = []
    for r in shown:
        cells = [_label(r), r["agent"], r["surface"] or "—", render.tok(r["calls"]),
                 render.tok(r["tokens_in"]), render.tok(r["cached_in"]),
                 render.tok(r["cache_write_in"]), render.tok(r["tokens_out"]),
                 render.tok(r["premium"])]
        if disp.usd:
            cells.append(_cost_cell(r))
        table_rows.append(cells)

    title = "Chats"
    if data.get("agent") and data["agent"] != "all":
        title += f" · agent {data['agent']}"
    if data.get("since"):
        title += f" · since {data['since']}"
    if disp.usd:
        title += " · usd"
    out = f"{title}\n\n" + render.table(head, table_rows, rights=rights)

    foot = _d.Footer()
    if cut:
        foot.gap(f"· {cut} more chat(s) — --all to show")
    if data.get("legacy_human"):
        n = data["legacy_human"]
        foot.caveat(f"· {n} legacy human-axis row(s) excluded — the agent-vs-human "
                    "axis was removed in v0.36 (`cage query savings-axis`)")
    if any(r["agent"] == "kiro" and r["surface"] == "ide" for r in rows):
        foot.caveat("· kiro (no session identity): its IDE log stamps every run under "
                    "the same constant session, so all of kiro's chats collapse into "
                    "this one row (`cage query kiro-routing`)")
    if kiro_route:
        foot.caveat(kiro_route)
    if data.get("unpriced_calls"):
        if disp.usd:
            foot.warn(report.unpriced_line({"_": {"calls": data["unpriced_calls"],
                                                   "tokens": data["unpriced_tokens"]}}))
        else:
            n = data["unpriced_calls"]
            foot.gap(f"· {n} call{'s' if n != 1 else ''} unpriced — matters when you "
                     f"view $ (`--usd`; cage prices unpriced)")
    tail = foot.render()
    return f"{out}\n\n{tail}" if tail else out


def render_csv(data: dict) -> str:
    """CSV over the same rows the text view groups — one structure, two renderers.
    **Untruncated** (CSV never gates, `--all` is a text-only concern); ``chat`` is the
    full, unshortened label. Column contract: docs/FORMULAS.md § chats-view."""
    from cage import csvout
    head = ["chat", "agent", "surface", "session", "calls", "tokens_in", "cached_in",
            "cache_write_in", "tokens_out", "premium", "cost_usd", "unpriced_calls",
            "unpriced_tokens", "method"]
    rows = [[r["title"], r["agent"], r["surface"], r["session"], r["calls"],
             r["tokens_in"], r["cached_in"], r["cache_write_in"], r["tokens_out"],
             r["premium"], round(r["cost"], 6), r["unpriced_calls"],
             r["unpriced_tokens"], "measured"]
            for r in data["rows"]]
    return csvout.table(head, rows)
