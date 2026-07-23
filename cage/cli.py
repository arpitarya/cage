"""`cage` CLI — argparse dispatch over the deterministic command surface (plan §7).

Phase 3 (CLI tiering): the front door is five daily verbs + six groups. Moved verbs
keep their exact flags and run functions — they dispatch from a group subparser
instead of the top level, so behavior is frozen. Old top-level names are removed and
answer with a one-line direction (`cage.verbmap`); `mcp`/`debug`/`demo` and the
`hook-*` plumbing stay callable but hidden from `cage --help`.
"""
from __future__ import annotations

import argparse

from cage import __version__, clicmds, errors, hooks, verbmap
from cage.agents import SURFACES
from cage.report import DIMENSIONS


# The verbatim front-door help (plan Phase 3 mock). `_RootParser.format_help` returns
# this exactly — no usage/options noise; the daily loop and the groups, one screen.
# Golden-pinned by tests/test_output_spec.py; any edit updates docs/cli-output-spec.md.
_ROOT_HELP = """\
cage — measure what your AI agents spend, prove what your tools save

daily:
  report      where the spend went (tokens; add $ views via [display])
  import      pull every agent's usage into the ledger
  setup       make this project (or --global) metered — scaffold + wire
  doctor      is capture healthy? (--paths shows every probed location)
  query       ask cage how any number or mechanism works

groups (run any group name for its commands):
  insights    attrib · matrix · roi · verdict · budget · compare · estimate ·
              calibration · trend · why · forecast · regression · recommend
  human       show · record · outcome · quality
  authorship  origin · verify · notes-sync · ledger-sync
  prices      list · unpriced · set · alias · route-tool · sync
  study       join · start · stop · report · id
  policy      diff · sync
  data        export · cleanup · limits · watch · serve · proxy · meter

$ cage report --since 7d          # the daily number
$ cage insights verdict graphify  # is this tool paying for itself?
$ cage human record 12m           # attest human time on the open task
$ cage study join baseline        # enroll this laptop in the fleet study
$ cage prices route-tool graphify --to copilot/claude-sonnet-4.6
"""


class _RootParser(argparse.ArgumentParser):
    """Top parser only: `cage --help` renders the curated front door verbatim
    (`_ROOT_HELP`), not argparse's auto usage/subcommand dump. Subparsers use the
    stock class (via `parser_class=` below), so `cage report --help` etc. are normal."""

    def format_help(self) -> str:  # noqa: D401 — argparse hook
        return _ROOT_HELP


def _json_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="machine-readable output (agent-as-user)")


def _html_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument("--html", metavar="PATH", help="write a standalone HTML page (no CDN)")


def _csv_flag(p: argparse.ArgumentParser) -> None:
    # nargs="?": bare `--csv` streams to stdout (pipe-friendly); `--csv PATH` writes
    # a file. CSV is a one-way REPORTING format for spreadsheets — same numbers as
    # the text view by construction; never an import source (`cage query csv-output`).
    p.add_argument("--csv", nargs="?", const="-", metavar="PATH",
                   help="emit this view as CSV (stdout, or to PATH); method tags "
                        "stay columns — see `cage query csv-output`")


def _capture_flags(p: argparse.ArgumentParser) -> None:
    """Capture-on-read controls shared by every read surface (capture-architecture
    Phase 1). ``--no-import`` skips the lazy pre-read sweep for this invocation (env
    ``CAGE_CAPTURE=0`` / ``CAGE_CAPTURE_ON_READ=0`` do the same standing); ``--quiet``
    (env ``CAGE_QUIET``) silences the ``· captured …`` confirmation without changing any
    number; ``--why-ledger`` prints the ledger-resolution decision (which sink + why +
    route-key) to stderr on demand."""
    p.add_argument("--no-import", dest="no_import", action="store_true",
                   help="skip the capture-on-read pre-sweep for this read")
    p.add_argument("--quiet", action="store_true",
                   help="silence capture confirmations (or set CAGE_QUIET=1)")
    p.add_argument("--why-ledger", dest="why_ledger", action="store_true",
                   help="print which ledger resolved and why (to stderr)")


def _group(sub, name: str, help_text: str):
    """A command group (insights/human/authorship/data) — a subparser holding nested
    subparsers that dispatch to the same run functions. Bare `cage <group>` prints the
    group's help (its command list); a chosen subcommand's own `fn` default wins."""
    g = sub.add_parser(name, help=help_text)
    g.set_defaults(fn=lambda _a, _g=g: (_g.print_help(), 0)[1])
    return g.add_subparsers(dest=f"{name}_cmd", metavar="<command>", required=False)


def build_parser() -> argparse.ArgumentParser:
    p = _RootParser(prog="cage", add_help=True,
                    formatter_class=argparse.RawDescriptionHelpFormatter)
    from cage import paths as _paths
    _dist = " (zipapp)" if _paths.distribution() == "zipapp" else ""
    p.add_argument("--version", action="version", version=f"cage {__version__}{_dist}")
    p.add_argument("--json", action="store_true", help="machine-readable output (bare cage: the headline dict)")
    p.add_argument("--usd", action="store_true",
                   help="bare cage: add dollar figures to the headline (tokens are "
                        "the default; `[display] usd = true` for always-on)")
    p.add_argument("--ledger", metavar="DIR", help="use this cage base dir as the active "
                   "ledger (overrides the project/global resolution; the .cage-equivalent "
                   "holding ledger/, state/ and policy.toml)")
    _capture_flags(p)  # bare `cage` (overview) is a read too — capture-on-read applies
    # required=False: bare `cage` (no subcommand) prints the headline banner via main().
    # parser_class: children are stock ArgumentParsers, so only the root overrides help.
    sub = p.add_subparsers(dest="cmd", required=False, metavar="<command>",
                           parser_class=argparse.ArgumentParser)

    # ── tier 1: the daily front door ──────────────────────────────────────────
    rep = sub.add_parser("report", help="ledger: spend by agent / route / model / day")
    rep.add_argument("--by", choices=DIMENSIONS, default="route", help="group dimension")
    rep.add_argument("--since", metavar="WINDOW", help="window like 7d / 24h / 2w")
    rep.add_argument("--scope", metavar="DIR", help="filter to one monorepo top-level dir (§3.6.2)")
    rep.add_argument("--project", nargs="?", const=".", metavar="NAME",
                     help="filter to one project (working-dir basename; '.' or bare flag = "
                          "current dir). Exact for Claude only (§3.7)")
    rep.add_argument("--team", action="store_true", help="read the merged refs/notes/cage-ledger team view (§3.6.3)")
    rep.add_argument("--usd", action="store_true",
                     help="add dollar columns (tokens are the default view; "
                          "`[display] usd = true` in policy for always-on)")
    rep.add_argument("--all-columns", action="store_true", dest="all_columns",
                     help="force the full column grid even without savings signal "
                          "(scripts wanting fixed shape; CSV never gates)")
    _json_flag(rep)
    _csv_flag(rep)
    _capture_flags(rep)
    rep.set_defaults(fn=clicmds.cmd_report)

    im = sub.add_parser("import", help="capture every agent's on-disk usage into the active ledger (the universal path)",
                        epilog="examples:\n"
                               "  cage import                              # every agent (default --agent all)\n"
                               "  cage import --agent claude --project .    # only this repo's Claude sessions\n"
                               "  cage import --agent copilot --since 7d    # Copilot events touched in 7d\n"
                               "  cage --ledger ~/.cage import              # capture into a specific ledger\n"
                               "Captures into the resolved ledger (--ledger/CAGE_BASE → project .cage/ → global ~/.cage);\n"
                               "works with no hooks and no project. Idempotent + incremental (per-agent cursor).",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    im.add_argument("bundles", nargs="*", metavar="BUNDLE",
                    help="study bundle zip(s) from `cage data export --study` — merged by row "
                         "identity, idempotent (fleet path, plan §4.9)")
    im.add_argument("--agent", choices=[*SURFACES, "all"], default="all",
                    help="which agent to meter (default: all)")
    im.add_argument("--path", help="a transcript file or dir to scan (log-bearing agents only)")
    im.add_argument("--project", help="restrict to one repo's sessions (Claude only)")
    im.add_argument("--since", metavar="WINDOW", help="only transcripts modified within a window like 7d / 24h / 2w")
    im.set_defaults(fn=clicmds.cmd_import)

    st = sub.add_parser("setup", help="make this project (or --global) metered: scaffold .cage/ + skill + per-project wiring + graphify (interactive, or drive it with --<agent>)",
                        epilog="examples:\n"
                               "  cage setup                      # interactive: scaffold, then pick an agent, y/n each step\n"
                               "  cage setup --claude             # non-interactive: all steps for claude\n"
                               "  cage setup --project-only --claude  # scaffold + graphify only, no global skill\n"
                               "  cage setup --wire-only --claude     # agent wiring only, no scaffold\n"
                               "  cage setup --status             # show which agents are wired\n"
                               "  cage setup --python-launcher --all  # no-exe wiring for locked-down endpoints",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    for _s in SURFACES:
        st.add_argument(f"--{_s}", action="store_true", help=f"set up the {_s} agent non-interactively (skips the wizard)")
    st.add_argument("--all", dest="all_agents", action="store_true", help="set up all three agents non-interactively (capture works for any of them)")
    st.add_argument("--project-only", action="store_true", help="scaffold .cage/ + graphify + PATH only; skip the global skill")
    st.add_argument("--wire-only", action="store_true", help="wire agent(s) only; skip scaffold and graphify")
    st.add_argument("--status", action="store_true", help="report which agents are wired (no changes)")
    st.add_argument("--global", dest="global_ledger", action="store_true",
                    help="initialize the global ledger (~/.cage) for project-less capture, then exit")
    st.add_argument("--no-skill", dest="skill", action="store_false", help="skip installing the /cage skill")
    st.add_argument("--repo-skill", dest="repo_skill", action="store_true", help="install the /cage skill into this repo (committed, team-shared) instead of the machine-wide home")
    st.add_argument("--no-project", dest="project", action="store_false", help="skip per-project .cage/ scaffold + hook wiring")
    st.add_argument("--no-graphify", dest="graphify", action="store_false", help="skip the graphify interceptor")
    st.add_argument("--python-launcher", action="store_true",
                    help="persist [wiring] python_launcher=true and wire everything "
                         "via `python3 -m cage` / `py -3 -m cage` — no exe probed or "
                         "executed (restricted endpoints; `cage query restricted-env`)")
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

    # ── group: insights (attribution + money views, the differentiator) ────────
    insights = _group(sub, "insights",
                       "per-tool savings & money views: attrib · matrix · roi · "
                       "verdict · budget · compare · estimate · calibration · trend · "
                       "why · forecast · regression · recommend")

    at = insights.add_parser("attrib", help="per-tool marginal savings for a task (§4.2)")
    at.add_argument("--task", help="task id (default: most recent)")
    at.add_argument("--scope", metavar="DIR", help="filter to one monorepo top-level dir (§3.6.2)")
    at.add_argument("--team", action="store_true", help="read the merged refs/notes/cage-ledger team view (§3.6.3)")
    _json_flag(at)
    _csv_flag(at)
    _capture_flags(at)
    at.set_defaults(fn=clicmds.cmd_attrib)

    mx = insights.add_parser("matrix", help="counterfactual permutation table for a task (§4.4)",
                             epilog="example:\n  cage insights matrix --human   # add a human-baseline row + vs-human columns",
                             formatter_class=argparse.RawDescriptionHelpFormatter)
    mx.add_argument("--task", help="task id (default: most recent)")
    mx.add_argument("--scope", metavar="DIR", help="filter to one monorepo top-level dir (§3.6.2)")
    mx.add_argument("--human", action="store_true",
                    help="add the Tier-1 human anchor row + vs-human columns "
                         "(a $ view — implies --usd)")
    mx.add_argument("--usd", action="store_true",
                    help="add the cost column (the token grid is the default and "
                         "always renders; `[display] usd = true` for always-on)")
    _json_flag(mx)
    _html_flag(mx)
    _capture_flags(mx)
    mx.set_defaults(fn=clicmds.cmd_matrix)

    ro = insights.add_parser("roi", help="saved $ per tool vs its own cost + latency")
    ro.add_argument("--since", metavar="WINDOW", help="window like 30d / 2w")
    _json_flag(ro)
    _csv_flag(ro)
    _capture_flags(ro)
    ro.set_defaults(fn=clicmds.cmd_roi)

    vd = insights.add_parser("verdict",
                             help="one-line answer: is this tool saving or costing? "
                                  "(pure composer over attrib/roi/trend/regression/quality)")
    vd.add_argument("tool", help="tool name as it appears on receipts (e.g. graphify)")
    vd.add_argument("--since", metavar="WINDOW", help="window like 30d / 2w (default: all history)")
    vd.add_argument("--agent-only", action="store_true",
                    help="suppress the total-cost line (agent $ + human attention minutes × rate)")
    _json_flag(vd)
    _capture_flags(vd)
    vd.set_defaults(fn=clicmds.cmd_verdict)

    bd = insights.add_parser("budget", help="session/day spend vs policy ceilings (§8.1)")
    bd.add_argument("--session", help="session id to total against the session cap")
    bd.add_argument("--scope", metavar="DIR", help="filter to one monorepo top-level dir (§3.6.2)")
    _json_flag(bd)
    _capture_flags(bd)
    bd.set_defaults(fn=clicmds.cmd_budget)

    cp = insights.add_parser("compare",
                             help="measured comparison of closed tasks grouped by stack "
                                  "(n · median · IQR; the delta is estimated, observational)")
    cp.add_argument("--scope", metavar="DIR", help="filter to one monorepo top-level dir")
    cp.add_argument("--label", metavar="WORD", help="filter to tasks labelled via `cage human outcome --label`")
    cp.add_argument("--by", default="stack", metavar="KEYS",
                    help="comma-separated grouping keys from stack,scope,label (stack always included)")
    cp.add_argument("--agent-only", action="store_true",
                    help="suppress the total-cost line (agent $ + human attention minutes × rate)")
    _json_flag(cp)
    _csv_flag(cp)
    _capture_flags(cp)
    cp.set_defaults(fn=clicmds.cmd_compare)

    es = insights.add_parser("estimate",
                             help="pre-task cost band (median + IQR) from matching closed "
                                  "tasks — modeled, refuses thin history")
    es.add_argument("--scope", metavar="DIR", help="match tasks in one monorepo top-level dir")
    es.add_argument("--label", metavar="WORD", help="match tasks labelled via `cage human outcome --label`")
    es.add_argument("--agent", metavar="NAME", help="match tasks a given agent worked")
    es.add_argument("--record", metavar="TASK",
                    help="stamp the band onto this OPEN task row (est_tokens/est_usd/est_n "
                         "+ band bounds) so `cage insights calibration` can score it at close")
    _json_flag(es)
    _capture_flags(es)
    es.set_defaults(fn=clicmds.cmd_estimate)

    cb = insights.add_parser("calibration",
                             help="measured hit-rate of recorded estimates vs actuals — the "
                                  "estimator's empirical confidence level")
    cb.add_argument("--human", action="store_true",
                    help="score the derived-attention heuristic instead: derived/attested "
                         "minute ratio over tasks carrying both (refuses thin data)")
    _json_flag(cb)
    _csv_flag(cb)
    _capture_flags(cb)
    cb.set_defaults(fn=clicmds.cmd_calibration)

    tr = insights.add_parser("trend", help="cost+time savings over time, by week or month (§5b.4)")
    tr.add_argument("--by", choices=["week", "month"], default="week")
    tr.add_argument("--metric", choices=["cost", "time", "both"], default="both")
    tr.add_argument("--since", metavar="WINDOW")
    _json_flag(tr)
    _html_flag(tr)
    _csv_flag(tr)
    _capture_flags(tr)
    tr.set_defaults(fn=clicmds.cmd_trend)

    wy = insights.add_parser("why", help="full provenance: a call + every receipt against it")
    wy.add_argument("call_id")
    _json_flag(wy)
    _capture_flags(wy)
    wy.set_defaults(fn=clicmds.cmd_why)

    fc = insights.add_parser("forecast", help="project monthly spend vs the budget (§8.5)")
    _json_flag(fc)
    _capture_flags(fc)
    fc.set_defaults(fn=clicmds.cmd_forecast)

    rg = insights.add_parser("regression", help="alert when cost-per-call drifts up (§8.3)")
    rg.add_argument("--since", default="7d", metavar="WINDOW", help="recent window vs the baseline before it")
    rg.add_argument("--tolerance", type=float, default=0.2, help="drift fraction that trips the flag")
    _json_flag(rg)
    _capture_flags(rg)
    rg.set_defaults(fn=clicmds.cmd_regression)

    rc = insights.add_parser("recommend", help="cheapest-path: which tools to enable/skip (§8.4)")
    rc.add_argument("--since", metavar="WINDOW")
    _json_flag(rc)
    _capture_flags(rc)
    rc.set_defaults(fn=clicmds.cmd_recommend)

    # ── group: human (agent-vs-human axis) ─────────────────────────────────────
    human = _group(sub, "human", "agent-vs-human savings: show · record · outcome · quality")

    hu = human.add_parser("show", help="agent-vs-human savings: $ and hours saved (§4.1)")
    hu.add_argument("--since", metavar="WINDOW", help="window like 30d / 2w")
    hu.add_argument("--task", help="single task id")
    hu.add_argument("--agent", help="filter to one agent")
    _json_flag(hu)
    _html_flag(hu)
    _csv_flag(hu)
    _capture_flags(hu)
    hu.set_defaults(fn=clicmds.cmd_human)

    hr = human.add_parser("record", help="record a Tier-1 human alternative for a task (§5)",
                          epilog="examples:\n"
                                 "  cage human record --task T --type feature   # price by task-type table\n"
                                 "  cage human record --task T --minutes 90      # or by explicit minutes\n"
                                 "  cage human record --task T --usd 150 --measured  # a real quote",
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

    oc = human.add_parser("outcome", help="record a task's outcome (ok / redo) for quality cost")
    oc.add_argument("task")
    oc.add_argument("--redo", action="store_true", help="mark the task as needing a human redo")
    oc.add_argument("--label", metavar="WORD",
                    help="tag the task with one short token (letters/digits/._-, ≤32 chars) "
                         "for `cage insights compare --by label` grouping — never a path or free text")
    oc.add_argument("--minutes", type=float, metavar="N",
                    help="attest the human minutes this task actually took (writes the same "
                         "tool=\"human\" receipt as `cage human record --minutes`; attested "
                         "beats derived turn-gap minutes, never summed)")
    oc.set_defaults(fn=clicmds.cmd_outcome)

    ql = human.add_parser("quality", help="quality-adjusted cost: cost per successful task (§8.2)")
    _json_flag(ql)
    _capture_flags(ql)
    ql.set_defaults(fn=clicmds.cmd_quality)

    # ── group: authorship (who wrote which files + its git-notes distribution) ──
    authorship = _group(sub, "authorship",
                        "who wrote which files + its distribution: origin · verify · "
                        "notes-sync · ledger-sync (§3.5, §3.6.3)")

    og = authorship.add_parser("origin", help="authorship attribution for a commit (§3.5)",
                               epilog="examples:\n"
                                      "  cage authorship origin HEAD                       # who wrote this commit\n"
                                      "  cage authorship origin a1b2c3d --attest human     # human triage: assert origin\n"
                                      "  cage authorship origin a1b2c3d --attest agent --agent claude-code",
                               formatter_class=argparse.RawDescriptionHelpFormatter)
    og.add_argument("sha")
    og.add_argument("--attest", choices=["human", "agent", "agent-autonomous"], help="record a human-triage attestation for this sha")
    og.add_argument("--agent", default="", help="agent name to attach to --attest")
    _json_flag(og)
    og.set_defaults(fn=clicmds.cmd_origin)

    authorship.add_parser("verify", help="report-only consistency check over the provenance ledger (never fails the build)").set_defaults(fn=clicmds.cmd_verify)

    ns = authorship.add_parser("notes-sync", help="merge buffered provenance into refs/notes/cage-provenance (§3.5)",
                               epilog="example:\n"
                                      "  cage authorship notes-sync                 # dry-run: print the merge plan\n"
                                      "  CAGE_NOTES_WRITE=1 cage authorship notes-sync  # actually push the notes (CI only)",
                               formatter_class=argparse.RawDescriptionHelpFormatter)
    ns.add_argument("--write", action="store_true", help="push to refs/notes (default: dry-run unless CAGE_NOTES_WRITE=1)")
    _json_flag(ns)
    ns.set_defaults(fn=clicmds.cmd_notes_sync)

    ls = authorship.add_parser("ledger-sync", help="merge local call/receipt rows into refs/notes/cage-ledger for a team view (§3.6.3)",
                               epilog="example:\n"
                                      "  cage authorship ledger-sync                # dry-run: print the merge plan\n"
                                      "  CAGE_NOTES_WRITE=1 cage authorship ledger-sync  # actually push the team ledger (CI only)\n"
                                      "  cage report --team              # read the merged team view",
                               formatter_class=argparse.RawDescriptionHelpFormatter)
    ls.add_argument("--write", action="store_true", help="push to refs/notes (default: dry-run unless CAGE_NOTES_WRITE=1)")
    _json_flag(ls)
    ls.set_defaults(fn=clicmds.cmd_ledger_sync)

    # ── group: prices (unchanged; positional-action pattern) ───────────────────
    pr = sub.add_parser("prices",
                        help="manage the price tables the ledger reprices against: "
                             "list · unpriced · set · alias · route-tool · sync (§3.3)",
                        epilog="examples:\n"
                               "  cage prices unpriced                     # what's billing $0, with a fix line each\n"
                               "  cage prices set anthropic claude-sonnet-5 --input 2 --output 10 --cache-read 0.20\n"
                               "  cage prices alias - copilot/auto --to anthropic/claude-sonnet-4-6\n"
                               "  cage prices route-tool graphify --to anthropic/claude-sonnet-4-6\n"
                               "  cage prices list                         # every visible row: bundled vs project\n"
                               "  cage prices sync                         # dry-run diff vs the installed bundle\n"
                               "Writes land in the project policy.toml (the bundled table is read-only);\n"
                               "derived views re-price immediately — the ledger is never rewritten.\n"
                               "cage never fetches a price: research is yours (vendor pricing page).",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    pr.add_argument("action", choices=["list", "unpriced", "set", "alias", "route-tool",
                                       "sync"],
                    help="list=rows+origin+meta · unpriced=$0 models+fix lines · "
                         "set=insert/update a project row · alias=route a router "
                         "pseudo-model · route-tool=price a tool's call-less receipts "
                         "(§4.5) · sync=diff vs the installed bundle")
    pr.add_argument("provider", nargs="?", help="set/alias: provider key ('-' = the "
                    "empty provider some router rows stamp) · route-tool: the tool name")
    pr.add_argument("model", nargs="?", help="set/alias: model id exactly as `cage "
                    "prices unpriced` printed it")
    pr.add_argument("--input", type=float, help="set: USD per MTok of input")
    pr.add_argument("--output", type=float, help="set: USD per MTok of output")
    pr.add_argument("--cache-read", dest="cache_read", type=float,
                    help="set: USD per MTok of cached input (default: 0.1× input)")
    pr.add_argument("--to", help="alias/route-tool: target price row as <provider>/<model>")
    pr.add_argument("--remove", action="store_true",
                    help="route-tool: delete the tool's route from the managed block")
    pr.add_argument("--update", action="store_true",
                    help="sync: apply bundled values to rows confirmed via --yes; "
                         "restamp [meta] (default: dry-run)")
    pr.add_argument("--yes", action="append", metavar="PROV/MODEL",
                    help="sync --update: confirm one drifted row (repeatable; 'all' "
                         "confirms every drifted row)")
    pr.add_argument("--since", metavar="WINDOW", help="unpriced: window like 7d / 2w")
    _json_flag(pr)
    pr.set_defaults(fn=clicmds.cmd_prices)

    # ── group: study (unchanged; positional-action pattern) ────────────────────
    st2 = sub.add_parser("study",
                         help="fleet study: recorded phases + paired-by-machine deltas "
                              "across laptops (plan §4.9)",
                         epilog="examples:\n"
                                "  cage study join baseline      # enroll this machine: wire + start + doctor\n"
                                "  cage study start plugin       # switch phase (opaque machine id, no hostname)\n"
                                "  cage study stop               # end the current phase\n"
                                "  cage data export --study      # one bundle for the analyst\n"
                                "  cage import bundle*.zip       # analyst: merge bundles (idempotent)\n"
                                "  cage study report             # coverage first, then the paired delta",
                         formatter_class=argparse.RawDescriptionHelpFormatter)
    st2.add_argument("action", choices=["join", "start", "stop", "report", "id"],
                     help="join=enroll+wire+start · start/stop=phase markers · "
                          "report=coverage+paired delta · id=print the opaque machine id")
    st2.add_argument("phase", nargs="?", help="phase label for join/start (one short token)")
    st2.add_argument("--agent-only", action="store_true",
                     help="report: suppress the total-cost line (agent $ + human "
                          "attention minutes × rate)")
    _json_flag(st2)
    _csv_flag(st2)
    st2.set_defaults(fn=clicmds.cmd_study)

    # ── group: policy (unchanged; positional-action pattern) ───────────────────
    po = sub.add_parser("policy",
                        help="upgrade the project policy.toml to the installed "
                             "bundle: diff · sync (§3.10)",
                        epilog="examples:\n"
                               "  cage policy diff                         # dry-run: add/update/keep/orphan categories\n"
                               "  cage policy sync --apply                 # write adds+updates, stamp [meta] policy_version\n"
                               "  cage policy sync --apply --yes all       # also accept the per-key confirm bucket\n"
                               "Customized values are never modified, orphans never deleted; pricing\n"
                               "tables delegate to `cage prices sync` (its summary embeds here).\n"
                               "Nothing ever auto-applies this — hints recommend, humans run.",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    po.add_argument("action", choices=["diff", "sync"],
                    help="diff=dry-run categorized view · sync=same view; --apply writes")
    po.add_argument("--apply", action="store_true",
                    help="sync: write adds/updates and stamp [meta] policy_version "
                         "(default: dry-run)")
    po.add_argument("--yes", action="append", metavar="SECTION.KEY",
                    help="sync --apply: confirm one non-reconstructable row "
                         "(repeatable; 'all' confirms every one shown)")
    _json_flag(po)
    po.set_defaults(fn=clicmds.cmd_policy)

    # ── group: data (capture, export, and local adapters) ──────────────────────
    data = _group(sub, "data",
                  "capture, export & local adapters: export · cleanup · limits · "
                  "watch · serve · proxy · meter")

    ex = data.add_parser("export", help="import (refresh) then emit the ledger as jsonl/csv/json",
                         epilog="examples:\n"
                                "  cage data export                         # refresh, then raw jsonl to stdout\n"
                                "  cage data export --csv calls -o spend.csv # flat call rows for a spreadsheet\n"
                                "  cage data export --csv receipts --since 30d # flat receipt rows (method column kept)\n"
                                "  cage data export --format json --since 30d  # structured summary (matches `cage report`)\n"
                                "  cage data export --no-import --format jsonl # emit the ledger as-is, no refresh\n"
                                "  cage data export --project . --agent claude # one project's Claude rows\n"
                                "Two export kinds, never blurred: the fleet bundle (--study, jsonl) is lossless,\n"
                                "merge-by-id, and re-importable; CSV is a one-way REPORTING format for\n"
                                "spreadsheets — never an import source (`cage query csv-output`).",
                         formatter_class=argparse.RawDescriptionHelpFormatter)
    ex.add_argument("--format", choices=["jsonl", "csv", "json"], default=None,
                    help="jsonl=raw rows (re-ingestable) · csv=flat call rows (same as "
                         "--csv calls) · json=summary (default: jsonl)")
    ex.add_argument("--csv", choices=["calls", "receipts", "tasks"], dest="csv_kind",
                    metavar="KIND",
                    help="flat one-way CSV of raw ledger rows for pivot-table analysis "
                         "(calls | receipts | tasks); same PII surface as the ledger — "
                         "counts and ids, never content")
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

    cu = data.add_parser("cleanup", help="prune aged .cage/state/ files (closed allowlist; dry-run by default)",
                         epilog="examples:\n"
                                "  cage data cleanup           # dry-run: list what would go (file · class · age)\n"
                                "  cage data cleanup --apply   # actually prune\n"
                                "  cage data cleanup --days 7  # tighter window for this run only\n"
                                "Cleanable (allowlist, by construction): aged debug.log/hooks-seen.jsonl rows,\n"
                                "stale pending-* provenance buffers, cursors whose source log is gone, *.tmp.\n"
                                "Never: ledger/, policy.toml, machine.json, study.jsonl, limits.json. State files\n"
                                "are never read by derived views — cleanup cannot change a reported number.",
                         formatter_class=argparse.RawDescriptionHelpFormatter)
    cu.add_argument("--apply", action="store_true", help="execute (default: dry-run print)")
    cu.add_argument("--days", type=int, metavar="N",
                    help="retention window for this run (default: [cleanup] days, else 30)")
    _json_flag(cu)
    cu.set_defaults(fn=clicmds.cmd_cleanup)

    lm = data.add_parser("limits", help="provider quota windows + estimated AI-credit use")
    _json_flag(lm)
    _capture_flags(lm)
    lm.set_defaults(fn=clicmds.cmd_limits)

    wt = data.add_parser("watch", help="foreground poll loop: import every interval until Ctrl-C (no OS job)",
                         epilog="example:\n"
                                "  cage data watch             # import all agents every 60s\n"
                                "  cage data watch --interval 300   # every 5 minutes\n"
                                "Registers nothing and stops with the terminal — cage installs no scheduler.",
                         formatter_class=argparse.RawDescriptionHelpFormatter)
    wt.add_argument("--agent", choices=[*SURFACES, "all"], default="all", help="which agent to meter (default: all)")
    wt.add_argument("--interval", type=int, default=60, metavar="SECONDS", help="seconds between imports (default: 60)")
    wt.add_argument("--since", metavar="WINDOW", help="only transcripts modified within a window like 7d / 24h / 2w")
    wt.set_defaults(fn=clicmds.cmd_watch)

    sv = data.add_parser("serve", help="local dashboard over the ledger ($0)")
    sv.add_argument("--port", type=int, default=8788)
    sv.set_defaults(fn=clicmds.cmd_serve)

    px = data.add_parser("proxy", help="metering reverse-proxy for clients you can't edit")
    px.add_argument("--port", type=int, default=8788)
    px.add_argument("--upstream", default="https://api.anthropic.com", help="real API base URL")
    px.set_defaults(fn=clicmds.cmd_proxy)

    mt = data.add_parser("meter", help="run a command under the metering proxy: cage data meter -- <cmd>")
    mt.add_argument("--upstream", default="https://api.anthropic.com")
    mt.add_argument("argv", nargs=argparse.REMAINDER, help="-- <command> [args…]")
    mt.set_defaults(fn=clicmds.cmd_meter)

    gf = data.add_parser("graphify", help="meter a third-party graphify call without touching it",
                         epilog="example:\n  cage data graphify -- graphify query \"auth flow\"   # runs graphify, files one savings receipt",
                         formatter_class=argparse.RawDescriptionHelpFormatter)
    gf.add_argument("--task", default="", help="task id to bind the saving to (default: project dir name)")
    gf.add_argument("argv", nargs=argparse.REMAINDER, help="-- graphify <query|path|explain> …")
    gf.set_defaults(fn=clicmds.cmd_graphify)

    # ── hidden top-level verbs (callable, off the front door) ──────────────────
    # mcp is spawned by wired configs; debug is a diagnostic; demo seeds the §4.4
    # example (referenced from the README quickstart). None are daily human verbs.
    sub.add_parser("mcp", help=argparse.SUPPRESS).set_defaults(fn=clicmds.cmd_mcp)
    sub.add_parser("demo", help=argparse.SUPPRESS).set_defaults(fn=clicmds.cmd_demo)
    dbg = sub.add_parser("debug", help=argparse.SUPPRESS)
    dbg.add_argument("--tail", type=int, default=20, metavar="N", help="show the last N events (default: 20)")
    dbg.add_argument("--json", action="store_true", help="one JSON event per line")
    dbg.set_defaults(fn=clicmds.cmd_debug)

    # Internal hook entrypoints (wired by `cage setup --wire-only`, not for direct use).
    sub.add_parser("hook-session-start", help=argparse.SUPPRESS).set_defaults(fn=lambda a: hooks.session_start())
    sub.add_parser("hook-stop", help=argparse.SUPPRESS).set_defaults(fn=lambda a: hooks.stop())
    sub.add_parser("hook-session-end", help=argparse.SUPPRESS).set_defaults(fn=lambda a: hooks.session_end())
    sub.add_parser("hook-post-tool-use", help=argparse.SUPPRESS).set_defaults(fn=lambda a: hooks.post_tool_use())
    sub.add_parser("hook-post-commit", help=argparse.SUPPRESS).set_defaults(fn=lambda a: hooks.post_commit())
    pcm = sub.add_parser("hook-prepare-commit-msg", help=argparse.SUPPRESS)
    pcm.add_argument("msg_path")
    pcm.set_defaults(fn=lambda a: hooks.prepare_commit_msg(a.msg_path))

    return p


# Global options that consume the following token (so the command word isn't mistaken
# for their value during the removed-verb pre-scan). Flags like --json/--usd/--version
# take no value and are skipped as bare options.
_VALUE_OPTS = ("--ledger",)


def _command_token(argv: list[str]) -> str | None:
    """The first positional token in ``argv`` — the command word — skipping global
    options (and the value of `--ledger DIR`). Used only to spot a removed verb before
    argparse runs; returns None if there is no command (bare `cage`)."""
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _VALUE_OPTS:
            i += 2
            continue
        if a.startswith("-"):  # a flag or --opt=value — never the command
            i += 1
            continue
        return a
    return None


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

    # Removed-verb directions (plan Phase 3 §4, one release): catch the old top-level
    # name before argparse would either mis-route it or reject it, print the new
    # invocation, exit 1 — a direction, never a silent alias, and never runs the moved
    # command. Genuinely-unknown verbs fall through to argparse's invalid-choice (exit 2).
    scan = sys.argv[1:] if argv is None else argv
    tok = _command_token(scan)
    if tok in verbmap.REMOVED:
        print(f"error: {verbmap.direction(tok)}", file=sys.stderr)
        return 1

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
