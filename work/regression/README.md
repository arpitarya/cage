# work/regression/ — capture reports & fixes from cage-lab

This folder is where the **cage-lab** sibling repo publishes its findings so they
live *with cage* and can be analysed and acted on here. It is populated
automatically after every regression/capture testing run.


## Latest fixes

- **[2026-08-14 — `calls` vs the metric ledgers, taken at the cut](2026-08-14-calls-vs-metric-crosscheck.md)** — the P0 gate of the ledger restructure, and the **only** mitigation for a deliberately-lifted freeze (`METRICS-DUAL-WRITE-END`): Claude Code sweeps transcripts at ~30 days, so once P5 stops the `calls` writer this comparison can never be repeated. Measured on **one sweep over the real stores**, both writers in the same run: claude's two writers disagree by **1.979× on rows** and **1.881× on input tokens** (the handoff expected ≈2.00× — recorded as found, and the two ratios differ because a duplicate row repeats a *cumulative* count). Kiro's `credits` shard and its `cli-conv` rows are **1:1 with identical values**, and the skip-rule difference the handoff called P2's crux measures a **delta of 0** across all 20 conversations. `codex` holds **373** rows no metric ledger will ever carry, which is why `calls` and `ledger.calls` are permanent. Sibling probe: [chat-title store probes](../research/2026-08-14-chat-title-store-probes.md).
- **[2026-08-12 — L1-FIELD Q3: the `args_hash` mismatch](2026-08-12-l1-attest-args-hash-mismatch.md)** — `cage insights adoption`'s attested-by-hook table read **zero** for nine days while `attest.jsonl` held real rows. Cause: **three producers, two conventions** — the shim route hashed the full argv (including `$REAL`, an absolute machine-specific path), the hook and the transcript route hash the tail. Every real attestation reproduced from the transcripts to prove it. **Fixed forward-only** (`graphifymeter.run` hashes `cmd[1:]`); no test caught it because every test built its usage row by hand with the *attestation's* convention, so the disagreeing producer was never exercised. **Two causes remain, stated not fixed:** piped invocations still miss (parked as [attest-join-command-normalization](../proposals/attest-join-command-normalization.proposal.md)), and an attested run can have no usage row at all.
- **[2026-08-08 — GFX-COV copilot VS Code field run](2026-08-08-gfx-cov-vscode-field-run.md)** — one real graphify query in a Copilot **Agent** chat: **146,261 tokens saved** (72 cited files), re-run idempotent, shim deliberately not on PATH so the store route was the only thing that could file. **The capture bought two tests the synthetic fixture could not**: a real agent emits `cd <repo> && graphify query …` (nothing had exercised the `&&` split), and the real part carries **no `resultDetails`** (so the ANSI-stripped fallback is the field carrier, ~89% of real parts). Fixture upgraded to a sanitized real capture. **Closes OPEN-WORK GFX-COV-FIELD** — both v0.47.0 routes now verified on real data.
- **[2026-08-07 — GFX-COV kiro-CLI field run](2026-08-07-gfx-cov-kiro-field-run.md)** — the v0.47.0 kiro route, on a real `conversations_v2` store: 2 graphify invocations, **1 filed (3,545 tokens saved), 1 refused as truncated**, re-run idempotent. Both branches proven on real data; ADR 0006 scoping observed working. **n=2 — not a refusal rate.** Closes half of OPEN-WORK **GFX-COV-FIELD**; the copilot **VS Code** half is still untested in the field (route built on 1,132 structural samples, fixture labelled SHAPE-VERIFIED / CONTENT-SYNTHETIC).
- **[2026-08-01 — leg D, the manual VS Code / IDE cells](2026-08-01-leg-d-run-report.md)** — Phase I complete. Same workspace, same six questions, same graphify install: **claude invoked graphify unprompted (2 queries, 18,456 tokens saved via the transcript route); copilot and kiro did not.** Adoption is agent-specific and cage *measured* it. **And the counterweight: the same paired arms show the ON session cost +31% while cage printed a saving — [`saved` is GROSS](2026-08-01-finding-saved-is-gross.md)** (label problem structural; the delta is n=1, UNPROVEN). Five findings: [`saved` is gross](2026-08-01-finding-saved-is-gross.md) (**HIGH**) · [copilot `--path` glob](2026-08-01-finding-copilot-path-glob.md) (real bug) · [kiro cross-ledger double-count](2026-08-01-finding-kiro-rows-double-count-across-ledgers.md) · [kiro rows carry no time/session/project](2026-08-01-finding-kiro-rows-carry-no-time-session-project.md) · [surface attribution is agent-dependent](2026-08-01-finding-surface-attribution-is-agent-dependent.md). Coverage: [phase benchmark](2026-08-01-phase-benchmark.md).
- [2026-07-29 — the graphify gap is ADOPTION, not capture](2026-07-29-finding-adoption-not-capture.md) — clean-room A/B (70 real prompts): 24 graphify receipts captured (23 via the new F1 copilot-CLI detector, validated on real traffic), copilot-plain=0 → agents don't invoke graphify unprompted; capture works. See the [run report](2026-07-29-run-report.md) + [phase benchmark](2026-07-29-phase-benchmark.md).
- [2026-07-28 — Kiro proxy probe (P2)](2026-07-28-kiro-proxy-probe.md) — the last route to exact Kiro tokens: **CLOSED negative**. kiro-cli routes to AWS CodeWhisperer/Q (no base-URL env, no token counts); credit-derived `estimated` is final by vendor design
- [2026-07-28 — Capture-precision fixes](2026-07-28-capture-precision-fixes.md) — Copilot delta-id self-heal, Kiro credits parser, Directive A/B

## Convention (do this after every testing run)

After running cage-lab against the real ledger (or the regression suite), publish
the results here, **dated**:

```
work/regression/
  <YYYY-MM-DD>-capture-report.md      # narrative findings + fixes + logging proposals
  <YYYY-MM-DD>-capture-report.json    # machine-readable findings (for scripts/agents)
  <YYYY-MM-DD>-fixes.md               # actionable, prioritized fix checklist
  latest-capture-report.md/.json      # stable path = a copy of the newest report
```

The cage-lab runner does this for you:

```bash
CAGE_REAL_LEDGER=~/.cage python ../cage-lab/labs/run_all.py     # writes the dated + latest files here
```

(Set `CAGE_REPO` if cage isn't at `../cage` relative to cage-lab.)

Why publish into cage and not just cage-lab: the findings are *about cage* and drive
*cage's* fixes, so they belong in cage's own history — diffable release to release,
and readable by any agent working on cage without needing the test repo checked out.

## Real-ledger lab runs

Real-ledger cage-lab sweeps, **one self-contained report per run** (report-per-run.plan
§7). Each run report carries no later status; a finding's current status lives in its
finding doc. Cross-run movement is in `cage-lab/golden/findings/HISTORY.md`.

| run | date | calls | headline |
|-----|------|------:|----------|
| [lab-run-001](2026-07-22-lab-run-001.md) | 2026-07-22 | 36,451 | 0 real receipts; capture-health mislabels 3/4 agents; kiro ~empty; `copilot/auto` UNPRICED; no debug.log |
| [cage-lab-baseline](2026-07-25-cage-lab-baseline.md) | 2026-07-25 | correctness matrix | 16/16 scenarios pass; kiro spec-correction (priced, not UNPRICED) |

Latest always at [`latest-capture-report.md`](latest-capture-report.md).

### Finding docs (lab-run-001, F1–F8)

Each owns its own current `Status:` line + append-only history. Stable slugs — the
cross-run handles the taxonomy was designed around.

| # | finding | status now |
|---|---------|------------|
| F1 | [receipts-empty](2026-07-22-finding-receipts-empty.md) | ⚠ PARTIALLY RESOLVED — capture-path cause fixed v0.32.0; residual is product-level (agents don't invoke savings tools unprompted) |
| F2 | [health-contradiction](2026-07-22-finding-health-contradiction.md) | ✅ RESOLVED v0.31.2 (snapshot-ordering off-by-one) |
| F3 | [kiro-empty](2026-07-22-finding-kiro-empty.md) | ✅ RESOLVED v0.34.0 (`capture-quality` doctor check) |
| F4 | [unpriced-copilot-auto](2026-07-22-finding-unpriced-copilot-auto.md) | ◻ OPEN — user-action item (route `copilot/auto`) |
| F5 | [cache-dominated-headline](2026-07-22-finding-cache-dominated-headline.md) | ✅ RESOLVED v0.34.0 (cache-efficiency footer line) |
| F6 | [no-debug-log](2026-07-22-finding-no-debug-log.md) | ✅ RESOLVED (always-on `capture.log`); hook-path breadcrumb deferred |
| F7 | [gap-ms-sparse](2026-07-22-finding-gap-ms-sparse.md) | ✅ RESOLVED v0.34.0 — reframed (wrong denominator; ~88% real coverage) |
| F8 | [stale-import](2026-07-22-finding-stale-import.md) | ◻ OPEN — user-action item (no scheduler by design) |

The original layered [2026-07-22-capture-report.md](2026-07-22-capture-report.md)
(· [fixes](2026-07-22-fixes.md)) is **SUPERSEDED** by the split above and retained
as history — never cite it for current status.

### Corrections (absorbed as finding-doc history; retained as cited evidence)

Both F-corrections now live as history *inside* the finding docs they correct; the
files below stay on disk, unedited, as the original published evidence. The 07-24
hook-gap diagnosis is owned as F6's deferred follow-on.

| date | corrects | absorbed into | what changed |
|------|----------|---------------|--------------|
| [2026-07-23](2026-07-23-f2-correction.md) | §F2 | [health-contradiction](2026-07-22-finding-health-contradiction.md) | real root cause was a snapshot-ordering off-by-one (`captured` read before this run's appends), not a this-run-vs-lifetime confusion; blast radius corrected to first-import-only. Fixed in `cage/importcmd.py`, shipped v0.31.2. |
| [2026-07-24](2026-07-24-f1-root-cause.md) | §F1 | [receipts-empty](2026-07-22-finding-receipts-empty.md) | "no real savings ever captured" is false machine-wide — 5 real receipts in a *project* ledger while the 36k calls live in the *global* one. Real cause is a **dead** interceptor, not a missing one (v0.28.0 verb rename → `cage graphify --help` exits 1 → falls through to unmetered binary; a class failure across every pre-rename shim/hook). Instrument gap fixed v0.31.4; stale-wiring class fix shipped v0.32.0. |
| [2026-07-24](2026-07-24-capture-log-hook-gap.md) | 2026-07-24 anomaly (flagged in the F1 report) | [no-debug-log](2026-07-22-finding-no-debug-log.md) (as follow-on) | Resolves, not corrects. `capture.log` only ever instrumented the pull/import path; the real-time Claude Stop/SessionEnd hook (`hooks.py`) appends directly and always bypassed it — 1,674 un-breadcrumbed `claude-code` rows. Surfaced once v0.32.0 re-livened this machine's dead global hook. Extending F6 to the hook path is deferred. |
| [2026-07-24](2026-07-24-field-gate-post-heal-check.md) | (acceptance analysis) | — self-contained | Phase 4 gate honesty: post-heal, ambient production data must not be used as the hooks-on arm (a new false-pass mode); the F6 gap is a cheap pre-check that advances Phase 4. No defect; owns its own status. |

### Follow-ups shipped

Findings above are historical records and are never rewritten; what shipped from them
is tracked here.

| finding | shipped in | what landed |
|---------|-----------|-------------|
| [2026-07-24](2026-07-24-f1-root-cause.md) — stale-wiring class fix (deferred there to a design pass) | **v0.32.0** | Detection of any installed artifact naming a verb the live CLI parser rejects (`cage/wiringscan.py`, user-level files included), healing on `cage setup`, `interceptor` upgraded from existence+PATH to liveness, and the deferred `receipts: 0` check shipped with it so the two report the true cause together. |

## What cage-lab is

A black-box regression suite + per-agent capture labs for the cage-flux package
(sibling repo `../cage-lab`). It never imports cage — it installs and runs the
shipped artifact, validates the numbers against a hand-derived reference, and (in
the labs) slices the real ledger per agent to surface capture gaps. See
`../cage-lab/TEST_PLAN.md` and `../cage-lab/CAPTURE_REPORT.md`.

## Validation reports (hashed)

Golden-set validation reports, hashed + published by `cage-lab/golden/publish_report.py` (Directive B). Append-only.

| date | phase | cells | headline | sha256 (12) |
|---|---|---|---|---|
| 2026-07-28 | Phase 1 re-run (post-fix; §4.5 RESOLVED) | V1–V5b | §4.5 surface-collision marked RESOLVED (declared-wins fix re-verified); baseline banners | `e22e6eeac5ea` |
| 2026-07-28 | Phase 1 re-run (post-fix; baseline banners) | V1–V5b | Baseline §1/§2/§3.1 banner-labelled as superseded; scripted cells CLOSED green | `adee80650612` |
| 2026-07-28 | Phase 1 re-run (post-fix) | V1–V5b | All red cells green: copilot 8/8 exact, kiro credits, claude byte-identical | `f3c058e4b1ec` |
| 2026-07-28 | Phase 1 (baseline, pre-re-run) | V1–V5b | Copilot -16–18%; Kiro CLI tokens null | `3abe494f0d60` |

## Per-run validation reports (hashed)

Golden-set reports are now **one per run** (`cage-lab/golden/publish_report.py`, report-per-run.plan). Append-only, newest first; each row names its run so numbers can never be misread across runs. Cross-run movement lives in `cage-lab/golden/findings/HISTORY.md`.

| run | date | phase | cells | copilot tokens_in | kiro | verdict | sha256 (12) |
|---|---|---|---|---|---|---|---|
| [I-legD](2026-08-01-leg-d-run-report.md) | 2026-08-01 | I manual leg D (VS Code / IDE, by hand) | D1–D6: claude+copilot VS Code × OFF/ON, kiro IDE × OFF/ON | 158,125 (OFF) / 139,302 (ON), `surface=vscode`, UNPRICED (router alias) | 22 / 28 rows — **not summable**, one global log per ledger; A/B not reconstructible | **claude invoked graphify unprompted (18,456 tok saved *gross*, transcript route); copilot + kiro did not** — *and the same paired arms cost +31% on the ON side (n=1, UNPROVEN)*. VS Code capture exact; 2 real defects (copilot `--path` glob; `saved` is gross) | `4b3567fa5fe4` |
| [I-scripted](2026-07-29-run-report.md) | 2026-07-29 | I scripted legs (clean-room A/B) | claude+copilot CLI × graphify OFF/ON | 5,708,554 (3 arms) | NOT AVAILABLE (unscriptable) | **24 graphify receipts (23 via new F1); adoption-not-capture; I.4 all PASS** | `a5d1056b75bc` |
| run-003 | 2026-07-28 | Phase 1 re-run (post-fix) | V1–V5b | 227,298 / 233,675 ✅ | 12/15 credit rows | all green | `ddf8c9a993a9` |
| run-002 | 2026-07-28 | Phase 1 baseline (pre-fix) | V1–V5b | 189,788 / 191,414 ❌ | 0 rows ❌ | 2 HIGH findings gate Phase 2 | `3b11bc8b61f7` |

## Phase benchmarks (hashed)

The **third artifact type** (run report = one run · finding doc = one defect ·
**benchmark = one phase**): *what does cage capture, and how correct is it?* across
a whole phase. Derived from existing runs — introduces no new number; every cell
carries a verdict + citation, and FINAL (vendor-design) vs PENDING (untested)
limits are never blurred.

| date | phase | coverage | headline | sha256 (12) |
|---|---|---|---|---|
| [2026-08-01](2026-08-01-phase-benchmark.md) | **I COMPLETE** (scripted + manual leg D) — **supersedes 2026-07-29** | token capture **4/6 verified**, 1 HONEST-LIMIT (kiro IDE), 1 NOT AVAILABLE (kiro CLI); graphify-ON capture **3/6 verified**, **2 UNTESTED** (copilot VS Code, kiro IDE — never invoked), 1 NOT AVAILABLE | VS Code capture **exact** for both extension agents · claude VS Code graphify savings captured via the **transcript** route (the shim was not on the extension PATH) · **F2's copilot-VS-Code limit was never exercised — untested, NOT confirmed** · kiro A/B **not reconstructible** · **savings figures are GROSS** (certifies capture, not the net win) | `7e5d80a473d9` |
| [2026-07-29](2026-07-29-phase-benchmark.md) | I (scripted legs) — **supersedes Phase-1**; **⚠ SUPERSEDED 2026-08-01** by the row above | 2/6 cells verified (claude+copilot CLI); 4 UNPROVEN (VS Code + kiro = manual leg D) | claude+copilot CLI **EXACT** (3-way, isolated) · **F1 copilot detection validated on real traffic (23 receipts)** · gap is **adoption, not capture** · kiro-CLI **NOT AVAILABLE** (no headless) | `555073bf63e2` |
| [2026-07-28](2026-07-28-phase-1-benchmark.md) | 1 (CLOSED) — **⚠ SUPERSEDED 2026-07-30** by the row above | 6/12 cells — scripted CLI only | claude/copilot CLI **EXACT** (3-way) · kiro CLI **HONEST-LIMIT** (credits estimated; tokens FINAL-null) · VS Code **UNPROVEN** (P3) | `58948469192c` |

The 2026-07-28 **and** 2026-07-29 benchmarks carry a superseded **banner only**, placed
*above* a `HASH-COVERS-BELOW` marker — their bodies and published hashes are
byte-identical to what was originally published. They are history; never cite them for
current coverage.

### Finding docs (Phase I)

| finding | status now |
|---|---|
| [call-id-collisions](2026-08-02-finding-call-id-collisions.md) | ⬛ **RESOLVED 2026-08-02 (unreleased, ID-ENTROPY)** — `ids.new_id` had **16 bits** of randomness per millisecond and every merge path dedupes *by id*, so a collision was a **silently dropped row**. Measured 874 dupes in 200,000 sequential ids (~1 in 229); it turned main red once (`test_study`, 37 vs 38). Widened to 32 bits: **0 dupes in 200,000** on re-measure. Rows already written keep their old ids and their old risk — never rewritten |
| [commit-window-timestamp-skew](2026-08-02-finding-commit-window-timestamp-skew.md) | ⬛ **RESOLVED 2026-08-02 (unreleased, REV-TS)** — commit windows compared raw `%cI` *committer-local* offsets lexicographically against UTC `…Z` probes, so every authorship join on a non-UTC machine (IST = the only one that has run this) landed on the wrong commit. **Two of the three claimed failure shapes reproduced; the third was falsified** — git renders `%cI` as `Z` at zero offset, so pure-UTC repos were correct all along, and that is what forced a **seconds** normal form rather than milliseconds. Frozen rows are not repaired: pre-fix rows keep their wrong sha forever |
| [gross-vs-net-savings](2026-08-01-finding-saved-is-gross.md) | ◻ **OPEN — HIGH**: `saved` is a per-query counterfactual that excludes the cost of *using* the tool, so cage can print a saving on a session that cost more (leg D: +31%, **n=1, UNPROVEN**). Label fix now, netting next; `repoceiling` inherits it |
| [adoption-not-capture](2026-07-29-finding-adoption-not-capture.md) (2026-07-29) | ◻ OPEN — **corroborated 2026-08-01** on VS Code and extended to kiro (claude invoked graphify unprompted; copilot + kiro did not). Product/behavioural, not a cage defect. Current status is in the doc's header block |
| [copilot-path-glob](2026-08-01-finding-copilot-path-glob.md) | ⬛ **RESOLVED 2026-08-01** (unreleased) — was: `import --agent copilot --path` hardcoded the CLI glob `*/events.jsonl`, so it could never reach the VS Code `chatSessions/*.jsonl` store (the parser handles both; only the glob was wrong). Fixed by **`[sources] path_globs`** — root-agnostic `--path` patterns declared in `cage.toml`, no glob literal left in any import branch (AST-gated). Status flipped by a **RESOLVED banner above a `HASH-COVERS-BELOW` marker**, so the published body is byte-identical and the digest is unchanged. See [path-globs handoff](../archive/v0.36-path-globs.handoff.md) |
| [kiro-rows-double-count-across-ledgers](2026-08-01-finding-kiro-rows-double-count-across-ledgers.md) | ◻ OPEN — document or warn: one global kiro log re-read by every ledger ⇒ kiro totals must never be summed across ledgers |
| [kiro-rows-carry-no-time-session-project](2026-08-01-finding-kiro-rows-carry-no-time-session-project.md) | ⬛ **HONEST-LIMIT — FINAL** unless kiro changes its log: no `ts`/`session`/`project` ⇒ **no kiro ON/OFF delta may ever be reported** |
| [surface-attribution-is-agent-dependent](2026-08-01-finding-surface-attribution-is-agent-dependent.md) | ⬛ HONEST-LIMIT — copilot's stores are separate (`surface=vscode` ✅); claude's are shared (`surface` empty, unknowable). For claude, `project` is the discriminator that works |

### Hash sidecars

Every hashed artifact ships a `<file>.sha256` beside it; verify with
`shasum -a 256 -c <file>.sha256`. **Two coverage conventions, each stated in its own
sidecar** — never assume one:

| artifact | hash covers |
|---|---|
| validation reports · `2026-07-28-phase-1-benchmark.md` · `2026-07-29-phase-benchmark.md` · `2026-07-29-finding-adoption-not-capture.md` | the body **below** the `<!-- HASH-COVERS-BELOW -->` marker (the header prints the hash, so it must be excluded) |
| `2026-07-29-run-report.md` · every 2026-08-01 artifact | the **whole file**, byte 0 to EOF — published without an in-body hash header, so there is no marker to exclude |

The two 2026-07-29 artifacts moved from whole-file to marker-range on 2026-08-01 **with
their digests unchanged**: a header was prepended above a new marker, so the bytes below
it are byte-identical to the original whole file. Nothing published was edited — the
banner (benchmark) and the current Status line (finding) live entirely above the marker.
