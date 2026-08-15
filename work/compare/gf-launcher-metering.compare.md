---
doc: compare — how the graphify interceptor finds cage when no `cage` is on PATH
status: DECIDED — B accepted by Arpit 2026-08-12; not yet built
decides: OPEN-WORK **GF-LAUNCHER**
---

# GF-LAUNCHER — how the interceptor reaches cage with no `cage` on PATH

**VERDICT: B — an unconditional interpreter arm in B5. ACCEPTED by Arpit 2026-08-12.**
~15 lines across the two twins; no new files, no policy read, no mode awareness, and it
fixes a *superset* of launcher mode. **Not yet built** — it is now queued agent work, and
the build inherits every constraint in §*Proposed verdict* and §*Reopen-trigger* below,
which stand unamended by the accept.

**The fork:** `cage setup --python-launcher` removes the `cage` command by design, but
[B5](../../docs/adr/0008_graphify.md)'s capability probe needs exactly that, so **neither twin**
meters — both degrade to correct, silently unmetered passthrough. Fixing one twin alone
is precisely the drift [ADR-GRAPHIFY](../../docs/adr/0008_graphify.md)
exists to prevent, which is why this is a decision and not a patch.

## What is actually lost today (the finding that moves the call)

Nowhere in the current GF-LAUNCHER prose, and it shrinks the stakes: the **GC2 transcript
route is PATH-independent**, so it keeps firing in launcher mode.

| invoker | metered in launcher mode? | why |
|---|---|---|
| claude, any surface | **yes** | `importcmd._detect_graphify` — GC0 verdict §3.0 |
| copilot **CLI** (`events.jsonl`) | **yes** | `importcmd._detect_graphify_copilot` |
| copilot **VS Code** (`chatSessions`) | no | store carries the command but no tool result (F2) |
| kiro | no | no graphify detection on the kiro leg at all |
| human, bare terminal call | no | shim route only — no transcript exists |

So GF-LAUNCHER is **not** a blackout: it costs the two agents with no result-bearing
transcript, plus every hand-typed call. That is a real gap and a smaller one than the
docs imply — the row above belongs in `work/restricted-environments.md` whichever option wins.

## The options

### A — mode-aware twin variants

`cage setup` writes interpreter-form twins when `policy.python_launcher` is on, exactly
as [`runshim.py`](../../cage/runshim.py) already picks `_SH_PY`/`_CMD_PY` over `_SH`/`_CMD`.

- **For:** zero runtime cost; an existing, working precedent in this codebase; the shim
  says nothing it cannot do, because the mode is decided before the file is written.
- **Against:** takes the hand-paired surface from 2 files to **4 in lockstep**, against a
  contract whose entire thesis is that hand-paired twins drift; and it moves the shims out
  of bundled package data into generated text, which is most of what ADR 0007 decided
  against 24 hours earlier. Buys a narrower fix than B for more permanent maintenance.

### B — unconditional interpreter arm in B5

One pair, no mode awareness. B5 gains a second arm, reached only when the first misses:

```
1. `cage` on PATH ∧ `cage data graphify --help` == 0        → meter as today
2. else `python3 -m cage data graphify --help` == 0         → meter via the interpreter
3. else                                                      → unmetered passthrough
```

- **For:** fixes a **superset** of launcher mode — a `cage.pyz` on `PYTHONPATH`, an
  unactivated venv, any importable-but-not-on-PATH install. Standard mode is unchanged in
  both behaviour and latency (arm 1 still wins first). No policy read, so the shim stays
  stateless and bundled. **The B3 marker set needs no change** — `cage data graphify` is
  still a substring of the new invocation, so twins keep skipping each other.
- **Against:** hardcodes an interpreter spelling into a bundled file, and `python3` is
  frequently absent on Windows — so the cmd twin must say `py -3` (with a `python`
  fallback), a **new permanent divergence, D8**. Adds one interpreter start to the
  cage-absent path: **~50 ms warm, 140 ms first run**, measured as `python3 -m cage data
  graphify --help` on a Linux box against cage 0.41.0. Bounded — where `python3` itself is
  absent the probe is a shell builtin and costs nothing.

### C — accept and close as a stated limitation

Delete the item; keep the gap, state it louder.

- **For:** the population is plausibly **zero** — no one has field-validated the
  locked-down-endpoint tier on a real WDAC/AppLocker fleet
  ([checklist](../restricted-environments.md), still unrun), and the table above shows
  claude and copilot-CLI already covered. Ships no code into a fail-open path.
- **Against:** closing an item because nobody has hit it yet is how WIN-GF survived to
  v0.37 — a structurally absent capture route that CI, not a user, eventually found.

## Matrix

| | A — variants | B — interpreter arm | C — accept |
|---|---|---|---|
| closes the gap | launcher mode only | launcher mode + every not-on-PATH install | no |
| files in lockstep | 4 twins + contract | 2 twins + contract | 0 |
| respects ADR 0007 | partly — generated text | yes — bundled, hand-paired | yes |
| cost on the fail-open path | none | one probe, ~50 ms warm | none |
| new permanent divergence | none | **D8** — `python3` vs `py -3` | none |
| verifiable on this machine | POSIX only | POSIX only | n/a |

## Verdict — **B** · ACCEPTED 2026-08-12

- It is the only option that treats the real defect: the probe asks *"is there a `cage`
  command"* when the question it means is *"can cage run"*. Launcher mode is one way to
  make those differ; it is not the only one.
- It does not grow the drift surface ADR 0007 bounded, and it keeps the twins bundled
  static text.
- The added latency lands only on people who already have no `cage` on PATH — for whom it
  converts unmetered into metered, or fails fast.

**What B does not claim.** It is verifiable end to end only on POSIX from this machine;
the cmd twin ships CI-asserted exactly as WIN-GF did. The honest close is *"fixed on
POSIX, CI-asserted on Windows"* — never *"fixed"* — and it does nothing for the three
non-shim rows in the table above.

## Reopen-trigger

- **B is reopened** if a measurement shows the arm-2 probe exceeding **250 ms** on a real
  target endpoint, or if a Windows install is found where neither `py -3` nor `python`
  resolves while `cage` is importable. Either finding pushes the call toward A, whose
  cost is paid at setup time instead.
- **C is reopened**, and B built, the moment one user reports a hand-typed or
  kiro-invoked graphify call going unmetered under launcher mode — a named report, not
  an argument.
- **A stays rejected** unless a *second* interceptor needs the same mode-aware treatment;
  two would make a setup-time variant mechanism cheaper than two runtime arms, and that is
  also the trigger ADR 0007 already names for templating.

## References

- [../../docs/adr/0008_graphify.md](../../docs/adr/0008_graphify.md) — B5, and the B1–B8/D1–D7 contract B would amend
- [ADR-GRAPHIFY](../../docs/adr/0008_graphify.md) §2 (absorbed from the archived twin-pair ADR,
  which is named, not cited) — hand-paired,
  not templated; every twin change costs two files plus the contract
- [restricted-environments.md](../restricted-environments.md) — the launcher-mode tier and
  the current GF-LAUNCHER statement
- [`cage/runshim.py`](../../cage/runshim.py) — the `_SH_PY`/`_CMD_PY` variant pair option A
  would copy
- [`cage/doctorcmd.py`](../../cage/doctorcmd.py) `_launcher_gap` — today's `_WARN`; under B
  it inverts into an importability check, mirroring `kiro-mcp`
- [`tests/test_win_graphify_shim.py`](../../tests/test_win_graphify_shim.py) — its B5 cases
  assume "cage absent"; that assumption is what B changes
