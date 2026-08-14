---
doc: the ADR set — four maintained per-agent records
status: current as of 2026-08-14 · replaces the numeric ADRs 0001–0011
update-rule: ANY capture, routing, or unit change for an agent updates that agent's ADR in the same change, and bumps its DOC-REGISTRY row
---

# ADRs — one record per metered agent

**The set is four, and it stays four.** One record per thing cage meters:

| # | record | covers |
|---|---|---|
| 0001 | [**ADR-CLAUDE**](0001_claude.md) | Claude Code — transcripts, the dedup law, authorship |
| 0002 | [**ADR-COPILOT**](0002_copilot.md) | GitHub Copilot — five stores, cumulative→delta, credits |
| 0003 | [**ADR-KIRO**](0003_kiro.md) | Kiro — the two-store split, machine facts, the absent spine |
| 0004 | [**ADR-GRAPHIFY**](0004_graphify.md) | graphify — the interceptor twins and the savings receipt |

Each has **two sections**: **§1 for humans** (one screen, diagrams, no jargon) and
**§2 for agents** (the binding detail — context, decision, consequences, alternatives,
reference, veto). Author from [TEMPLATE.md](TEMPLATE.md).

## Cite them by name, never by number

In prose write **ADR-CLAUDE · ADR-COPILOT · ADR-KIRO · ADR-GRAPHIFY**.

A bare "ADR 0001" is now ambiguous — it meant *team ledger aggregation via `refs/notes`*
for six weeks and there are ~90 live references to the numeric names. The numbers survive
only as filename ordering. **"ADR 0001–0011" always means an
[archived](../../work/archive/adr/README.md) record; a named ADR always means a live one.**

## The five laws that bind all four

Stated once here so no ADR restates them and none can quietly drift from them. Each is
ratified in an [archived](../../work/archive/adr/README.md) record; the citation is the
proof, not decoration.

| law | means | ratified in |
|---|---|---|
| **Pull-only** | Capture is `cage import` + capture-on-read. No hook, no OS scheduler, no network, `$0`. MCP is the only surface cage wires. | [0003](../../work/archive/adr/0003-hookless-capture-pull-only-mcp-only-wiring.md) |
| **One sink** | `--ledger`/`CAGE_BASE` → nearest project `.cage/` → global `~/.cage`. Never a double-write. `project` is a derived view, never a capture scope. | [0002](../../work/archive/adr/0002-universal-capture-global-ledger-explicit-import-export.md) |
| **Append-only** | No ledger row is ever mutated. A cumulative source is reconciled with delta rows; a different *shape* of number gets its own row kind. | [0004](../../work/archive/adr/0004-append-only-delta-rows-and-separate-by-schema.md) |
| **Counts, never content** | Prompts, responses, diffs and command output may be read **transiently**; only counts, hashes and ids persist. Not even a line hash. | [0008](../../work/archive/adr/0008-line-match-authorship-counts-persisted-content-transient.md) · [0009](../../work/archive/adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md) |
| **Usage, never cost** | Two units — tokens and credits — both **recorded counts**. No rate card, no price table, and **no conversion between units in any direction**. | [0011](../../work/archive/adr/0011-cage-measures-usage-not-cost.md) |

And the governing principle underneath all five:

> **Cage can never be more precise than its source.** Where a source has no dimension,
> cage renders `—` **with the reason**, never a `0`, and never invents the split.

## Reading order

Start at **§1** of the agent you care about. Read **§2** only when changing that agent's
capture. If you are adding a *fifth* agent, read this file and
[TEMPLATE.md](TEMPLATE.md) first — the five laws above bind it before you write a line.
