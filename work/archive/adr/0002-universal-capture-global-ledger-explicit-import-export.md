# ADR 0002 — Universal capture: a global ledger + explicit import/export, no OS scheduler

- **Status:** Accepted (v0.12.0, plan §3.7)
- **Date:** 2026-06-27
- **Deciders:** Arpit (ratifier), Claude Code (executor)

## Context

Capture was hook-led and project-local. Two field-proven facts broke that for whole
classes of users:

1. **Hooks are client-specific and mostly don't fire.** A VS Code extension never runs
   `.codex/hooks.json` / `.kiro/hooks/*.hook` / `~/.copilot/hooks`; only Claude Code's
   extension honors its hooks. Yet `cage doctor` reported a *wired* hook as "capture
   wired," so a Copilot-only user (or anyone in a VS Code extension) could run for days
   with an empty ledger and a green doctor.
2. **The non-Claude logs carry no project identity.** Copilot and Kiro have a single
   global usage log with no cwd; the Codex parser extracts none. Only Claude's log is
   project-mapped. So per-project *capture* is impossible for three of four agents.

Meanwhile the on-disk import already works for all four, always. The fix is to lead with
explicit import/export, not hooks — and to install nothing in the background.

## Decision

**Capture is pull-based and global. `cage import` (capture) and `cage export`
(import-then-emit) are the canonical verbs over a resolved ledger; hooks are an optional
real-time add-on; cage installs no OS scheduler. Project is a derived view via a dedicated
`project` field, not a capture scope.**

- **Global ledger + one-sink resolution.** `--ledger`/`CAGE_BASE` → nearest project
  `.cage/` from cwd → global `~/.cage` (`paths.resolve_root`). One active sink per run,
  never a double-write. The global ledger mirrors a project `.cage/` (its own `ledger/`,
  `state/`, `policy.toml`), is month-partitioned like any other, and is created on first
  write or by `cage setup --global`. The legacy `CAGE_LEDGER` (a ledger-*dir* override,
  e.g. Orff's elgar store) is unchanged and honored independently by `Footprint.ledger`.
- **The cwd-`.cage` guard is removed.** Its only job was to stop a hook firing in a random
  repo from scattering a stray local `.cage/`. Under global resolution a no-project cwd
  resolves to `~/.cage`, so scatter is structurally impossible — and dropping the guard is
  what lets a Copilot-only user's hook capture at all (it lands in the global ledger). This
  also honors the "do not alter hooks" invariant: the wire files are untouched (the
  alternative — a per-hook `--hook` flag to preserve the guard — would have altered all
  four agents' hook commands).
- **Project is a derived view.** One additive optional `project` field on the call record
  (basename-only PII guard, empty = legacy), stamped from the cwd where the log exposes it
  (Claude now; others empty, a named follow-up). `cage report --project` slices the global
  ledger; exact for Claude, projectless rows of the other agents excluded (and the output
  says so). `scope` (§3.6.2) is a different axis and is untouched.
- **No OS scheduler, ever.** No launchd/systemd/cron/schtasks unit, no `cage scheduler`
  command. The heaviest thing cage runs is `cage watch`, a foreground `sleep` poll loop
  the user starts and Ctrl-Cs. Hands-off automation is the user's *own* cron line calling
  `cage import` — documented, never created by cage.
- **Incremental import.** A per-agent high-water cursor (`state/cursors.json`, last-seen
  `(size, mtime)` per file) skips unchanged files; the ledger dedupe `seen` set is built
  once per run and shared across agents. id-dedupe stays the correctness backstop.

## Consequences

- Keeps the `$0` / stdlib-only wedge intact (`csv`/`json` only; no filesystem-watch lib,
  no network on the capture/read path). Counts-never-content holds in every export.
- The no-project user is captured for the first time; the universal path is identical
  across CLI and VS Code clients. `cage export` makes the ledger portable (jsonl/csv/json)
  with deterministic, byte-identical output for a given `--since` window.
- `cage doctor` is honest: it never claims an unfireable hook is "capture wired," names the
  active sink, and shows "last import: N ago".
- Per-project numbers are exact only for Claude — surfaced, never implied. Capture is
  on-demand by design; the staleness nudge is what keeps that from reading as a bug.

## Alternatives rejected

- **Keep the cwd-`.cage` guard for hooks (via a `--hook` flag in the wire files).** The
  literal prior wording, but it would alter all four agents' hooks, block the copilot-only
  user's hook from ever capturing, and add surface for a scatter risk the resolver already
  eliminates. Rejected in favor of dropping the guard.
- **Overload `scope` for the project axis.** `scope` is the monorepo top-level changed dir
  (§3.6.2) — a different question. A dedicated `project` field keeps both exact.
- **Any background/OS scheduler** (launchd/systemd/cron/schtasks, or a `cage scheduler`
  command). Out of scope on principle: cage installs nothing persistent. A user-owned cron
  line is the documented escape hatch.

## Veto condition (when to revisit)

If a future client exposes the cwd in Copilot/Kiro/Codex logs, `project` capture for those
agents becomes possible — that's the named follow-up, additive and non-breaking (the field
already exists). The "no OS scheduler" stance is not volume-gated; it is a product
invariant and would only change with an explicit, ratified reversal of this ADR.
