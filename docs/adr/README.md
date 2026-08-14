---
doc: the ADR set — four maintained per-agent records
status: current as of 2026-08-14 · replaces the numeric ADRs 0001–0011
update-rule: ANY capture, routing, or unit change for an agent updates that agent's ADR in the same change, and bumps its DOC-REGISTRY row
---

# ADRs — one record per metered agent

**One record per thing cage meters, plus one for what binds them all and one for the surface it is all read through.**

| # | record | covers |
|---|---|---|
| 0001 | [**ADR-LAWS**](0001_laws.md) | the five cross-cutting laws — read this first |
| 0002 | [**ADR-CLI**](0002_cli.md) | the command surface: every command, every flag, an example each |
| 0003 | [**ADR-CLAUDE**](0003_claude.md) | Claude Code — transcripts, the dedup law, authorship |
| 0004 | [**ADR-COPILOT**](0004_copilot.md) | GitHub Copilot — five stores, cumulative→delta, credits |
| 0005 | [**ADR-KIRO**](0005_kiro.md) | Kiro — the two-store split, machine facts, the absent spine |
| 0006 | [**ADR-CONSUMERS**](0006_consumer.md) | the things cage meters that are not agents — library, custom sources, retired agents |
| 0007 | [**ADR-GRAPHIFY**](0007_graphify.md) | graphify — the interceptor twins and the savings receipt |

Each has **two sections**: **§1 for humans** (one screen, diagrams, no jargon) and
**§2 for agents** (the binding detail — context, decision, consequences, alternatives,
reference, veto). Author from [TEMPLATE.md](TEMPLATE.md).

## Cite them by name, never by number

In prose write **ADR-CLAUDE · ADR-COPILOT · ADR-KIRO · ADR-GRAPHIFY**.

A bare "ADR 0001" is now ambiguous — it meant *team ledger aggregation via `refs/notes`*
for six weeks and there are ~90 live references to the numeric names. The numbers survive
only as filename ordering. **"ADR 0001–0011" always means an
[archived](../../work/archive/adr/README.md) record; a named ADR always means a live one.**

## The five laws

They live in **[ADR-LAWS](0001_laws.md)**, in full, each with its ratification and its
veto condition: **pull-only · one sink · append-only · counts-never-content ·
usage-never-cost**. They are stated **there and nowhere else** — a per-agent record that
restates a law creates a second copy that can drift, and drift here is invisible until it
produces a wrong number.

The principle underneath them all:

> **Cage can never be more precise than its source.** Where a source has no dimension,
> cage renders `—` **with the reason**, never a `0`, and never invents the split.

## Reading order

**[ADR-LAWS](0001_laws.md) §1 first** — five minutes, and every other record assumes it.
Then **§1** of the agent you care about. Read a **§2** only when changing that agent's
capture. Adding a new metered thing? Check it against ADR-LAWS §2 *before* writing its
record — several plausible designs are ruled out at that gate rather than after
implementation.
