"""`cage` CLI — argparse dispatch over the deterministic command surface (plan §7)."""
from __future__ import annotations

import argparse

from cage import __version__, clicmds, hooks
from cage.agents import SURFACES
from cage.report import DIMENSIONS


_DESCRIPTION = """\
Cage — a flux: a deterministic attribution ledger for LLM token traffic and tool
savings. $0, stdlib-only, deterministic; the ledger is append-only and every view
is derived (same ledger + same policy ⇒ same numbers). Third in the family after
graphify (code→graph) and fux (decisions→rules)."""

_EPILOG = """\
commands by category:
  ledger        report · budget · why            spend & per-call provenance
  attribution   attrib · matrix · roi            per-tool savings (the differentiator)
  human axis    human · human-record · trend     agent-vs-human $ and hours saved
  ops           quality · regression · recommend · forecast · outcome
  setup         init · adopt · doctor · setup · hooks · proxy · meter · mcp · serve
  meta          query · demo · graphify · import-codex

examples:
  cage report --by model --since 7d        # where the spend went, last 7 days
  cage matrix --human                       # what each tool stack would cost vs a person
  cage human-record --task T --type feature # log the human alternative for a task
  cage query "how is human cost calculated" # explain any number with its live formula
  cage adopt                                # wire cage into this project's agents

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
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="scaffold .cage/ (policy + gitignored ledger)").set_defaults(fn=clicmds.cmd_init)

    rep = sub.add_parser("report", help="ledger: spend by agent / route / model / day")
    rep.add_argument("--by", choices=DIMENSIONS, default="route", help="group dimension")
    rep.add_argument("--since", metavar="WINDOW", help="window like 7d / 24h / 2w")
    _json_flag(rep)
    rep.set_defaults(fn=clicmds.cmd_report)

    at = sub.add_parser("attrib", help="per-tool marginal savings for a task (§4.2)")
    at.add_argument("--task", help="task id (default: most recent)")
    _json_flag(at)
    at.set_defaults(fn=clicmds.cmd_attrib)

    mx = sub.add_parser("matrix", help="counterfactual permutation table for a task (§4.4)",
                        epilog="example:\n  cage matrix --human   # add a human-baseline row + vs-human columns",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    mx.add_argument("--task", help="task id (default: most recent)")
    mx.add_argument("--human", action="store_true", help="add the Tier-1 human anchor row + vs-human columns")
    _json_flag(mx)
    _html_flag(mx)
    mx.set_defaults(fn=clicmds.cmd_matrix)

    bd = sub.add_parser("budget", help="session/day spend vs policy ceilings (§8.1)")
    bd.add_argument("--session", help="session id to total against the session cap")
    _json_flag(bd)
    bd.set_defaults(fn=clicmds.cmd_budget)

    ro = sub.add_parser("roi", help="saved $ per tool vs its own cost + latency")
    ro.add_argument("--since", metavar="WINDOW", help="window like 30d / 2w")
    _json_flag(ro)
    ro.set_defaults(fn=clicmds.cmd_roi)

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
    sub.add_parser("setup", help="install the global /cage asset into all agent homes (claude/codex/copilot/kiro)").set_defaults(fn=clicmds.cmd_setup)

    ad = sub.add_parser("adopt", help="full per-project setup: init + agent wiring (claude/codex/copilot/kiro) + graphify interceptor + PATH")
    ad.add_argument("--no-hooks", dest="hooks", action="store_false", help="skip all agent wiring (claude/codex/copilot/kiro)")
    ad.add_argument("--no-graphify", dest="graphify", action="store_false", help="skip the graphify interceptor")
    for _s in SURFACES:
        ad.add_argument(f"--{_s}", action="store_true", help=f"wire only the {_s} surface (default: all four)")
    ad.add_argument("--json", action="store_true", help="machine-readable output")
    ad.set_defaults(fn=clicmds.cmd_adopt)

    dr = sub.add_parser("doctor", help="verify this project's Cage setup is correct and working")
    dr.add_argument("--json", action="store_true", help="machine-readable output")
    dr.set_defaults(fn=clicmds.cmd_doctor)

    hk = sub.add_parser("hooks", help="wire Cage into agents (claude/codex/copilot/kiro)")
    hk.add_argument("action", choices=["install", "status"], nargs="?", default="install")
    for _s in SURFACES:
        hk.add_argument(f"--{_s}", action="store_true", help=f"only the {_s} surface")
    hk.set_defaults(fn=clicmds.cmd_hooks)

    ic = sub.add_parser("import-codex", help="best-effort meter a Codex rollout JSONL (file or dir)")
    ic.add_argument("path", help="a rollout-*.jsonl file or ~/.codex/sessions dir")
    ic.set_defaults(fn=clicmds.cmd_import_codex)

    # Internal hook entrypoints (wired by `cage hooks install`, not for direct use).
    sub.add_parser("hook-session-start").set_defaults(fn=lambda a: hooks.session_start())
    sub.add_parser("hook-session-end").set_defaults(fn=lambda a: hooks.session_end())
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)
