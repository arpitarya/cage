---
item: KIRO-MCP-FIELD
lane: your hands
status: open · five minutes, binary answer
raised: 2026-08
---

# KIRO-MCP-FIELD — does the path-free MCP entry start on a real Kiro?

**One question, one answer, five minutes** — and the wiring is already committed and
shipping to users.

Kiro resolves neither the shim nor a workspace variable (it spawns MCP servers from its
install dir), so the committed entry is path-free: `python3 -m cage mcp`. The trade is
named, not buried — it depends on *which* `python3` resolves.

Commands: [FIELD-RUNBOOK §2](../FIELD-RUNBOOK.md).

## The rule that makes this item worth having

**If it does not start: REPORT IT.** Do **not** fall back to a gitignored absolute path —
that is precisely the failure this item exists to prevent. On Windows the documented
answer is `cage setup --python-launcher` (the `py -3` form), never a hand-edited path.

A venv miss is otherwise a *silent* no-MCP, which is the F1 failure class one layer up;
doctor's `kiro-mcp` check asks that interpreter to `import cage` for exactly this reason.
