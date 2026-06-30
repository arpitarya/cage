"""Command handlers — load policy, derive a view, print it (plan §7, §8)."""
from __future__ import annotations

from pathlib import Path

from cage import (agents, attribution, budget, demo, doctorcmd,
                  explain, exportcmd, forecast, graphifymeter, humanview, importcmd, initcmd,
                  ledger, ledgersync, matrix, mcpserver, metercmd, metering, notessync,
                  origin, paths, policy, provenance, proxy, quality, recommend, regression,
                  report, roi, serve, tasks, trend, verifycmd, watchcmd, wizard)
from cage.cliutil import emit, ledger_root, root
from cage.errors import CageError


def _project_filter(args):
    """The `--project` value, resolving the `.` (or bare-flag) shorthand to the current
    directory's basename — a project view of the global ledger (plan §3.7)."""
    p = getattr(args, "project", None)
    return Path.cwd().name if p == "." else p


def _policy(r=None):
    """Policy for ``r`` (the active root). Defaults to the project root; ledger/read
    commands pass ``ledger_root()`` so a no-project user reads the global ledger's policy.

    A malformed project ``policy.toml`` is a user-facing failure, so surface it as a
    clean ``CageError`` (``cli.main`` → ``error: …`` + exit 1) instead of leaking a raw
    ``TOMLDecodeError`` traceback at the read boundary. Write paths call ``policy.load``
    directly and stay fail-open; only this CLI read chokepoint converts."""
    path = paths.Footprint(r or root()).policy
    try:
        return policy.load(path)
    except Exception as e:  # noqa: BLE001 — malformed policy.toml → clean CLI error, not a traceback
        raise CageError(f"{path.name}: {e}") from e


def _latest_task(r) -> str | None:
    tasks = [c.get("task") for c in ledger.calls(r) if c.get("task")]
    return tasks[-1] if tasks else None


def cmd_init(_args) -> int:
    info = initcmd.run(root())
    print(f"✔ Cage initialised at {info['footprint']}")
    print(f"  policy   → {info['policy']}")
    print(f"  ledger   → {info['ledger']}/  (gitignored, append-only)")
    print(f"  pointer  → {info['claude_md']}")
    print("Next: meter traffic (`cage.meter(...)`), then `cage report`. Try `cage demo`.")
    return 0


def cmd_report(args) -> int:
    r = ledger_root()
    rep = report.summarize(r, _policy(r), dim=args.by, since=args.since,
                           scope=getattr(args, "scope", None),
                           project=_project_filter(args),
                           team=getattr(args, "team", False))
    return emit(args, rep, report.render_report(rep, last_import=importcmd.last_import(r)))


def cmd_overview(args) -> int:
    """Bare `cage` — the one-look spent/saved/net headline (§4). No subcommand."""
    r = ledger_root()
    o = report.overview(r, _policy(r))
    return emit(args, o, report.render_overview(o, last_import=importcmd.last_import(r)))


def cmd_attrib(args) -> int:
    r = ledger_root()
    task = args.task or _latest_task(r)
    data = attribution.attribute(r, task, _policy(r), scope=getattr(args, "scope", None),
                                 team=getattr(args, "team", False))
    return emit(args, data, attribution.render_attrib(data))


def cmd_matrix(args) -> int:
    r = ledger_root()
    task = args.task or _latest_task(r)
    data = matrix.matrix(r, task, _policy(r), human=getattr(args, "human", False),
                         scope=getattr(args, "scope", None))
    text = matrix.render_matrix(data)
    if getattr(args, "html", None):
        serve.write_html(args.html, f"Matrix · {task}", {f"Matrix · {task}": text})
        print(f"✔ wrote {args.html}")
        return 0
    return emit(args, data, text)


def cmd_human(args) -> int:
    r = ledger_root()
    data = humanview.rollup(r, _policy(r), since=args.since, agent=args.agent, task=args.task)
    text = humanview.render_human(data)
    if getattr(args, "html", None):
        serve.write_html(args.html, "Agent vs human", {"Agent vs human": text})
        print(f"✔ wrote {args.html}")
        return 0
    return emit(args, data, text)


def cmd_human_record(args) -> int:
    rid = metering.record_human(task=args.task, minutes=args.minutes, usd=args.usd,
                                task_type=args.task_type or "", rate_usd_per_hr=args.rate,
                                call=args.call, agent=args.agent, measured=args.measured,
                                root=ledger_root())
    print(f"✔ recorded human alternative for {args.task!r}." if rid
          else f"· {args.task!r} already has a human receipt for that call (no double count).")
    return 0


def cmd_trend(args) -> int:
    r = ledger_root()
    data = trend.series(r, _policy(r), by=args.by, since=args.since)
    text = trend.render_trend(data, metric=args.metric)
    if getattr(args, "html", None):
        serve.write_html(args.html, "Savings trend", {"Savings trend": text})
        print(f"✔ wrote {args.html}")
        return 0
    return emit(args, data, text)


def cmd_budget(args) -> int:
    r = ledger_root()
    verdict = budget.check(r, _policy(r), session=args.session,
                           scope=getattr(args, "scope", None))
    return emit(args, verdict, budget.render_budget(verdict))


def cmd_roi(args) -> int:
    r = ledger_root()
    data = roi.by_tool(r, _policy(r), since=args.since)
    return emit(args, data, roi.render_roi(data))


def cmd_why(args) -> int:
    data = provenance.explain(ledger_root(), args.call_id)
    return emit(args, data, provenance.render_why(data, args.call_id))


def cmd_serve(args) -> int:
    return serve.serve(ledger_root(), port=args.port)


def cmd_query(args) -> int:
    """Explain how a value is calculated, or how cage itself works — deterministic,
    live numbers, $0 (no LLM)."""
    import json
    pol = _policy()
    kind = getattr(args, "kind", None)
    if getattr(args, "list", False):
        rows = [e for e in explain.REGISTRY if kind is None or e.kind == kind]
        if getattr(args, "json", False):
            print(json.dumps([explain.payload(e, pol) for e in rows],
                             ensure_ascii=False, indent=2))
        else:
            print("cage query topics — `cage query <id>` or a question:\n")
            print(explain.render_list(kind=kind))
        return 0
    hits = explain.match(args.question, top=5 if getattr(args, "all", False) else 1)
    if not hits:
        ids = ", ".join(explain.closest_ids(args.question))
        print(f"cage: no explainer matched {args.question!r}. Closest topics: {ids}")
        print("Run `cage query --list` for all topics.")
        return 1
    if getattr(args, "json", False):
        out = [explain.payload(e, pol) for e in hits]
        print(json.dumps(out if getattr(args, "all", False) else out[0],
                         ensure_ascii=False, indent=2))
        return 0
    print("\n\n".join(explain.render(e, pol) for e in hits))
    return 0


def cmd_demo(_args) -> int:
    call_id = demo.seed(ledger_root())
    print(f"✔ Seeded the §4.4 worked example (task {demo.TASK!r}, call {call_id}).")
    print("  Now run:  cage attrib   ·   cage matrix   ·   cage report")
    return 0


# ── §8 ledger features ───────────────────────────────────────────────────────

def cmd_quality(args) -> int:
    s = quality.summarize(ledger_root())
    return emit(args, s, quality.render_quality(s))


def cmd_outcome(args) -> int:
    r = ledger_root()
    quality.record_outcome(r, args.task, ok=not args.redo)
    tasks.record(r, args.task, outcome="ok" if not args.redo else "redo")
    print(f"✔ recorded {args.task!r} as {'redo' if args.redo else 'ok'}.")
    return 0


def cmd_regression(args) -> int:
    r = regression.detect(ledger_root(), since=args.since, tolerance=args.tolerance)
    return emit(args, r, regression.render_regression(r))


def cmd_recommend(args) -> int:
    lr = ledger_root()
    r = recommend.recommend(lr, _policy(lr), since=args.since)
    return emit(args, r, recommend.render_recommend(r))


def cmd_forecast(args) -> int:
    lr = ledger_root()
    f = forecast.project(lr, _policy(lr))
    return emit(args, f, forecast.render_forecast(f))


# ── adapters: proxy / meter / mcp / agents (plan §5, §6) ─────────────────────

def cmd_proxy(args) -> int:
    return proxy.serve(root(), port=args.port, upstream=args.upstream)


def cmd_meter(args) -> int:
    return metercmd.run(root(), args.argv, upstream=args.upstream)


def cmd_graphify(args) -> int:
    return graphifymeter.run(root(), args.argv, task=args.task)


def cmd_mcp(_args) -> int:
    return mcpserver.serve()


def cmd_setup(args) -> int:
    import sys

    here = root()

    # Handle --global: initialize the machine-wide global ledger (~/.cage) and exit. This
    # is the project-less capture sink (plan §3.7) — `cage import`/`cage export` from any
    # dir without a project `.cage/` land here.
    if getattr(args, "global_ledger", False):
        info = initcmd.run(paths.global_home(), pointer=False)
        print(f"✔ Global ledger initialised at {info['footprint']}")
        print(f"  policy   → {info['policy']}")
        print(f"  ledger   → {info['ledger']}/  (append-only)")
        print("Capture into it from anywhere: `cage import` · read it: `cage report`.")
        return 0

    # Handle --status: report current wiring and exit
    if getattr(args, "status", False):
        for surface, on in agents.status(here).items():
            print(f"  {'✔' if on else '·'} {surface:<8} {'wired' if on else 'not wired'}")
        return 0

    all_agents = getattr(args, "all_agents", False)

    # Handle --wire-only: agent wiring only, no scaffold/graphify
    if getattr(args, "wire_only", False):
        flagged = agents.SURFACES if all_agents else \
            tuple(s for s in agents.SURFACES if getattr(args, s, False))
        if not flagged:
            print("Pick an agent to wire: " + " | ".join(agents.SURFACES))
            print("e.g. `cage setup --wire-only --claude`")
            return 2
        print("✔ Cage wired into:")
        for surface, where in agents.install(here, flagged).items():
            print(f"  {surface:<8} → {', '.join(where.values())}")
        print("Metering: claude=transcript hook · others=`cage meter -- <cmd>` or `cage proxy`.")
        return 0

    # Handle --project-only: scaffold + graphify + PATH, no global skill
    project_only = getattr(args, "project_only", False)
    if project_only:
        # Override the flags for project-only mode
        args.skill = False
        args.project = True
        args.graphify = getattr(args, "graphify", True)

    # Standard setup: interactive wizard, --all, or per-agent flags
    flagged = tuple(s for s in agents.SURFACES if getattr(args, s, False))
    scope = "project" if getattr(args, "repo_skill", False) else "global"
    if all_agents:  # one plan that fans out to every agent (wizard.apply handles "all")
        plans = [{"agent": "all", "skill": args.skill, "skill_scope": scope,
                  "project": args.project, "graphify": args.graphify}]
    elif not flagged:
        if not sys.stdin.isatty():
            print("Pick an agent: " + " | ".join(agents.SURFACES) + " | all")
            print("e.g. `cage setup --claude` or `cage setup --all`  (or run `cage setup` "
                  "in a terminal for the guided wizard)")
            return 2
        plans = [wizard.interactive_plan()]
    else:
        plans = [{"agent": a, "skill": args.skill, "skill_scope": scope,
                  "project": args.project, "graphify": args.graphify} for a in flagged]

    for plan in plans:
        print(f"\n▸ cage setup — {plan['agent']}")
        for line in wizard.apply(here, **plan):
            print(f"  {line}")
    print("\nDone. Verify with `cage doctor`; then `cage report`.")
    return 0




def cmd_doctor(args) -> int:
    res = doctorcmd.run(root())
    if getattr(args, "json", False):
        import json
        print(json.dumps(res))
    else:
        glyph = {"ok": "✔", "warn": "·", "fail": "✗"}
        for c in res["checks"]:
            print(f"  {glyph[c['level']]} {c['name']:<12} {c['detail']}")
        verdict = {"ok": "Cage is set up and working.",
                   "warn": "Cage works; some optional wiring is missing (see ·).",
                   "fail": "Cage setup is broken (see ✗) — run `cage setup`."}
        print(f"\n{glyph[res['status']]} {verdict[res['status']]}")
    return 1 if res["status"] == "fail" else 0




def cmd_debug(args) -> int:
    """Print recent capture-path debug events ($0, metadata-only). When debug is off the
    log won't exist — say how to turn it on rather than printing nothing."""
    from cage import debuglog
    r = ledger_root()
    if not policy.debug_enabled(_policy(r)) and not paths.Footprint(r).debug_log.exists():
        print("· capture debug is off — set CAGE_DEBUG=1 (or [debug] enabled=true in policy.toml),")
        print("  re-run your agent, then `cage debug` to see per-hook events + errors.")
        return 0
    events = debuglog.tail(r, getattr(args, "tail", 20))
    if not events:
        print("· no debug events recorded yet (debug log is empty).")
        return 0
    import json
    if getattr(args, "json", False):
        for ev in events:
            print(json.dumps(ev))
        return 0
    for ev in events:
        ts = ev.get("ts", "").replace("T", " ")[:19]  # 'YYYY-MM-DD HH:MM:SS' — drop micros/tz
        agent = ev.get("agent", "?")
        name = ev.get("event", "?")
        rest = {k: v for k, v in ev.items() if k not in ("ts", "agent", "event")}
        detail = " ".join(f"{k}={v}" for k, v in rest.items() if k != "traceback")
        print(f"  {ts}  {agent}/{name}  {detail}".rstrip())
        if "traceback" in rest:
            print("    " + rest["traceback"].rstrip().replace("\n", "\n    "))
    return 0


def cmd_notes_sync(args) -> int:
    res = notessync.sync(root(), write=True if args.write else None)
    if getattr(args, "json", False):
        import json
        print(json.dumps(res))
        return 0
    if res["wrote"]:
        print(f"✔ wrote {len(res['shas'])} note(s) to refs/notes/cage-provenance.")
    else:
        print(f"· dry-run — {len(res['shas'])} sha(s) have buffered provenance to merge.")
        print("  Set CAGE_NOTES_WRITE=1 (CI) or pass --write to actually push notes.")
    return 0


def cmd_ledger_sync(args) -> int:
    """Merge the local ledger buffer into refs/notes/cage-ledger (§3.6.3). Dry-run by
    default — mirrors `cage notes-sync`; CI (`CAGE_NOTES_WRITE=1`) is the sole writer."""
    res = ledgersync.sync(root(), write=True if args.write else None)
    if getattr(args, "json", False):
        import json
        print(json.dumps(res))
        return 0
    if res["wrote"]:
        print(f"✔ wrote {res['rows']} row(s) to refs/notes/cage-ledger.")
    else:
        print(f"· dry-run — {res['rows']} merged call/receipt row(s) ready for the team ref.")
        print("  Set CAGE_NOTES_WRITE=1 (CI) or pass --write to actually push notes.")
    return 0


def cmd_origin(args) -> int:
    r = root()
    if args.attest:
        status = origin.attest(r, args.sha, origin=args.attest, agent=args.agent)
        msg = {
            "recorded": f"✔ attested {args.sha!r} as origin={args.attest!r}.",
            "already-attested": f"· {args.sha!r} is already attested — the append-only "
                                f"ledger keeps the first attestation (run `cage origin {args.sha}` to see it).",
            "no-diff": f"· attestation for {args.sha!r} was a no-op — sha not found or no diff to attest against.",
            "invalid-origin": f"· {args.attest!r} can't be attested (unknown isn't a fact worth writing).",
        }.get(status, f"· attestation for {args.sha!r} was a no-op.")
        print(msg)
        return 0
    data = origin.explain(r, args.sha)
    return emit(args, data, origin.render_origin(data))


def cmd_verify(_args) -> int:
    res = verifycmd.run(root())
    for w in res["warnings"]:
        print(f"  · {w}")
    print(f"\ncage verify: {len(res['warnings'])} warning(s) — report-only, never fails the build.")
    return 0


def cmd_import(args) -> int:
    """Umbrella hookless import across all four agents (default ``--agent all``) — the
    canonical explicit capture verb. Captures into the active ledger (``--ledger``/
    ``CAGE_BASE`` → project ``.cage/`` → global ``~/.cage``), so it works with no hooks
    and no project. Each agent prints its own count line; the proxy fallback for those
    with no on-disk usage log. Always exits 0 (fail-open)."""
    for line in importcmd.run(ledger_root(), args.agent, args):
        print(line)
    return 0


def cmd_import_codex(args) -> int:
    n, m = importcmd.import_codex(ledger_root(), args)
    print(f"✔ imported {n} Codex call(s) from {m} rollout file(s).")
    return 0


def cmd_import_claude(args) -> int:
    """Meter Claude Code with no hooks/MCP — pull the transcripts it already writes
    to disk. Idempotent (append_new dedupes on the per-turn call id), fail-open per
    file (an unreadable transcript is skipped, never raised), $0/offline."""
    n, m = importcmd.import_claude(ledger_root(), args)
    print(f"✔ imported {n} Claude call(s) from {m} transcript(s).")
    return 0


def cmd_export(args) -> int:
    """Import-first (unless ``--no-import``) then emit the active ledger as jsonl/csv/json
    (counts-never-content, deterministic). The universal pull-based export path."""
    r = ledger_root()
    args.project = _project_filter(args)
    return exportcmd.run(r, args, pol=_policy(r))


def cmd_watch(args) -> int:
    """Foreground poll loop — import every interval until Ctrl-C. Registers no OS job."""
    return watchcmd.run(ledger_root(), args)
