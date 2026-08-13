"""L2 — MCP: the two product-question tools, the one write tool, and the refusals.

`verdict` and `compare` answer *"is this tool worth keeping"*, and both routinely
**decline**. This file's premise is that the declining is the valuable part: an agent
that receives an empty result reads it as **zero**, which is the one thing a refusal
never means. So every refusal is asserted **byte-identically against the CLI's own
rendering** — not "contains INSUFFICIENT DATA", but *the same string a human would
read*, so no summarizing layer can ever grow between the composer and the agent.

The write half is one tool, deliberately. `cage_task_outcome` exists because every
starved surface (`compare`/`estimate`/`calibration`/net) is starved for the same
reason — nobody closes tasks — and it is pinned here as the **only** mutation cage
exposes, so a later reader cannot add a second by analogy.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cage import (agents, cfgio, clicmds, compare, ledger, mcpserver, policy, quality,
                  roi, schema, tasks, verdict)
from cage.constants import MIN_COMPARE_N

_MODEL = dict(route="chat", provider="anthropic", model="claude-opus-4-8",
              agent="claude-code")


@pytest.fixture
def mcp(proj, monkeypatch):
    """`mcpserver` rooted at an isolated project, with capture-on-read off (the suite
    pins it off; this makes the read a pure function of the seeded ledger)."""
    monkeypatch.setattr(mcpserver, "_root", lambda: proj)
    monkeypatch.chdir(proj)
    return proj


def _call(root, task, ts) -> str:
    row = schema.make_call(tokens_in=1_000, tokens_out=100, task=task,
                           session=f"s-{task}", ts=ts, **_MODEL)
    ledger.append_row(root, "calls", row)
    return row["id"]


def _receipt(root, tool, saved, ts, task="", call="", tool_cost=0.0):
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool=tool, raw_alternative=saved + 100, actual=100, task=task, call=call, ts=ts,
        meta={"tool_cost_usd": tool_cost} if tool_cost else {}))


def _seed_gross_only(root):
    """A tool whose savings ARE priceable but whose cost of use is not: each receipt's
    task has a call (so the price ladder resolves a dominant model), but the call sits
    five hours away — far outside the +/-120s attribution window — so no in-window call
    exists and the net is *uncovered*. That is exactly the `SAVING (GROSS)` shape."""
    for i in range(8):
        _call(root, f"t-{i}", f"2026-06-1{i}T10:00:00Z")
        _receipt(root, "graphify", 10_000, f"2026-06-1{i}T15:00:00Z", task=f"t-{i}")


def _seed_costing(root):
    for i in range(8):
        cid = _call(root, f"c-{i}", f"2026-06-1{i}T10:00:00Z")
        _receipt(root, "pricey-ml", 1_000, f"2026-06-1{i}T10:00:00Z",
                 task=f"c-{i}", call=cid, tool_cost=0.5)


def _text(name, args=None):
    return mcpserver._call(name, args or {})[0]


# ── the tools exist, and the read/write split is explicit ─────────────────────

def test_tools_list_carries_verdict_compare_and_the_one_write_tool(mcp):
    names = {t["name"] for t in mcpserver.TOOLS}
    assert {"cage_report", "cage_attrib", "cage_matrix", "cage_budget", "cage_roi",
            "cage_adoption", "cage_why", "cage_verdict", "cage_compare",
            "cage_task_outcome"} == names
    listed = mcpserver._handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert {t["name"] for t in listed["result"]["tools"]} == names


def test_exactly_one_write_tool_in_the_whole_ladder(mcp):
    """The ladder's read/write asymmetry is the design. A second write tool added by
    analogy would need this line changed — which is the point of asserting it."""
    assert mcpserver.WRITE_TOOLS == frozenset({"cage_task_outcome"})
    assert mcpserver.WRITE_TOOLS < {t["name"] for t in mcpserver.TOOLS}
    doc = mcpserver.__doc__ or ""
    assert "ONLY write tool" in doc  # and it says so where the next reader will look


def test_no_read_tool_writes_to_the_ledger(mcp):
    _seed_gross_only(mcp)
    _close(mcp, "t-0")
    from cage import paths
    fp = paths.Footprint(mcp)
    before = {k: b"".join(p.read_bytes() for p in fp.shards(k))
              for k in ("calls", "receipts", "tasks")}
    for t in mcpserver.TOOLS:
        if t["name"] in mcpserver.WRITE_TOOLS:
            continue
        args = {"tool": "graphify"} if t["name"] == "cage_verdict" else {}
        if t["name"] == "cage_why":
            args = {"call_id": "nope"}
        mcpserver._call(t["name"], args)
    after = {k: b"".join(p.read_bytes() for p in fp.shards(k))
             for k in ("calls", "receipts", "tasks")}
    assert after == before


def _close(root, tid, ts="2026-06-10T10:00:00Z", label=""):
    tasks.record(root, tid, outcome="ok", ts=ts, snapshot=False,
                 **({"label": label} if label else {}))


# ── the refusals cross the boundary VERBATIM ──────────────────────────────────

def test_verdict_insufficient_data_reaches_the_agent_verbatim(mcp):
    """No receipts for the tool ⇒ cage refuses. The agent must get the refusal, not an
    empty string it will read as 'nothing was saved'."""
    text = _text("cage_verdict", {"tool": "never-ran"})
    assert "INSUFFICIENT DATA" in text
    assert text == verdict.render_verdict(
        verdict.compose(mcp, policy.load(None), "never-ran"))
    assert text.strip(), "a refusal must never arrive as silence"


def test_verdict_saving_gross_reaches_the_agent_verbatim(mcp):
    """Savings computable, cost-of-use not ⇒ `SAVING (GROSS)`, never a bare SAVING.
    The qualifier is the whole finding (work/regression/2026-08-01-finding-saved-is-gross.md);
    an MCP wrapper that dropped it would re-tell the lie the CLI was fixed to stop."""
    _seed_gross_only(mcp)
    d = verdict.compose(mcp, policy.load(None), "graphify")
    assert d["gross_of_use"] is True and d["verdict"] == "SAVING (GROSS)"
    text = _text("cage_verdict", {"tool": "graphify"})
    assert "SAVING (GROSS)" in text and "GROSS" in text
    assert text == verdict.render_verdict(d)


def test_verdict_costing_is_still_asserted_bare(mcp):
    """The asymmetry that makes the refusal principled rather than timid: the omitted
    term is >= 0, so only the *positive* side can be wiped out by it."""
    _seed_costing(mcp)
    text = _text("cage_verdict", {"tool": "pricey-ml"})
    assert "COSTING" in text and "COSTING (GROSS)" not in text
    assert text == verdict.render_verdict(
        verdict.compose(mcp, policy.load(None), "pricey-ml"))


def test_compare_min_n_block_reaches_the_agent_verbatim(mcp):
    """A group below MIN_COMPARE_N is BLOCKED and says its own n. An agent that got
    the numbers without the block would compare two medians drawn from one task each."""
    for i in range(2):                                  # 2 < MIN_COMPARE_N
        cid = _call(mcp, f"g-{i}", f"2026-06-1{i}T10:00:00Z")
        _receipt(mcp, "graphify", 5_000, f"2026-06-1{i}T10:00:00Z", task=f"g-{i}", call=cid)
        _close(mcp, f"g-{i}", f"2026-06-1{i}T11:00:00Z")
    d = compare.summarize(mcp, policy.load(None), by=("stack",))
    blocked = [g for g in d["groups"] if g.get("reason")]
    assert blocked and all(str(MIN_COMPARE_N) in g["reason"] for g in blocked)
    text = _text("cage_compare")
    assert text == compare.render_compare(d)
    assert str(MIN_COMPARE_N) in text and "insufficient data" in text


def test_compare_csv_keeps_the_blocked_group_as_a_row(mcp):
    """CSV never gates: a blocked group keeps its row (with its reason) rather than
    vanishing into a table that reads complete."""
    for i in range(2):
        cid = _call(mcp, f"g-{i}", f"2026-06-1{i}T10:00:00Z")
        _receipt(mcp, "graphify", 5_000, f"2026-06-1{i}T10:00:00Z", task=f"g-{i}", call=cid)
        _close(mcp, f"g-{i}", f"2026-06-1{i}T11:00:00Z")
    csv_text = _text("cage_compare", {"format": "csv"})
    assert csv_text == compare.render_csv(compare.summarize(mcp, policy.load(None),
                                                            by=("stack",)))
    assert "insufficient data" in csv_text


def test_compare_rejects_an_unknown_by_key_with_the_choices(mcp):
    reply = mcpserver._handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                               "params": {"name": "cage_compare",
                                          "arguments": {"by": "author"}}})
    assert reply["result"]["isError"] is True
    assert "stack, scope, label" in reply["result"]["content"][0]["text"]


def test_verdict_without_a_tool_name_explains_instead_of_KeyError(mcp):
    reply = mcpserver._handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                               "params": {"name": "cage_verdict", "arguments": {}}})
    assert reply["result"]["isError"] is True
    assert "cage_roi" in reply["result"]["content"][0]["text"]  # names the way forward


# ── MCP and the CLI cannot disagree ───────────────────────────────────────────

def test_mcp_output_is_byte_identical_to_the_cli(mcp, capsys):
    """One composer, one renderer, two transports. If these ever diverge, one surface
    is summarizing — the failure this layer exists to prevent."""
    _seed_gross_only(mcp)
    _close(mcp, "t-0")

    assert clicmds.cmd_verdict(SimpleNamespace(
        tool="graphify", since=None, json=False, csv=None, no_import=True)) == 0
    assert capsys.readouterr().out.rstrip("\n") == _text(
        "cage_verdict", {"tool": "graphify"}).rstrip("\n")

    assert clicmds.cmd_compare(SimpleNamespace(
        by="stack", scope=None, label=None, json=False, csv=None, no_import=True)) == 0
    assert capsys.readouterr().out.rstrip("\n") == _text("cage_compare").rstrip("\n")


# ── the one write tool ────────────────────────────────────────────────────────

def test_task_outcome_closes_a_task_through_the_cli_path(mcp):
    _call(mcp, "fix-bug", "2026-06-10T10:00:00Z")
    text = _text("cage_task_outcome", {"task": "fix-bug", "label": "bugfix"})
    assert "fix-bug" in text and "ok" in text and "bugfix" in text
    row = tasks.read(mcp)["fix-bug"]
    assert row["outcome"] == "ok" and row["label"] == "bugfix"
    assert quality.summarize(mcp, pol=policy.load(None))  # the quality view sees it


def test_task_outcome_and_the_cli_verb_share_one_implementation(mcp, capsys):
    """Same guard, same append, same wording — `clicmds.close_task` is the one path."""
    _call(mcp, "via-cli", "2026-06-10T10:00:00Z")
    assert clicmds.cmd_outcome(SimpleNamespace(task="via-cli", redo=False,
                                               label="shared")) == 0
    cli_line = capsys.readouterr().out.strip()
    _call(mcp, "via-mcp", "2026-06-10T10:00:00Z")
    mcp_line = _text("cage_task_outcome", {"task": "via-mcp", "label": "shared"}).strip()
    assert cli_line.replace("via-cli", "X") == mcp_line.replace("via-mcp", "X")


def test_task_outcome_label_guard_refuses_free_text(mcp):
    """A label is a grouping key, never a message — the PII guard is the CLI's, reached
    through the shared path, so it cannot be laxer on the agent-facing surface."""
    _call(mcp, "t", "2026-06-10T10:00:00Z")
    for bad in ("fixed the login bug", "src/auth/login.py", "a" * 40):
        reply = mcpserver._handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                   "params": {"name": "cage_task_outcome",
                                              "arguments": {"task": "t", "label": bad}}})
        assert reply["result"]["isError"] is True
        assert "one short token" in reply["result"]["content"][0]["text"]
    assert tasks.read(mcp).get("t", {}).get("outcome") in (None, "")  # nothing written


def test_task_outcome_is_append_only_and_never_rewrites_history(mcp):
    """Re-closing supersedes by last-write-wins; the earlier row stays on disk. The
    ledger's only mutation is append — an agent-driven write may not change that."""
    from cage import paths
    _call(mcp, "twice", "2026-06-10T10:00:00Z")
    _text("cage_task_outcome", {"task": "twice"})
    first = b"".join(p.read_bytes() for p in paths.Footprint(mcp).shards("tasks"))
    _text("cage_task_outcome", {"task": "twice", "redo": True})
    second = b"".join(p.read_bytes() for p in paths.Footprint(mcp).shards("tasks"))
    assert second.startswith(first), "an earlier task row was rewritten, not superseded"
    assert len(second) > len(first)
    assert tasks.read(mcp)["twice"]["outcome"] == "redo"   # last write wins on read


def test_task_outcome_without_a_task_explains(mcp):
    reply = mcpserver._handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                               "params": {"name": "cage_task_outcome", "arguments": {}}})
    assert reply["result"]["isError"] is True
    assert "task" in reply["result"]["content"][0]["text"]


# ── parity: all three agents resolve the server, from committed files ─────────

def test_every_agent_resolves_the_mcp_server_from_a_committed_file(proj, monkeypatch):
    from cage import kirowire, runshim
    monkeypatch.setattr("cage.paths.cage_bin", lambda: "/machine/specific/cage")
    agents.install(proj)
    claude = cfgio.load_json(proj / ".mcp.json")["mcpServers"]["cage"]
    copilot = cfgio.load_json(proj / ".vscode" / "mcp.json")["servers"]["cage"]
    kiro = cfgio.load_json(proj / ".kiro" / "settings" / "mcp.json")["mcpServers"]["cage"]
    assert claude["command"] == f"${{CLAUDE_PROJECT_DIR:-.}}/{runshim.SHIM_REL}"
    assert copilot["command"] == f"${{workspaceFolder}}/{runshim.SHIM_REL}"
    # Kiro resolves neither a relative path nor a variable — so it carries no path.
    assert kiro == kirowire.PATH_FREE
    assert kiro["command"] == "python3" and kiro["args"] == ["-m", "cage", "mcp"]
    for rel in (".mcp.json", ".vscode/mcp.json", ".kiro/settings/mcp.json"):
        assert "/machine/specific/cage" not in (proj / rel).read_text(encoding="utf-8")


def test_kiro_mcp_is_byte_identical_across_machines(proj, tmp_path, monkeypatch):
    """Two teammates, two different cage installs, one committed file — identical
    bytes, or `cage setup` churns a diff on every commit."""
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setattr("cage.paths.cage_bin", lambda: "/home/a/.local/bin/cage")
    agents.install(proj)
    monkeypatch.setattr("cage.paths.cage_bin", lambda: "C:\\tools\\cage.exe")
    agents.install(other)
    rel = ".kiro/settings/mcp.json"
    assert (proj / rel).read_bytes() == (other / rel).read_bytes()


def test_reinstall_migrates_the_legacy_absolute_kiro_entry(proj):
    """The old form is on real machines and in real gitignores. Setup heals it and
    *says* it did — a silent migration is how you get a diff nobody understands."""
    from cage import kirowire
    mcp = proj / ".kiro" / "settings" / "mcp.json"
    mcp.parent.mkdir(parents=True)
    mcp.write_text(json.dumps({"mcpServers": {
        "cage": {"command": "/opt/cage/bin/cage", "args": ["mcp"]},
        "other": {"command": "/opt/other"},          # foreign entry: never touched
    }}), encoding="utf-8")
    out = kirowire.install(proj)
    data = cfgio.load_json(mcp)["mcpServers"]
    assert data["cage"] == kirowire.PATH_FREE
    assert data["other"] == {"command": "/opt/other"}
    assert "migrated" in out and "path-free" in out["migrated"]
    assert "migrated" not in kirowire.install(proj)   # second run: nothing to migrate


def test_kiro_mcp_doctor_check_probes_the_resolved_interpreter(proj):
    """The price of going path-free, named rather than assumed: doctor asks the
    interpreter Kiro will resolve whether it can actually import cage."""
    from cage import doctorcmd
    agents.install(proj)
    rows = {c["name"]: c for c in doctorcmd.run(proj)["checks"]}
    assert "kiro-mcp" in rows
    detail = rows["kiro-mcp"]["detail"]
    assert rows["kiro-mcp"]["level"] in {"ok", "warn", "fail"}
    # Whatever the verdict, it names the interpreter — never a bare pass/fail.
    assert "python3" in detail or "py" in detail
