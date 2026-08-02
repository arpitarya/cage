# Proposed CLAUDE.md edit — COPILOT-CREDITS (v0.44)

**Held for Arpit's review — deliberately NOT applied.** The prompt's §9.5 says: propose
the CLAUDE.md edit and surface it, never silently rewrite. Apply / amend / decline, then
delete this file and bump the CLAUDE.md row in [DOC-REGISTRY.md](DOC-REGISTRY.md).

Same shape as [claude-md-hr1.proposed.md](claude-md-hr1.proposed.md).

---

## 1 · Amend the **Unit→USD** bullet

It currently opens by describing `convert.py` as "the single dispatch for a receipt's
`saved` in dollars". That stays true — the credit ladder is about **calls**, not
receipts, and `receiptprice.py` was not touched. **Append one sentence** so a reader
doesn't infer that receipts price by credits:

> Credits never enter this dispatch: a **call**'s dollars may resolve by billed credits
> (see the per-call bullet), but a *receipt*'s `saved` is tokens/usd/ms/gco2 only, and
> `receiptprice`'s ladder is untouched by COPILOT-CREDITS.

## 2 · Amend the **Per-call cost** bullet

Insert after the first sentence (`report`/`budget` **recompute** each call from
`tokens × policy`…):

> **The copilot exception, and the one choke point.** `call_usd_match` is the ONE place
> a call becomes dollars — `call_usd` wraps it, and every USD consumer (report · budget ·
> chats · compare · verdict · roi · netsaved · study · forecast · quality · freshness ·
> doctor) reaches a dollar through one of the two — so a pricing rung added there is
> inherited with **no per-view fork** (grep-pinned by `tests/test_copilot_credits.py`).
> Since v0.44 a copilot row resolves by a three-rung ladder
> ([creditprice.py](cage/creditprice.py), FORMULAS §1.1a): **recorded `credits` × the
> configured `[billing.<agent>] usd_per_credit`** → **tokens × price table** → loudly
> UNPRICED. Rung 1 wins outright, because since 2026-06-01 a Copilot credit *is*
> GitHub's own tokens×rates computation done with what cage cannot see (what
> `copilot/auto` routed to, GitHub's current rates) — so it prices that router **exactly**
> with no price-table row. It is **`modeled`, never `measured`**: the count is a recorded
> fact, the dollar is a rate the user set and cage cannot check against an invoice, and
> **any aggregate containing one credits-priced row degrades to `modeled`** — the weaker
> tag always wins (`creditprice.method_for`), or a configured rate would read as an
> invoice. **Rate unset ≠ rate zero:** unset skips the rung and credits render as a
> *count*, never a dollar; `0.0` is a real rate that prices at $0.0000. **Absence ≠ a
> recorded zero**, and credits are **never derived from tokens in either direction** — so
> `schema.make_call`'s `credits` defaults to a `None` sentinel rather than the usual
> omit-at-zero idiom, the one additive field that breaks that pattern and the only way
> both facts survive. A total spanning both bases prints the split (never blended
> silently); CSV names the basis per row in `priced_via`. `cage query copilot-credits`
> explains it.

## 3 · Amend the **Config file** / **Prices file** pair

Both bullets teach "vendor facts move, routing decisions stay". Add to the **Config
file** bullet:

> The same rule decides where a **billing rate** lives: `[billing.<agent>]
> usd_per_credit` is in `cage.toml`, because your plan's overage rate must survive a
> `cage prices sync` that replaces `prices.toml` wholesale. It is deliberately **not**
> spelled `[credits.<agent>]` — `[credits]` is the vendor rate card's per-model
> `per_mtok` table and is in `policy._PRICE_SECTIONS`, so a rate filed there would be
> read from the prices file and merge as **absent** in every project that has one. The
> collision is silent, which is exactly why the section is named differently.

## 4 · One line for the **Substrate** bullet

Where it lists the additive-optional call fields, add:

> …and an additive optional `credits` (the provider's own billed figure, verbatim) —
> the one additive field whose default is a `None` sentinel rather than zero, because
> absence and a recorded `0.0` are different billing facts (plan §3.1).

## 5 · The test count in the **Dev** block

```diff
-just test          # python -m pytest -q   (1354 tests; +10 Windows-only skips)
+just test          # python -m pytest -q   (1391 tests; +10 Windows-only skips)
```

Mechanical, and the release rule requires it — bundled here rather than applied
separately only because the no-silent-rewrite instruction is unqualified for this file.
Apply it even if you decline §1–§4.

---

## Why this is proposed rather than applied

CLAUDE.md is the steering file every agent reads first, and three of these four edits
change how a future agent reasons about **method tagging** and **where config lives** —
the two places a wrong inherited rule is most expensive. It should be read by a human
before it becomes law.

Nothing here is load-bearing for the code: all four statements are already true in the
implementation and pinned by tests, and are documented in
[FORMULAS.md §1.1a](FORMULAS.md), [PLAN.md §3.1](PLAN.md), [GLOSSARY.md](GLOSSARY.md)
and `cage query copilot-credits`.
