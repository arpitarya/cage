"""Command handlers — load policy, derive a view, print it (plan §7, §8)."""
from __future__ import annotations

from cage import (agents, attribution, budget, demo, doctorcmd,
                  explain, forecast, graphifymeter, humanview, importcmd, initcmd,
                  ledger, ledgersync, matrix, mcpserver, metercmd, metering, notessync,
                  origin, paths, policy, provenance, proxy, quality, recommend, regression,
                  report, roi, serve, tasks, trend, verifycmd, wizard)
from cage.cliutil import emit, root


def _policy():
    return policy.load(paths.Footprint(root()).policy)


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
    rep = report.summarize(root(), _policy(), dim=args.by, since=args.since,
                           scope=getattr(args, "scope", None),
                           team=getattr(args, "team", False))
    return emit(args, rep, report.render_report(rep))


def cmd_overview(args) -> int:
    """Bare `cage` — the one-look spent/saved/net headline (§4). No subcommand."""
    o = report.overview(root(), _policy())
    return emit(args, o, report.render_overview(o))


def cmd_attrib(args) -> int:
    r = root()
    task = args.task or _latest_task(r)
    data = attribution.attribute(r, task, _policy(), scope=getattr(args, "scope", None),
                                 team=getattr(args, "team", False))
    return emit(args, data, attribution.render_attrib(data))


def cmd_matrix(args) -> int:
    r = root()
    task = args.task or _latest_task(r)
    data = matrix.matrix(r, task, _policy(), human=getattr(args, "human", False),
                         scope=getattr(args, "scope", None))
    text = matrix.render_matrix(data)
    if getattr(args, "html", None):
        serve.write_html(args.html, f"Matrix · {task}", {f"Matrix · {task}": text})
        print(f"✔ wrote {args.html}")
        return 0
    return emit(args, data, text)


def cmd_human(args) -> int:
    r = root()
    data = humanview.rollup(r, _policy(), since=args.since, agent=args.agent, task=args.task)
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
                                root=root())
    print(f"✔ recorded human alternative for {args.task!r}." if rid
          else f"· {args.task!r} already has a human receipt for that call (no double count).")
    return 0


def cmd_trend(args) -> int:
    data = trend.series(root(), _policy(), by=args.by, since=args.since)
    text = trend.render_trend(data, metric=args.metric)
    if getattr(args, "html", None):
        serve.write_html(args.html, "Savings trend", {"Savings trend": text})
        print(f"✔ wrote {args.html}")
        return 0
    return emit(args, data, text)


def cmd_budget(args) -> int:
    verdict = budget.check(root(), _policy(), session=args.session,
                           scope=getattr(args, "scope", None))
    return emit(args, verdict, budget.render_budget(verdict))


def cmd_roi(args) -> int:
    data = roi.by_tool(root(), _policy(), since=args.since)
    return emit(args, data, roi.render_roi(data))


def cmd_why(args) -> int:
    data = provenance.explain(root(), args.call_id)
    return emit(args, data, provenance.render_why(data, args.call_id))


def cmd_serve(args) -> int:
    return serve.serve(root(), port=args.port)


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
    call_id = demo.seed(root())
    print(f"✔ Seeded the §4.4 worked example (task {demo.TASK!r}, call {call_id}).")
    print("  Now run:  cage attrib   ·   cage matrix   ·   cage report")
    return 0


# ── §8 ledger features ───────────────────────────────────────────────────────

def cmd_quality(args) -> int:
    s = quality.summarize(root())
    return emit(args, s, quality.render_quality(s))


def cmd_outcome(args) -> int:
    r = root()
    quality.record_outcome(r, args.task, ok=not args.redo)
    tasks.record(r, args.task, outcome="ok" if not args.redo else "redo")
    print(f"✔ recorded {args.task!r} as {'redo' if args.redo else 'ok'}.")
    return 0


def cmd_regression(args) -> int:
    r = regression.detect(root(), since=args.since, tolerance=args.tolerance)
    return emit(args, r, regression.render_regression(r))


def cmd_recommend(args) -> int:
    r = recommend.recommend(root(), _policy(), since=args.since)
    return emit(args, r, recommend.render_recommend(r))


def cmd_forecast(args) -> int:
    f = forecast.project(root(), _policy())
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

    # Handle --status: report current wiring and exit
    if getattr(args, "status", False):
        for surface, on in agents.status(here).items():
            print(f"  {'✔' if on else '·'} {surface:<8} {'wired' if on else 'not wired'}")
        return 0

    # Handle --wire-only: agent wiring only, no scaffold/graphify
    if getattr(args, "wire_only", False):
        flagged = tuple(s for s in agents.SURFACES if getattr(args, s, False))
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

    # Standard setup: interactive wizard or flagged agents
    flagged = tuple(s for s in agents.SURFACES if getattr(args, s, False))
    if not flagged:
        if not sys.stdin.isatty():
            print("Pick an agent: " + " | ".join(agents.SURFACES))
            print("e.g. `cage setup --claude`  (or run `cage setup` in a terminal "
                  "for the guided wizard)")
            return 2
        plans = [wizard.interactive_plan()]
    else:
        plans = [{"agent": a, "skill": args.skill, "project": args.project,
                  "graphify": args.graphify} for a in flagged]

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
    """Umbrella hookless import across all four agents (default ``--agent all``).
    Each agent prints its own line: an import count for log-bearing agents, the proxy
    fallback for those with no on-disk usage log. Always exits 0 (fail-open)."""
    for line in importcmd.run(root(), args.agent, args):
        print(line)
    return 0


def cmd_import_codex(args) -> int:
    n, m = importcmd.import_codex(root(), args)
    print(f"✔ imported {n} Codex call(s) from {m} rollout file(s).")
    return 0


def cmd_import_claude(args) -> int:
    """Meter Claude Code with no hooks/MCP — pull the transcripts it already writes
    to disk. Idempotent (append_new dedupes on the per-turn call id), fail-open per
    file (an unreadable transcript is skipped, never raised), $0/offline."""
    n, m = importcmd.import_claude(root(), args)
    print(f"✔ imported {n} Claude call(s) from {m} transcript(s).")
    return 0
