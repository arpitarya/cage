"""`cage insights chats` — one row per chat, titled where the store has a title
(proposal `work/archive/v0.42-chats-view.proposal.md`, handoff
`work/archive/v0.42-chats-view.handoff.md`).

The differentiating question no usage dashboard answers per-*chat*: which conversation
used the tokens, and (where the store carries a title) what was it about? The
substrate already carries everything numeric — `session`, `agent`, `surface`,
`tokens_in`, `tokens_out`, `cached_in`, `cache_write_in`, `credits` are all call-row
fields (plan §3.1) — so this is pure derive, no substrate change.

**Mechanism (the proposal's five steps, binding):**

1. Read the ledger's calls (`ledger.calls`, `--since` month-partition skip like
   `report`), dropping legacy-human rows (`report._is_legacy_human` — counted,
   footnoted; calls never actually carry `tool`/`unit`, so this only fires against a
   hand-crafted legacy row, but the predicate is applied uniformly with every other
   view rather than assumed absent).
2. Group by `(agent, surface, session)` — the same bucket key
   `importcmd._write_manifest` uses. Sum tokens/cached/cache-write, and carry
   `credits` as a COUNT (never priced — USAGE-ONLY, ADR 0011).
3. Label — join `session → session_name` from `imports.jsonl`, **labels only** (the
   one carve-out `manifest.py`'s docstring now documents). No name ⇒ the session id.
   Kiro-IDE stamps a constant `session="kiro"`, so every kiro-IDE run already
   collapses into ONE bucket by construction; its label is the honest
   `"kiro (no session identity)"`, never the literal id.
4. Rank & bound — `tokens_in` desc, then session id (deterministic). Top-20
   (`constants.CHATS_DEFAULT_ROWS`) by default; the cut count is footnoted
   (no-silent-caps law), `--all` lifts it. Ranking/truncation is a render-time
   concern — `summarize()` returns every row so `--all` can never perturb a number.
5. Render — text via `display.Display`/`Footer`; `--csv` from the same rows,
   untruncated (CSV never gates).

**The two units, and the two absences** (`units.py`): tokens and credits are both
recorded counts, and neither exists for all three agents — claude records no credit
unit at all, kiro has no IDE token store. Each absence renders `—` **with its own
reason** in the footer, never a `0`, because the two are different kinds of fact (a
vendor law vs. a missing file). And **credits are never summed across agents**: a
copilot credit is GitHub's tokens×rates figure, a kiro credit is an AWS credit. The
view states that outright when both are on screen (`units.cross_agent_note`).

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
the arbiter for any single sha**. No rate and no minutes ever touches this number (the
v0.36 law), and since ADR 0011 there is no currency in this view to combine with.

**Known honesty limits, stated not fixed** (proposal): a manifest row is written only
when a sweep *appends* rows for that session, so a chat renamed after its last new
call keeps its stale title. Legacy (pre-manifest) sessions have no name row at all —
id display, never backfilled.

**Kiro-CLI conversations are `credits` rows, not calls (CHATS-CREDITS)** — a
different row shape with no `tokens_in`/`tokens_out` (`schema.make_credit`), read
from `ledger.credits` and bucketed the same way as a call chat: one row per
`(agent, surface, session)`, still independent in the direction that matters — a
credits row can never perturb a *token cell that belongs to a call chat*, it only ever
adds a row of its own. Rendered with `calls` and all four token cells `—` (text) /
empty (CSV) and `credits` filled. No manifest row exists for a
kiro-CLI conversation today, so its title always falls back to the session id
(`named=False`) — a future store-side title is a follow-up, not this change.

**Local-only by construction:** no `--team`, no manifest data leaves this machine.
"""
from __future__ import annotations

from pathlib import Path

from cage import agents as _agents
from cage import authorcapture, ledger, manifest, report, units
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


def _bucket_key(c: dict, *, credits: bool = False) -> tuple[str, str, str, bool]:
    """The chat bucket key. The trailing ``credits`` flag keeps a credits-row bucket
    structurally apart from a call bucket sharing the same `(agent, surface, session)`
    — today that overlap cannot happen (kiro-CLI records credits *instead of* calls),
    but the discriminator means a future agent that records both shapes for the same
    conversation gets two rows, never one bucket silently blending both axes."""
    a = _agents.row_surface(c.get("agent")) or c.get("agent") or "?"
    return a, c.get("surface", ""), c.get("session", ""), credits


def _new_bucket() -> dict:
    # `credits` starts at None, not 0.0 — the same absent-vs-recorded-zero distinction
    # the call field carries (`schema.make_call`). A chat where no request recorded a
    # credit renders `—`; a chat that recorded 0.0 renders `0.00`, and they are
    # different facts.
    # `premium` is still summed and still in the payload (so `--json`, the raw-data
    # surface, keeps the recorded fact) but is rendered by neither table — precision in
    # the data, brevity in the display, the same split shas already follow.
    # `from_credits` marks a bucket built from a `ledger.credits` row rather than a
    # call: it never mixes with a call bucket (the key discriminator above), and every
    # renderer reads this flag to dash the token cells instead of printing a lying 0.
    return {"calls": 0, "tokens_in": 0, "cached_in": 0, "cache_write_in": 0,
            "tokens_out": 0, "premium": 0, "credits": None, "credits_calls": 0,
            "from_credits": False}


def summarize(root: Path, pol: dict, since: str | None = None,
             agent: str | None = None) -> dict:
    """The one data structure every renderer consumes (the same-numbers-by-
    construction rule) — deterministic, and **untruncated**: ranking/bounding is a
    render-time concern (`--all`) so it can never perturb a numeric cell."""
    raw_calls = ledger.spend(root)
    calls = ledger.since(ledger.spend(root, since=since), since) if since else raw_calls
    raw_credits = ledger.credits(root)
    credit_rows = (ledger.since(ledger.credits(root, since=since), since)
                  if since else raw_credits)
    names = _title_map(root)
    buckets: dict[tuple[str, str, str, bool], dict] = {}
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
        # A recorded credit is kept as a COUNT, verbatim. The None sentinel is
        # preserved: absent and a recorded 0.0 are different billing facts.
        rec = c.get("credits")
        if rec is not None and not isinstance(rec, bool) and isinstance(rec, (int, float)):
            b["credits"] = (b["credits"] or 0.0) + float(rec)
            b["credits_calls"] += 1

    # Credits rows (kiro-CLI conversations, CHATS-CREDITS): a separate bucket, never
    # folded into a call bucket's token sums — the discriminator in `_bucket_key`
    # guarantees that even if a future agent's session id collided with a call chat's.
    for cr in credit_rows:
        b = buckets.setdefault(_bucket_key(cr, credits=True), _new_bucket())
        b["from_credits"] = True
        cred = cr.get("credits")
        if isinstance(cred, bool) or not isinstance(cred, (int, float)):
            continue
        b["credits"] = (b["credits"] or 0.0) + float(cred)

    authorship = _authorship_map(root)
    # A session that appears under more than one surface: provenance carries no surface,
    # so its counts attach to every one of those buckets. Detected here so render can
    # footnote it rather than let a reader read two rows as independent evidence.
    per_session: dict[tuple[str, str], int] = {}
    for (a, _surf, session, _cred) in buckets:
        per_session[(a, session)] = per_session.get((a, session), 0) + 1

    rows: list[dict] = []
    for (a, surf, session, _cred), b in buckets.items():
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
    # Credits never enter the rank arithmetic on the same axis as tokens — they are a
    # second, independent sort key, never summed or blended with `tokens_in`. A
    # credits-only chat sorts below every token-bearing chat (tokens_in=0 there) and
    # among its own kind by credits desc.
    rows.sort(key=lambda r: (-r["tokens_in"], -(r["credits"] or 0.0), r["session"]))

    return {"since": since, "agent": agent, "rows": rows,
            "legacy_human": legacy_human,
            # The agents actually present, so a renderer can apply the cross-agent
            # credit law (`units.summable`) without re-deriving the set.
            "agents_present": sorted({r["agent"] for r in rows if r["agent"]}),
            "any_calls": bool(raw_calls) or bool(raw_credits)}


# ── rendering ────────────────────────────────────────────────────────────────

_EMPTY = """No chats recorded yet.

next: cage import        pull every agent's usage into the ledger
      cage doctor        check capture is wired and healthy"""


def _structural_reasons(data: dict, kiro_route: str) -> list[str]:
    """Why this view is empty for reasons a *filter* did not cause — each one a fact
    about where the rows live or what shape they were recorded in, evidenced from the
    ledger rather than asserted.

    Only reasons that apply to the **agent actually asked about** are listed. An
    unfiltered empty view names every one it can see; `--agent copilot` is never told
    about kiro.

    Kiro-CLI credits used to have a reason here (their rows carried no call at all, so
    no chat row could exist for them) — CHATS-CREDITS removed that limit by giving a
    credits row its own bucket, so the only structural reason left is kiro-IDE's ADR
    0006 routing to another ledger entirely."""
    agent = data.get("agent") or "all"
    want = None if agent == "all" else agent
    out = []
    if kiro_route and want in (None, "kiro"):
        out.append(kiro_route)
    return out


def _render_empty(data: dict, kiro_route: str = "") -> str:
    """The empty view. **The filter is blamed only when the filter is the reason.**

    `No chats match agent 'kiro' — the filter is empty, not the ledger` is a true
    sentence about the filter and a misleading one about kiro-IDE: those rows are a
    machine fact routed to another sink (ADR 0006), a thing cage knows and can say.
    Saying *filter* when the answer is *architecture* sends a reader to check their
    typing instead of the ledger they actually want — the same class of failure as an
    agent showing no rows because capture silently broke. (Kiro-CLI conversations used
    to carry a second structural reason here — CHATS-CREDITS gave their credits rows a
    real chat row instead, so that reason is gone; an empty `--agent kiro` view now
    means only the IDE sink, or an ordinary empty filter.)"""
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
    """The billed-credits cell: `—` when this chat has no credits, else the 2dp sum.

    Two different `—`s live here and the footer distinguishes them (`units.ABSENT`):
    an agent that records **no credit unit at all** (claude) versus a chat on an agent
    that does, which simply recorded none. Both are `—` in the cell — there is one
    column width — but never `0.00`: a recorded zero is a real billing fact and gets
    that cell to itself. The dash never reaches CSV (`render_csv` emits an empty
    cell)."""
    from cage.display import DASH
    if b.get("credits") is None:
        return DASH
    return f"{b['credits']:,.2f}"


def _agent_cell(b: dict) -> str:
    """The `agent%` cell: `—` on any refusal, else the share as a whole percent.

    **`—` never means 0%** — a refusal and a measured zero are different claims, and
    every refusal shape carries its reason in the footer. A real `0%` (the chat's
    proposals landed in files whose matchable lines all came from somewhere else) does
    render as `0%`, which is why the dash must never be spent on absence of evidence."""
    from cage.display import DASH
    pct = b.get("agent_pct")
    return DASH if pct is None else f"{round(pct)}%"


def _num_cell(r: dict, field: str) -> str:
    """A token/call cell: `—` for a credits-only chat (it has none, not a recorded
    zero), else the plain count. The same absence-vs-zero rule `_credits_cell` follows,
    applied to the other direction — a call-based chat's `0` stays a real `0`."""
    from cage import render
    from cage.display import DASH
    return DASH if r.get("from_credits") else render.tok(r[field])


def _unit_absence_notes(shown: list[dict]) -> list[str]:
    """One footer line per (agent, unit) absence actually on screen, in the unit
    policy's own words (`units.ABSENT`).

    **The two absences must not read alike** — claude having no credit concept is a
    vendor law; kiro having no IDE token store is a missing file a future release can
    ship. A shared `—` in the cell is a column-width fact; the *reason* is what tells
    the two apart, and it is why neither renders as `0`."""
    seen = {r["agent"] for r in shown if r.get("agent")}
    out = []
    for agent in sorted(seen):
        for unit in units.UNITS:
            reason = units.absent_reason(agent, unit)
            if reason:
                out.append(f"· {agent} {unit}: — ({reason})")
    return out


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
    """The text table (tokens and credits — the two units cage records). ``kiro_route`` is
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

    # No `premium` column (COPILOT-PREMIUM-DEAD, closed 2026-08-11). It is
    # `floor(credits)` — the SAME counter, read as an int — so it sat next to `credits`
    # as a **lossy duplicate**: `totalPremiumRequests` is fractional in every real sample
    # (0.33), `int()` floors it and `make_call`'s `if premium:` drops the key, so the
    # column printed `0` for every row cage writes today and would merely round the
    # column beside it when it did not. The FIELD is untouched — it is a recorded
    # provider fact on append-only rows, and narrowing the substrate to delete it would
    # lose that. A field with no display is fine; a column that can only mislead is not.
    head = ["chat", "agent", "surface", "calls", "tokens_in", "cached_in",
            "cache_write", "tokens_out", "credits", "agent%"]
    rights = set(range(3, len(head)))

    table_rows = []
    for r in shown:
        cells = [_label(r), r["agent"], r["surface"] or "—", _num_cell(r, "calls"),
                 _num_cell(r, "tokens_in"), _num_cell(r, "cached_in"),
                 _num_cell(r, "cache_write_in"), _num_cell(r, "tokens_out"),
                 _credits_cell(r), _agent_cell(r)]
        table_rows.append(cells)

    title = "Chats"
    if data.get("agent") and data["agent"] != "all":
        title += f" · agent {data['agent']}"
    if data.get("since"):
        title += f" · since {data['since']}"
    out = f"{title}\n\n" + render.table(head, table_rows, rights=rights)

    foot = _d.Footer()
    if cut:
        foot.gap(f"· {cut} more chat(s) — --all to show")
    for line in _unit_absence_notes(shown):
        foot.footnote(line)
    # THE CROSS-AGENT LAW (units.py): a credits column spanning two agents is two
    # different units sharing a heading. The column stays — per-chat credits are each
    # correct — but the view says outright that they do not add up, so no reader (and
    # no agent relaying this table) totals them.
    _credit_agents = {r["agent"] for r in shown
                      if r.get("credits") is not None and r.get("agent")}
    if not units.summable(units.CREDITS, _credit_agents):
        foot.caveat(units.cross_agent_note(_credit_agents))
    _authorship_footer(foot, shown)
    if data.get("legacy_human"):
        n = data["legacy_human"]
        foot.caveat(f"· {n} legacy human-axis row(s) excluded — the agent-vs-human "
                    "axis was removed in v0.36 (`cage query savings-axis`)")
    if any(r["agent"] == "kiro" and r["surface"] == "ide" for r in rows):
        foot.caveat("· kiro (no session identity): its IDE log stamps every run under "
                    "the same constant session, so all of kiro's chats collapse into "
                    "this one row (`cage query kiro-routing`)")
    if any(r.get("from_credits") for r in shown):
        foot.caveat("· kiro CLI reports credits only — its store carries no token "
                    "counts, so token cells are '—' (`cage query copilot-credits`)")
    if kiro_route:
        foot.caveat(kiro_route)
    tail = foot.render()
    return f"{out}\n\n{tail}" if tail else out


def _csv_num(r: dict, field: str):
    """The CSV twin of `_num_cell`: empty — never `0` — for a credits-only chat's
    call/token cells (CSV never gates, but it also never fabricates a zero)."""
    return "" if r.get("from_credits") else r[field]


def _chat_method(r: dict) -> str:
    """The CSV `method` tag for one chat row — **`measured` throughout**.

    Every figure in this view is now a recorded count read back verbatim: tokens from
    the metric ledger, credits from the provider's own row. The `modeled`/`estimated`
    grades this used to carry existed because a credit was being turned into a *dollar*
    at a rate the user configured and cage could not check. With no dollar, there is no
    inference left to grade down — and kiro's credits are retagged `measured` at the
    substrate for the same reason (USAGE-ONLY P3, `schema.make_credit`)."""
    return "measured"


def render_csv(data: dict) -> str:
    """CSV over the same rows the text view groups — one structure, two renderers.
    **Untruncated** (CSV never gates, `--all` is a text-only concern); ``chat`` is the
    full, unshortened label. Column contract: docs/FORMULAS.md § chats-view."""
    from cage import csvout
    head = ["chat", "agent", "surface", "session", "calls", "tokens_in", "cached_in",
            "cache_write_in", "tokens_out", "credits", "agent_lines",
            "residual_lines", "agent_pct", "method"]
    rows = [[r["title"], r["agent"], r["surface"], r["session"],
             _csv_num(r, "calls"), _csv_num(r, "tokens_in"), _csv_num(r, "cached_in"),
             _csv_num(r, "cache_write_in"), _csv_num(r, "tokens_out"),
             "" if r["credits"] is None else round(r["credits"], 6),
             *_authorship_csv(r), _chat_method(r)]
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
