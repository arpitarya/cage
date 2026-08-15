---
doc: the ADR set — fifteen maintained records, and the rule that keeps them true
status: current as of 2026-08-15 · ADR-LEDGER added 2026-08-15 (ratified and shipped same day, reverses ADR-KIRO's routed-exception carve-out) · ADR-MATRIX added 2026-08-15 (ratified, graduated from work/compare/tool-combination-matrix.compare.md — MATRIX-REVIVAL — not yet built) · ADR-LADDER added 2026-08-15 (the agent-surface ladder, built 2026-08-02 for v0.41, not previously recorded as its own ADR) · ADR-COVERAGE renumbered to 0002 2026-08-15 (adjacent to ADR-LAWS; the rest of 0002–0008 shifted down by one) · ADR-CONFIG added 2026-08-15 (ratified, not yet built) · replaces the numeric ADRs 0001–0011 · ADR-AUTHORSHIP carved out of ADR-CLAUDE 2026-08-14 · ADR-INTEGRITY added 2026-08-15 · ADR-CLEANUP added 2026-08-15
update-rule: NO behaviour change lands without its owning ADR updated in the same change (see "The standing rule"). A change touching no recorded decision says "no ADR affected" out loud
---

# ADRs — the durable *why*, and the rule that keeps it true

**One record per thing cage meters, plus one for what binds them all, one for the map of
what each surface can and cannot yield, one for the surface it is all read through, one
for the cross-agent question of who wrote which lines, one for proving nothing already
recorded has changed, one for what may ever be deleted, one for the file that holds every
decision you get to make, one for the layers an agent reaches all of it through, one for
how measured tool combinations compare without ever faking the one that has no receipts
yet, and one for which ledger a run's captured rows land in.**

| # | record | covers |
|---|---|---|
| 0001 | [**ADR-LAWS**](0001_laws.md) | the five cross-cutting laws — read this first |
| 0002 | [**ADR-COVERAGE**](0002_coverage.md) | what cage can and cannot say, per agent × surface — and why an absence is never a zero |
| 0003 | [**ADR-CLI**](0003_cli.md) | the command surface: every command, every flag, an example each |
| 0004 | [**ADR-CLAUDE**](0004_claude.md) | Claude Code — transcripts, the dedup law, authorship |
| 0005 | [**ADR-COPILOT**](0005_copilot.md) | GitHub Copilot — five stores, cumulative→delta, credits |
| 0006 | [**ADR-KIRO**](0006_kiro.md) | Kiro — the two-store split, machine facts, the absent spine |
| 0007 | [**ADR-CONSUMERS**](0007_consumer.md) | the things cage meters that are not agents — library, custom sources, retired agents |
| 0008 | [**ADR-GRAPHIFY**](0008_graphify.md) | graphify — the interceptor twins and the savings receipt |
| 0009 | [**ADR-AUTHORSHIP**](0009_authorship.md) | who wrote which lines of a commit — the agent is measured, the human is the residual |
| 0010 | [**ADR-INTEGRITY**](0010_integrity.md) | proving nothing that was already written has changed — a hash chain, report-only |
| 0011 | [**ADR-CLEANUP**](0011_cleanup.md) | what `.cage/state/` debris may ever be deleted, and why only a typed command does it |
| 0012 | [**ADR-CONFIG**](0012_config.md) | `cage.toml` — resolution, precedence, and the rule for what may be a setting at all |
| 0013 | [**ADR-LADDER**](0013_ladder.md) | the agent-surface ladder — L0 hookless (mandatory) → L1 hooks+steering → L2 MCP → L3 skills |
| 0014 | [**ADR-MATRIX**](0014_matrix.md) | token cost/savings across tool combinations, per closed task — a tool with no receipts yet renders honestly empty, never a faked zero |
| 0015 | [**ADR-LEDGER**](0015_ledger.md) | one active ledger per run, no per-agent routing exceptions — reverses ADR-KIRO's Kiro-IDE machine-ledger carve-out |

Each has **two sections**: **§1 for humans** (one screen, diagrams, no jargon) and
**§2 for agents** (the binding detail — context, decision, consequences, alternatives,
reference, veto). Author from [TEMPLATE.md](TEMPLATE.md).

## The standing rule — no behaviour change without its record

**Arpit, 2026-08-14: the ADRs are kept up to date, and a change to the code does not land
without its ADR updated in the same change.**

**The trigger, stated precisely so the rule stays meaningful.** Update the owning record
when a change:

- alters behaviour a record describes — a parser, a store, a routing decision, a schema
  field, a unit, a rendered refusal, an interceptor behaviour, a CLI command or flag; or
- makes, reverses or narrows a decision — including one taken *by deletion*; or
- invalidates a **veto condition**, a stated gap, or a *deliberately not taken* item.

**And say so when it does not.** A change that touches no recorded decision — a typo, a
refactor with identical behaviour, a test-only edit — states *"no ADR affected"* in its
commit message. That sentence is the rule working, not an exemption from it: a rule that
demands an edit for every keystroke decays into ritual edits, and a doc nobody trusts is
worse than no doc. This project has already watched that happen to a header seven times.

**A stale record is a defect of the same class as a missing changelog entry.** It is not
tidied up later; it is fixed on contact.

## Which record owns what

So *"update the ADR"* has an answer rather than a judgement call. A module may be claimed
by exactly one record; `tests/test_adr_ownership.py` fails when a module in `cage/` is
claimed by none, which is precisely the moment a new decision is being made without a
record to hold it.

| record | owns |
|---|---|
| [ADR-LAWS](0001_laws.md) | `ledger` · `schema` · `savings` · `units` · `paths` · `constants` · `errors` · `mergeutil` · `ids` |
| [ADR-INTEGRITY](0010_integrity.md) | `integrity` |
| [ADR-CLI](0003_cli.md) | `cli` · `clicmds` · `cliutil` · `verbmap` · `render` · `display` · `csvout` · `viewexport` · `runstamp` · `explain*` · `chats` · `commitview` |
| [ADR-CLAUDE](0004_claude.md) | the claude half of `transcript` · `claudewire` |
| [ADR-COPILOT](0005_copilot.md) | the copilot half of `transcript` · `copilotwire` |
| [ADR-KIRO](0006_kiro.md) | the kiro half of `transcript` · `kirowire` |
| [ADR-CONSUMERS](0007_consumer.md) | `metering` · `usageparse` · `usagelog` · `manifest` |
| [ADR-GRAPHIFY](0008_graphify.md) | `graphify*` · `pathshim` · `runshim` · `adoptcmd` · `compress` · `responsecache` |
| [ADR-COVERAGE](0002_coverage.md) | no module — it owns the cross-cutting *rule* the five gap tables obey (`ABSENT_SPINES` · `units.ABSENT` · `COVERAGE_GAPS` · `GRAPHIFY_COVERAGE` · `HOOK_EVENTS`/`HOOK_GAPS`), each of which stays owned by its own record |
| [ADR-AUTHORSHIP](0009_authorship.md) | the authorship half of `transcript` and `importcmd` · `authorcapture` · `linematch` · `commitjoin` · `provenance` · `origin*` · `notessync` · `verifycmd` — and the **contents** of `COVERAGE_GAPS`, whose cross-cutting rule stays ADR-COVERAGE's |
| [ADR-CLEANUP](0011_cleanup.md) | `cleanup` |
| [ADR-CONFIG](0012_config.md) | `policy` · `policysync` · `tomledit` · `cfgio` · `initcmd` — the config **file**; every section's *meaning* stays with the record that owns the behaviour (ADR-CONFIG carries the pointer table) |
| [ADR-LADDER](0013_ladder.md) | `mcpserver` · `hookcmd` · `attest` · `steering` · `wiringscan` — the four layers above L0 and the floor gate that proves none of them may become a dependency of a lower one |
| [ADR-MATRIX](0014_matrix.md) | `matrixview` — not yet built; the name is reserved here so the module lands under this record on day one rather than needing an ownership-test fixup |
| [ADR-LEDGER](0015_ledger.md) | no module — it owns the cross-cutting *rule* that every source captures into the run's one resolved ledger. The mechanism itself (`paths.resolve_root`, `paths.kiro_ledger`, `paths.kiro_routed`) stays owned by [ADR-LAWS](0001_laws.md) alongside the rest of `paths`; this record owns the *decision*, the same split ADR-COVERAGE has with the gap tables it doesn't store |

**Shared and infrastructure modules are claimed explicitly, never by silence** — the
ownership test carries the list and the reason for each. `transcript.py` is deliberately
claimed by **four** records: three vendors' parsers plus `parse_edits`, the authorship reader,
and pretending otherwise would send a copilot change to the wrong reviewer.

## Cite them by name, never by number

In prose write **ADR-LAWS · ADR-COVERAGE · ADR-CLI · ADR-CLAUDE · ADR-COPILOT · ADR-KIRO ·
ADR-CONSUMERS · ADR-GRAPHIFY · ADR-AUTHORSHIP · ADR-INTEGRITY · ADR-CLEANUP · ADR-CONFIG ·
ADR-LADDER · ADR-MATRIX · ADR-LEDGER**.

A bare "ADR 0001" is now ambiguous — it meant *team ledger aggregation via `refs/notes`*
for six weeks and there are ~90 live references to the numeric names. The numbers survive
only as filename ordering. **"ADR 0001–0011" always means an
[archived](../../work/archive/adr/README.md) record; a named ADR always means a live one.**

**And an archived record is NAMED, never CITED.** Every record here was swept clean of
archive-backed references on 2026-08-14: an archived file may have been edited or
overwritten since freezing, so it cannot ground anything — least of all a **Reference**
section, whose whole job is grounding. Write *"ratified as archived ADR 0008"* without a
link, and point the actual grounding at the live successor, the code, or a
[regression](../../work/regression/) measurement. The full rule is in
[CLAUDE.md](../../CLAUDE.md) *Documentation discipline*; the archived-to-live map is in
[work/archive/adr/README.md](../../work/archive/adr/README.md).

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
