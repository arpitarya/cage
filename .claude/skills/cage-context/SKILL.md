---
name: cage-context
description: Read before answering what something cost, whether a tool is worth keeping, or whether spend is within budget.
---

# Cage — what it is and what to ask it

This project meters its LLM traffic with **cage** — a deterministic attribution ledger.
It costs nothing to query: every view is arithmetic over an append-only log, with no
model call on the read path.

## The one rule when you use it

**Never produce a cage number yourself. Run cage and quote what it says.**

- Copy **method tags** through verbatim. `measured` is an invoice. `modeled` and
  `estimated` are reconstructions. They are not interchangeable, and dropping the tag
  turns a reconstruction into a claim.
- **Relay refusals; never smooth them.** `INSUFFICIENT DATA` means cage declines to
  answer — report that, do not substitute zero or "no savings". `SAVING (GROSS)` means
  the cost of *using* the tool is excluded and unknown, so it is not a proven saving.
  A blocked comparison means too few closed tasks, not "no difference".
- Do no arithmetic on cage's output. If two numbers need combining, there is a cage
  view that already does it correctly.

## What to run

| question | command |
|---|---|
| what has this cost? | `cage report --by agent --since 7d` |
| which tool actually saved anything? | `cage insights attrib` |
| is tool X worth keeping? | `cage insights verdict <tool>` |
| did the stack with X really cost less? | `cage insights compare` |
| are we over budget? | `cage insights budget` |
| do the agents actually use the tools? | `cage insights adoption` |
| why is this number what it is? | `cage query "how is attribution calculated"` |

If MCP is wired, the same views are available as tools (`cage_report`, `cage_attrib`,
`cage_verdict`, `cage_compare`, …) and return the same text — quote it the same way.

## Close your tasks

`compare`, `estimate` and `calibration` can say nothing about work nobody closed. When
a unit of work finishes, close it: `cage task outcome <task>` (or the `cage_task_outcome`
MCP tool, the only write tool cage exposes). One short label, never a sentence or a path.

## What cage never has

Prompt text. The ledger carries token *counts* only, so no cage output can leak what
anyone wrote — and no cage command will produce it for you if asked.
