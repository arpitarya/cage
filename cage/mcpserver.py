"""`cage mcp` — expose the Cage ledger to any agent over MCP (stdlib-only, $0).

A minimal Model Context Protocol server on stdio: newline-delimited JSON-RPC 2.0,
hand-rolled so it adds no dependency. Publishes Cage's read paths — report /
attrib / matrix / budget / roi / adoption / why / **verdict / compare** — as MCP
*tools*, so an agent (Claude Code, Kiro, Copilot) can ask "what did this cost, and
what saved me money?" and answer from its own ledger. Every read tool is
deterministic and never calls an LLM.

    claude mcp add cage -- cage mcp        # or the equivalent for copilot / kiro

**The refusals are the point (L2 of the agent-surface ladder).** `verdict` and
`compare` are the two views that answer *"is this tool worth keeping"*, and both
routinely decline to answer: `INSUFFICIENT DATA` when a tool has no receipts,
`SAVING (GROSS)` when no cost-of-use figure exists, the `MIN_COMPARE_N` block when a
group is too thin. Those texts cross this boundary **verbatim**, because a tool that
returns silence where the CLI would have explained itself is worse than no tool — an
agent reads an empty result as *zero*, which is the one thing it never means. Nothing
here summarizes, thresholds, or re-derives; each tool renders the same string the CLI
prints, from the same composer.

**`cage_task_outcome` is the ONLY write tool in the entire ladder** — L0…L3 included.
It exists because every starved surface (`compare`, `estimate`, `calibration`, the net
saving) is starved for one reason: nobody closes tasks. Do **not** add a second write
tool by analogy with it; the read/write asymmetry here is the design, not an oversight.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from cage import (__version__, attribution, budget, matrix, paths, policy,
                  provenance, report, roi)

PROTOCOL = "2024-11-05"

# `format: "csv"` on the view tools returns the same CSV the CLI's --csv emits
# (one shared data structure per view feeds both renderers), so an extension-hosted
# agent with no shell can still hand the user a spreadsheet-ready artifact.
_FORMAT = {"type": "string", "enum": ["text", "csv"], "default": "text",
           "description": "text = the rendered table · csv = the flat reporting "
                          "CSV (method tags stay columns)"}

TOOLS = [
    {"name": "cage_report",
     "description": "Ledger rollup: LLM spend by route / model / day / agent.",
     "inputSchema": {"type": "object", "properties": {
         "by": {"type": "string", "default": "route"}, "since": {"type": "string"},
         "format": _FORMAT}}},
    {"name": "cage_attrib",
     "description": "Per-tool marginal token/$ savings for a task (the attribution table).",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"},
                                                      "format": _FORMAT}}},
    {"name": "cage_matrix",
     "description": "Counterfactual permutation table — what every tool combination would cost.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}}}},
    {"name": "cage_budget",
     "description": "Session/day spend vs the policy ceilings.",
     "inputSchema": {"type": "object", "properties": {"session": {"type": "string"}}}},
    {"name": "cage_roi",
     "description": "Saved $ per tool vs its own cost + added latency.",
     "inputSchema": {"type": "object", "properties": {"since": {"type": "string"},
                                                      "format": _FORMAT}}},
    {"name": "cage_adoption",
     "description": "Do the agents actually invoke the wired tools? Invocation counts + "
                    "outcomes, and per-agent attribution where it is derivable. Counts "
                    "only — never priced.",
     "inputSchema": {"type": "object", "properties": {"since": {"type": "string"},
                                                      "format": _FORMAT}}},
    {"name": "cage_why",
     "description": "Full provenance for one call id: the call + every receipt against it.",
     "inputSchema": {"type": "object", "required": ["call_id"],
                     "properties": {"call_id": {"type": "string"}}}},
    {"name": "cage_verdict",
     "description": "Is one tool worth keeping? The one-line answer, composed from "
                    "attrib/roi/regression/quality — it computes no new statistic. "
                    "READ THE VERDICT WORD LITERALLY: 'SAVING (GROSS)' means the cost "
                    "of USING the tool is excluded and unknown, so it is NOT a proven "
                    "saving; 'INSUFFICIENT DATA' means cage declines to answer and must "
                    "be relayed as a refusal, never as zero or as 'no savings'.",
     "inputSchema": {"type": "object", "required": ["tool"],
                     "properties": {"tool": {"type": "string",
                                             "description": "the tool name as it appears "
                                                            "in its savings receipts"},
                                    "since": {"type": "string"}}}},
    {"name": "cage_compare",
     "description": "Observational cost comparison between tool stacks over closed "
                    "tasks — the measured counterpart to verdict's modeled answer. "
                    "Group totals are measured; the delta is always 'estimated' and "
                    "carries an observational caveat (the groups were not randomized). "
                    "A group with too few tasks is BLOCKED with its own n — relay that "
                    "refusal verbatim rather than comparing the numbers anyway.",
     "inputSchema": {"type": "object", "properties": {
         "by": {"type": "string", "default": "stack",
                "description": "comma-separated: stack, scope, label"},
         "scope": {"type": "string"}, "label": {"type": "string"}, "format": _FORMAT}}},
    # ── the one write tool in the whole ladder — see the module docstring ──────
    {"name": "cage_task_outcome",
     "description": "Close a task as ok or redo (optionally with a one-token label). "
                    "THE ONLY WRITE TOOL CAGE EXPOSES. Append-only: it never rewrites "
                    "history, and re-closing a task supersedes rather than edits. Call "
                    "it when a unit of work finishes — compare/estimate/calibration can "
                    "say nothing at all about tasks nobody closed.",
     "inputSchema": {"type": "object", "required": ["task"], "properties": {
         "task": {"type": "string", "description": "the task id used when metering"},
         "redo": {"type": "boolean", "default": False,
                  "description": "true = the work had to be redone (not a success)"},
         "label": {"type": "string",
                   "description": "optional grouping key — ONE short token "
                                  "(letters/digits/._-, <=32 chars). Never a path, a "
                                  "sentence, or a commit message."}}}},
]

# Tool names that mutate. Everything not listed is a pure read — the split is explicit
# so "is this server safe to auto-approve" is answerable by reading one line.
WRITE_TOOLS = frozenset({"cage_task_outcome"})


def _root() -> Path:
    # Read the *active* ledger like the CLI (`cliutil.ledger_root`): a no-project
    # MCP server answers from the global ~/.cage, not an empty cwd footprint.
    return paths.resolve_root()


def _pol(root: Path) -> dict:
    return policy.load(paths.Footprint(root).policy)


def _latest_task(root: Path) -> str | None:
    from cage import ledger
    tasks = [c.get("task") for c in ledger.calls(root) if c.get("task")]
    return tasks[-1] if tasks else None


def _call(name: str, args: dict) -> tuple[str, dict | None]:
    root = _root()
    # Capture-on-read (capture-architecture Phase 1): the MCP read tools are the
    # agent-facing surface and the de-facto real-time path — an agent asking cage about
    # spend mid-session triggers a fresh sweep first. The summary rides back as a
    # STRUCTURED field (see `_handle`), never stdout — stray stdout would corrupt the
    # JSON-RPC protocol. Throttled + gated + fail-open inside `ensure_captured`.
    from cage import importcmd
    summary = importcmd.ensure_captured(root)
    as_csv = args.get("format") == "csv"  # same structure feeds both renderers
    if name == "cage_report":
        rep = report.summarize(root, _pol(root), dim=args.get("by", "route"),
                               since=args.get("since"))
        text = report.render_csv(rep) if as_csv else report.render_report(rep)
    elif name == "cage_attrib":
        task = args.get("task") or _latest_task(root)
        data = attribution.attribute(root, task, _pol(root))
        text = attribution.render_csv(data) if as_csv else attribution.render_attrib(data)
    elif name == "cage_matrix":
        task = args.get("task") or _latest_task(root)
        text = matrix.render_matrix(matrix.matrix(root, task, _pol(root)))
    elif name == "cage_budget":
        text = budget.render_budget(budget.check(root, _pol(root), session=args.get("session")))
    elif name == "cage_roi":
        data = roi.by_tool(root, _pol(root), since=args.get("since"))
        text = roi.render_csv(data) if as_csv else roi.render_roi(data)
    elif name == "cage_adoption":
        from cage import adoption
        data = adoption.summarize(root, since=args.get("since"))
        text = adoption.render_csv(data) if as_csv else adoption.render_adoption(data)
    elif name == "cage_why":
        cid = args["call_id"]
        text = provenance.render_why(provenance.explain(root, cid), cid)
    elif name == "cage_verdict":
        from cage import verdict
        if not args.get("tool"):
            raise ValueError("cage_verdict needs a 'tool' name (as it appears in its "
                             "savings receipts) — try cage_roi to list the tools on file")
        # `verdict.compose` is a pure composer and `render_verdict` is the CLI's own
        # renderer — so INSUFFICIENT DATA / SAVING (GROSS) / the ⚠ gross note reach the
        # agent as the exact text a human would read. No summarizing layer here, ever.
        text = verdict.render_verdict(
            verdict.compose(root, _pol(root), args["tool"], since=args.get("since")))
    elif name == "cage_compare":
        from cage import compare
        by = tuple(k.strip() for k in (args.get("by") or "stack").split(",") if k.strip())
        bad = [k for k in by if k not in ("stack", "scope", "label")]
        if bad:
            raise ValueError(f"unknown by key(s) {bad}; choose from stack, scope, label")
        data = compare.summarize(root, _pol(root), by=by, scope=args.get("scope"),
                                 label=args.get("label"))
        # The MIN_COMPARE_N block is *inside* this structure (per-group `reason`), so it
        # survives into both renderings — CSV included, where a blocked group keeps its
        # row rather than vanishing into an apparently-complete table.
        text = compare.render_csv(data) if as_csv else compare.render_compare(data)
    elif name == "cage_task_outcome":
        # The ONLY write tool cage exposes (module docstring). It goes through the same
        # `clicmds.close_task` the CLI verb uses — same label guard, same append-only
        # write, same confirmation wording — so the two surfaces cannot diverge.
        from cage import clicmds
        if not args.get("task"):
            raise ValueError("cage_task_outcome needs the 'task' id the work was "
                             "metered under — closing an unnamed task is not possible")
        text = clicmds.close_task(root, args["task"], redo=bool(args.get("redo")),
                                  label=args.get("label") or "")
    else:
        raise ValueError(f"unknown tool '{name}'")
    return text, summary


def _handle(msg: dict) -> dict | None:
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        return _ok(mid, {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                         "serverInfo": {"name": "cage", "version": __version__}})
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return _ok(mid, {})
    if method == "tools/list":
        return _ok(mid, {"tools": TOOLS})
    if method == "tools/call":
        try:
            text, capture = _call(params.get("name", ""), params.get("arguments") or {})
            result = {"content": [{"type": "text", "text": text}]}
            if capture:  # capture-on-read proof-of-life — a structured field, not stdout
                result["structuredContent"] = {"capture": capture}
            return _ok(mid, result)
        except Exception as exc:  # noqa: BLE001 — surface as a tool error, not a crash
            return _ok(mid, {"content": [{"type": "text", "text": f"error: {exc}"}],
                             "isError": True})
    if mid is not None:
        return _err(mid, -32601, f"method not found: {method}")
    return None


def _ok(mid, result) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid, code, message) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def serve(stdin=None, stdout=None) -> int:
    rd, wr = stdin or sys.stdin, stdout or sys.stdout
    for line in rd:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = _handle(msg)
        if reply is not None:
            wr.write(json.dumps(reply, ensure_ascii=False) + "\n")
            wr.flush()
    return 0
