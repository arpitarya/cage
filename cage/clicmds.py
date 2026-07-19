"""Command handlers — load policy, derive a view, print it (plan §7, §8)."""
from __future__ import annotations

import re
from pathlib import Path

from cage import (adoptcmd, agents, attribution, budget, compare, demo, doctorcmd,
                  explain, exportcmd, forecast, graphifymeter, humanview, importcmd, initcmd,
                  ledger, ledgersync, limits, matrix, mcpserver, metercmd, metering, notessync,
                  origin, paths, policy, provenance, proxy, quality, recommend, regression,
                  render, report, roi, serve, tasks, trend, verifycmd, watchcmd, wizard)
from cage.cliutil import captured_read_root, csv_dest, emit, ledger_root, root
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


def cmd_report(args) -> int:
    from cage import display, policy
    r = captured_read_root(args)
    pol = _policy(r)
    rep = report.summarize(r, pol, dim=args.by, since=args.since,
                           scope=getattr(args, "scope", None),
                           project=_project_filter(args),
                           team=getattr(args, "team", False))
    if (dest := csv_dest(args)) is not None:
        from cage import csvout
        return csvout.write(report.render_csv(rep), dest)
    return emit(args, rep, report.render_report(
        rep, last_import=importcmd.last_import(r), disp=display.resolve(args, pol),
        stale_hours=policy.import_stale_hours(pol), health=importcmd.capture_health(r)))


def cmd_overview(args) -> int:
    """Bare `cage` — the one-look headline (§4; tokens by default, plan Phase 2.5).
    No subcommand."""
    from cage import display
    r = captured_read_root(args)
    pol = _policy(r)
    o = report.overview(r, pol)
    return emit(args, o, report.render_overview(
        o, last_import=importcmd.last_import(r), disp=display.resolve(args, pol)))


def cmd_attrib(args) -> int:
    r = captured_read_root(args)
    task = args.task or _latest_task(r)
    data = attribution.attribute(r, task, _policy(r), scope=getattr(args, "scope", None),
                                 team=getattr(args, "team", False))
    if (dest := csv_dest(args)) is not None:
        from cage import csvout
        return csvout.write(attribution.render_csv(data), dest)
    return emit(args, data, attribution.render_attrib(data))


def cmd_matrix(args) -> int:
    from cage import display
    r = captured_read_root(args)
    pol = _policy(r)
    task = args.task or _latest_task(r)
    data = matrix.matrix(r, task, pol, human=getattr(args, "human", False),
                         scope=getattr(args, "scope", None))
    # --human implies the $ view: the anchor row and vs-human columns are dollars.
    usd = display.resolve(args, pol).usd or getattr(args, "human", False)
    text = matrix.render_matrix(data, usd=usd)
    if getattr(args, "html", None):
        serve.write_html(args.html, f"Matrix · {task}", {f"Matrix · {task}": text})
        print(f"✔ wrote {args.html}")
        return 0
    return emit(args, data, text)


def cmd_human(args) -> int:
    r = captured_read_root(args)
    data = humanview.rollup(r, _policy(r), since=args.since, agent=args.agent, task=args.task)
    if (dest := csv_dest(args)) is not None:
        from cage import csvout
        return csvout.write(humanview.render_csv(data), dest)
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
    r = captured_read_root(args)
    data = trend.series(r, _policy(r), by=args.by, since=args.since)
    if (dest := csv_dest(args)) is not None:
        from cage import csvout
        return csvout.write(trend.render_csv(data), dest)
    text = trend.render_trend(data, metric=args.metric)
    if getattr(args, "html", None):
        serve.write_html(args.html, "Savings trend", {"Savings trend": text})
        print(f"✔ wrote {args.html}")
        return 0
    return emit(args, data, text)


def cmd_budget(args) -> int:
    r = captured_read_root(args)
    verdict = budget.check(r, _policy(r), session=args.session,
                           scope=getattr(args, "scope", None))
    return emit(args, verdict, budget.render_budget(verdict))


def cmd_limits(args) -> int:
    """`cage data limits` — provider quota windows (latest local snapshot) + estimated
    AI-credit consumption (token-based providers only). `--json` emits the `cage.v1`
    envelope. Read-only/derive; never writes the ledger."""
    r = captured_read_root(args)
    data = limits.rollup(r, _policy(r))
    if getattr(args, "json", False):
        import json
        print(json.dumps(render.envelope("limits", data), ensure_ascii=False, indent=2))
        return 0
    print(limits.render_limits(data))
    return 0


def cmd_roi(args) -> int:
    r = captured_read_root(args)
    data = roi.by_tool(r, _policy(r), since=args.since)
    if (dest := csv_dest(args)) is not None:
        from cage import csvout
        return csvout.write(roi.render_csv(data), dest)
    return emit(args, data, roi.render_roi(data))


def cmd_why(args) -> int:
    lr = captured_read_root(args)
    data = provenance.explain(lr, args.call_id, pol=_policy(lr))
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
    root = ledger_root()
    already = any(c.get("task") == demo.TASK for c in ledger.calls(root))
    call_id = demo.seed(root)
    verb = "already seeded" if already else "Seeded"
    print(f"✔ {verb} the §4.4 worked example (task {demo.TASK!r}, call {call_id}).")
    print("  Now run:  cage insights attrib   ·   cage insights matrix   ·   cage report")
    return 0


# ── §8 ledger features ───────────────────────────────────────────────────────

def cmd_quality(args) -> int:
    lr = captured_read_root(args)
    s = quality.summarize(lr, pol=_policy(lr))
    return emit(args, s, quality.render_quality(s))


_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}\Z")


def cmd_outcome(args) -> int:
    r = ledger_root()
    label = getattr(args, "label", None) or ""
    if label and not _LABEL.match(label):
        # Single-token PII guard (roadmap P2): a label is a grouping key for
        # `cage insights compare --by label`, never free text, a path, or a message.
        raise CageError("label must be one short token (letters/digits/._-, ≤32 chars) "
                        "— no spaces, slashes, or paths")
    quality.record_outcome(r, args.task, ok=not args.redo)
    tasks.record(r, args.task, outcome="ok" if not args.redo else "redo", label=label)
    tag = f" (label: {label})" if label else ""
    print(f"✔ recorded {args.task!r} as {'redo' if args.redo else 'ok'}{tag}.")
    minutes = getattr(args, "minutes", None)
    if minutes is not None:
        # The §6 attestation friction-drop: same fail-open, idempotent receipt path
        # as `cage human record --minutes` — attested minutes outrank derived
        # turn-gap minutes for this task (never summed).
        rid = metering.record_human(task=args.task, minutes=minutes, root=r)
        print(f"✔ attested {minutes:g} human minute(s) for {args.task!r}." if rid
              else f"· {args.task!r} already has a human receipt (no double count).")
    return 0


def cmd_compare(args) -> int:
    r = captured_read_root(args)
    by = tuple(k.strip() for k in (args.by or "stack").split(",") if k.strip())
    bad = [k for k in by if k not in ("stack", "scope", "label")]
    if bad:
        raise CageError(f"unknown --by key(s) {bad}; choose from stack, scope, label")
    d = compare.summarize(r, _policy(r), by=by, scope=args.scope, label=args.label,
                          agent_only=getattr(args, "agent_only", False))
    if (dest := csv_dest(args)) is not None:
        from cage import csvout
        return csvout.write(compare.render_csv(d), dest)
    return emit(args, render.envelope("compare", d) if args.json else d,
                compare.render_compare(d))


def cmd_estimate(args) -> int:
    from cage import estimate
    r = captured_read_root(args)
    d = estimate.band(r, _policy(r), scope=args.scope, label=args.label, agent=args.agent)
    recorded = ""
    if args.record:
        if not d["ok"]:
            raise CageError(f"cannot record: {d['reason']}")
        if tasks.read(r).get(args.record, {}).get("outcome"):
            # A retroactive estimate is exactly what calibration must never count.
            raise CageError(f"task {args.record!r} is already closed — "
                            "record estimates before the task runs")
        if not estimate.record(r, args.record, d):  # fail-open write; surface at CLI
            raise CageError("estimate could not be written (ledger not writable?)")
        recorded = args.record
    payload = {**d, **({"recorded": recorded} if recorded else {})}
    return emit(args, render.envelope("estimate", payload) if args.json else payload,
                estimate.render_estimate(d, recorded))


def cmd_calibration(args) -> int:
    from cage import calibration
    r = captured_read_root(args)
    if getattr(args, "human", False):  # plan §4.10 — score the turn-gap heuristic
        d = calibration.summarize_human(r, _policy(r))
        if (dest := csv_dest(args)) is not None:
            from cage import csvout
            return csvout.write(calibration.render_csv_human(d), dest)
        return emit(args, render.envelope("calibration", d) if args.json else d,
                    calibration.render_calibration_human(d))
    d = calibration.summarize(r, _policy(r))
    if (dest := csv_dest(args)) is not None:
        from cage import csvout
        return csvout.write(calibration.render_csv(d), dest)
    return emit(args, render.envelope("calibration", d) if args.json else d,
                calibration.render_calibration(d))


def cmd_verdict(args) -> int:
    from cage import verdict
    r = captured_read_root(args)
    d = verdict.compose(r, _policy(r), args.tool, since=args.since,
                        agent_only=getattr(args, "agent_only", False))
    return emit(args, render.envelope("verdict", d) if args.json else d,
                verdict.render_verdict(d))


def cmd_prices(args) -> int:
    """`cage prices <list|unpriced|set|alias|sync>` (plan §3.3). Reads and writes
    both act on the *resolved* ledger root — writes land in that root's project
    policy.toml; the bundled table is read-only at runtime."""
    from cage import pricescmd
    r = ledger_root()
    payload, text = pricescmd.run(args, r, _policy(r))
    return emit(args, render.envelope("prices", payload) if args.json else payload, text)


def cmd_policy(args) -> int:
    """`cage policy <diff|sync>` (plan §3.10) — upgrade the resolved root's
    project policy.toml to the installed bundle; dry-run by default, never
    auto-applied by anything."""
    from cage import policysync
    r = ledger_root()
    payload, text = policysync.run(args, r, _policy(r))
    return emit(args, render.envelope("policy", payload) if args.json else payload, text)


def cmd_cleanup(args) -> int:
    """`cage data cleanup` — dry-run print by default (house pattern), --apply prunes."""
    from cage import cleanup
    r = ledger_root()
    payload, text = cleanup.run_cli(r, _policy(r), apply=args.apply,
                                    days=getattr(args, "days", None))
    return emit(args, render.envelope("cleanup", payload) if args.json else payload, text)


def cmd_study(args) -> int:
    """Fleet-study verbs (plan §4.9). Markers/report act on the *active* ledger
    (capture lands there); `join` additionally wires this project's agents."""
    from cage import machine, study
    r = ledger_root()
    if args.action != "report" and getattr(args, "csv", None) is not None:
        raise CageError("--csv applies to `cage study report` only")
    if args.action == "id":
        mid = machine.machine_id(r)
        print(mid if mid else "not enrolled — `cage study join <phase>` (or `start`) "
                              "generates the opaque machine id")
        return 0
    if args.action == "start":
        if not args.phase:
            raise CageError("cage study start needs a phase label (one short token)")
        mid = study.start(r, args.phase)
        print(f"✔ phase {args.phase!r} started (machine {mid}) — rows from now on are "
              "assigned to it by their own timestamps")
        return 0
    if args.action == "stop":
        study.stop(r)
        print("✔ phase stopped — rows after this marker are unphased until the next start")
        return 0
    if args.action == "report":
        d = study.summarize(r, _policy(r), agent_only=getattr(args, "agent_only", False))
        if (dest := csv_dest(args)) is not None:
            from cage import csvout
            return csvout.write(study.render_csv(d), dest)
        return emit(args, render.envelope("study", d) if args.json else d,
                    study.render_study(d))
    # join — one-command enrollment: scaffold → wire all four → start → doctor
    if not args.phase:
        raise CageError("cage study join needs the starting phase label (e.g. baseline)")
    initcmd.run(paths.resolve_root(), pointer=False)
    wired = agents.install(root())
    mid = study.start(r, args.phase)
    print(f"✔ enrolled: machine {mid} · phase {args.phase!r} started · wired: "
          + ", ".join(sorted(wired)))
    res = doctorcmd.run(root())
    glyph = {"ok": "✔", "warn": "·", "fail": "✗"}
    for c in res["checks"]:
        print(f"  {glyph[c['level']]} {c['name']:<12} {c['detail']}")
    print(f"\n{glyph[res['status']]} doctor: {res['status']} — automate capture with your "
          f"own scheduler line, e.g.:  {render.scheduler_hint()}   (cage installs no scheduler)")
    return 1 if res["status"] == "fail" else 0


def cmd_regression(args) -> int:
    lr = captured_read_root(args)
    r = regression.detect(lr, since=args.since, tolerance=args.tolerance, pol=_policy(lr))
    return emit(args, r, regression.render_regression(r))


def cmd_recommend(args) -> int:
    lr = captured_read_root(args)
    r = recommend.recommend(lr, _policy(lr), since=args.since)
    return emit(args, r, recommend.render_recommend(r))


def cmd_forecast(args) -> int:
    lr = captured_read_root(args)
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
    # is the project-less capture sink (plan §3.7) — `cage import`/`cage data export` from any
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

    # Persist the wiring mode FIRST (docs/restricted-environments.md): the flag is a
    # project-policy setting (`[wiring] python_launcher`), so it must land before any
    # wiring path below — agents.install re-reads it from policy on every run, which
    # is also why a later plain `cage setup` preserves the mode with no flag repeated.
    if getattr(args, "python_launcher", False):
        from cage import pricestoml
        if not paths.Footprint(here).policy.exists():
            initcmd.run(here)  # the mode needs a project policy file to live in
            print("✔ .cage/ scaffolded (needed to persist the wiring mode)")
        res = pricestoml.set_wiring(here, {"python_launcher": True})
        print(f"✔ wiring mode → python-launcher ({res['mode']}, {res['path']})")

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
        print("Metering: claude=transcript hook · others=`cage data meter -- <cmd>` or `cage data proxy`.")
        return 0

    # Handle --project-only: scaffold + graphify + PATH, no global skill
    project_only = getattr(args, "project_only", False)
    if project_only:
        # Override the flags for project-only mode
        args.skill = False
        args.project = True
        args.graphify = getattr(args, "graphify", True)
        # `--project-only` is agent-independent scaffolding (its --help: "scaffold
        # .cage/ + graphify + PATH only"). With no agent flag, scaffold and stop —
        # don't fall through to the "pick an agent" wiring path and no-op. Wiring an
        # agent stays a separate, explicit step (`cage setup --wire-only --<agent>`).
        if not all_agents and not any(getattr(args, s, False) for s in agents.SURFACES):
            res = adoptcmd.run(here, graphify=args.graphify, surfaces=None)
            print("\n▸ cage setup — project scaffold")
            print(f"  ✔ .cage/ ready → {res['init']}")
            if "shim" in res:
                print(f"  ✔ graphify interceptor → {res['shim']}")
                if res.get("path"):
                    print(f"  ✔ bin/ added to PATH in {res['path']} — open a new shell")
            elif args.graphify:
                print("  · graphify not installed — interceptor skipped")
            print("\nDone. Verify with `cage doctor`; wire an agent with "
                  "`cage setup --wire-only --<agent>`.")
            return 0

    # init merged into setup (plan Phase 3 §2): ensure .cage/ exists first — the old
    # `init` verb's job, now unconditional step one of onboarding. Idempotent, so the
    # wizard's adopt step (when --project/--graphify also scaffold) re-runs it
    # harmlessly; this closes the skill-only (`--no-project --no-graphify`) gap.
    initcmd.run(here)

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
    if getattr(args, "paths", False):
        from cage import pathprobe
        try:  # fail-open: a broken policy still shows built-in candidates
            pol = policy.load(paths.Footprint(paths.resolve_root(root())).policy)
        except Exception:  # noqa: BLE001
            pol = {}
        print(pathprobe.run(root(), pol))
        return 0
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
    if getattr(args, "bundle", None):
        from cage import doctorbundle
        out = doctorbundle.run(root(), args.bundle)
        print(f"✔ diagnostics bundle written: {out} (redacted — counts-never-content)")
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
    default — mirrors `cage authorship notes-sync`; CI (`CAGE_NOTES_WRITE=1`) is the sole writer."""
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
                                f"ledger keeps the first attestation (run `cage authorship origin {args.sha}` to see it).",
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
    print(f"\ncage authorship verify: {len(res['warnings'])} warning(s) — report-only, never fails the build.")
    return 0


def cmd_import(args) -> int:
    """Umbrella hookless import across all four agents (default ``--agent all``) — the
    canonical explicit capture verb. Captures into the active ledger (``--ledger``/
    ``CAGE_BASE`` → project ``.cage/`` → global ``~/.cage``), so it works with no hooks
    and no project. Each agent prints its own count line; the proxy fallback for those
    with no on-disk usage log. Always exits 0 (fail-open).

    With positional BUNDLE args (fleet path, plan §4.9), merges study bundles by row
    identity instead — the analyst's verb; idempotent, a bad bundle is a typed error."""
    if getattr(args, "bundles", None):
        from cage import study
        for line in study.import_bundles(ledger_root(), args.bundles):
            print(line)
        return 0
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
    (counts-never-content, deterministic). The universal pull-based export path.
    ``--study`` writes the one-file fleet bundle instead (plan §4.9)."""
    r = ledger_root()
    pol = _policy(r)
    if getattr(args, "study", None) is not None:
        if getattr(args, "csv_kind", None) or getattr(args, "format", None):
            # Two export kinds, never blurred: the bundle is lossless jsonl by
            # design; CSV is one-way reporting and never an import source.
            raise CageError("--study writes the jsonl fleet bundle — it cannot "
                            "combine with --csv/--format (`cage query csv-output`)")
        from cage import study
        refresh = {"ran": False, "new_calls": 0}
        if getattr(args, "do_import", True) and policy.import_before_export(pol):
            ran, added = exportcmd.sweep(r, getattr(args, "since", None))
            refresh = {"ran": ran, "new_calls": added}
        out = study.export_bundle(r, args.study or None, refresh=refresh)
        tag = (f"self-refreshed: +{refresh['new_calls']} call(s)" if refresh["ran"]
               else "snapshot only (no sweep)")
        print(f"✔ study bundle written: {out} (rows + phase markers + counts-only "
              f"manifest · {tag})")
        return 0
    args.project = _project_filter(args)
    return exportcmd.run(r, args, pol=pol)


def cmd_watch(args) -> int:
    """Foreground poll loop — import every interval until Ctrl-C. Registers no OS job."""
    return watchcmd.run(ledger_root(), args)
