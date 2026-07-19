"""`cage mcp` — expose the Cage ledger to any agent over MCP (stdlib-only, $0).

A minimal Model Context Protocol server on stdio: newline-delimited JSON-RPC 2.0,
hand-rolled so it adds no dependency. Publishes Cage's read paths — report /
attrib / matrix / budget / roi / why — as MCP *tools*, so an agent (Claude Code,
Codex, Kiro, Copilot) can ask "what did this cost, and what saved me money?" and
answer from its own ledger. Every tool is deterministic and never calls an LLM.

    claude mcp add cage -- cage mcp        # or the equivalent for codex / kiro
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
    {"name": "cage_why",
     "description": "Full provenance for one call id: the call + every receipt against it.",
     "inputSchema": {"type": "object", "required": ["call_id"],
                     "properties": {"call_id": {"type": "string"}}}},
]


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
    elif name == "cage_why":
        cid = args["call_id"]
        text = provenance.render_why(provenance.explain(root, cid), cid)
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
