---
doc: PROPOSED CLAUDE.md diff for SURFACE-CUT — not applied
status: awaiting Arpit · steering files are never silently rewritten
pair: [surface-cut.decision.md](surface-cut.decision.md)
---

# Proposed `CLAUDE.md` diff — SURFACE-CUT

**Not applied.** CLAUDE.md is the always-loaded contract; the standing rule is that its
diffs are proposed and Arpit lands them. **24 lines are now false.** Two of them
(`docs/shim-contract.md`, `docs/adr/0011-…`) were already stale before this change — the
ADR restructure moved them the same day.

Grouped by what kind of wrong they are.

## A · Dead command in a *rule* (highest priority — these are instructions)

| line | now says | proposed |
|---|---|---|
| **422** | "cage itself can price a session (`cage report`)" | *"cage itself can measure a session — but see line 434: the command that did it is gone."* |
| **434** | "Every WORKLOG entry ends with a `Cost:` line — the session's spend from `cage report`" | **The rule now names a deleted command.** `cage insights chats` is per *chat*, not per session, so it cannot isolate one session. Either (a) restate as `Cost: unmeasured — no per-session reader ships` until one exists, or (b) build the reader. **This session's own WORKLOG entry had to write option (a).** |
| **938–942** | dogfood snapshot = "the three allowlisted commands — `cage report`, `cage insights attrib`, `cage insights adoption`" | All three are deleted. Propose: `cage insights chats` is **still forbidden** (chat titles leak private project names, and this repo is public), so the allowlist becomes `cage insights graphify` + `cage insights commits` + `cage doctor`. The `cage report --project` prohibition can go — the view no longer exists. |

## B · Architecture block (the data-flow diagram + substrate bullets)

| line | fix |
|---|---|
| **35** | drop `--team · ledger-sync (§3.6)` from the flow line; drop `report · attrib · adoption` from the derived-views list, leaving `chats · graphify · commits · commit · why · why · origin`. |
| **64** | `project` is still stamped — but its "*derived* `cage report --project` view" is deleted. Restate as *recorded, no reader (UNREAD-FACTS)*. |
| **142** | the legacy-human exclusion is footnoted on **`cage insights chats`** now, not `cage report`. The law is unchanged. |
| **242–244** | the whole `compare`/`estimate`/`calibration` paragraph describes deleted commands. Propose replacing with one sentence: *the usage-impact surface was removed in v0.50; `tasks.jsonl` still records outcomes and est_* fields, and nothing reads them.* |
| **263, 269, 284, 546** | `cage data export --study` → **`cage study export`**; `data export --csv calls\|receipts\|tasks` and `--otel` are gone (`otelout.py` deleted). |
| **381** | `--export` is on **every `cage insights` view** plus `authorship summary` / `study report` — no longer "on `cage report` and". |
| **402** | `.cage/out/` "is `cage data serve`'s docroot" → **was**. Keep the separation rule and say why it is kept. |
| **554** | "deletion only ever happens via an explicit `cage data cleanup --apply`" — **that verb is gone and nothing prunes `state/`**. This is the STATE-RETENTION gap; the rule should say so rather than name a dead command. |
| **970, 1013** | `cage import`/`cage data export` → `cage import`; `cage data watch` no longer exists (capture is manual + capture-on-read). |
| **1035** | drop `--team` / `ledger-sync` from the ledger-scale surface. |
| **1055** | L1 benefit *(a)* "turning `cage insights adoption`'s half A from agent-blind into per-agent" — **the consumer is deleted**; the attestation is still written and read by nothing. This is the sharpest of the six unread facts and the rule should carry it. |
| **1300** | the bundled project-CLAUDE.md snippet still advertises `cage report` / `insights attrib`. Already fixed in `initcmd.py` for *new* projects; this copy is the one in this repo's own file. |

## C · Already stale before this change (ADR restructure, same day)

- **`docs/shim-contract.md`** is cited ~6× as the interceptor's contract. It was
  **absorbed into ADR-GRAPHIFY §2 and removed**. Re-point to
  [docs/adr/0005_graphify.md](../docs/adr/0005_graphify.md).
- **`docs/adr/0011-cage-measures-usage-not-cost.md`** (and every other numeric ADR path)
  now lives under [work/archive/adr/](archive/adr/README.md). CLAUDE.md cites the old
  `docs/adr/` path in several places, including the ADR-0011 rule near the top.
- The **Decision records** section describes an 11-record numbered set with a veto
  template. The live set is **four per-agent records**; the numbered ones are frozen
  history. That whole section needs rewriting against
  [docs/adr/README.md](../docs/adr/README.md).

## D · One rule to consider *adding*

Nothing in CLAUDE.md currently says **"a deleted reader does not license deleting its
writer."** This cut produced six recorded-but-unread facts, and the tempting cleanup —
stop writing them — would be irreversible and would silently narrow what a future view
could ever answer. Proposed wording:

> **A reader may be deleted; the writer it read is a separate decision.** Capture is
> cheap, append-only and irreversible-to-lose. When a view goes, the fields it read stay
> recorded by default, and the gap is filed rather than tidied away. Stopping a writer
> needs its own justification and its own line in OPEN-WORK.
