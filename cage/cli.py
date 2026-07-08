"""`cage` CLI — argparse dispatch over the deterministic command surface (plan §7)."""
from __future__ import annotations

import argparse

from cage import __version__, clicmds, errors, hooks
from cage.agents import SURFACES
from cage.report import DIMENSIONS


_DESCRIPTION = """\
Cage — a flux: a deterministic attribution ledger for LLM token traffic and tool
savings. $0, stdlib-only, deterministic; the ledger is append-only and every view
is derived (same ledger + same policy ⇒ same numbers). Third in the family after
graphify (code→graph) and fux (decisions→rules)."""

_EPILOG = """\
commands by category:
  ledger        report · budget · why · ledger-sync   spend, per-call provenance, team view (§3.6)
  attribution   attrib · matrix · roi · compare · verdict  per-tool savings (the differentiator)
  human axis    human · human-record · trend     agent-vs-human $ and hours saved
  authorship    origin · notes-sync · verify     who wrote which files (§3.5)
  ops           quality · regression · recommend · forecast · outcome · estimate · calibration
  capture       import · export · watch · limits  universal pull-based metering + quota (§3.7)
  setup         init · doctor · debug · setup · proxy · meter · mcp · serve
  meta          query · demo · graphify (· import-claude · import-codex)

examples:
  cage report --by model --since 7d        # where the spend went, last 7 days
  cage matrix --human                       # what each tool stack would cost vs a person
  cage human-record --task T --type feature # log the human alternative for a task
  cage query "how is human cost calculated" # explain any number with its live formula
  cage setup --claude                       # guided onboarding: scaffold + wire one agent

Global flag: --json on any read command emits structured output (agent-as-user).
Ask how anything works: `cage query "how does cage work"` — and how any value is
computed: `cage query "how is X calculated"` — both deterministic, live numbers."""


def _json_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="machine-readable output (agent-as-user)")


def _html_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument("--html", metavar="PATH", help="write a standalone HTML page (no CDN)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cage", description=_DESCRIPTION, epilog=_EPILOG,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"cage {__version__}")
    p.add_argument("--json", action="store_true", help="machine-readable output (bare cage: the headline dict)")
    p.add_argument("--ledger", metavar="DIR", help="use this cage base dir as the active "
                   "ledger (overrides the project/global resolution; the .cage-equivalent "
                   "holding ledger/, state/ and policy.toml)")
    # required=False: bare `cage` (no subcommand) prints the headline banner via main().
    sub = p.add_subparsers(dest="cmd", required=False, metavar="<command>")

    sub.add_parser("init", help="scaffold .cage/ (policy + gitignored ledger)").set_defaults(fn=clicmds.cmd_init)

    rep = sub.add_parser("report", help="ledger: spend by agent / route / model / day")
    rep.add_argument("--by", choices=DIMENSIONS, default="route", help="group dimension")
    rep.add_argument("--since", metavar="WINDOW", help="window like 7d / 24h / 2w")
    rep.add_argument("--scope", metavar="DIR", help="filter to one monorepo top-level dir (§3.6.2)")
    rep.add_argument("--project", nargs="?", const=".", metavar="NAME",
                     help="filter to one project (working-dir basename; '.' or bare flag = "
                          "current dir). Exact for Claude only (§3.7)")
    rep.add_argument("--team", action="store_true", help="read the merged refs/notes/cage-ledger team view (§3.6.3)")
    _json_flag(rep)
    rep.set_defaults(fn=clicmds.cmd_report)

    at = sub.add_parser("attrib", help="per-tool marginal savings for a task (§4.2)")
    at.add_argument("--task", help="task id (default: most recent)")
    at.add_argument("--scope", metavar="DIR", help="filter to one monorepo top-level dir (§3.6.2)")
    at.add_argument("--team", action="store_true", help="read the merged refs/notes/cage-ledger team view (§3.6.3)")
    _json_flag(at)
    at.set_defaults(fn=clicmds.cmd_attrib)

    mx = sub.add_parser("matrix", help="counterfactual permutation table for a task (§4.4)",
                        epilog="example:\n  cage matrix --human   # add a human-baseline row + vs-human columns",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    mx.add_argument("--task", help="task id (default: most recent)")
    mx.add_argument("--scope", metavar="DIR", help="filter to one monorepo top-level dir (§3.6.2)")
    mx.add_argument("--human", action="store_true", help="add the Tier-1 human anchor row + vs-human columns")
    _json_flag(mx)
    _html_flag(mx)
    mx.set_defaults(fn=clicmds.cmd_matrix)

    bd = sub.add_parser("budget", help="session/day spend vs policy ceilings (§8.1)")
    bd.add_argument("--session", help="session id to total against the session cap")
    bd.add_argument("--scope", metavar="DIR", help="filter to one monorepo top-level dir (§3.6.2)")
    _json_flag(bd)
    bd.set_defaults(fn=clicmds.cmd_budget)

    lm = sub.add_parser("limits", help="provider quota windows + estimated AI-credit use")
    _json_flag(lm)
    lm.set_defaults(fn=clicmds.cmd_limits)

    ro = sub.add_parser("roi", help="saved $ per tool vs its own cost + latency")
    ro.add_argument("--since", metavar="WINDOW", help="window like 30d / 2w")
    _json_flag(ro)
    ro.set_defaults(fn=clicmds.cmd_roi)

    cp = sub.add_parser("compare",
                        help="measured comparison of closed tasks grouped by stack "
                             "(n · median · IQR; the delta is estimated, observational)")
    cp.add_argument("--scope", metavar="DIR", help="filter to one monorepo top-level dir")
    cp.add_argument("--label", metavar="WORD", help="filter to tasks labelled via `cage outcome --label`")
    cp.add_argument("--by", default="stack", metavar="KEYS",
                    help="comma-separated grouping keys from stack,scope,label (stack always included)")
    _json_flag(cp)
    cp.set_defaults(fn=clicmds.cmd_compare)

    es = sub.add_parser("estimate",
                        help="pre-task cost band (median + IQR) from matching closed "
                             "tasks — modeled, refuses thin history")
    es.add_argument("--scope", metavar="DIR", help="match tasks in one monorepo top-level dir")
    es.add_argument("--label", metavar="WORD", help="match tasks labelled via `cage outcome --label`")
    es.add_argument("--agent", metavar="NAME", help="match tasks a given agent worked")
    es.add_argument("--record", metavar="TASK",
                    help="stamp the band onto this OPEN task row (est_tokens/est_usd/est_n "
                         "+ band bounds) so `cage calibration` can score it at close")
    _json_flag(es)
    es.set_defaults(fn=clicmds.cmd_estimate)

    cb = sub.add_parser("calibration",
                        help="measured hit-rate of recorded estimates vs actuals — the "
                             "estimator's empirical confidence level")
    _json_flag(cb)
    cb.set_defaults(fn=clicmds.cmd_calibration)

    vd = sub.add_parser("verdict",
                        help="one-line answer: is this tool saving or costing? "
                             "(pure composer over attrib/roi/trend/regression/quality)")
    vd.add_argument("tool", help="tool name as it appears on receipts (e.g. graphify)")
    vd.add_argument("--since", metavar="WINDOW", help="window like 30d / 2w (default: all history)")
    _json_flag(vd)
    vd.set_defaults(fn=clicmds.cmd_verdict)

    st2 = sub.add_parser("study",
                         help="fleet study: recorded phases + paired-by-machine deltas "
                              "across laptops (plan §4.9)",
                         epilog="examples:\n"
                                "  cage study join baseline      # enroll this machine: wire + start + doctor\n"
                                "  cage study start plugin       # switch phase (opaque machine id, no hostname)\n"
                                "  cage study stop               # end the current phase\n"
                                "  cage export --study           # one bundle for the analyst\n"
                                "  cage import bundle*.zip       # analyst: merge bundles (idempotent)\n"
                                "  cage study report             # coverage first, then the paired delta",
                         formatter_class=argparse.RawDescriptionHelpFormatter)
    st2.add_argument("action", choices=["join", "start", "stop", "report", "id"],
                     help="join=enroll+wire+start · start/stop=phase markers · "
                          "report=coverage+paired delta · id=print the opaque machine id")
    st2.add_argument("phase", nargs="?", help="phase label for join/start (one short token)")
    _json_flag(st2)
    st2.set_defaults(fn=clicmds.cmd_study)

    hu = sub.add_parser("human", help="agent-vs-human savings: $ and hours saved (§4.1)")
    hu.add_argument("--since", metavar="WINDOW", help="window like 30d / 2w")
    hu.add_argument("--task", help="single task id")
    hu.add_argument("--agent", help="filter to one agent")
    _json_flag(hu)
    _html_flag(hu)
    hu.set_defaults(fn=clicmds.cmd_human)

    hr = sub.add_parser("human-record", help="record a Tier-1 human alternative for a task (§5)",
                        epilog="examples:\n"
                               "  cage human-record --task T --type feature   # price by task-type table\n"
                               "  cage human-record --task T --minutes 90      # or by explicit minutes\n"
                               "  cage human-record --task T --usd 150 --measured  # a real quote",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    hr.add_argument("--task", required=True)
    hr.add_argument("--type", dest="task_type", help="task type (feature/bugfix/refactor/research/review)")
    hr.add_argument("--minutes", type=float, help="human-minutes the task would have taken")
    hr.add_argument("--usd", type=float, help="a directly-quoted dollar alternative")
    hr.add_argument("--rate", type=float, help="override $/hr for this receipt")
    hr.add_argument("--call", default="", help="the agent call this is the alternative to")
    hr.add_argument("--agent", default="", help="attribute the saving to this agent")
    hr.add_argument("--measured", action="store_true", help="a real timesheet/quote (not an estimate)")
    hr.set_defaults(fn=clicmds.cmd_human_record)

    tr = sub.add_parser("trend", help="cost+time savings over time, by week or month (§5b.4)")
    tr.add_argument("--by", choices=["week", "month"], default="week")
    tr.add_argument("--metric", choices=["cost", "time", "both"], default="both")
    tr.add_argument("--since", metavar="WINDOW")
    _json_flag(tr)
    _html_flag(tr)
    tr.set_defaults(fn=clicmds.cmd_trend)

    wy = sub.add_parser("why", help="full provenance: a call + every receipt against it")
    wy.add_argument("call_id")
    _json_flag(wy)
    wy.set_defaults(fn=clicmds.cmd_why)

    sv = sub.add_parser("serve", help="local dashboard over the ledger ($0)")
    sv.add_argument("--port", type=int, default=8788)
    sv.set_defaults(fn=clicmds.cmd_serve)

    sub.add_parser("demo", help="seed the plan's §4.4 worked example to prove the thesis").set_defaults(fn=clicmds.cmd_demo)

    qy = sub.add_parser("query", help="explain how a value is calculated, or how cage itself works ($0, deterministic)",
                        epilog="examples:\n"
                               "  cage query \"how does cage work\"      # concept: the front door\n"
                               "  cage query \"how is human cost calculated\"\n"
                               "  cage query cost                      # exact topic id\n"
                               "  cage query --list --kind concept     # just the how-it-works topics\n"
                               "  cage query roi --json                # structured, for an agent",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    qy.add_argument("question", nargs="?", default="", help="a question or an exact topic id")
    qy.add_argument("--list", action="store_true", help="list every explainer topic")
    qy.add_argument("--kind", choices=["calculation", "concept"], help="filter --list to one kind")
    qy.add_argument("--all", action="store_true", help="show the top matches, not just the best")
    _json_flag(qy)
    qy.set_defaults(fn=clicmds.cmd_query)

    # ── §8 ledger features ───────────────────────────────────────────────────
    ql = sub.add_parser("quality", help="quality-adjusted cost: cost per successful task (§8.2)")
    _json_flag(ql)
    ql.set_defaults(fn=clicmds.cmd_quality)

    oc = sub.add_parser("outcome", help="record a task's outcome (ok / redo) for quality cost")
    oc.add_argument("task")
    oc.add_argument("--redo", action="store_true", help="mark the task as needing a human redo")
    oc.add_argument("--label", metavar="WORD",
                    help="tag the task with one short token (letters/digits/._-, ≤32 chars) "
                         "for `cage compare --by label` grouping — never a path or free text")
    oc.set_defaults(fn=clicmds.cmd_outcome)

    rg = sub.add_parser("regression", help="alert when cost-per-call drifts up (§8.3)")
    rg.add_argument("--since", default="7d", metavar="WINDOW", help="recent window vs the baseline before it")
    rg.add_argument("--tolerance", type=float, default=0.2, help="drift fraction that trips the flag")
    _json_flag(rg)
    rg.set_defaults(fn=clicmds.cmd_regression)

    rc = sub.add_parser("recommend", help="cheapest-path: which tools to enable/skip (§8.4)")
    rc.add_argument("--since", metavar="WINDOW")
    _json_flag(rc)
    rc.set_defaults(fn=clicmds.cmd_recommend)

    fc = sub.add_parser("forecast", help="project monthly spend vs the budget (§8.5)")
    _json_flag(fc)
    fc.set_defaults(fn=clicmds.cmd_forecast)

    # ── adapters: proxy / meter / mcp + agent wiring (plan §5, §6) ────────────
    px = sub.add_parser("proxy", help="metering reverse-proxy for clients you can't edit")
    px.add_argument("--port", type=int, default=8788)
    px.add_argument("--upstream", default="https://api.anthropic.com", help="real API base URL")
    px.set_defaults(fn=clicmds.cmd_proxy)

    mt = sub.add_parser("meter", help="run a command under the metering proxy: cage meter -- <cmd>")
    mt.add_argument("--upstream", default="https://api.anthropic.com")
    mt.add_argument("argv", nargs=argparse.REMAINDER, help="-- <command> [args…]")
    mt.set_defaults(fn=clicmds.cmd_meter)

    gf = sub.add_parser("graphify", help="meter a third-party graphify call without touching it",
                        epilog="example:\n  cage graphify -- graphify query \"auth flow\"   # runs graphify, files one savings receipt",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    gf.add_argument("--task", default="", help="task id to bind the saving to (default: project dir name)")
    gf.add_argument("argv", nargs=argparse.REMAINDER, help="-- graphify <query|path|explain> …")
    gf.set_defaults(fn=clicmds.cmd_graphify)

    sub.add_parser("mcp", help="serve the ledger over MCP (stdio JSON-RPC) for any agent").set_defaults(fn=clicmds.cmd_mcp)
    st = sub.add_parser("setup", help="guided onboarding wizard: skill + init + per-project wiring + graphify for one agent (interactive, or drive it with --<agent>)",
                        epilog="examples:\n"
                               "  cage setup                      # interactive: pick an agent, y/n each step\n"
                               "  cage setup --claude             # non-interactive: all steps for claude\n"
                               "  cage setup --project-only --claude  # scaffold + graphify only, no global skill\n"
                               "  cage setup --wire-only --claude     # agent wiring only, no scaffold\n"
                               "  cage setup --status             # show which agents are wired",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    for _s in SURFACES:
        st.add_argument(f"--{_s}", action="store_true", help=f"set up the {_s} agent non-interactively (skips the wizard)")
    st.add_argument("--all", dest="all_agents", action="store_true", help="set up all four agents non-interactively (capture works for any of them)")
    st.add_argument("--project-only", action="store_true", help="scaffold .cage/ + graphify + PATH only; skip the global skill")
    st.add_argument("--wire-only", action="store_true", help="wire agent(s) only; skip scaffold and graphify")
    st.add_argument("--status", action="store_true", help="report which agents are wired (no changes)")
    st.add_argument("--global", dest="global_ledger", action="store_true",
                    help="initialize the global ledger (~/.cage) for project-less capture, then exit")
    st.add_argument("--no-skill", dest="skill", action="store_false", help="skip installing the /cage skill")
    st.add_argument("--repo-skill", dest="repo_skill", action="store_true", help="install the /cage skill into this repo (committed, team-shared) instead of the machine-wide home")
    st.add_argument("--no-project", dest="project", action="store_false", help="skip per-project .cage/ scaffold + hook wiring")
    st.add_argument("--no-graphify", dest="graphify", action="store_false", help="skip the graphify interceptor")
    st.set_defaults(fn=clicmds.cmd_setup)

    dr = sub.add_parser("doctor", help="verify this project's Cage setup is correct and working")
    dr.add_argument("--json", action="store_true", help="machine-readable output")
    dr.add_argument("--bundle", nargs="?", const="cage-doctor-bundle.zip", metavar="PATH",
                    help="also write one redacted diagnostics archive (counts-never-content): "
                         "doctor output, path probe, debug log + heartbeats, version/platform, "
                         "footprint paths + row counts, policy provenance, cursor state")
    dr.add_argument("--paths", action="store_true",
                    help="read-only path probe: every candidate log location per agent on "
                         "this OS — found/missing, files matched, parseable rows, cursor "
                         "state, and why a location missed (writes nothing)")
    dr.set_defaults(fn=clicmds.cmd_doctor)

    dbg = sub.add_parser("debug", help="print recent capture-path debug events ($0, metadata-only; needs CAGE_DEBUG=1)")
    dbg.add_argument("--tail", type=int, default=20, metavar="N", help="show the last N events (default: 20)")
    dbg.add_argument("--json", action="store_true", help="one JSON event per line")
    dbg.set_defaults(fn=clicmds.cmd_debug)

    im = sub.add_parser("import", help="capture every agent's on-disk usage into the active ledger (the universal path)",
                        epilog="examples:\n"
                               "  cage import                              # every agent (default --agent all)\n"
                               "  cage import --agent claude --project .    # only this repo's Claude sessions\n"
                               "  cage import --agent codex --since 7d      # Codex rollouts touched in 7d\n"
                               "  cage --ledger ~/.cage import              # capture into a specific ledger\n"
                               "Captures into the resolved ledger (--ledger/CAGE_BASE → project .cage/ → global ~/.cage);\n"
                               "works with no hooks and no project. Idempotent + incremental (per-agent cursor).",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    im.add_argument("bundles", nargs="*", metavar="BUNDLE",
                    help="study bundle zip(s) from `cage export --study` — merged by row "
                         "identity, idempotent (fleet path, plan §4.9)")
    im.add_argument("--agent", choices=[*SURFACES, "all"], default="all",
                    help="which agent to meter (default: all)")
    im.add_argument("--path", help="a transcript file or dir to scan (log-bearing agents only)")
    im.add_argument("--project", help="restrict to one repo's sessions (Claude only)")
    im.add_argument("--since", metavar="WINDOW", help="only transcripts modified within a window like 7d / 24h / 2w")
    im.set_defaults(fn=clicmds.cmd_import)

    ex = sub.add_parser("export", help="import (refresh) then emit the ledger as jsonl/csv/json",
                        epilog="examples:\n"
                               "  cage export                              # refresh, then raw jsonl to stdout\n"
                               "  cage export --format csv -o spend.csv     # flat csv for a spreadsheet\n"
                               "  cage export --format json --since 30d     # structured summary (matches `cage report`)\n"
                               "  cage export --no-import --format jsonl    # emit the ledger as-is, no refresh\n"
                               "  cage export --project . --agent claude    # one project's Claude rows",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    ex.add_argument("--format", choices=["jsonl", "csv", "json"], default="jsonl",
                    help="jsonl=raw rows (re-ingestable) · csv=flat · json=summary (default: jsonl)")
    ex.add_argument("--json", action="store_const", dest="format", const="json",
                    help="alias for --format json (the structured summary)")
    ex.add_argument("--since", metavar="WINDOW", help="window like 7d / 24h / 2w")
    ex.add_argument("--project", nargs="?", const=".", metavar="NAME",
                    help="filter to one project (basename; '.' = current dir). Claude-exact (§3.7)")
    ex.add_argument("--agent", choices=[*SURFACES], help="filter to one agent")
    ex.add_argument("--no-import", dest="do_import", action="store_false",
                    help="skip the import-first refresh; emit the ledger exactly as-is")
    ex.add_argument("-o", "--output", metavar="FILE", help="write to FILE (default: stdout)")
    ex.add_argument("--study", nargs="?", const="", metavar="PATH", dest="study",
                    help="write one fleet-study bundle instead (rows + phase markers + "
                         "counts-only manifest; default name cage-study-<machine>.zip)")
    ex.set_defaults(fn=clicmds.cmd_export)

    wt = sub.add_parser("watch", help="foreground poll loop: import every interval until Ctrl-C (no OS job)",
                        epilog="example:\n"
                               "  cage watch                  # import all agents every 60s\n"
                               "  cage watch --interval 300   # every 5 minutes\n"
                               "Registers nothing and stops with the terminal — cage installs no scheduler.",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    wt.add_argument("--agent", choices=[*SURFACES, "all"], default="all", help="which agent to meter (default: all)")
    wt.add_argument("--interval", type=int, default=60, metavar="SECONDS", help="seconds between imports (default: 60)")
    wt.add_argument("--since", metavar="WINDOW", help="only transcripts modified within a window like 7d / 24h / 2w")
    wt.set_defaults(fn=clicmds.cmd_watch)

    ic = sub.add_parser("import-codex", help="best-effort meter a Codex rollout JSONL (file or dir)")
    ic.add_argument("path", help="a rollout-*.jsonl file or ~/.codex/sessions dir")
    ic.set_defaults(fn=clicmds.cmd_import_codex)

    icl = sub.add_parser("import-claude", help="meter Claude Code from its on-disk transcripts (no hooks/MCP needed)",
                         epilog="examples:\n"
                                "  cage import-claude                       # every project on this machine\n"
                                "  cage import-claude --project .           # only this repo's sessions\n"
                                "  cage import-claude --path run.jsonl      # one transcript\n"
                                "  cage import-claude --since 7d            # only transcripts touched in 7d",
                         formatter_class=argparse.RawDescriptionHelpFormatter)
    icl.add_argument("--path", help="a transcript .jsonl file or dir to scan (default: ~/.claude/projects)")
    icl.add_argument("--project", help="restrict to one repo's sessions (resolves its ~/.claude/projects slug)")
    icl.add_argument("--since", metavar="WINDOW", help="only transcripts modified within a window like 7d / 24h / 2w")
    icl.set_defaults(fn=clicmds.cmd_import_claude)

    ns = sub.add_parser("notes-sync", help="merge buffered provenance into refs/notes/cage-provenance (§3.5)",
                        epilog="example:\n"
                               "  cage notes-sync                 # dry-run: print the merge plan\n"
                               "  CAGE_NOTES_WRITE=1 cage notes-sync  # actually push the notes (CI only)",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    ns.add_argument("--write", action="store_true", help="push to refs/notes (default: dry-run unless CAGE_NOTES_WRITE=1)")
    _json_flag(ns)
    ns.set_defaults(fn=clicmds.cmd_notes_sync)

    ls = sub.add_parser("ledger-sync", help="merge local call/receipt rows into refs/notes/cage-ledger for a team view (§3.6.3)",
                        epilog="example:\n"
                               "  cage ledger-sync                # dry-run: print the merge plan\n"
                               "  CAGE_NOTES_WRITE=1 cage ledger-sync  # actually push the team ledger (CI only)\n"
                               "  cage report --team              # read the merged team view",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    ls.add_argument("--write", action="store_true", help="push to refs/notes (default: dry-run unless CAGE_NOTES_WRITE=1)")
    _json_flag(ls)
    ls.set_defaults(fn=clicmds.cmd_ledger_sync)

    og = sub.add_parser("origin", help="authorship attribution for a commit (§3.5)",
                        epilog="examples:\n"
                               "  cage origin HEAD                       # who wrote this commit\n"
                               "  cage origin a1b2c3d --attest human     # human triage: assert origin\n"
                               "  cage origin a1b2c3d --attest agent --agent claude-code",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    og.add_argument("sha")
    og.add_argument("--attest", choices=["human", "agent", "agent-autonomous"], help="record a human-triage attestation for this sha")
    og.add_argument("--agent", default="", help="agent name to attach to --attest")
    _json_flag(og)
    og.set_defaults(fn=clicmds.cmd_origin)

    sub.add_parser("verify", help="report-only consistency check over the provenance ledger (never fails the build)").set_defaults(fn=clicmds.cmd_verify)

    # Internal hook entrypoints (wired by `cage setup --wire-only`, not for direct use).
    sub.add_parser("hook-session-start").set_defaults(fn=lambda a: hooks.session_start())
    sub.add_parser("hook-stop").set_defaults(fn=lambda a: hooks.stop())
    sub.add_parser("hook-session-end").set_defaults(fn=lambda a: hooks.session_end())
    sub.add_parser("hook-post-tool-use").set_defaults(fn=lambda a: hooks.post_tool_use())
    sub.add_parser("hook-post-commit").set_defaults(fn=lambda a: hooks.post_commit())
    pcm = sub.add_parser("hook-prepare-commit-msg")
    pcm.add_argument("msg_path")
    pcm.set_defaults(fn=lambda a: hooks.prepare_commit_msg(a.msg_path))
    return p


def main(argv: list[str] | None = None) -> int:
    import os
    import sys

    # A non-UTF console (Windows cp1252) would raise UnicodeEncodeError on the first
    # ✔/·/⚠ glyph and kill the command. Degrade the glyph, never the command — the
    # tables and numbers are ASCII; only decorations are at stake. Fail-open.
    for stream in (sys.stdout, sys.stderr):
        try:
            if "utf" not in (getattr(stream, "encoding", "") or "").lower():
                stream.reconfigure(errors="replace")
        except Exception:  # noqa: BLE001 — cosmetic only, never block the CLI
            pass

    # argparse renders its own usage error + exits 2 here, before the try (stdlib).
    args = build_parser().parse_args(argv)
    if getattr(args, "ledger", None):  # --ledger re-bases every Footprint to one sink (§3.7)
        os.environ["CAGE_BASE"] = str(args.ledger)
    try:
        # A malformed --since used to be *silently ignored* (an unfiltered table that
        # claims a window is a wrong number). One CLI-boundary check; capture hooks
        # call importcmd directly and stay fail-open (full-test-plan finding #2).
        from cage import ledger as _ledger
        since = getattr(args, "since", None)
        if since and not _ledger.valid_since(since):
            raise errors.CageError(
                f"invalid --since {since!r} — use a window like 7d, 24h, or 2w")
        if getattr(args, "fn", None) is None:  # no subcommand → the bare-`cage` headline (§4)
            return clicmds.cmd_overview(args)
        return args.fn(args)
    except KeyboardInterrupt:  # Ctrl-C (e.g. aborting the `cage setup` wizard) — exit clean, no traceback
        print("\naborted.")
        return 130
    except errors.CageError as e:  # an expected, user-facing failure → clean line, no traceback
        print(f"error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 — last-resort boundary: terse error; full traceback only under CAGE_DEBUG
        print(f"error: {e}", file=sys.stderr)
        if errors.debug_enabled():
            import traceback
            traceback.print_exc()
        return 1
