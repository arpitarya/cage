---
doc: cage-lab reporting & publishing
audience: whoever writes up a run
---

# 04 — Publish: three artifact types, never merged

**Why three:** one document answering three different questions is what produced a
report that contradicted itself — a defect's later status embedded inside a run's
frozen numbers, so nobody could tell what was current.

| artifact | scope | mutable? |
|---|---|---|
| **run report** | ONE run — what happened, that run's data only | **No.** Immutable + hashed. No before/after columns, no forward references |
| **finding doc** | ONE defect, across runs | **Yes** — it owns its own Status line, and it is the *only* place status lives |
| **phase benchmark** | ONE phase — derived from run reports | Derived only. **Introduces no new numbers** |

Plus a **history index**: one row per run — date · phase · cells · headline · hash.

## 1. Run report rules

- Readable standalone. If you need another file to know whether its numbers are
  current, it's wrong.
- Every cell carries a **verdict + citation** (which log, which ledger row).
- **FINAL vs PENDING limits never blurred** — kiro's `estimated` is FINAL; an
  unverified VS Code cell is PENDING.
- Re-publishing an existing run report is forbidden. A new run gets a new report.

## 2. Publishing into cage

Results live in **cage**, not in the lab — the lab is disposable, the evidence is not.

- Copy into `cage/docs/regression/`, dated, with a **sha256 sidecar**.
- Add the index row to `docs/regression/README.md`.
- **`docs/regression/**` is append-only.** Never edit a published file.
- Superseding: add a **banner** to the old artifact pointing at the new one. Body and
  hash stay intact — a superseded report is still evidence of what was true then.

## 3. What a good headline looks like

State the limit as prominently as the win:

> *24 graphify savings receipts captured across both scriptable CLIs; all I.4 checks
> pass. Where a saving was missed the cause is **adoption**, not a cage defect. Kiro
> and both VS Code surfaces remain UNPROVEN (4 of 6 cells) — they are not scriptable
> and await the manual leg.*

The second sentence is what makes the first believable.

## 4. Findings

- One doc per defect, dated, with a Status line it owns (`OPEN` / `RESOLVED vX.Y` /
  `SUPERSEDED`).
- A superseded diagnosis stays visible but is marked — the first explanation of a bug
  is often wrong, and burying that costs the next person the same investigation.
- The finding doc is where status changes. Never edit a run report to reflect a later
  fix.

## 5. After publishing

- Update `docs/OPEN-WORK.md` — move the phase out of pending, record the verdict.
- Append to `docs/IMPLEMENTATION.md` and `docs/WORKLOG.md`.
- Bump the relevant `docs/DOC-REGISTRY.md` rows.

Next: [05-manual-cells.md](05-manual-cells.md) for the cells a script can't reach.
