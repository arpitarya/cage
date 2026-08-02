---
doc: proposal — the four CLAUDE.md edits held for Arpit, in one sitting
status: proposed
raised: 2026-08-02 (four separate programs; merged into one file 2026-08-03)
owner: Arpit — steering-file edits are never applied silently
held: not applied — CLAUDE.md is the file every agent reads first
---

# Proposal — the steering edits waiting on one decision

Four CLAUDE.md edits, raised by four programs, all held for the same reason: **the
prompts that produced them forbid rewriting a steering file without a human read.**

They were four separate proposals until 2026-08-03. They patch one file and need one
sitting, so they are one document — read once, decide four times.

**Re-verified against CLAUDE.md at HEAD 2026-08-03: none of the four is applied.**

| # | the edit | verified absent at HEAD | verdict |
|---|---|---|---|
| **A** | the authorship architecture bullet (+ the "a v2 exists" amendment) | no `Authorship, per commit` bullet; no v2 amendment on the v0.36 bullet | ☐ apply ☐ amend ☐ decline |
| **B** | the copilot credit ladder (4 bullets) | no `[billing.<agent>]` text anywhere | ☐ apply ☐ amend ☐ decline |
| **C** | `FORMULAS.md` joins the ALL-CAPS entry-point list | `:674–676` still omits it | ☐ apply ☐ amend ☐ decline |
| **D** | a "Dogfood snapshot" section | absent; its anchor `## Regression & capture reports` exists | ☐ apply ☐ amend ☐ decline |
| **E** | refresh the `just test` count | `:760` reads 1401; suite is **1423** | ☐ apply ☐ decline |

**On applying any row: delete that section from this file** — an applied edit is
removed, never ticked, same law as OPEN-WORK. The file goes when the table is empty.
Bump the CLAUDE.md row in [DOC-REGISTRY.md](../DOC-REGISTRY.md) in the same change.

---

## E · The test count — the rule, not a number

**Both source proposals hardcoded a target and both went stale.** HR1 asked for
1148→1354; COPILOT-CREDITS asked for 1354→1391. CLAUDE.md is at **1401** and the suite
now prints **1423**, so either would have *regressed* the file.

That is the whole lesson: a held patch decays against the file it patches.

**So the edit is a rule, not a value** — set `:760` to whatever `just test` prints on
the day you apply it, and treat the same way the README `$0` section's count. This is
mechanical, not new guidance; the Must-Know release rule already sanctions refreshing it
on contact. **Apply it even if you decline A–D.**

---

## A · The authorship architecture bullet

*Raised 2026-08-02 by `agent-vs-human-v2.prompt.md` §9.5; amended by REV-TS (the windows
sentence gained the UTC normal form).*

### 1. New architecture bullet

Insert after the **Provenance (authorship attribution)** bullet, since it is the
capture half of the same subject.

> - **Authorship, per commit** ([linematch.py](cage/linematch.py) matcher,
>   [commitjoin.py](cage/commitjoin.py) windows + call join,
>   [authorcapture.py](cage/authorcapture.py) the pass,
>   [commitview.py](cage/commitview.py) the views;
>   [ADR 0008](docs/adr/0008-line-match-authorship-counts-persisted-content-transient.md),
>   FORMULAS §2.14) — the agent-vs-human axis, rebuilt at a unit you can `git show`.
>   **Never observe the human; observe the agent precisely and let the human be the
>   residual.** A Claude transcript records the exact text an `Edit`/`Write`/
>   `MultiEdit`/`NotebookEdit` block proposed; at import that text is matched
>   **transiently, in memory** against the added lines of the commit whose *window*
>   contains the edit. **Only counts persist — no line body and no line *hash*** (a hash
>   is a membership oracle over the source; it is named because it is the obvious "safe"
>   shortcut and is not one). Five additive-optional provenance counts, omitted at 0, so
>   `schema_ver` stays 1. **Windows, never `HEAD`-at-import**: commit *i* owns
>   `(ts_{i-1}, ts_i]`, upper bound inclusive, and work after the newest commit is left
>   **unrecorded** this sweep — idempotency picks it up exactly once when its commit
>   exists, and guessing a commit that does not exist yet would be wrong forever.
>   Every bound and probe is in **ONE UTC normal form** (`YYYY-MM-DDTHH:MM:SSZ`,
>   sub-seconds truncated; `commitjoin.norm_ts`), normalized at `Window` construction so
>   a raw `%cI` bound cannot be built — git renders each commit in the *committer's own*
>   offset, and the compare is a string compare. **Seconds, not milliseconds:** `%cI`
>   has no sub-second, so finer precision would push an edit made inside the commit's
>   own second out of it and break the inclusive bound
>   ([finding](docs/regression/2026-08-02-finding-commit-window-timestamp-skew.md)).
>   **FOUR line buckets, never three, and none is redistributed:** `agent` (matched a
>   proposal — read from the row, *never* re-matched at render time) · `human~` (in a
>   file that session *did* propose, matching nothing — a real human tweak, `estimated`
>   by construction) · `unattributed` (in a file **no** session proposed: a person, a
>   vendored tree, or generated output — cage does not guess) · `unknown` (sub-gate or
>   binary). The fourth bucket exists **because it was measured**: a single `human`
>   bucket printed 76.6% on cage's own repo, 89% of it one commit of generated JSON
>   ([dogfood](docs/regression/2026-08-02-p1-authorship-dogfood.md)) — a residual
>   presented as a finding is the v1 mistake in new clothes. **Coverage is per-agent and
>   stated** (`authorcapture.COVERAGE_GAPS`): claude only; copilot and kiro persist no
>   edit payload and render `—` with the reason, never `0%`. The call→commit join reuses
>   `taskgroup.join_rows` (task-id first, window fallback) and **never forks a second
>   join**; a task closed on a **dirty tree** is not trusted (its sha is the *prior*
>   commit), and a call with **no `project` stamp is *unconfirmable*, not adopted** —
>   otherwise a global ledger would pull every other repo's spend onto these commits.
>   **`[authorship] capture` / `CAGE_AUTHORSHIP` is its own consent switch**, separate
>   from `[capture] enabled`: this is the one path that reads a repository's *diffs*,
>   and metering spend is a different permission from reading code. `cage query
>   agent-authorship` explains it.

### 2. Amend the existing v0.36 amputation bullet

The bullet **"The Tier-1 human axis is GONE (v0.36)"** currently ends with the list of
what survives. It is still true and must stay — but a reader now meets `cage insights
commits` and needs to know it is not a reintroduction. Append:

> **A v2 exists and it is a different question (v0.43).** `cage insights commits` /
> `commit <sha>` rebuilt agent-vs-human **per commit**, and nothing amputated came back:
> no rate, no USD, no `gap_ms`, no `minutes` unit, no derived attention, no `cage human`.
> What it adds is *line-level evidence* and a human that is an explicitly-labelled
> residual. **The standing guard is the load-bearing part: no USD, rate or valuation
> appears on any authorship surface** — structurally, not by policy (`commitview.py`
> imports no pricing module, asserted by AST in the suite). Hours exist only as an
> attestation (`cage task time`, rendered `*`) or a guarded `~` estimate that **refuses
> four ways** rather than print fog — including when no agent span joined, where
> `wall − nothing` would render the raw commit gap as effort. That last refusal is v1's
> exact mistake, caught in this build by smoking the real repo.

### Also in A: the flow diagram

The derive line gains the two views HR1 shipped:
`… · compare · verdict · why · origin · chats · commits · commit`.

*(A's original §3 also asked for a test-count bump — folded into **E** above.)*

---

## B · The copilot credit ladder

*Raised 2026-08-02 by `copilot-credits.prompt.md` §9.5.*

**Why held rather than applied:** three of these four change how a future agent reasons
about **method tagging** and **where config lives** — the two places a wrong inherited
rule is most expensive.

Nothing here is load-bearing for the code: all four statements are already true in the
implementation and pinned by tests, and documented in [FORMULAS.md §1.1a](../FORMULAS.md),
[PLAN.md §3.1](../PLAN.md), [GLOSSARY.md](../GLOSSARY.md) and `cage query copilot-credits`.

### 1 · Amend the **Unit→USD** bullet

It currently opens by describing `convert.py` as "the single dispatch for a receipt's
`saved` in dollars". That stays true — the credit ladder is about **calls**, not
receipts, and `receiptprice.py` was not touched. **Append one sentence** so a reader
doesn't infer that receipts price by credits:

> Credits never enter this dispatch: a **call**'s dollars may resolve by billed credits
> (see the per-call bullet), but a *receipt*'s `saved` is tokens/usd/ms/gco2 only, and
> `receiptprice`'s ladder is untouched by COPILOT-CREDITS.

### 2 · Amend the **Per-call cost** bullet

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

### 3 · Amend the **Config file** / **Prices file** pair

Both bullets teach "vendor facts move, routing decisions stay". Add to the **Config
file** bullet:

> The same rule decides where a **billing rate** lives: `[billing.<agent>]
> usd_per_credit` is in `cage.toml`, because your plan's overage rate must survive a
> `cage prices sync` that replaces `prices.toml` wholesale. It is deliberately **not**
> spelled `[credits.<agent>]` — `[credits]` is the vendor rate card's per-model
> `per_mtok` table and is in `policy._PRICE_SECTIONS`, so a rate filed there would be
> read from the prices file and merge as **absent** in every project that has one. The
> collision is silent, which is exactly why the section is named differently.

### 4 · One line for the **Substrate** bullet

Where it lists the additive-optional call fields, add:

> …and an additive optional `credits` (the provider's own billed figure, verbatim) —
> the one additive field whose default is a `None` sentinel rather than zero, because
> absence and a recorded `0.0` are different billing facts (plan §3.1).

---

## C · `FORMULAS.md` joins the ALL-CAPS entry-point list

*Raised 2026-08-02 by DOC-CASE.*

DOC-CASE renamed `docs/formulas.md` → `docs/FORMULAS.md` so the tracked filename matches
the 120 citations that already spelled it uppercase, and its own `# FORMULAS` H1.
CLAUDE.md's closing note lists every ALL-CAPS entry-point file and omits it.

One word inserted into the existing `docs/` list. No other change.

### Proposed change

In `/Users/arpitarya/my_programs/cage/CLAUDE.md`, the closing note (currently):

```
Note: ALL-CAPS entry-point/tracker files (CLAUDE.md, CHANGELOG.md, README.md and
AGENTS.md at root; IMPLEMENTATION.md, PLAN.md, INTERVIEW.md, GLOSSARY.md, WORKLOG.md,
DOC-REGISTRY.md under `docs/`) carry no frontmatter; lowercase docs may.
```

becomes:

```
Note: ALL-CAPS entry-point/tracker files (CLAUDE.md, CHANGELOG.md, README.md and
AGENTS.md at root; IMPLEMENTATION.md, PLAN.md, INTERVIEW.md, GLOSSARY.md, WORKLOG.md,
DOC-REGISTRY.md, FORMULAS.md under `docs/`) carry no frontmatter; lowercase docs may.
```

One word inserted (`FORMULAS.md,`) into the existing `docs/` list — no other change.

---

## D · A "Dogfood snapshot" section

*Raised 2026-08-02 by `dogfood-report.prompt.md`. Everything else in that feature is
built; this is the one item held.*

### Proposed addition — a short section mirroring "Regression & capture reports"

Insert after the **Regression & capture reports** section (`## Dev` block), since
`docs/dogfood/` is built as that section's twin — same append-only/dated-snapshot
shape, same reason for living in `docs/` rather than only in a chat transcript.

> ## Dogfood snapshot (refresh periodically)
>
> `docs/dogfood/` publishes cage's own real `~/.cage` ledger numbers so the README
> never has to chase them — design of record:
> [dogfood-report.handoff.md](docs/archive/v0.44-dogfood-report.handoff.md) (archived
> on implement; the living pattern is `docs/dogfood/README.md`).
>
> To refresh: on the dev machine, run the three allowlisted commands — `cage report`,
> `cage insights attrib`, `cage insights adoption` — over the same absolute window
> (all-time, no `--since`), paste the output verbatim (method tags intact) into a new
> `docs/dogfood/<YYYY-MM-DD>.md`, and copy it over `latest.md`. **Never**
> `cage insights chats` or `cage report --project` in a snapshot — chat titles and
> working-dir basenames leak private project names, and this repo is public.
> **Never author a number** — if a command has nothing real to show (an empty task
> ledger, say), the snapshot states that instead of fabricating one.
> `tests/test_dogfood_freshness.py` fails once `latest.md` is >60 days old or its
> `snapshot_date` disagrees with the newest filename; `CAGE_SKIP_DOGFOOD_FRESHNESS=1`
> is the bisect/old-tag escape hatch.

### What D deliberately does not propose

- **No new Must-Know rule.** The ZERO-dummy-data law and the counts-never-content
  discipline already govern this.
- **No entry in the maintained-doc enumeration.** `docs/regression/` is not listed there
  either — it is covered by the `## Dev` section, and `docs/dogfood/` follows that
  precedent rather than growing the list.

---

## What none of these propose, and why

- **No new Must-Know rule anywhere.** Every edit here follows rules that already exist
  (counts-never-content, method-is-sacred, refusals render, one-implementation). Adding
  a rule for a feature that obeys the current ones would dilute the list.
- **No change to the `paths.py`-splits-on-contact seam list.** None of the four programs
  touched `paths.py`, so none has a seam to claim.

## Trigger

None — these wait on Arpit alone. They are **tier 3** in
[OPEN-WORK](../OPEN-WORK.md): one sitting, ~30 minutes, and every agent session until
then reads a CLAUDE.md that is behind the code.
