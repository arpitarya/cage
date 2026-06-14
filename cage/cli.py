"""`cage` CLI — argparse dispatch over the deterministic command surface (plan §7)."""
from __future__ import annotations

import argparse

from cage import __version__, clicmds, hooks
from cage.agents import SURFACES
from cage.report import DIMENSIONS


def _json_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="machine-readable output (agent-as-user)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cage",
                                description="Cage — a flux: LLM cost + savings ledger ($0, deterministic).")
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

    mx = sub.add_parser("matrix", help="counterfactual permutation table for a task (§4.4)")
    mx.add_argument("--task", help="task id (default: most recent)")
    _json_flag(mx)
    mx.set_defaults(fn=clicmds.cmd_matrix)

    bd = sub.add_parser("budget", help="session/day spend vs policy ceilings (§8.1)")
    bd.add_argument("--session", help="session id to total against the session cap")
    _json_flag(bd)
    bd.set_defaults(fn=clicmds.cmd_budget)

    ro = sub.add_parser("roi", help="saved $ per tool vs its own cost + latency")
    ro.add_argument("--since", metavar="WINDOW", help="window like 30d / 2w")
    _json_flag(ro)
    ro.set_defaults(fn=clicmds.cmd_roi)

    wy = sub.add_parser("why", help="full provenance: a call + every receipt against it")
    wy.add_argument("call_id")
    _json_flag(wy)
    wy.set_defaults(fn=clicmds.cmd_why)

    sv = sub.add_parser("serve", help="local dashboard over the ledger ($0)")
    sv.add_argument("--port", type=int, default=8788)
    sv.set_defaults(fn=clicmds.cmd_serve)

    sub.add_parser("demo", help="seed the plan's §4.4 worked example to prove the thesis").set_defaults(fn=clicmds.cmd_demo)

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

    sub.add_parser("mcp", help="serve the ledger over MCP (stdio JSON-RPC) for any agent").set_defaults(fn=clicmds.cmd_mcp)
    sub.add_parser("setup", help="install the /cage skill into ~/.claude + ~/.codex").set_defaults(fn=clicmds.cmd_setup)

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
