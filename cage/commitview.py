"""`cage insights commits` · `cage insights commit <sha>` · `cage authorship summary`
— the per-commit surfaces of agent-vs-human v2 (P3).

**The unit is a commit**, because a commit is a real, inspectable piece of work you can
`git show`. v1 died anchoring numbers to an inferred turn-gap; every figure here hangs
off something a reader can go and look at.

**There is no USD, no rate and no valuation on any of these surfaces** — deliberately,
and it is the standing guard from the v1 removal. Tokens and hours only; valuation
stays in the reader's spreadsheet. Nothing in this module imports `prices` or
`convert`, so the omission is structural rather than an oversight waiting to be
"fixed".

**Four line buckets, never three, and nothing is redistributed.** The handoff mocked
`agent / human / unknown`; measured on cage's own repo that printed **human~ 76.6%**,
89% of it a single commit of generated JSON
([dogfood](../work/regression/2026-08-02-p1-authorship-dogfood.md) §4). A residual
presented as a finding is exactly the v1 mistake, so the residual splits:

- ``agent``        — matched an agent proposal (direct evidence, from the ledger).
- ``human~``       — added in a file this session **did** propose, matching nothing.
                     A real human tweak of agent work; the highest-signal residual.
- ``unattributed`` — added in a file **no** session proposed: human-written, vendored,
                     or generated output. Cage has no evidence either way and says so.
- ``unknown``      — below the content gate, or in a binary file. Structural.

**Refusals render.** A commit with no joinable call shows `—` for tokens, never `0` —
"nothing joined here" and "this cost nothing" are different claims. Excluded calls are
counted by *reason*, and every reason is footnoted (`commitjoin.EXCLUSION_TEXT`).

**Hours.** Three visibly distinct tiers: ``*`` attested (`cage task time`, P4) always
wins · ``~`` estimated (`wall − agent span`, floored at 0) only when
`[authorship] estimate_hours` is on **and** the commit gap is within `max_est_gap` ·
``—`` otherwise, with the reason named. The estimator's method is stated in the view's
own footnote, not in a doc a reader will never open.

Deterministic: every figure derives from the ledger plus `git show`. The only clock is
`render.ago`-class advice, which these views do not print.
"""
from __future__ import annotations

from pathlib import Path

from cage import commitjoin, ledger, linematch, originrecord, render, tasks
from cage.constants import COMMITS_DEFAULT_ROWS, SHORT_SHA_DISPLAY

# The four buckets, in render order. A tuple so every renderer walks them identically.
BUCKETS = ("agent", "human", "unattributed", "unknown")
BUCKET_LABEL = {"agent": "agent", "human": "human~", "unattributed": "unattr",
                "unknown": "unkn"}

ATTESTED, ESTIMATED = "attested", "estimated"
DASH = "—"

# Why an hours cell refuses. Named, never blank.
NO_ESTIMATE = "estimator off ([authorship] estimate_hours = false)"
GAP_TOO_WIDE = "commit gap exceeds [authorship] max_est_gap"
NO_WALL = "no previous commit to measure wall-clock against"
NO_AGENT_SPAN = "no agent span joined — the estimate would just be the commit gap"


def _iso(ts: str):
    """The ONE timestamp parse (`commitjoin.as_utc`), never a second copy of it.

    Always UTC-**aware**, which this module needs and its own former version did not
    guarantee: an offset-free input used to return naive, and comparing that against
    `ledger.since_cutoff`'s aware cutoff below raises `TypeError`."""
    return commitjoin.as_utc(ts)


def _seconds(lo: str, hi: str):
    a, b = _iso(lo), _iso(hi)
    return int((b - a).total_seconds()) if a and b else None


def _gap_seconds(spec: str) -> int:
    """A ``4h``/``2d`` window as seconds, reusing the ONE window parser
    (`ledger.since_cutoff`'s vocabulary) rather than inventing a second one."""
    from cage.constants import SINCE_WINDOW_DAYS
    import re
    m = re.match(r"^(\d+)([dhw])$", (spec or "").strip())
    if not m:
        return 0
    return int(round(int(m.group(1)) * SINCE_WINDOW_DAYS[m.group(2)] * 86400))


def _hours(row_wall, agent_span, attested_min, *, estimate_on: bool, cap_s: int) -> dict:
    """The hours cell: ``{value, tier, reason}``. An attestation **always** wins — it is
    a person's assertion about their own time, and no inference outranks it."""
    if attested_min is not None:
        return {"value": round(attested_min / 60.0, 2), "tier": ATTESTED, "reason": ""}
    if not estimate_on:
        return {"value": None, "tier": None, "reason": NO_ESTIMATE}
    if row_wall is None:
        return {"value": None, "tier": None, "reason": NO_WALL}
    if agent_span is None:
        # THE degenerate case, and it must refuse. `wall − agent_span` with no agent
        # span is just `wall` — the raw gap between two commits, printed in an "hours"
        # column where it reads as measured effort. That is precisely the v1 mistake:
        # an interval the tool did not observe, wearing a number.
        return {"value": None, "tier": None, "reason": NO_AGENT_SPAN}
    if cap_s and row_wall > cap_s:
        # Past the cap the wall clock has stopped describing the work — an overnight
        # gap would read as hours at the keyboard. Fog is refused, not printed.
        return {"value": None, "tier": None, "reason": GAP_TOO_WIDE}
    return {"value": round(max(0, row_wall - agent_span) / 3600.0, 2),
            "tier": ESTIMATED, "reason": ""}


def _buckets(diff: dict, prov_rows: list[dict]) -> dict:
    """The four line buckets for one commit, from its diff and its provenance rows.

    ``agent`` is **read** from the recorded ``agent_lines`` — never re-derived here.
    Re-matching at render time would be a second implementation of the matcher, free to
    disagree with the one that wrote the row (the mistake `adoption.py` calls out for
    outcomes). Summed across sessions and clamped to the matchable total: two agents
    that both proposed the same line must not each claim it."""
    added = diff["added"]
    proposed: set = set()
    for r in prov_rows:
        proposed |= set(r.get("files") or [])
    total = matchable = gated = untouched = 0
    for path, lines in added.items():
        total += len(lines)
        keep = sum(1 for ln in lines if linematch.matchable(linematch.normalize(ln)))
        gated += len(lines) - keep
        matchable += keep
        if path not in proposed:
            untouched += keep
    agent = min(sum(int(r.get("agent_lines", 0) or 0) for r in prov_rows),
                matchable - untouched)
    agent = max(0, agent)
    return {"added": total, "agent": agent,
            "human": max(0, matchable - untouched - agent),
            "unattributed": untouched, "unknown": gated,
            "binary_files": len(diff["binary"]),
            "removed": sum(r for _a, r in diff["numstat"].values())}


def _tokens(calls: list[dict]) -> dict:
    return {"calls": len(calls),
            "tokens_in": sum(int(c.get("tokens_in", 0)) for c in calls),
            "tokens_out": sum(int(c.get("tokens_out", 0)) for c in calls),
            "cache_read": sum(int(c.get("cached_in", 0)) for c in calls),
            "cache_write": sum(int(c.get("cache_write_in", 0)) for c in calls)}


def _agent_span(calls: list[dict]) -> tuple[int | None, str]:
    """``(seconds, method)`` for the agent's time on a commit.

    ``latency_ms`` is **measured** but only the library meter sets it — every
    transcript-imported call carries 0 (verified 2026-08-02). So the fallback is the
    first→last turn span, which includes the human's think-time *between* turns and is
    therefore an over-estimate labelled `~`. Two different facts, two different labels;
    they are never summed together."""
    lat = sum(int(c.get("latency_ms", 0) or 0) for c in calls)
    if lat > 0:
        return lat // 1000, "measured"
    ts = sorted(c["ts"] for c in calls if c.get("ts"))
    if len(ts) < 2:
        return (0, "span") if ts else (None, "")
    return _seconds(ts[0], ts[-1]), "span"


def _repo(root: Path, repo: Path | None) -> Path | None:
    return repo or commitjoin.toplevel(Path.cwd()) or commitjoin.toplevel(root)


def summarize(root: Path, pol: dict, *, since: str | None = None,
              repo: Path | None = None, sha: str | None = None,
              limit: int | None = None) -> dict:
    """The ONE data structure every renderer consumes — list, detail, CSV and JSON.

    ``sha`` narrows to a single commit and adds the per-file breakdown (the detail
    view); otherwise every commit in the ``since`` window is summarized. Pure derive
    over the ledger + `git show`; no clock, no pricing, no mutation.

    ``limit`` is the **cost bound** (OPEN-WORK COMMITS-WINDOW, verdict B accepted
    2026-08-11 — [compare](../work/compare/commits-view-cost-bound.compare.md)). Every
    row costs one `linematch.commit_diff` → `git show --numstat` **subprocess**, so an
    uncapped read makes this view O(*history*) while the screen is O(*rows*): measured
    **6.4s to print 20 rows from 123 commits**. It keeps the **newest** ``limit``
    commits — capping on the axis the view is already paged on — and stays a pure
    function of the ledger + repo. The rejected alternative was a default relative
    ``--since``, which would put a **wall clock in the default path** (the same ledger
    renders differently next month) and did not bound cost at all when measured.

    **Only the text path passes it.** ``--csv``/``--json`` stay complete and pay full
    cost (CSV is never truncated), ``--all`` lifts it, and ``sha`` (the detail view)
    is never capped — a commit of any age must be readable. The commits it drops are
    counted into ``limited_out`` and footnoted, never silently cut."""
    from cage import policy
    r = _repo(root, repo)
    base = {"repo": "", "branch": "", "since": since, "sha": sha, "rows": [],
            "ok": False, "reason": "", "excluded": [], "unattributed": [],
            "dirty_tasks": 0, "estimate_on": policy.authorship_estimate_hours(pol),
            "max_est_gap": policy.authorship_max_est_gap(pol),
            "coverage": "", "joinability": commitjoin.joinability_note(),
            "totals": {}, "provenance_rows": 0, "limited_out": 0}
    if r is None:
        base["reason"] = "not a git repository — these views are per-commit"
        return base
    from cage import authorcapture
    base.update(repo=str(r), coverage=authorcapture.coverage_note())
    windows = commitjoin.commit_windows(r)
    if not windows:
        base["reason"] = f"no commits in {r}"
        return base
    base["branch"] = commitjoin._git(r, "rev-parse", "--abbrev-ref", "HEAD") or ""
    base["branch"] = base["branch"].strip()

    calls = ledger.spend(root)
    join = commitjoin.join_calls(calls, windows, tasks.read(root),
                                 project=r.name, receipts=ledger.receipts(root))
    # Provenance and task rows are keyed by whatever sha shape was current when they
    # were written — SHORT before 2026-08-11, full after — and they are append-only, so
    # both shapes coexist forever. Resolve each row onto a window sha once, here, rather
    # than letting an exact `.get(w.sha)` miss silently further down.
    all_shas = {w.sha for w in windows}
    prov: dict[str, list[dict]] = {}
    for row in originrecord.read_all(root):
        key, _why = commitjoin.prefix_match(all_shas, row.get("sha", ""))
        prov.setdefault(key or row.get("sha", ""), []).append(row)
    base["provenance_rows"] = sum(len(v) for v in prov.values())
    base["excluded"] = join["excluded"]
    base["dirty_tasks"] = join["dirty_tasks"]

    attested = _attested_minutes(root, join, all_shas)
    cut = ledger.since_cutoff(since)
    cap_s = _gap_seconds(base["max_est_gap"])
    if sha:
        # THE missing refusal. Prefix matching already existed here and was already
        # symmetric — what it never did was notice a probe matching TWO commits.
        # `render_commit` then took `rows[0]` over an **oldest-first** sort, so an
        # ambiguous prefix rendered the OLDEST match, confidently. (The proposal recorded
        # this symptom backwards, as "the newest".)
        resolved, why = commitjoin.prefix_match({w.sha for w in windows}, sha)
        if why == commitjoin.AMBIGUOUS:
            hits = sorted(w.sha for w in windows if w.sha.startswith(sha))
            base["reason"] = (f"{sha}: ambiguous — matches {len(hits)} commits "
                              f"({', '.join(_short(h) for h in hits[:4])}"
                              f"{', …' if len(hits) > 4 else ''}). Use more characters")
            return base
        wanted = [w for w in windows if w.sha == resolved]
    else:
        wanted = list(windows)
    if sha and not wanted:
        base["reason"] = f"{sha}: not a commit in this history"
        return base
    if cut is not None:
        before_window = len(wanted)
        wanted = [w for w in wanted if (t := _iso(w.hi)) is not None and t >= cut]
        # No silent caps: the window is now a DEFAULT, so a reader who never typed
        # `--since` has to be told what it hid and how to see it.
        base["windowed_out"] = before_window - len(wanted)
    # THE cost bound. `windows` is oldest-first, so the newest `limit` commits are the
    # tail — and they are the ones a reader scans first (`rows.reverse()` below). Applied
    # BEFORE the loop, which is the whole point: `render_commits`' 20-row cap was applied
    # after every row had already paid for its own `git show`.
    if limit is not None and sha is None and len(wanted) > limit:
        base["limited_out"] = len(wanted) - limit
        wanted = wanted[-limit:]
    # A SET, membership-tested once per commit. `w not in wanted` over a list made the
    # selection O(n²); the `git show` below dominates, but there is no reason to pay
    # both.
    keep = {w.sha for w in wanted}

    rows = []
    for w in windows:
        if w.sha not in keep:
            continue
        grp = join["by_sha"].get(w.sha, {"calls": [], "via": {}})
        diff = linematch.commit_diff(r, w.sha)      # ONE git call per rendered commit
        prov_rows = prov.get(w.sha, [])
        span, span_method = _agent_span(grp["calls"])
        wall = _seconds(w.lo, w.hi) if w.lo else None
        row = {"sha": w.sha, "ts": w.hi,
               "attributed": bool(grp["calls"]),
               "via": {k: v for k, v in (grp.get("via") or {}).items() if v},
               "agent_span_s": span, "agent_span_method": span_method,
               "wall_s": wall,
               "hours": _hours(wall, span, attested.get(w.sha),
                               estimate_on=base["estimate_on"], cap_s=cap_s),
               "sessions": sorted({p.get("session_id", "") for p in prov_rows} - {""}),
               "agents": sorted({p.get("agent", "") for p in prov_rows} - {""}),
               "confidence": max((float(p.get("confidence", 0.0)) for p in prov_rows),
                                 default=0.0),
               "method": (max(prov_rows, key=lambda p: p.get("confidence", 0.0))
                          .get("method") if prov_rows else None),
               "suggested": sum(int(p.get("suggested", 0) or 0) for p in prov_rows),
               "kept": sum(int(p.get("kept", 0) or 0) for p in prov_rows),
               "kept_modified": sum(int(p.get("kept_modified", 0) or 0) for p in prov_rows),
               "dropped": sum(int(p.get("dropped", 0) or 0) for p in prov_rows),
               **_tokens(grp["calls"]), **_buckets(diff, prov_rows)}
        if sha is not None:
            row["files"] = _file_rows(diff, prov_rows)
        rows.append(row)
    rows.reverse()   # newest first — the order a reader scans

    base["rows"] = rows
    base["ok"] = True
    base["unattributed"] = [x["sha"] for x in rows if not x["attributed"]]
    base["totals"] = _totals(rows)
    return base


def _attested_minutes(root: Path, join: dict, shas=()) -> dict:
    """``{sha: minutes}`` from `cage task time` (P4) — a task's attested minutes land on
    the commit its snapshot names. Only *clean* snapshots are trusted, the same guard
    `commitjoin._task_commits` applies: a task closed on a dirty tree names the prior
    commit, and its hours belong to the next one.

    **Keyed onto the WINDOW's sha, via `prefix_match`.** This is the "an attestation
    always wins" break: a task row carrying a short `commit` never equalled a full window
    sha, `attested.get(w.sha)` returned None, and `_hours` fell straight through to the
    `~` estimate — silently replacing a person's own assertion about their time with an
    inference, which is the one substitution this module is built to prevent."""
    out: dict[str, float] = {}
    for _tid, row in sorted(tasks.read(root).items()):
        mins, sha = row.get("human_minutes"), row.get("commit")
        if mins is None or not sha or not row.get("outcome"):
            continue
        if int(row.get("files_changed", 0) or 0):
            continue
        key, _why = commitjoin.prefix_match(shas, sha)
        key = key or sha
        try:
            out[key] = out.get(key, 0.0) + float(mins)
        except (TypeError, ValueError):
            continue
    return out


def _file_rows(diff: dict, prov_rows: list[dict]) -> list[dict]:
    """Per-file buckets for the detail view, newest-question-first: which files did the
    agent write, which did a person, and which can cage not speak to."""
    proposed: set = set()
    for r in prov_rows:
        proposed |= set(r.get("files") or [])
    agent_total = sum(int(r.get("agent_lines", 0) or 0) for r in prov_rows)
    # Distribute the recorded agent total across proposed files by their matchable
    # share. The ROW is the recorded fact; this split is presentation, and it is
    # labelled as such in the view's footnote rather than dressed up as per-file
    # evidence — the substrate stores one agent count per (sha, session), not per file.
    weights = {}
    for path, lines in diff["added"].items():
        if path in proposed:
            weights[path] = sum(1 for ln in lines
                                if linematch.matchable(linematch.normalize(ln)))
    pool = sum(weights.values())
    out = []
    for path in sorted(set(diff["numstat"]) | set(diff["binary"])):
        added, removed = diff["numstat"].get(path, (0, 0))
        lines = diff["added"].get(path, [])
        keep = sum(1 for ln in lines if linematch.matchable(linematch.normalize(ln)))
        gated = len(lines) - keep
        if path in diff["binary"]:
            out.append({"path": path, "added": 0, "removed": 0, "agent": 0, "human": 0,
                        "unattributed": 0, "unknown": 0, "binary": True})
            continue
        agent = int(round(agent_total * weights[path] / pool)) if path in weights and pool else 0
        agent = min(agent, keep)
        out.append({"path": path, "added": added, "removed": removed, "agent": agent,
                    "human": max(0, keep - agent) if path in proposed else 0,
                    "unattributed": 0 if path in proposed else keep,
                    "unknown": gated, "binary": False})
    out.sort(key=lambda f: (-f["added"], f["path"]))
    return out


def _totals(rows: list[dict]) -> dict:
    t = {k: 0 for k in ("calls", "tokens_in", "tokens_out", "cache_read", "cache_write",
                        "added", "removed", "suggested", "kept", "kept_modified",
                        "dropped", "binary_files", *BUCKETS)}
    hours, attested, estimated = 0.0, 0, 0
    for r in rows:
        for k in t:
            t[k] += r.get(k, 0)
        h = r["hours"]
        if h["value"] is not None:
            hours += h["value"]
            if h["tier"] == ATTESTED:
                attested += 1
            else:
                estimated += 1
    t["hours"] = round(hours, 2)
    t["hours_attested_n"] = attested
    t["hours_estimated_n"] = estimated
    t["commits"] = len(rows)
    t["attributed"] = sum(1 for r in rows if r["attributed"])
    return t


# ── rendering ────────────────────────────────────────────────────────────────

_NO_REPO = """No commits to report on.

{reason}

next: cage report                 spend by agent / route / model
      cage query agent-authorship how the per-commit split is derived"""


def _split_cell(r: dict) -> str:
    """The four-bucket split as percentages of *classified* added lines. `unknown` is
    shown and never redistributed, so the four add to 100 and none of them is a
    leftover."""
    n = sum(r[b] for b in BUCKETS)
    if not n:
        return DASH
    return " / ".join(f"{100 * r[b] / n:3.0f}%" for b in BUCKETS)


def _hours_cell(r: dict) -> str:
    h = r["hours"]
    if h["value"] is None:
        return DASH
    return f"{h['value']:.1f}" + ("*" if h["tier"] == ATTESTED else "~")


def _tok(v, attributed: bool) -> str:
    return render.tok(v) if attributed else DASH


def _date(ts: str) -> str:
    return (ts or "")[5:16].replace("T", " · ")


def _short(sha: str) -> str:
    """A sha for a HUMAN to read. Display only — `--json`/`--csv` carry the full one
    (`constants.SHORT_SHA_DISPLAY`)."""
    return (sha or "")[:SHORT_SHA_DISPLAY]


def render_commits(data: dict, show_all: bool = False) -> str:
    """The list view. Tokens, hours and the four-way split, one row per commit."""
    from cage.display import Footer
    if not data["ok"]:
        return _NO_REPO.format(reason=data["reason"])
    rows = data["rows"]
    if not rows:
        win = f" in the last {data['since']}" if data["since"] else ""
        return (f"No commits{win} — the window is empty, not the repository.\n\n"
                f"next: cage insights commits          every commit")
    limit = None if show_all else COMMITS_DEFAULT_ROWS
    shown = rows if limit is None else rows[:limit]
    cut = 0 if limit is None else max(0, len(rows) - limit)

    head = ["commit", "date · time", "tok in", "tok out", "cache r", "cache w",
            "human hrs", "  agent / human~ / unattr / unkn"]
    body = []
    for r in rows if limit is None else shown:
        a = r["attributed"]
        body.append([_short(r["sha"]), _date(r["ts"]), _tok(r["tokens_in"], a),
                     _tok(r["tokens_out"], a), _tok(r["cache_read"], a),
                     _tok(r["cache_write"], a), _hours_cell(r), _split_cell(r)])
    t = data["totals"]
    body.append(["─" * 7, "", "", "", "", "", "", ""])
    # A total of zero attributed commits must refuse exactly like its rows do. Printing
    # `0` under a column of `—` would be the one thing this view exists to prevent:
    # "cage joined nothing" rendered as "this cost nothing".
    any_attr = t["attributed"] > 0
    body.append([f"Σ {t['commits']}", DASH, _tok(t["tokens_in"], any_attr),
                 _tok(t["tokens_out"], any_attr), _tok(t["cache_read"], any_attr),
                 _tok(t["cache_write"], any_attr),
                 f"{t['hours']:.1f}" if (t["hours_attested_n"] or t["hours_estimated_n"]) else DASH,
                 _split_cell(t)])

    title = f"Commits · {data['branch'] or 'HEAD'}"
    if data["since"]:
        title += f" · last {data['since']}"
    title += f" · {t['commits']} commit{'s' if t['commits'] != 1 else ''}"
    out = f"{title}\n\n" + render.table(head, body, rights=set(range(2, 8)))
    return out + _footer(data, Footer(), cut=cut)


# Kept as a backstop, not as the bound: a caller that summarizes without `limit` (a test,
# `--all`, the CSV path re-rendered as text) still pages at the same number. The cost is
# bounded upstream, in `summarize`.


def _footer(data: dict, foot, *, cut: int = 0) -> str:
    """Every caveat these views owe the reader, in one place so the two surfaces
    cannot footnote the same number differently."""
    t = data["totals"]
    if cut:
        foot.gap(f"· {cut} more commit(s) — --all to show")
    # The no-silent-caps half of the cost bound. These commits were not merely hidden,
    # they were never READ — so every figure above, the Σ row included, is over the rows
    # shown. Saying only "N more" would let a bounded total read as a whole-history one.
    if data.get("limited_out"):
        foot.gap(f"· {data['limited_out']} older commit(s) not read — the default view "
                 f"reads the newest {COMMITS_DEFAULT_ROWS} (one `git show` each), so the "
                 "Σ row\n  covers those only. --all reads every commit; "
                 "--csv/--json are never capped")
    if data.get("windowed_out"):
        foot.gap(f"· {data['windowed_out']} commit(s) older than {data.get('since')} "
                 "not read — --since WINDOW or --all")
    foot.caveat("· split = share of CLASSIFIED added lines. agent = matched an agent's "
                "recorded\n  proposal (direct); human~ = added in a file that session "
                "proposed but matching\n  nothing (ESTIMATED residual); unattr = added "
                "in a file no session proposed —\n  a person, a vendored tree or "
                "generated output, cage does not guess which;\n  unkn = below the "
                "content gate or binary. Never redistributed, never a score.")
    if data["estimate_on"]:
        foot.caveat(f"· human hrs marked ~ are ESTIMATED: commit wall-clock minus the "
                    f"agent's turn-span,\n  floored at 0 and refused past "
                    f"[authorship] max_est_gap = {data['max_est_gap']}. An inference, "
                    f"not a\n  measurement. * = attested via `cage task time` — always "
                    f"wins over the estimate.")
    else:
        foot.caveat("· human hrs are only ever attested (`cage task time`) — the "
                    "estimator is off\n  ([authorship] estimate_hours = false).")
    foot.caveat("· tokens are MEASURED; placing a call on a commit is MODELED "
                "(task-id join first,\n  commit-window fallback). No USD on this "
                "surface, by design.")
    if data["unattributed"]:
        n = len(data["unattributed"])
        foot.gap(f"· {n} commit(s) unattributed — no joinable call. Tokens render "
                 f"'{DASH}', never 0:\n  cage has no evidence they cost nothing.")
    for e in data["excluded"]:
        foot.gap(f"· {e['calls']:,} call(s) ({e['tokens']:,} tokens) excluded — "
                 f"{commitjoin.EXCLUSION_TEXT[e['reason']]}")
    if data["dirty_tasks"]:
        foot.gap(f"· {data['dirty_tasks']} closed task(s) had uncommitted work at "
                 f"close, so their\n  recorded sha is the PRIOR commit — those calls "
                 f"fell back to the window join.")
    if data["joinability"]:
        foot.caveat(f"· not window-joinable: {data['joinability']}")
    if data["coverage"]:
        foot.caveat(f"· not line-matchable: {data['coverage']} — their commits show "
                    f"as unattr, never 0%")
    if not data["provenance_rows"]:
        foot.gap("· no authorship rows recorded yet — every added line is unattr/unkn. "
                 "Run\n  `cage import` in this repo (or check [authorship] capture).")
    block = foot.render()
    return f"\n\n{block}" if block else ""


def render_commit(data: dict, show_files: bool = False) -> str:
    """The detail view for one commit."""
    from cage.display import Footer
    if not data["ok"]:
        return _NO_REPO.format(reason=data["reason"])
    if not data["rows"]:
        return _NO_REPO.format(reason=f"{data['sha']}: no such commit in this history")
    r = data["rows"][0]
    who = ", ".join(r["agents"]) or "no agent recorded"
    # Two independent facts, and conflating them was the first thing this header got
    # wrong: sessions come from the AUTHORSHIP rows (who wrote it), `via` from the CALL
    # join (whose spend it was). A commit can have three sessions of recorded authorship
    # and no joinable call, so "3 sessions joined (unattributed)" was a contradiction.
    sess = f"{len(r['sessions'])} session(s) recorded" if r["sessions"] else "no session recorded"
    via = ("calls joined via " + "+".join(sorted(r["via"]))) if r["via"] else "no call joined"
    head = (f"commit {_short(r['sha'])} · {(r['ts'] or '')[:16].replace('T', ' ')} · "
            f"{data['branch']} · {who} · {sess} · {via}")

    lines = [head, ""]
    if r["attributed"]:
        lines.append(f"  tokens     in {render.tok(r['tokens_in'])} · out "
                     f"{render.tok(r['tokens_out'])} · cache read "
                     f"{render.tok(r['cache_read'])} · cache write "
                     f"{render.tok(r['cache_write'])}   ({r['calls']} call(s))")
    else:
        lines.append(f"  tokens     {DASH}  no joinable call — never 0")
    if r["method"]:
        lines.append(f"  origin     agent · confidence {r['confidence']:.2f} "
                     f"({r['method']}) — human only by attestation, unknown by absence")
    else:
        lines.append("  origin     unknown — by absence, not a stored row")
    lines.append(f"  lines      +{r['added']} / −{r['removed']} total")
    for b in BUCKETS:
        note = {"agent": "line-match vs the session's recorded edit blocks",
                "human": "residual in files the session proposed (estimated)",
                "unattributed": "in files no session proposed — cage does not guess",
                "unknown": "below the content gate / binary"}[b]
        lines.append(f"             {BUCKET_LABEL[b]:<12}{r[b]:>7}    {note}")
    if r["binary_files"]:
        lines.append(f"             binary      {r['binary_files']:>7} file(s)  "
                     f"no readable lines — counted as files, never as lines")
    if r["suggested"]:
        lines.append(f"  suggested  {r['suggested']} line(s) across "
                     f"{len(r['sessions'])} session(s)")
        lines.append(f"  kept       {r['kept']} verbatim · {r['kept_modified']} "
                     f"landed-modified · {r['dropped']} dropped")
    else:
        lines.append(f"  suggested  {DASH}  no proposals recorded for this commit")
    lines.append(f"  time       wall {_dur(r['wall_s'])} · agent "
                 f"{_dur(r['agent_span_s'])}{'~' if r['agent_span_method'] == 'span' else ''} "
                 f"· human {_hours_cell(r)}")

    files = r.get("files") or []
    if files:
        shown = files if show_files else files[:8]
        lines.append("")
        lines.append(render.table(
            ["file", "+", "−", *(BUCKET_LABEL[b] for b in BUCKETS)],
            [[f["path"], f["added"], f["removed"],
              *(("bin" if f["binary"] and b == "unknown" else f[b]) for b in BUCKETS)]
             for f in shown],
            rights={1, 2, 3, 4, 5, 6}))
        if len(files) > len(shown):
            lines.append(f"  ({len(files) - len(shown)} more file(s) — --files for all)")
    lines.append("  " + "─" * 51)
    lines.append(f"  Σ suggested {r['suggested']} · kept {r['kept']} — counts, not a score")
    return "\n".join(lines) + _footer(data, Footer())


def _dur(secs) -> str:
    if secs is None:
        return DASH
    h, m = divmod(int(secs) // 60, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"


def render_csv(data: dict) -> str:
    """CSV over the same rows the text view renders — **untruncated** (CSV never gates)
    and refusals survive as columns: an unattributed commit's token cells are EMPTY,
    never 0, and the hours cell carries its refusal reason. Column contract:
    docs/FORMULAS.md §2.14."""
    from cage import csvout
    head = ["sha", "ts", "attributed", "joined_via", "calls", "tokens_in", "tokens_out",
            "cache_read", "cache_write", "lines_added", "lines_removed",
            *BUCKETS, "binary_files", "suggested", "kept", "kept_modified", "dropped",
            "wall_s", "agent_span_s", "agent_span_method", "human_hours",
            "human_hours_tier", "human_hours_refused", "confidence", "method"]
    rows = []
    for r in data["rows"]:
        a = r["attributed"]
        rows.append([r["sha"], r["ts"], a, "+".join(sorted(r["via"])) or None,
                     r["calls"] if a else None,
                     *( (r["tokens_in"], r["tokens_out"], r["cache_read"],
                         r["cache_write"]) if a else (None, None, None, None)),
                     r["added"], r["removed"], *(r[b] for b in BUCKETS),
                     r["binary_files"], r["suggested"], r["kept"], r["kept_modified"],
                     r["dropped"], r["wall_s"], r["agent_span_s"],
                     r["agent_span_method"] or None, r["hours"]["value"],
                     r["hours"]["tier"], r["hours"]["reason"] or None,
                     round(r["confidence"], 4) or None, r["method"]])
    return csvout.table(head, rows)


# ── `cage authorship summary` ────────────────────────────────────────────────

def summarize_authorship(root: Path, pol: dict, *, since: str | None = None,
                         repo: Path | None = None) -> dict:
    """Thin aggregation over the now-live provenance rows — **unknown-rate first**.

    Deliberately the reverse emphasis of the commit views: this answers "how much of
    this repo's history can cage speak to at all", so the coverage gap leads and the
    attribution follows. `unmatched` shas (recorded provenance whose commit is no
    longer in the history — squashed, rebased, another branch) get their own line
    rather than silently vanishing from a denominator."""
    r = _repo(root, repo)
    out = {"repo": str(r) if r else "", "since": since, "ok": False, "reason": "",
           "commits": 0, "with_rows": 0, "unmatched": [], "rows": 0,
           "by_agent": [], "by_method": [], "suggested": 0, "kept": 0,
           "kept_modified": 0, "dropped": 0,
           "coverage": ""}
    if r is None:
        out["reason"] = "not a git repository — authorship is per-commit"
        return out
    from cage import authorcapture
    out["coverage"] = authorcapture.coverage_note()
    windows = commitjoin.commit_windows(r)
    if not windows:
        out["reason"] = f"no commits in {r}"
        return out
    cut = ledger.since_cutoff(since)
    keep = [w for w in windows
            if cut is None or ((t := _iso(w.hi)) is not None and t >= cut)]
    known = {w.sha for w in keep}
    every = {w.sha for w in windows}
    # Resolve each stored row onto a window sha ONCE — rows written before 2026-08-11
    # carry short shas and would never equal a full window sha. `unmatched` is then a
    # real finding ("recorded provenance whose commit is not in this history") instead of
    # every pre-change row in the ledger.
    # ONE read, and the resolution is carried as a pair — `read_all` builds fresh dicts
    # on every call, so keying a side table by identity across two reads silently
    # resolves nothing (and made every real row look unmatched).
    placed = [(x, commitjoin.prefix_match(every, x.get("sha", ""))[0])
              for x in originrecord.read_all(root)]
    rows = [(x, w) for x, w in placed if cut is None or w in known or w is None]
    in_window = [x for x, w in rows if w in known]
    out.update(ok=True, commits=len(keep), rows=len(in_window),
               with_rows=len({w for _x, w in rows if w in known}))
    out["unmatched"] = sorted({x.get("sha", "") for x, w in rows if w is None} - {""})
    agents_, methods = {}, {}
    for x in in_window:
        agents_[x.get("agent", "") or "?"] = agents_.get(x.get("agent", "") or "?", 0) + 1
        methods[x.get("method", "")] = methods.get(x.get("method", ""), 0) + 1
        for k in ("suggested", "kept", "kept_modified", "dropped"):
            out[k] += int(x.get(k, 0) or 0)
    out["by_agent"] = [{"agent": a, "rows": n} for a, n in
                       sorted(agents_.items(), key=lambda kv: (-kv[1], kv[0]))]
    out["by_method"] = [{"method": m, "rows": n} for m, n in
                        sorted(methods.items(), key=lambda kv: (-kv[1], kv[0]))]
    return out


def render_authorship(d: dict) -> str:
    from cage.display import Footer
    if not d["ok"]:
        return _NO_REPO.format(reason=d["reason"])
    unknown = d["commits"] - d["with_rows"]
    pct = (100 * unknown / d["commits"]) if d["commits"] else 0
    win = f" · last {d['since']}" if d["since"] else ""
    lines = [f"Authorship{win} · {d['commits']} commit(s)", "",
             f"  UNKNOWN     {unknown} of {d['commits']} commit(s) ({pct:.0f}%) have no "
             f"authorship row at all",
             f"              — unknown by ABSENCE, never a stored row",
             f"  recorded    {d['with_rows']} commit(s) · {d['rows']} row(s)"]
    if d["unmatched"]:
        lines.append(f"  unmatched   {len(d['unmatched'])} recorded sha(s) are not in "
                     f"this history\n              — squashed, rebased or another "
                     f"branch; never chased")
    if d["by_agent"]:
        lines += ["", render.table(["agent", "rows"],
                                   [[g["agent"], g["rows"]] for g in d["by_agent"]],
                                   rights={1})]
    if d["by_method"]:
        lines += ["", render.table(["method", "rows"],
                                   [[g["method"], g["rows"]] for g in d["by_method"]],
                                   rights={1})]
    if d["suggested"]:
        lines += ["", f"  suggested {d['suggested']:,} · kept {d['kept']:,} verbatim · "
                      f"{d['kept_modified']:,} landed-modified · {d['dropped']:,} dropped",
                  "  counts, not a score — no acceptance percentage is derived from them"]
    foot = Footer()
    foot.caveat("· `unknown` is the honest headline: a commit cage never saw looks "
                "exactly like\n  one made before cage existed. Absence of evidence.")
    if d["coverage"]:
        foot.caveat(f"· not line-matchable: {d['coverage']}")
    block = foot.render()
    return "\n".join(lines) + (f"\n\n{block}" if block else "")


def render_authorship_csv(d: dict) -> str:
    from cage import csvout
    head = ["dimension", "key", "rows", "commits", "suggested", "kept",
            "kept_modified", "dropped"]
    rows = [["total", "all", d["rows"], d["commits"], d["suggested"], d["kept"],
             d["kept_modified"], d["dropped"]],
            ["coverage", "with-rows", d["rows"], d["with_rows"], None, None, None, None],
            ["coverage", "unknown", 0, d["commits"] - d["with_rows"], None, None, None, None],
            ["coverage", "unmatched", len(d["unmatched"]), None, None, None, None, None]]
    rows += [["agent", g["agent"], g["rows"], None, None, None, None, None]
             for g in d["by_agent"]]
    rows += [["method", g["method"], g["rows"], None, None, None, None, None]
             for g in d["by_method"]]
    return csvout.table(head, rows)
