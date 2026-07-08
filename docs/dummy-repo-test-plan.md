# Cage End-to-End Test Plan — Dummy Repo (CLI + VS Code)

**Goal:** exercise cage across a fresh, disposable repo and confirm every capture,
derive, and safety surface works **both** under a CLI client and under a VS Code
extension — then produce a ranked list of what needs fixing.

**Scope:** all four agents (`claude`, `codex`, `copilot`, `kiro`), the four-agent
invariant. Version under test: `cage 0.16.0`.

**Automated companion:** `python -m tools.dummyrepo` (build-time only, stdlib,
never in the wheel) scaffolds the disposable sibling repo and runs every
*automatable* step of this plan against the sanitized fixture corpus
(`tests/fixtures/transcripts/` — all four agents × CLI/VS Code, exact expected
rows). Steps that need a live agent print as a `MANUAL` checklist; scenario
slots whose cage feature hasn't shipped yet print `PENDING` with their phase.
Run it first; spend your manual time only on what it can't reach.

---

## Why the plan is shaped this way (the debate's conclusion)

Two facts decide the whole structure:

1. **The suite already covers breadth.** `just test` asserts exact plan numbers across
   most modules. Re-running every feature by hand mostly re-confirms what determinism
   already guarantees. So the baseline is one command, and the real effort goes to the
   **integration seams the suite can't reach**.

2. **The CLI vs VS Code split is the crux, and it is not a bug to be discovered — it is
   a documented design fact.** From cage's own README: *hooks fire only under a CLI
   client, never under a VS Code extension; `cage import` / `cage export` is the path
   that always works.* So every agent is tested **twice**: once on the CLI path (hooks
   fire in real time) and once on the VS Code path (hooks are silent, `cage import`
   ingests the on-disk session log). The pass/fail question for VS Code is narrow and
   sharp: **does `cage import` correctly parse the session log the extension actually
   writes?**

Everything below follows from those two facts: thin on breadth, heavy on the seams and
on the invariants (fail-open, determinism, `method` integrity, PII, $0/stdlib) that only
break under adversarial input, never on the happy path.

---

## 0. Preconditions (record these before starting)

- [ ] `cage --version` → `cage 0.15.0`
- [ ] `python -c "import cage"` succeeds with **no extras installed** (proves the $0 /
      stdlib-only default path — ML must stay opt-in).
- [ ] Note, per agent, whether you have it as a **CLI** client, a **VS Code
      extension**, or both. You can only test the surface you actually have installed;
      mark the rest **N/A (not installed)** rather than fail.
- [ ] Fresh shell env; unset `CAGE_BASE`, `CAGE_HUMAN_RATE`, `CAGE_CAPTURE`,
      `CAGE_NOTES_WRITE`, `CAGE_DEBUG` unless a step sets them deliberately.

## 1. Baseline — free breadth (do this first)

```bash
cd <cage repo>
just test          # expect: all passing, 0 failures
```

If the suite is red, stop and fix that first — no point testing a broken build against a
dummy repo. Record the pass count; a green suite is your breadth coverage, and every
later step targets what it *doesn't* cover.

## 2. Scaffold the disposable repo

```bash
mkdir /tmp/cage-testbed && cd /tmp/cage-testbed
git init && printf "# testbed\n" > README.md
mkdir -p src docs && echo "print('hi')" > src/app.py
git add -A && git commit -m "seed"

cage setup --project-only           # scaffolds .cage/ + graphify interceptor, no global skill
# then wire each agent you'll test on the CLI path:
cage setup --wire-only --claude
cage setup --wire-only --codex
cage setup --wire-only --copilot
cage setup --wire-only --kiro
cage setup --status                 # expect: reports which of the four are wired
```

Checks:

- [ ] `.cage/` exists with `policy.toml` and a `ledger/` dir.
- [ ] `policy.toml` carries a `[prices]` table keyed with `provider="anthropic"` rows
      (the transcript meter stamps `anthropic`; without those rows Claude calls price at
      $0 — see §6). 
- [ ] `cage setup --status` lists all four agents' wiring state; none silently missing.
- [ ] `cage doctor` runs and shows the **active ledger path**, per-agent capture state,
      and "last import: …".

## 3. CLI capture path — hooks fire in real time (per agent)

For each agent you have **as a CLI**, from inside `/tmp/cage-testbed`:

1. Run one real prompt through the agent's CLI that makes it emit tokens (e.g. "explain
   src/app.py").
2. Immediately, **without** running import:

```bash
cage report            # expect: a call row appeared in real time (hook fired)
cage doctor            # expect: that agent shows a recent hook / capture event
```

- [ ] **claude** — Stop hook wrote a call row live.
- [ ] **codex** — Stop hook wrote a call row live.
- [ ] **copilot** — `agentStop` hook wrote a call row live.
- [ ] **kiro** — `agentStop` hook wrote a call row live (Kiro's log is coarse; the row
      may be lower fidelity — note it, don't fail it).
- [ ] Run the same prompt twice → confirm the re-import path **dedupes** (no double
      counting; deterministic `call_id` for uuid-less rows).

## 4. VS Code extension capture path — the crux (per agent)

This is where the objective ("must work with VS Code extensions") is actually decided.
For each agent you have **as a VS Code extension**, from a workspace opened on
`/tmp/cage-testbed`:

1. Run one real prompt through the agent **inside VS Code** (the extension, not an
   integrated-terminal CLI call).
2. **Expect hooks to be silent** — verify the *absence* first:

```bash
cage report            # expect: NO new row yet (hooks don't fire under the extension)
```

- [ ] Confirmed no row appeared from the extension run alone. (If a row *did* appear,
      that's a finding — either you were on a CLI, or hook behavior changed.)

3. Now run the universal capture path and confirm ingestion:

```bash
cage import            # reads every agent's on-disk session log into the ledger
cage report            # expect: the extension's spend now appears
cage doctor            # expect: "last import" is now; per-agent capture = ok
```

- [ ] **claude** — `cage import` ingested the extension's transcript.
- [ ] **codex** — `cage import` ingested the extension's rollout log.
- [ ] **copilot** — `cage import` ingested `session-state/<id>/events.jsonl`.
- [ ] **kiro** — `cage import` ingested `tokens_generated.jsonl`.
- [ ] Run `cage import` **again** with no new activity → no duplicate rows (the
      high-water cursor in `state/cursors.json` holds).
- [ ] `cage export` (refresh + emit) reflects the same totals as report.
- [ ] Set `CAGE_CAPTURE=0` (or `[capture] enabled=false`) → `cage import` captures
      nothing; unset → capture resumes. (Consumer pause switch works without unwiring.)

**Log locations to sanity-check if an agent doesn't show up** (see [Debugging capture](debugging-capture.md)):

| Agent | On-disk log cage imports |
|---|---|
| Claude | `~/.claude/**` session transcript |
| Codex | `~/.codex/**` rollouts |
| Copilot | `~/.copilot/session-state/<id>/events.jsonl` (`session.shutdown` carries usage) |
| Kiro | `~/.kiro/**/dev_data/tokens_generated.jsonl` (coarse) |

## 5. Read / derive surfaces (run against the seeded ledger)

With rows now in the ledger, walk every read surface once. These are pure derives — the
value is confirming they render, honor flags, and don't crash on real data.

```bash
cage report --by route            # also try --by model/agent, --since 7d, --scope src, --project, --team
cage attrib                       # marginal-by-fixed-order savings
cage matrix                       # and: cage matrix --human   (adds the human anchor row)
cage budget                       # and: --session <id>, --scope
cage roi --since 30d
cage human --since 30d            # agent-vs-human; check saved $ AND saved hrs (hrs may go negative)
cage human-record --task <id> --minutes 30 --type feature   # then re-run cage human
cage trend --by week --metric both
cage why <call_id>                # pick a real id from cage report
cage query overview               # concept; also: data-flow, metering, attribution, determinism, pii-safety
cage query "how is cost calculated"   # calculation kind; formulas should interpolate LIVE policy values
cage query --list --kind concept  # and --kind calculation
cage origin <sha>                 # authorship for a commit you made in §2
cage verify                       # MUST exit 0 (report-only, never a gate)
cage notes-sync                   # on a dev machine defaults to DRY-RUN print (must NOT write refs/notes)
cage ledger-sync                  # team-view aggregation (dry-run expectations same)
cage limits                       # Codex quota if present; off-by-default credits stay empty
cage forecast; cage recommend; cage quality; cage regression --since 7d
cage demo                         # MUST reproduce the plan §4.4 attrib/matrix tables exactly
cage export --json                # structured summary (alias for --format json); also cage report --json
cage mcp / cage serve             # MCP + HTTP read surface boot (smoke; serve renders the HTML dashboard)
```

Checks:

- [ ] Every subcommand exits cleanly (0) or with a typed `error: …` + exit 1 — never a
      raw traceback (unless `CAGE_DEBUG=1`).
- [ ] `--json` outputs use the `cage.v1` envelope where documented.
- [ ] `cage query` for a calculation reflects a changed `CAGE_HUMAN_RATE` in the printed
      rate (live interpolation, not a hard-coded literal).
- [ ] `cage demo` matches the plan's §4.4 numbers byte-for-byte.
- [ ] `--project` filter: exact for Claude rows; Copilot/Kiro/Codex excluded (they carry
      no project) — confirm that's what happens, not a crash.

## 6. Invariants & adversarial states (where the real bugs live)

The happy path won't break these. Feed bad input on purpose.

- [ ] **Determinism.** `cage report --json > a; cage report --json > b; diff a b` →
      byte-identical. Same for `cage demo`. No clocks/random in derives.
- [ ] **Fail-open write path.** Truncate the last line of a ledger shard mid-JSON, then
      run a capture + `cage report` → reads tolerate the torn tail, writes return
      `False` not raise. Point cage at an unwritable base dir → metering swallows the
      error, request path unaffected.
- [ ] **Unpriced-model pricing (known risk).** Seed a call whose `(provider, model)`
      is **not** in the policy table → confirm behavior: prices from stored
      `est_cost_usd` fallback, and a token-only meter row does **not** silently become
      `$0`. This is the documented pricing-zero trap (model id not exact-matching the
      policy key) — verify the `anthropic` rows in `policy.toml` actually cover the model
      ids your Claude runs stamp.
- [ ] **`method` integrity.** In `cage matrix`, a reconstructed counterfactual cell must
      read `modeled` / `estimated` — **never** `measured`. Only the recorded run is an
      invoice.
- [ ] **Human cost tagging.** A `tool="human"` receipt resolves as `estimated` by
      default (never `measured` unless `--measured`, never `modeled`).
- [ ] **Non-repo / detached HEAD.** Run a task-closing flow outside a git repo and in a
      detached-HEAD state → task/provenance rows omit git fields, no crash (shelled to
      git, fail-open).
- [ ] **PII surface.** `grep -rE '(prompt|message|content)' .cage/ledger/*.jsonl` and
      inspect rows → token **counts** only, no prompt bodies, no commit messages, no file
      diffs. Provenance rows carry repo-relative **paths** only (its wider surface), never
      content.
- [ ] **$0 / stdlib.** Run the whole plan with **no** network access → nothing in the
      default path reaches out (no LLM, no fetch). `query` matching stays local
      token-overlap.
- [ ] **Exit codes.** `0` ok · `1` typed error · `2` argparse usage · `130` interrupt ·
      `cage verify` stays `0`.

## 7. Provenance & git hooks (authorship path)

- [ ] `cage setup` installed the local `post-commit` (+ `prepare-commit-msg`) git hooks
      alongside the Claude wiring.
- [ ] Make an agent edit a file in the testbed, then commit → the `PostToolUse` buffer
      resolves at `post-commit` into a **`hooked`** provenance row (highest trust).
- [ ] `cage origin <sha>` shows the author agent; a sha with no signal reports
      `unknown` (read-time default — confirm **no** `unknown` row was written).
- [ ] `cage origin <sha> --attest human` → row is `origin=human` **and**
      `method=heuristic` (enforced pairing).
- [ ] `cage notes-sync` on this dev machine → **dry-run print only**, does not write
      `refs/notes/cage-provenance` (CI is the sole writer; needs `CAGE_NOTES_WRITE=1`).

## 8. Scenario matrix (S1–S8 — what `tools/dummyrepo` runs)

The runner's scenario ids, mapped to this plan's sections and the roadmap phase
that ships each (`docs/cage-handoff-cost-impact-roadmap.md` §9):

| Scenario | What it proves | Plan § | Ships with |
|---|---|---|---|
| S1 per agent × CLI | all four agents wire; planted CLI-format logs → `cage import` → exact rows; doctor ok (hook-fires-live half is manual §3) | §2–§3 | P0 ✅ |
| S2 per agent × VS Code | hooks stay unwired; planted extension-format logs → exact rows; re-import byte-identical (cursor); stand-in formats flagged `UNVERIFIED` | §4 | P0 ✅ |
| S3 broken setups (bad policy, unwritable ledger, truncated shard, empty log) | fail-open + a `debug.log` line + doctor flags each | §6 | P1 ✅ |
| S4 bundle | `doctor --bundle` produced; PII grep of the archive clean | §6 | P1 ✅ |
| S5 seeded tasks: 5 agent-only vs 5 agent+graphify (+ cross-month pair, + an n=2 group) | `cage compare` exact medians; delta tagged `estimated` + caveat; n=2 refused; byte-identical re-run | — | P2 ✅ |
| S6 estimate → run → close ×N | `cage estimate` band exact; refusal on thin history; `--record` lands; `cage calibration` exact hit-rate; byte-identical | — | P3 ✅ |
| S7 verdict on seeded net-positive / net-negative tool | correct SAVING/COSTING verdict, inputs + method tags printed, insufficient-data path, byte-identical | — | P4 ✅ |
| S8 determinism sweep | every derived view byte-identical across two runs; `CAGE_DEBUG=1` doesn't change derived output; PII grep of the ledger clean | §6 | P0 ✅ |
| S9 fleet study: 7 simulated machines (5 complete, 1 mid-week gap, 1 missing phase 2 — 3-machine sketch predates the min-n gate) | bundles → import-merge → exact coverage, gap flagged, pairs only complete machines (6), exact paired delta; double-import idempotent; PII grep clean | — | P5 ✅ |

## 9. Findings template (the deliverable)

Record every step's outcome in this shape so "what needs fixing" is ranked and
actionable, not a wall of prose:

| # | Area | Command / step | Expected | Actual | Verdict | Fix / owner | Severity |
|---|------|----------------|----------|--------|---------|-------------|----------|
| 1 | VS Code / copilot | `cage import` after extension run | events.jsonl ingested | … | pass/fail | … | P0/P1/P2 |

Severity guide: **P0** = capture silently loses spend, a write path raises, or `method`
mislabels a projection as measured (contract violation). **P1** = a derive crashes or a
flag is ignored. **P2** = cosmetic / doc drift.

---

## Notes / assumptions

- I can drive cage's **CLI** in a sandbox, but I cannot run your actual VS Code
  extensions — §3, §4, and §7 require you to run the agents on your machine. §1, §5, §6
  I can execute for you against a synthetic ledger if you want a dry pass first.
- "Test every feature" was deliberately *not* the plan. The suite owns breadth; this plan
  spends its effort on the CLI-vs-VS-Code seam and the invariants, because that is where
  bugs that a green test run still hides actually live.
