"""Command handlers — load policy, derive a view, print it (plan §7, §8)."""
from __future__ import annotations

from pathlib import Path

from cage import (adoptcmd, agents, attribution, budget, demo, doctorcmd,
                  forecast, graphifymeter, hooks, humanview, initcmd, ledger,
                  matrix, mcpserver, metercmd, metering, paths, policy, provenance,
                  proxy, quality, recommend, regression, report, roi, serve,
                  setupcmd, tasks, trend, transcript)
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
    rep = report.summarize(root(), dim=args.by, since=args.since)
    return emit(args, rep, report.render_report(rep))


def cmd_attrib(args) -> int:
    r = root()
    task = args.task or _latest_task(r)
    data = attribution.attribute(r, task, _policy())
    return emit(args, data, attribution.render_attrib(data))


def cmd_matrix(args) -> int:
    r = root()
    task = args.task or _latest_task(r)
    data = matrix.matrix(r, task, _policy(), human=getattr(args, "human", False))
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
    verdict = budget.check(root(), _policy(), session=args.session)
    return emit(args, verdict, budget.render_budget(verdict))


def cmd_roi(args) -> int:
    data = roi.by_tool(root(), _policy(), since=args.since)
    return emit(args, data, roi.render_roi(data))


def cmd_why(args) -> int:
    data = provenance.explain(root(), args.call_id)
    return emit(args, data, provenance.render_why(data, args.call_id))


def cmd_serve(args) -> int:
    return serve.serve(root(), port=args.port)


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


def cmd_setup(_args) -> int:
    for agent, where in setupcmd.run().items():
        print(f"✔ {agent:<8} → {where}")
    print("Next, in a project: `cage adopt` "
          "(init + wire claude/codex/copilot/kiro + graphify interceptor).")
    return 0


def cmd_adopt(args) -> int:
    picked = tuple(s for s in agents.SURFACES if getattr(args, s, False)) or None
    res = adoptcmd.run(root(), hooks=args.hooks, graphify=args.graphify,
                       surfaces=picked)
    if getattr(args, "json", False):
        import json
        print(json.dumps(res))
        return 0
    print(f"✔ .cage/ ready → {res['init']}")
    if "hooks" in res:
        wired = ", ".join(res["hooks"])  # one ledger, the surfaces actually wired
        print(f"✔ agent metering + MCP wired for: {wired}")
    if "shim" in res:
        print(f"✔ graphify interceptor → {res['shim']}")
        if res.get("path"):
            print(f"✔ bin/ added to PATH in {res['path']} — open a new shell to meter graphify")
    elif args.graphify:
        print("· graphify not installed — interceptor skipped")
    print("Done. Verify with `cage doctor`; then `cage report` / `cage matrix`.")
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
                   "fail": "Cage setup is broken (see ✗) — run `cage adopt`."}
        print(f"\n{glyph[res['status']]} {verdict[res['status']]}")
    return 1 if res["status"] == "fail" else 0


def cmd_hooks(args) -> int:
    here = root()
    if args.action == "status":
        for surface, on in agents.status(here).items():
            print(f"  {'✔' if on else '·'} {surface:<8} {'wired' if on else 'not wired'}")
        return 0
    picked = tuple(s for s in agents.SURFACES if getattr(args, s, False)) or None
    print("✔ Cage wired into:")
    for surface, where in agents.install(here, picked).items():
        print(f"  {surface:<8} → {', '.join(where.values())}")
    print("Metering: claude=transcript hook · others=`cage meter -- <cmd>` or `cage proxy`.")
    return 0


def cmd_import_codex(args) -> int:
    here = root()
    src = Path(args.path)
    files = sorted(src.glob("**/rollout-*.jsonl")) if src.is_dir() else [src]
    total = 0
    for f in files:
        total += hooks.append_new(here, transcript.parse_codex_calls(f))
    print(f"✔ imported {total} Codex call(s) from {len(files)} rollout file(s).")
    return 0
