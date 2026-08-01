---
doc: proposal — the tool integration contract (the paved road)
status: proposed
raised: 2026-08-01 (Arpit: "i want graphify to work and maybe in future more tools")
---

# Proposal — one contract, many tools

**The goal, stated by Arpit:** graphify works end-to-end; the *next* tool doesn't cost
what graphify cost. Today "graphify" appears in **34 of 91 modules** — the receipt
substrate is generic, but the capture side is bespoke. This extracts the paved road.

## What is already generic (do not rebuild)

`savings.record(tool=…)` + `savings/<tool>/` tree · `make_receipt`/`make_savings` ·
the `receiptprice` ladder (`[tools.<tool>] price_at` → task-model → UNPRICED) ·
`[tools] order` + marginal attribution · `roi`/`attrib`/`verdict` by tool ·
`netsaved.by_tool`. **A second tool's *reporting* works today with zero code.**

## What is bespoke to graphify (the contract extracts these)

| piece | today | contract form |
|---|---|---|
| PATH interceptor | `data/shims/graphify`, name hardcoded | a **template** parameterized by tool name + meter-verb filter; `cage setup --intercept <tool>` renders it (the `runshim.py` pattern; WIN-GF's `.cmd` twin renders from the same template) |
| meter verb | `cage data graphify` | `cage data meter <tool> -- <argv>`: run, measure, receipt, pass through — graphify's verb becomes an alias |
| savings model | `graphifymodel.py` (raw_alternative) | per-tool model plugged behind one interface; a tool with no model gets `actual`-only rows, honestly UNPRICED on the counterfactual |
| transcript detection | graphify patterns in `transcript.py` | a small per-tool detection registry (invocation patterns + report-read paths), data not code |
| liveness | `pathshim`/`hookbypass`/`wiringscan` know "graphify" | scan any registered interceptor by name |
| confidence | `GRAPHIFY_RECEIPT_CONFIDENCE` | per-tool in the registry, constants-fallback |

## The proof of genericity: fux is the second tool

`fux/cage_receipt.py` already pushes receipts (zero-dep shim, deliberate `len/4` copy).
Migrating fux onto the contract — registry entry, rendered interceptor, detection
patterns — is the acceptance test. **The contract ships when two tools use it**, not
before (a one-consumer abstraction is speculation; the rule of three, minus one, with
the third named: any MCP-serving tool).

## Sequencing (serves the "graphify works" goal directly)

1. **CI-GF first** — prove the *current* graphify integration in CI (absent/present).
   The contract refactor then has a green harness proving it changed nothing.
2. **WIN-GF phases 1–2** produce the shim behaviour contract — **that document is this
   contract's first artifact**; the `.cmd` twin and the template are the same work.
3. Extract template + registry (pure refactor under CI-GF's harness).
4. fux migrates. Two tools, one road.

## Out of scope

A plugin/entry-point system (stdlib-only law; the registry is data in cage, not
third-party code execution) · metering arbitrary tools with no receipt semantics ·
play 1/2 distribution work (declined 2026-08-01).
