"""Command handlers — load policy, derive a view, print it (plan §7, §8)."""
from __future__ import annotations

import re
from pathlib import Path

from cage import (adoptcmd, agents, attribution, budget, compare, demo, doctorcmd,
                  explain, exportcmd, forecast, graphifymeter, importcmd, initcmd,
                  ledger, ledgersync, matrix, mcpserver, metercmd, metering, notessync,
                  origin, paths, policy, provenance, proxy, quality, recommend, regression,
                  render, report, roi, serve, tasks, verifycmd, watchcmd)
from cage.cliutil import captured_read_root, csv_dest, emit, ledger_root, root
from cage.constants import COMMITS_DEFAULT_ROWS
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
    import sys
    foot = paths.Footprint(r or root())
    if (shadowed := foot.shadowed_config) is not None:
        # Both cage.toml and the legacy policy.toml on disk: cage.toml wins, the other
        # is silently ignored. Name it once on stderr (stdout stays byte-identical) so
        # the user isn't editing a file cage never reads. `cage doctor` explains it fully.
        print(f"⚠ cage: {shadowed.name} is ignored — {foot.policy.name} takes precedence "
              f"(delete {shadowed.name} to silence this)", file=sys.stderr)
    if foot.shadowed_prices is not None:
        # prices.toml exists AND the policy file still declares [prices…]/[credits…]:
        # prices.toml wins, the in-cage.toml block is ignored (prices-toml plan §3). Name
        # it once on stderr; `cage doctor` / `cage query prices-file` explain it.
        print(f"⚠ cage: the [prices]/[credits] block in {foot.shadowed_prices.name} is "
              f"ignored — {paths.PRICES_FILENAME} takes precedence (remove those tables "
              f"from {foot.shadowed_prices.name} to silence this)", file=sys.stderr)
    path = foot.policy
    try:
        return policy.load(path)
    except Exception as e:  # noqa: BLE001 — malformed config → clean CLI error, not a traceback
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

    def text() -> str:
        # G4: the graphify day-one repo ceiling (modeled) surfaces in the footer. Read
        # here (I/O) so render_report stays pure; silent in non-graphify projects. Uses
        # cwd's graphify-out/, not the ledger root — the graph describes the working
        # project. **Lazy**: a plain `--csv` run never renders text, so it never pays
        # for this read — and CSV still never sees the ceiling (G4).
        from cage import graphifymodel
        return report.render_report(
            rep, last_import=importcmd.last_import(r), disp=display.resolve(args, pol),
            stale_hours=policy.import_stale_hours(pol), health=importcmd.capture_health(r),
            ceiling=graphifymodel.repo_ceiling(r),
            kiro_route=report.kiro_routed_line(r, pol))

    return emit(args, rep, text, csv=lambda: report.render_csv(rep), root=r)


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
    return emit(args, data, attribution.render_attrib(data),
                csv=lambda: attribution.render_csv(data), root=r)


def cmd_matrix(args) -> int:
    from cage import display
    r = captured_read_root(args)
    pol = _policy(r)
    task = args.task or _latest_task(r)
    data = matrix.matrix(r, task, pol, scope=getattr(args, "scope", None))
    text = matrix.render_matrix(data, usd=display.resolve(args, pol).usd)
    if getattr(args, "html", None):
        serve.write_html(args.html, f"Matrix · {task}", {f"Matrix · {task}": text})
        print(f"✔ wrote {args.html}")
        return 0
    return emit(args, data, text, root=r)


def cmd_budget(args) -> int:
    r = captured_read_root(args)
    verdict = budget.check(r, _policy(r), session=args.session,
                           scope=getattr(args, "scope", None))
    return emit(args, verdict, budget.render_budget(verdict), root=r)


def cmd_roi(args) -> int:
    r = captured_read_root(args)
    data = roi.by_tool(r, _policy(r), since=args.since)
    return emit(args, data, roi.render_roi(data),
                csv=lambda: roi.render_csv(data), root=r)


def cmd_adoption(args) -> int:
    """`cage insights adoption` — counts only; no policy is loaded because nothing in
    this view prices anything (the diagnostic-only invariant, `adoption.py`'s docstring)."""
    from cage import adoption
    r = captured_read_root(args)
    data = adoption.summarize(r, since=args.since)
    return emit(args, data, adoption.render_adoption(data),
                csv=lambda: adoption.render_csv(data), root=r)


def cmd_chats(args) -> int:
    """`cage insights chats` — per-chat detail view; local-only by construction (no
    `--team`, `chats.py`'s module docstring)."""
    from cage import chats, display
    r = captured_read_root(args)
    pol = _policy(r)
    data = chats.summarize(r, pol, since=args.since, agent=getattr(args, "agent", None))
    return emit(args, data, chats.render_chats(
        data, disp=display.resolve(args, pol), show_all=getattr(args, "all", False),
        kiro_route=report.kiro_routed_line(r, pol, verb="insights chats")),
        csv=lambda: chats.render_csv(data), root=r)


def cmd_graphify_chats(args) -> int:
    """`cage insights graphify` — per-chat graphify usage & GROSS saving; tokens-only,
    no `--usd` (graphify-chats handoff)."""
    from cage import graphifychat
    r = captured_read_root(args)
    pol = _policy(r)
    data = graphifychat.summarize(r, pol, since=args.since,
                                  agent=getattr(args, "agent", None))
    return emit(args, data, graphifychat.render_view(
        data, show_all=getattr(args, "all", False),
        all_chats=getattr(args, "all_chats", False),
        kiro_route=report.kiro_routed_line(r, pol, verb="insights graphify")),
        csv=lambda: graphifychat.render_csv(data), root=r)


def cmd_commits(args) -> int:
    """`cage insights commits` — per-commit tokens, hours and the line split.
    **No USD**: nothing on this surface is priced, so no `display` context is
    resolved and no dollar column can appear (`commitview.py`'s docstring)."""
    from cage import commitview
    r = captured_read_root(args)
    # ⚠️ Still no default `--since`, deliberately — a *relative* default window would put
    # a wall clock in the default path (the same ledger renders differently next month
    # with no code change). COMMITS-WINDOW closed 2026-08-11 with verdict **B** instead:
    # the cost is bounded by the ROW CAP, the axis this view is already paged on, and
    # only on the **text** path. `--csv`/`--json` stay complete (CSV is never truncated)
    # and pay full cost — honestly, rather than accidentally; `--all` lifts it everywhere.
    full = (getattr(args, "all", False) or csv_dest(args) is not None
            or getattr(args, "json", False) or getattr(args, "export", None) is not None)
    data = commitview.summarize(r, _policy(r), since=args.since,
                                limit=None if full else COMMITS_DEFAULT_ROWS)
    return emit(args, render.envelope("commits", data) if args.json else data,
                commitview.render_commits(data, show_all=getattr(args, "all", False)),
                csv=lambda: commitview.render_csv(data), root=r)


def cmd_commit(args) -> int:
    """`cage insights commit <sha>` — one commit in detail."""
    from cage import commitview
    r = captured_read_root(args)
    data = commitview.summarize(r, _policy(r), sha=args.sha)
    return emit(args, render.envelope("commit", data) if args.json else data,
                commitview.render_commit(data, show_files=getattr(args, "files", False)),
                csv=lambda: commitview.render_csv(data), root=r)


def cmd_authorship_summary(args) -> int:
    """`cage authorship summary` — unknown-rate first, then what was recorded."""
    from cage import commitview
    r = captured_read_root(args)
    data = commitview.summarize_authorship(r, _policy(r), since=args.since)
    # Through the ONE chokepoint, like the other exportable views — the hand-rolled
    # `csv_dest` branch this replaced is exactly the duplication `emit` exists to remove
    # (and is why this view had no `--export`).
    return emit(args, render.envelope("authorship-summary", data) if args.json else data,
                commitview.render_authorship(data),
                csv=lambda: commitview.render_authorship_csv(data), root=r)


def cmd_why(args) -> int:
    lr = captured_read_root(args)
    data = provenance.explain(lr, args.call_id, pol=_policy(lr))
    return emit(args, data, provenance.render_why(data, args.call_id), root=lr)


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
    # No `csv=`: this view owns no `render_csv`, so `--export` refuses that format with a
    # typed message rather than writing an empty file (an empty CSV reads as *no rows*).
    return emit(args, s, quality.render_quality(s), root=lr)


_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}\Z")


def close_task(root, task: str, *, redo: bool = False, label: str = "") -> str:
    """Record a task's outcome and return the confirmation line.

    **The one task-close path**, shared by `cage task outcome` and the MCP
    `cage_task_outcome` tool (the ladder's only write tool) — so the label guard,
    the append-only semantics and the wording cannot diverge between the two
    surfaces. Both writes are appends: `tasks.jsonl` is last-write-wins by id, so
    re-closing a task supersedes the earlier row and never rewrites it.
    """
    label = label or ""
    if label and not _LABEL.match(label):
        # Single-token PII guard (roadmap P2): a label is a grouping key for
        # `cage insights compare --by label`, never free text, a path, or a message.
        raise CageError("label must be one short token (letters/digits/._-, ≤32 chars) "
                        "— no spaces, slashes, or paths")
    quality.record_outcome(root, task, ok=not redo)
    tasks.record(root, task, outcome="redo" if redo else "ok", label=label)
    tag = f" (label: {label})" if label else ""
    return f"✔ recorded {task!r} as {'redo' if redo else 'ok'}{tag}."


def cmd_outcome(args) -> int:
    print(close_task(ledger_root(), args.task, redo=args.redo,
                     label=getattr(args, "label", None) or ""))
    return 0


def cmd_task_time(args) -> int:
    """`cage task time <duration>` — attest how long *you* spent on a task (v2 P4).

    The one number on the authorship surfaces a person asserts outright, so it is
    written with `human_minutes_method="attested"` and **always outranks** the
    estimator in `cage insights commits`. It is minutes only: **no rate, no USD**, here
    or anywhere downstream — that pairing is what killed the v1 axis.

    Task rows are append-only and last-write-wins by id, so re-attesting supersedes
    rather than rewrites. `snapshot=False`: re-running git here would overwrite the
    task's recorded `commit`/diff counts with *now*, and it is that recorded sha the
    hours are attached to."""
    r = ledger_root()
    try:
        minutes = tasks.parse_duration(args.duration)
    except ValueError as e:
        raise CageError(str(e)) from e
    known = tasks.read(r)
    task = args.task or _newest_task(known)
    if not task:
        raise CageError("no task to attest against — pass --task ID, or close one "
                        "first with `cage task outcome <id>`")
    if not tasks.record(r, task, human_minutes=minutes,
                        human_minutes_method="attested", snapshot=False):
        raise CageError("could not write the task row (ledger not writable?)")
    h, m = divmod(minutes, 60)
    pretty = f"{h}h{m:02d}m" if h else f"{m}m"
    print(f"✔ attested {pretty} of human time on {task!r}.")
    row = known.get(task, {})
    if not row.get("outcome"):
        # Recorded, but say where it will and will not show. The commit views read
        # attested minutes only from CLOSED tasks (the same guard the call join uses),
        # so silently accepting this would look exactly like the write not working.
        print(f"  · {task!r} is still open — the hours appear on `cage insights "
              f"commits` once you close it (`cage task outcome {task}`).")
    elif int(row.get("files_changed", 0) or 0):
        # Its snapshot sha is the PRIOR commit; donating hours to it would put them on
        # the wrong commit, so the view declines. Say so rather than let it vanish.
        print(f"  · {task!r} was closed with uncommitted work, so its recorded commit "
              f"is the\n    one before that work landed — the hours stay on the task, "
              f"not on a commit.")


    return 0


def _newest_task(known: dict) -> str:
    """The most recently recorded task id — the one a person means by "this work".
    Ties break on the id so the choice is stable, never dict order."""
    if not known:
        return ""
    return max(known.items(), key=lambda kv: (kv[1].get("ts", ""), kv[0]))[0]


def cmd_compare(args) -> int:
    r = captured_read_root(args)
    by = tuple(k.strip() for k in (args.by or "stack").split(",") if k.strip())
    bad = [k for k in by if k not in ("stack", "scope", "label")]
    if bad:
        raise CageError(f"unknown --by key(s) {bad}; choose from stack, scope, label")
    d = compare.summarize(r, _policy(r), by=by, scope=args.scope, label=args.label)
    return emit(args, render.envelope("compare", d) if args.json else d,
                compare.render_compare(d), csv=lambda: compare.render_csv(d), root=r)


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
                estimate.render_estimate(d, recorded), root=r)


def cmd_calibration(args) -> int:
    from cage import calibration
    r = captured_read_root(args)
    d = calibration.summarize(r, _policy(r))
    return emit(args, render.envelope("calibration", d) if args.json else d,
                calibration.render_calibration(d),
                csv=lambda: calibration.render_csv(d), root=r)


def cmd_verdict(args) -> int:
    from cage import verdict
    r = captured_read_root(args)
    d = verdict.compose(r, _policy(r), args.tool, since=args.since)
    return emit(args, render.envelope("verdict", d) if args.json else d,
                verdict.render_verdict(d), root=r)


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


def cmd_migrate_savings(args) -> int:
    """`cage data migrate-savings` — consolidate historical graphify receipts into the
    savings tree, precisely (plan §3). Dry-run print by default (house pattern), --apply
    copies; refuses to apply on a reconciliation conflict."""
    from cage import migratecmd
    r = ledger_root()
    payload, text = migratecmd.run_cli(r, do_apply=args.apply)
    return emit(args, render.envelope("migrate-savings", payload) if args.json else payload, text)


def cmd_study(args) -> int:
    """Fleet-study verbs (plan §4.9). Markers/report act on the *active* ledger
    (capture lands there); `join` additionally wires this project's agents."""
    # No runtime refusal for `--csv`/`--export`/`--stamp` on a marker verb any more:
    # CLI-GAPS(b) gave each study action its own parser, and only `report` — the one
    # rendered VIEW here — carries them. A marker verb no longer *has* the flag, so
    # argparse rejects it as a usage error (exit 2) before this function is reached.
    from cage import machine, study
    r = ledger_root()
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
        d = study.summarize(r, _policy(r))
        # Through the ONE chokepoint. The hand-rolled `csv_dest` branch this replaced is
        # why the first `--export` here silently produced no CSV for a view that owns a
        # `render_csv` — an artifact missing a format it HAS is the same lie as an empty
        # file, just quieter.
        return emit(args, render.envelope("study", d) if args.json else d,
                    study.render_study(d), csv=lambda: study.render_csv(d), root=r)
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
    return emit(args, r, regression.render_regression(r), root=lr)


def cmd_recommend(args) -> int:
    lr = captured_read_root(args)
    r = recommend.recommend(lr, _policy(lr), since=args.since)
    return emit(args, r, recommend.render_recommend(r), root=lr)


def cmd_forecast(args) -> int:
    lr = captured_read_root(args)
    f = forecast.project(lr, _policy(lr))
    return emit(args, f, forecast.render_forecast(f), root=lr)


# ── adapters: proxy / meter / mcp / agents (plan §5, §6) ─────────────────────

def cmd_proxy(args) -> int:
    return proxy.serve(root(), port=args.port, upstream=args.upstream)


def cmd_meter(args) -> int:
    return metercmd.run(root(), args.argv, upstream=args.upstream)


def cmd_graphify(args) -> int:
    return graphifymeter.run(root(), args.argv, task=args.task)


def cmd_mcp(_args) -> int:
    return mcpserver.serve()


def _note_config_migration(migrated) -> None:
    """One-line notice when `cage setup` renamed a legacy `policy.toml` → `cage.toml`
    (initcmd does the rename; this just reports it). Silent when nothing moved."""
    if migrated:
        print(f"  ✔ migrated legacy policy.toml → {migrated}")


def _note_prices_migration(migrated) -> None:
    """One-line notice when `cage setup` moved a legacy in-cage.toml price block out to
    `prices.toml` (money-neutral; initcmd does the move). Silent when nothing moved."""
    if migrated:
        print(f"  ✔ moved model prices → {migrated} (routing decisions stay in cage.toml)")


def _hooks(args) -> bool:
    """The `cage setup --hooks` switch (L1, opt-in).

    Default **False** and deliberately so: the hookless floor must be what you get by
    doing nothing, and `agents.install(hooks=False)` also *removes* cage's hook entries,
    so re-running plain `cage setup` is the documented off-switch. `--no-hooks` is
    accepted for symmetry and is what a script uses to assert hooklessness explicitly."""
    if getattr(args, "no_hooks", False):
        return False
    return bool(getattr(args, "hooks", False))


def _skills(args) -> bool:
    """The `cage setup --skills` switch (L3, opt-in).

    Separate from `--hooks` because they are separate layers: a team can want the
    procedural documents without the lifecycle hooks, or the reverse. Both default off
    and both are two-way — a plain `cage setup` removes whichever is present."""
    return bool(getattr(args, "skills", False))


def cmd_setup(args) -> int:
    import sys

    here = root()

    # Handle --global: initialize the machine-wide global ledger (~/.cage) and exit. This
    # is the project-less capture sink (plan §3.7) — `cage import`/`cage data export` from any
    # dir without a project `.cage/` land here.
    if getattr(args, "global_ledger", False):
        info = initcmd.run(paths.global_home(), pointer=False)
        print(f"✔ Global ledger initialised at {info['footprint']}")
        _note_config_migration(info.get("migrated_config"))
        _note_prices_migration(info.get("migrated_prices"))
        print(f"  policy   → {info['policy']}")
        print(f"  prices   → {info['prices']}")
        print(f"  ledger   → {info['ledger']}/  (append-only)")
        print("Capture into it from anywhere: `cage import` · read it: `cage report`.")
        return 0

    # Handle --sync-sources: refresh the cage-managed [sources] block (Directive A) and
    # exit. Materializes the current built-in defaults into project + global cage.toml,
    # preserving any user-added [[sources.<name>]] entries outside the managed markers.
    if getattr(args, "sync_sources", False):
        did = False
        for label, r in (("project", paths.resolve_root()), ("global", paths.global_home())):
            fp = paths.Footprint(r)
            if not fp.policy.exists():
                initcmd.run(r, pointer=(label == "project"))
            changed = initcmd.sync_sources(fp)
            did = did or changed
            print(f"  {'✔ refreshed' if changed else '· already current'}  "
                  f"{label}: {fp.policy}")
        print("Sources synced." if did else "Sources already up to date.")
        return 0

    # Handle --status: report current wiring and exit
    if getattr(args, "status", False):
        from cage import steering
        l1, l3 = steering.by_layer("L1"), steering.by_layer("L3")
        for surface, on in agents.status(here).items():
            wire = agents._WIRE[surface]
            n = wire.hook_status(here)
            doc = sum(1 for d in l1 if steering.paths_for(here, d)[surface].exists())
            skill = sum(1 for d in l3 if steering.paths_for(here, d)[surface].exists())
            extra = []
            if n:
                # The count comes straight from the wired file's contents, so it says
                # only that N hooks are INSTALLED — never that all N do what L1 offers.
                # An unqualified `L1 hooks ×2` beside copilot read as auto-close working
                # when copilot cannot produce a session id at all. Qualified from the ONE
                # capability table, and the specific limit is in the block below.
                limited = " (limited — see L1 limits)" if surface in agents.HOOK_GAPS else ""
                extra.append(f"L1 hooks ×{n}{limited}")
            if doc:
                extra.append(f"steering ×{doc}")
            if skill:
                extra.append(f"L3 skills ×{skill}")
            tail = f"  [{' · '.join(extra)}]" if extra else ""
            print(f"  {'✔' if on else '·'} {surface:<8} "
                  f"{'MCP wired' if on else 'not wired'}{tail}")
        if any(agents._WIRE[s].hook_status(here) for s in agents.SURFACES):
            # A capability one agent lacks is printed, never left to be discovered as
            # "nothing happened" — the three-agent invariant applies to the LIMITS too.
            print("\n  L1 limits:")
            for line in agents.hook_gap_lines():
                print(f"    · {line}")
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
        for surface, where in agents.install(here, flagged, hooks=_hooks(args), skills=_skills(args)).items():
            print(f"  {surface:<8} → {', '.join(where.values())}")
        print("Metering: pull-based — `cage import` (or `cage data meter -- <cmd>` / `cage data proxy`).")
        return 0

    # Handle --project-only: scaffold + graphify + PATH, no MCP wiring
    project_only = getattr(args, "project_only", False)
    if project_only:
        # Override the flags for project-only mode
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
            _note_config_migration(res.get("migrated_config"))
            _note_prices_migration(res.get("migrated_prices"))
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
    # `init` verb's job, now unconditional step one of onboarding. Idempotent.
    _setup_info = initcmd.run(here)
    _note_config_migration(_setup_info.get("migrated_config"))
    _note_prices_migration(_setup_info.get("migrated_prices"))

    # Standard setup: --all or per-agent flags (the interactive wizard was removed
    # with the hook machinery — setup is now three deterministic steps).
    flagged = tuple(s for s in agents.SURFACES if getattr(args, s, False))
    if all_agents:
        flagged = agents.SURFACES
    if not flagged:
        print("Pick an agent: " + " | ".join(agents.SURFACES) + " | all")
        print("e.g. `cage setup --claude` or `cage setup --all`")
        return 2

    for agent in flagged:
        print(f"\n▸ cage setup — {agent}")
        if getattr(args, "project", True):
            res = adoptcmd.run(here, graphify=getattr(args, "graphify", True),
                               surfaces=(agent,), hooks=_hooks(args), skills=_skills(args))
            print(f"  ✔ .cage/ ready → {res['init']}")
            if "shim" in res:
                print(f"  ✔ graphify interceptor → {res['shim']}")
                if res.get("path"):
                    print(f"  ✔ bin/ added to PATH in {res['path']} — open a new shell")
            for surface, where in res.get("hooks", {}).items():
                print(f"  ✔ {surface:<8} → {', '.join(where.values())}")
        else:
            for surface, where in agents.install(here, (agent,), hooks=_hooks(args), skills=_skills(args)).items():
                print(f"  ✔ {surface:<8} → {', '.join(where.values())}")
    print("\nDone. Verify with `cage doctor`; capture with `cage import`; then `cage report`.")
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
    if getattr(args, "wiring", False):
        rep = doctorcmd.wiring_report(root())
        if getattr(args, "json", False):
            import json
            print(json.dumps(rep))
        else:
            print(doctorcmd.render_wiring_text(rep))
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
    """Umbrella hookless import across all three agents (default ``--agent all``) — the
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


def cmd_import_claude(args) -> int:
    """Meter Claude Code with no hooks/MCP — pull the transcripts it already writes
    to disk. Idempotent (append_new dedupes on the per-turn call id), fail-open per
    file (an unreadable transcript is skipped, never raised), $0/offline.

    The policy is threaded in because `--path`/`--project` now take their discovery
    patterns from ``cage.toml``'s ``[sources] path_globs`` (path-globs handoff §5) — with
    no policy this command would resolve zero patterns and scan nothing."""
    r = ledger_root()
    pol = _policy(r)
    n, m = importcmd.import_claude(r, args, pol=pol)
    for line in importcmd.missing_path_globs(args, ("claude",), pol):
        print(line)
    print(f"✔ imported {n} Claude call(s) from {m} transcript(s).")
    return 0


def cmd_export(args) -> int:
    """Import-first (unless ``--no-import``) then emit the active ledger as jsonl/csv/json
    (counts-never-content, deterministic). The universal pull-based export path.
    ``--study`` writes the one-file fleet bundle instead (plan §4.9)."""
    r = ledger_root()
    pol = _policy(r)
    if getattr(args, "study", None) is not None:
        if getattr(args, "csv_kind", None) or getattr(args, "format", None) or getattr(args, "otel", False):
            # Two export kinds, never blurred: the bundle is lossless jsonl by
            # design; CSV/OTel are one-way reporting formats and never an import source.
            raise CageError("--study writes the jsonl fleet bundle — it cannot "
                            "combine with --csv/--format/--otel (`cage query csv-output`)")
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
