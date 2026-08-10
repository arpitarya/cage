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

**The `agent%` column (CHATS-AUTHOR)** joins one more append-only file: per chat, the
share of *evidenced* landed lines — `agent_lines / (agent_lines + residual_lines)`
summed over the provenance rows sharing this chat's `(agent, session)`. It is **read,
never re-derived**: no matcher runs at render, no git call happens, and the counts are
whatever `authorcapture` recorded (a second matcher would be free to disagree with the
one that wrote the row — §2.14's stated mistake).

That makes `provenance.jsonl` the **second** scoped carve-out to `manifest.py`'s
"never read by a derived view" contract, and it holds on the same terms as the first:
counts only, and deleting the file moves **zero** pre-existing cell — only the new
authorship cells fall to `—`. Pinned by `tests/test_chats.py`.

The scope is narrower than it looks and the footnote says so: the denominator is the
matchable lines in files *this chat proposed*. Lines in files no session proposed are
`commitview`'s `unattributed` — commit-scoped, structurally outside this denominator,
never redistributed into it. Per-chat there is also no diff to clamp against, so two
chats that proposed the same landed file each count its lines; **the commit view stays
the arbiter for any single sha**. No USD, no rate, no minutes ever touches this number
(the v0.36 law) — it never combines with `cost`.

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
from cage import authorcapture, creditprice, ledger, manifest, prices, report
from cage.constants import CHATS_DEFAULT_ROWS

KIRO_IDE_LABEL = "kiro (no session identity)"
_NO_SESSION = "(no session)"

# Why an `agent%` cell refuses. Each is a DIFFERENT fact with a different fix, so they
# are never merged into one bucket and never rendered as 0% — the whole point of the
# column is that "no evidence" and "the agent wrote none of it" are not the same claim.
COVERAGE = "coverage"        # this agent's store cannot be line-matched at all
NO_EVIDENCE = "no-evidence"  # nothing landed (or nothing matchable) to compute a share from
PRE_UPGRADE = "pre-upgrade"  # rows exist but all predate `residual_lines`


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


def _authorship_map(root: Path) -> dict[tuple[str, str], dict]:
    """`(agent, session_id) -> {agent_lines, residual_lines, rows, pre_upgrade}` from
    `provenance.jsonl` — the second money-independent carve-out (counts only, never a
    numeric money cell; pinned by `tests/test_chats.py`).

    **Both sides pass through `agents.row_surface`**, because they spell the same agent
    differently: a provenance row stamps `claude-code` (the ledger's raw agent) and a
    chat bucket keys on `claude` (the SURFACES name). One normalization function, used
    on both sides — never a second mapping.

    **The surface is deliberately not in the key.** Provenance rows carry none, so a
    count attaches to every bucket sharing `(agent, session)`; a session split across
    surfaces is footnoted at render rather than silently assigned to one of them.

    **Rows lacking `residual_lines` contribute to NEITHER sum** and are counted as
    `pre_upgrade` instead. They are frozen by `originrecord`'s idempotency key and can
    never be backfilled, so folding their `agent_lines` into the numerator with no
    denominator to match would inflate every mixed chat's percentage."""
    out: dict[tuple[str, str], dict] = {}
    for r in ledger.provenance(root):
        session = r.get("session_id") or ""
        if not session:
            continue  # nothing to join on — a row cage cannot place in a chat
        agent = _agents.row_surface(r.get("agent")) or r.get("agent") or "?"
        a = out.setdefault((agent, session), {"agent_lines": 0, "residual_lines": 0,
                                              "rows": 0, "pre_upgrade": 0})
        a["rows"] += 1
        if "residual_lines" not in r:
            a["pre_upgrade"] += 1      # presence of the key IS the version gate
            continue
        a["agent_lines"] += int(r.get("agent_lines", 0) or 0)
        a["residual_lines"] += int(r.get("residual_lines", 0) or 0)
    return out


def _authorship_cells(agent: str, auth: dict | None) -> dict:
    """One chat's authorship cells: the two counts, the share, and the refusal reason.

    Refusals are ordered by how *structural* they are — an agent whose store cannot be
    line-matched refuses for that reason even if rows somehow exist, because coverage is
    the fact the reader needs. `NO_EVIDENCE` deliberately covers two shapes that reduce
    to the same statement: no provenance row joined at all, and rows that joined but
    carry no matchable line (a commit of only binary files). Both mean *there is no
    landed code evidence to compute a share from* — neither means 0%."""
    cells = {"agent_lines": 0, "residual_lines": 0, "auth_rows": 0,
             "auth_pre_upgrade": 0, "agent_pct": None, "auth_refusal": ""}
    if agent in authorcapture.COVERAGE_GAPS:
        cells["auth_refusal"] = COVERAGE
        return cells
    if not auth or not auth["rows"]:
        cells["auth_refusal"] = NO_EVIDENCE
        return cells
    cells.update(agent_lines=auth["agent_lines"], residual_lines=auth["residual_lines"],
                 auth_rows=auth["rows"], auth_pre_upgrade=auth["pre_upgrade"])
    carrying = auth["rows"] - auth["pre_upgrade"]
    if not carrying:
        cells["auth_refusal"] = PRE_UPGRADE
        return cells
    total = auth["agent_lines"] + auth["residual_lines"]
    if not total:
        cells["auth_refusal"] = NO_EVIDENCE
        return cells
    cells["agent_pct"] = 100.0 * auth["agent_lines"] / total
    return cells


def _bucket_key(c: dict) -> tuple[str, str, str]:
    a = _agents.row_surface(c.get("agent")) or c.get("agent") or "?"
    return a, c.get("surface", ""), c.get("session", "")


def _new_bucket() -> dict:
    # `credits` starts at None, not 0.0 — the same absent-vs-recorded-zero distinction
    # the call field carries (`schema.make_call`). A chat where no request recorded a
    # credit renders `—`; a chat that recorded 0.0 renders `0.00`, and they are
    # different facts. `basis` tallies which ladder rung actually paid, per rung label,
    # so `priced_via` can name a mixed chat instead of picking a winner.
    return {"calls": 0, "tokens_in": 0, "cached_in": 0, "cache_write_in": 0,
            "tokens_out": 0, "premium": 0, "cost": 0.0, "unpriced_calls": 0,
            "unpriced_tokens": 0, "credits": None, "credits_calls": 0, "basis": {}}


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
        rec = creditprice.recorded(c)
        if rec is not None:
            b["credits"] = (b["credits"] or 0.0) + rec
            b["credits_calls"] += 1
        usd, match, _ = prices.call_usd_match(pol, c)
        if (basis := creditprice.via(match)):
            b["basis"][basis] = b["basis"].get(basis, 0) + 1
        if match == "none":
            b["unpriced_calls"] += 1
            b["unpriced_tokens"] += c.get("tokens_in", 0) + c.get("tokens_out", 0)
        else:
            b["cost"] += usd

    authorship = _authorship_map(root)
    # A session that appears under more than one surface: provenance carries no surface,
    # so its counts attach to every one of those buckets. Detected here so render can
    # footnote it rather than let a reader read two rows as independent evidence.
    per_session: dict[tuple[str, str], int] = {}
    for (a, _surf, session) in buckets:
        per_session[(a, session)] = per_session.get((a, session), 0) + 1

    rows: list[dict] = []
    for (a, surf, session), b in buckets.items():
        if a == "kiro" and surf == "ide":
            title, named = KIRO_IDE_LABEL, False
        else:
            name = names.get((a, session))
            title, named = (name or session or _NO_SESSION), bool(name)
        auth = _authorship_cells(a, authorship.get((a, session)))
        auth["auth_split"] = bool(auth["auth_rows"]) and per_session[(a, session)] > 1
        rows.append({"agent": a, "surface": surf, "session": session,
                     "title": title, "named": named, **b, **auth})
    if agent and agent != "all":
        rows = [r for r in rows if r["agent"] == agent]
    rows.sort(key=lambda r: (-r["tokens_in"], r["session"]))

    return {"since": since, "agent": agent, "rows": rows,
            "legacy_human": legacy_human,
            "unpriced_calls": sum(r["unpriced_calls"] for r in rows),
            "unpriced_tokens": sum(r["unpriced_tokens"] for r in rows),
            "any_calls": bool(raw_calls),
            "credit_agents": _credit_agents(root)}


def _credit_agents(root: Path) -> list[str]:
    """Agents whose usage this ledger records as **credits** rather than token calls
    (`ledger.credits` — kiro CLI today), normalized to their SURFACES name.

    A **third** money-independent carve-out, on the same terms as the manifest-title and
    provenance-count ones: it is read for a *refusal*, never for a cell. Nothing here
    enters `rows`, no total moves, and deleting every credits shard changes no number in
    this view — it only removes cage's ability to say *why* an agent is absent.

    That "why" is the whole point. A credits row has no `tokens_in`/`tokens_out` and no
    call at all (`schema.make_credit` — a call with `tokens_in=0` would be a lie), so an
    agent recorded that way can never produce a chat row. Without this read the view says
    *your filter matched nothing*, which reads as *you have no kiro usage* — and the
    ledger sitting right there says otherwise. Absent-because-structural and
    absent-because-empty are different facts, and cage never merges them."""
    seen: dict[str, None] = {}
    for row in ledger.credits(root):
        a = _agents.row_surface(row.get("agent")) or row.get("agent") or ""
        if a:
            seen.setdefault(a, None)
    return sorted(seen)


# ── rendering ────────────────────────────────────────────────────────────────

_EMPTY = """No chats recorded yet.

next: cage import        pull every agent's usage into the ledger
      cage doctor        check capture is wired and healthy"""


def _structural_reasons(data: dict, kiro_route: str) -> list[str]:
    """Why this view is empty for reasons a *filter* did not cause — each one a fact
    about where the rows live or what shape they were recorded in, evidenced from the
    ledger rather than asserted.

    Order is by how completely the reason explains the emptiness: a row shape that can
    never produce a chat comes before a sink that merely holds the rows elsewhere.

    Only reasons that apply to the **agent actually asked about** are listed. An
    unfiltered empty view names every one it can see; `--agent copilot` is never told
    about kiro."""
    agent = data.get("agent") or "all"
    want = None if agent == "all" else agent
    out = []
    for a in data.get("credit_agents") or []:
        if want in (None, a):
            out.append(
                f"· {a}'s conversations are recorded as credits, not token calls — that\n"
                f"  store reports no tokens at all, so those rows carry no call and no\n"
                f"  chat row can exist for them (`cage query copilot-credits`)")
    if kiro_route and want in (None, "kiro"):
        out.append(kiro_route)
    return out


def _render_empty(data: dict, kiro_route: str = "") -> str:
    """The empty view. **The filter is blamed only when the filter is the reason.**

    `No chats match agent 'kiro' — the filter is empty, not the ledger` is a true
    sentence about the filter and a misleading one about kiro: its IDE rows are a
    machine fact routed to another sink (ADR 0006) and its CLI conversations are credit
    rows that structurally cannot become chats. Both are things cage knows. Saying
    *filter* when the answer is *architecture* sends a reader to check their typing
    instead of the ledger they actually want — the same class of failure as an agent
    showing no rows because capture silently broke."""
    filters = []
    if data.get("since"):
        filters.append(f"since {data['since']}")
    if data.get("agent") and data["agent"] != "all":
        filters.append(f"agent '{data['agent']}'")
    label = " · ".join(filters)
    if (reasons := _structural_reasons(data, kiro_route)):
        head = (f"No chats for {label} — and the filter is not the reason:"
                if filters else "No chats to show — the ledger has usage cage cannot "
                                "render as a chat:")
        return (f"{head}\n\n" + "\n".join(reasons) + "\n\n"
                "next: cage report                         where that usage IS counted")
    if data.get("any_calls") and filters:
        return (f"No chats match {label} — the filter is empty, "
                "not the ledger.\n\n"
                "next: cage insights chats                 the unfiltered view")
    return _EMPTY


def _short(session: str) -> str:
    return session if len(session) <= 12 else session[:12] + "…"


def _label(r: dict) -> str:
    if r["named"] or r["title"] in (KIRO_IDE_LABEL, _NO_SESSION):
        return r["title"]
    return _short(r["title"])  # an untitled fallback is the raw session id — shorten it


def _credits_cell(b: dict) -> str:
    """The billed-credits cell: `—` when this chat recorded none, else the 2dp sum.

    `—` reads as *not recorded*, which is the honest statement for a store that only
    persists credits on some requests (and for claude/kiro, which never do). It is
    deliberately NOT `0.00` — a recorded zero is a real billing fact and gets that cell
    to itself. The dash never reaches CSV (`render_csv` emits an empty cell)."""
    from cage.display import DASH
    return DASH if b.get("credits") is None else creditprice.fmt(b["credits"])


def _agent_cell(b: dict) -> str:
    """The `agent%` cell: `—` on any refusal, else the share as a whole percent.

    **`—` never means 0%** — a refusal and a measured zero are different claims, and
    every refusal shape carries its reason in the footer. A real `0%` (the chat's
    proposals landed in files whose matchable lines all came from somewhere else) does
    render as `0%`, which is why the dash must never be spent on absence of evidence."""
    from cage.display import DASH
    pct = b.get("agent_pct")
    return DASH if pct is None else f"{round(pct)}%"


def _cost_cell(b: dict) -> str:
    from cage import render
    from cage.display import DASH
    if b["unpriced_calls"] and b["unpriced_calls"] == b["calls"] and not b["cost"]:
        return DASH
    cell = render.usd(b["cost"])
    if b["unpriced_calls"]:
        cell += f" (+{b['unpriced_calls']} unpriced)"
    return cell


def _authorship_footer(foot, shown: list[dict]) -> None:
    """Every `agent%` line below the table: the scope sentence, then one line per
    refusal shape actually present. A refusal that renders `—` and explains nothing is
    the failure this whole column is trying to avoid, so each shape gets its reason,
    counted — and the coverage reason is `authorcapture.coverage_note()` verbatim, never
    re-worded here (one phrasing, one owner, like `netsaved.GROSS_NOTE`)."""
    if any(r.get("agent_pct") is not None for r in shown):
        foot.footnote("· agent% is the share of evidenced lines in files this chat "
                      "touched — not a share of the chat's work; lines in files no "
                      "chat proposed belong to no chat (`cage query agent-authorship`)")
    if any(r.get("auth_refusal") == COVERAGE for r in shown):
        foot.gap(f"· agent% `—` for {authorcapture.coverage_note()}")
    if (n := sum(1 for r in shown if r.get("auth_refusal") == NO_EVIDENCE)):
        foot.gap(f"· {n} chat(s) show agent% `—`: no landed code evidence — not "
                 "committed yet, committed in another repo, or nothing matchable "
                 "landed. `—` is never 0%")
    pre = sum(r.get("auth_pre_upgrade", 0) for r in shown)
    if pre:
        foot.gap(f"· {pre} provenance row(s) predate residual counts — excluded "
                 "(frozen rows are never backfilled)")
    if any(r.get("auth_split") for r in shown):
        foot.caveat("· a provenance row carries no surface, so a session split across "
                    "surfaces attaches its authorship counts to every one of its rows "
                    "— those rows are not independent evidence")


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
        return _render_empty(data, kiro_route)
    limit = None if show_all else CHATS_DEFAULT_ROWS
    shown = rows if limit is None else rows[:limit]
    cut = 0 if limit is None else max(0, len(rows) - limit)

    head = ["chat", "agent", "surface", "calls", "tokens_in", "cached_in",
            "cache_write", "tokens_out", "premium", "credits", "agent%"]
    if disp.usd:
        head.append("cost")
    rights = set(range(3, len(head)))

    table_rows = []
    for r in shown:
        cells = [_label(r), r["agent"], r["surface"] or "—", render.tok(r["calls"]),
                 render.tok(r["tokens_in"]), render.tok(r["cached_in"]),
                 render.tok(r["cache_write_in"]), render.tok(r["tokens_out"]),
                 render.tok(r["premium"]), _credits_cell(r), _agent_cell(r)]
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
    if any(r["credits"] is not None for r in shown):
        foot.footnote("· cost basis per row: credits×rate where recorded, else "
                      "token×table (`—` = not recorded) — `cage query copilot-credits`")
    _authorship_footer(foot, shown)
    if data.get("legacy_human"):
        n = data["legacy_human"]
        foot.caveat(f"· {n} legacy human-axis row(s) excluded — the agent-vs-human "
                    "axis was removed in v0.36 (`cage query savings-axis`)")
    if any(r["agent"] == "kiro" and r["surface"] == "ide" for r in rows):
        foot.caveat("· kiro (no session identity): its IDE log stamps every run under "
                    "the same constant session, so all of kiro's chats collapse into "
                    "this one row (`cage query kiro-routing`)")
    if (credit := data.get("credit_agents")):
        # No-silent-omission: this ledger holds usage that structurally cannot become a
        # chat row, and a table that just doesn't show it reads as "there is none".
        foot.gap(f"· {' · '.join(credit)} usage recorded as credits carries no calls, "
                 f"so it has no\n  chat row here — `cage report` counts it "
                 f"(`cage query copilot-credits`)")
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
            "cache_write_in", "tokens_out", "premium", "credits", "agent_lines",
            "residual_lines", "agent_pct", "cost_usd", "priced_via", "unpriced_calls",
            "unpriced_tokens", "method"]
    rows = [[r["title"], r["agent"], r["surface"], r["session"], r["calls"],
             r["tokens_in"], r["cached_in"], r["cache_write_in"], r["tokens_out"],
             r["premium"], "" if r["credits"] is None else round(r["credits"], 6),
             *_authorship_csv(r),
             round(r["cost"], 6), creditprice.basis_of(r["basis"]), r["unpriced_calls"],
             r["unpriced_tokens"], creditprice.method_for(r["basis"])]
            for r in data["rows"]]
    return csvout.table(head, rows)


def _authorship_csv(r: dict) -> tuple:
    """`(agent_lines, residual_lines, agent_pct)` for one CSV row.

    **All three go empty on a refusal**, not just the percentage — the same
    empty-not-dash rule `credits` follows, applied to the counts as well because a
    refused chat's counts are `0` only in the sense that no row exists to count. Writing
    `0,0` for a copilot chat would put the very claim the text `—` refuses to make
    (*this agent wrote none of it*) into a machine-readable cell.

    `agent_pct` is 0–100 with 1dp — the text column's own scale, one decimal finer, the
    same text-rounds/CSV-carries split `credits` uses. (`csvout.cell` then trims a
    cosmetic trailing zero, as it does for every float cage emits.)"""
    if r.get("auth_refusal"):
        return "", "", ""
    return r["agent_lines"], r["residual_lines"], round(r["agent_pct"], 1)
