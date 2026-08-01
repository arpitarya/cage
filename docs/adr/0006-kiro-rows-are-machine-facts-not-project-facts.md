# ADR 0006 — Kiro **IDE** rows are machine facts, not project facts

**Status:** accepted 2026-08-01 · **Ships:** v0.36 · **Supersedes:** nothing

## Scope — which kiro store (amended 2026-08-01, before implementation)

Kiro has **two** stores with **opposite** attribution properties. This ADR governs the
first only; applying it to the second would destroy real attribution.

| store | parser | carries | verdict |
|---|---|---|---|
| **IDE** `tokens_generated.jsonl` | `parse_kiro_calls` | no project · `session="kiro"` · no `ts` | **machine fact** — this ADR |
| **CLI** `conversations_v2` (SQLite) | `parse_kiro_cli_credits` | **keyed by cwd** · real `conversation_id` · real `updated_at` | **project-attributable — excluded** |

The CLI store is keyed by cwd and `parse_kiro_cli_credits(db, workspace=…)` already
filters on it. Its rows *are* double-counted today, but only because the importer reads
with `workspace=""` (all conversations). The correct fix there is the **opposite** of
this ADR: pass the project's cwd and stamp `project` on the row. Tracked separately.

## Context

Kiro's **IDE** log is one *global* append-only file (`dev_data/tokens_generated.jsonl`). Every
ledger that imports kiro reads that whole file, so the same turn lands in every ledger
that ever imports it.

Row ids are stable across ledgers — `c_kiro{line_index}{sha1(line)[:8]}` — so these are
**the same row stored twice**, not distinct rows. Every id-merging path
(`ledger-sync`, `--team`, the fleet-study bundle) already dedupes correctly. Only naive
summing of two ledger *files* breaks.

But the damage is larger than "don't sum". Kiro's log carries **no project, no session,
no timestamp**. Importing it into a *new* project therefore pulls kiro's entire global
history. Measured in the lab: `workspace-off` 22 rows, `workspace-on` 28 — of which 22
were the same turns, from work done in the other workspace
([finding](../regression/2026-08-01-finding-kiro-rows-double-count-across-ledgers.md)).

**A per-project kiro cost has never been correct.** Kiro is a paid tool, so this is a
money-correctness problem, not a reporting nicety.

## Decision

**Kiro IDE rows are written to the global ledger (`~/.cage`) only — never a project
`.cage/`.** Kiro CLI credits are out of scope (see *Scope* above). An explicit `--ledger` / `CAGE_BASE` still wins, so cage-lab keeps its
isolation.

One copy exists per machine, so double-counting is impossible **by construction**
rather than by warning. Project-scoped reports show no kiro, which loses nothing real:
that number was fiction.

## Rationale

This is cage's governing principle applied literally — *cage can never be more precise
than its source*. Kiro's source has no project dimension, so a kiro cost is a
**machine-level fact**. Storing it at project level invented a precision the source
cannot support, which is the exact failure cage exists to prevent in other tools.

**Reference:** the lab finding above; the principle is stated in
[cage-lab/03-verify.md](../cage-lab/03-verify.md) §1 and applied identically to kiro's
`estimated` token counts, which are accepted as a limit rather than "fixed".

## Consequences

- A project report gains no kiro section. Doctor/report should say why, not stay silent.
- Machine-level totals stay correct and become the only place kiro is counted.
- Kiro rows remain credit-derived `estimated` — this fixes attribution, not precision.
- Behaviour change ⇒ CHANGELOG entry; users with kiro rows in project ledgers keep
  them (append-only; nothing is rewritten) but gain no new ones.

## Deliberately not taken

- **Import-cursor partition** (a fresh ledger seeks to EOF, so turns split across
  ledgers by import order). Rejected: attribution becomes an artefact of *when you ran
  import*, which is arbitrary and unreproducible. Revisit only if kiro adds a project
  or workspace field, at which point real partitioning becomes possible.
- **A marker + read-time exclusion** (rows land anywhere, derived views drop them from
  project totals). Rejected as more machinery for the same outcome, and it leaves the
  wrong rows on disk. Reconsider if another agent ever needs the same treatment while
  *also* requiring project-local storage.

## Veto condition (when to revisit)

**Contingent — auto-revisits on evidence:** if kiro's **IDE** log gains a project,
workspace, or cwd field (the CLI store already has one, which is why it is excluded), this decision is obsolete and kiro should be attributed like any other
agent. Trigger is a *named field in a shipped kiro version*, not a plan or a rumour.

**Invariant — changes only by reversing this ADR:** "a source with no project dimension
is not stored at project level" is a product value, not a volume threshold. It does not
become wrong because a user wants a per-project kiro number; the number would still be
fiction. Reversing it requires arguing that inventing attribution is acceptable — which
contradicts the method law.
