---
status: proposed
date: 2026-07-28
author: Claude Code (capture-precision cycle)
---

# Proposed CLAUDE.md edits — `[sources]` becomes the single path authority

**Propose, don't apply** (per the handoff): these are Must-Know changes to CLAUDE.md that
follow from Directive A shipping. Arpit accepts or overrides before they land in CLAUDE.md.

## 1. The Config-file / Constants bullet — sources authority (Must-Know)

The current "Adapters & agents" text says `[sources]` *extends/replaces* the built-in
registry and that "no `[sources]` ⇒ the built-in registry byte-for-byte." **That is now
false.** Replace with:

> **`[sources]` is the ONLY source of log paths** (Directive A, ADR 0004-adjacent,
> capture-precision §3.6). `paths.resolve_log_sources` reads **only** `cage.toml
> [sources]`; the built-in registry (`paths.sources_seed`) is a **seed** that `cage
> setup`/`initcmd` **materialize** into an active `[[sources.<name>]]` table (project +
> global `~/.cage`). No built-in runtime fallback; **home-env vars are no longer consulted
> for path resolution**. An empty/absent `[sources]` captures **nothing, loudly** (`⚠ no
> [sources]` on import; "not declared" per agent in `doctor --paths`). Mandatory staleness
> mitigation: `cage doctor` diffs the project table vs the seed (`paths.sources_drift`) and
> announces now-ignored env vars; `cage setup --sync-sources` refreshes the cage-managed
> marker block, preserving user `[[sources.<name>]]` entries.

## 2. The Kiro / capture bullets — credits are a distinct kind

Add to the meter/adapters section:

> **Kiro CLI** logs to a SQLite store (`kiro-cli/data.sqlite3`) that carries **no token
> counts** (null even with an explicit model). `transcript.parse_kiro_cli_credits` reads it
> **read-only**, counts/metadata only (never the `value` transcript body or `auth_kv`), and
> records a **distinct `credits` row kind** (`schema.make_credit`, `unit="credits"`,
> `method="estimated"`, **recorded not priced**) — never a `tokens_in=0` call row.
> `ledger.credits` reads it last-write-wins per session. Wired via `[sources]
> format="kiro-cli"`. See ADR 0004 (separate by schema, not by source).

## 3. The Copilot / determinism bullets — delta rows

Add near "Transcript call ids are deterministic":

> **Copilot cumulative shutdowns → append-only delta rows.** A resumed Copilot session
> writes cumulative `session.shutdown` metrics; `parse_copilot_calls` emits per-shutdown
> **delta** rows whose id carries the shutdown ordinal — **ord 0 byte-identical to the
> legacy id**, so a legacy ledger self-heals on re-import (ord 0 dedupes, deltas append,
> rows sum to the cumulative). Never mutate a row to a moving cumulative (ADR 0004).

## 4. Constants / ledger kinds

Note the new `credits` ledger kind alongside calls/receipts/tasks/provenance, and that it
is read by no call-based view (so determinism/goldens are unperturbed).

## Also outstanding (proposed 2026-07-27, still pending Arpit)

The union/migrate lines noted on 2026-07-27 remain unapplied — carry them into the same
CLAUDE.md edit pass.
