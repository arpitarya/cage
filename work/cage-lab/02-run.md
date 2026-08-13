---
doc: cage-lab run protocol
audience: whoever is driving a validation run
---

# 02 — Running: drive, capture, account for every call

**Goal:** every prompt spent produces evidence, and the run can say afterwards exactly
what it cost and what PATH it ran under.

## 1. Write the manifest BEFORE the first call

`runs/<run-id>/run-manifest.md`, authored up front:

- run id (`YYYYMMDD-HHMM`), date, operator
- **the call budget** — cells × questions × arms × repeats, arithmetic shown
- models per agent (use the **cheapest** model per agent unless the question is about
  model behaviour — this is a capture test, not a quality test)
- cage + graphify versions, and which cage build
- the **proven PATH** (`command -v graphify` / `command -v cage` output)
- `~/.cage` mtime before the run

A run that discovers its cost afterwards has no cost control.

## 1a. Ledger hygiene before the first real call

**First: confirm capture-on-read is OFF** ([01-setup.md](01-setup.md) §4b). A single
`cage report` with it on sweeps the whole machine's agent history into the lab ledger —
33,003 calls, in the case that found this. Read with `--no-import` and import only with
an explicit `--path`.


`labledger/` may already hold rows from the setup smoke test. They are **real, not
dummy** — so they are never deleted silently. Choose one and write it in the manifest:

- **Reset** — move `labledger/` aside as `labledger.smoke-<date>/` and start clean
  (preferred: the run's totals then mean exactly what they say), **or**
- **Keep** — record the pre-run row counts (`calls`, `receipts`) in the manifest and
  subtract them when reporting.

Either way, state the pre-run counts. A total that silently includes setup traffic is
the kind of small dishonesty this whole lab exists to prevent.

## 2. Repeats — 3, but only where they buy something

| question type | repeats | why |
|---|---|---|
| **graphify-sensitive** (the ON/OFF delta is the measurement) | **3** | agents are non-deterministic; report the delta as a **range** across the three, never a single number presented as exact |
| **capture-correctness** (does the ledger match the log) | **1** | verification is against *that run's own log* — deterministic. A repeat buys nothing |

Applying 3× everywhere roughly triples the bill for no extra signal. Put the split in
the manifest.

## 3. The driver (`drive.sh`)

Responsibilities, in order:

1. `export PATH="$WORKSPACE/bin:$LAB/.venv/bin:$PATH"` — explicit, never
   activation. Use the **specific** workspace being driven (`workspace-off` or
   `workspace-on`), not a shared lab-level `bin/` — the interceptor shim lives
   per-workspace and `cage doctor`'s liveness check requires that exact `bin/`
   on `PATH` (01-setup.md §2 correction).
2. **Prove PATH** — write `command -v graphify` / `command -v cage` into the manifest.
3. **Pre-snapshot** the agent's log dir (listing + size/mtime/sha) so the run's own
   output is provably isolated.
4. Ask each question through the agent's **real CLI**, one turn at a time, in the
   right workspace (`workspace-off` or `workspace-on`).
5. **Post-snapshot + diff** → exactly which files this run touched.
6. Copy the new/changed log files **verbatim** into `runs/<run-id>/logs/`; record
   sha256 of source and copy.
7. Import into the **isolated** ledger: `cage --ledger labledger import`.
8. Write `transcript-map.json` — question id → session id → the log lines it produced.
   This is what makes a capture checkable by eye.

**Never edit a captured byte.** The questions are authored, so there is nothing to
sanitize.

## 4. What is scriptable, and what is not

| agent | CLI drivable? | note |
|---|---|---|
| claude | **yes** — `claude -p` | the reference surface |
| copilot | **yes** | `--allow-all-tools` or equivalent for tool turns |
| **kiro** | **no** | Electron IDE, no headless mode. **Manual only** — [05-manual-cells.md](05-manual-cells.md) |

If an agent CLI isn't installed, the run records `NOT AVAILABLE — <agent> CLI not
installed` and exits 0. **A gap is reported, never simulated.**

**Kiro is still in scope** (law 0) — it is simply driven by hand instead of by script,
in [05-manual-cells.md](05-manual-cells.md). "Not scriptable" is a *route* difference,
never a reason to drop an agent from the matrix or the report.

## 5. The ON/OFF pairing

- Same questions, same fixture, same models, same order. Graphify is the **only**
  variable.
- Run OFF first — it's the baseline and it can't be contaminated by a graph.
- Expect a real possibility: **ON produces zero savings** because the agent never
  reached for graphify. That is an **adoption** finding, not a capture failure, and
  the run must be able to say which. Usage rows are what let it: "graphify ran 0×"
  and "graphify ran 6×, 0 receipts" are completely different results.

## 6. During the run

- Watch for **UNPRICED** rows — they should be zero. One appearing mid-run is worth
  stopping for.
- Watch that `~/.cage` mtime hasn't moved.
- If a protocol flaw appears, **stop**. A flaw discovered late costs the calls *and*
  freezes itself into every capture taken so far.

## 7. After the run

- Re-import once more: the second import must yield **0 new rows** (idempotency).
- Record actual spend against the budgeted spend in the manifest.
- Proceed to [03-verify.md](03-verify.md) — a run isn't a result until it reconciles.
