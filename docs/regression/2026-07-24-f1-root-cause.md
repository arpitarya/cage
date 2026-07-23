# 2026-07-24 — Correction to F1 (tool-savings receipts are effectively absent)

This is a correction to a finding in
[2026-07-22-capture-report.md](2026-07-22-capture-report.md) §F1. Per this repo's
convention, dated regression reports are historical records and are never rewritten —
corrections are published as new, dated entries. The 07-22 report is unchanged.

Diagnosis run against the real machine (`~/.cage` read-only; every reproduction on a
scratch ledger) with cage 0.31.3, using the F6 capture observability shipped for
exactly this purpose.

## What the 07-22 report claimed

> **Evidence:** `total_receipts = 3`, all with `task = fix-handover-bug` (the demo
> seed); `real_receipts = 0` against 36,451 calls. […] **No real savings has ever been
> captured.**
>
> **Likely cause:** the receipt-emitting paths aren't firing in the real workflow —
> graphify is being run directly rather than through `cage data graphify -- …`, and the
> fux `cage_receipt.py` / compressor / response-cache shims aren't wired or aren't
> pushing.

## Correction 1 — "no real savings ever captured" is false at machine scope

Accurate *for `~/.cage`*: that ledger has never held a real receipt (as of this
diagnosis it holds no `receipts*.jsonl` at all — it was recreated 2026-07-23 13:25 and
now carries 4,989 calls and zero receipts).

But machine-wide the claim does not hold. The one `receipts*.jsonl` on disk —
`anton/.cage/ledger/receipts.jsonl` — holds 8 rows, of which **5 are real**:

| ts | tool | task | method | saved (tok) | meta |
|---|---|---|---|---|---|
| 2026-06-19 | graphify | `probe-grid` | modeled | 67,080 | `op=query` |
| 2026-06-20 | fux | `''` | modeled | 228 | `op=hook-recall` |
| 2026-06-20 | fux | `''` | modeled | 37 | `op=hook-recall` |
| 2026-06-20 | fux | `''` | modeled | 162 | `op=hook-recall` |
| 2026-06-20T19:10:19 | graphify | `fix-handover-bug` | modeled | 27,000 | **demo seed** |
| 2026-06-20T19:10:19 | fux | `fix-handover-bug` | modeled | 6,400 | **demo seed** |
| 2026-06-20T19:10:19 | compressor | `fix-handover-bug` | measured | 8,000 | **demo seed** |
| 2026-06-27 | fux | `''` | modeled | 236 | `op=hook-recall` |

The three identical-timestamp `fix-handover-bug` rows are the `cage demo` seed —
confirmed, and the same seed the 07-22 report saw in `~/.cage`.

**Why the report couldn't see the other five:** receipts are written to the *resolved*
ledger root, so a project with a `.cage/` keeps its own; the 36k calls live in the
*global* ledger. A global-only analysis is structurally blind to project-local
receipts. The report's numerator and denominator came from different sinks.

`compressor` and `responsecache` have never produced a real receipt anywhere — that
part of the finding stands.

## Correction 2 — the real root cause (H2): a dead interceptor, not a missing one

The report's stated cause is wrong on the wiring. The graphify interceptor **is**
installed and **is** first on `PATH`:

```
$ which -a graphify
/Users/arpitarya/my_programs/anton/bin/graphify      ← the cage interceptor
/Users/arpitarya/.local/bin/graphify                 ← the real binary
```

It is nonetheless **dead**. The shim gates on a capability probe, and that probe has
returned exit 1 since v0.28.0 (`048a962`, 2026-07-15) removed the `graphify` verb
([`cage/verbmap.py`](../../cage/verbmap.py) maps `graphify` → `data graphify`):

```
$ bash -x anton/bin/graphify --version
+ command -v cage
+ cage graphify --help                                   ← exit 1: 'graphify' is now 'cage data graphify'
+ exec /Users/arpitarya/.local/bin/graphify --version     ← raw binary, unmetered, silent
```

So every `graphify` invocation on this machine execs the real binary with no metering
and no signal. `cage adopt` — which installed this shim — no longer exists, and nothing
rewrites an already-installed shim. The *bundled* template
([`cage/data/shims/graphify`](../../cage/data/shims/graphify)) is correct and probes
`cage data graphify`; only the installed copy is stale.

Reproduction with the F6 instrument (scratch ledger, `CAGE_DEBUG=1`):

| run | invocation | debug trace | receipt |
|---|---|---|---|
| B | `cage data graphify -- graphify query …` | `{"event":"receipt","tool":"graphify","produced":true,"skip_reason":"","op":"query"}` | ✅ 74,563 tok, modeled, conf 0.6, `route_key` stamped |
| C | bare `graphify query …` (how it is actually invoked) | **no line at all** | ❌ none |

Run B proves the push path, sink resolution and ledger write are all healthy — a
silently-failing push (the "H1" hypothesis) is **ruled out**. Run C is the
*interceptor-never-invoked* signature.

## Correction 3 — this is a class failure, not a graphify one

The same v0.28.0 rename orphaned the global Claude Code `SessionStart` hook in
`~/.claude/settings.json`:

```
command: /Users/arpitarya/.local/bin/cage import-claude --project .
$ cage import-claude --project .   →  error: 'import-claude' is now 'cage import --agent claude'   (exit 1)
```

Every previously-installed wiring artifact that references a renamed verb fails
silently the same way. `verbmap.REMOVED` currently lists 31 renamed verbs, so the
exposure is the whole set of shims and hooks written before 2026-07-15.

## Correction 4 — the report's proposed fix would not have worked

> **Cage fix:** (a) make the graphify interceptor the default path `cage setup` wires
> (it scaffolds `bin/graphify` — verify it's on PATH ahead of the real one)

On this machine it was *already* wired and *already* on PATH.
[`doctorcmd._interceptor`](../../cage/doctorcmd.py) tests exactly those two
things — file exists, parent dir on `PATH` — and would have reported **✅ OK** the
entire time the shim was dead. Existence + PATH is not liveness.

## H3 also holds, independently

Even during the window when the shim worked, the savings tools were barely exercised:
graphify filed exactly **one** real receipt ever (2026-06-19); fux filed four, none
since 2026-06-27; compressor and response-cache zero outside the demo seed. The cage
repo itself has no `.cage/` and no shim, and graphify is used here as `graphify
update .` / direct `graphify-out/` reads — non-metered verbs by design.

So real receipt volume on this machine would be low even with a perfect interceptor.
Both causes are true at once, and a fix for one is not a fix for the other. This is why
the "receipts: 0 — attribution has no data" doctor check the 07-22 report proposed
(F1(b)) must ship **with** stale-wiring detection, not before it: on this machine the
proximate cause is a dead shim, and a bare "no data" line would read as H3 and mislead.

## Instrument caveat (fixed in v0.31.4)

F6's `CAGE_DEBUG` receipt trace was itself suppressed under a `--ledger`/`CAGE_BASE`
override: `debuglog._may_write_under_cage` required `root/.cage` to be a directory, but
under an override `resolve_root` returns the *cwd* while the footprint re-bases onto the
override — so the guard inspected a directory unrelated to the active sink. The
instrument shipped for this diagnosis was silent in exactly the scratch-ledger setup a
diagnosis must use; run B above needed `CAGE_DEBUG_LOG` to produce any output.

Fixed in [`cage/debuglog.py`](../../cage/debuglog.py) (v0.31.4): an explicit
`CAGE_BASE`/`--ledger` root now authorizes the write. A bare cwd with neither `.cage/`
nor an override is still refused, so debug never scatters a stray footprint. Regression
tests in [`tests/test_debuglog.py`](../../tests/test_debuglog.py) — confirmed failing
before the fix, passing after — including a determinism assertion that a rendered
`cage report` is byte-identical with debug under `CAGE_BASE` on vs off.

F6's always-on `state/capture.log` breadcrumb was verified working and needed no change.

## Deferred, deliberately

- **The stale-wiring class fix.** Version-stamping generated wiring artifacts, checking
  installed shim/hook commands against `verbmap.REMOVED`, and healing or migrating stale
  artifacts on `cage setup`. Open questions (does `setup` overwrite an installed shim?
  version-stamp vs. static grep? warn vs. auto-migrate?) make this a design pass, not a
  code task.
- **The loud "receipts: 0 — attribution has no data" doctor check** — must ship with the
  above, per the reasoning in the H3 section.

## Anomaly flagged for separate diagnosis

`~/.cage/state/capture.log` is absent although calls were appended to
`~/.cage/ledger/calls-2026-07.jsonl` at 2026-07-24 01:20 — after 0.31.3 shipped the
always-on breadcrumb. `_record_capture_log` is called unconditionally from
`importcmd.run`, so those appends did **not** go through `importcmd.run`. Not part of
F1; it needs its own pass.

## Process note

Same lesson as the F2 correction: the cage-lab loop surfaced a real and deeper defect —
a whole class of silently-orphaned wiring — even though its stated cause was wrong.
Evidence beat hypothesis again. Keep publishing reports, keep treating their stated
causes as hypotheses, and keep correcting them in the open as new dated entries.
