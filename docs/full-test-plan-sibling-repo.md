# Cage full test plan — sibling repo, everything, including real extensions

**Version under test:** `cage <version under test>`
**Last executed:** v0.22.1 — run record archived at [docs/archive/v0.22.1-full-test-run.md](archive/v0.22.1-full-test-run.md); prior: [docs/archive/v0.16-full-test-run.md](archive/v0.16-full-test-run.md)
**Goal:** exercise *every* cage surface against a fresh sibling repo — automated where the S1–S13 runner covers it, **manual with the real CLI clients and VS Code extensions** where it can't. All fixture formats are field-verified as of v0.22; if an agent update changes a log format, the manual pass re-captures a sanitized sample (see `tests/fixtures/transcripts/README.md`).
**Relation to other docs:** supersedes the manual parts of the dummy-repo test plan (archived: `docs/archive/v0.16-dummy-repo-test.plan.md`); Part A delegates all scripted coverage to `python -m tools.dummyrepo`.

**Result recording:** keep a findings table as you go (template at the end). Every failed step gets a row — don't stop to fix mid-run unless capture itself is broken.

---

## Part A — Automated baseline (run first, ~minutes)

- [ ] `just test` → all passing, 0 failures. Record the count. If red, stop and fix first.
- [ ] `python -m tools.dummyrepo` → S1–S13 all PASS (scripted capture, adversarial states, bundle PII, compare/estimate/calibration/verdict goldens, fleet merge, attention gaps, pricing/unpriced, launcher mode, pyz parity).
- [ ] `python -m tools.skillgen --check` → no drift.
- [ ] `python -c "import cage"` in a venv with **no extras** → succeeds ($0/stdlib path).
- [ ] `cage demo` → reproduces the plan §4.4 tables.

Everything below targets only what A cannot reach: real clients, real extensions, real hooks, real logs, multi-day behavior.

## Part B — Scaffold the manual sibling repo

```bash
cd ~/my_programs
git init cage-testbed && cd cage-testbed
printf 'hello\n' > README.md && mkdir -p src docs && git add -A && git commit -m init
cage init                      # project .cage/
cage setup                     # wire ALL FOUR agents + git hooks + skill assets
cage doctor                    # expect: ok/warn only; note every warn
```

- [ ] `cage setup` run **twice** → second run idempotent (no duplicate hooks/config, byte-identical files).
- [ ] Fresh env: unset `CAGE_BASE`, `CAGE_CAPTURE`, `CAGE_DEBUG`, `CAGE_HUMAN_RATE`, `CAGE_NOTES_WRITE` unless a step sets them.
- [ ] Snapshot wiring for later diff: `cage doctor > /tmp/doctor-0.txt`.

## Part C — Capture matrix: 4 agents × (CLI, VS Code extension)

For each cell you actually have installed (mark the rest **N/A (not installed)**), do a real session in `cage-testbed`: ask the agent to make a small edit (e.g. "add a docstring to src/x.py"), let it finish, then verify. Prefix every check with `CAGE_DEBUG=1` so failures leave `debug.log` lines.

**Per-cell check (same for all):**

1. Session done → `cage import` → `cage report` shows new call rows with the right `agent`, non-zero tokens, a priced USD (not $0 — if $0, check `(provider, model)` exact-match in policy; known bug class).
2. `cage doctor` → capture path for that agent reported correctly (CLI: hook wired + fired; extension: hook marked "may not fire", import path healthy).
3. Ledger PII grep: `grep -rE "docstring|src/x.py content|<anything you typed>" .cage/ledger/` → **no prompt text, ever** (task rows: top-level dirs only; provenance: repo-relative paths allowed, no content).
4. Row sanity: `python -m json.tool` one row from `calls-2026-07.jsonl` — fields match schema, `scope`/`project` sensible.

**Per-cell specifics:**

| Cell | Session log to verify | Extra checks |
|---|---|---|
| Claude Code **CLI** | `~/.claude/projects/<slug>/*.jsonl` | Hooks fire live: row appears at SessionEnd *without* manual `cage import`. Post-commit: make the agent commit → `provenance.jsonl` gets a `hooked` row; `cage origin <sha>` explains it. |
| Claude Code **VS Code ext** | same | Claude's extension honors hooks — verify rows land live; if not, `cage import` must catch up and `debug.log` must say why the hook missed. |
| Codex **CLI** | `~/.codex/sessions/**/rollout-*.jsonl` | `cage limits` after the session → rate-limit snapshot in `.cage/state/limits.json`; `cage limits --json` = `cage.v1` envelope. |
| Codex **VS Code ext** | find the real log (extension may write elsewhere — search `~/.codex` and VS Code globalStorage) | **Deliverable:** sanitized sample → `tests/fixtures/transcripts/codex/vscode/`, remove `UNVERIFIED-FORMAT`. If format differs and import parses 0 rows from a non-empty log → confirm `debug.log` records it, file a finding. |
| Copilot **CLI** | `~/.copilot/session-state/*/events.jsonl` | Hook is user-level (`~/.copilot/hooks/cage.json`) — verify it swept *all* agents' logs (`paths.cage_import_all`), not just copilot's. |
| Copilot **VS Code ext** | extension log ≠ CLI log — locate it (globalStorage / output channels) | **Deliverable:** real sample → `copilot/vscode` fixture. `.vscode/mcp.json` present → in VS Code, ask Copilot to consult cage via MCP (read check below). |
| Kiro **IDE** (it *is* VS Code-family) | `…/globalStorage/kiro.kiroagent/dev_data/tokens_generated.jsonl` | `agentStop` hook self-backfills whole log each turn → run two sessions, confirm **no duplicate rows** (composite-id dedupe). Coarse token counts expected; note fidelity. **Deliverable:** pin `kiro/vscode` fixture on this machine's layout. |
| Kiro **CLI** (if installed) | same token log | Same dedupe check. |

- [ ] After all cells: `cage report` totals = sum of what each agent session added (spot-check arithmetic).
- [ ] **Attention (v0.18):** claude-sourced call rows carry `gap_ms` (codex/copilot/kiro rows don't — absence explicit); `cage human` shows derived minutes labelled `derived (turn-gaps, capped)`.
- [ ] **Export sweep (v0.19):** run one agent session, do NOT `cage import`, then `cage export` → the fresh rows are in the output (imports-everything-first); `--no-import` → they aren't; manifest records which ("snapshot only (no sweep)").
- [ ] `CAGE_CAPTURE=0 cage import` → no new rows (capture switch); `=1` restores; `[capture] import_before_export = false` skips the export sweep.
- [ ] Delete the project `.cage/`, run one more agent session, `cage import` from `$HOME` → rows land in **global** `~/.cage` (resolver precedence); restore project ledger after (`cage init` again). Record which sink `cage doctor` names each time.
- [ ] `cage doctor --paths` (v0.17): per agent, every candidate log location with found/missing + a `why` per miss; active sink + precedence chain at the end; nothing written.

## Part D — Every read surface, against the real ledger

Run each against `cage-testbed`'s now-populated ledger. Pass = renders without error, numbers self-consistent, `method` tags visible where they apply, exit code 0 (or documented).

- [ ] `cage report` · `--project` · `--scope <dir>` · `--since <window>` (7d/24h/2w; cutoff respected across month shards)
- [ ] `cage attrib` · `cage matrix` · `cage matrix --human` (flag adds the anchor row; without it, byte-identical to before)
- [ ] `cage budget` (set a tiny budget in policy.toml → warn/block behavior) · `cage roi` · `cage recommend` · `cage forecast` · `cage regression`
- [ ] `cage human-record` + `cage human` + `cage trend` (record a human receipt with minutes → USD via `[human]` rates; `CAGE_HUMAN_RATE=200 cage human` → header shows provenance, number changes)
- [ ] `cage why` · `cage quality` + `cage outcome <task> [--redo] --label <word>` (success is the default) (label = single token; try a path → must be rejected)
- [ ] `cage compare` (groups from Part C tasks; n<5 groups → refusal text, never numbers) · `cage estimate --label <word>` (band, `modeled` tag) · `--record` then close → `cage calibration` (hit-rate line)
- [ ] `cage verdict <tool>` (with graphify/fux receipts if present, else INSUFFICIENT DATA path)
- [ ] `cage query "how is roi calculated"` + a concept ("how does cage work") + a nonsense query (suggests closest ids, never guesses) · `cage --help` (grouped, points at query)
- [ ] `cage limits` (state snapshot, absent → clean message) · credits: no active `[credits]` rows ⇒ **no** credit numbers anywhere (off by default)
- [ ] `cage origin <sha>` (hooked row from C) · `--attest human` (writes heuristic+human pair) · `cage verify` (**always exit 0**) · `cage notes-sync` (dry-run print by default; `CAGE_NOTES_WRITE=1` only if you want a real local write) · `cage ledger-sync` (dry-run) · `--team` view
- [ ] `cage doctor --bundle` → open the archive: doctor report, debug.log, versions, policy provenance, cursors — then `grep` the archive members for any prompt text/paths-with-content → clean
- [ ] MCP: `cage mcp` server + from Claude Code (`.mcp.json`) ask "what did I spend today" → answer matches `cage report`
- [ ] `cage proxy` (point any OpenAI-compatible client at it → call rows land) · `cage watch` (foreground loop, Ctrl-C exits 130) · `cage meter` / `cage graphify` receipt paths if wired
- [ ] Exit codes: bad subcommand → 2; induced user error (e.g. `--since garbage`) → `error: <msg>` + exit 1, full traceback **only** under `CAGE_DEBUG=1`
- [ ] **Pricing (v0.19):** `cage prices list` (bundled vs project origin, `[meta]` versions) · `cage prices unpriced` (each none-match key + ready-to-run fix line) · `set` a price → `report` re-prices **retroactively** (spot-check one historical row's USD changed) · `alias` a router key · `sync` dry-run prints, recommendation line appears when project meta is older · UNPRICED ⚠ summary on report/compare/study report while any none-match rows exist.
- [ ] **Human attention (v0.18):** `cage human`/`trend` show attested vs derived on separate lines, never blended · `cage outcome <task> --minutes 7` → attested beats derived for that task (both visible, never summed) · `cage calibration --human` (measured heuristic accuracy, or refusal below min-n) · `compare`/`verdict`/`study report` print the total-cost line (agent $ + human) with the human method tag; `--agent-only` suppresses it.
- [ ] **CSV (v0.21):** `cage report --csv`, `attrib --csv`, `compare --csv`, `calibration --csv` → RFC-4180, LF endings, method/match tags present as columns, numbers identical to the text view · `cage export --csv calls` (raw rows, PII grep clean) · CSV runs byte-identical twice · one MCP report call with `format: csv` returns the same content.
- [ ] **Cleanup (v0.19):** `cage cleanup` → dry-run listing (file, age, class), nothing deleted · `--apply` removes only allowlist classes · with `[cleanup] days = 0`: ledger/, policy.toml, machine id, study.jsonl, `.cage/bin/` all survive · derived views byte-identical before/after · `CAGE_CLEANUP=0` disables the auto path.

## Part E — The cost-impact loop, end-to-end by hand

The product story in one sitting, in `cage-testbed`:

1. `cage estimate --label docfix --record` (needs ≥ MIN_ESTIMATE_N history — Part C tasks with `--label docfix`; below it, verify the refusal first, then seed more)
2. Do the task with an agent → `cage outcome <task> --label docfix`
3. `cage calibration` → the new task scored against the recorded band
4. `cage compare --label docfix` → agent-only vs agent+tool groups (if graphify wired), delta `estimated`
5. `cage verdict graphify` → composed verdict, all inputs tagged, break-even line
- [ ] Every number traces: `cage query` explains each calculation with **live** values.

## Part F — Fleet study, manually (the multi-laptop story)

Minimum real test = this laptop + one simulated second machine (or a real second laptop if available):

1. This machine: `cage study join baseline` → doctor output + cron line printed; work normally ≥2 days (or backdate via short phases); `cage study start plugin` after wiring graphify; work again.
2. Second machine (or `CAGE_BASE=/tmp/machine2` simulated root): same join/phases; give it a capture gap on purpose.
3. Both: `cage export --study` → one bundle each; check manifest = version + opaque machine id + spans + row counts, **no hostname/username anywhere** (`grep -i "$(hostname)\|$USER"` the bundle → nothing).
4. Analyst laptop, fresh dir: `cage init && cage import bundle1.zip bundle2.zip` → import **twice** → identical totals (idempotent).
5. `cage study report` → coverage first (the gap is flagged), paired-by-machine delta only over complete machines, `estimated` tag + work-mix caveat; with <MIN_COMPARE_N complete machines → the refusal, not a number.
- [ ] Unenrolled sanity: a repo that never ran `study join` writes rows with **no** `machine` field (byte-identical legacy).

## Part G — Invariants under adversarial conditions

- [ ] **Determinism:** run every Part D command twice, `diff` outputs → byte-identical; repeat one with `CAGE_DEBUG=1` → derived output unchanged.
- [ ] **Fail-open write path:** `chmod -w .cage/ledger/` → run an agent session + `cage import` → exit 0, agent unaffected, `debug.log` says why; restore.
- [ ] Truncate the last line of a calls shard mid-row → every view still renders (tolerant tail).
- [ ] Corrupt `policy.toml` (syntax error) → read commands raise `CageError` → `error: …` exit 1; capture still fail-open.
- [ ] **$0/no-network:** run the full Part D suite with Wi-Fi off → identical behavior (a network-denied sandbox, e.g. macOS `sandbox-exec -p '(version 1)(allow default)(deny network*)'`, is an accepted equivalent when the run is driven by a network-attached agent).
- [ ] **PII sweep, whole footprint:** `grep -rE "<a distinctive phrase you typed to an agent>" .cage/ ~/.cage/` → nothing; commit messages absent from tasks/provenance rows.
- [ ] **No scheduler:** confirm cage installed no launchd/cron entries (`launchctl list | grep -i cage`; `crontab -l`) — the scheduler hint is printed, never installed (OS-aware: cron here, schtasks on Windows).
- [ ] **Portable wiring (v0.20):** grep every committed wired file in the testbed for absolute paths → none (except the documented `.kiro/settings/mcp.json` case, gitignore-advised) · clone-simulate (copy testbed sans `.git/.cage/state` to a new path) → `cage doctor` portability clean, shim resolves · legacy check: plant an absolute entry → doctor flags it, `cage setup` migrates it.
- [ ] **Launcher mode (v0.22):** `cage setup --python-launcher` → shims + user-level files interpreter-only (grep: nothing exe-shaped), `[wiring] python_launcher = true`, doctor names the mode · flip to `false` + re-setup → clean revert · `CAGE_RUN_PYTHON=1` honored by the standard shim.
- [ ] **Zipapp (v0.22):** build `cage.pyz` locally per docs/restricted-environments.md → `python3 cage.pyz --version` shows `(zipapp)` · `demo` reproduces §4.4 · `report` over the testbed ledger byte-identical to the installed cage's output.
- [ ] **Docs hygiene (v0.22.1):** `docs/` root = living docs + active pairs only; every shipped pair archived + linked from its CHANGELOG entry; no broken `docs/…` links in README/CHANGELOG (grep); CLAUDE.md carries the docs-lifecycle rule.
- [ ] Version/docs: `cage --version` = <version under test> = CHANGELOG top entry; README test count = Part A count.

## Findings table (fill as you go)

| # | Part/step | Agent×surface | Expected | Actual | Severity (blocker/bug/paper-cut) | debug.log line? |
|---|---|---|---|---|---|---|

**Done means:** Parts A–G all checked or N/A-with-reason; any fixture whose real log format has drifted since the last run re-captured as a sanitized sample (or a finding explains why not); findings triaged into fix-now vs backlog. Fixture replacements go through a normal review — **commit nothing during the test run itself.**
