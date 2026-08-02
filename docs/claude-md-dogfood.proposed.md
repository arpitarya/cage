---
doc: proposed CLAUDE.md edit — DOGFOOD
status: AWAITING ARPIT'S REVIEW — not applied
raised: 2026-08-02 (Claude Code, executing dogfood-report.prompt.md)
---

# Proposed CLAUDE.md edit — DOGFOOD

**Not applied.** The prompt's guardrails are explicit: *"if CLAUDE.md needs a line,
write `docs/claude-md-dogfood.proposed.md` and stop there; never edit a steering file
silently."* Everything else in the feature is built; this is the one item held for
review. The `just test` comment's raw count (1391 → 1401) **was** refreshed directly —
that is a mechanical number, not new guidance, and the repo's own Must-Know rule
("Every release updates the changelog") already sanctions refreshing that count on
contact.

**Apply, amend, or decline.** If applied, delete this file and bump the CLAUDE.md row
in [DOC-REGISTRY.md](DOC-REGISTRY.md) accordingly.

---

## Proposed addition — a short section mirroring "Regression & capture reports"

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

## What I am *not* proposing, and why

- **No new Must-Know rule.** The ZERO-dummy-data law and the counts-never-content
  discipline already govern this; a dedicated rule would duplicate what OPEN-WORK.md
  and the handoff already state.
- **No entry in the "Documentation discipline" maintained-doc enumeration.**
  `docs/regression/` isn't listed there either (it's covered by the `## Dev` section
  instead) — `docs/dogfood/` follows the same precedent rather than growing that list.
