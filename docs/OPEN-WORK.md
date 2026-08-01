# OPEN-WORK — the one plan of pending work

**Next:** **ADOPT** — do agents actually invoke graphify? Then NET-1 (does it pay).
Nothing is blocked; v0.38.0 is released.
**State:** **v0.38.0 tagged, released and on PyPI** (2026-08-02) — the GitHub release
fired publish.yml: PyPI upload, cross-OS `cage.pyz` smoke, release assets, all green.
**Two consecutive fully-green CI runs, all 12 jobs**, including the Windows behaviour
tier that had never executed before.
Suite: **995 pass / 0 fail / 10 skipped** (dev machine, macOS/posix path only; the 10
skips are the Windows-only shim behaviour tier and run on CI).

## Pending

| # | what | next action |
|---|---|---|
| **GF-LAUNCHER** | under `--python-launcher` neither twin meters (B5) | a decision — must move both twins |
| **ADOPT** | ③ see whether agents *use* graphify at all | [proposal](proposals/insights-adoption.md) — derived view |
| **NET-1** | ④ prove graphify pays — n=1, gate 5 | [proposal](proposals/net-positive-evidence-run.md) — **your hands** |
| **TOOL-SDK** | the paved road: next tool ≠ 34 modules; fux is the proof | [proposal](proposals/tool-integration-contract.md) — builds on [shim-contract](shim-contract.md) |
| **DOGFOOD** | README shows demo data, not cage's own ledger | [proposal](proposals/dogfood-report.md) — dev machine, ~1h |
| **SKILLS** | six skill candidates over existing surfaces | [proposal](proposals/cage-skills.md) — analyst + task-closer first |
| **HR1** | agent-vs-human v2, four asks graded | [proposal](proposals/agent-vs-human-v2.md) — after the track |

**WIN-CI closed 2026-08-02 — and it earned its keep.** The first-ever Windows run was
**red**, on two independent bugs neither reasoning nor macOS could have found:
(1) **in the shim** — a `rem` comment inside the nested `for` block contained
`"<candidate>"`, and cmd.exe tokenizes redirection characters *inside comments nested in
a `(...)` block*, corrupting the block into a recursion abort on every invocation;
(2) **in the test harness** — `_run()` wiped `PATH` so the shim's own
`findstr.exe`/`where.exe` could not resolve. Five pushes; two earlier hypotheses were
real improvements that did not fix the failure, and the CHANGELOG diagnosis was
**corrected** rather than left standing. Both facts are now in
[shim-contract.md](shim-contract.md) as **B8a** + a test-harness corollary, and B8's
superseded diagnosis is marked as such — the contract is what TOOL-SDK's future
interceptors inherit, so the lesson had to live there, not in a changelog.
**Windows is now CI-executed; still not field-validated** (the README says so).

**Graphify-works track (decided 2026-08-01)** — the distribution plays were declined
and removed (a `uvx` push, ccusage interop); the OTel export (below, now built) was the
only one that shipped. The priority is **graphify
end-to-end, then a paved road for more tools**. ①② are done; **ADOPT** shows whether
agents invoke it · **NET-1** proves value. **fux is the second tool** (its receipt shim
already exists) — the [tool-integration-contract](proposals/tool-integration-contract.md)
ships only when two tools use it, and now has its first artifact to build on
([shim-contract.md](shim-contract.md)).

**CMD-SYNC closed 2026-08-02** — one proposal applied, one declined, both independently
re-verified against code at execution time (not just carried forward from the handoff).
✅ `claude-md-prices-file` **applied**: the flow diagram + Must-Know bullets now name
`prices.toml` as the vendor rate card home, `cage.toml` keeping order/budgets/routing
(`grep -c prices.toml CLAUDE.md` 0 → 10). ❌ `claude-md-sources-authority` **declined** —
`paths.resolve_log_sources`'s docstring still reads *"an empty/absent `[sources]`
returns exactly the built-in registry"*, which is what CLAUDE.md already said; the
proposal described a Directive A end-state that never shipped. Zero code changes.
995/0 (unchanged — docs only). Pair archived to `docs/archive/v0.39-claude-md-sync.*`;
both proposals archived to `docs/archive/v0.39-claude-md-{prices-file,sources-authority}.proposal.md`.

**OTEL closed 2026-08-02** — `cage data export --otel` ships: one-way GenAI-conformant
JSON, exactly like `--csv` (never an import source; `--study` stays jsonl), stdlib only
(no OTel SDK — `dependencies = []` unchanged). Calls map to `gen_ai.system` ·
`gen_ai.request.model` · `gen_ai.usage.input_tokens`/`output_tokens` ·
`gen_ai.client.operation.duration` (omitted, never zero, when `latency_ms` is unknown).
**Decision: receipts/savings have no GenAI equivalent, so they're cage-namespaced**
(`cage.savings[].cage.*` — `cage.saved` GROSS, `cage.saved_usd` priced via the existing
`receiptprice` ladder and omitted, never `$0`, on an UNPRICED refusal or a non-money
unit) — no `gen_ai.*` name invented. **The convention is pre-stable**
(`constants.OTEL_SEMCONV_VERSION = "1.42.0"`, stamped in every document's `cage.meta`
block); a spec bump is a deliberate, changelog'd change, same discipline as
`prices_version`. New module `cage/otelout.py`; `cage query otel-export` explains it.
982/0 ⇒ 995/0. Pair archived to `docs/archive/v0.39-otel-export.*`.

**DEBT closed 2026-08-01** — Part 1 **landed**: the `paths.py` splits-on-contact rule is
in `CLAUDE.md` (seams `routing`/`logsources`/`agenthomes`/`footprint`, plus CODEX-OUT's
earned clause *a deletion and a move never share a diff*). Part 2 stays **declined** —
re-verified a third time, independently, by the agent that executed the prompt: bare
`cage` runs `cmd_overview` (`cli.py:651`), already prints tokens · calls · unpriced ·
last-import, `_ROOT_HELP` only shows on `--help`, and the capture-on-read is deliberate
(`cli.py:114`). No code changes. Pair archived to `docs/archive/v0.39-structural-debt.*`.

**CODEX-OUT closed 2026-08-01** — the agent's residue is gone (`codex_home` +
`CODEX_HOME` · `wiringscan`'s `~/.codex/config.toml` scan and `.codex/hooks.json`
enumeration · doctor's read · the bundle env entry · six prose enumerations);
`grep -riI codex cage/` now returns only the OpenAI model rows. **The category-2 trap
held**: `data/prices.toml` is byte-identical and a new guard prices a Copilot call on
every `gpt-5.x-codex` id, so the next blind grep fails loudly. The accepted trade — a
pre-v0.33 `~/.codex/config.toml` keeps a dead `cage` verb undetected — is named in the
CHANGELOG `Removed` entry. `paths.py` deliberately not split; `agenthomes` and the
earned clause *a deletion and a move never share a diff* live in `CLAUDE.md`'s
split-on-contact rule (promoted there by the concurrent DEBT session). Pair archived to `docs/archive/v0.39-codex-purge.*`. 983/0 ⇒ 982/0.
**Carried forward:** nothing — DEBT's `agenthomes` move stays its own fix-on-contact item.

**GF-DEBT closed 2026-08-01** — v0.38's code was sound; its honesty surface wasn't, and
all six gaps are closed in the same change, before commit. `docs/restricted-environments.md`
restored (8 citing files now resolve) with a new GF-LAUNCHER section; the README
Platforms line and `cage doctor`'s new `launcher-gap` check both state the same gap;
`cage query graphify-shims` explains the twin pair, live-interpolated;
[ADR 0007](adr/0007-graphify-twin-pair-hand-paired-not-templated.md) records the three
decisions (both twins/every OS · hand-paired not templated · contract outside package
data); `docs/cage-lab/{01-setup,03-verify}.md` now state POSIX-twin-only coverage; the
corpus-sizing rule is written into `tools/cigraphify.py` and pinned by 4 new tests
(`tests/test_cigraphify.py` — the vacuous-corpus check was already enforced in code, it
just lacked a regression test). 979/0 ⇒ 983/0. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--v0380-gf-debt--the-six-honesty-debts-win-gfci-gf-left-behind).
Archived pair: [handoff](archive/v0.38-graphify-honesty-debts.handoff.md) ·
[prompt](archive/v0.38-graphify-honesty-debts.prompt.md). GF-LAUNCHER stays open above —
this documented it, it did not fix it.

**CI-GF + WIN-GF closed 2026-08-01 (v0.38.0, unreleased)** — `graphify.cmd` ships as
bundled text against one written [behaviour contract](shim-contract.md) (B1–B8 binding,
D1–D7 divergences documented — cmd has no `exec`); both twins install on every OS;
`pathshim`/`wiringscan`/`doctor` learned PATHEXT liveness, so an interceptor this OS
cannot resolve is now a doctor **failure** rather than a green tick. CI grew a `$0`
`present` leg on 3 OSes (`tools/cigraphify.py`, corpus `tests/fixtures/cicorpus/`) whose
Windows assertion shipped already flipped. 962/0 ⇒ 979/0. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--v0380-win-gf-the-graphifycmd-twin--ci-gf-the-graphify-ci-axis).
Archived pairs: [WIN-GF](archive/v0.38-win-graphify-shim.handoff.md) ·
[CI-GF](archive/v0.38-ci-graphify-matrix.handoff.md). Residuals carried forward above as
**WIN-CI** and **GF-LAUNCHER**.

**CLEAN closed 2026-08-01** — retention **30 → 90 days**; the auto sweep (piggybacked on
`cage import`) now only **warns** on stderr — count, reclaimable KB, the exact fix,
silent when nothing's eligible, throttled 24h — and never deletes; only `cage data
cleanup --apply` deletes, and it runs regardless of `[cleanup] enabled` (decided: an
explicit command is always honored, `enabled=false` only silences the automatic
reminder). New `[cleanup] warn` switch, default true, env `CAGE_CLEANUP_WARN`. Tool
savings (`ledger/savings/<tool>/`) get the never-per-tool invariant stated at
`cleanup.NEVER` and tested surviving `prune` at `days=0`. 956/0 ⇒ 961/0. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--cleanup-becomes-advisory-90d-default-warn-only-never-per-tool).
[Archived pair](archive/v0.36-cleanup-safety.handoff.md).

**SUITE closed 2026-08-01** — **G-SAV**: `savings.record()` was missing `ts` from its
signature; added and forwarded (kept `**_ignore` for the shim callers), plus a
kwarg-parity guard test. **BUD-V-TEST**: the five sync tests re-pointed from
`[budgets]` (opt-in, commented out by BUD-V) to `[quality] signal` — a table the
bundle actually ships. Same mechanics, different worked example. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--suite-green-g-sav-fixed-bud-v-test-re-pointed-9496--9560).

**SYNC-GUARD closed 2026-08-01** — **guard now, fixture later.** The pain was
*diagnosis*, not repair — 5 budget-unrelated failures with no obvious cause. The
borrowed table/key (`[quality] signal`) now lives in one constant in
`test_policysync.py` (re-point is a one-line edit) and a new guard test fails with the
exact fix if it's ever removed from the bundle. The synthetic-bundle refactor stays
filed with a trigger — a **third** removal: [proposal](proposals/policysync-synthetic-bundle.md).
961/0 ⇒ 962/0. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--sync-guard-name-the-sync-tests-borrowed-table-guard-its-removal).
[Archived prompt](archive/v0.36-sync-guard.prompt.md).

**README-FIX closed 2026-08-01** — shipped as **v0.37.2** (committed and tagged): the
human-axis claims replaced with the real capabilities (gross/net + adoption), the
gross-vs-net honesty line added to the story, the Windows shim gap stated in Platforms —
and **closed one version later** by WIN-GF, above. Full accounting: the v0.37.2 entry in
[CHANGELOG.md](../CHANGELOG.md). The mooted grep gate for removed-feature claims is
deliberately **not** filed; raise it again if a second such claim ever ships.

**HR1** — v1 removed completely in v0.36 (substrate included); v2 proposed per-commit:
tokens/commit (join reuse) · authorship/commit (provenance aggregation, mostly built) ·
suggested-vs-accepted (new capture, counts-only, `estimated`) · time (agent measured,
wall-clock measured, **human only by attestation — never gap-derived**, the v1 killer).
[Proposal](proposals/agent-vs-human-v2.md). What existed:
[archived handoff](archive/v0.36-human-removal.handoff.md).

**BUD-V closed 2026-08-01** — verified via `just test` on the dev machine (Python
3.14): the bundle change needs no code fix; `cage policy sync` does not try to re-add
`[budgets]` (an active table buckets as `project_own`, untouched). Goldens P5/P6a/P6b
re-blessed (only the in-sync key count moved, 11→8). Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--budget-ceilings-become-opt-in-bundle-only--verified-bud-v-closed).
**NET-1 needs no code** — `insights compare` is gated at `MIN_COMPARE_N = 5`.

**KIRO-CLI-SCOPE** (carried forward from K2) — kiro-CLI credits captured while the cwd
sits outside any project reach only a *machine-ledger* sweep. Nothing is lost (the store
is re-read), but a user who never runs a project-less `cage import` never sees them.
Revisit if that turns out to be common.

## Decisions open

1. ~~Corpus refresh cadence~~ — **decided 2026-08-01: the corpus is FROZEN.** `tinyshop`
   is never mutated; a new question gets a **new named corpus alongside** it and every
   result is labelled by the corpus that produced it. Old evidence stays valid forever.
   Whether tinyshop is too *small* is a separate, filed question:
   [proposal](proposals/larger-lab-corpus.md).
2. ~~Cost cap for paid legs~~ — **decided: opt-in via `cage.toml`**, bundle ships
   `[budgets]` commented out, no constant fallback. **Verified 2026-08-01 (BUD-V)** —
   see [IMPLEMENTATION.md](IMPLEMENTATION.md). Test-debt closed 2026-08-01 (SUITE,
   re-pointed at `[quality]`); the residual coupling is closed 2026-08-01 (`SYNC-GUARD`,
   above) — the synthetic-bundle fixture itself stays a parked
   [proposal](proposals/policysync-synthetic-bundle.md) behind a third-removal trigger.

## Binds the next lab run

- **F2's copilot-VS-Code receipt limit is UNTESTED** — never claim it confirmed.
- **Record the prompt count per cell as it runs** — D3/D4 are UNVERIFIED without it.

## How this file is maintained

Continuously; completed items **deleted, not ticked**; its own markers are never
evidence. Full law: [`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*.
Done work: [IMPLEMENTATION.md](IMPLEMENTATION.md) · evidence: [regression/](regression/).
