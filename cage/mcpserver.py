"""`cage mcp` — expose the Cage ledger to any agent over MCP (stdlib-only, $0).

A minimal Model Context Protocol server on stdio: newline-delimited JSON-RPC 2.0,
hand-rolled so it adds no dependency. Publishes Cage's read path — **`why`**, full
provenance for one call id — as an MCP *tool*, so an agent (Claude Code, Kiro,
Copilot) can trace a call to every receipt filed against it from its own ledger. The
read tool is deterministic and never calls an LLM.

    claude mcp add cage -- cage mcp        # or the equivalent for copilot / kiro

**The surface is now two tools, and that is a floor, not a trend.** It was nine, then
five (USAGE-ONLY took `matrix`/`budget`/`roi`/`verdict` with the money subsystem, ADR
0011), and SURFACE-CUT took `report`/`attrib`/`adoption`/`compare` with the ledger
rollup and the task-comparison family. What survives is the one read no other surface
answers and the one write the whole ladder depends on.

**Whatever a tool returns crosses this boundary verbatim.** A refusal or a caveat is
relayed unsmoothed, because a tool that returns silence where the CLI would have
explained itself is worse than no tool — an agent reads an empty result as *zero*,
which is the one thing it never means. Nothing here summarizes, thresholds, or
re-derives; each tool renders the same string the CLI prints, from the same composer.

**`cage_task_outcome` is the ONLY write tool in the entire ladder** — L0…L3 included.
Do **not** add a second write tool by analogy with it; the read/write asymmetry here is
the design, not an oversight.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from cage import __version__, paths, policy, provenance

PROTOCOL = "2024-11-05"

TOOLS = [
    {"name": "cage_why",
     "description": "Full provenance for one call id: the call + every receipt against it.",
     "inputSchema": {"type": "object", "required": ["call_id"],
                     "properties": {"call_id": {"type": "string"}}}},
    # ── the one write tool in the whole ladder — see the module docstring ──────
    {"name": "cage_task_outcome",
     "description": "Close a task as ok or redo (optionally with a one-token label). "
                    "THE ONLY WRITE TOOL CAGE EXPOSES. Append-only: it never rewrites "
                    "history, and re-closing a task supersedes rather than edits. Call "
                    "it when a unit of work finishes — a task nobody closes is invisible "
                    "to every task-grain view cage could ever build.",
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


def _call(name: str, args: dict) -> tuple[str, dict | None]:
    root = _root()
    # Capture-on-read (capture-architecture Phase 1): the MCP read tools are the
    # agent-facing surface and the de-facto real-time path — an agent asking cage about
    # spend mid-session triggers a fresh sweep first. The summary rides back as a
    # STRUCTURED field (see `_handle`), never stdout — stray stdout would corrupt the
    # JSON-RPC protocol. Throttled + gated + fail-open inside `ensure_captured`.
    from cage import importcmd
    summary = importcmd.ensure_captured(root)
    if name == "cage_why":
        cid = args["call_id"]
        text = provenance.render_why(provenance.explain(root, cid), cid)
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
