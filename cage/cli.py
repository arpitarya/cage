"""`cage` CLI — argparse dispatch over the deterministic command surface (plan §7).

Phase 3 (CLI tiering): the front door is five daily verbs + six groups. Moved verbs
keep their exact flags and run functions — they dispatch from a group subparser
instead of the top level, so behavior is frozen. Old top-level names are removed and
answer with a one-line direction (`cage.verbmap`); `mcp`/`debug`/`demo` and the
`hook-*` plumbing stay callable but hidden from `cage --help`.
"""
from __future__ import annotations

import argparse

from cage import __version__, clicmds, errors, hookcmd, verbmap
from cage.agents import SURFACES


# The verbatim front-door help (plan Phase 3 mock). `_RootParser.format_help` returns
# this exactly — no usage/options noise; the daily loop and the groups, one screen.
# Golden-pinned by tests/test_output_spec.py — the goldens ARE the output contract
# (the generated docs/cli-output-spec.md was removed in the hookless rebuild);
# any edit ⇒ re-bless with CAGE_BLESS_GOLDENS=1.
_ROOT_HELP = """\
cage — measure what your AI agents use, prove what your tools save

daily:
  import      pull every agent's usage into the ledger
  setup       make this project (or --global) metered — scaffold + wire
  doctor      is capture healthy? (--paths shows every probed location)
  query       ask cage how any number or mechanism works

groups (run any group name for its commands):
  insights    chats · graphify · commits · commit · why
  task        outcome · time
  authorship  origin · summary · verify · notes-sync
  study       join · start · stop · report · export · id
  policy      diff · sync

$ cage import                     # pull every agent's usage into the ledger
$ cage insights chats            # which conversation used the tokens?
$ cage task outcome t_9f31        # close a task so the authorship views can see it
$ cage study join baseline        # enroll this laptop in the fleet study
$ cage insights graphify         # per-chat graphify saving
"""


class _RootParser(argparse.ArgumentParser):
    """Top parser only: `cage --help` renders the curated front door verbatim
    (`_ROOT_HELP`), not argparse's auto usage/subcommand dump. Subparsers use the
    stock class (via `parser_class=` below), so `cage import --help` etc. are normal."""

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


def _export_flags(p: argparse.ArgumentParser, view: str) -> None:
    """The artifact surface every insight carries (`cage/viewexport.py`).

    ``--export`` writes the view to disk: bare = `<ledger>/.cage/output/<view>-<stamp>/`
    holding every format this view has, a path with a known suffix = exactly that file,
    any other path = a per-run folder under it. **Additive** — stdout is byte-identical
    with and without it, and the confirmation goes to stderr.

    ``--stamp`` is the opt-in half of the same metadata block: mandatory in an artifact,
    optional on a terminal (`runstamp`'s docstring says why the determinism law
    survives). ``view`` is the parser's own verb path, and it is set HERE rather than at
    the handler so the artifact's name and its `view=` field can never disagree with the
    command that produced it.

    Deliberately **not** on bare `cage`: a root-level `--export` with an optional value
    would swallow the following subcommand (`cage --export chats` would export to a file
    named `chats`). Bare `cage` is a help surface, not a view; the per-view flag is the
    only artifact route."""
    p.add_argument("--export", nargs="?", const="", metavar="PATH",
                   help="write this view to disk (default "
                        ".cage/output/<view>-<stamp>/, every format it has; "
                        "PATH.csv/.json/.md/.txt writes one file) — every artifact "
                        "carries a generated-at stamp (`cage query view-export`)")
    p.add_argument("--stamp", action="store_true",
                   help="prepend the generated-at metadata block to stdout too "
                        "(always present in an --export artifact)")
    p.set_defaults(view=view)


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
    """A command group (insights/task/authorship/data) — a subparser holding nested
    subparsers that dispatch to the same run functions. Bare `cage <group>` prints the
    group's help (its command list); a chosen subcommand's own `fn` default wins.

    NOTE: ``help_text`` is **not rendered anywhere** — it would appear in the parent's
    subcommand listing, and the parent is the root, whose help `_RootParser.format_help`
    replaces wholesale with `_ROOT_HELP`. The front door people actually read is that
    literal, and `tests/test_cli_tiering.py` gates it against the live parser."""
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
    p.add_argument("--ledger", metavar="DIR", help="use this cage base dir as the active "
                   "ledger (overrides the project/global resolution; the .cage-equivalent "
                   "holding ledger/, state/ and policy.toml)")
    _capture_flags(p)  # bare `cage` (overview) is a read too — capture-on-read applies
    # required=False: bare `cage` (no subcommand) prints the headline banner via main().
    # parser_class: children are stock ArgumentParsers, so only the root overrides help.
    sub = p.add_subparsers(dest="cmd", required=False, metavar="<command>",
                           parser_class=argparse.ArgumentParser)

    # ── tier 1: the daily front door ──────────────────────────────────────────
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
    im.add_argument("--rescan-graphify", dest="rescan_graphify", action="store_true",
                    help="re-run graphify savings detection over every matched log, ignoring "
                         "the incremental cursor (backfills sessions ingested before a route "
                         "shipped; detection only — no call/credit re-ingest, idempotent)")
    im.add_argument("--rescan-metrics", dest="rescan_metrics", action="store_true",
                    help="re-parse every matched log into the per-agent metrics ledgers "
                         "(ledger/{claude,copilot,kiro}/), ignoring the incremental cursor "
                         "(backfills stores ingested before the metric routes shipped; "
                         "metrics only — no call/credit re-ingest, idempotent)")
    im.set_defaults(fn=clicmds.cmd_import)

    st = sub.add_parser("setup", help="make this project (or --global) metered: scaffold .cage/ + MCP wiring + graphify (capture is pull-based — `cage import`)",
                        epilog="examples:\n"
                               "  cage setup --claude             # scaffold + MCP wiring + graphify for claude\n"
                               "  cage setup --all                # all three agents\n"
                               "  cage setup --project-only --claude  # scaffold + graphify only, no MCP wiring\n"
                               "  cage setup --wire-only --claude     # MCP wiring only, no scaffold\n"
                               "  cage setup --status             # show which agents are wired\n"
                               "  cage setup --python-launcher --all  # no-exe wiring for locked-down endpoints",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    for _s in SURFACES:
        st.add_argument(f"--{_s}", action="store_true", help=f"set up the {_s} agent")
    st.add_argument("--all", dest="all_agents", action="store_true", help="set up all three agents (capture works for any of them)")
    st.add_argument("--project-only", action="store_true", help="scaffold .cage/ + graphify + PATH only; skip MCP wiring")
    st.add_argument("--wire-only", action="store_true", help="wire agent(s) only; skip scaffold and graphify")
    st.add_argument("--status", action="store_true", help="report which agents are wired (no changes)")
    st.add_argument("--global", dest="global_ledger", action="store_true",
                    help="initialize the global ledger (~/.cage) for project-less capture, then exit")
    st.add_argument("--no-project", dest="project", action="store_false", help="skip per-project .cage/ scaffold + MCP wiring")
    st.add_argument("--no-graphify", dest="graphify", action="store_false", help="skip the graphify interceptor")
    st.add_argument("--python-launcher", action="store_true",
                    help="persist [wiring] python_launcher=true and wire everything "
                         "via `python3 -m cage` / `py -3 -m cage` — no exe probed or "
                         "executed (restricted endpoints; `cage query restricted-env`)")
    st.add_argument("--hooks", action="store_true",
                    help="also wire the opt-in L1 lifecycle hooks (agent identity at "
                         "capture, auto task-close, budget blocking). OFF by default — "
                         "capture needs no hooks, and re-running `cage setup` without "
                         "this flag removes them again. CLI sessions only: hooks do not "
                         "fire under a VS Code extension")
    st.add_argument("--skills", action="store_true",
                    help="also install the opt-in L3 skills — one source text delivered "
                         "as a Claude skill, a Copilot prompt and a Kiro steering doc. "
                         "OFF by default; re-running `cage setup` without this flag "
                         "removes them. A skill never computes a number: it runs cage "
                         "and quotes it")
    st.add_argument("--no-hooks", action="store_true",
                    help="explicitly assert the hookless floor (the default) — a script "
                         "uses this to state the intent rather than rely on it")
    st.add_argument("--sync-sources", dest="sync_sources", action="store_true",
                    help="refresh the cage-managed [sources] block in cage.toml from the "
                         "built-in defaults (Directive A) — preserves user-added entries; "
                         "run after upgrading cage to pick up new/corrected default paths")
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
    dr.add_argument("--wiring", action="store_true",
                    help="installed-artifact inventory: every wired file (project + "
                         "global/user), its status (current/stale/dead/foreign), and "
                         "a per-agent fully/partially/not-wired verdict (read-only)")
    dr.set_defaults(fn=clicmds.cmd_doctor)

    qy = sub.add_parser("query", help="explain how a value is calculated, or how cage itself works ($0, deterministic)",
                        epilog="examples:\n"
                               "  cage query \"how does cage work\"      # concept: the front door\n"
                               "  cage query \"how is attribution calculated\"\n"
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

    # ── group: insights (per-chat & per-commit usage views, the differentiator) ─
    insights = _group(sub, "insights",
                       "per-chat & per-commit usage views: chats · graphify · "
                       "commits · commit · why")

    ch = insights.add_parser("chats",
                             help="per-chat detail view: tokens/cached/cost by "
                                  "(agent, surface, session), titled where the store "
                                  "has a title (local-only — no --team)")
    ch.add_argument("--since", metavar="WINDOW", help="window like 30d / 2w")
    ch.add_argument("--agent", choices=[*SURFACES, "all"], default="all",
                    help="filter to one agent (default: all)")
    ch.add_argument("--all", action="store_true",
                    help="show every chat (default: top 20 by tokens_in)")
    _json_flag(ch)
    _csv_flag(ch)
    _capture_flags(ch)
    _export_flags(ch, "insights chats")
    ch.set_defaults(fn=clicmds.cmd_chats)

    gx = insights.add_parser("graphify",
                             help="per-chat graphify usage & GROSS saving: recorded "
                                  "tokens · without-graphify counterfactual · saved%% "
                                  "(tokens-only — no --usd)")
    gx.add_argument("--since", metavar="WINDOW", help="window like 30d / 2w")
    gx.add_argument("--agent", choices=[*SURFACES, "all"], default="all",
                    help="filter to one agent (default: all)")
    gx.add_argument("--all", action="store_true",
                    help="show every receipt-bearing chat (default: top 20 by saved)")
    gx.add_argument("--all-chats", dest="all_chats", action="store_true",
                    help="include chats with no graphify receipts too (gfx cells `—`)")
    _json_flag(gx)
    _csv_flag(gx)
    _capture_flags(gx)
    _export_flags(gx, "insights graphify")
    gx.set_defaults(fn=clicmds.cmd_graphify_chats)

    cm = insights.add_parser("commits",
                             help="one row per commit: tokens, human hours, and the "
                                  "agent / human~ / unattr / unkn line split "
                                  "(no USD on this surface, by design)")
    cm.add_argument("--since", metavar="WINDOW",
                    help="window like 7d / 24h / 2w (no default; each commit costs one "
                         "`git show`, so a window is the way to bound a big history)")
    cm.add_argument("--all", action="store_true",
                    help="show every commit (default: the 20 newest)")
    _json_flag(cm)
    _csv_flag(cm)
    _capture_flags(cm)
    _export_flags(cm, "insights commits")
    cm.set_defaults(fn=clicmds.cmd_commits)

    cd = insights.add_parser("commit",
                             help="one commit in detail: tokens · origin · line "
                                  "buckets · suggested-vs-kept · per-file · time")
    cd.add_argument("sha", help="commit sha (short or full)")
    cd.add_argument("--files", action="store_true",
                    help="show every file (default: the 8 largest)")
    _json_flag(cd)
    _csv_flag(cd)
    _capture_flags(cd)
    _export_flags(cd, "insights commit")
    cd.set_defaults(fn=clicmds.cmd_commit)

    wy = insights.add_parser("why", help="full provenance: a call + every receipt against it")
    wy.add_argument("call_id")
    _json_flag(wy)
    _capture_flags(wy)
    _export_flags(wy, "insights why")
    wy.set_defaults(fn=clicmds.cmd_why)

    # ── group: task (the task-outcome axis the cost-impact views read) ─────────
    # These two lived under the `human` group until v0.36 purely by filing accident:
    # neither is the removed Tier-1 human-cost axis. `outcome` is the task-CLOSE verb
    # every cost-impact view depends on (compare/estimate/calibration read only closed
    # tasks); `quality` is cost-per-successful-task (§8.2). They moved, they did not go.
    task = _group(sub, "task", "task outcomes, attested time and quality-adjusted cost: outcome · time · quality")

    oc = task.add_parser("outcome", help="close a task with its outcome (ok / redo)")
    oc.add_argument("task")
    oc.add_argument("--redo", action="store_true", help="mark the task as needing a redo")
    oc.add_argument("--label", metavar="WORD",
                    help="tag the task with one short token (letters/digits/._-, ≤32 chars); "
                         "recorded on the task row — never a path or free text")
    oc.set_defaults(fn=clicmds.cmd_outcome)

    tt = task.add_parser("time",
                         help="attest how long YOU spent on a task — minutes only, "
                              "never a rate (`cage insights commits` shows it as *)",
                         epilog="examples:\n"
                                "  cage task time 45m                 # the most recent task\n"
                                "  cage task time 1h30m --task t_9f31\n"
                                "  cage task time 90                  # bare digits = minutes\n"
                                "An attestation ALWAYS outranks the wall-clock estimator, and no\n"
                                "hourly rate or dollar figure is derived from it — anywhere.",
                         formatter_class=argparse.RawDescriptionHelpFormatter)
    tt.add_argument("duration", help="45m · 2h · 1h30m · a bare number of minutes")
    tt.add_argument("--task", help="task id (default: the most recent)")
    tt.set_defaults(fn=clicmds.cmd_task_time)

    # ── group: authorship (who wrote which files + its git-notes distribution) ──
    authorship = _group(sub, "authorship",
                        "who wrote which files + its distribution: origin · summary · "
                        "verify · notes-sync (§3.5)")

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

    au = authorship.add_parser("summary",
                               help="how much of this repo's history cage can speak "
                                    "to at all — unknown-rate first, then the rows")
    au.add_argument("--since", metavar="WINDOW", help="window like 7d / 24h / 2w")
    _json_flag(au)
    _csv_flag(au)
    _capture_flags(au)
    _export_flags(au, "authorship summary")
    au.set_defaults(fn=clicmds.cmd_authorship_summary)

    authorship.add_parser("verify", help="report-only consistency check over the provenance ledger (never fails the build)").set_defaults(fn=clicmds.cmd_verify)

    ns = authorship.add_parser("notes-sync", help="merge buffered provenance into refs/notes/cage-provenance (§3.5)",
                               epilog="example:\n"
                                      "  cage authorship notes-sync                 # dry-run: print the merge plan\n"
                                      "  CAGE_NOTES_WRITE=1 cage authorship notes-sync  # actually push the notes (CI only)",
                               formatter_class=argparse.RawDescriptionHelpFormatter)
    ns.add_argument("--write", action="store_true", help="push to refs/notes (default: dry-run unless CAGE_NOTES_WRITE=1)")
    _json_flag(ns)
    ns.set_defaults(fn=clicmds.cmd_notes_sync)



    # ── group: study ───────────────────────────────────────────────────────────
    st_g = sub.add_parser("study",
                         help="fleet study: recorded phases + paired-by-machine deltas "
                              "across laptops (plan §4.9)",
                         epilog="examples:\n"
                                "  cage study join baseline      # enroll this machine: wire + start + doctor\n"
                                "  cage study start plugin       # switch phase (opaque machine id, no hostname)\n"
                                "  cage study stop               # end the current phase\n"
                                "  cage study export             # one bundle for the analyst\n"
                                "  cage import bundle*.zip       # analyst: merge bundles (idempotent)\n"
                                "  cage study report             # coverage first, then the paired delta",
                         formatter_class=argparse.RawDescriptionHelpFormatter)
    st_g.set_defaults(fn=lambda _a, _g=st_g: (_g.print_help(), 0)[1])
    st2 = st_g.add_subparsers(dest="study_cmd", metavar="<command>", required=False)

    def _study(name: str, help_text: str):
        q = st2.add_parser(name, help=help_text)
        _json_flag(q)
        q.set_defaults(fn=clicmds.cmd_study, action=name, phase=None)
        return q

    st_join = _study("join", "enroll this machine: wire + start + doctor")
    st_join.add_argument("phase", help="phase label (one short token)")
    st_start = _study("start", "switch phase (opaque machine id, no hostname)")
    st_start.add_argument("phase", help="phase label (one short token)")
    _study("stop", "end the current phase")
    _study("id", "print the opaque machine id")
    # The fleet bundle's only route. It lived on `cage data export --study` until
    # SURFACE-CUT deleted that group; the bundle is a study artifact, not a ledger
    # export, so it belongs on this group and never carried the csv/otel flags anyway
    # (they were a runtime refusal there — two export kinds, never blurred).
    st_exp = _study("export", "write the one-file fleet bundle for the analyst")
    st_exp.add_argument("out", nargs="?", default="",
                        metavar="PATH", help="bundle path (default: a stamped name in the ledger)")
    st_exp.add_argument("--since", metavar="WINDOW", help="window like 30d / 2w for the refresh sweep")
    _capture_flags(st_exp)
    st_rep = _study("report", "coverage first, then the paired-by-machine delta")
    # `report` is the ONLY study verb that is a rendered VIEW, so it is the only one
    # that carries the artifact/CSV surface. Before CLI-GAPS(b) these sat on the group
    # (the action was a positional) and `cmd_study` refused them at runtime; now a
    # marker verb simply has no such flag, and argparse says so as a usage error.
    _csv_flag(st_rep)
    _export_flags(st_rep, "study report")

    # ── group: policy ──────────────────────────────────────────────────────────
    po_g = sub.add_parser("policy",
                        help="upgrade the project policy.toml to the installed "
                             "bundle: diff · sync (§3.10)",
                        epilog="examples:\n"
                               "  cage policy diff                         # dry-run: add/update/keep/orphan categories\n"
                               "  cage policy sync --apply                 # write adds+updates, stamp [meta] policy_version\n"
                               "  cage policy sync --apply --yes all       # also accept the per-key confirm bucket\n"
                               "Customized values are never modified, orphans never deleted; pricing\n"

                               "Nothing ever auto-applies this — hints recommend, humans run.",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    po_g.set_defaults(fn=lambda _a, _g=po_g: (_g.print_help(), 0)[1])
    po = po_g.add_subparsers(dest="policy_cmd", metavar="<command>", required=False)

    def _policy_cmd(name: str, help_text: str):
        q = po.add_parser(name, help=help_text)
        _json_flag(q)
        q.set_defaults(fn=clicmds.cmd_policy, action=name, apply=False, yes=None)
        return q

    _policy_cmd("diff", "dry-run: add/update/keep/orphan categories")
    po_sy = _policy_cmd("sync", "the same view; --apply writes")
    po_sy.add_argument("--apply", action="store_true",
                       help="write adds/updates and stamp [meta] policy_version "
                            "(default: dry-run)")
    po_sy.add_argument("--yes", action="append", metavar="SECTION.KEY",
                       help="confirm one non-reconstructable row (repeatable; 'all' "
                            "confirms every one shown)")

    # ── hidden top-level verbs (callable, off the front door) ──────────────────
    # mcp is spawned by wired configs; debug is a diagnostic; demo seeds the §4.4
    # example (referenced from the README quickstart). None are daily human verbs.
    sub.add_parser("mcp", help=argparse.SUPPRESS).set_defaults(fn=clicmds.cmd_mcp)
    sub.add_parser("demo", help=argparse.SUPPRESS).set_defaults(fn=clicmds.cmd_demo)
    dbg = sub.add_parser("debug", help=argparse.SUPPRESS)
    dbg.add_argument("--tail", type=int, default=20, metavar="N", help="show the last N events (default: 20)")
    dbg.add_argument("--json", action="store_true", help="one JSON event per line")
    dbg.set_defaults(fn=clicmds.cmd_debug)

    # `cage hook <event>` — the ONE entrypoint the opt-in L1 hooks call
    # ([hookcmd.py](hookcmd.py)). Hidden from `cage --help` like `mcp`/`debug`: it is
    # wiring plumbing, not a verb a human types. It must stay a LIVE parser verb
    # regardless, because `wiringscan` checks every installed hook command against this
    # parser — a hook naming a dead verb exits 1 into a void, which is the F1 class.
    # The old pre-rebuild `hook-*` spellings stay in `verbmap.REMOVED` so stale wiring
    # from before v0.36 still prints a direction instead of failing silently.
    hk = sub.add_parser("hook", help=argparse.SUPPRESS)
    hk.add_argument("event", choices=hookcmd.EVENTS)
    hk.add_argument("--agent", required=True,
                    help="which agent fired this hook — stamped, never inferred")
    hk.add_argument("--session", default="", help="the host's session id, if it has one")
    hk.add_argument("--command", default="",
                    help="the command an agent ran (hashed for attestation, never stored)")
    hk.set_defaults(fn=lambda args: hookcmd.run(args))
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


def _hook_usage_failopen(scan: list[str]) -> None:
    """Explain a rejected `cage hook` invocation, then let the caller exit 0.

    **The direction is derived from `hookcmd.EVENTS`, not from a hand-maintained
    migration map.** That is the same lesson `wiringscan` records at the top of its
    own module — the detector (and here the fix-hint) must be the live thing, because
    a hand-kept map of renamed events is exactly what goes stale in the release that
    renames one. A rename therefore becomes a wiring migration with a printed fix, and
    it cannot rot.

    argparse has already written its own usage error to stderr; this adds the part an
    agent (or a human reading a hook log) can act on. Never raises."""
    import sys
    try:
        bad = next((a for a in scan[1:] if not a.startswith("-")), "")
        print(f"cage hook: {'unknown event ' + repr(bad) if bad else 'incomplete invocation'} — "
              f"this cage accepts: {', '.join(hookcmd.EVENTS)}. The wiring that called "
              f"this is stale; re-run `cage setup --hooks` to rewrite it. "
              f"Exiting 0 — a cage problem must never block your turn.", file=sys.stderr)
        from cage import debuglog, paths
        debuglog.event(paths.resolve_root(), event="hook", produced=False,
                       skip_reason=f"usage-error:{bad or 'incomplete'}",
                       detail="exited 0 instead of 2 (2 is the HOST's block code)")
    except Exception:  # noqa: BLE001 — this IS the fail-open path; never raise from it
        pass


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
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        # `cage hook` is the ONE verb where argparse's usage exit is not merely an
        # error. **Exit 2 is the HOST's "block this tool call" code** on a
        # `PreToolUse`/`Bash` hook — Claude Code's documented meaning, and the other
        # hosts treat any non-zero the same way. So a stale wired event name — the exact
        # thing a rename produces, and the class this repo has already paid for twice —
        # would block EVERY Bash call in the session, and silently, because a blocked
        # tool call reads to the user as the agent refusing.
        #
        # **This guard OUTLIVED cage's own budget block** (USAGE-ONLY, ADR 0011). Cage no
        # longer emits 2 deliberately anywhere — `hookcmd.BLOCK` is gone and every event
        # exits 0 — which makes an *accidental* 2 from argparse strictly worse than
        # before: there is now no path where blocking is intended, so any block is a bug.
        # The literal is the host's constant, not cage's, and is why it is spelled here.
        if tok == "hook" and exc.code == 2:
            _hook_usage_failopen(scan)
            return 0
        raise
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
        # No subcommand → the curated front door. The one-look headline died with
        # `report` in SURFACE-CUT: the overview was a rendered ledger view, and cage
        # no longer ships one. `cage --help` and bare `cage` are now the same surface.
        if getattr(args, "fn", None) is None:
            build_parser().print_help()
            return 0
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
