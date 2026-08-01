---
status: proposed
date: 2026-07-28
author: Claude Code (prices-toml cycle)
---

# Proposed CLAUDE.md edits — model prices split into `prices.toml`

**Propose, don't apply** (per the prompt): these are Must-Know / architecture-bullet
changes to CLAUDE.md that follow from the prices split shipping. Arpit accepts or
overrides before they land. Sibling to [claude-md-sources-authority.md](claude-md-sources-authority.md);
both are parked, neither overwrites the other.

The governing rule this whole change turns on: **vendor facts move, routing decisions
stay.**

## 1. The one-way-data-flow diagram + its caption

The ASCII flow names `cage.toml (prices/order/budgets/human)` as the single config
input. Split it:

> `cage.toml` (order / budgets / human / routing) **+ `prices.toml`** (model prices,
> `[credits]`) → report · attrib · …

And in the caption prose that follows, add: *prices live in `prices.toml`; a legacy
in-`cage.toml` block still reads via the fallback.*

## 2. The **Config file** architecture bullet

Currently: "the project config is `.cage/cage.toml` (the policy layer)." Add a
parallel bullet (or extend it):

> **Prices file** ([paths.py](cage/paths.py) `Footprint.prices`) — model prices are a
> **vendor rate card** with the opposite lifecycle to policy (replaced wholesale by
> `cage prices sync`, never hand-preserved), so they live in `.cage/prices.toml`:
> every `[prices.<provider>.<model>]` row, `[credits]`, and the `[meta]
> prices_version/prices_date` counters. `cage.toml` keeps the **routing decisions**
> (`[alias]`, `[tools.<tool>] price_at`) and `[meta] cage_version/policy_version` —
> **vendor facts move, routing decisions stay.** The split is **non-breaking**:
> `prices.toml` → legacy in-`cage.toml` prices → bundled default, resolved in ONE
> place (`Footprint.prices`); `cage setup` migrates a legacy inline block
> **money-neutrally** (idempotent, non-destructive); both present ⇒ `prices.toml`
> wins (`cage doctor` names the shadowed block, one-line stderr warning at load).
> `policy.load` still returns ONE merged dict, so every pricing consumer
> (`prices.call_usd`, `policy.price_match`, `convert`, `receiptprice`) is unchanged.
> `[meta]` splits **per key** — a mis-split silently stops a staleness check firing.
> `cage query prices-file` explains it.

## 3. The **Pricing is managed** Must-Know bullet

It currently says `cage prices list|unpriced|set|alias|sync` manages the project
`[prices]`/`[alias]` tables and "the bundled `data/cage.toml` is read-only." Amend:

> Writes are a **two-file** split: `cage prices set`/`sync` write **`prices.toml`**
> (vendor facts); `alias`/`route-tool` write **`cage.toml`** (routing decisions).
> `cage prices sync` replaces the cage-managed region of `prices.toml` while
> `# cage:custom` rows survive; `cage policy sync` is unambiguously `cage.toml`-only.
> The bundled defaults are read-only at runtime and ship split as `data/cage.toml`
> + `data/prices.toml` (both resolve from the zipapp via `paths.bundled_data()`).

## 4. The **state cleanup allowlist** bullet

Add `prices.toml` to the NEVER list beside `cage.toml`/`policy.toml`.

## 5. Constants / numbers-layers phrasing

Where the *policy* layer is described as "user-economics in `cage.toml`", note that
the **vendor rate card** is the `prices.toml` half of that layer; constants and
contract are unchanged.
