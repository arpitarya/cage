# IMPLEMENTATION.md — running build log

What is *actually built*, milestone by milestone. Newest first. One entry per small
milestone (green checkpoint / commit / phase step). This is a log, never spec —
where it disagrees with `CLAUDE.md` or the plans in `docs/`, those win.

Entry format:

```
## YYYY-MM-DD — <milestone>
- Implemented: <what, concretely>
- Files: <touched paths>
- Tests: <green | red (why) | not run>
- Next: <the immediate next step>
```

---

## 2026-08-14 — CLAUDE-METRICS: `.cage/ledger/claude/`, the per-chat Claude metrics ledger

- **Implemented:** a new capture-only row kind, deliberately separate from `calls`
  (`schema.make_claude_metric` — no credits field at all, unlike `make_call`/
  `make_copilot_metric`, because no credit unit exists for Claude Code on disk).
  THE DEDUP LAW as code: `transcript._fold_claude_chat` folds duplicate assistant
  rows per `(chat_key, requestId, message.id)`, last occurrence wins — `raw_rows`
  vs `requests` on the emitted row is the inflation evidence (naive summation, what
  `parse_calls` still does, inflates ~2-3×). Chat key = the row's own `sessionId`,
  so a subagent transcript (`<sessionId>/subagents/agent-*.jsonl`) joins its PARENT
  chat and splits into `sidechain_tokens_in/out`, instead of landing in a phantom
  chat keyed by the subagent's own filename (the exact CLAUDE-SUBAGENT-KEY defect,
  dodged not fixed). `importcmd._claude_session_filesets` regroups a sweep's
  changed files into WHOLE session filesets before parsing — a subagent-only
  change still re-reads the main file too (even unchanged), and a fileset whose
  main file doesn't exist keeps going without it, keying purely on row `sessionId`.
  `_ingest_claude_metrics` mirrors `_ingest_copilot_metrics`: own kind (`"claude"`),
  own id namespace (`clm_`), own seen-set from `ledger.claude_metrics_raw`, no
  cursor of its own (rides the calls sweep's `files`). Storage mirrors `copilot/`/
  `kiro/` (`Footprint.claude_dir/claude_shard/claude_shards`, `shard()` routing for
  plain `"claude"`). `ledger.claude_metrics()` collapses last-write-wins per
  `session`, winner = max `(requests, tokens_in+tokens_out, id)` — `credits()`'s
  collapse with `turns` generalized to `requests`. `metric_id` folds the chat's own
  recorded values (never `ts`, deliberately, so an unchanged re-parse dedupes).
  `parse_calls`/`_usage_to_row` (the calls path) are byte-identical — untouched,
  pinned by a test on the same dedup fixture; CLAUDE-DEDUP/CLAUDE-SUBAGENT-KEY stay
  open OPEN-WORK items. `cage doctor` gains `claude-metrics`: raw/collapsed counts,
  plus a retention nudge (Claude Code's own `cleanupPeriodDays` default is 30 days;
  nudges at 25, probing the real transcript store's mtimes — best-effort, never a
  gate). `explain_data.py` gains a `claude-metrics` concept entry; `docs/PLAN.md`
  gains §3.13.
- **Files:** `cage/schema.py` (`make_claude_metric`, `CLAUDE_METRIC_FIELDS`),
  `cage/paths.py` (`claude_dir`/`claude_shard`/`claude_shards`, `shard()` routing),
  `cage/ledger.py` (`claude_metrics_raw`/`claude_metrics`), `cage/transcript.py`
  (`_fold_claude_chat`, `parse_claude_chat_metrics`), `cage/importcmd.py`
  (`_claude_session_filesets`, `_ingest_claude_metrics`, call site in
  `import_claude`), `cage/doctorcmd.py` (`_claude_metrics` advisory + registration),
  `cage/explain_data.py` (`claude-metrics` entry), `tests/test_claude_metrics.py`
  (new, 30 tests), `tests/test_doctor.py` (check-name set gains `claude-metrics`),
  `tests/test_debuglog.py` (allowed debug-key set gains `kind`/`filesets`),
  `docs/PLAN.md` (§3.13), `docs/GLOSSARY.md` (*claude metrics row*, *THE DEDUP
  LAW*, *session fileset*), `docs/claude-capture.md` (refreshed — the new ledger
  section, calls-path defects rescoped to `calls` only, retention nudge now
  present-tense), `work/DOC-REGISTRY.md` (six rows bumped), `docs/README.md`,
  `work/archive/README.md` (new row), pair archived to
  `work/archive/v0.49-claude-metrics-ledger.{handoff,prompt}.md`.
- **Tests:** green — 1768/0 ⇒ 1798/11 skipped (30 new, zero collateral breakage,
  zero goldens re-blessed, `test_floor` untouched).
- **Incident, disclosed and fixed in the same session:** the manual end-to-end CLI
  verification step (`cage import --agent claude` twice on a "scratch ledger")
  omitted the sandbox env vars the pytest suite sets automatically, so it ran
  against the REAL `~/.cage` global ledger instead of an isolated temp dir. Three
  fabricated rows landed (`calls-2026-08.jsonl`, `imports.jsonl`, a new
  `ledger/claude/` dir) tagged `session="sess1"`/`project="claude-scratch"`. Found
  immediately after the run, confirmed exactly one polluting trailing line per
  file, removed both precisely (Python line-surgery, not a blind truncate), and
  deleted the fabricated `claude/` dir — verified clean before continuing.
  `cage.toml`'s content also changed across two follow-up `cage setup --global`
  invocations made while investigating (stabilized on the third); `cage doctor`
  confirms it loads correctly with sane content (51 price rows, correct staleness
  state, `policy-version` un-bumped as designed) but the true pre-incident bytes
  were not backed up, so a byte-exact "no drift" claim can't be made — flagged to
  Arpit rather than asserted. End-to-end verification for the remainder of this
  build relied on the sandboxed pytest suite instead of a second live run.
- **Next:** CLAUDE-METRICS-READ (a read surface) and CLAUDE-METRICS-CSV
  (`cage data export --csv claude`) are parked OPEN-WORK items; the `CLAUDE.md`
  diff (ledger diagram + substrate bullet) is proposed to Arpit, not applied.

## 2026-08-14 — KIRO-METRICS: `.cage/ledger/kiro/`, the per-chat Kiro metrics ledger

- **Implemented:** a new capture-only row kind, deliberately separate from `calls`/
  `credits` (`schema.make_kiro_metric`, `KIRO_METRIC_SOURCES = (ide, cli-conv,
  cli-turn)`) — mirrors COPILOT-METRICS' already-shipped design exactly. Omit-at-zero
  counts, None-sentinel `credits`, the community chars÷4/cumulative/chunk-count trio
  explicitly banned as token facts in the docstring, the 2026-02-28 `tokens_prompt`
  cutover recorded verbatim rather than corrected. Storage mirrors the `copilot/`
  mechanism (`Footprint.kiro_dir/kiro_metric_shard/kiro_metric_shards`, `shard()`
  routing for the plain `"kiro"` kind). `ledger.kiro_metrics_raw`/`kiro_metrics` — the
  latter collapses last-write-wins per `(source, session, turn, row_ref)`, winner =
  max `(turns, tokens_in+tokens_out, id)`. Two parsers in `transcript.py`:
  `parse_kiro_ide_metrics` (stdlib `sqlite3`, `mode=ro&immutable=1`, explicit
  4-column SELECT against `devdata.sqlite`'s `tokens_generated` table, fail-open) and
  `parse_kiro_cli_metrics` (conv + turn rows from the CLI SQLite store). Refactored
  `parse_kiro_cli_credits` first: extracted `_kiro_cli_conversations` (the connect/
  scope/parse loop, now enumerating BOTH `conversations_v2` and the older
  `conversations` table, falling back to a bare `(key, value)` read when the wide
  5-column shape doesn't exist) so the credits and metrics parsers share one read —
  `parse_kiro_cli_credits` became a thin wrapper, and the full existing
  `test_kiro_routing.py`/`test_graphify_kiro.py` suites (43 tests) passed unmodified
  as the byte-identity regression pin. `_ingest_kiro_metrics` mirrors
  `_ingest_copilot_metrics` (own seen-set, fail-open per file/db); the CLI leg hooks
  into `_ingest_credits` right after its credits loop (inherits `workspace` — no
  re-scan, no re-decided scoping), the IDE leg hooks into `import_kiro` after its
  existing source loop (inherits the routed-sink `root` from `_kiro_leg` — zero new
  routing code for the ADR 0006 machine-ledger case). `cage doctor` gains an advisory
  `kiro-metrics` check (per-source counts, plus the upgrade-watch surfaced as
  "armed"/"tripped"). `cage query kiro-metrics` explainer entry + `docs/PLAN.md`
  §3.12. Capture-only: no derived view reads the kind — pinned by a byte-identity
  test (`report`/`insights chats` stdout identical with the `kiro/` tree present vs
  deleted).
- **Files:** `cage/schema.py`, `cage/paths.py`, `cage/ledger.py`, `cage/transcript.py`,
  `cage/importcmd.py`, `cage/doctorcmd.py`, `cage/explain_data.py`, `docs/PLAN.md`,
  `docs/GLOSSARY.md`, `docs/kiro-capture.md`, `work/DOC-REGISTRY.md`,
  `tests/test_kiro_metrics.py` (new, 31 tests), `tests/test_doctor.py` (the
  exhaustive check-name set gains `"kiro-metrics"`).
- **Tests:** full suite green, 1768 passed / 11 skipped (1737 + 31 new), **zero
  goldens re-blessed**, zero collateral test breakage (no new `_builtin_log_sources`
  entries this time — `kiro_devdata_db` is deliberately not registered there).
  `tests/test_debug_coverage.py`, `tests/test_floor.py`, `tests/test_output_spec.py`,
  `tests/test_cli_reference.py` re-run explicitly green.
- **Next:** `work/OPEN-WORK.md` (remove the KIRO-METRICS line, add its two scope-out
  lines), archive the handoff/prompt pair to `work/archive/v0.49-kiro-metrics-ledger.
  {handoff,prompt}.md`, and propose (never silently apply) the `CLAUDE.md` diff for
  the ledger diagram + kiro adapter bullet in the session's final summary.

## 2026-08-14 — COPILOT-METRICS: `.cage/ledger/copilot/`, the five-store per-chat metrics ledger

- **Implemented:** a new capture-only row kind, deliberately separate from `calls`
  (`schema.make_copilot_metric`, `COPILOT_METRIC_SOURCES = (chat, cli, sidecar,
  debuglog, otel)`) — omit-at-zero counts, None-sentinel `credits`/`session_credits`/
  `nano_aiu`, a strict `model_totals` field whitelist. Storage mirrors the `savings/`
  mechanism (`Footprint.copilot_dir/copilot_shard/copilot_shards`, `shard()` routing for
  the plain `"copilot"` kind). `ledger.copilot_metrics_raw`/`copilot_metrics` — the
  latter collapses last-write-wins per `(source, session, surface, request, call)`,
  winner = max `(tokens_in+tokens_out, credits or -1, id)` — generalizing the
  `ledger.credits()` collapse. Five parsers in `transcript.py`:
  `parse_copilot_vscode_metrics` + `parse_copilot_cli_metrics` (always-on; the latter
  cumulative-verbatim, never delta'd, dodging the v0.44 CLI delta-loss bug by
  construction) and three gated-store parsers — `parse_copilot_sidecar_metrics`,
  `parse_copilot_debuglog_metrics`, `parse_copilot_otel_metrics` (stdlib `sqlite3`,
  `mode=ro`) — the latter two whitelist-read only, next to prompt bodies the same lines
  carry. `_vscode_chat_requests` extracted as a pure refactor (existing vscode calls
  fixture stays byte-identical) so the calls and metrics vscode parsers share one
  read+merge pass. Two new chatSessions roots added to `paths._builtin_log_sources`
  (`emptyWindowChatSessions`, `transferredChatSessions`) — calls capture gains these
  chats too, which forced `importcmd._is_chat_session_file` (both parsers' dispatch
  checked a literal `"chatSessions"` parent-dir name, mis-routing the two new roots to
  the CLI parser). `_ingest_copilot_metrics` mirrors `_ingest_credits` (own seen-set,
  fail-open per file/db); wired into `import_copilot`'s existing per-source loop (no
  rescan) plus a new gated-store loop over `paths.copilot_metric_sources()`. `cage
  doctor` gains an advisory `copilot-metrics` check (per-source counts, the enabling VS
  Code setting named for each gated store). `cage query copilot-metrics` explainer
  entry + `docs/PLAN.md` §3.11. Capture-only: no derived view reads the kind — pinned by
  a byte-identity test (`report`/`insights chats` stdout identical with the `copilot/`
  tree present vs deleted).
- **Files:** `cage/schema.py`, `cage/paths.py`, `cage/ledger.py`, `cage/transcript.py`,
  `cage/importcmd.py`, `cage/doctorcmd.py`, `cage/explain_data.py`, `docs/PLAN.md`,
  `docs/GLOSSARY.md`, `docs/copilot-capture.md`, `tests/test_copilot_metrics.py` (new,
  33 tests), `tests/test_platform_paths.py`, `tests/test_path_globs.py`,
  `tests/test_doctor.py`, `tests/test_debuglog.py` (a pre-existing "last src-bearing
  event" test's filter needed to exclude the new `kind`-carrying event, the same way it
  already implicitly excluded credits), `tests/srcseed.py` (env-seed mirror gains the
  two new roots), `work/OPEN-WORK.md` (COPILOT-METRICS removed; two scope-out lines
  added — a read surface and `--csv copilot`, both parked per §3 Out).
- **Tests:** full suite green, 1737 passed / 11 skipped, **zero goldens re-blessed**.
  Manually verified: `cage import --agent copilot` run twice on a scratch ledger appends
  2 rows then 0; `cage doctor` renders the per-source advisory line correctly.
- **Note:** a `CLAUDE.md` diff (ledger diagram line + a substrate bullet) is proposed,
  not applied — flagged for Arpit's review per the standing rule.
- **Next:** archive the handoff/prompt pair to `work/archive/`, update the two doc
  indexes, and get Arpit's call on the proposed `CLAUDE.md` diff. The two scope-out
  items above are the next agent-closable candidates for the read surface.

## 2026-08-13 — GRAPHIFY-CHATS: `cage insights graphify` built, per-chat graphify usage & GROSS saving

- **Implemented:** new `cage/graphifychat.py` — `summarize()` reuses `chats.summarize`
  verbatim for the chat universe and joins `ledger.savings` (`tool="graphify"`) onto it
  by `session` alone (savings rows carry no agent). Per chat: `receipts`, `saved`,
  `raw_alternative`, `actual` (sums), worst-case `method`/`confidence` (the
  `attribution.receipts_by_tool` aggregation, inlined), `tokens = tokens_in + tokens_out`
  (`None` when `from_credits`), `without = tokens + saved` (never clamped), `pct` (`None`
  when `tokens` is `None` or `without <= 0`). Two tallies never fold into a row:
  `unassignable` (shim's `session=""`, GC3) and `unmatched` (a session joining no chat).
  `render_view`: default rows are receipt-bearing chats only (`--all-chats` lifts it),
  ranked `(-saved, session)`, top-20 (`GRAPHIFY_CHATS_DEFAULT_ROWS`, `--all` lifts).
  `render_csv`: untruncated, never filters by receipts, refused cells empty.
- **Files:** `cage/graphifychat.py` (new), `cage/cli.py` (+`insights graphify` parser,
  root-help group listing), `cage/clicmds.py` (+`cmd_graphify_chats`),
  `cage/constants.py` (+`GRAPHIFY_CHATS_DEFAULT_ROWS`), `cage/explain_data.py`
  (+`graphify-chats` entry), `cage/explain.py` (+live value),
  `tests/test_graphifychat.py` (new, 23 tests), `tests/fixtures/cli-help.txt`,
  `tests/test_view_export.py` (`EXPECTED_VIEWS`), `docs/FORMULAS.md` (§2.15),
  `docs/CLI.md` (new command + flags rows, 54⇒55 commands, 16⇒17 insights views),
  `CHANGELOG.md`, `work/DOC-REGISTRY.md`.
- **Tests:** `tests/test_graphifychat.py` (23, all green) + full suite green,
  1704 passed / 11 skipped. Briefly 1703 passed / 1 failed
  (`test_doc_links.py::test_every_live_doc_link_resolves`) while a concurrent
  Cowork session's `docs/copilot-capture.md` work was still uncommitted in this
  same tree — verified unrelated at the time (dangling links named files this
  change never touched), and resolved once that session's docs landed.
- **Next:** archive the handoff/prompt pair on implement; surface the CLAUDE.md
  views-list edit for Arpit's review (never silently applied).

## 2026-08-13 — REPORT-CREDITS: `cage report` gains a credits column

- **Implemented:** on Arpit's decision ("report should show credit and for token it
  should say N/A"), `report.summarize` now folds `ledger.credits` in on the `agent`
  and default `route` dims (a synthetic `"credits"` route bucket, since a credits row
  carries no `route` field; other dims left untouched — a credits row doesn't carry
  `model`/`task` cleanly, and `cage insights chats` §2.13 already owns the
  per-conversation view). A `credits` column appears only when the view actually
  joined one (byte-identical text/CSV otherwise, no golden re-bless needed). A
  credits-only group's `calls`/`tok in`/`tok out` render `—` in text / **empty** in
  CSV; cost prices only through `[billing.<agent>] usd_per_credit`, the same rung
  `chats.py` uses.
  **Two real bugs found and fixed before writing tests, both via manual exercise of
  the real ledger:** (1) a variable-name collision — the credits loop's local `cred`
  clobbered the pre-existing `cred` dict (the COPILOT-CREDITS per-call ladder
  summary), raising `TypeError: 'float' object is not subscriptable` on any
  `--by agent` report; renamed to `cr_val`. (2) the TOTAL row's cost cell silently
  DROPPED a rated credits dollar whenever any other group had real calls (`total["
  calls"]` nonzero routed it past the credits-only branch straight to `g["usd"]`
  alone) — understating spend, the one thing a total must never do. Fixed by summing
  `usd + credits_usd` whenever `credits_rated`, in both `_cost_cell` and the CSV cell
  builder, plus a matching fix to `net_usd` (was subtracting only `g["usd"]`, so `net
  vs spend` could overstate a saving), and a new footnote naming the split
  (`· total spans two pricing bases: …`) whenever both bases are non-zero.
- **Files:** `cage/report.py` (`_new_group`, `summarize`, `_cost_cell`, `_row`,
  `render_report`, `render_csv`), `tests/test_report_credits.py` (new, 17 tests
  covering the render contract, the N/A cells, the rate ladder, the mixed-bucket sum,
  CSV emptiness/method, `--since`, and determinism), `docs/FORMULAS.md` §1.7,
  `CLAUDE.md` (new architecture bullet after "Per-call cost"), `CHANGELOG.md`,
  `README.md`/`CLAUDE.md` test counts, `work/OPEN-WORK.md` (REPORT-CREDITS? removed).
- **Tests:** green, 1662/0 ⇒ 1679/0. `test_floor.py`/`test_cli_reference.py`/
  `test_output_spec.py` unchanged and green; no golden needed re-blessing.
- **Next:** no agent-closable or Arpit-decides items remain from this thread;
  `work/OPEN-WORK.md`'s CHATS-CREDITS-adjacent work is fully closed.

## 2026-08-13 — CHATS-CREDITS: kiro-CLI conversations render as chat rows

- **Implemented:** `cage insights chats` now reads `ledger.credits` alongside `calls`
  and buckets a credits row into its own chat (never blended with a call bucket — a
  trailing discriminator in the bucket key keeps the two shapes structurally apart).
  A credits-only chat renders `calls` and all four token cells `—` (text) / empty
  (CSV), `credits` filled, cost priced only through `[billing.<agent>] usd_per_credit`
  (unset ⇒ `—`, `0.0` ⇒ `$0.0000`). Rank gains a second key
  (`-tokens_in, -(credits or 0.0), session`). CSV `method` reports the row's own
  `estimated` when unrated, `modeled` when rate-priced (a plain `creditprice.
  method_for` on an empty basis would have overclaimed `measured`). The false
  "`cage report` counts it" refusal and its `_credit_agents` machinery are gone —
  nothing else ever read `ledger.credits`, so the fix pointer was never true for the
  one agent that could trigger it. `agent%` refuses for kiro via the existing
  `authorcapture.COVERAGE_GAPS` path, no new authorship logic.
- **Files:** `cage/chats.py` (summarize, both renderers, docstring), `cage/ledger.py`
  (`credits` docstring re-word), `tests/test_chats.py` (3 stale tests rewritten, 10
  new), `docs/FORMULAS.md` §2.13, `cage/explain_data.py` (`chats-view`),
  `docs/GLOSSARY.md` (`chat (view)`), `CHANGELOG.md`, `README.md` (test count),
  `CLAUDE.md` (`just test` count — the chats-bullet correction is proposed, not
  applied, see WORKLOG), `work/OPEN-WORK.md`.
- **Tests:** green, 1662/0 (was 1655/0 — net +7: 3 rewritten in place, 7 wholly new).
  `test_floor.py` / `test_cli_reference.py` / `test_output_spec.py` unchanged and
  green; no golden needed re-blessing (no existing golden fixture records a credits
  row).
- **Next:** Arpit reviews the proposed `CLAUDE.md` chats-bullet edit (see WORKLOG); no
  agent-closable work remains in `work/OPEN-WORK.md`.

## 2026-08-12 — WORK-DIR: the five session-tracking docs moved to root `work/`

- **Implemented:** on Arpit's explicit instruction, `IMPLEMENTATION.md`, `INTERVIEW.md`,
  `MACHINE.md`, `OPEN-WORK.md`, `WORKLOG.md` moved from `docs/` to a new root `work/`
  directory via `git mv` (history preserved). `docs/` stays the design/reference tree;
  `work/` is now the session-tracking tree. Every live-doc markdown link that resolved
  through the old `docs/<file>` path was mechanically rewritten (a script that mirrors
  `tests/test_doc_links.py`'s own resolve logic, run across every tracked `.md` file
  except `work/archive/**`, `work/regression/**`, and `CHANGELOG.md`, which stay
  frozen history) — 11 live files changed, plus the moved docs' own outgoing links.
  `tests/test_doc_links.py`'s `HISTORY_FILES` set (which exempts `WORKLOG.md`/
  `IMPLEMENTATION.md` from the dangling-link gate) was repointed to the new `work/`
  paths; `tests/test_queue_honesty.py`'s `QUEUE` constant likewise. `CLAUDE.md`'s
  ALL-CAPS-tracker-location note, the *Documentation discipline* section's five
  bullets, and every other prose/link mention across `CLAUDE.md`/`work/DOC-REGISTRY.md`/
  `docs/PLAN.md`/`docs/README.md`/`docs/CLI.md`/`work/cage-lab/README.md`/
  `work/compare/README.md`/`docs/doc-size-discipline.md`/`cage/explain_data.py` were
  hand-fixed where the script's mechanical link rewrite didn't reach (bare prose,
  backtick-only mentions, a stale `§I.2a` section citation). **On a separate explicit
  instruction, `work/OPEN-WORK.md` was additionally stripped** from a header +
  11-row closure table down to a bare "the queue is empty" statement — the closure
  history remains in `work/archive/` and this file, just no longer indexed from
  OPEN-WORK.md itself.
- **Found in passing, fixed on contact:** `docs/restricted-environments.md` had been
  deleted a *second* time (first was the v0.36 hookless sweep, restored then because
  eight source files still cited it — see the 2026-08-11 `GF-LAUNCHER` entry below) by
  the prior uncommitted session's queue-closure sweep, with no citation migration and
  no recorded decision to remove it — six live citations across `CLAUDE.md`, `README.md`,
  `work/DOC-REGISTRY.md`, `work/compare/gf-launcher-metering.compare.md` (×2), and
  `docs/shim-contract.md` went dangling. Restored via `git checkout HEAD --
  docs/restricted-environments.md` rather than migrating the citations, since every
  citing doc still describes its content as current.
- **Files:** `work/{IMPLEMENTATION,INTERVIEW,MACHINE,OPEN-WORK,WORKLOG}.md` (moved),
  `CLAUDE.md`, `work/DOC-REGISTRY.md`, `docs/PLAN.md`, `docs/README.md`, `docs/CLI.md`,
  `work/cage-lab/README.md`, `work/compare/README.md`, `docs/doc-size-discipline.md`,
  `cage/explain_data.py`, `tests/test_doc_links.py`, `tests/test_queue_honesty.py`,
  `docs/restricted-environments.md` (restored).
- **Tests:** green, 1655 passed / 11 skipped (`just test`'s pinned count unchanged —
  no test added or removed, only two tests' path constants updated).
- **Next:** commit, then Arpit's follow-on instruction (merge to main, delete stale
  branches, publish a new version) — see `WORKLOG.md` for the check-in on that.

## 2026-08-12 — the queue closed wholesale: 16 docs archived unbuilt, OPEN-WORK emptied

- **Implemented: nothing.** This is a *decision* recorded, not work built — Arpit
  instructed that all open items and all parked proposals be closed and archived. Every
  one of the 16 was `status: proposed` or blocked on his hands/decision; **none was
  built**, so each archive header says *closed by decision, never built* and names what
  it left unresolved, rather than the usual *implemented, living spec is X*.
- **Archived (11 items):** NET-1 · SHIM-TOOL-DEPS · L1-FIELD · KIRO-MCP-FIELD · HR-FIELD ·
  GFX-KIRO-RATE · TOOL-SDK · COPILOT-SIDECAR · POLICYSYNC-FIXTURE · KIRO-CLI-SCOPE ·
  OUTPUT-GROWTH → `work/archive/v0.49-*.item.md`.
- **Archived (5 proposals):** net-positive-evidence-run · tool-integration-contract ·
  larger-lab-corpus · policysync-synthetic-bundle · attest-join-command-normalization →
  `work/archive/v0.49-*.proposal.md`.
- **Archived (3 directory docs):** `open/CONSTRAINTS.md` · `open/README.md` ·
  `proposals/README.md`. **`docs/open/` and `docs/proposals/` no longer exist.**
- **What this leaves unresolved, stated once so it is not lost:** cage has still never
  measured a tool netting positive (NET-1); **SHIM-TOOL-DEPS is a measured defect closed
  unfixed** — with no `grep` on PATH the shipped POSIX twin selects itself and re-execs
  forever, a reproduced 120s hang; and `cage setup --status` still tells users copilot/kiro
  auto-close is wired with no machine ever having verified it (L1-FIELD Q1/Q2).
- **CONSTRAINTS.md is the one that could quietly cost something.** It was never open work.
  Its rules were archived with the directory and **not migrated into CLAUDE.md**; its
  header splits them into those enforced mechanically (`tests/test_floor.py`,
  `agents.SURFACES`, `wiringscan`, `attest.LIMIT`) and five carried by prose alone, which
  are now at risk: the frozen lab corpus, the "unverified on a real Copilot" honesty
  requirement, the `--hooks`-off-by-default trap, F2's UNTESTED VS Code receipt limit, and
  the `test_portable_wiring.py`-never-existed correction.
- **Files:** `docs/OPEN-WORK.md` (rewritten as an empty queue + closure table) ·
  `work/archive/` (+16 files, new sweep section in its README) · `CLAUDE.md` (three rules:
  compare-on-a-fork, the proposal lifecycle, the OPEN-WORK maintained-doc bullet; plus the
  OUTPUT-GROWTH citation) · `docs/README.md` · `work/DOC-REGISTRY.md` (6 rows) ·
  `docs/FIELD-RUNBOOK.md` · `docs/GLOSSARY.md` · `docs/shim-contract.md` ·
  `work/compare/README.md` · `work/cage-lab/README.md` · `cage/viewexport.py`.
- **Tests:** see the verification note in the same-day WORKLOG entry.
- **Next:** Arpit deletes the two now-empty directories and `_to_delete/`, and decides
  whether SHIM-TOOL-DEPS stays closed — it is the only closure that is a live defect
  rather than an unstarted idea.


## 2026-08-12 — GF-LAUNCHER verdict B built: the interceptor reaches cage without a `cage` command

- Implemented: **B5 arm 2** in both twins. When no `cage` command resolves, they probe
  `python3 -m cage` (POSIX) / `py -3` then `python` (Windows, new permanent divergence
  **D8**) and meter through it. Arm 1 is still tried first, so a standard install pays
  no interpreter start. B3's marker set is **unchanged** — `cage data graphify` is still
  a substring of the arm-2 invocation, so twins still skip each other.
- `doctorcmd._launcher_gap` **inverted**: it no longer warns that launcher mode means
  unmetered (that stopped being true). It asks whether the interpreter winning on PATH
  can import cage — the `kiro-mcp` silent-start class — and warns only when it cannot.
- **Verified by execution, not by grep.** `tests/test_gf_launcher_arm2.py` runs the POSIX
  twin with no `cage` on PATH and asserts a real receipt lands; also that arm 1 wins
  first, and that a genuinely-unreachable cage still passes through unmetered. The cmd
  twin is contract-asserted + CI. Honest close: **fixed on POSIX, CI-asserted on
  Windows** — never "fixed".
- **One test was rewritten rather than relaxed.** `test_cmd_twin_reads_the_exit_code_on_its_own_line`
  asserted `count("exit /b %ERRORLEVEL%") == 2`, a proxy for two branches; arm 2 makes it
  four. Bumping the literal would have let the new branches ship unchecked, so it now
  asserts the D1 **contract** — every `call` forwarding `%*` is followed immediately by
  the exit line — which binds any number of branches, including future ones.
- **A defect was found that the compare doc did not predict**, and it is not GF-LAUNCHER's:
  B3's content check shells out to `grep`/`findstr`, so on a PATH where that tool does not
  resolve, every candidate reads as *not an interceptor* and a twin selects **itself**,
  re-execing forever. Measured as a 120s hang, pre-existing in every shipped version.
  Filed as **SHIM-TOOL-DEPS** with the fork unresolved — a hang is a worse failure shape
  than either a refusal or an unmetered run, which is the asymmetry that should decide it.
- **A harness bug worth recording**: the first version of the arm-2 test set
  `CAGE_BASE=<proj>` and read `ledger.receipts(proj)`. `CAGE_BASE` names the cage root
  *directly*, so the shim wrote `<proj>/ledger/…` while the assertion read
  `<proj>/.cage/ledger/…` — the feature worked and the test said it did not. Found by
  reproducing the run by hand rather than by trusting the red.
- Files: `cage/data/shims/graphify` · `cage/data/shims/graphify.cmd` · `cage/doctorcmd.py`
  · `tests/test_gf_launcher_arm2.py` (new) · `tests/test_win_graphify_shim.py` ·
  `docs/shim-contract.md` (B5b + D8) · `docs/restricted-environments.md` ·
  `work/compare/gf-launcher-metering.compare.md` (verdict accepted) ·
  `docs/open/SHIM-TOOL-DEPS.md` (new) · `docs/open/GF-LAUNCHER.md` (deleted) ·
  `docs/OPEN-WORK.md` · `CHANGELOG.md`
- Tests: green — **1650 ⇒ 1655** (+5 arm-2; the cmd-twin exit-code test was rewritten,
  not added).
- Next: Arpit's call on SHIM-TOOL-DEPS' fork; the remaining queue is field work only.

---

## 2026-08-12 — the agent lane refilled: P0·P1·P2 built, P3 read-only

The four items in `docs/open-queue-agent-lane.handoff.md` — the only agent-buildable work
left in the queue. **Baseline re-measured before anything moved: 1639 passed / 0 failed /
11 skipped.** The figure the queue had been carrying was correct, but it had been an
assertion for eleven days.

- **P0 — the `docs/open/` migration finished in the law.** The 2026-08-11 restructure had
  moved the queue's detail into `docs/open/` and indexed it nowhere. `docs/README.md` now
  lists it under *Current spec* beside the index it details (and re-describes OPEN-WORK as
  an index, naming its new gate); `work/DOC-REGISTRY.md` gained its row with the trigger
  *an item opens, closes, or changes gate*. *Active work* re-opened for this handoff,
  recorded as **handoff-only** — its prompt was handed over inline and never written to
  `docs/`, so there is no `.prompt.md` to archive with it.
  **The `CLAUDE.md` correction is PROPOSED, not applied** — surfaced as a diff for Arpit.
- **P1 — `tests/test_queue_honesty.py`.** Fails only on a *contradiction* between the
  queue header's checkable claims (version · tag · clean-and-pushed) and git; silent when
  the header claims nothing; skips when ground truth is unavailable. Counts are not gated.
  **Two false negatives were found by falsifying the real file, not by reading the
  regex** — and both would have left the gate green while reading nothing: (a) the
  past-tense filter swallowed a live claim fused to it across `.**`, (b) the matcher
  wanted bare `HEAD == origin/main` while every claim in this repo is written
  `` `HEAD` is `origin/main` ``. Each earned its own test. Mutation-checked in both
  directions: stubbing `contradictions` reddens 4 tests, removing the past-tense filter
  reddens exactly 1 — the right one.
- **P2 — L1-FIELD Q3 answered, and one cause fixed.** Three producers write `args_hash`;
  the shim route folded in `argv[0]` (`$REAL`, an absolute machine-specific path) while
  the hook and transcript route hash the tail, so the exact join was structurally unable
  to fire. Established by **reconstructing all three real attestations from the Claude
  transcripts and re-hashing them**, not by inference. Fixed forward-only in
  `graphifymeter.run`. **Judged a fix, not a capture change**: no new field, no schema
  change, and the convention was already documented in `content_signature` and already
  implemented by two of three producers. **Necessary, not sufficient** — a piped
  invocation still misses (cause 2, parked as a proposal) and an attested run can have no
  usage row at all (cause 3, reported not fixed). No test caught it because every existing
  test built its usage row by hand with the *attestation's* convention, asserting one
  side's code against itself.
- **P3 — commit hygiene, read-only.** 65 staged files / 8 unpushed commits inventoried and
  a split proposed in the session response. **Nothing pushed, tagged, or discarded.**
- Nine of eleven queue items were **not touched, simulated, or prepared** — they need a
  real Copilot/Kiro/second repo or a trigger that has not fired.

- Implemented: `docs/README.md` + `work/DOC-REGISTRY.md` (`open/` row) · new
  `tests/test_queue_honesty.py` · `graphifymeter.run` hashes `cmd[1:]` + its first
  real-interceptor test · `work/regression/2026-08-12-l1-attest-args-hash-mismatch.md` ·
  `docs/proposals/attest-join-command-normalization.proposal.md` · `docs/open/L1-FIELD.md`
  Q3 · FORMULAS §2.11/§2.12 · CHANGELOG v0.49.0 · the queue header de-staled (47 → 65
  files, suite figure now measured).
- Files: `cage/graphifymeter.py` · `tests/test_queue_honesty.py` ·
  `tests/test_hooks_layer.py` · `docs/{README,DOC-REGISTRY,OPEN-WORK,FORMULAS}.md` ·
  `docs/open/L1-FIELD.md` · `docs/proposals/{README,attest-join-command-normalization}.md` ·
  `work/regression/{README,2026-08-12-l1-attest-args-hash-mismatch}.md` · `CHANGELOG.md`
- Tests: **green — 1650 passed / 0 failed / 11 skipped** (1639 → 1650; +10 queue-honesty,
  +1 real-interceptor join).
- Archived on implement: the handoff moved to
  `work/archive/v0.49-open-queue-agent-lane.handoff.md` with its header naming the three
  ways the build corrected it; `docs/README.md` *Active work* emptied, archive index and
  CHANGELOG *Built from* updated, `INTERVIEW.md` state-of-play rewritten. **No prompt
  doc exists to archive** — it was handed over inline, recorded rather than fabricated.
- **OPENWORK-SECTION-REFS filed and CLOSED in the same session.** Five live citations
  named OPEN-WORK sections the 2026-08-11 restructure deleted — found while drafting the
  `CLAUDE.md` diff, whose line 953 was one of them. All five re-pointed at a surviving
  home and made **explicitly past-tense** ("raised as §G.1; that section is gone — the
  standing note is now here"), per the removed-doc citation rule: `constants.py` +
  `FORMULAS.md` §2.10 (the 0.3 confidence note) · `pathshim.py` → `wiringscan` /
  `cage query stale-wiring` · `viewexport.py` → `docs/open/OUTPUT-GROWTH.md` ·
  `explain_data.py` (bare `OPEN-WORK.md` → a resolvable path) · `CLAUDE.md`'s lab-PATH
  rule. **The residual is the interesting part and is carried forward in the item's
  place:** `test_doc_links.py` structurally cannot see this class — they are bare prose,
  not markdown links — and OPEN-WORK no longer *has* stable sections to anchor to, so the
  honest fix is *stop citing sections*, not *gate them*. Recorded here rather than left as
  a queue row, since nothing remains to do.
- **The `CLAUDE.md` correction was APPLIED** (2026-08-12), on Arpit's explicit go — the
  *Documentation discipline* OPEN-WORK bullet now describes the index-plus-`docs/open/`
  shape, names the queue-honesty gate, and records **why counts are not gated**.
- Next: Arpit's call on the proposed `CLAUDE.md` diff and the commit split; then push the
  65 files, then [NET-1](../docs/open/NET-1.md).

---

## 2026-08-11 — the queue emptied: five held decisions taken, two doc programs built

The seven items that made up tiers 2 and 3 of `OPEN-WORK.md`, closed in one session.
**Every one of them was a decision that had been deliberately withheld from a fix
commit**, so the record of *why* matters more than the diff.

- **Implemented — COMMITS-WINDOW (verdict B).** `commitview.summarize(limit=…)` bounds
  the read at the row cap, applied **before** the per-commit `git show` rather than after
  every row has paid for one. Text path only: `--csv`/`--json` stay complete, `--all`
  lifts it, `sha` (detail) is never capped. Dropped commits land in `limited_out` and are
  footnoted as **not read** — the Σ row covers only what was read, so "N more" alone would
  have let a bounded total read as a whole-history one. A default relative `--since` was
  rejected (a wall clock in the default path; it also bounded *nothing* when measured).
- **Implemented — COPILOT-PREMIUM-DEAD.** The `premium` column is gone from the chats
  text table and CSV; the field is untouched and still summed into the payload, so
  `--json` keeps the recorded fact. It is `floor(credits)` — a lossy duplicate of the
  column beside it — and the earlier framing ("can only print 0") was itself an
  over-claim: it prints 0 whenever credits < 1, and merely rounds otherwise.
- **Implemented — REV-CREDITS defect 2 (one basis per shutdown).** New additive-optional
  call field `billed_with` + pricing **rung 0**: every non-carrier row of a credit-bearing
  copilot shutdown links to the carrier and prices at `$0.00` **on the credits basis**,
  with the carrier's id as the matched key. Reports the **same** `credits` match kind as
  rung 1 on purpose, so every consumer that already excludes a credits-priced row from
  token-derived reasoning inherits it with no per-view fork. Suppression is conditional on
  a rate existing. **Pro-rata by token share was rejected** — it would derive credits from
  tokens. **Forward-only**; carried as `CREDITS-LEGACY-SPLIT`.
- **Implemented — OTEL-SEMCONV-PIN.** Verification changed the answer: the GenAI repo has
  **no tagged release** (changelog is `## Unreleased`, everything `Status: Development`),
  so option 3 as written was impossible. The pin now *states what it pins* —
  `OTEL_SEMCONV_VERSION_MEANS` + `_SOURCE` + a maturity string — rather than inventing a
  version. `gen_ai.system` → `gen_ai.provider.name` (renamed in semconv v1.37.0, five
  releases before the pinned one). Emitting both rejected: a consumer that sums rather
  than coalesces would double-count. **Breaking for `--otel` consumers.**
- **Implemented — CLI-GAPS(b).** `prices`/`study`/`policy` are real subparsers. Each
  action owns its `--help` and its own flags, so an inapplicable flag is an argparse
  usage error (exit 2) instead of a flat union plus a runtime refusal — `cmd_study`'s
  `--csv`/`--export` refusals were deleted as unreachable, and `study report` became a
  real parser leaf (`VIEW_LABELS` is now empty).
- **Implemented — STEERING-EDITS.** All six held `CLAUDE.md` edits applied (A·B·C·D·F·G).
  **Two landed amended by the same day's work**: A gained the commits cost bound, B's
  per-call bullet gained rung 0. Proposal archived.
- **Implemented — DOC-LINK-CHECK.** `tests/test_doc_links.py`: case-sensitive against
  `git ls-files`, never the filesystem. **Policy: LIVE fails, HISTORY is exempt and
  counted.** A naive walker was red on **155** links, nearly all history pointing at pairs
  that gained a `vX.Y-` prefix when archived — those were correct when written, and
  rewriting a dated record to keep a link green would falsify the record. Links inside
  code spans/fences are illustrations, not citations. Repaired **15** live dangles.
- **Two OPEN-WORK items were already built at HEAD** and the file still listed them as
  pending: REV-HARDEN P2's adoption `--since` double-filter and the fabricated `$0`
  (`convert.saved_usd_opt`). Fourth staleness in that file in a week — its markers are
  not evidence.
- Files: `cage/commitview.py` · `cage/clicmds.py` · `cage/constants.py` · `cage/chats.py`
  · `cage/schema.py` · `cage/transcript.py` · `cage/creditprice.py` · `cage/prices.py` ·
  `cage/otelout.py` · `cage/explain.py` · `cage/explain_data.py` · `cage/cli.py` ·
  `CLAUDE.md` · `README.md` · `docs/{OPEN-WORK,FORMULAS,CLI,README,doc-size-discipline}.md`
  · `work/compare/copilot-pricing-basis.compare.md` ·
  `work/research/2026-08-03-otel-genai-semconv-pin.md` · `docs/{DOC-REGISTRY,INTERVIEW,WORKLOG}.md`
  · `docs/proposals/README.md` → `work/archive/v0.49-steering-edits-pending.proposal.md`
  · `tests/` (7 files + new `test_doc_links.py`) · 3 chats goldens re-blessed ·
  `tests/fixtures/transcripts/copilot/cli/expected.json`
- Tests: **green — 1639 pass / 0 fail / 11 skipped** (from 1616). Every fix ships a test
  that fails before it; the copilot-CLI fixture corpus proved defect 2 on real fixture
  data (its expected rows are the multi-model shutdown case).
- Next: **the agent lane is empty.** NET-1 and the field verifications are Arpit's;
  `CREDITS-LEGACY-SPLIT` needs a count from a real ledger before any code.

---

## 2026-08-11 — agent-lane sweep P6: EXPORT-SCOPE — the last three report-shaped views

- **Verified against the live parser first:** `cage authorship summary`, `cage study
  report` and `cage task quality` had `--csv`/`--json` but no `--export`/`--stamp`.
- **Implemented:** `_export_flags` on all three, and each handler routed through
  `cliutil.emit(..., csv=…, root=…)`.
- **The cause was the same in two of them, and it is worth naming:** both kept a
  **hand-rolled `csv_dest` branch** ahead of `emit` — exactly the duplication the
  chokepoint was created to delete in v0.48.0. That branch is why they were skipped, and
  it bit again mid-change: the first wiring of `study report` produced an artifact with
  **no CSV for a view that owns a `render_csv`**, because the branch shadowed it. An
  artifact missing a format the view has is the same lie as an empty file, only quieter.
- **`study` needed a decision:** its action is a **positional**
  (`join|start|stop|report|id`), not a subparser, so the flags necessarily sit on the
  group and are reachable from the marker verbs. `cmd_study` **refuses** them on any
  action but `report`, mirroring the guard `--csv` already had — silently writing an
  artifact for `cage study id` would be worse than the refusal.
- **The gate did its job in both directions.** `EXPECTED_VIEWS` failed the moment the
  flags appeared without being listed, naming all three. Its key is the parser **leaf
  path**, so `study` is listed bare while its `view=` label is `study report` — recorded
  in a `VIEW_LABELS` map rather than by loosening the assertion.
- **`test_export_never_changes_stdout` extended to all three** — the binding gate of the
  whole artifact surface, and the new views are held to it, not exempted from it.
- **Files:** `cage/cli.py` · `cage/clicmds.py` · `tests/test_view_export.py` ·
  `docs/CLI.md` · `docs/*`.
- **Tests:** green — **1609 ⇒ 1616**, 11 skipped.
- **Next:** the sweep is complete. **COMMITS-WINDOW** is the one open decision it raised
  ([compare](../work/compare/commits-view-cost-bound.compare.md)).

## 2026-08-11 — agent-lane sweep P5: HR-COPILOT-JOIN — copilot VS Code rows carry a project

- **Both claims verified first.** `parse_copilot_vscode_calls` built rows with no
  `project=` (the only stamping sites in the package were claude and kiro-CLI), and
  copilot/vscode is *already* whitelisted for window-joining — so `ts_fidelity` passed
  and every row fell straight through to `commitjoin`'s `project` gate and was dropped
  `NO_PROJECT`. **The join was built and could not fire for any copilot call, ever.**
- **The handoff's framing correction is the load-bearing part, and it held.** The store
  *does* carry a cwd, but "following the claude precedent … it window-joins for free" is
  false: claude's `cwd` sits on the very record the row is built from, and here it does
  not — the per-request serialized fields carry no cwd at all. The real precedent is
  **kiro CLI**: a *store-level* cwd resolved once per file, before the row loop. Built
  that way.
- **Implemented:** `transcript._vscode_project` resolves one project per chat-session
  file — `workspaceStorage/<hash>/workspace.json` → `{"folder": "file:///…"}` first (one
  read, covers every request), falling back to the first `toolSpecificData.cwd.path`
  (exact but partial — only requests that ran a terminal command), else `""`. Basename
  only, percent-decoded, same PII guard as `scope`/tasks.
- **The three decisions, made and recorded in the module docstring:**
  1. **Multi-root workspaces fall through, they are not guessed.** VS Code stores a
     `"workspace"` key (a `.code-workspace` path) naming *several* roots; stamping its
     basename would put a whole chat's spend on something that is not a working
     directory. Carrier 1 declines and carrier 2 gets a chance — a terminal command's cwd
     is a real directory and is better evidence than the workspace file.
  2. **A `--path` run fails open to `""`.** The log is read from a relocated tree where
     `parents[1]` is no longer the `workspaceStorage/<hash>` dir, so a `workspace.json`
     found there could belong to something else. The layout is **checked** — the file's
     own parent must be named `chatSessions` — never assumed.
  3. **Percent-decoding**, because `my%20project` matches nothing a `--project` filter or
     a commit join would look for.
- **The fixture gap the handoff flagged was real and is closed.** No `workspace.json`
  existed anywhere in the repo, so the fix would have shipped untested against a golden
  that legitimately stayed `project: ""`. Added a **sidecar** mechanism to
  `tests/test_fixture_corpus.py` (files a store keeps *beside* the log that the parser
  also reads, planted at their real relative layout — the parser checks that layout) and
  planted one. `test_floor.py` needed none: it plants only CLI fixtures.
- **Corrected on contact:** `schema.py`'s `project` docstring asserted "Copilot/Kiro leave
  it empty" flatly — false for two of those four routes even before this change (kiro CLI
  has stamped it since v0.36).
- **Files:** `cage/transcript.py` · `cage/schema.py` · `tests/test_transcript.py` ·
  `tests/test_commitjoin.py` · `tests/test_fixture_corpus.py` ·
  `tests/fixtures/transcripts/copilot/vscode/{workspace.json,expected.json}` · `docs/*`.
- **Tests:** green — **1600 ⇒ 1609**, 11 skipped. Removing the `project=` stamp fails the
  golden corpus row-for-row.
- **Next:** P6 — EXPORT-SCOPE (additive; three report-shaped views v0.48.0 missed).

## 2026-08-11 — agent-lane sweep P4: REV-HARDEN P4's judgment half (3 items, sha rewrite last)

- **Landed 4.1 → 4.2 → 4.3, each verified first, the sha rewrite last** as the handoff
  required — it rewrites the field the other items' tests had just been written against.
- **4.1 rename syntax.** `git show --numstat` renders a rename as `old.py => new.py` or
  `d/{a => b}/f.py`; neither can key-match a `+++ b/<path>` line, so a renamed file's
  counts went to a phantom key and the file itself scored **DROPPED**. New
  `linematch.numstat_path` resolves both to the **destination** and is shared by
  `commit_diff` and `originrecord.commit_numstat` — the two keep duplicate `_NUMSTAT`
  patterns, which is exactly how this class survives. Both degenerate braced forms
  (`{ => d}/x.py`, `d/{a => }/x.py`) are handled and tested; a path genuinely containing
  `" => "` is inherently ambiguous in this porcelain and is documented as such.
- **4.2 Edit context lines counted as `suggested`.** `old_string` was read **nowhere** in
  the package. An `Edit`'s `new_string` is a replacement *block*, not a diff, so every
  re-stated anchor line entered `suggested` — and `kept_modified` via
  `modified = suggested − kept`.
- **The design call, made and written down:** the subtraction lives in **`linematch`**
  (`subtract_context`), not `transcript`. Deciding whether a proposed line is the same as
  a context line *is* matching, and rule 1 of that module says only it may normalize for
  matching; `transcript._context_lines` transports raw `old_string` and compares nothing.
  Consumes 1:1, never touches a sub-gate line (that would move lines out of `unknown`).
- **The harm is stated at its real size, not oversold** — inflation was certain; false
  *agent credit* additionally needed a context line to coincide with a human-added one,
  which `MIN_MATCH_CHARS` and 1:1 consumption make possible, not routine. The opposite
  error (an agent legitimately re-adding an `old_string` line is now under-credited) is
  in the docstring, with why that is the right direction to err. `Write`/`NotebookEdit`
  have no `old_string`, so their inflation is **named, not fixed**. Historical rows keep
  the old counts — provenance is frozen by its idempotency key.
- **4.3 full shas + prefix-match + an ambiguity refusal.** All four write sites now record
  40 characters (`commitjoin.head`, `commit_windows` `%H`, `tasks.git_snapshot`,
  `originrecord.current_sha`). Both sides were `--short` and therefore agreed — *by
  coincidence of the moment*: git's abbreviation length grows with the repo, so rows
  written months apart stop comparing equal, **silently**.
- **`commitjoin.prefix_match` is prefix-SYMMETRIC, and that is the whole back-compat
  mechanism** — rows written before today carry short shas and are append-only. Wired
  into every read: the task join, the provenance grouping, `_attested_minutes`, the
  authorship summary, `originrecord._already_recorded` (an exact compare would have
  written a *duplicate* row that the deterministic id cannot dedupe) and `for_sha`.
- **⚠️ The proposal's symptom was backwards, as the handoff said.** Prefix matching
  already existed and was already symmetric; what was missing is the **ambiguity
  refusal**. `render_commit` takes `rows[0]` over an **oldest-first** sort, so an
  ambiguous prefix rendered the **oldest** match confidently. `AMBIGUOUS` is a distinct
  reason from `no-match` — *cannot tell which* and *do not have it* are different answers.
- **The recorded decision: full in the data, abbreviated in the display**
  (`constants.SHORT_SHA_DISPLAY = 7`), the same split as tokens vs `$`. **The goldens
  needed no re-blessing** — `full[:7]` is exactly the `%h` a small repo already rendered —
  so the output contract is untouched, which is the check that the split is right.
  `--json`/`--csv` carry the full sha; an abbreviated *key* is what this change exists to
  stop storing.
- **One bug of my own, caught by a test:** the summary join keyed a side table by
  `id(row)` across **two** `read_all` calls, which build fresh dicts — so it resolved
  nothing and made every real row look `unmatched`. Read once, carry the pair.
- **Files:** `cage/linematch.py` · `cage/transcript.py` · `cage/authorcapture.py` ·
  `cage/commitjoin.py` · `cage/commitview.py` · `cage/originrecord.py` · `cage/tasks.py` ·
  `cage/constants.py` · `tests/test_authorship_capture.py` · `tests/test_commitjoin.py` ·
  `tests/test_commitview.py` · `tests/goldenseed.py` · `docs/FORMULAS.md` · `docs/*`.
- **Tests:** green — **1583 ⇒ 1600**, 11 skipped. Both `prefix_match` mutants (drop
  symmetry, drop the refusal) kill tests; so do 4.1's and 4.2's.
- **Next:** P5 — HR-COPILOT-JOIN (a capture change; fail open to `""`, never guess).

## 2026-08-11 — agent-lane sweep P3: REV-HARDEN P4's mechanical half (4 of 5 landed, 1 raised as a fork)

- **Landed in the specified order 7 → 3 → 4 → 5; item 2 stopped at a decision.**
- **3.1 (item 7) two `cigraphify` checks that asserted nothing.** `determinism` ran both
  `cage report --csv` calls with `check=False` and compared only stdout, so two *crashed*
  runs gave `"" == ""` ⇒ pass — the vacuous-green class this module exists to prevent,
  inside the module itself. Now gates `returncode == 0` and non-empty output on both.
  `intercept`'s `rows[before:]` was a positional slice over `sorted(rglob("*.jsonl"))`; a
  row landing in an **earlier-sorted shard** shifts every index. Diffs an **id set** now.
- **3.2 (item 3) `_uncovered` judged coverage over other repos' edits.** The raw parse
  result went in unfiltered while `_repo_relative` was applied only to bucketing, so on a
  repo whose newest commit is old, any newer edit *anywhere on the machine* held the
  transcript uncovered — cursor never advanced, full re-parse every sweep, forever. New
  `_in_repo` shares `_repo_relative` with `_bucket_edits`, so coverage and bucketing
  finally agree on what "an edit in this repo" means.
- **A correction to the handoff, and it changed a test:** it asked for the `newest == ""`
  interaction to be asserted. **That branch is unreachable from `capture()`** — a repo
  with no commits short-circuits at `skipped="no-commits"` before any transcript is
  parsed. Recorded as such and unit-tested directly instead; a test that appears to
  exercise a branch it cannot reach is worse than none.
- **3.3 (item 4) unthrottled session-end sweep.** `ensure_captured` gained `force`, set by
  `_session_end` **only**. It skips the **throttle** and deliberately not
  `capture.enabled` (the consumer's master switch) or `--no-import` — both are decisions a
  user made; the throttle is an optimisation. `_session_start` stays throttled, with a
  comment and a test so the divergence cannot be "tidied" away. The test observes
  `importcmd.run`, because `ensure_captured` returns `None` both when throttled *and*
  when it swept and found nothing — the two states the defect is about telling apart.
- **3.5 (item 5, first half) quoted paths — and a second defect the handoff did not
  name.** No `core.quotePath` anywhere in the repo; git C-quotes any non-ASCII path, so
  `+++ "b/caf\303\251.py"` missed `_DIFF_FILE` and every line the agent landed scored
  **DROPPED**. Set inside all three `_git` helpers. **The second half survives that fix:**
  git appends a literal **tab** to `+++ b/a b.py`, so a path with a **space** captured as
  `"a b.py\t"` and could never key-match numstat's `a b.py`. `_DIFF_FILE` now absorbs it.
  **And a third site the handoff's list omitted:** `tasks.git_snapshot` splits
  `git diff --name-only` for its top-level-dirs guard, so a non-ASCII dir was stamped into
  the ledger's `scope` as `"caf\303\251` — a persisted, never-rewritten field.
- **There was no non-ASCII path fixture anywhere in `tests/` before this.** There are five
  now, all mutation-checked.
- **3.4 (item 2) `commitview`'s missing window — STOPPED, raised as a fork.** The two
  uncontested halves landed: the O(n²) `w not in wanted` list scan is a sha set, and a
  `--since` window that hides commits now reports how many (`windowed_out`) instead of
  making the repo look shorter. **The default window did not**, and the reason is the
  finding: a relative default puts a wall clock in the default path — the goldens' fixed
  `2026-07-01` fixtures render differently once they age past it (two broke on exactly
  that), and INTERVIEW.md's DOGFOOD lesson already ruled *make a published window
  absolute, never relative*. Measured **6.4s for 20 rows on 123 commits**; a 90d default
  cut **zero** of them, so it would not even have bounded the cost here.
  `constants.COMMITS_DEFAULT_ROWS`' comment claimed the row cap bounded cost — it never
  did (the cap is applied after every row is built), and that false comment is why this
  stayed invisible. Corrected. Fork filed:
  [compare](../work/compare/commits-view-cost-bound.compare.md) + OPEN-WORK **COMMITS-WINDOW**.
- **Files:** `tools/cigraphify.py` · `cage/authorcapture.py` · `cage/hookcmd.py` ·
  `cage/importcmd.py` · `cage/commitview.py` · `cage/clicmds.py` · `cage/cli.py` ·
  `cage/constants.py` · `cage/linematch.py` · `cage/originrecord.py` · `cage/tasks.py` ·
  four test files · `work/compare/commits-view-cost-bound.compare.md` · `docs/*`.
- **Tests:** green — **1562 ⇒ 1583**, 11 skipped.
- **Next:** P4 — REV-HARDEN P4's judgment half (Opus; the sha rewrite lands LAST).

## 2026-08-11 — agent-lane sweep P2: REV-HARDEN P3 — wiring hygiene (five items)

- **All five verified as still-real before any fix**, three of them by reproducing the
  failure in-process. The handoff was right about all five and **wrong about none** — but
  it under-counted one (below).
- **2.1 `.gitattributes` LF pin.** `git check-attr -a` returned *no attributes at all*
  for `cage/data/shims/graphify` — entirely unpinned, LF today, so latent. Added
  `text eol=lf`. The mechanism is **working tree → package**, not the commit: `autocrlf`
  normalizes CRLF→LF *at commit*, so the blob stays clean; what it changes is the
  checkout, which `pyproject`'s `data/shims/*` packages verbatim, shipping
  `#!/usr/bin/env bash\r` to every user of that build. Test asserts **the pin**, via
  `git check-attr`, not the bytes — a bytes assertion passes on a repo with no rule.
- **2.2 kiro's POSIX-only L1 hook — NAMED, not twinned.** New `agents.HOOK_SHELL_LIMIT`,
  rendered as a second all-agents line. It cannot be a `HOOK_GAPS` key (a full-event-set
  agent must stay disjoint from that table, and claude has the full set) and it is not
  per-agent — **all three commands are POSIX shell**, claude's included. Twinning was
  refused: kiro's hook document is committed and byte-compared, so a per-OS command
  churns the diff on every `cage setup` in a mixed-OS team. Same trade as kiro's
  path-free MCP entry.
- **2.3 copilot's overclaim, both halves.** `HOOK_GAPS["copilot"]` ended *"session
  identity and auto task-close are wired"* — false twice over: the two event names are
  cage's own with no vendor evidence, and `hookcmd._session()` parses only Claude Code's
  stdin shape, so on copilot it returns `""` and `_session_end` closes nothing. Reworded,
  **and** `clicmds`'s `L1 hooks ×{n}` — which reads file *contents*, independent of the
  gap text — now renders `(limited — see L1 limits)` for any agent in the one table.
- **2.4 the non-dict hook entry: five crash sites, plus a sixth I found.** Reproduced:
  `{"hooks": {"sessionStart": ["cage import"]}}` took `copilotwire._wire_hooks`,
  `copilotwire.hook_status`, `claudewire._wire_hooks`, `claudewire.hook_status` and both
  `wiringscan` spec builders down with `AttributeError: 'str' object has no attribute
  'get'`. **The sixth is `claudewire`'s `enable=True` wiring loop** (`e.get("matcher")`)
  — it only becomes reachable *once foreign entries are correctly preserved*, so fixing
  preservation alone would have moved the crash rather than closed it.
- **The data loss was the sharper half, and it is fixed as two branches.** A non-dict
  `hooks` VALUE was coerced to `{}` and fell through to `path.unlink()` on the **default**
  (`hooks=False`) `cage setup` path — reproduced destroying a file's `myTeamSettings`.
  *"Nothing left to preserve"* and *"a shape I don't understand"* are now different
  branches: emptiness is a conclusion cage may only draw about a shape it actually read.
  Both opposing green tests stay green — the unlink still fires when only cage's entries
  were present, foreign entries still survive — and a bare-string entry is now **kept as
  foreign by construction** (cage only ever writes `{"bash": …}`).
- **2.5a `covered` compared annotated displays against bare ones.** Reproduced on a wired
  project: **five phantom `other` rows** (four `.claude/settings.json`, one kiro).
  `_base_display` strips **any** trailing parenthetical — kiro's is `" (L1 hook)"`,
  *singular*, so the literal `removesuffix` would have fixed two of three.
- **2.5b `committed_artifacts` under-enumerated.** `.github/hooks/cage.json` (copilot's
  repo-level hook) and `.kiro/settings/mcp.json` were never walked, so a dead verb in
  either was invisible to the headline `wiring` check — verified by planting one and
  watching the scan come back clean. Landed **after** 5a, as specified; a test now pins
  that ordering constraint rather than leaving it a note.
- **2.5c `interceptor_dead` is one bool applied per-twin.** New `Scan.dead_interceptors`
  (a defaulted `frozenset`) beside it; the inventory and doctor's message read the set,
  `doctorcmd._receipts` keeps the bool because *is anything dead* is genuinely its
  question. Doctor no longer blames the healthy twin this OS happens to resolve.
- **The tests that would have caught these are the point.** `test_win_graphify_shim.py`
  pinned `scan.dead` but never the **rendered rows** — which is exactly how 5c stayed
  green — so the new tests assert the inventory rows and doctor's text. All five items
  were **mutation-checked**: reverting each guard kills its test.
- **Files:** `.gitattributes` · `cage/agents.py` · `cage/claudewire.py` ·
  `cage/copilotwire.py` · `cage/kirowire.py` · `cage/clicmds.py` · `cage/wiringscan.py` ·
  `cage/doctorcmd.py` · `tests/test_win_graphify_shim.py` · `tests/test_hooks_layer.py` ·
  `tests/test_agents.py` · `tests/test_wiringscan.py` · `docs/*` · `README.md` ·
  `CLAUDE.md`.
- **Tests:** green — **1545 ⇒ 1562**, 11 skipped.
- **Next:** P3 — REV-HARDEN P4's low-blast-radius half (Sonnet-shaped; order 7 → 3 → 4 →
  2 → 5-quotePath). **Not** to be batched with P4.

## 2026-08-11 — agent-lane sweep P1: CIGF-HERMETIC — the graphify CI leg is hermetic on a dev box

- **Verified first, and the defect is exactly as filed.** With `HOME`/`CAGE_HOME`
  redirected into the sandbox the way `cigraphify._env` does,
  `paths.find_project_root(Path("/Users/arpitarya/my_programs"))` returns
  `/Users/arpitarya` — the developer's real home. Both entries of the `excluded` set
  (`global_base()` and `Path.home()/".cage"`) collapse onto `sandbox/home/.cage`, so the
  real `~/.cage` stops being excluded and the upward walk from a sandbox built at
  `REPO_ROOT.parent` adopts it. **The hermeticity mechanism was the bug.**
- **Implemented:** two guards in `tools/cigraphify.py`. (1) `main()` seeds
  `(project / ".cage").mkdir(parents=True)` *before* any check — `find_project_root`
  returns on the first hit, so `cur == project` short-circuits before the walk can leave
  the sandbox, wherever the sandbox lives (including under `--path ~`). (2) a new
  `_sandbox_parent()` defaults the parent to `tempfile.gettempdir()` instead of
  `REPO_ROOT.parent`. Guard 1 is the load-bearing one; guard 2 is defence in depth and
  **cannot stand alone** — on Windows `gettempdir()` is under `USERPROFILE`.
- **Both fixes the tracker named are wrong, and that is recorded in the module
  docstring, not just here.** Pinning the root in `_env` via `CAGE_BASE` is impossible —
  the resolver that bites is `cliutil.root()` → `find_project_root`, which has no
  `CAGE_BASE` branch (only `resolve_root`, the *read* path, does). `gettempdir()` alone
  is holed on Windows, which is the one OS this runner exists for.
- **The property given up, stated:** ".cage scaffolded from nothing" no longer holds. No
  check ever asserted it (`check_setup_installs_both_twins` asserts only the two `bin/`
  twins) and `initcmd.run` is idempotent over an existing dir.
- **Also recorded, not fixed:** `check_passthrough_is_transparent` and
  `check_doctor_reports_live` pass **vacuously** when the `setup` check has already
  failed — with no shim in `project/bin`, `through` and `direct` are the same unmetered
  invocation. Honest as written (`setup` is the check that fails), but a green
  `passthrough` is not evidence of interception; `intercept` is the only check that
  proves the shim ran. Comment added at the site.
- **Acceptance is the real leg, not the unit tests.** `python -m tools.cigraphify` was run
  on this machine against the real installed graphify: **7/7 checks passed** (`setup` ·
  `graph` 70 nodes · `intercept` 1 savings row ~2,562 tokens gross · `passthrough` ·
  `doctor-live` · `doctor-dead` · `determinism`) — it had never been runnable on a
  developer box before, and the tracker's 3-of-7 failure claim (`setup`, `intercept`,
  `doctor-dead`) was exact. Hermeticity was proven by a **before/after shasum manifest of
  `~/.cage`, `~/bin` and `~/CLAUDE.md`: byte-identical**, and the sandbox landed under
  `/var/folders/…/T/`, not beside the repo.
- **Files:** `tools/cigraphify.py` · `tests/test_cigraphify.py` · `docs/OPEN-WORK.md` ·
  `work/DOC-REGISTRY.md` · `README.md` · `CLAUDE.md`.
- **Tests:** green — **1542 ⇒ 1545**, 11 skipped. Three added, and the first is a
  **negative control that reproduces the bug**: without the seed,
  `find_project_root(project)` returns the fake dev home. A regression test could not be
  written against `main()` (it needs a real graphify install to reach the seeding), so
  the tests pin the *mechanism* — the short-circuit — plus `_sandbox_parent`'s default.
- **Correction to the trackers, found on contact:** the suite baseline was **1542**, not
  the 1541 recorded in `INTERVIEW.md`, `README.md`, `CLAUDE.md` and the sweep handoff.
  Counts refreshed to 1545.
- **Next:** P2 — REV-HARDEN P3 wiring hygiene (five items, Opus; 5a before 5b).

## 2026-08-10 — v0.48.0: the artifact surface (`--export`/`--stamp`) + the chats structural-empty fix

- **Implemented (1):** `--export` on `cage report` + all 16 `cage insights` views.
  `cage/runstamp.py` is the ONE clock call on a read surface (one metadata block, three
  renderings: `# cage: k=v` for text/CSV, a `cage` object for JSON; `CAGE_RUN_STAMP`
  pins it). `cage/viewexport.py` owns destinations (bare → `<ledger>/.cage/output/
  <view>-<stamp>/`, known suffix → that file, other path → a per-run folder under it),
  the available-format set, and the stderr confirmation. `cliutil.emit` became the ONE
  chokepoint — export, then exactly one of CSV/JSON/text — which also deleted the
  duplicated `csv_dest` branch from 15 handlers.
- **The design decision, recorded:** stdout is byte-identical with and without
  `--export`, so the determinism law is untouched and the goldens keep pinning a
  clock-free surface. The stamp is mandatory in an artifact (a file outlives its
  terminal), optional on stdout (`--stamp`). `--csv`/`--json` byte contracts unchanged,
  stdout *and* to a path.
- **Implemented (2):** `cage insights chats --agent kiro` named the filter for an
  architectural fact. The empty view now evidences its structural reasons (credits rows
  carry no calls; IDE rows route to the machine ledger, ADR 0006) and only for the agent
  asked about; a genuinely empty filter keeps the old message. `kiro_routed_line` gained
  a `verb` param so one phrasing names the right fix per view. Non-empty views footnote
  credits usage they cannot show. `ledger.credits` is the third money-independent
  carve-out — read for a refusal, never a cell.
- **Files:** new `cage/runstamp.py` · `cage/viewexport.py` · `tests/test_view_export.py`
  · `work/compare/view-export-and-run-stamp.compare.md`; changed `cage/cli.py`
  (`_export_flags`) · `cage/cliutil.py` · `cage/clicmds.py` · `cage/paths.py`
  (`Footprint.output`) · `cage/chats.py` · `cage/report.py` · `cage/initcmd.py`
  (gitignore heal) · `cage/explain_data.py` (`view-export`) · `docs/CLI.md` ·
  `tests/test_chats.py` · `tests/test_doctor.py` · `.gitignore` · CHANGELOG · README.
- **Tests:** green — **1503 → 1541** (32 new in `test_view_export.py`, 6 in
  `test_chats.py`, 1 in `test_doctor.py`). Full suite run under the container's root
  user, so `test_policysync.py::test_readonly_target_errors_cleanly_no_partial_write` is
  deselected there (root ignores a read-only bit); it passes normally.
- **Next:** tag/release v0.48.0 through the GitHub-release trigger (never publish from
  local), then decide the `.cage/output/` growth question if a real machine reports a
  number.

---

## 2026-08-08 — v0.47.2: the same Windows class, one syntax layer over

- **v0.47.1 fixed 25 of 26.** The survivor was the *same* defect in TOML that v0.47.1 had
  just fixed in JSON: the E2E kiro test wrote `paths = ["{proj / "data.sqlite3"}"]`, and on
  Windows that is `C:\Users\…` inside a TOML **basic** string, where `\U` is an escape —
  `tomllib` raises `Invalid hex value`, the source never resolves, the sweep files nothing.
- **The fix was already the repo's convention**, not a new mechanism: `.as_posix()`, which
  **six other `[sources]` tests here already use** and which is why they pass on Windows.
  Mine was the only one in the suite not following it. (I had first written a TOML literal
  string — correct, but a *second* idiom for a problem this repo had already ruled on.
  INTERVIEW's "search before you invent" applied literally.)
- **A grep-gate now closes the class:** `test_sources.py::test_no_test_writes_a_raw_path_
  into_a_toml_basic_string`. Two things it taught while being written: its first pattern
  had **the same blind spot as the bug** (a quote-excluding class skipped
  `["{proj / "x"}"]`, the exact shipped form), and it flagged its own explanatory comment
  until comment lines were skipped. Mutation-checked.
- **The rule both patches share:** a filesystem path crossing into any escape-processing
  syntax — JSON, a TOML basic string, a shell — needs an explicit conversion, never `str()`.
- Files: `tests/test_graphify_kiro.py` · `tests/test_sources.py` (+1 gate) ·
  `cage/__init__.py` · `CHANGELOG.md` · `README.md` · `CLAUDE.md` · goldens (version line).
  **No product code changed in this release.**
- Tests: **green, 1503 passed / 11 skipped**.
- Next: confirm the Windows legs are green on v0.47.2.

## 2026-08-08 — v0.47.1: the Windows break, and the reason it shipped

- **v0.47.0's `build` job went red on both Windows legs** (26 failures). Every POSIX leg
  and all three graphify legs were green. Two distinct faults:
  1. **Product.** `graphifytx._repo_of` gated on `startswith("/")`. A Windows path is
     `C:/…`, so it returned `""`, the graph resolved against the process CWD instead of the
     repo, and the **copilot VS Code report-read route filed nothing on Windows** — no
     error, just an absent receipt, which is indistinguishable from "graphify never ran".
     Now matches `^(/|[A-Za-z]:/)`. **`Path.is_absolute()` is deliberately not used**: on
     POSIX it calls `C:/x` relative and on Windows it calls `/tmp/x` relative (no drive),
     so each OS would reject exactly the form the other produces.
  2. **Harness.** The new fixture tests substituted `str(tmp_path)` into **raw JSON text**;
     on Windows its backslashes are invalid JSON escapes ⇒ 26 `JSONDecodeError`s. Moved to
     `tests/gfxfixture` — parse first, substitute in parsed strings, re-serialize.
- **Why it shipped, which is the part worth keeping:** both faults were Windows-only and
  every test that could have caught them was **also** Windows-only. The two new regression
  tests run on **every** OS by construction (one asserts `_repo_of` against both absolute
  conventions, one round-trips a `C:\Users\…` root through the loader), so the POSIX legs
  alone would now fail. **Verified by mutation:** restoring the v0.47.0 predicate makes the
  new test fail on macOS.
- A small joke on itself, kept as a comment: the new test's own docstring broke collection
  because `\U` in a non-raw docstring is a unicode escape — the same class of bug.
- Files: `cage/graphifytx.py` · `tests/gfxfixture.py` (new) · `tests/test_graphify_vscode.py`
  (+2) · `tests/test_graphify_kiro.py` · `cage/__init__.py` · `CHANGELOG.md` · `README.md` ·
  `CLAUDE.md` · `tests/fixtures/goldens/P1.txt` (version line).
- Tests: **green, 1502 passed / 11 skipped** (1500 → 1502).
- Next: push, tag v0.47.1, release; confirm both Windows legs green.

## 2026-08-08 — GFX-COV field run: copilot VS Code verified; the capture earned two tests

- **Verified on a real Copilot Agent chat:** one terminal `graphify query` filed a receipt
  through the shipped route — **146,261 tokens saved**, raw 147,789 / actual 1,528 across
  **72 cited files**, `modeled`, conf 0.6, session taken from the store. Re-run filed 0.
  The PATH shim was deliberately not in play, so the store route was the only thing that
  could file (had the shim fired, ADR 0005 deferral would have made the run prove nothing).
- **The capture disproved two of my own fixture's assumptions**, and both are now tested:
  (1) a real agent emits **`cd <repo> && graphify query …`** — `run_in_terminal` reuses one
  shell — so **nothing had exercised `graphify_ops`' `&&` segment split**; it worked by
  design, not by test. (2) The real part carries **no `resultDetails`**, so the field
  carrier is the ANSI-stripped `terminalCommandOutput` fallback (~89% of real parts) —
  pinned so a change cannot quietly make the preferred carrier mandatory.
- **Fixture provenance upgraded from SHAPE-VERIFIED/CONTENT-SYNTHETIC to VERIFIED:**
  `chatSession-graphify.jsonl` is the sanitized real record (structure verbatim, answer
  abridged to the two planted files); `chatSession-report-read.jsonl` is a **new** fixture
  built from a real `copilot_readFile` part — kept separate because the captured session
  had no report read, and folding a synthetic part into a real capture would launder
  invention into a fixture labelled real. Sanitization asserted: no user path, no username
  anywhere under `tests/fixtures/transcripts/graphify/`.
- Files: `work/regression/2026-08-08-gfx-cov-vscode-field-run.md` (new) ·
  `work/regression/README.md` · `tests/fixtures/transcripts/graphify/copilot-vscode/*` ·
  `tests/fixtures/transcripts/graphify/README.md` · `tests/test_graphify_vscode.py` (+2) ·
  `docs/OPEN-WORK.md` (**GFX-COV-FIELD closed**, narrowed to **GFX-KIRO-RATE**).
- Tests: **green, 1500 passed / 11 skipped** (1498 → 1500).
- Next: the v0.47.0 release cut — the only thing left, and it needs Arpit's explicit go.

## 2026-08-07 — GFX-COV field run: the kiro route verified on a real store

- **Verified, not asserted:** the v0.47.0 kiro-CLI route read a real
  `conversations_v2` store (kiro-cli 2.16.0) through the shipped code path and filed
  **1 receipt — 3,545 tokens saved** (`graphify explain`, raw 3,620 / actual 75, modeled,
  conf 0.6) — while **refusing** the other invocation, an ordinary
  `graphify query` whose 6,039-char stdout ended in kiro's truncation marker. Re-run
  filed 0. **Both branches of the guard execute on real traffic.**
- **ADR 0006 scoping observed working:** a project-scoped sweep from a sandbox filed
  nothing, because the real conversations are keyed to `~/my_programs/cage`. Only the
  machine-ledger scope (`workspace=""`) saw them.
- **The real ledger was not touched** — receipts went to a throwaway sandbox; `~/.cage`
  still holds 0 graphify receipts and its 5 pre-existing savings rows from 2026-08-03.
- **n = 2. Deliberately not published as a refusal rate** — it proves both paths run and
  nothing more. ADR 0009's veto (reopen below a 10% file rate) needs a real usage sample.
- Files: `work/regression/2026-08-07-gfx-cov-kiro-field-run.md` (new) ·
  `work/regression/README.md` · `docs/OPEN-WORK.md` (GFX-COV-FIELD narrowed to its two
  surviving residuals).
- Tests: unchanged, **1498 passed / 11 skipped** (a field run, no code change).
- Next: the copilot **VS Code** field half (needs a real Copilot chat), or the v0.47.0
  release cut.

## 2026-08-07 — GFX-COV **P3**: `--rescan-graphify` backfill + the loud coverage gap (green)

- **`cage import --rescan-graphify`** — one helper, `importcmd.graphify_scan_set`, decides
  which file set graphify detection walks: normally the sweep's own `files` (so detection
  keeps inheriting the cursor), the source's **full match set** under the flag. Threaded
  into all three legs (claude · copilot · the kiro-CLI credits leg). **Detection only** —
  it feeds the graphify detectors and nothing else, so no call or credit row is re-ingested
  (pinned by test); idempotent by receipt id.
  The defect it closes: the cursor is keyed on `(size, mtime)`, which is right for calls
  and wrong for savings — a route shipping *after* a session was ingested could never see
  that session again. That is precisely how copilot VS Code and kiro stayed dark.
- **`graphifytx.GRAPHIFY_COVERAGE` is ONE table** naming every agent surface, whether it
  files receipts, and — for the one that cannot — the measured reason. Read by both
  `cage doctor`'s new **`graphify-coverage`** check (rendered directly below
  `graphify-usage`: how often graphify *ran* vs what could be *filed*) and the new
  **`cage query graphify-coverage`** explainer, via `coverage_lines()`. A test asserts the
  two word a gap identically — re-deriving either side would let one go stale silently.
- Files: `cage/cli.py` · `cage/importcmd.py` · `cage/graphifytx.py` · `cage/doctorcmd.py` ·
  `cage/explain.py` · `cage/explain_data.py` · `docs/CLI.md` ·
  `tests/test_graphify_copilot.py` (+5) · `tests/test_doctor.py`.
- Tests: **green, 1498 passed / 11 skipped** (1493 → 1498). `test_cli_reference.py`'s
  bidirectional gate caught the undocumented flag before the suite did — the doc migration
  worked as designed.
- Next: P4 — the remaining docs pass (CHANGELOG, README, OPEN-WORK, WORKLOG, DOC-REGISTRY,
  archive the pair) and the proposed CLAUDE.md edits.

## 2026-08-07 — GFX-COV **P2**: the kiro-CLI graphify route + ADR 0009 (green)

- **Implemented:** `transcript.parse_kiro_cli_tool_runs` (+ `_kiro_cli_tool_runs`) reads
  completed tool runs out of `conversations_v2` — same read-only
  `mode=ro&immutable=1` connection and same `workspace` tree scoping as the credits
  parser. `graphifytx.detect_and_file_kiro_cli` detects `execute_bash` graphify runs and
  `fs_read` report-reads and files through the shared `_file_query`/`_file_report_read`.
- **ADR 0009 authored in the same change** —
  `docs/adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md`. It does
  **not** re-argue *counts persisted, content transient* (ADR **0008** already ratified
  that for line-match authorship, and more strictly — it forbids even a line hash); it
  records **where the boundary falls in this store**, which is the part 0008 could not
  answer, because kiro's is the one store whose law is a written key whitelist. The
  whitelist comment in `transcript.py` now names the carve-out and its single function.
- **The truncation guard is the load-bearing part.** kiro caps tool stdout at ~2000 tokens
  and appends `... (truncated to ~2000 token budget)`, cutting mid-token — pinned verbatim
  as `transcript.KIRO_CLI_TRUNCATION_MARKER` and matched **anchored at end-of-string**. A
  truncated run files nothing (under-counted `actual` ⇒ inflated saving). A test asserts
  the anchoring specifically, using the rust-clippy false positive the VS Code corpus
  actually produced.
- **Wiring:** `importcmd._detect_graphify_kiro_cli` hangs off the credits leg
  (`_ingest_credits`) deliberately — that leg has already resolved sink and tree
  (ADR 0006), so the route never adds a second resolver. Scoping is pinned by test.
- Files: `cage/transcript.py` · `cage/graphifytx.py` · `cage/importcmd.py` ·
  `docs/adr/0009-*.md` (new) · `tests/test_graphify_kiro.py` (new, 16 tests) ·
  fixtures under `tests/fixtures/transcripts/graphify/kiro-cli/`.
- Tests: **green, 1493 passed / 11 skipped** (1477 → 1493).
- Next: P3 — `cage import --rescan-graphify` + the loud-gap surfaces (doctor + explainer).

## 2026-08-07 — GFX-COV **P1**: the copilot VS Code graphify route (green)

- **Implemented:** `graphifytx.detect_and_file_copilot_vscode` — walks the chatSessions
  patch stream's **three** part carriers, reads `run_in_terminal`
  (`commandLine.original` · `cwd.path` · output) and `copilot_readFile`
  (`invocationMessage.uris[].path`), and files through the existing
  `_file_query`/`_file_report_read`. No new formula, no new confidence constant, no
  schema change. `importcmd._detect_graphify_copilot` now **dispatches by store** instead
  of `continue`-ing on `chatSessions/` — the F2 skip is gone.
- **Carrier precedence (P0 verdict A):** `resultDetails.output[].value` (model-facing)
  wins; ANSI-stripped `terminalCommandOutput.text` is the fallback. Pinned by test.
- **Truncation guard is structural (P0 verdict C):** no output carrier, or
  `terminalCommandState.exitCode != 0`/absent ⇒ file nothing + a `CAGE_DEBUG` skip event.
  **No marker string is matched** — all 23 `truncat` hits in 1,132 real parts were rust
  clippy lint output, and a test pins that a lint-bearing answer still files.
- `_repo_of()` recovers the repo root from an absolute report path (a `copilot_readFile`
  part carries no cwd, unlike a claude transcript record).
- Files: `cage/graphifytx.py` · `cage/importcmd.py` · `tests/test_graphify_vscode.py` (new,
  15 tests) · fixtures under `tests/fixtures/transcripts/graphify/copilot-vscode/`.
- Tests: **green, 1477 passed / 11 skipped** (1462 → 1477). ADR-0005 acceptance tests
  re-asserted for this route (two sessions ⇒ two receipts; shim-then-store ⇒ exactly one).
- Next: P2 — the kiro-CLI route + its counts-never-content ADR in the same change.

## 2026-08-07 — GFX-COV **P0**: real-store evidence gate complete (STOP — awaiting verdict)

- **Probed, read-only, on real stores:** copilot VS Code `chatSessions` (VS Code 1.132.0,
  157 files, 7,741 tool parts, 1,132 `run_in_terminal` runs) · kiro-cli 2.16.0
  `conversations_v2` (19 conversations + 2 live probe runs made for this gate) · Kiro IDE
  0.12.333 `workspace-sessions` (16 session files).
- **The handoff's F2 assumption is FALSE.** `run_in_terminal` persists
  `toolSpecificData.commandLine.original` (the command), `.cwd` (per-command, exact —
  better than the planned `workspace.json` lookup) **and** the output, via two carriers:
  `terminalCommandOutput.{text,lineCount}` (1,011/1,132) and `resultDetails.output[].value`
  (133/1,132). The VS Code query route is buildable.
- **kiro-CLI shapes pinned against a live `execute_bash` run:** `ToolUse.tool_uses[]` →
  `{id, name, args:{command, working_dir}}`; the result lands in the **next** history entry
  as `ToolUseResults.tool_use_results[] → {tool_use_id, status, content:[{Json:{exit_status,
  stdout, stderr}}]}`. **kiro truncates stdout at ~2000 tokens** with the verbatim marker
  `\n... (truncated to ~2000 token budget)\n` — reproduced on a real graphify query.
- **Kiro IDE is unbuildable, confirmed not assumed — and for a different reason than the
  handoff gave.** A richer per-workspace session store exists
  (`workspace-sessions/<base64url(cwd)>/<id>.json`), and it *still* persists no assistant
  output: 26/26 `promptLogs[].completion` are the empty string, zero tool blocks.
- **No VS Code truncation marker exists** in 1,132 samples; all 23 candidate hits were the
  command's own output (rust clippy `cast_possible_truncation`). A substring guard would
  have false-positived. `lineCount` is not a truncation detector either (338/341
  discrepancies are `\r`/ANSI redraws).
- Files: `work/research/2026-08-07-graphify-store-evidence.md` (new) ·
  `tests/fixtures/transcripts/graphify/{README.md,copilot-vscode/*3,kiro-cli/*5,kiro-ide/*1}`
  (new — no `expected.json`, so `test_fixture_corpus.py` does not pick them up).
- Tests: **green, 1462 passed / 11 skipped** (unchanged — P0 added no code).
- Next: **STOP.** Arpit's verdict on handoff OPEN QUESTIONS 1–2 (both answered by the
  evidence) plus four new forks the evidence raised (A–D in the research doc §5). No P1
  code until then.

## 2026-08-03 — CI-S18: the `build` gate goes green again (v0.46.1)

- **Found while verifying the v0.46.0 release**, not reported by anyone: the `build` job
  had been failing on **all nine** platform legs since v0.45.0, and two releases shipped
  straight through it. `publish-pypi` fires on `release: published` with **no `needs`
  link to `build`** (deliberate — CLAUDE.md), so neither publish was compromised; the
  cost was a gate everyone had learned to ignore.
- **Diagnosis: the harness asserted the pre-hookless heal.** `tools/dummyrepo` S18 plants
  a stale pre-v0.36 cage hook in `.claude/settings.json`, heals it with `cage setup`, and
  then re-read that file to assert the dead verb was gone. Cage plants nothing else
  there, so the strip empties the object and `claudewire._wire_hooks` **unlinks a file it
  alone reduced to `{}`** (so an off-switch leaves no permanent diff). The scenario died
  with `FileNotFoundError` **on the correct outcome** — a test encoding an expectation
  the product had deliberately moved past.
- **Implemented:** S18 now *asserts* the removal rather than tolerating it (absence is
  the strongest form of "the dead verb is gone", and it is documented behaviour no other
  scenario covered); a file left behind is a named failure that prints its contents; the
  byte-identical idempotency check reads absent as `b""` on both sides, so a re-heal
  cannot resurrect an empty file either.
- **No product code changed** — nothing under `cage/` is touched by this release.
- **Files:** `tools/dummyrepo/run.py` · `cage/__init__.py` (0.46.1) · CHANGELOG · README ·
  OPEN-WORK (new **CIGF-HERMETIC** row) · DOC-REGISTRY.
- **Tests:** `just test` 1462/0 · `python -m tools.dummyrepo` **17/17 PASS** (was 16/17
  with S18 erroring) · `python -m tools.cigraphify` green in CI on all three OSes.
- **Also found, filed not fixed (CIGF-HERMETIC):** `tools/cigraphify` is **not runnable
  on a developer machine**. It builds its sandbox as a sibling of the repo, so on a dev
  box that path sits under `$HOME` — and `paths.resolve_root` walks up and adopts the
  real `~/.cage`, making `cage setup --project-only` scaffold into the *home* root
  instead of the sandbox (3 of 7 checks fail). CI has no ancestor `.cage`, so it passes
  there and the gap is invisible. Same family as the cage-lab PATH rule in CLAUDE.md: a
  lab that is not hermetic against the developer's machine cannot be verified before
  pushing. **Caution for whoever picks it up:** running that leg from under `$HOME`
  writes to the real `~/.cage` (it rewrote `cage.toml`/`prices.toml` here — idempotent
  and non-destructive, ledger untouched, `cage doctor` green after).
- **Next:** tier 2's three decisions; CIGF-HERMETIC when someone needs to verify the
  graphify leg locally.

## 2026-08-03 — CHATS-AUTHOR: the `agent%` column on `cage insights chats` (1442/0 ⇒ 1462/0)

- **Phase 0 gate (REV-TS) verified before any work** — `commitjoin.norm_ts` normalizes,
  `Window` normalizes at construction, `window_for` normalizes its probe; the five
  non-UTC / mixed-offset / inclusive-bound fixtures in `tests/test_authorship_capture.py`
  pass. Verified independently rather than trusting the prompt's status line.
- **Implemented:** per chat, `agent% = agent_lines / (agent_lines + residual_lines)` over
  the provenance rows sharing `(agents.row_surface(agent), session_id)` — a pure ledger
  join, **no git at render**, counts **read** never re-matched.
  - Substrate: `residual_lines` joins `PROVENANCE_COUNT_FIELDS`. **The one count written
    at 0** (`PROVENANCE_ZERO_BEARING_COUNTS`); its default is a `None` *omit* sentinel, so
    every non-matching caller writes the pre-v2 row byte-for-byte while presence of the
    key is the version gate. `originrecord`'s `**counts` boundary passes a `0` through and
    drops a `None` (never `int(None)` inside a never-raising path).
  - Capture: `authorcapture._residual` sums `FileMatch.added_matchable` over the row's
    **landed** files minus `agent_lines`, floored at 0 — off the match list already in
    hand, **no extra git call**.
  - Render: one `agent%` column after `credits`, **default on**. Three refusal shapes
    render `—`, each footnoted: coverage (`coverage_note()` verbatim) · no landed evidence
    (no row joined, *or* rows carrying no matchable line — the divide-by-zero case, folded
    in because both reduce to the same statement) · pre-upgrade (excluded from both sums,
    counted). A measured `0%` renders `0%`. Split-across-surfaces is footnoted.
  - CSV: `agent_lines` · `residual_lines` · `agent_pct` (0–100, 1dp); **all three empty on
    a refusal** — writing `0,0` would put the claim the dash refuses to make into data.
- **Decisions:** (a) the handoff's "demote behind `--authorship` if the golden overflows
  100 cols" trigger was **moot** — I10a was already 113 cols before this column, so it
  could not be what decides it; Arpit confirmed default-on. (b) §10 open question resolved:
  `agent_pct` is **0–100 with 1dp**, pinned in FORMULAS §2.13 and a golden.
- **Files:** `cage/schema.py` · `cage/originrecord.py` · `cage/authorcapture.py` ·
  `cage/chats.py` · `cage/explain_data.py` · `tests/test_chats.py` (+14) ·
  `tests/test_authorship_capture.py` (+6) · `tests/goldenseed.py` ·
  `tests/test_copilot_credits.py` (positional CSV reads → by header) ·
  `tests/fixtures/goldens/I10{a,b,d}.txt` · FORMULAS §2.13/§2.14 · PLAN §3.5/§7 ·
  GLOSSARY · README · CHANGELOG (v0.46.0 unreleased) · DOC-REGISTRY.
- **Tests:** green — **1462 passed, 0 failed**, 11 Windows-only skips. Goldens re-blessed
  (chats only; no other view moved a byte). The reconciliation assertion holds across the
  seam: a chat's sums equal `commitview._buckets`' `agent`/`human` on the same session.
  Money-independence extended: deleting `provenance.jsonl` moves zero pre-existing cell.
  Plant-string test untouched and green.
- **Released as v0.46.0** the same day: `__version__` bumped, README "What's new"
  replaced, both test counts refreshed to 1462 (the steering proposal's item E — the one
  row the release rule already mandates — applied and deleted from it). The **chats-bullet**
  CLAUDE.md edit stays **proposed, not applied** (item F), because it changes a stated
  law's cardinality.
- **Next:** tier 2's three decisions (COPILOT-PREMIUM-DEAD · REV-CREDITS defect 2 ·
  OTEL-SEMCONV-PIN), none of which is a build.

## 2026-08-03 — Tier 2: REV-CREDITS · REV-HARDEN P2 · CLI-GAPS(a) (1423/0 ⇒ 1441/0)

- **REV-CREDITS defect 1 + the guard gaps.** The copilot CLI shutdown loop dropped a
  billing delta whenever the *first-listed* model had idled — `prev_cred` advances
  before the per-model loop, an idle model emits no row, and the delta was pinned to
  index 0. Now built rows first, then `_place_billing_delta` stamps the shutdown's
  counters on the **largest token mover** (ties by model name): deterministic,
  order-independent, and explicitly **not** an attribution claim. Every model idle +
  a real delta ⇒ a zero-token carrier row (a true statement; dropping it is the defect).
  A backwards counter now reads as a **reset** (new cumulative = the delta) rather than
  a negative that shrinks USD totals — clamping to 0 was rejected as discarding real
  spend. **A finding worse than filed:** a non-finite counter did not merely store a bad
  value, `int()` **raised** and cost the whole file's rows; `_first_int`/`_first_float`
  now skip non-finite and the tokens beside them survive.
- **Defect 2 deliberately not built** — multi-model double-counting is a genuine basis
  fork and belongs in the compare doc, exactly as the proposal instructs.
- **The method law reaches `compare`.** It wrote the literal `"measured"` for every
  eligible group while credit-priced dollars are `modeled` by the feature's own law.
  `taskgroup.stats` now carries `credit_calls` (the basis was simply unavailable to
  compare, which is *why* it hardcoded), and both CSV cells and the text header degrade
  through `creditprice.method_for` — together, since a header claiming `measured` over a
  modeled row is the same lie as the cell.
- **REV-HARDEN P2, four of five.** adoption `--since` half B now row-filters like half A
  (it was month-granular, so one flag answered two questions) · a shared session gets its
  own **`ambiguous`** reason instead of `unjoined`'s *"capture gap worth chasing"*, which
  was a false fact · `convert.saved_usd_opt` owns the unpriced-vs-zero distinction so an
  UNPRICED saving is **omitted** from OTel rather than exported as `$0` (fixed in
  `convert`, not `otelout` — a second copy of that ladder is how the credits rung drifted
  once) · the `--hooks` off-switch now uses the path that drops an emptied `hooks` table
  and removes a file cage alone emptied, so unwiring stops being a permanent diff; the
  redundant `_strip_stale_hooks` went with it (identical predicate, half the job).
- **The fifth is a fork, not a fix.** `gen_ai.system` *is* deprecated (renamed in semconv
  **v1.37.0**, before cage's pinned 1.42.0) — but verifying it surfaced that the GenAI
  conventions moved to their own repository, so the pinned version string may not name
  what cage thinks. Filed as
  [research](../work/research/2026-08-03-otel-genai-semconv-pin.md) with three
  options and a recommendation; `otelout` and the pin are untouched.
- **CLI-GAPS(a):** `cage --help` advertised six of `data`'s eight commands. Fixed *and*
  **gated bidirectionally against the live parser** — a command that exists but is
  unnamed, or a name with no command, now fails the suite. Found on the way: each
  group's `help=` string duplicates those lists and is **rendered nowhere**; a first
  attempt to derive it was reverted as dead code and the fact noted at `cli._group`.
- **Files:** `cage/transcript.py` · `cage/taskgroup.py` · `cage/compare.py` ·
  `cage/adoption.py` · `cage/convert.py` · `cage/otelout.py` · `cage/claudewire.py` ·
  `cage/cli.py` · six test modules (+18) · `tests/fixtures/cli-help.txt` (re-blessed) ·
  `CHANGELOG.md` · `work/research/2026-08-03-otel-genai-semconv-pin.md`.
- **Tests:** green — **1441 passed, 11 skipped, 0 failed**. Zero goldens re-blessed.
- **Open / carried forward:** **COPILOT-PREMIUM-DEAD's premise is FALSE** — OPEN-WORK
  says `premium` "now has no reader", but `chats.py` sums it into a rendered column and
  a CSV column, pinned by three goldens (I10a/b/d). Its two options therefore have
  materially different user-visible outcomes and it needs a decision, not a sweep. Also
  open: REV-CREDITS defect 2 (basis fork) and the OTel semconv pin (above).
- **Next:** tier 2's remaining rows are the two decisions above; the queue's next
  *buildable* work is tier 3 (Arpit's steering-file sitting) and tier 5's triggers.

## 2026-08-03 — REV-DOGFOOD-DATE + REV-HARDEN P1: two armed bombs defused (1416/0 ⇒ 1423/0)

- **Implemented (P1, the fail-open hole):** `cage hook` usage errors now exit **0**
  instead of **2**. Exit 2 is `hookcmd.BLOCK`, wired to `PreToolUse`/`Bash` — so an
  unknown event name (what a rename against stale committed wiring produces) blocked
  **every Bash call in the session**, and silently, because a blocked tool call reads as
  the agent refusing rather than as cage failing. Reproduced at HEAD before the fix
  (`cage hook not-an-event --agent claude` → exit 2). The catch is scoped to the `hook`
  verb: `cage insights bogus` still exits 2, `cage hook --help` still exits 0, and a
  **real** budget block still returns 2 — asserted through `cli.main` (the path a host
  invokes) rather than `hookcmd.run`, since that is where both codes travel.
- **One deliberate divergence from the proposal, and it is the interesting part.** The
  spec also asked for a `verbmap.REMOVED`-style migration row for hook *event* names.
  Not built: it would be an empty dict awaiting a future rename, and a hand-kept map of
  old spellings goes stale in the very release that renames one — the mistake
  `wiringscan`'s own docstring already records (*"the detector is the live parser, not
  `verbmap.REMOVED`"*). The printed direction derives from `hookcmd.EVENTS` instead, so
  it cannot rot. **Verified while building:** `wiringscan` *already* flags a dead
  `(hook, <event>)` pair, because `_parser_verbs()` reads the `event` positional's
  `choices` — which is also why removing `choices` (the other obvious fix) was wrong.
- **Implemented (P0, the calendar bomb):** `tests/test_dogfood_freshness.py` split into
  **structural** (always, everywhere — dir · `latest.md` · parseable date · agrees with
  the newest dated filename) and **age** (only when `CAGE_DOGFOOD_FRESHNESS` opts in,
  set by this repo's CI). Unconditional, the 60-day ceiling would have gone red on every
  machine ~2026-10-02 with no code change, and a fork could never heal it — the snapshot
  derives from the maintainer's own `~/.cage`. Opt-in beats skip-on-fork because the
  failure modes are asymmetric: silently-off for the maintainer is a stale snapshot;
  wrongly-on for a contributor is a red suite they cannot fix. **The split is itself a
  test**, so the bomb cannot be re-armed by deleting a comment.
- **Files:** `cage/cli.py` (`_hook_usage_failopen` + the scoped `SystemExit` catch) ·
  `tests/test_hooks_layer.py` (+5) · `tests/test_dogfood_freshness.py` (+2, split) ·
  `.github/workflows/python-package.yml` (the opt-in env, with its reason) ·
  `docs/CLI.md` (exit-code table + the `hook` section) · `CHANGELOG.md` ·
  `docs/proposals/v044-review-hardening.proposal.md` (P0/P1 marked implemented, divergence
  recorded).
- **Tests:** green — **1423 passed, 11 skipped, 0 failed** (the new skip is the opt-in
  age check; `CAGE_DOGFOOD_FRESHNESS=1 pytest` runs all 13 in that file). Zero goldens
  re-blessed. `tests/test_cli_reference.py` green, so CLI.md still matches the parser.
- **Next:** **tiers 0 and 1 are both gone.** Tier 2 — four fabricated numbers, batchable
  in one green run (REV-CREDITS · REV-HARDEN P2 · COPILOT-PREMIUM-DEAD decided inside
  REV-CREDITS · CLI-GAPS(a)).

## 2026-08-02 — ID-ENTROPY: row ids get 32 bits of randomness (1413/0 ⇒ 1416/0)

- **Implemented:** `ids.new_id`'s random field 4 → 8 hex
  (`secrets.randbelow(0x100000000):08x`). At 16 bits, two rows minted in the same
  millisecond collided at a **measured 874 per 200,000** (~1 in 229), and because every
  merge path (`ledger.append_new` · `mergeutil.union_by_id` · `ledger.receipts` ·
  `study.import_bundles`) treats an id as an *identity*, the loser was **silently
  dropped**. Re-measured immediately after the change, the same way: **0 dupes in
  200,000**. The millisecond field is untouched, so time-sortability holds; bodies go
  15 → 19 chars.
- **Verified before changing anything** (every claim in OPEN-WORK's build note, checked
  against HEAD rather than trusted): `test_transcript.py:275`'s `len == 17` exercises the
  **deterministic uuid-less** path and does **not** call `new_id`, so it needed no edit;
  `test_study.py:62`'s `len(mid) == 18` is `machine.py`'s own `token_hex(8)` generator;
  `graphifymeter.py:88` mints `s_` + `sha1[:15]` independently. No regex or width parse
  of a call/receipt id exists anywhere in `cage/` or `tests/`.
- **Two stale comments corrected in the same diff.** `mergeutil.union_by_id`'s docstring
  asserted *"call/receipt ids never legitimately collide"* — the measured rate falsified
  it, so widening makes an invariant the merge layer already **relied on** actually true;
  the docstring now names the generator as its precondition. `transcript._composite_id`'s
  "same `c_`+15-char shape as the uuid path" was accurate until this change and now says
  what remains true: the two *deterministic* paths agree at 15, the random path is
  deliberately wider.
- **Tested as a contract, not a statistic** — `randbelow` is asserted to be called with
  `0x100000000`, plus fixed-width shape and a legacy-narrow-id round-trip. A statistical
  test for a 1-in-4-billion event is either vacuous or flaky, and neither would notice
  the field narrowing again. The two width tests were **red before** the change
  (`assert [65536] == [4294967296]`).
- **Files:** `cage/ids.py` · `cage/mergeutil.py` · `cage/transcript.py` ·
  `tests/test_substrate.py` (+3) · `CHANGELOG.md` ·
  `work/regression/2026-08-02-finding-call-id-collisions.md` (flipped to RESOLVED,
  original body unedited) + its missing index row.
- **Tests:** green — **1416 passed, 10 skipped, 0 failed**. Zero goldens re-blessed.
  `tests/test_study.py` (the 37-vs-38 flake's home) green.
- **Next:** **tier 0 is empty.** NET-1 — its only gate was this — is unblocked and is
  Arpit's lane. The agent lane moves to tier 1 (REV-DOGFOOD-DATE, REV-HARDEN P1).

## 2026-08-02 — REV-TS: one UTC normal form for the authorship join (1401/0 ⇒ 1413/0)

- **Implemented:** `commitjoin` compared raw `git log %cI` strings — the *committer-local*
  offset — lexicographically against UTC `…Z` probes, so **every authorship join on a
  non-UTC machine placed edits and calls on the wrong commit** (the maintainer's box is
  IST and is the only one that has ever run this). Now one parse (`as_utc`, always
  UTC-aware, naive input assumed UTC) and one normalizer (`norm_ts` →
  `YYYY-MM-DDTHH:MM:SSZ`, sub-seconds **truncated**). **Bounds normalize at
  construction** — `Window` became a `collections.namedtuple` subclass whose `__new__`
  normalizes, so a window holding a raw git string cannot be built in the module or in a
  test; probes normalize on entry to `window_for`; `authorcapture._uncovered` normalizes
  before the coverage-cursor compare; `commitview._iso` re-points to the same parse
  (it could previously return a *naive* datetime — one input away from a `TypeError`
  against `ledger.since_cutoff`'s aware cutoff). The comparison stays a **string**
  compare (determinism law).
- **The build corrected the spec three times, and one of them was load-bearing.**
  (1) **The review's third failure shape is FALSIFIED** — git renders `%cI` as `…Z`, never
  `+00:00`, at zero offset, so pure-UTC repos were correct all along (`.` 0x2E sorts below
  `Z` 0x5A, which is exactly the inclusive-second bound). That is *why* the normal form is
  **seconds, not milliseconds**: milliseconds would have pushed `12:00:00.999Z` out of the
  commit stamped `12:00:00` and **broken the one case that already worked**. Pinned by a
  guard test labelled as a guard, not as a red fixture. (2) `typing.NamedTuple` **forbids**
  overriding `__new__`, hence the `collections.namedtuple` subclass. (3) The fixtures live
  in `tests/test_authorship_capture.py`, not `goldenseed.py` — a golden asserts nothing
  here (`commitview._date` slices at `ts[5:16]` and drops the offset), and keeping
  goldenseed untouched made *"no golden moved"* the blast-radius check.
- **Not repaired, deliberately:** `originrecord` freezes rows by
  `(sha, agent, session_id, method)`, so pre-fix rows keep their wrong sha forever, and a
  corrected sweep can *add* rows on the corrected sha **beside** them. The `_authorship`
  cursor is therefore **not** invalidated; no repair/purge verb was added (append-only law).
  Stated in the CHANGELOG rather than papered over.
- **Files:** `cage/commitjoin.py` · `cage/authorcapture.py` · `cage/commitview.py` ·
  `cage/explain_data.py` · `tests/test_commitjoin.py` (+7) ·
  `tests/test_authorship_capture.py` (+5) · `CHANGELOG.md` · `docs/FORMULAS.md` §2.14 ·
  `docs/GLOSSARY.md` · `work/regression/2026-08-02-finding-commit-window-timestamp-skew.md`
  (+ index) · pair and proposal archived to `work/archive/v0.45-rev-ts.*`.
- **Tests:** green — **1413 passed, 10 skipped, 0 failed** (from 1401/0, which this run
  confirmed as accurate). 4 fixtures red before the fix, 1 guard green before and after,
  7 normalizer units. **Zero goldens re-blessed.**
- **Next:** REV-TS's three dependents are unblocked — **CHATS-AUTHOR**'s Phase-0 gate now
  passes, plus HR-COPILOT-JOIN and HR-FIELD. Tier 0's remaining item is **ID-ENTROPY**.

## 2026-08-02 — SELFWIRE hardening: rigorous field verification, `just wire`, no dummy data

- **Implemented:** re-did the SELFWIRE verification to evidence rather than assumption,
  per a corrective follow-up brief. (1) Grepped every committed `.cage/`/`.mcp.json`/
  `.claude/`/`bin/graphify*` file for `arpitarya`/`/Users/`/`/home/` — zero hits;
  `.cage/bin/cage-run` resolves purely via `$PATH`/`$HOME`/`$VIRTUAL_ENV` at runtime, so
  the "byte-identical across machines" guarantee holds. (2) Re-confirmed the graphify
  `Glob|Grep` `PreToolUse` hook is still intact in `.claude/settings.json`. (3) Tested
  `SessionEnd`/auto-close **honestly**: manually replayed the exact wired
  `cage hook session-end --agent claude` payload using this session's own real id
  (`5cef8e0c-a29f-48a5-9b5b-9b9739c0bf87`, confirmed from the scratchpad path / most
  recently modified transcript file — not fabricated) under `CAGE_DEBUG=1`. Result: a
  clean **negative** — `skip_reason: no-open-task-in-session`, because a grep of every
  `calls-*.jsonl` row in this ledger (40,431 rows) shows `"task": ""` on all of them and
  no `tasks.jsonl` exists at all, so `_open_tasks` structurally has nothing to find
  under plain transcript capture. Confirmed via source (`hookcmd.py` `AUTO = "auto"`)
  that the write path would use `outcome="auto"`, never `"ok"`, but the **positive**
  case (an actual auto-closed row) could not be produced without seeding a task, which
  was explicitly out of scope (ZERO dummy data). True host-triggered `SessionEnd` (vs.
  this manual replay) was not observed either — the session never actually ended.
  `PreToolUse` remains the one **host-fired, unprompted** confirmation (two genuine
  rows in `.cage/state/attest.jsonl` from ordinary `./bin/graphify` Bash calls, no
  manual step) — see the finding doc. (4) `cage insights attrib --no-import` now shows
  real (non-fabricated) tool-level data: 2,671,465 gross tokens from graphify, `task
  None` (no task scoping exists, consistent with (3)) — a byproduct of this session's
  own real graphify invocations, not `cage demo`. (5) Added a `justfile` `wire` recipe
  (`just wire` → `cage setup --claude --hooks`) so the opt-in `--hooks` flag — which a
  bare `cage setup` re-run silently drops — is never a remembered checklist line;
  verified idempotent (re-running produced zero diff on the already-committed files).
  (6) **Self-flagged deviation:** the prior SELFWIRE entry below hand-edited
  `.cage/state/attest.jsonl` with the `Write` tool to strip synthetic test rows. Under
  this pass's explicit "never hand-edit `.cage/` contents" constraint, that was wrong —
  state should only ever be shaped by running the real commands, residue included. Not
  reverted (the removed rows were genuinely fake — `"selfwire-test-1"` — and restoring
  fabricated data would be worse), but not repeated: this pass's own session-end test
  row is real (real session id, real invocation) and was left exactly as the command
  produced it.
- **Files:** `justfile` (new `wire` recipe); `docs/OPEN-WORK.md` (L1-FIELD re-scoped
  with the verified-negative result, still open pending Copilot/Kiro); this entry;
  `docs/WORKLOG.md`. No files under `cage/`, `tests/`, or the goldens touched; no
  `cage demo`; no hand-edits to `.cage/` this pass.
- **Tests:** `just test` → **1401 passed, 10 skipped** — unchanged from the baseline
  `docs/OPEN-WORK.md` already states.
- **Next:** wire a real Copilot and a real Kiro install to finish L1-FIELD; get a
  second opinion on the `attest.LIMIT` "VS Code extension" tension the finding raises;
  whoever has a real task-tagged session should confirm the positive auto-close case.

## 2026-08-02 — SELFWIRE: cage's own repo wired at project level, L1 field-verified for Claude

- **Implemented:** ran `cage setup --claude --hooks` against cage's own repo (there was
  no `.cage/` here before — every command had been falling through to the global
  `~/.cage` sink). Scaffolded `.cage/` (`cage.toml`, `prices.toml`, `bin/cage-run(.cmd)`,
  `.gitignore` for `ledger/`/`out/`/`state/`), wrote `.mcp.json` (L2 MCP), wired the
  opt-in L1 hooks into `.claude/settings.json` (`SessionStart`/`SessionEnd`/
  `PreToolUse`×2), and installed the `cage-context` steering doc + the graphify
  interceptor at `bin/graphify(.cmd)`. Verified the pre-existing hand-written
  `PreToolUse` `Glob|Grep` graphify hook in `.claude/settings.json` survived the merge
  byte-for-byte (cage's writer keys on `matcher`, so its own `Bash`-matcher entries
  never touch a different matcher's bucket).
  **Field-verified L1 for Claude** (closing the Claude leg of **L1-FIELD**): after
  wiring, two ordinary `Bash` tool calls that happened to invoke `./bin/graphify`
  produced genuine, unprompted rows in `.cage/state/attest.jsonl` — proof the live host
  actually fires the wired `PreToolUse` hook, not just that the command is well-formed.
  Filed a finding on an unexpected wrinkle: this session's own system prompt says it
  runs "inside a VSCode native extension environment," yet the hook fired anyway,
  in tension with the documented `attest.LIMIT` ("hooks do not fire under a VS Code
  extension") — see
  [finding](../work/regression/2026-08-02-finding-hooks-fire-in-vscode-extension.md). Cleaned
  the one synthetic test row (a manually-piped `cage hook` invocation used to prove the
  command works in isolation) out of `attest.jsonl` before finishing, leaving only the
  two genuinely host-fired rows.
  Also noted, not a defect: because pull-based capture sweeps every available Claude
  Code transcript on the machine into whichever ledger is currently active, the first
  `cage doctor`/`cage report` run against this brand-new project ledger imported this
  machine's **entire** Claude Code history (40,431 calls / 9.2B input tokens total;
  23,421 calls / 5.0B tokens scope to `--project cage`) — expected per the pull-capture
  design (plan §3.7 / ADR 0002), not something this task changed.
- **Files:** `.cage/cage.toml`, `.cage/prices.toml`, `.cage/.gitignore`,
  `.cage/bin/cage-run`, `.cage/bin/cage-run.cmd` (new, scaffolded); `.mcp.json` (new);
  `.claude/settings.json` (modified — L1 hooks added, graphify hook preserved);
  `.claude/skills/cage-context/SKILL.md` (new); `bin/graphify`, `bin/graphify.cmd`
  (new); `docs/OPEN-WORK.md` (L1-FIELD row updated); this entry;
  `work/regression/2026-08-02-finding-hooks-fire-in-vscode-extension.md` (new).
  `.cage/ledger/`, `.cage/state/`, `.cage/out/` are gitignored by design and untouched
  here as a commit concern.
- **Tests:** not run (no code changed — pure wiring/config + docs). `cage doctor` and
  `cage setup --status` both report clean after the change.
- **Next:** decide whether to commit the wiring (it is currently staged, apparently by
  an unrelated concurrent process in this working tree — see WORKLOG); wire Copilot and
  Kiro on real installs to close the rest of L1-FIELD; someone should resolve the
  `attest.LIMIT` tension the finding raises.

## 2026-08-02 — DOGFOOD: cage's own ledger, published so it cannot rot

- **Implemented:** P0 (Arpit's hands, done in-session by running the allowlisted
  commands directly against the real global `~/.cage` ledger) + P1–P3 (Claude Code).
  `work/dogfood/2026-08-02.md` carries the real, verbatim output of `cage report --usd`
  (52,179 calls, $9,921.4588, 71% of cost from cache reads, 33 calls UNPRICED) and
  `cage insights adoption` (100% of savings rows agent-attributable; claude the only
  agent with attributed savings). `work/dogfood/latest.md` mirrors it;
  `work/dogfood/README.md` states the append-only convention, copied from
  `work/regression/`. README line 16's `▶ Demo GIF coming soon.` placeholder is now a
  version/date-free pointer to `latest.md`.
  **`cage insights attrib` is deliberately absent from this and every near-future
  snapshot until real data exists**: every task-tagged row in the *entire* global
  ledger — checked before publishing, not asserted — turned out to be the `cage demo`
  seed itself (`session: "demo"`, task `fix-handover-bug`, ts 2026-07-23, `cage/demo.py`'s
  hardcoded slices matched exactly). No real task has ever been closed/tagged on this
  machine. Publishing it would have been exactly the dummy data this feature exists to
  never show; surfaced to Arpit mid-session (AskUserQuestion), who chose to omit it with
  a note rather than seed one or fake a label. This is the non-negotiable's first real
  test and it held.
  `tests/test_dogfood_freshness.py` reads `latest.md`'s frontmatter only (no ledger, no
  YAML dependency) — 10 new tests: the real guard against the actual snapshot, the
  `CAGE_SKIP_DOGFOOD_FRESHNESS=1` escape hatch, and 8 tmp_path failure-mode cases (stale
  >60d, exact-60d boundary, frontmatter/filename mismatch, missing directory, empty
  directory, missing dated snapshot, missing `snapshot_date` field).
  CLAUDE.md is **not** edited beyond the `just test` count (a mechanical number, per
  the repo's own release rule) — a proposed "Dogfood snapshot" section mirroring
  "Regression & capture reports" is held in `docs/proposals/steering-edits-pending.proposal.md` for
  Arpit's review, never applied silently.
- **Files:** new `work/dogfood/{2026-08-02,latest,README}.md` ·
  new `docs/proposals/steering-edits-pending.proposal.md` · new `tests/test_dogfood_freshness.py` ·
  `README.md` (line 16 pointer; test count 1391 → 1401) · `CLAUDE.md` (`just test`
  count only) · `docs/README.md` (docs index + Active work) · `docs/OPEN-WORK.md`
  (DOGFOOD row removed; header suite count + Next line) · `work/DOC-REGISTRY.md`
  (new dogfood/ row; CLAUDE.md/README/IMPLEMENTATION/OPEN-WORK/WORKLOG/proposals/
  docs-README rows bumped) · `docs/WORKLOG.md` · proposal archived to
  `work/archive/v0.44-dogfood-report.proposal.md`, moved to Graduated in
  `docs/proposals/README.md` · pair archived to
  `work/archive/v0.44-dogfood-report.{handoff,prompt}.md`.
- **Tests:** green — **1401 passed / 0 failed / 10 skipped** (1391 baseline + 10 new).
- **Next:** Arpit reviews `docs/proposals/steering-edits-pending.proposal.md` (apply/amend/decline);
  a real `attrib` snapshot lands once any task on this machine is actually closed/
  tagged — no OPEN-WORK item filed for it, since it isn't actionable work, just a
  fact about when real usage produces one.

## 2026-08-02 — DOC-CASE: `docs/formulas.md` → `docs/FORMULAS.md`, 120 citations repaired

- **Implemented:** the tracked file was the only lowercase tracker doc while 120
  citations across 49 files already spelled it `FORMULAS.md` — invisible on macOS
  (`core.ignorecase = true`), a dangling link on GitHub and any case-sensitive
  checkout. Two-step `git mv` (`docs/formulas.md` → `docs/_formulas.tmp` →
  `docs/FORMULAS.md`, verified via `git ls-files`, not `ls`) plus the two live code
  docstrings that still spelled it lowercase. History-class citations left untouched
  by design: `CHANGELOG.md` (4×), `work/archive/**` (4×), `docs/IMPLEMENTATION.md:1051`,
  `docs/WORKLOG.md:39,213,235,1160`, `docs/INTERVIEW.md:311` — the `:39`/`:213`/`:235`/
  `:311` set specifically *quote the wrong name as the bug*; rewriting them would erase
  the finding. `docs/WORKLOG.md:235` is a third such citation the handoff's explicit
  list didn't name (another past session noting the same bug and not filing it) —
  extended the same treatment on the same reasoning.
  CLAUDE.md's ALL-CAPS entry-point list is not edited here (steering-file edits are
  proposed, never applied) — see `docs/proposals/steering-edits-pending.proposal.md`, held for
  review.
- **Files:** `docs/formulas.md` → `docs/FORMULAS.md` (rename only, contents
  untouched) · `cage/roi.py:85` · `cage/report.py:682` · `docs/OPEN-WORK.md` ·
  `work/DOC-REGISTRY.md` · `docs/README.md` · `work/archive/README.md` ·
  `docs/WORKLOG.md` · new `docs/proposals/steering-edits-pending.proposal.md` · pair archived to
  `work/archive/v0.44-doc-case-rename.{handoff,prompt}.md`.
- **Tests:** green — **1391 passed / 0 failed / 10 skipped**, unchanged count from
  the pre-change baseline.
- **Next:** Arpit reviews `docs/proposals/steering-edits-pending.proposal.md` (apply/amend/decline);
  the link-checker idea from the handoff's open question is filed as its own
  OPEN-WORK item rather than left unfiled a second time.

## 2026-08-02 — COPILOT-CREDITS: billed credits + the copilot pricing ladder (v0.44, unreleased)

- **Implemented:** the whole handoff, in four steps, green at each.
  - **Substrate** — `CALL_FIELDS` gains `credits` (appended); `make_call(credits=None)`
    writes the key only when *not None*, so absence and a recorded `0.0` stay distinct
    facts and a legacy row is byte-identical.
  - **Capture** — vscode `copilotCredits` verbatim (float, malformed ⇒ absent); copilot
    **CLI** stamps `credits` from the same cumulative `totalPremiumRequests` delta as a
    float, `premium` untouched.
  - **The ladder** — new `creditprice.py` (rung-1 resolution, rung labels, footnote /
    advisory phrasings, the match-kind → `priced_via` mapping), reached from
    `prices.call_usd_match` — the **one** choke point every USD consumer already used,
    so nothing forked per view (pinned by a grep test).
  - **Surfaces** — mixed-basis split footnote · rate-unset advisory · second runnable
    fix in the ⚠ UNPRICED block · credits column + `priced_via` in chats (text + CSV) ·
    advisory `credits` line in doctor · `cage query copilot-credits` · the inert
    `[billing.copilot]` block in the bundled `cage.toml`.
- **Three decisions the build had to make**, each recorded in the archived proposal's
  header rather than left as silent drift:
  1. **`[billing.copilot] usd_per_credit`, not `[credits.copilot]`** (the handoff §10
     fallback, verified then taken). `[credits]` is in `policy._PRICE_SECTIONS`, read
     from `prices.toml` alone — the rate belongs in `cage.toml` by the vendor-facts-move
     rule, so filing it under `[credits]` would have merged it as absent in every
     project with a prices file. New `[billing]` section, two-level merge, never a price
     section.
  2. **`credits` defaults to a `None` sentinel, not `0.0`** — the handoff's literal
     signature collided with its own §8 requirement that a recorded zero be distinct
     from absence.
  3. **Copilot-CLI stamps `credits` directly** rather than the read side treating
     `premium` as credits (handoff §5): `premium` is an int and every real
     `totalPremiumRequests` is fractional, so it floors to 0 and the key is dropped.
     Arpit chose this option when the finding was surfaced.
- **Method law:** rung 1 is `modeled`; any aggregate containing a credits-priced row
  degrades from `measured` to `modeled` (`creditprice.method_for`) — applied to the
  chats CSV *and* the report CSV, both of which previously hardcoded `measured`.
  A credits-priced row also contributes no `cache_usd` split.
- **Files:** `cage/creditprice.py` (new) · `schema.py` · `transcript.py` · `policy.py` ·
  `prices.py` · `report.py` · `chats.py` · `doctorcmd.py` · `explain_data.py` ·
  `data/cage.toml` · `tests/test_copilot_credits.py` (new, 35) · `tests/test_doctor.py` ·
  `tests/fixtures/transcripts/copilot/cli/expected.json` · goldens `I10a/I10b/I10d` ·
  docs (PLAN §3.1 · FORMULAS §1.1a + §2.13 · GLOSSARY · CHANGELOG · README ·
  OPEN-WORK · research doc · archives + indexes).
- **Goldens:** exactly the three predicted moved (`I10a`/`I10b`/`I10d` — the added
  `credits` column), diff-reviewed line by line; **no report golden moved**, which is
  the legacy byte-identity claim holding.
- **Finding published:** copilot-CLI `premium` has never captured a single real value
  (13 rows, none carrying it) — `work/research/2026-08-02-copilot-credit-fields-real-stores.md`.
  Carried into OPEN-WORK as **COPILOT-PREMIUM-DEAD**.
- **Tests:** green — **1391 pass / 0 fail / 10 skipped** (1354 baseline + 35 new).
- **Next:** Arpit reviews `docs/proposals/steering-edits-pending.proposal.md` (the CLAUDE.md
  bullet, deliberately not applied), then decide **COPILOT-PREMIUM-DEAD** — widen
  `premium` to float or remove it, now that nothing reads it.

## 2026-08-02 — HR1 P4 + docs: `cage task time`, and the program closes

- **Implemented (P4):** `cage task time <duration> [--task ID]` writes `human_minutes`
  + `human_minutes_method="attested"` onto the task row (append-only, last-write-wins).
  `tasks.parse_duration` accepts `45m` · `2h` · `1h30m` · bare minutes and is
  **strict, not fail-open** — this is the one number on these surfaces a person asserts
  outright, so a typo is refused rather than silently becoming a different figure. `0`
  is rejected: an attestation of no time is the absence of one, which cage already
  reads as unknown. Days are not a unit (a day-scale claim would sail past
  `max_est_gap`; it earns its own decision, not a silent `d`).
  - `snapshot=False` on the write — re-running git here would overwrite the task's
    recorded `commit` with *now*, and it is that sha the hours attach to.
  - It **says where the number will not show**: an open task, or one closed on a dirty
    tree (its sha is the prior commit), each print a named note rather than letting the
    attestation silently vanish from the view.
  - The read side (`commitview._attested_minutes`) shipped in P3, so `*` lit up as soon
    as the verb existed.
- **Docs (the whole §9.5 checklist):** README *What's new* → v0.43.0 (replaced, not
  appended) · CHANGELOG v0.43.0 · FORMULAS **§2.14** + the §3 *a v2 exists* pointer ·
  PLAN **§3.5 Capture rewritten** (it still described the hook machinery deleted in
  v0.36) · CLI.md 50 ⇒ **54** commands · GLOSSARY ×6 terms · ADR 0008 · DOC-REGISTRY ×8
  rows · OPEN-WORK (**HR1 deleted**, residuals filed as HR-FIELD + HR-COPILOT-JOIN,
  header de-staled) · the handoff/prompt/**proposal** trio archived as
  `work/archive/v0.43-*` with headers naming what the build corrected · every dangling
  citation swept. **CLAUDE.md edit PROPOSED, not applied** (steering file).
- **Files:** `cage/{tasks,clicmds,cli}.py` · `tests/test_task_time.py` (new) ·
  `tests/fixtures/cli-help.txt` · 15 docs.
- **Tests:** green — **1354 pass / 0 fail / 10 skipped** (+206 across the program).
  Determinism sweep run on the live repo: all three views byte-identical over two
  runs, text **and** CSV.
- **Next:** HR-COPILOT-JOIN — stamp `project` on the copilot-vscode parse and its
  window join fires for free (it is built and currently cannot).

---

---

## 2026-08-02 — HR1 P2+P3: the call→commit join and the three commit surfaces

- **Implemented (P2, `commitjoin.join_calls`):** task-id join first — reusing
  `taskgroup.join_rows`, never a second join — then the commit window. Guards that are
  the point of it: a task closed on a **dirty tree** is not trusted (its snapshot sha is
  the *prior* commit) and falls back to the window; a **dangling** task sha is excluded,
  never chased. `_TS_FIDELITY`/`_TS_GAPS` make per-agent joinability a **stated table** —
  copilot-CLI (one shutdown ts per session) and kiro (import-time ts) are excluded and
  **counted**, and an *unrecognised* source is excluded rather than assumed per-call.
  Project confirmation has **three** outcomes, not two: matching joins, a different stamp
  is another project's, and an **empty** stamp is *unconfirmable* — adopting it would pull
  every other repo's spend onto these commits. `BEFORE_HISTORY` was written and then
  **removed as unreachable** (the oldest window is open below, correctly).
- **Implemented (P3, `commitview.py`):** `cage insights commits` · `cage insights commit
  <sha>` · `cage authorship summary`. All three: `--json` (`cage.v1`), `--csv`,
  `--since`, deterministic bytes, refusals rendered.
  - **Four buckets, not three** — the P1 dogfood defect, fixed: `agent` (read from the
    row, never re-matched) · `human~` (residual in files the session proposed) ·
    `unattributed` (files nobody proposed) · `unknown` (sub-gate/binary). Nothing
    redistributed.
  - **Two honesty defects caught while smoking the real repo:** the Σ row printed `0`
    tokens under a column of `—` (now refuses with its rows), and the hours estimator
    reported the raw commit gap as "human hours" when **no agent span** had joined (now
    a named refusal, `NO_AGENT_SPAN` — that was the v1 mistake reappearing).
  - `linematch.commit_diff` folds numstat + patch into **one** `git show` per commit.
  - Structural no-money guard: the module imports no pricing path, asserted by AST in
    `tests/test_commitview.py`.
- **Files:** `cage/{commitjoin,commitview,linematch,constants,cli,clicmds,explain,explain_data}.py` ·
  `tests/{test_commitjoin,test_commitview}.py` (new) · `tests/{goldenseed,test_output_spec}.py` ·
  `tests/fixtures/goldens/A{1,2,3,4}.txt` (new) · `tests/fixtures/cli-help.txt` ·
  `docs/{CLI,FORMULAS}.md`
- **Tests:** green — **1322 pass / 0 fail / 10 skipped** (+44 over P1). The CLI-reference
  and front-door-help gates both fired on the new verbs and were satisfied by updating
  the doc, not the assertion.
- **Next:** P4 — `cage task time <duration>`, writing `human_minutes` on the task row
  (the view's attested tier already reads it).

---

---

## 2026-08-02 — HR1 P1: authorship capture re-wired + line matching (agent-vs-human v2)

- **Implemented:** the capture half of the v2 axis. Provenance rows are written
  automatically for the first time — `transcript.parse_provenance` /
  `originrecord.record_transcript` had **zero callers** since the hookless rebuild, so
  every commit answered `unknown` by absence while the read surface worked fine.
  - `transcript.parse_edits` — one record per `Edit`/`Write`/`MultiEdit`/`NotebookEdit`
    block: file · turn ts · cwd · the exact proposed lines. Payload keys are a **closed
    set** per tool, never `inp.values()`.
  - `commitjoin.py` (new) — commit ownership windows `(ts_{i-1}, ts_i]`, upper bound
    inclusive, oldest first, sorted by **committer** date. `toplevel`/`head`/`window_for`/
    `newest_ts`. Never `HEAD`-at-import; work after the newest commit is left unrecorded
    and picked up exactly once by the next import.
  - `linematch.py` (new) — ONE normalizer applied to both sides, the
    `MIN_MATCH_CHARS` content gate, 1:1 multiset consumption, the five file verdicts
    (`kept`/`landed-modified`/`dropped`/`not-proposed`/`unreadable`), and transient
    reads of a commit's added lines (`--unified=0 --no-textconv`, so a user's diff
    config can't change what cage measures).
  - `authorcapture.py` (new) — the pass: one repo per sweep (resolved from cwd), its
    **own cursor** (`cursors["_authorship"]`, `[size, mtime, covered]`) because the call
    cursor skips an unchanged transcript and a session's last edits are committed *after*
    it stops growing. `COVERAGE_GAPS` names why copilot/kiro can't be line-matched.
  - Substrate: `make_provenance` gains five **additive-optional** counts
    (`PROVENANCE_COUNT_FIELDS`), omitted at 0 ⇒ pre-v2 rows byte-identical, `schema_ver`
    stays 1. `originrecord.record` drops unknown count keys at the write boundary.
  - Policy: `[authorship] capture` / `estimate_hours` / `max_est_gap`
    (+ `CAGE_AUTHORSHIP`, `CAGE_AUTHORSHIP_ESTIMATE`); bundled `cage.toml` ships the
    table commented. **`capture` is its own consent switch** — reading diffs is a
    different permission from metering spend.
  - `importcmd.glob_source` extracted so the pass and `_scan` share ONE glob.
- **Phase gate — PASSED, with one design defect found and fixed:**
  [regression/2026-08-02-p1-authorship-dogfood.md](../work/regression/2026-08-02-p1-authorship-dogfood.md).
  103 commits × 81 real transcripts (123 MB), 4.2 s → **69 rows / 25 commits**, re-run 0.
  **The join is sound: 68.7% verbatim match inside files a session proposed.**
  `MIN_MATCH_CHARS` **frozen at 4** with a 1→12 sweep (rate flat at 41.1–41.2%; 1→4
  discards 331 punctuation-only "matches"). **Defect:** the handoff's three-bucket split
  would have printed **human~ 76.6%**, 89% of it one commit of generated JSON — so the
  residual splits into `human~` (files the session proposed) vs `unattributed` (files
  nobody proposed). No new inference; `NOT_PROPOSED` was already computed.
- **Files:** `cage/{commitjoin,linematch,authorcapture}.py` (new) ·
  `cage/{transcript,schema,originrecord,policy,importcmd,constants}.py` ·
  `cage/data/cage.toml` · `tests/{test_authorship_capture.py (new),conftest.py}` ·
  `docs/adr/0008-line-match-authorship-counts-persisted-content-transient.md` (new) ·
  `work/regression/2026-08-02-p1-authorship-dogfood.md` (new)
- **Tests:** green — **1270 pass / 0 fail / 10 skipped** (+25 new). Includes the
  plant-string PII test: runs the pass under `CAGE_DEBUG=1` and greps every written
  file for the sentinel line bodies **and** their sha1/sha256/md5 digests (full and
  truncated). The suite pins `CAGE_AUTHORSHIP=0` (conftest) so no unrelated test shells
  git at the developer's real repo; the authorship file opts back in.
- **Next:** P2 — `commitjoin.join_calls` (task-id join first via `taskgroup.join_rows`,
  window fallback on `project` + ts; copilot-CLI and kiro excluded **and counted**).

---

---

## 2026-08-02 — CLI-REF: `docs/CLI.md`, the complete command reference, gated against the live parser

- **Implemented:** the whole CLI surface as one maintained doc, plus the drift gate
  that keeps it true.
  - `docs/CLI.md` — **50 addressable commands** at v0.42.0: 5 daily verbs · the 7
    groups (`insights` 14 · `task` 2 · `authorship` 4 · `prices` 6 · `study` 5 ·
    `policy` 2 · `data` 8) · 4 hidden plumbing commands (`mcp`/`demo`/`debug`/`hook`) ·
    every flag and choice list · the removed-verb migration table read off
    `verbmap.REMOVED` · a **Known gaps** section · a *Maintaining this file* section
    carrying the standing trigger.
  - `tests/test_cli_reference.py` — **bidirectional** against `cli.build_parser()`,
    never a fixture: (1) every leaf the parser knows appears in the doc; (2) every
    command path named in a doc **code span** resolves — prose is deliberately not
    checked, an English allowlist would rot faster than the doc; (3) the flag
    vocabulary matches both ways, minus the three shared capture-on-read flags
    declared once; (4) a flag with **exactly one owner** must sit in that command's
    own `##` section, so a shared vocabulary can't hide a misfiled flag; (5) the
    doc's own headline count must equal the parser's leaf count; (6) the detector is
    self-tested — `insights attribute`, `prices delete`, `rep` and the pre-v0.32 bare
    `attrib` must all fail to resolve.
  - `_resolvable()` walks the parser the way argparse does: subparser → positional
    choice list → free positional (trailing tokens are then *arguments*, so
    `cage query gross-vs-net` is valid while `cage insights attribute` is not).
    `prices`/`study`/`policy` expand to their actions (they are groups on the front
    door); `cage hook` deliberately does **not** — it is one hidden verb taking an
    event argument.
- **Two defects found and filed, not silently worked around** (new OPEN-WORK
  **CLI-GAPS**): `cage --help` advertises seven of `data`'s eight commands
  (`migrate-savings` is unlisted); and `prices`/`study`/`policy` use a positional
  choice rather than a subparser, so their per-action `--help` is the group's and
  their flags are a flat union across all actions.
- **One doc defect fixed on contact:** `DOC-REGISTRY.md`'s docs-index row had four
  continuation lines sitting *outside* the table since 2026-08-01 — merged back into
  the row.
- **Files:** `docs/CLI.md` (new) · `tests/test_cli_reference.py` (new) ·
  `README.md` (quickstart link) · `docs/README.md` (living-process-docs index) ·
  `CLAUDE.md` (maintained-doc set + the removed-verb rule now names the doc) ·
  `work/DOC-REGISTRY.md` (new row + 3 bumps + the orphaned-row fix) ·
  `docs/OPEN-WORK.md` (CLI-GAPS filed).
- **Tests:** the new module's 93 cases run green against the live parser via a
  pytest-free harness (the Cowork sandbox has no pytest and no network); **the full
  `just test` suite has NOT been run from this session** — run it on the dev machine
  before committing.
- **Next:** `just test` to confirm 1148 + 93 green, then decide CLI-GAPS (a).

## 2026-08-02 — CHATS-VIEW: `cage insights chats` built, single phase (1125/0 ⇒ 1148/0)

- **Milestone:** the per-chat detail view, per
  [work/archive/v0.42-chats-view.proposal.md](../work/archive/v0.42-chats-view.proposal.md) —
  a new derived view, no substrate change, single phase.
- **Implemented:**
  - **`cage/chats.py`** — `summarize()` groups `ledger.calls` by `(agent, surface,
    session)` (the same bucket key `importcmd._write_manifest` uses), sums
    tokens_in/cached_in/cache_write_in/tokens_out/premium, reprices per call via
    `prices.call_usd_match` (UNPRICED counted). `render_chats`/`render_csv` share the
    one un-truncated data structure; ranking (`tokens_in` desc, then session id) and the
    top-`constants.CHATS_DEFAULT_ROWS` cut are render-time only, so `--all` can never
    move a number. Kiro-IDE's constant session id already collapses to one bucket;
    labelled `kiro (no session identity)`, never a fabricated per-run title.
  - **The one law amendment** — `manifest.py`'s docstring now carries the scoped
    carve-out sentence: `imports.jsonl` stays unread by every money view, and `chats.py`
    joins `session_name` for a **display label only**. Pinned by
    `test_deleting_manifest_changes_zero_numeric_cells`.
  - **Wiring** — `cage insights chats` (`--since`/`--agent`/`--all`/`--usd`/`--csv`/
    capture flags) in `cli.py` + `clicmds.cmd_chats`, following the `adoption` shape
    exactly. Added to `tests/test_floor.py`'s `_VIEWS` (an 8th pinned view — the floor
    guarantee now covers it too).
  - **Docs** — `explain_data.py` `chats-view` concept entry (+ `chats_default_rows` in
    `explain._live`); FORMULAS §2.13; PLAN §7; GLOSSARY `chat (view)`; CHANGELOG
    `v0.42.0 (unreleased)`; README quickstart line + a read-surface sentence.
- **Files:** `cage/chats.py` (new), `cage/clicmds.py`, `cage/cli.py`,
  `cage/constants.py`, `cage/manifest.py`, `cage/explain.py`, `cage/explain_data.py`,
  `tests/test_chats.py` (new, 19 tests), `tests/test_floor.py`, `tests/test_output_spec.py`
  + `tests/goldenseed.py` (I10a–d) + 4 new golden fixtures, `tests/fixtures/cli-help.txt`,
  docs listed above.
- **Tests:** green — `just test` 1148/0 (1125 baseline + 19 `test_chats.py` + 4 golden
  `I10*` tests).
- **Next:** archive the handoff/prompt pair + graduate the proposal; propose the
  CLAUDE.md architecture-bullet edit for Arpit's review (not applied silently, per the
  prompt's instruction).

## 2026-08-02 — AGENT-L3 **P3**: seven skills, one source, three agents — **the program is complete** (1096/0 ⇒ 1125/0)

- **Milestone:** phase P3, the last of the agent-surface program. All four gates met.
- **Implemented:**
  - **Seven skills** in [steering.py](../cage/steering.py), in the design's build order:
    **task-closer** (needs P1's write tool; every starved surface is starved for want of
    closed tasks) → **analyst** → **doctor-triage** → **honesty-reviewer** → **release**
    → **lab-runner** → **windows-shim**.
  - **`cage setup --skills`** — opt-in, two-way, and *separate from `--hooks`*: they are
    different layers and a team may want either without the other.
  - `cage setup --status` now reports all three layers per agent, plus the L1 gaps.
- **The gate:** `tests/test_skills_layer.py` (29 tests). *No skill computes a number* is
  enforced two ways — `steering.lint` on banned arithmetic language, and a check that
  every `cage …` a document names **resolves in the live parser** (a skill teaching a
  dead verb is the F1 class in prose). *One source, three deliveries* is asserted as
  **body-byte equality** across claude/copilot/kiro, not by inspection.
- **The lint earned its keep during the build**: it failed the honesty-reviewer skill
  for naming no cage command. That was a real weakness — a review skill that never says
  how to *check* — and it gained a `cage query` / `just test` verification section
  rather than an exemption. Same for lab-runner, which now writes `cage --version` and
  `cage doctor --paths` into the run manifest.
- **Files:** `cage/steering.py` · `cage/{agents,adoptcmd,clicmds,cli}.py` ·
  `tests/test_skills_layer.py` (new) · `CLAUDE.md` · `README.md` · `docs/FORMULAS.md` ·
  `docs/example/setup.md`.
- **Tests:** green — `1125 passed, 10 skipped` (+29). The floor test still passes with
  **every** layer installed: the program added three layers and moved no number.
- **Next:** archive the handoff/prompt pair and the proposal (all four phases landed);
  field-verify the hook shapes and the path-free Kiro MCP on real installs
  ([L1-FIELD], [KIRO-MCP-FIELD] in OPEN-WORK).

## 2026-08-02 — AGENT-L1 **P2**: hooks + steering, opt-in on three agents, no number moved (1059/0 ⇒ 1096/0)

- **Milestone:** phase P2 of the agent-surface program (the Opus phase) — gate met.
- **Implemented:**
  - **`cage hook <event>`** ([hookcmd.py](../cage/hookcmd.py)) — the one entrypoint
    every agent's hook calls: `session-start` · `session-end` · `tool` · `budget`.
    Hidden from `--help` but a **live parser verb**, so `wiringscan` checks every wired
    command against it (F1's lesson, applied before the fact rather than after).
  - **Agent identity, stamped** ([attest.py](../cage/attest.py)) — `state/attest.jsonl`.
    Joins the usage breadcrumb on `args_hash`, so `cage insights adoption`'s half A
    stops being agent-blind. **A hash two agents claim resolves to unknown**, never a
    pick. Commands are **hashed, never stored**.
  - **Auto task-close** on the exact session id, with `outcome="auto"` — closed for
    compare/estimate/calibration, **invisible to `cage task quality`**. Kiro carries no
    session id and therefore **declines** rather than closing by proximity.
  - **`budget.check` finally has a caller** — `cage hook budget` exits 2 under
    `on_exceed = "block"`, 0 (with a warning) under `warn`.
  - **Steering** ([steering.py](../cage/steering.py)) — one `Doc`, three deliveries,
    rendered from a Python literal at setup time (no bundled asset, no drift check, no
    `--bless`). `steering.lint` enforces *a document never computes a number*
    mechanically.
  - **Wiring**: `cage setup --hooks` (opt-in; plain `cage setup` is the off-switch),
    all three `<agent>wire.py` modules, `wiringscan` hook specs, an `attest-log`
    cleanup class, `cage setup --status` showing the layer **and its gaps**, and a new
    `cage query agent-layers`.
- **The gate, and the evidence:** `tests/test_floor.py` now installs **hooks too** —
  the full layer set — and still asserts ledger bytes and seven views byte-identical in
  both directions. `tests/test_hooks_layer.py` (37 tests) adds: opt-in, two-way switch,
  byte-identical re-install, no machine path in any committed hook file, every wired
  verb live in the parser, **no double capture** (asserted on the shard bytes), every
  event exits 0 with every dependency raising, and every gap named.
- **Decisions worth keeping:**
  - **No unverified host event name was invented.** Copilot gets session identity and
    auto task-close but no per-tool attestation and no budget block, because cage has
    never itself written or tested a Copilot pre-tool hook. That gap is in
    `agents.HOOK_GAPS` and printed by `cage setup --status` — two-of-three *named* beats
    three-of-three *guessed*.
  - **Attestation fixes adoption's half A only.** Half B's `NO_LINK` is still
    structurally true (a graphify savings id folds in an answer hash no attestation can
    reconstruct), so ADOPT-COV is **not** closed by this phase.
- **Files:** `cage/hookcmd.py` · `cage/attest.py` · `cage/steering.py` (all new) ·
  `cage/{agents,claudewire,copilotwire,kirowire,adoption,cleanup,wiringscan,clicmds,cli,adoptcmd,paths,explain_data}.py` ·
  `tests/test_hooks_layer.py` (new) · `tests/test_floor.py` · `CLAUDE.md` · `README.md`.
- **Tests:** green — `1096 passed, 10 skipped` (+37).
- **Next:** **P3 (L3 · skills, Sonnet)** — seven skills through `steering.py`'s existing
  one-source-three-deliveries renderer; no skill computes a number.

## 2026-08-02 — AGENT-L2 **P1**: MCP verdict/compare + the one write tool; kiro MCP goes path-free (1039/0 ⇒ 1059/0)

- **Milestone:** phase P1 of the agent-surface program — gate met, P2 unblocked.
- **Implemented:**
  - **`cage_verdict` + `cage_compare`** ([mcpserver.py](../cage/mcpserver.py)) — the two
    views that answer *"is this tool worth keeping"* and were the only ones missing.
    Both render through the **CLI's own renderer over the CLI's own composer**, so
    `INSUFFICIENT DATA`, `SAVING (GROSS)` and the `MIN_COMPARE_N` block cross the
    boundary **byte-identically** — asserted as *equality with the CLI's stdout*, not as
    substring presence, because substring tests permit exactly the summarizing layer
    this rule forbids. `verdict` stays a pure composer; no new statistic was needed.
  - **`cage_task_outcome`** — the ladder's **only** write tool, pinned as such
    (`mcpserver.WRITE_TOOLS`, a test, and the module docstring where the next reader
    will look). It goes through the new **`clicmds.close_task`**, extracted so the CLI
    verb and the tool share one label guard, one append, one wording.
  - **Kiro's MCP config is committed** — the last portability exception, closed.
    `kirowire.PATH_FREE` (`python3 -m cage mcp`) carries no path at all, so the file is
    byte-identical across machines; `install` migrates a legacy absolute entry **and
    says it did**; `wiringscan`'s kiro spec is `required=True` again.
  - **New doctor check `kiro-mcp`** — path-free buys portability with a dependency on
    *which* `python3` resolves, so doctor resolves it and asks **that interpreter** to
    import cage. A venv miss is otherwise a silent no-MCP (the F1 class, one layer up).
    Windows is a **stated limit**, not a silent one: `python3` is often absent there,
    and the check names `cage setup --python-launcher` as the per-machine fix.
- **Files:** `cage/mcpserver.py` · `cage/clicmds.py` · `cage/kirowire.py` ·
  `cage/doctorcmd.py` · `cage/wiringscan.py` · `cage/explain_data.py` ·
  `tests/test_mcp_layer.py` (new, 20) · `tests/test_agents.py` · `tests/test_doctor.py` ·
  `README.md` · `CLAUDE.md` · `docs/example/setup.md`.
- **Tests:** green — `1059 passed, 10 skipped` (+20). Floor test still green: the new
  layer moved no number.
- **Correction to the spec:** CLAUDE.md and the prompt both cite
  `tests/test_portable_wiring.py` as the grep gate. **No such file has ever existed** —
  the assertions live in `tests/test_agents.py` and now `tests/test_mcp_layer.py`.
  CLAUDE.md now says so.
- **Next:** **P2 (L1 · hooks + steering, Opus)** — agent identity at capture and auto
  task-close, opt-in, on all three agents, proving hooks change no number.

## 2026-08-02 — AGENT-L0 **P0**: skill residue cleared, the floor proven (1024/0 ⇒ 1039/0)

- **Milestone:** phase P0 of the agent-surface program
  ([handoff](../work/archive/v0.41-agent-surface.handoff.md) · [prompt](../work/archive/v0.41-agent-surface.prompt.md)) — gate met,
  P1 unblocked.
- **Implemented:**
  - **`tests/test_floor.py` (new, 15 tests) — the floor proof, built *before* the layers
    it judges.** Per agent (`agents.SURFACES`, parametrized — a missing agent is a
    failure, never a narrower run): a project with **zero** wiring artifacts imports that
    agent's real CLI session log to the corpus's exact expected rows, and every derived
    view renders. Then the acceptance criterion for P1–P3: `agents.install` on the
    *same* already-captured project must leave the ledger shards **and seven views'
    stdout byte-identical**, and stripping the wiring again must too. Plus:
    `agents.install` is byte-identical on a second run (multi-user hygiene), no
    skill/prompt/steering asset ships, `setup --no-skill` exits 2, and no live doc
    claims a skill.
  - `_WIRING_ARTIFACTS` enumerates every project path any layer writes (L1 hook files,
    L2 MCP configs, L3 skill/prompt/steering, the shim). **A new layer is wired into the
    floor by adding a row — never by relaxing an assertion.**
  - **Residue removed.** README ×3 (the wizard line, `--no-skill` in the adopting note,
    *"the `cage` skill on **all four agents**"* — wrong twice: no skill ships, and there
    have been **three** agents since v0.33; all three were live on PyPI). `--no-skill`
    itself was already gone from the parser — verified, now regression-pinned.
  - **Stale live spec corrected on contact:** CLAUDE.md's wiring bullet claimed
    `claudewire` wires `hooks+MCP`, a kiro `agentStop` hook, `backfill_status`/
    `realtime_status`, `pointers.py` and `setupcmd.py` — **all five are gone**; it now
    describes MCP-only wiring plus the heal path, and records Kiro's hook shape as a
    forward note for L1. `docs/example/setup.md` (a copy-from contract) said setup writes
    "hooks + MCP config + skill/steering pointers, plus the local git commit hooks" —
    it writes **none** of those. `paths.bundled_data` docstring.
  - `claudewire._strip_stale_hooks` **kept** (migration, not residue — per the handoff).
- **Files:** `tests/test_floor.py` (new) · `README.md` · `CLAUDE.md` ·
  `docs/example/setup.md` · `cage/paths.py` (docstring) · `docs/OPEN-WORK.md` ·
  `docs/WORKLOG.md`. **No behaviour change** — no cage module's logic was touched.
- **Tests:** green — `1039 passed, 10 skipped` (was 1024/10; +15).
- **Next:** **P1 (L2 · MCP, Sonnet)** — `cage_verdict` + `cage_compare` with the
  refusals crossing verbatim, and `cage_task_outcome`, the ladder's only write tool;
  plus Kiro's MCP moving to the committed path-free `python3 -m cage mcp` form and the
  doctor check that the resolved interpreter can import cage.

## 2026-08-02 — PLAN.md de-staled; §8 anchors created (docs + 2 comments)

- **Milestone:** the design of record no longer describes removed features as current,
  and every `plan §X` cited from code resolves.
- **Implemented:**
  - `docs/PLAN.md` header — "Nothing built yet" replaced with an honest status; added
    reader's notes for the marked-never-renumbered rule, the v0.36 hookless rebuild, and
    the three-agent count.
  - **§5.1** (`tools/skillgen`) and **§3.8** (`cage data limits`) marked **REMOVED**,
    numbers retained for citation stability.
  - **§8.1–§8.8 anchors added** — five shipped modules cited them; the section had no
    subsections. Numbering flagged load-bearing.
  - Inline: 3 Codex enumerations, 2 "four agents" claims, 1 moot hook example.
  - `cage/policy.py` + `cage/transcript.py` — two bare `plan §2.1` comments qualified to
    the archived plans they actually mean.
- **Verified:** anchor sweep over every `plan §X` in `cage/*.py` ⇒ **no dangling
  references into PLAN.md**; both edited modules parse.
- **Files:** `docs/PLAN.md` · `cage/policy.py` · `cage/transcript.py` · `docs/WORKLOG.md`
- **Tests: NOT RUN** — sandbox is Python 3.10. Docs + comments only; run `just test`
  before commit.
- **Next step:** the agent-surface program from P0.

## 2026-08-02 — `cage insights adoption` (ADOPT) built and green

- **Milestone:** the README's third capability claim ("which tools your agents actually
  adopt") is now a command, not a regression doc. Derived view only — no capture change,
  no schema change, no new field.
- **Implemented:**
  - **`cage/adoption.py`** (new) — two halves that are never blended, because they have
    different precision. **A · invocations**: the usage breadcrumb, exact and
    **agent-blind** (a usage row has no `agent` field); per-outcome counts are **read**
    from the recorded `outcome`, never re-derived. **B · per-agent**: savings rows joined
    to `calls.agent` — by linked `call` id first (exact, stronger than the session), else
    by a `session` exactly one agent's calls carry. A session shared by two agents stays
    unknown rather than resolving to an arbitrary name.
  - **Agent-unknown is split by cause and never bucketed as "other"**: `no-link` is the
    interceptor's *structural* limit (a subprocess cannot know its caller, so it stamps
    an empty session on purpose); `unjoined` is a *capture gap*. Neither is ever
    attributed by timestamp proximity.
  - **Correction found during the build — "never invoked" needs two strengths.** *No
    evidence of invocation* is sound only when **every** savings row found an agent;
    otherwise an unattributed row could belong to the agent being named, so the claim
    drops to *no savings row attributed to them* (`NO_EVIDENCE` / `NOT_ATTRIBUTED`, and
    the distinction survives into CSV). The golden that exposed this (`I9b`) printed "no
    evidence of invocation: claude" beside two unattributable claude-era rows.
  - **Decision recorded: an empty half B renders its refusal, it is never suppressed** —
    suppressing it would make *cage cannot attribute these* read like *cage has no
    per-agent answer at all*, the exact conflation the view exists to prevent.
  - **Zero currency anywhere**, in all three output formats — the `state/`
    diagnostic-only invariant re-asserted from its first-ever reader.
  - Surface is deliberately **not** a dimension (K4: claude CLI/VS Code share one store).
  - CSV parity (`section`/`dimension` keep the halves apart when flattened; an
    inapplicable cell is empty, never `0`), MCP mirror (`cage_adoption`, text + csv),
    `cage query tool-adoption`, `--since`, `--json`.
- **Files:** `cage/adoption.py` (new) · `cage/cli.py` · `cage/clicmds.py` ·
  `cage/mcpserver.py` · `cage/explain.py` · `cage/explain_data.py` ·
  `tests/test_adoption.py` (new) · `tests/test_output_spec.py` · `tests/goldenseed.py` ·
  `tests/fixtures/goldens/I9{a,b,c,d}.txt` (new) · `tests/fixtures/cli-help.txt` ·
  `docs/FORMULAS.md` §2.12 · proposal + handoff/prompt archived to `work/archive/`.
- **Coverage on the real dev ledger (the honest number):** 6/6 savings rows are
  agent-attributable — but only **3 via the session join** (all graphify, all
  `claude-code`); the other 3 are legacy receipts carrying a `call` id, one of which
  is a `cage demo` seed row. Graphify alone: 3 of 4 rows by session, 4 of 4 with the
  call rung. Small-n; the shim-route blind spot is structural, not visible here.
- **Tests:** green — 1024 passed, 10 skipped (was 995; +25 adoption unit tests,
  +4 goldens). `just test`'s count and the README's need the new figure at release.
- **Version:** v0.39.0 was tagged and published *during* this session (another session's
  release commit), so ADOPT lands **after** it and rides **v0.40.0** — its CHANGELOG
  entry is written as `## v0.40.0 (unreleased)`, and `__version__` stays `0.39.0` until
  the release commit bumps it (this repo's standing pattern).
- **Next:** nothing blocking (the tree is uncommitted by instruction); `cage-lab` can now assert adoption output black-box.

## 2026-08-02 — shim-contract B8 diagnosis corrected + B8a added (docs-only)

- **Milestone:** the living spec no longer carries a disproved technical claim; the real
  Windows fact that cost five pushes is now written where future interceptors inherit it.
- **Implemented (documentation only):**
  - `docs/shim-contract.md` **B8** — the flat-`for` requirement no longer justifies
    itself with the `call`/`goto` stack-leak hypothesis (which did **not** fix the
    observed failure). Retained on its own merits, correction marked and dated, sourced
    from the v0.38.0 CHANGELOG written by the debugging session.
  - **B8a (new)** — no `<`/`>` inside a parenthesized block, *including in `rem`
    comments*: cmd.exe tokenizes redirection characters there because `rem` is a command
    whose line is still parsed. Binding on this twin and on every future interceptor.
  - Test-harness corollary — keep `%SystemRoot%\System32` on `PATH` for the shim's own
    `findstr.exe`/`where.exe`; prepend tmp dirs, never wipe, never inherit wholesale.
  - `docs/OPEN-WORK.md` — WIN-CI closed and removed; State corrected to released.
- **Why:** the CHANGELOG had been corrected but the contract had not, leaving history
  truthful and the spec wrong — the inverse of this repo's docs law.
- **Files:** `docs/shim-contract.md` · `docs/OPEN-WORK.md` · `docs/WORKLOG.md`
- **Tests:** none run — documentation only; no code touched. Suite last green at 995.
- **Next step:** ADOPT.

## 2026-08-02 — OTEL: `cage data export --otel` — GenAI-conformant JSON, pre-stable spec pinned

- **Milestone:** `cage data export --otel` ships, closing the OTEL item off
  OPEN-WORK.md's Pending table.
- **Implemented:** new module `cage/otelout.py` renders calls → `gen_ai.system` /
  `gen_ai.request.model` / `gen_ai.usage.input_tokens` / `output_tokens` /
  `gen_ai.client.operation.duration` (seconds, from `latency_ms`; omitted, never a
  fabricated zero, when latency was never captured). Wired `--otel` into `cage data
  export` (`cage/cli.py`, `cage/exportcmd.py`), mutually exclusive with
  `--csv`/`--format`/`--study` (typed `CageError`). **Decision — receipts/savings
  have no GenAI equivalent**: cage-namespaced under `cage.savings[].cage.*`, never an
  invented `gen_ai.*` name; `cage.saved` is GROSS, `cage.saved_usd` prices through
  the existing `receiptprice` resolution ladder (`price_at` → `task-model` →
  refusal) and is omitted — never `$0` — on an UNPRICED refusal or a non-money unit
  (`ms`/`gco2`); `cage.method` always survives. Legacy Tier-1 human-axis rows are
  excluded and counted in `cage.meta.legacy_human_excluded`, same predicate
  `report.py` uses. **Pinned the pre-stable semconv target**:
  `constants.OTEL_SEMCONV_VERSION = "1.42.0"` / `OTEL_SEMCONV_STATUS = "pre-stable"`,
  stamped in every document's `cage.meta` block and interpolated live into `cage
  query otel-export` (new registry entry, `explain.py`'s `_live()` gained
  `semconv`/`semconv_status`). `--agent`/`--project` filter the `calls` array only —
  receipts have neither field, and the pricing ladder is built from the *unfiltered*
  call set so a call-less receipt can still resolve its task-model rung.
- **Files:** `cage/otelout.py` (new), `cage/constants.py`, `cage/exportcmd.py`,
  `cage/cli.py`, `cage/clicmds.py`, `cage/explain.py`, `cage/explain_data.py`,
  `tests/test_otel_export.py` (new, 13 tests).
- **Tests:** green — 982 → 995 (13 new), full suite `python -m pytest -q`.
- **Docs:** proposal `otel-genai-export.md` and the handoff/prompt pair archived to
  `work/archive/v0.39-otel-{export.handoff,export.prompt,genai-export.proposal}.md`
  (implemented-for-v0.39, unreleased); `docs/proposals/README.md`,
  `work/archive/README.md`, `docs/README.md` (Active work emptied),
  `docs/OPEN-WORK.md`, `work/DOC-REGISTRY.md`, `CHANGELOG.md` (new `## Unreleased —
  OTel GenAI export (OTEL)` section), `README.md` + `CLAUDE.md` test counts, and a
  new `CLAUDE.md` **OTel GenAI export** architecture bullet all updated in this
  change.
- **Next:** nothing carried forward — no residual. `cage data export --otel`'s
  sample document and the receipts/savings decision are reproducible via `cage query
  otel-export` and `tests/test_otel_export.py`.

## 2026-08-02 — CMD-SYNC: `prices.toml` split applied to CLAUDE.md; `[sources]` authority declined

- **Milestone:** CMD-SYNC fully resolved — one CLAUDE.md docs proposal applied
  verbatim, one independently re-verified and declined. Zero code changes.
- **Implemented:** applied `claude-md-prices-file` — the one-way-data-flow diagram +
  caption now name `cage.toml` (order/budgets/routing) and `prices.toml` (model
  prices, `[credits]`) as the two config inputs; new **Prices file** architecture
  bullet (`Footprint.prices`); **Pricing is managed** Must-Know bullet states the
  two-file write split (`prices set`/`sync` → `prices.toml`; `alias`/`route-tool` →
  `cage.toml`); **State cleanup** NEVER list gained `prices.toml`; constants/
  numbers-layers phrasing updated. Governing sentence kept verbatim: *vendor facts
  move, routing decisions stay*. `grep -c prices.toml CLAUDE.md`: 0 → 10.
- **Declined (no code):** `claude-md-sources-authority` — independently re-verified
  against `cage/paths.py` `resolve_log_sources`'s docstring, which still reads *"an
  empty/absent `[sources]` returns exactly the built-in registry"*, matching what
  CLAUDE.md already said. The proposal asked CLAUDE.md to assert the opposite
  (`[sources]` as the sole authority, no runtime fallback) — a Directive A end-state
  that never shipped. Applying it would have replaced a true statement with a false
  one, so it was not applied.
- **Files:** `CLAUDE.md`; both proposals moved to
  `work/archive/v0.39-claude-md-{prices-file,sources-authority}.proposal.md`; the
  handoff+prompt pair moved to `work/archive/v0.39-claude-md-sync.{handoff,prompt}.md`;
  `docs/proposals/README.md`, `docs/README.md`, `docs/OPEN-WORK.md`,
  `work/archive/README.md`, `work/DOC-REGISTRY.md` updated.
- **Tests:** green — 995 passed / 0 failed / 10 skipped (unchanged by this docs-only
  change; `git diff --stat cage/` carries no edits from this session).
- **Next:** none — CMD-SYNC has no residual. Directive A (making `[sources]` the sole
  authority) stays unfiled unless it is explicitly wanted — it would be a code change.

## 2026-08-01 — DEBT: `paths.py` split-on-contact rule landed; Part 2 declined

- **Milestone:** DEBT fully resolved — one CLAUDE.md rule shipped, one feature request
  closed as unnecessary after its premise failed verification a third time.
- **Implemented:** Part 1 — added the **`paths.py` splits on contact, never wholesale**
  bullet to `CLAUDE.md`'s "Must-Know Rules" (beside the "renamed or removed verb" rule).
  Names the four seams (`routing.py`/`logsources.py`/`agenthomes.py`/`footprint.py`) and
  CODEX-OUT's earned clause — a deletion and a move never share a diff.
- **Declined (no code):** Part 2 (a one-line state header above `_ROOT_HELP` on bare
  `cage`) was never built. Verifying the prompt's own required first step (`run cage
  with no args`) showed bare `cage` dispatches to `clicmds.cmd_overview` (`cli.py:651`),
  not `_ROOT_HELP` — and `cmd_overview` already prints tokens · calls · unpriced ·
  last-import, with deliberate capture-on-read (`cli.py:114`). Both the original
  proposal ("prints argparse usage") and the handoff's "correction" ("prints
  `_ROOT_HELP`") were wrong; this is the **second** independent verification reaching
  the same conclusion (the first closed it in an earlier session same day — see
  `docs/WORKLOG.md`). Offered the human four rescope options; chose "leave Part 2 alone
  entirely."
- **Files:** `CLAUDE.md` · `docs/proposals/README.md` · `docs/README.md` ·
  `docs/OPEN-WORK.md` · `work/archive/v0.39-structural-debt.{proposal,handoff,prompt}.md`
  (new) · `docs/proposals/structural-debt.md`, `docs/structural-debt.{handoff,prompt}.md`
  (removed, superseded by the archive copies)
- **Tests:** not run — no code changed, docs/CLAUDE.md only.
- **Next:** WIN-CI (unaffected, unrelated track).

## 2026-08-01 — CODEX-OUT: the Codex agent's residue is gone; its model ids are not

- **Milestone:** `grep -riI codex cage/` returns **only** category 2 (the OpenAI model
  rows in `data/prices.toml` + `policy.normalize_model`'s effort fold). The agent is
  fully out; live Copilot pricing is provably untouched.
- **Implemented:**
  - **Deleted (the agent):** `paths.codex_home()` + its `CODEX_HOME` env read ·
    `wiringscan`'s `~/.codex/config.toml` MCP scan, its `.codex/hooks.json` entry in
    `committed_artifacts`, and the `.codex` tag in `_leftover_agent` ·
    `doctorcmd`'s `hooks_cmds(".codex/hooks.json")` · `"CODEX_HOME"` from
    `doctorbundle._CAGE_ENVS` · the `~/.codex/config.toml` mention in `explain_data`'s
    stale-wiring entry · `agents.py`'s removal paragraph.
  - **Kept, deliberately (the model family):** all 20 `gpt-5.x-codex` /
    `codex-mini-latest` rows in `data/prices.toml` (**byte-identical — verified by an
    empty `git diff` and an unchanged sha256**) and `policy.normalize_model`'s
    `…-codex-high` → `…-codex` fold. These are OpenAI ids **Copilot emits**; deleting
    them would silently UNPRICE a supported agent.
  - **New regression guard:** `test_pricing.test_codex_model_ids_are_not_the_codex_agent`
    prices a `agent="copilot"` call on every one of the seven codex ids and asserts the
    effort-suffix fold still resolves to the base row. The next blind
    `grep -i codex && delete` now fails loudly instead of costing money.
  - **Prose (drop the word, keep the sentence):** `schema.py` · `ledger.py` ·
    `report.py` (the `--project` caveat) · `proxy.py` · `runshim.py` · `paths.py`.
  - **`paths.py:106/122/126`** (the three judgement calls): all three are *docstring
    examples* of verb-tail parsing, not behaviour. 106/122 re-pointed at
    `--agent claude`; 126's `import-claude`/`import-codex` pair generalised to
    `import-<agent>`. `import-codex` is still caught as a dead verb by the live parser
    — the detector never enumerated agent names, so nothing was lost.
  - **Trade-off recorded, not buried:** a pre-v0.33 `~/.codex/config.toml` can no longer
    be scanned for a dead `cage` verb — the user-level F1 class. Named in the CHANGELOG
    `Removed` entry per Arpit's call.
  - **DEBT:** `paths.py` deliberately **not** split. The verdict — *a deletion and a
    move never share a diff* — was promoted by the concurrent DEBT session into
    `CLAUDE.md`'s `paths.py`-splits-on-contact rule, alongside the `agenthomes` seam;
    the motivating proposal is archived as
    `work/archive/v0.39-structural-debt.proposal.md`.
- **Files:** `cage/{paths,wiringscan,doctorcmd,doctorbundle,explain_data,agents,schema,
  ledger,report,proxy,runshim}.py` · `tests/{test_wiringscan,test_pricing,conftest,
  goldenseed,test_estimate,test_debuglog,test_capture_on_read,test_prices_cli,
  test_universal_capture,test_zipapp,test_substrate,test_debug_coverage,
  test_doctor_bundle}.py` · `CHANGELOG.md` · `README.md` · `CLAUDE.md` ·
  `docs/{OPEN-WORK,README,DOC-REGISTRY}.md` · `docs/proposals/structural-debt.md` ·
  `work/archive/v0.39-codex-purge.{handoff,prompt}.md` (+ archive README row).
- **Tests:** green — **982 passed, 10 skipped** (was 983/10: two codex cases deleted,
  one guard added). **No golden needed re-blessing** — the removed text appears in no
  golden fixture, and `tests/fixtures/goldens/P1.txt`'s seven codex *price* rows are
  category 2 and unchanged.
- **Next:** OTEL or DEBT (both parallel-safe); v0.39 is uncommitted and unreleased.

## 2026-08-01 — Dead doc-citation sweep + Codex legacy labelling ⚠️ UNVERIFIED

- **Milestone:** every dangling `docs/*.md` pointer in source is resolved; the Codex
  residue is documented as deliberate rather than looking like dead code.
- **Implemented (comments/docstrings only, no logic):**
  - 11 citations re-pointed across `cli`, `attribution`, `calibration`, `capturelog`,
    `importcmd`, `paths`, `compare`, `study`, `csvout`, `exportcmd`, `explain_data`.
    Dead targets were `cli-output-spec.md`, `csv-output.md` (×6),
    `debugging-capture.md` (×2), `sources.md`.
  - `paths.codex_home()` gained a docstring stating it is **legacy-only** and why the
    scan must survive (pre-v0.33 machines hold a stale cage command; deleting the scan
    is the user-level F1 class), plus the deletion condition.
  - `doctorcmd`'s `.codex/hooks.json` scan gained the same one-line note.
  - `CLAUDE.md`: new rule — **deleting a doc is a citation migration**, with the sweep
    command inline.
- **Deliberately not done:** removing Codex scanning (it is stale-artifact detection,
  not support) · changing `paths.py`'s pre-Directive-A `[sources]` wording (that is
  CMD-SYNC, awaiting accept — flagged inline so they land together).
- **Files:** 12 modules + `CLAUDE.md` · `docs/WORKLOG.md`
- **Tests: NOT RUN** — Cowork sandbox is Python 3.10, cage needs 3.11+. All 12 files
  verified to parse. **Run `just test` before commit.**
- **Next step:** `just test`, then WIN-CI.

## 2026-08-01 — v0.38.0: GF-DEBT — the six honesty debts WIN-GF/CI-GF left behind

- **Implemented, all six, same change as v0.38.0 (never shipped separately):**
  - **Restored `docs/restricted-environments.md`** (deleted in the v0.36 hookless sweep,
    `b2c4253`; 8 source files still cited it by path — `clicmds.py`, `doctorcmd.py` ×2,
    `paths.py`, `policy.py`, `runshim.py` ×2, `CLAUDE.md`). Restore-then-update, not
    rewrite: fixed the stale "Companion to portable-wiring.md" reference (that file was
    folded into `cage query portable-wiring` + PLAN §5.3 during the same sweep that
    deleted this doc), dropped the removed Codex MCP row from the launcher-mode table,
    and added a new **GF-LAUNCHER** subsection.
  - **GF-LAUNCHER stated where users are:** one clause in the README Platforms line;
    the restored doc's new subsection; `cage doctor`'s new `launcher-gap` check
    (`doctorcmd._launcher_gap`, fires only when python-launcher mode is on **and** an
    interceptor is installed — the exact combination where the gap bites silently).
  - **`cage query graphify-shims`** — a new concept entry in `explain_data.py`
    (inserted between `stale-wiring` and `wiring-inventory`), live-interpolated from
    three new `_live()` values (`graphify_shim_posix`/`_windows`/`_here`, sourced from
    `paths.GRAPHIFY_SHIMS`/`graphify_shim_name()`). Covers: why two twins · PATHEXT has
    no extensionless entry · `.EXE` precedes `.CMD` (directory-major/extension-minor
    resolution) · content-based identity · D1 (`call` not `exec`) · the GF-LAUNCHER gap.
  - **ADR 0007** (`docs/adr/0007-graphify-twin-pair-hand-paired-not-templated.md`) —
    records three decisions as load-bearing: both twins install on every OS,
    hand-paired not templated, contract lives in `docs/` not package data. Veto
    condition: templating reopens only on a **third** interceptor sharing a syntax
    family with an existing one; the written-contract-as-shared-artifact principle is
    invariant regardless of tool count.
  - **cage-lab states POSIX-only coverage:** `01-setup.md`'s PATH-proof
    (`command -v graphify`) now says explicitly it proves the POSIX twin only (a shell
    builtin can never invoke `.cmd`); `03-verify.md` gained a new §6 stating a green
    lab run is never Windows coverage — that lives in CI-GF alone.
  - **The corpus-sizing rule, written AND enforced:** documented in
    `tools/cigraphify.py`'s module docstring (the actual near-miss: the first
    `cicorpus` draft was ~1.2 KB and every query came back honestly `unmeasurable`).
    Not just written down — `check_bare_graphify_is_intercepted` already raised `Fail`
    on zero new savings rows or a non-positive saving, so a vacuous corpus cannot
    silently pass; **4 new unit tests** (`tests/test_cigraphify.py`, monkeypatching the
    shell-call and ledger-read seams, no real graphify needed) pin that as a
    regression, not an accident of the current corpus size.
- **Two fixes needed after building the above:**
  - `tests/test_doctor.py::test_every_check_has_a_known_level` — added `"launcher-gap"`
    to the expected check-name set.
  - `tests/test_cli_tiering.py::test_no_stale_old_verb_hints_in_source_or_assets` — the
    new `graphify-shims` explainer's prose literally contained "cage graphify" (the
    marker string it was describing), which the stale-verb grep gate correctly flagged
    since `graphify` is in `verbmap.REMOVED`. Reworded to describe the marker without
    spelling the two words adjacently, rather than weakening the gate.
- **Files:** `docs/restricted-environments.md` (restored) ·
  `docs/adr/0007-graphify-twin-pair-hand-paired-not-templated.md` (new) ·
  `tests/test_cigraphify.py` (new) · `cage/doctorcmd.py` (`_launcher_gap` + wiring) ·
  `cage/explain.py` (+3 `_live()` values) · `cage/explain_data.py` (`graphify-shims`
  entry) · `tools/cigraphify.py` (docstring) · `docs/shim-contract.md` (cross-links) ·
  `work/cage-lab/{01-setup,03-verify}.md` · `README.md` · `CLAUDE.md` ·
  `tests/{test_doctor,test_cli_tiering}.py` (fixes) · docs indexes/trackers.
- **Tests:** green. `just test` **983 pass / 0 fail / 10 skipped** (979 before — the 4
  new `test_cigraphify.py` cases). No goldens affected (nothing here touches a golden
  fixture's output surface — `cage query`/`cage doctor` are not golden-pinned).
- **Next:** GF-LAUNCHER stays open (documented, not fixed) — needs a decision to move
  both twins together, not a patch. Then ③ ADOPT.

## 2026-08-01 — v0.38.0: WIN-GF (the `graphify.cmd` twin) + CI-GF (the graphify CI axis)

- **Implemented — CI-GF first, as its harness:**
  - `tests/fixtures/cicorpus/` — a **new named corpus** (frozen-corpus rule: never
    mutate an existing one), 3 modules ≈ 13.7 KB. Sized deliberately: the first draft
    was ~1.2 KB and every query came back `unmeasurable` because the answer cost more
    than the files it cited, so the leg asserted nothing while passing.
  - `tools/cigraphify.py` — the `present` leg as one cross-platform runner (7 checks:
    setup installs both twins · graph builds · **bare `graphify query` is intercepted
    and files a savings row** · passthrough · doctor live · killed shim ⇒ `dead` ⇒
    healed · determinism). Every invocation goes through `shell=True` because Python's
    `CreateProcess` appends only `.exe` and would never find `graphify.cmd` — it would
    fail the Windows leg for a reason unrelated to cage.
  - `.github/workflows/python-package.yml` — new `graphify` job, 3 OS × py3.13
    (graphifyy declares `>=3.10,<3.14`), pinned install, `continue-on-error` + a loud
    `::warning::` skip. The `build` (absent) job is byte-identical.
- **Implemented — WIN-GF, five phases:**
  - `docs/shim-contract.md` — the behaviour contract. B1–B8 binding, D1–D7 divergences.
    Corrects two handoff claims (npm→PyPI; re-entry skips metering only).
  - `cage/data/shims/graphify.cmd` — the twin. CRLF, pinned via a new `.gitattributes`.
    Bounded PATH walk + `where` fallback + `findstr` content skip; no delayed expansion
    (it eats `!` from `%*`); `exit /b %ERRORLEVEL%` on its **own line** (the one-line
    `& exit /b` form the prompt suggested expands ERRORLEVEL at parse time and is wrong).
  - `paths.GRAPHIFY_SHIMS`/`graphify_shim_name()`/`graphify_shims()` — one enumeration
    the writer and every read surface share. `adoptcmd` installs both twins on every OS;
    `refresh_shim` now **completes** the pair (the POSIX→Windows upgrade path).
  - `pathshim._candidates` no longer offers the extensionless name on Windows (it can
    never run there; counting it was a false ✅). `wiringscan` scans both twins and names
    the offending file; `doctorcmd._interceptor` fails a root carrying only the twin this
    OS cannot resolve. `wiringscan._BATCH_COMMENT` strips `rem` lines — without it the
    twin's own prose reported a dead `cage command` verb.
- **Files:** `cage/data/shims/graphify.cmd` (new) · `.gitattributes` (new) ·
  `docs/shim-contract.md` (new) · `tools/cigraphify.py` (new) ·
  `tests/fixtures/cicorpus/` (new) · `tests/test_win_graphify_shim.py` (new) ·
  `cage/{paths,adoptcmd,pathshim,wiringscan,doctorcmd}.py` ·
  `.github/workflows/python-package.yml` · `README.md` · `CHANGELOG.md` ·
  `cage/__init__.py` (0.37.2 → 0.38.0) · `tests/fixtures/goldens/P1.txt` (re-blessed,
  version stamp only) · docs (archive pair + indexes + trackers).
- **Tests:** green. `just test` **979 pass / 0 fail / 10 skipped** (962 before; the 10
  skips are the Windows-only behaviour tier and run on CI). `python -m tools.dummyrepo`
  S1–S18 all PASS. `python -m tools.cigraphify` **7/7 on macOS** — real interception
  proven end to end: bare `graphify query` → shim → cage → one savings row, ~2,562
  tokens gross.
- **`cage/data/shims/graphify` is byte-identical** (`git diff` empty) — the POSIX path
  is unchanged by construction, not by assertion.
- **Next:** the Windows behaviour tier has never executed — it runs first on CI. Then
  ③ ADOPT.

## 2026-08-01 — v0.37.1: Windows dev-CI green (graphify subprocess + test fixes)

- **Implemented:**
  - `cage/graphifymeter.py` gains `_resolve_argv()`: on Windows, when the subprocess
    target has no native-executable extension (`.exe`/`.cmd`/`.bat`/`.com`), it peeks
    the file's `#!` shebang and prepends the interpreter before calling
    `subprocess.run` — `CreateProcess` never honors a shebang (POSIX-kernel-only
    behavior), which is why `cage data graphify` crashed with `WinError 193` against
    any non-native target (a real npm `graphify.cmd` install was unaffected; the six
    new v0.36.0 graphify-integration test files, which all use a shebang-script
    stand-in, were not). A `python`/`python3` shebang resolves to `sys.executable`
    rather than trusting a same-named PATH binary.
  - `cage/hookbypass.py` `_tokens()`: Windows non-posix `shlex.split` mode (kept so an
    unquoted native `C:\...` path retains its backslashes) leaves quote marks on a
    quoted token — added `_unquote()` to strip them after tokenizing, fixing
    `test_quoted_path_survives_tokenization`.
  - `tests/test_kiro_routing.py` (×2) + `tests/test_import_unified.py`: both asserted
    an absolute sink path where the printed line correctly uses `importcmd._tilde`'s
    tilde-relative form (explicitly "machine-portable in tests" per its own
    docstring) — only ever a no-op locally because POSIX CI sandboxes aren't under
    `$HOME`, unlike `%TEMP%` on Windows. Now compare against `_tilde(...)` directly.
  - `tests/test_kiro_routing.py`'s `test_cli_credits_import_is_scoped_and_stamped`:
    the test wrote a raw Windows path into a TOML string in its own setup — the same
    backslash-escape bug v0.37.0 fixed in `paths.sources_toml`. Fixed with
    `.as_posix()`.
  - `docs/OPEN-WORK.md` gains **WIN-GF**: cage's own graphify interceptor
    (`cage/data/shims/graphify`) is a bash script with no extension, so Windows'
    PATHEXT-based bare-name PATH lookup can never find it at all — independent of
    today's subprocess fix, which only helps once something has already located the
    shim by an exact path. Needs a Windows-native twin (feature-sized, not attempted
    here); filed with a `proposals/` doc as the next action.
  - `__version__` bumped to 0.37.1; `CHANGELOG.md` + README "What's new" updated;
    golden `P1.txt` re-blessed for the version string.
- **Files:** `cage/graphifymeter.py`, `cage/hookbypass.py`, `cage/__init__.py`,
  `tests/test_kiro_routing.py`, `tests/test_import_unified.py`,
  `tests/fixtures/goldens/P1.txt`, `docs/OPEN-WORK.md`, `CHANGELOG.md`, `README.md`.
- **Tests:** green locally (962/962; the Windows-specific branches are verified by
  code inspection + a safe `os.name`-shim simulation, since there is no local Windows
  environment — real confirmation is the `python-package.yml` `windows-latest` CI
  matrix on push).
- **Next:** confirm `python-package.yml` is green on all three OSes after push; if
  Windows still shows red, read the new failure closely — don't assume it's the same
  class of bug twice in a row.

## 2026-08-01 — v0.37.0: Windows `sources.toml` crash + dummyrepo resync

- **Implemented:**
  - `cage/paths.py` `sources_toml()` now normalizes every written `path`/`glob`/
    `path_globs` value to `/` before embedding it in a TOML basic string. A raw
    Windows `\` there is a TOML escape character — `\A`, `\U`… aren't valid
    escapes — so `cage setup` on Windows was writing an unparseable `cage.toml`;
    `metering.record_call`'s (unguarded) policy load then crashed the first
    metered call after setup, which is exactly what the v0.36.0 release-CI zipapp
    smoke chain caught on `windows-latest` (`pyz demo` exit 1) while macOS/Ubuntu
    and the full `just test` (962 tests) stayed green — this class of gap only
    shows on the exact-artifact, per-OS smoke chain.
  - `tools/dummyrepo/run.py` resynced to v0.36.0's actual behavior — 10 of 18
    scenarios (S1, S2, S3, S9, S11, S12, S13, S15, S16, S17) were silently stale
    against changes v0.36.0 shipped but never propagated into this out-of-tree
    suite: the `policy.toml` → `cage.toml` rename (6 literal paths), kiro's
    IDE-log rows now routing to the machine ledger (ADR 0006 — `assert_exact_rows`
    takes `env` and asserts kiro's rows against `$CAGE_HOME` separately),
    Directive A ("no `[sources]` ⇒ captures nothing" — S9's fleet-simulation
    machine now runs `cage setup` before its import-sweep test), the `[prices]`/
    `[meta] prices_version` file split (a stray backdate write landed in
    `cage.toml` instead of `prices.toml`), `[budgets]` going opt-in/commented-out
    (BUD-V — S16 now exercises `[quality] signal`, mirroring
    `tests/test_policysync.py`'s own re-point), the new `import_id` manifest FK
    (now always volatile in the row-equality check), and `imports.jsonl`'s
    documented, deliberate session-title PII widening (import-ledger plan §7 —
    `assert_pii_clean` now excludes that one file from the generic marker scan).
  - `__version__` bumped to 0.37.0; `CHANGELOG.md` + README "What's new" updated.
- **Files:** `cage/paths.py`, `cage/__init__.py`, `tools/dummyrepo/run.py`,
  `CHANGELOG.md`, `README.md`.
- **Tests:** green — `just test` (962 tests) and the full `python -m
  tools.dummyrepo` (18/18 scenarios) both pass locally.
- **Next:** watch the v0.37.0 release-CI pyz smoke chain on all three OSes to
  confirm the Windows fix holds on real Windows CI (only reproducible there —
  no local Windows environment to verify against directly).

## 2026-08-01 — SYNC-GUARD: name the sync tests' borrowed table, guard its removal

- **Implemented:**
  - `tests/test_policysync.py` gains one named constant, `_EXAMPLE_TABLE,
    _EXAMPLE_KEY = "quality", "signal"` (plus `_EXAMPLE_DEFAULT = "task_ok"`), with a
    comment pointing at `docs/proposals/policysync-synthetic-bundle.proposal.md` explaining why
    it exists: five sync-mechanics tests (keep-customized, marked/block-owned,
    update-stale-default, update-known-version-customized, confirm-bucket, orphan-
    warning) borrow whatever bundle-shipped scalar-keyed table happens to survive
    `_strip_to_v016` as their worked example — `[budgets]` before BUD-V, `[quality]
    signal` since SUITE. A bundle removal reddens all of them for a reason unrelated
    to whatever removed it.
  - All six borrowing tests re-pointed to build their TOML text edits and assertions
    from the constant instead of the literal strings `"quality"`/`"signal"`/
    `"task_ok"` — a future re-point is now a one-line edit to the constant.
  - New `test_borrowed_example_table_still_in_bundle` asserts
    `policy.bundled_raw()["quality"]["signal"] == "task_ok"`, failing with the exact
    message specified in the prompt (names the coupling, says re-point to another
    actively-shipped scalar key that survives `_strip_to_v016`, links the proposal).
  - Verified the guard in isolation: monkeypatched a **copy** of `policy.bundled_raw()`
    with `[quality]` popped (never touched the shipped `cage/data/cage.toml`) and
    reran `tests/test_policysync.py` — the guard fails with the intended message, and
    (as expected, matching the original SUITE incident) five of the six re-pointed
    tests fail alongside it for reasons that are no longer mysterious, since the guard
    names the cause. `test_already_in_sync_message_on_current_file` was not touched
    and still runs against the real bundle.
  - Nothing else in the test suite borrows a live bundle table the same way — the only
    other `policy.bundled_raw()[...]` reads are against `[meta]` (a permanent,
    never-removed table: `test_prices_cli.py`, `test_prices_split.py`,
    `test_explain.py`, `tests/goldenseed.py`, `test_freshness.py`).
  - Archived the solo prompt (no handoff pair — too small for one) to
    `work/archive/v0.36-sync-guard.prompt.md`; removed `SYNC-GUARD` from
    `docs/OPEN-WORK.md`; updated `docs/README.md`, `work/archive/README.md`,
    `work/DOC-REGISTRY.md`, root `README.md`, `CLAUDE.md` test count.
- **Files:** `tests/test_policysync.py`; `docs/OPEN-WORK.md`; `docs/README.md`;
  `work/archive/README.md`; `work/archive/v0.36-sync-guard.prompt.md` (new, moved
  from `docs/sync-fixture-guard.prompt.md`); `work/DOC-REGISTRY.md`; `docs/WORKLOG.md`;
  `README.md`; `CLAUDE.md`.
- **Tests:** green — 962/0 (`python -m pytest -q`, was 961/0).
- **Next:** none — the synthetic bundle fixture stays parked as a proposal behind a
  third-table-removal trigger.

---

## 2026-08-01 — Cleanup becomes advisory: 90d default, warn-only, never per-tool

- **Implemented:**
  - **Retention 30 → 90 days.** `constants.CLEANUP_DEFAULT_DAYS` and its comment
    (rewritten — it argued for 30, now argues for 90); bundled `data/cage.toml`
    `[cleanup] days` too, so a scaffolded project doesn't keep the old window.
    `policy.cleanup_days` (project `[cleanup] days`) still wins.
  - **The auto sweep (`cleanup.maybe_run`) warns; it never deletes.** One stderr line
    when something is eligible, silent at zero: `` cage: N state/ item(s) older than
    {days}d (~{KB} KB reclaimable) — `cage data cleanup` to review, `--apply` to
    prune. `` Throttled to the existing 24h stamp; fail-open (an exception is
    debug-logged under `cleanup.prune`, never raised).
  - **New switch `[cleanup] warn`** (`policy.cleanup_warn`, env `CAGE_CLEANUP_WARN`,
    default true, via the existing `_flag` precedence ladder) — silences just the
    reminder text.
  - **`[cleanup] enabled` semantics, decided:** `false` ⇒ the auto path does nothing
    at all (not even the reminder, not even the throttle stamp) — but a
    manually-typed `cage data cleanup` / `--apply` **always** runs, regardless of
    the switch. The safer reading named in the handoff: an explicit command is never
    silently ignored. `run_cli`'s payload key renamed `enabled` → `auto_reminder` to
    say so; dry-run/apply text reads `(auto-reminder on/off)` instead of
    `(enabled/DISABLED)`.
  - **Never a per-tool cleanup, made explicit.** A comment at `cleanup.NEVER` states
    tool savings are covered only because they sit under `ledger/`, and that a
    per-tool class must never be added; `test_cleanup_never_touches_the_savings_tree`
    (`tests/test_savings.py`) now runs at the maximally-aggressive `days=0`.
  - `scan()` now stamps a `bytes` estimate per candidate (stale row bytes for
    rewrite-class files, file size for delete-class files) so the reminder can name
    a reclaimable size without a second pass.
  - `explain_data.py`'s `cleanup` entry, `cage.toml`'s `[cleanup]` comment block,
    `docs/example/toml-config.md`, `GLOSSARY.md`, and `CLAUDE.md`'s cleanup paragraph
    all rewritten to the new shape. `cli.py`'s `--days` help text and epilog updated.
  - `policysync.DEFAULT_CHANGES[("cleanup","days")] = (("0.27.0", 30),)` added so
    `cage policy sync` offers the 30→90 refresh to an already-tracked project; bundle
    `[meta] policy_version` bumped 0.26.0 → 0.27.0.
- **Files:** `cage/constants.py`, `cage/policy.py`, `cage/cleanup.py`, `cage/cli.py`,
  `cage/data/cage.toml`, `cage/policysync.py`, `cage/explain.py`,
  `cage/explain_data.py`, `docs/example/toml-config.md`, `docs/GLOSSARY.md`,
  `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `tests/test_cleanup.py`,
  `tests/test_savings.py`, `tests/test_policysync.py`, goldens `P5`/`P6a`/`P6b`
  re-blessed (policy_version 0.26.0→0.27.0, in-sync count 8→9).
- **Tests:** green, **961 passed, 0 failed** (956 → 961: five new cleanup tests —
  silent-at-zero, warn-switch precedence, enabled=false disables the auto path
  entirely, apply/dry-run ignore `enabled`, the warn default/env-precedence unit
  test). No advisory text reaches stdout (asserted directly in
  `test_maybe_run_warns_but_never_deletes`); derived-views-byte-identical test
  (`test_derived_views_identical_before_and_after_cleanup`) still green unchanged.
- **Next:** none for this item — see `SYNC-GUARD` in [OPEN-WORK.md](OPEN-WORK.md)
  for the next pending item.

## 2026-08-01 — SUITE green: G-SAV fixed, BUD-V-TEST re-pointed (949/6 ⇒ 956/0)

- **Implemented:**
  - **G-SAV** — `savings.record()` was missing `ts` from its signature, so a caller's
    `ts=` fell into `**_ignore` and every savings row was stamped *now* regardless of
    when the work happened. Added `ts: str | None = None`, forwarded it to
    `schema.make_savings` (which already accepted it). `**_ignore` kept — three shim
    callers (`graphifytx` ×2, `graphifymeter`) rely on the fail-open push contract.
    `tests/test_savings.py::test_record_writes_into_the_per_source_month_shard` now
    proves a **past-month** `ts` lands in that month's shard, not merely today's.
  - **Kwarg-parity guard (asked, approved)** — new
    `test_record_explicitly_accepts_every_make_savings_keyword` asserts every keyword
    `schema.make_savings` accepts (other than `route_key`, which `record()` derives
    itself via `paths.routing_key`) is also explicit in `record()`'s own signature.
    Makes the next silent kwarg-drop through `**_ignore` a test failure, not a latent bug.
  - **BUD-V-TEST** — the five `test_policysync` mechanics tests (keep-customized,
    marked/block-owned, update-stale-default, update-known-version-customized,
    confirm-bucket) used `[budgets]` as their worked example; the bundle now ships
    `[budgets]` commented out (opt-in, verified correct by BUD-V). Hand-writing
    `[budgets]` back into the fixture doesn't work — the assertions compare against a
    **bundled** default, and with none present an active table buckets as
    `project_own` (exactly what BUD-V verified). Re-pointed all five at `[quality]
    signal` — an active, bundle-shipped, scalar-keyed table that survives
    `_strip_to_v016` and isn't already another test's subject. Each test still asserts
    the same mechanics as before, only the worked example (a float `[budgets]` key →
    a string `[quality]` key) and the literal values changed — see the diff in
    `tests/test_policysync.py` for the exact before/after per test.
  - **Decision on the underlying fragility** (per the handoff's three options):
    **re-pointed now** (this change) **and filed the synthetic-bundle-fixture
    follow-up** as `SYNC-FIXTURE` in `OPEN-WORK.md` — re-pointing alone leaves the
    same coupling (generic sync mechanics ⇒ whatever cage happens to ship) that will
    redden again on the next table removal; the synthetic fixture is real work
    (designing a fake bundle these tests own) so it's carried forward rather than
    done inline.
- **Files:** `cage/savings.py` (`record()` signature + forward); `tests/test_savings.py`
  (shard-test proof unchanged, new parity test); `tests/test_policysync.py` (5 tests
  re-pointed); `README.md` / `CLAUDE.md` (test count 955→956).
- **Tests:** **956 passed, 0 failed** — full suite green.
- **Next:** `SYNC-FIXTURE` (synthetic bundle fixture for `test_policysync`), then
  NET-1 / H (release, blocked on the no-commit directive).

---

## 2026-08-01 — K+NET: gross vs net savings (K · NET-2 · NET-3)

- **Implemented:**
  - **K — `saved` is relabelled GROSS everywhere it surfaces**, text *and* CSV, from ONE
    phrasing (`netsaved.GROSS_NOTE`) so the views cannot drift apart. `report`:
    `saved tok`→`gross tok`, `saved`→`gross`, `net`→`net vs spend` (CSV
    `gross_saved_usd` / `net_vs_spend_usd`). `attrib`: `gross tok` / `gross $` (CSV
    `gross_saved_tokens` / `gross_saved_usd`). `roi`: `gross saved` / `net of own cost`
    (CSV `gross_saved_usd` / `net_of_own_cost_usd`). Overview headline: `gross saved`.
    graphify's repo ceiling + history band say GROSS on their own line. **No maths moved.**
  - **NET-2 — `verdict` stops over-claiming.** A positive/zero roi net with no complete
    cost-of-use figure now reads `SAVING (GROSS)` / `BREAK-EVEN (GROSS)` with a ⚠ naming
    the exclusion and pointing at `cage insights compare`. **COSTING is still asserted**
    bare — the omitted term is ≥ 0, so a negative net can only get more negative. That
    asymmetry *is* the rule; it is not a blanket refusal. `verdict` stays a pure composer.
  - **NET-3 — `cage/netsaved.py`** (new): task-level `net = gross − cost of use`, composed
    into `verdict` as its own input line beside gross, `modeled` at
    `NET_SAVED_CONFIDENCE = 0.4` (below gross's own — it stacks a join on a counterfactual).
  - **The attributable-cost rule chosen:** the **±120s task-window union**
    (`NET_ATTRIB_WINDOW_S`) — the distinct calls joined to the receipt's task whose `ts`
    is within the window of *any* of that tool's receipts on it, counted once. Symmetric
    (invoking turn precedes the receipt, consuming turn follows). Rejected: *whole task*
    (measures task size), *turns with a tool-use block* (no ledger field marks one —
    needs a capture-time change). A task with no in-window call is UNCOVERED and its net
    reads **unavailable**; `net == gross` is structurally impossible.
- **Files:** new `cage/netsaved.py`, `tests/test_netsaved.py`; `cage/constants.py`
  (2 constants), `cage/verdict.py`, `cage/roi.py`, `cage/report.py`,
  `cage/attribution.py`, `cage/graphifymodel.py`, `cage/explain.py`,
  `cage/explain_data.py` (new `gross-vs-net` entry); `docs/formulas.md` (§2.1 rewritten,
  §2.1a new, §2.5/§2.6/§2.10 amended); goldens R1/R2/R6/I2/I3/O2 re-blessed; tests
  test_csv / test_verdict / test_explain / test_report_savings / test_report_cache_split /
  test_graphify_forward / test_output_spec updated.
- **Tests:** **947 passed, 8 failed** — none from this work. All 8 pre-existing and
  verified so against a stripped-out copy of this change: 7 = **BUD-V** (the budget
  opt-in bundle change: `test_policysync` ×5 + goldens P5/P6), 1 = **G-SAV**.
  P5/P6 were deliberately **not** re-blessed — blessing them would launder BUD-V's defect.
- **Next:** BUD-V (decide bundle-vs-tests), then NET-1 — the repeats=3 paired lab run
  that would settle whether graphify actually made leg D's sessions more expensive.

---

## 2026-08-01 — K2 finished: routed leg, CLI scoping, read-side, and the tests (supersedes the entry below)

- **Milestone:** K2 executed end-to-end from
  [the archived prompt](../work/archive/v0.36-kiro-routing.prompt.md). **Supersedes the
  "⚠️ Tests: NOT PINNED / K-TEST" line in the entry below** — `tests/test_kiro_routing.py`
  (27 tests) now pins the routing, the CLI scoping and both caveat texts.

### The per-root map that was actually executed

`run()` builds ten things per root; the leg rebuilds each against the sink, and three are
deliberately *not* rebuilt:

| per-root object | routed kiro leg |
|---|---|
| `seen` (`ledger.calls`) | own, from the sink — else kiro dedupes against the wrong ledger and re-appends every run |
| cursors (`_load/_save`) | own, in the sink — the high-water skip must be relative to the sink |
| `_import_lock` | own, on the sink; **taken and released before** the sweep's own |
| `seen`-sharing / `collected` | own list — never merged into the sweep's rollup |
| `import_id` + `_write_manifest` | own — one id spanning two ledgers would claim the two row sets were one |
| `_record_health` / `_record_capture_log` | own, against the sink |
| `_last_import` | **not written** — a kiro-only leg is not a full sweep; writing it would lie to doctor *and* throttle a later global capture-on-read out of sweeping claude/copilot |
| `cleanup.maybe_run` | **not run** — the sink gets cleanup when it is the active sink |
| the sweep root's stale `kiro` cursor + `_health["kiro"]` | **dropped** (`_drop_routed_kiro_state`) — a stale health record re-fires "installed but capturing nothing" forever, for an agent that is capturing fine, elsewhere |

- **Deadlock:** impossible by construction, not by lock ordering. The leg's lock is
  released before the sweep's is taken, so no process ever holds two — the hold-and-wait
  edge a deadlock requires never exists. The same-process double-lock (two fds, one file)
  is excluded upstream: when the ledger dirs coincide `paths.kiro_routed` returns `None`
  and there is no second leg.

### The two decisions the prompt left open

1. **Whose capture switch governs the global leg? → BOTH (AND).** The project's gates the
   sweep (unchanged, the early return); the sink's policy additionally gates the leg. Most
   restrictive wins — the only composition that violates neither stated intent: "pause
   metering for this work" and "don't write to my machine ledger" are different sentences
   and neither may override the other. Visible in `--debug` as
   `event=import agent=kiro route=sink capture_here=… capture_at_sink=…`, and never
   silent — a vetoed leg prints a line.
2. **What the summary reports across two ledgers.** The kiro line **names its sink**
   (`✔ kiro: imported N call(s) from M file(s) → <machine ledger> (…)`), and the rollup
   table is built only from rows that landed in *this* ledger, so a total can never
   include a row that went elsewhere. Same on the read side: `ensure_captured` diffs the
   local ledger only, so `· captured N new` stays honest.

### `conversations_v2.key`, verified against the real store (not assumed)

17 conversations in `~/Library/Application Support/kiro-cli/data.sqlite3`. The key is the
**absolute, symlink-resolved cwd, no trailing separator** — a conversation started under
`/tmp/x` is stored as `/private/tmp/x`. That is exactly the near-miss the prompt warned
about, so `_norm_cwd_key` resolves symlinks, drops the trailing separator and applies
`os.path.normcase` (a real fold on Windows, a no-op on POSIX). Measured read-only against
the live store: unscoped 17 · scoped to the `cage-lab` tree 14 (subdir conversations
included) · scoped to `cage` **0** (a prefix match on a separator boundary, so `cage` never
swallows `cage-lab`) · scoped via a `/tmp` symlink 3 (would have been 0 without the
resolve). No path reaches any row — only the cwd **basename**, as `project`.

### Read side (K2's honesty half, done with K3/K4's wording)

`report.kiro_routed_line` (footer, computed at the CLI boundary so `render_report` stays
pure) · `doctor`'s capture timeline names kiro's sink instead of showing an empty row ·
`cage doctor --paths` reads kiro's cursor **from the sink** (it would otherwise report
"not yet imported" forever for a file cage imports every run) and names where IDE rows
land · `cage query kiro-routing`.

- **Bug caught by writing the test:** `_surface_caveat` (K4) checked `"claude" in agents`,
  but a claude row's `agent` field is `claude-code` — the caveat would have silently never
  fired on a real ledger. Now normalized through `agents.row_surface`.
- **Files:** `cage/paths.py` · `cage/importcmd.py` · `cage/transcript.py` ·
  `cage/schema.py` (`make_credit` gains additive-optional `project`) · `cage/report.py` ·
  `cage/clicmds.py` · `cage/doctorcmd.py` · `cage/pathprobe.py` · `cage/explain.py` ·
  `cage/explain_data.py` · `tests/test_kiro_routing.py` (new) + 8 updated test files ·
  goldens R1/R2/R4 re-blessed (the K3 caveat line).
- **Tests: green for this work — 937 passed.** 8 red, none from this change: 7 are the
  concurrent budget-opt-in bundle change (5 × `test_policysync` + goldens P5/P6, tracked
  as `BUD-V`), 1 is the pre-existing `G-SAV` savings-shard failure.
- **Next:** `BUD-V`, then `K+NET`.

## 2026-08-01 — K2 + K3 + K4 built (kiro routing, and the two HONEST-LIMIT lines)

- **Milestone:** closes OPEN-WORK **K2** and **K3/K4**. Found in the working tree during
  a Cowork reconciliation — built by the executing session, not yet logged here.
- **K2 — kiro capture routing** (per [ADR 0006](../docs/adr/0006-kiro-rows-are-machine-facts-not-project-facts.md)):
  - `paths.kiro_routed(root)` — returns the kiro-IDE sink only when it **differs** from
    `root`'s ledger, else `None`. The single predicate the sweep branches on. Compared on
    the resolved **ledger dir**, not the root, which collapses both `CAGE_BASE` and
    `CAGE_LEDGER` overrides for free — under either, the two sinks are the same files, so
    there is nothing to route, no second lock, and a same-process double-lock is
    impossible **by construction**. That is a better answer than the handoff's
    "fixed lock order" suggestion.
  - `importcmd._kiro_leg` + the `kiro_sink` branch — the contained nested leg; per-root
    state is suppressed where it would otherwise lie.
  - CLI credits: `_ingest_credits` now passes `parse_kiro_cli_credits(f, workspace=…)`,
    the opposite fix, as specced.
- **K3 — `report._kiro_limits_caveat`**: fires on any kiro row. States that `ts` is
  import-stamped, `session` is the constant `"kiro"` and `project` is absent. Calls the
  **`--since` case out by name** — a time window includes/excludes kiro rows by when the
  *import* ran, which is the reading that is wrong rather than merely coarse.
- **K4 — `report._surface_caveat`**: fires only on the surface view, and only when a
  blank-surface claude row is actually on screen (the misreading needs the blank cell
  visible). Says blank = "the source does not say", never `"cli"`.
- **Explainer:** a `kiro-routing` concept entry in `explain_data.py` covering both stores,
  both fixes, the override precedence and the limits.
- **Files:** `cage/paths.py` · `cage/importcmd.py` · `cage/report.py` ·
  `cage/explain_data.py` · `cage/transcript.py`
- **⚠️ Tests: NOT PINNED — carried forward as `K-TEST`.** *(Resolved 2026-08-01 by the
  entry above: `tests/test_kiro_routing.py` pins all of it. Left here as written — the log
  records what was true at the milestone.)* `tests/test_fixture_corpus.py`
  and `tests/test_debuglog.py` *call* `paths.kiro_routed` to stay routing-aware, but
  **no test asserts the routing behaviour** (kiro lands globally from inside a project ·
  `--ledger` still wins · the turn appears once across two project ledgers) and **no test
  or golden pins either caveat's text**. For an honesty feature that is the wrong way
  round: the lines can regress silently, and their whole purpose is to prevent a silent
  wrong reading.
- **Suite:** not run here (Cowork sandbox is Python 3.10; cage needs 3.11+).
- **Next step:** `K-TEST`, then `K+NET`.

## 2026-08-01 — Budget ceilings become opt-in (bundle only) — VERIFIED (BUD-V closed)

- **Milestone:** `[budgets]` no longer ships enabled. Absent keys ⇒ no ceiling.
- **Implemented:** `cage/data/cage.toml` — the `[budgets]` table commented out with its
  semantics documented, following the `[ledger] warn_mb` precedent. **No constant
  fallback** by design.
- **No code change needed** — `policy.budgets` already returns `None` for missing keys,
  `budget.check`'s `over = bool(cap and …)` can't trip on `None`, `proceed` stays True,
  and `render_budget` renders `—`. Verified by reading and by exercising
  `render_budget` with null caps.
- **Verification run (`just test` on the dev machine, `.venv`, Python 3.14):**
  - Full suite: **949 passed, 6 failed** (up from 937/8 before re-blessing P5/P6 —
    reblessing those two goldens turned 2 of the 8 red tests green).
  - **6 remaining failures, all pre-existing / test-design, none a code defect:**
    5 × `tests/test_policysync.py` (`test_hand_edited_value_is_kept_customized_never_clobbered`,
    `test_marked_and_block_owned_tables_stay_customized`,
    `test_update_category_refreshes_stale_old_default`,
    `test_update_known_version_differing_from_old_default_is_customized`,
    `test_confirm_bucket_pre_version_needs_yes`) — these use `[budgets]` purely as a
    convenient multi-key example table to exercise generic `policy sync` mechanics
    (add/update/confirm/customized categories), text-replacing values like
    `"session_usd = 2.0"` that only existed when the bundle shipped the table active.
    They now pin the **old** always-on-budgets shape, not budget semantics — the
    decision this milestone makes obsolete. **Recommendation: rewrite them against a
    different actively-shipped multi-key table** (e.g. `[cleanup]` or `[capture]`), or
    hand-write an active `[budgets]` block into the `v016` fixture's project file so the
    generic-mechanics assertions no longer depend on the bundle's default. Not fixed
    here — a test-design call, not an obviously-correct one-liner (out of this
    verification's scope; the bundle change itself needed no code fix).
    1 × `tests/test_savings.py::test_record_writes_into_the_per_source_month_shard` —
    unrelated pre-existing bug (`G-SAV`, tracked separately): `savings.record()`'s
    signature has no `ts` parameter, so a caller-supplied `ts` is silently absorbed by
    its `**_ignore` catch-all and never reaches `schema.make_savings`, which then stamps
    the current wall-clock time instead — the row lands in this month's shard, not the
    caller-requested one. Nothing to do with budgets; not touched here.
  - **`cage policy sync` does NOT try to re-add `[budgets]`** — the escalation
    condition in the verify prompt. An active project `[budgets]` table (existing
    projects, or one freshly opted into) simply has no bundled counterpart to diff
    against, so `_walk`/`sync_view` bucket its keys as `project_own` ("your own keys —
    not in the bundle — untouched"), never `add`/`orphan`. Confirmed live:
    `cage policy sync --apply` on a project with an active, customized `[budgets]`
    left the file **byte-identical**.
  - `explain_data.py`'s `budget` entry, `freshness.py` and `cage doctor` all checked —
    none reference `[budgets]` keys live (the formula string is static prose, not
    interpolated), so none regress when the table is absent.
  - Live-exercised in a scaffolded `/tmp` project (`cage setup --claude`):
    `cage prices list` header carries no budget noise; `cage insights budget` with no
    caps renders `—`/`—` on both axes, no ⚠, exit 0; `budget.check(..., add_usd=1e12)`
    → `over=False, proceed=True`; uncommenting `[budgets]` with `session_usd = 0.01`,
    `on_exceed = "block"` → `cage insights budget` shows the cap and `⚠ OVER`, and
    `budget.check` → `over=True, proceed=False`.
  - Goldens **P5** (`policy diff`) and **P6a/P6b** (`policy sync`) re-blessed — the only
    change in all three is `"11 project keys equal to the bundle — in sync"` →
    `"8"` (budgets' 3 keys no longer exist on either side of the diff to count as
    in-sync). No other line moved.
- **Files:** `cage/data/cage.toml` (already committed-pending, no further code change);
  `tests/fixtures/goldens/{P5,P6a,P6b}.txt` re-blessed.
- **Recommendation: keep as-is.** The bundle change is correct and complete; the 5 red
  `test_policysync` tests are a test-design debt (recommendation above), not a defect
  in the shipped behavior.
- **Next step:** rewrite the 5 `test_policysync` tests off `[budgets]` as their example
  table (or stop treating it as budget-specific in `IMPLEMENTATION.md`'s BUD-V tracking
  and file it as ordinary test-debt), then proceed to whatever OPEN-WORK item follows.

## 2026-08-01 — Tier-1 human axis REMOVED (substrate included) — breaking, ships v0.36

- **Implemented:** the whole agent-vs-human cost axis is gone, deliberately and
  completely (Arpit's decision 2026-08-01; a clean amputation, reconsidered from
  scratch after the release — OPEN-WORK **HR1**).
  - Deleted: `human.py` · `humanview.py` · `trend.py` · `attention.py` +
    `test_human*.py` · `test_attention.py`.
  - CLI: `cage human show|record` and `cage insights trend` removed; `--human`
    (matrix, calibration) and `--agent-only` (compare, verdict, study report) removed.
  - **Scope correction the handoff missed:** `cage human outcome` and `cage human
    quality` are NOT the human axis — `outcome` is the *task-close* verb the whole
    cost-impact surface (`compare`/`estimate`/`calibration`, `taskgroup.closed_tasks`)
    depends on, and `quality` is §8.2. Deleting them as the handoff specified would
    have amputated §4.7–§4.8. They **moved** to a new `task` group
    (`cage task outcome` / `cage task quality`); `outcome` lost only `--minutes`.
  - Substrate: `gap_ms` out of `CALL_FIELDS`/`CREDIT_FIELDS`/`make_call`/`make_credit`
    and out of `transcript.parse_calls`; `"minutes"` out of `schema.UNITS`;
    `IDLE_CAP_MINUTES` out of `constants.py`; `[human.*]` out of `data/cage.toml`;
    `policy.human_rates`/`human_rate_source`, `metering.record_human`,
    `cage.record_human` and `CAGE_HUMAN_RATE` all removed.
  - **Legacy-row decision (was left open for the executor): excluded from money views
    with a visible, counted footnote** — not priced at `$0` silently. `convert` values
    a `minutes` receipt at `$0`, `report._is_legacy_human` is the ONE shared predicate
    (`tool == "human" or unit == "minutes"` — the second half matters: `record_receipt`
    took an arbitrary unit, so a third-party tool could have written minutes under its
    own name), and `cage report` prints `· N legacy human-axis receipt(s) excluded …`.
  - Wiring migration: `verbmap.REMOVED` gains `human`/`human-record`/`trend` (removed)
    and `outcome`/`quality` (moved), plus a new `_BODIES` map for removals that need a
    sentence rather than an "is now" tail. `tests/test_cli_tiering.py`'s `_GROUPED`
    allowlist dropped `human` — which immediately exposed five stale `cage human …`
    strings the looser pattern had been hiding.
  - New explainer concept `savings-axis` (replaces `human-axis`) documents the removal,
    the legacy-row contract, and the two-different-"human"s distinction.
- **Files:** `cage/{cli,clicmds,schema,transcript,convert,constants,policy,metering,
  report,roi,attribution,freshness,importcmd,matrix,compare,verdict,study,calibration,
  serve,quality,taskgroup,estimate,doctorcmd,doctorbundle,explain,explain_data,verbmap,
  wiringscan,__init__}.py` · `cage/data/cage.toml` · `tools/dummyrepo/run.py` (S10
  removed) · `tests/` (new `test_legacy_ledger.py`; `test_csv`/`test_constants`/
  `test_explain`/`test_features`/`test_compare`/`test_policysync`/`test_cli_tiering`/
  `test_output_spec`/`test_graphify_forward`/`test_report_savings` updated) ·
  10 goldens + `cli-help.txt` re-blessed · claude/cli fixture `gap_ms` stripped ·
  docs: CLAUDE · README · CHANGELOG · PLAN §3.1/§4.6/§4.10/§7 · formulas §3 ·
  GLOSSARY · architecture-flow · example/{cli,debug,toml-config,README}.
- **Tests: green — 915 passed, 1 failed.** The failure
  (`test_savings.py::test_record_writes_into_the_per_source_month_shard`) is
  **pre-existing and unrelated** — it failed identically on the baseline run before any
  edit; filed as OPEN-WORK **G-SAV**. New `tests/test_legacy_ledger.py` (30 cases) pins
  the old-ledger contract and was **mutation-verified**: weakening
  `_is_legacy_human` to the tool-only test makes it fail.
- **Next:** OPEN-WORK **K** — relabel `saved` as gross.

---

## 2026-08-01 — `[meta] cage_version` derives from the package version, never a stale literal

- **Milestone:** closes the OPEN-WORK **meta** item — `data/cage.toml [meta]
  cage_version` was a hand-maintained literal (`"0.25.0"`) eleven releases behind the
  package (`0.36.0`), printed by `cage prices list` and copied into every newly
  scaffolded project. It now derives live from `cage.__version__`; a scaffolded
  project's own copy stays a historical stamp (set once, at creation, never rewritten).
- **Implemented:**
  - `cage/data/cage.toml` — the `cage_version` literal removed from `[meta]`
    (`policy_version` untouched — it's a content counter, deliberately not coupled to
    the release, per the standing pushback in WORKLOG 2026-08-01).
  - `cage/policy.py` `_bundled()` — derives `meta["cage_version"]` from
    `cage.__version__` at the end of assembly (lazy import, avoids any package
    import-order coupling), so every `bundled_raw()`/`load()` caller sees the live
    version. `pricescmd.render_list` (the `prices — bundled … (cage …)` header) and
    `pricescmd._stamp_meta_on_create` needed no code change — both already read
    through `bundled_raw()`.
  - `cage/initcmd.py` — new `_stamp_cage_version()`, called right after a fresh
    `cage.toml` is scaffolded (`default_toml()` copies the bundled file verbatim, which
    no longer carries the key). Stamps via `pricestoml.set_table(..., mark_custom=False)`
    — deliberately unmarked: this is a version fact, not a user edit, and marking
    `[meta]` `# cage:custom` broke `test_policysync.py`'s `_strip_to_v016` fixture
    (an exact-string header match) the first time through.
  - `cage/pricestoml.py` `_inplace_table_edit` — fixed a latent insertion-point bug
    surfaced by the stamp: a brand-new key was inserted right before the table span's
    *next header*, not after its own last key — harmless for tables with no trailing
    prose, but `[meta]` in the bundle is followed by ~20 lines introducing `[capture]`,
    so the stamped `cage_version` line landed valid-but-buried in the middle of that
    unrelated comment block (confirmed via a manual `cage setup` smoke test, not
    caught by any existing test — none pin exact insertion position). Now inserts
    right after the table's own last recognized `key = value` line. Full suite
    re-run clean after the change (no other caller hits this combination today).
  - Tests: `tests/test_prices_split.py` — two new tests, the drift-impossible guard
    (`bundled_raw()["meta"]["cage_version"] == __version__`) and the fresh-scaffold
    stamp check. `tests/test_zipapp.py::test_init_writes_the_bundled_policy_from_the_zip`
    updated — its "written == bundle verbatim" assumption is now "written == bundle
    plus exactly one stamped `cage_version` line" (a real behavior change, not a
    weakened assertion). Re-blessed `tests/fixtures/goldens/P1.txt` (`cage 0.25.0` →
    `cage 0.36.0`).
  - Docs: `CLAUDE.md` gained the derive-rule (Must-Know Rules) plus a release-checklist
    line; `docs/meta-version.prompt.md` archived to
    `work/archive/v0.36-meta-version.prompt.md`; `docs/OPEN-WORK.md`, `docs/README.md`,
    `work/DOC-REGISTRY.md`, `work/archive/README.md` updated to match
    (remove-on-done). `docs/example/toml-config.md` already showed `0.36.0` — no
    change needed, it was asserting the invariant the shipped file violated.
- **Files:** `cage/data/cage.toml` · `cage/policy.py` · `cage/initcmd.py` ·
  `CLAUDE.md` · `tests/test_prices_split.py` · `tests/test_zipapp.py` ·
  `tests/fixtures/goldens/P1.txt` · `docs/OPEN-WORK.md` · `docs/README.md` ·
  `work/DOC-REGISTRY.md` · `work/archive/README.md` ·
  `work/archive/v0.36-meta-version.prompt.md` (new)
- **Tests:** green — 942 passed (three new tests: the drift guard, the fresh-scaffold
  stamp check, and the insertion-point regression test for `pricestoml`). Two
  unrelated pre-existing failures left untouched
  (out of scope, confirmed unrelated by running each in isolation before this change
  too): `test_output_spec.py::test_I2_verdict_saving` (golden drift, date-relative
  regression-window seed) and `test_savings.py::test_record_writes_into_the_per_source_month_shard`
  (savings-shard partitioning, no `[meta]`/policy involvement).
- **Next step:** **K — relabel `saved` as gross** (proposal B) — the next item atop
  OPEN-WORK's phase index.

## 2026-08-01 — Three decisions specced: human removal, kiro routing, NET (docs-only)

- **Milestone:** the v0.36 queue reshaped by three of Arpit's calls; nothing built yet,
  but the two expensive ones are now execution-ready.
- **Decided + documented:**
  - **HUMAN** — remove the Tier-1 human axis **including substrate** (`gap_ms`,
    `"minutes"` in `UNITS`), shipping in **0.36 as breaking**. Specced as
    `docs/human-removal.{handoff,prompt}.md` (**Opus** — deletion with entanglements).
    The handoff leads with the trap: cage has **two** unrelated "human"s, and
    provenance `origin="human"` (authorship) must survive untouched.
  - **K2** — upgraded from "document or warn" to a **fix**, on Arpit's push that kiro
    is paid so a wrong number is a real problem. Investigation found it worse than
    double-summing: kiro's log has no project/session/ts, so importing into a *new*
    project pulls its whole global history — per-project kiro cost has never been
    correct. Decision recorded as
    [ADR 0006](../docs/adr/0006-kiro-rows-are-machine-facts-not-project-facts.md): kiro rows go
    to the **global ledger only**, explicit `--ledger`/`CAGE_BASE` still winning.
    Also established that kiro ids are stable across ledgers, so every id-merging path
    was already safe.
  - **NET** — filed as its own item: the real "is graphify actually saving money"
    question that K only mislabels.
- **Sequencing:** HUMAN first — `compare`/`verdict`/`matrix` carry human total-cost
  lines that NET and K would otherwise edit twice.
- **Files:** `docs/human-removal.handoff.md` (new) · `docs/human-removal.prompt.md`
  (new) · `docs/adr/0006-*.md` (new) · `docs/OPEN-WORK.md` · `docs/README.md` ·
  `work/DOC-REGISTRY.md` · `docs/WORKLOG.md`
- **Tests:** none — documentation only. Suite last green at 833.
- **Next step:** run `human-removal.prompt.md` (Opus).

## 2026-08-01 — OPEN-WORK re-cut to the size budget (docs-only)

- **Milestone:** the pending-work plan now fits one screen — the first real application
  of the doc-size trial, which also produced its first amendment.
- **Implemented (documentation, no code):**
  - `docs/OPEN-WORK.md` — **205 → 40 lines** (budget: ~40). Structure: 3-line lead
    (next · blocked · state) · 5-row pending table · open decisions · constraints
    binding the next lab run · 5-line maintenance pointer. Detail moved to the finding
    docs it already had; durable rules dropped to a link after verifying all seven are
    homed in `CLAUDE.md` or `work/cage-lab/`.
  - `docs/doc-size-discipline.md` — **rule 4 amended**: the ≤120-char row limit
    measures **rendered** text, not raw. Raw counting penalized markdown link targets
    (~60 chars, zero reading burden), putting rule 4 in direct conflict with rule 3.
    Amendment tagged and dated, with a runnable check.
- **Files:** `docs/OPEN-WORK.md` · `docs/doc-size-discipline.md` · `docs/WORKLOG.md`
- **Tests:** none run — documentation only. Suite last green at 833. Budget verified
  by the check in `doc-size-discipline.md` §4: 40 lines, 0 rows over.
- **Next step:** **K — relabel `saved` as gross** (proposal B).

## 2026-08-01 — Document size discipline (⏳ TRIAL to 2026-09-01, docs-only)

- **Milestone:** cage's docs law gains a *size* constraint, shipped as a dated trial
  rather than a permanent rule.
- **Implemented (documentation, no code):**
  - `CLAUDE.md` — a short *Document size discipline* block in *Documentation
    discipline*: four composing rules (lead with the answer · one audience per doc ·
    evidence lives elsewhere · hard budget ~40 lines / ≤120-char rows), the
    reference-doc exemption from rule 4 only, the expiry, and a link out for detail.
  - `docs/doc-size-discipline.md` (**new**) — full spec: per-rule detail, the
    three-audience table, a worked bad/good evidence example, the four-step fix
    procedure for an over-budget doc, and the trial-exit criteria.
  - `work/DOC-REGISTRY.md` + `docs/README.md` — row and index entry, both carrying the
    2026-09-01 expiry.
- **Design notes:** the trial **lapses if unreviewed** (a trial that persists by
  default was never a trial). Enforcement (a grep test for over-length rows) is
  deliberately **not built** — it becomes an option only if the trial is retained.
- **Files:** `CLAUDE.md` · `docs/doc-size-discipline.md` · `work/DOC-REGISTRY.md` ·
  `docs/README.md` · `docs/WORKLOG.md`
- **Tests:** none run — documentation only. Suite last green at 833.
- **Next step:** re-cut `docs/OPEN-WORK.md` to the budget — the trial's first test.

## 2026-08-01 — OPEN-WORK made a continuously-maintained doc (docs-only)

- **Milestone:** the plan file now has a *currency* law as well as a *removal* law, so
  it stays true between sessions rather than being reconciled after the fact.
- **Implemented (documentation, no code):**
  - `CLAUDE.md` — the OPEN-WORK entry gained (1) the continuous-maintenance obligation
    with six named triggers and the symmetry *discovering work and not filing it is the
    same defect as finishing work and not removing it*, and (2) a **do not trust its own
    markers** clause: a ✅ in a plan file is an assertion, not evidence — reconcile
    against `regression/`, `archive/`, `IMPLEMENTATION.md` and the code.
  - `docs/OPEN-WORK.md` — header mirrors both rules.
  - `work/DOC-REGISTRY.md` — trigger widened from "a phase opens, closes, or its
    verdict/scope changes" to the full continuous list.
- **Files:** `CLAUDE.md` · `docs/OPEN-WORK.md` · `work/DOC-REGISTRY.md` ·
  `docs/WORKLOG.md`
- **Tests:** none run — documentation only. Suite last green at 833.
- **Next step:** **K — relabel `saved` as gross** (proposal B).

## 2026-08-01 — OPEN-WORK becomes remove-on-done (docs-only)

- **Milestone:** the pending-work plan is now governed by an explicit law rather than
  convention, and the law is written where an agent will read it.
- **Implemented (documentation, no code):**
  - `CLAUDE.md` — two entries. A **release-checklist line** for `[meta] cage_version`
    (derive from `cage.__version__`; `policy_version` deliberately decoupled, it is a
    content counter driving `cage policy sync`). A **maintained-doc entry for
    `docs/OPEN-WORK.md`** carrying the rule: *a completed item is REMOVED, never left
    ticked*; removal legal only after IMPLEMENTATION.md records the outcome and any
    evidence reaches `regression/`; residuals carried forward as their own items.
  - `docs/OPEN-WORK.md` — rewritten under that rule. Header states the law; phase
    index rebuilt **pending-only**; completed section bodies (A · B+B-fix · C · D · E ·
    F · G · I · J) deleted, compressed into one *Done and removed* line; resolved **K1**
    row removed with a pointer to where it was recorded. Duplicate `## K` heading fixed
    (follow-up tracker → `## L`).
  - `docs/README.md` — spent `legd-publish` prompt out of *Active work*; OPEN-WORK
    blurb restated as the law; "Leg D is DONE" → **DONE and PUBLISHED** with the true
    remaining list.
  - `work/archive/v0.36-legd-publish.prompt.md` — archived with the standard header.
- **Why it matters:** the first pass of this very change listed two already-built items
  (`B-fix-3`, the copilot `--path` glob) as pending, because the file's own ✅ markers
  had gone stale. Ground truth came from `regression/` and `archive/`, not the plan —
  which is the failure mode the rule removes.
- **Files:** `CLAUDE.md` · `docs/OPEN-WORK.md` · `docs/README.md` ·
  `docs/WORKLOG.md` · `work/DOC-REGISTRY.md` ·
  `work/archive/v0.36-legd-publish.prompt.md` (moved)
- **Tests:** none run — documentation only, no code touched. Suite last green at 833.
- **Remaining after this:** K (relabel `saved` gross) · meta (`cage_version` drift) ·
  K2 (kiro cross-ledger decision) · K3/K4 (two HONEST-LIMITs to state) · H (release,
  blocked by the no-commit directive).
- **Next step:** **K — relabel `saved` as gross** (proposal B).

## 2026-08-01 — `[sources] path_globs`: `--path` discovery patterns move into `cage.toml`
- **Implemented:** the fix for leg-D finding **K1**. `cage import --path` no longer uses
  per-agent glob literals hardcoded in `importcmd.py`; it reads a new **root-agnostic**
  `path_globs` key from the `[sources]` table. Two keys, two jobs — `glob` stays
  **anchored** to its declared `path` and drives every normal import; `path_globs`
  (`**/…`) is read *only* when `--path`/`--project` replaces the location with a
  user-named root. Reusing the anchored key was rejected in design: it would relocate the
  bug (`*/chatSessions/*.jsonl` matches nothing when `--path` points **at** a
  `chatSessions` dir), not fix it.
- **Shape (decided this session, both options put to Arpit):** `path_globs` is a
  **per-entry key inside the existing `[sources]` table**, not a sibling `[path_globs]`
  table — so there is one table, one materializer, one resolver, and `replace = true`
  covers it for free (same table, same entries, same semantics). An abandoned unstaged
  WIP block in `paths.py` that built a separate table was removed. `--project` was also
  brought onto the key (Arpit's call), so **no** glob literal survives in any import
  branch, not just the `--path` ones.
- **Seed → materialize → authority**, exactly as `[sources]` already works: code holds the
  seed (claude `**/*.jsonl` · copilot `**/events.jsonl` + `**/chatSessions/*.jsonl` · kiro
  `*`), `cage setup` / `--sync-sources` materializes it into `cage.toml`, import reads
  `cage.toml` (Directive A). Copilot names **both** shapes explicitly rather than a blanket
  `**/*.jsonl` — a foreign `.jsonl` under `--path` is never *matched*, rather than being
  read and happening to parse to zero rows.
- **Deliberate behaviour change, made loud:** absent `path_globs` ⇒ `--path` scans
  nothing and prints `⚠ <agent>: no path_globs declared … Run cage setup --sync-sources`.
  No code fallback — a fallback would put the patterns back in two places, which is the
  condition that let the bug exist. A malformed `cage.toml` now also disables `--path`
  capture (fail-open still holds: exit 0, no traceback, and the ⚠ is printed).
- **The other half of the fix:** the zero-match warning now **names the patterns tried** —
  `matched 0 files (tried: **/events.jsonl, **/chatSessions/*.jsonl)`. The glob being
  hidden is why the original bug cost ~20 minutes to find. `_scan` records the patterns
  into the capture-health record; `cage doctor --paths` gained an advisory for a table
  materialized before the key existed.
- **Files:** `cage/paths.py` (`LogSource.path_globs`, seed as triples, per-entry +
  table-level resolution, `path_globs_for`, `path_globs_missing`, renderer),
  `cage/importcmd.py` (`_override_sources`, `missing_path_globs`, `_scan` takes a pattern
  *sequence* and dedupes the file set, health carries the patterns), `cage/report.py`
  (`capture_warnings` names them), `cage/clicmds.py` (`cmd_import_claude` threads policy —
  it passed none, so it would have resolved zero patterns), `cage/pathprobe.py`,
  `cage/data/cage.toml` (inert comment block), `cage/explain_data.py`
  (`cage query path-globs` + the `sources` entry), `tests/srcseed.py`,
  `tests/test_path_globs.py` (new, 15), `tests/test_import_claude.py`,
  `tests/test_universal_capture.py`; docs: `example/toml-config.md`, `GLOSSARY.md`,
  `OPEN-WORK.md` (K1 → RESOLVED), `regression/README.md`, `docs/README.md`,
  `archive/README.md`, the archived handoff/prompt pair.
- **Tests: green — 939 passing.** Two failures predate this change and are unrelated
  (`test_output_spec.py::test_I2_verdict_saving`, `test_savings.py::
  test_record_writes_into_the_per_source_month_shard` — both clock-relative; verified by
  re-running them against the pre-change tree). No golden needed re-blessing: the
  `(tried: …)` clause renders only when the health record carries patterns, and the
  golden fixtures' hand-built records don't. The grep-gate is an AST walk over the import
  adapters and was proven to bite by temporarily reintroducing a literal.
- **Finding doc:** `2026-08-01-finding-copilot-path-glob.md` flipped to **RESOLVED** using
  the repo's existing convention for a sealed published doc — a banner **above** a
  `HASH-COVERS-BELOW` marker, so the published body stays byte-identical and the digest
  verifies unchanged. Body never rewritten.
- **Next:** K0 — relabel `saved` as gross (the only open finding touching the headline
  number).

## 2026-08-01 — Phase I closed: leg D written up, published + hashed
- **Implemented:** the write-up of leg D (the six manual VS Code / IDE cells Arpit drove
  by hand on 2026-08-01), published into `work/regression/` as the three artifact types,
  never merged: one **run report** (immutable, hashed, standalone-readable), four
  **finding docs** (each owning its own Status line), one **phase benchmark** (derived,
  introduces no new numbers) superseding 2026-07-29's.
- **Headline recorded:** same workspace, same six questions, same graphify install —
  **claude invoked graphify unprompted (2 queries, 18,456 tokens saved via the
  *transcript* route, since the shim was not on the VS Code extension's PATH); copilot and
  kiro did not invoke it at all.** Adoption is agent-specific, and cage *measured* it: the
  usage log distinguishes "never ran" from "ran but cage missed it".
- **Honesty boundaries held explicitly:** F2's copilot-VS-Code receipt limit is **UNTESTED
  (never exercised, NOT confirmed)**; the D3/D4 prompt counts are **UNVERIFIED**; the kiro
  ON/OFF delta is **not reconstructible** from the ledger and is not reported. Deviations
  recorded rather than dropped (first D1 import landed in `~/.cage`, 42 rows;
  `workspace-off` contaminated twice and wiped before D1 and D3; cage installed `-e ../cage`).
- **The counterweight, published with the headline (not as a footnote):** a seventh cell
  record appeared mid-write-up — **`saved` is GROSS**. It excludes the cost of *using* the
  tool, so cage printed 18,456 tokens saved on a session whose measured est cost was
  **+31%** over its unassisted twin. The **label** problem is structural (n-independent);
  the **delta** is n = 1 and stays **UNPROVEN**. Corrected the cell record's cost row
  explicitly rather than silently: it apportioned D1's cost from a two-session total
  (≈$0.28 ⇒ ≈+14%), but `imports.jsonl` carries a per-session row for D1
  (`est_cost_usd 0.242783`, 30 rows) ⇒ **+31%**. The correction strengthens the finding.
- **Findings filed:** `saved` is gross (**HIGH**) · copilot `--path` glob (**real code bug** — `importcmd.py:477`
  hardcodes `*/events.jsonl`, unreachable for the VS Code `chatSessions` store) · kiro
  cross-ledger double-count (OPEN) · kiro rows carry no time/session/project
  (HONEST-LIMIT, FINAL) · surface attribution is agent-dependent (HONEST-LIMIT).
- **Hash convention:** the two 2026-07-29 artifacts that needed a banner / status update
  moved from whole-file to `HASH-COVERS-BELOW` marker-range **with their digests
  unchanged** — the header sits above the marker, the bytes below are byte-identical to
  what was published. Nothing existing was edited below a marker.
- **Files:** `work/regression/2026-08-01-leg-d-run-report.md` ·
  `2026-08-01-phase-benchmark.md` · `2026-08-01-finding-{copilot-path-glob,
  kiro-rows-double-count-across-ledgers, kiro-rows-carry-no-time-session-project,
  surface-attribution-is-agent-dependent}.md` (+ `.sha256` sidecars) ·
  `work/regression/README.md` (index rows) · bannered `2026-07-29-phase-benchmark.md` +
  status-headered `2026-07-29-finding-adoption-not-capture.md` (+ their sidecars) ·
  `docs/OPEN-WORK.md` (D done, I complete, new **K** follow-up) · `docs/WORKLOG.md` ·
  `work/DOC-REGISTRY.md`. Cell records committed in `cage-lab`.
- **Tests:** not run — documentation-only change in the cage tree; **no cage code was
  touched** (the copilot glob bug is filed, not fixed).
- **Next:** K1 — fix the copilot `--path` glob, with a test over a `chatSessions/` tree.

## 2026-07-30 — shim integrity: the PATH-winning interceptor, its heal boundary, the hook bypass
- **Implemented (B-fix-1):** `cage/pathshim.py` — resolves `graphify` the way the shell
  does (walk `PATH`, first executable wins) and classifies the winner `absent` · `live` ·
  `dead` · `shadowed` · `foreign`. New doctor check `path-interceptor`: **dead = FAIL**
  with a runnable fix naming the exact file · `shadowed` = warn naming **both** paths ·
  `foreign` = **ok-level** informational (the existing `interceptor` check already warns
  about that same absence; two warns for one condition is the noise that trains people to
  ignore the check) · `absent` = ok. Runs on **every** doctor invocation. The detector is
  `wiringscan.is_live_verb` (the live parser); `verbmap.REMOVED` supplies the fix-hint
  tail only. Reads ≤8 KiB of the winner, executes nothing.
- **Implemented (B-fix-2):** `agents.install` now heals a **dead** PATH-winning
  interceptor when — and only when — it sits in a cage-managed root (`<root>/bin/graphify`
  beside `<root>/.cage/`, `pathshim.managed_root`, deliberately not a walk-up so `~/.cage`
  can't make the whole home dir writable). Outside one, cage never writes; doctor names
  the file and prints the fix. Idempotent (`adoptcmd.refresh_shim` byte-compares first).
- **Implemented (B-fix-3):** `cage/hookbypass.py` — an agent hook naming `graphify` by a
  **path** (claude project/local/user settings, `*.kiro.hook`, foreign hooks included)
  never traverses PATH, so both cage routes are blind. **Advisory, never a failure**;
  wording escalates under `--strict`/`GRAPHIFY_HOOK_STRICT`; the hook is never modified.
- **Published (Task 1):** the three Phase-I lab artifacts now carry `.sha256` sidecars
  (whole-file coverage, stated in each sidecar — distinct from the validation reports'
  marker-range convention); `2026-07-28-phase-1-benchmark.md` bannered **superseded**
  *above* its `HASH-COVERS-BELOW` marker, so its body and published hash are byte-identical
  (verified). Index rows + a hash-convention table added to `work/regression/README.md`.
- **Refactors, no behaviour change:** `wiringscan.verbs_in_shell` extracted from
  `interceptor_verbs` (one detector, not two); `hook_commands`/`display_path` made public
  for `hookbypass` to reuse rather than fork; `doctor --wiring` gained a `_path_winner`
  row so the inventory names the file that decides whether graphify is metered at all.
- **Test-suite hazard closed:** `tests/conftest.py` strips graphify-bearing dirs from
  `PATH`. Without it the B-fix-2 heal would rewrite the developer's own *other-project*
  shim from inside a test run — same class as the existing agent-home redirection.
- **Files:** `cage/pathshim.py` (new) · `cage/hookbypass.py` (new) · `cage/wiringscan.py`
  · `cage/doctorcmd.py` · `cage/agents.py` · `cage/explain_data.py` ·
  `tests/test_pathshim.py` (new) · `tests/test_hookbypass.py` (new) ·
  `tests/conftest.py` · `tests/test_doctor.py` · `work/regression/*` · `docs/GLOSSARY.md`
  · `docs/OPEN-WORK.md` · `docs/README.md` · `work/archive/README.md` + the archived pair.
- **Tests:** 925 passed, **1 pre-existing failure** —
  `test_output_spec.py::test_I2_verdict_saving`, a **clock-driven** golden unrelated to
  this change: `insights verdict` composes `insights regression`, whose 7d window is read
  from the live clock, while `goldenseed._ts` pins 2026-07-01/08/15/22. Today the cutoff
  is `2026-07-22 20:19Z` and the newest seeded call is `2026-07-22 09:00Z` — 11 hours
  outside, so the view flipped to INSUFFICIENT DATA. Deliberately **not re-blessed**:
  blessing would encode a clock-dependent state as the output contract. The 37 new tests
  and every other golden are green.
- **Verified by hand:** all four states reproduced in a scratch tree (dead-in-managed-root
  → `cage setup --wire-only` fix line · dead-outside → `cage setup --project-only <root>`
  or delete · foreign → ok · absent → ok · shadowed → both paths), doctor **exits 1** on
  dead, the out-of-root shim byte-identical after. **The live nine-day failure is now
  visible on this machine:** `✗ path-interceptor` names
  `~/my_programs/anton/bin/graphify` (dead adopt-era shim, cage-managed root) while the
  old root-scoped `interceptor` check still prints the reassuring "not installed (ok if
  you don't use graphify)" directly above it — exactly the false-OK this fix kills.
  anton's shim was **not** touched (out of scope, per Arpit 2026-07-29).
- **Next:** Arpit's call on (a) the clock-dependent I2 golden, (b) the proposed CLAUDE.md
  wiring-liveness sentence (drafted, not applied — the prompt says propose and stop).
  Then manual leg D; the v0.36 release stays blocked on the no-commit directive.

## 2026-07-30 — cage-lab three-agent parity fix (claude+copilot+kiro, both workspaces)
- **Gap found:** the same-day rebuild (below) wired **claude only**
  (`cage setup --claude`) and ran only the claude (+ a stray user-level copilot)
  graphify installer in `workspace-on`. Arpit's standing rule is all three agents,
  always — an unwired agent's ON cell silently becomes a second OFF cell, misread as
  an adoption finding rather than the setup bug it is. Now **law 0** in
  `work/cage-lab/01-setup.md`/`README.md`: three agents, always in scope; a
  non-scriptable one (kiro) is driven by hand, never dropped from the matrix.
- **Fixed:** `cage setup --all --no-graphify` in `workspace-off`, `cage setup --all`
  in `workspace-on` (was `--claude` in both); added `graphify kiro install` alongside
  the (re-run, idempotent) claude/copilot installers in `workspace-on`. `cage setup
  --status` now lists claude+copilot+kiro wired in **both** workspaces.
- **Re-verified the full gate** after the fix: workspace-off still has zero graphify
  artifacts (including in its new `.kiro/` MCP-config dir); workspace-on carries all
  three graphify integrations (CLAUDE.md block+hook, copilot SKILL.md, kiro
  skill+steering) with no clobbering between installers or with cage's own block;
  interceptor still live, still routes through `cage data graphify`, still
  out-competes the stale anton shim; fixture hashes unchanged (fixture was **not**
  re-authored, per standing law); `~/.cage` mtime and `~/.zshrc` sha256 both
  unchanged across the whole pass. `rebuild.sh` updated to assert all of this from
  scratch, idempotently, at $0; `drive.sh` header updated to cite law 0.
- **Found, not fixed (flagged for Arpit):** `work/cage-lab/01-setup.md` §3/§4 have
  been edited elsewhere to pin a *different* fixture layout (`_src/pkg/...`) and
  question set than what's actually built (`_src/tinyshop/...`, this lab's own
  `questions.txt`). Left both exactly as-is per the "never re-author the fixture,
  a hash mismatch is Arpit's call" rule — recorded in `cage-lab/SETUP.md`'s new
  "manual-vs-reality mismatch" section. Needs a decision: revert the doc or
  deliberately re-baseline the fixture.
- Files: `cage-lab/{workspace-off,workspace-on}/` (agent wiring + graphify
  installs), `cage-lab/rebuild.sh`, `cage-lab/drive.sh`, `cage-lab/SETUP.md`,
  `cage-lab/{workspace-off,workspace-on}/.gitignore` (new — kiro's absolute MCP
  path, per `cage doctor`'s own advice); `work/cage-lab/01-setup.md` (§6 gained the
  three-agent + all-graphify-integrations checks).
- Tests: not run (lab-only, no cage source changed).
- Next: still Arpit's call on driving; also his call on the fixture/manual mismatch
  above.

## 2026-07-30 — cage-lab rebuilt from scratch (foundation only, setup + §6 gate)
- **`../cage-lab` was deleted and rebuilt from `work/cage-lab/01-setup.md`**, scoped
  deliberately to setup + verification per Arpit's instruction — no driving, one
  authorized ~$0.02 smoke prompt, everything else $0.
- Built: `_src/tinyshop/` fixture (6 files — `models.py` ~8.1k tokens/20+ dataclasses,
  4 small cross-calling modules: `pricing.py`/`inventory.py`/`orders.py`/`cli.py`,
  real 2-hop call chain `cli→orders→pricing/inventory→models`; hashed into
  `_src/.fixture-sha256`, ran end-to-end before freezing); `questions.txt` (6 Qs, 3
  graphify-sensitive + 3 capture-correctness); `workspace-off` (cage only,
  `--no-graphify`, genuinely clean); `workspace-on` (`graphify update .` → 255
  nodes/450 edges/12 communities, `graphify claude install` + `graphify copilot
  install`, `cage setup --claude` — both CLAUDE.md blocks coexist, no clobbering);
  `SETUP.md`, `rebuild.sh` (idempotent, $0 by default, `--smoke` opts into the paid
  check), `drive.sh` (built, syntax-checked, not run), isolated `labledger/`.
- **All 6 §6 checks PASS**: interceptor resolves inside `$LAB` and routes through
  `cage data graphify` (not dead `cage graphify`); `cage doctor` reports it live;
  both CLAUDE.md blocks present in workspace-on; workspace-off has zero graphify
  artifacts; fixture hashes match; one real smoke prompt (`claude -p`, haiku,
  $0.0189) captured 2 calls into `labledger/`, re-import idempotent (0 new rows),
  `~/.cage` mtime and `~/.zshrc` sha256 both confirmed unchanged before/after.
- **Three real-CLI deviations found and folded back into the manual in this same
  change** (`work/cage-lab/01-setup.md` + `02-run.md`): `.venv` needs a `>=3.11`
  interpreter (machine default `python3` is 3.9.6, too old for cage `>=3.11` and
  graphifyy `>=3.10`); `workspace-off`'s `cage setup` needs `--no-graphify` explicitly
  (else the shared lab `.venv`'s `graphify` on PATH gets OFF its own interceptor
  shim, failing its own "no graphify artifacts" check); PATH needs the *specific*
  workspace's `bin/`, not a generic `$LAB/bin` (`cage doctor`'s liveness check is a
  literal PATH-membership test on the shim's parent dir).
  Also found: `graphifyy` **is** published on PyPI (latest 0.9.30) — the earlier
  belief it wasn't was an artifact of checking under the wrong (too-old) Python.
- **Finding, not a fix:** the 2026-07-29 run's raw artifacts
  (`cage-lab/reports/2026-07-29-*.md`) were never published to `cage/work/regression/`
  before that lab instance was deleted — they no longer exist. Only the prose
  conclusions already transcribed into this file/WORKLOG.md/OPEN-WORK.md survive.
  Recorded as a process lesson in `docs/OPEN-WORK.md` §I.
- Files: `cage-lab/` (new sibling repo — `_src/`, `workspace-off/`, `workspace-on/`,
  `SETUP.md`, `rebuild.sh`, `drive.sh`, `questions.txt`, `.gitignore`, `bin/`,
  `labledger/`); `work/cage-lab/01-setup.md`, `work/cage-lab/02-run.md`,
  `docs/OPEN-WORK.md` (this repo).
- Tests: not run this leg (lab-only work, no cage source changed); cage's own
  in-tree suite untouched.
- Next: Arpit reviews `questions.txt`, authors `runs/<run-id>/run-manifest.md`
  (02-run.md §1), then drives with `./drive.sh on claude <run-id>` (and the copilot/off
  arms) himself.

## 2026-07-29 — OPEN-WORK Phase I scripted legs — clean-room A/B, F1 validated on real traffic
- Built cage-lab from scratch (clean capture, NEW baseline): `_src` toy repo (one ~8.6k-tok
  `big_module.py`), `workspace-off` (clean) + `workspace-on` (261-node graph + `graphify
  claude/copilot install`), `rebuild.sh`/`SETUP.md`/`questions.txt`/`drive.sh`/`run_all.sh`/
  `verify.py`/`run-manifest.md`, isolated `labledger/`.
- Drove **70 real prompts** (claude {OFF,ON} + copilot {OFF, ON-plain, ON-forced}), cheapest
  model each (claude `haiku`, copilot `auto`), captured per-arm with the **dev cage** (F1),
  isolated (`--ledger`, `~/.cage` untouched). Cost **$5.29**, 429 metered turns, 82% cache.
- **Result: 24 graphify savings receipts, all `transcript` route — 23 via the F1 copilot-CLI
  detector (validated on real traffic), 1 via claude auto-adoption.** copilot-on-plain=0 →
  adoption is the gap, not capture. All I.4 assertions PASS (zero UNPRICED, usage=receipts,
  re-import idempotent, three-way reconcile exact).
- Premise corrections: kiro not scriptable (manual leg D); copilot ON is a passive skill.
- Deliverables (in cage-lab/reports/, immutable, hashed): run report · adoption finding ·
  phase benchmark (supersedes Phase-1 benchmark). NOT yet published to `cage/work/regression/`
  (gated on Arpit).
- Tests: cage in-tree suite still **889 passed** (no cage source changed this leg — lab work).
- Next: Arpit's call on publishing artifacts to work/regression + manual leg D (VS Code/kiro).

## 2026-07-29 — OPEN-WORK Phase G (honesty debts + ceiling surfacing) + Phase F (copilot capture reach)
- Implemented **G1** — report-read confidence 0.3 labelled **UNVALIDATED** everywhere it
  surfaces (runtime footnote `graphifytx.report_read_footnote`, `constants` note + test,
  `explain_data`, FORMULAS §2.8, GLOSSARY). **G2** — ADR 0005 veto threshold made precise
  (`dc > 1.0%` over ≥ MIN_COMPARE_N both-route runs) and the honest gap named (`dc` is not
  yet instrumented — a miss is untallied; filed as a follow-up, natural home `insights
  calibration`). **G3** — verified against graphify source: metered verbs (query/path/
  explain) + exports (wiki/html) are LLM-free; `extract`/`update` semantic extraction +
  community labelling call a backend **only when a provider key is set**; the route is the
  existing `cage data proxy` via `*_BASE_URL` (config-only, no code). **G4** — the bounded
  repo ceiling now renders in the `report` footer (`graphifymodel.ceiling_footer_line` →
  `report.render_report(ceiling=…)`, computed in `clicmds.cmd_report`), modeled,
  token-native, **not in CSV**; silent in non-graphify projects (0 goldens changed).
- Implemented **F1** — copilot **CLI** transcript-side graphify detection
  (`graphifytx.detect_and_file_copilot`, wired via `importcmd._detect_graphify_copilot`).
  Reuses the claude `_file_query`/`_file_report_read` (shared counterfactual/id/deferral —
  no forked formula). ADR-0005 acceptance tests pass for copilot. Verified the real
  events.jsonl shape on-machine. **F2** — probed copilot **VS Code** `chatSessions`:
  command present (`commandLine.original`), result absent → usage-row-only, no receipt
  (skipped by the detector).
- Files: `cage/constants.py`, `cage/graphifytx.py`, `cage/graphifymodel.py`,
  `cage/report.py`, `cage/clicmds.py`, `cage/importcmd.py`, `cage/explain_data.py`,
  `docs/adr/0005-*.md`, `docs/FORMULAS.md`, `docs/GLOSSARY.md`, `docs/OPEN-WORK.md`;
  tests: `test_report_savings.py` (+3), `test_graphify_forward.py` (updated),
  `test_graphify_transcript.py` (+UNVALIDATED assert), `test_graphify_copilot.py` (new, 5).
- Tests: `just test` green — **889 passed** (was 881). 0 goldens re-blessed (ceiling silent
  without a graph; bless run confirmed byte-identical).
- Next: propose the CLAUDE.md architecture-note update (graphifytx now claude+copilot-CLI,
  ceiling now community-bounded + in report footer) — **stop, do not edit CLAUDE.md silently.**

## 2026-07-29 — OPEN-WORK Phase A (community-bounded ceiling) + Phase B (VS Code shim probe)
- Implemented: **A** — the day-one repo ceiling is now **bounded by the graph's community
  structure**. New `repoceiling.community_corpus` groups nodes' `source_file` by
  `community` id, resolves+tokenizes each file once, returns the largest community's
  corpus (upper bound), the median (typical), and the whole corpus (context only).
  `graphifymodel.repo_ceiling` uses it (drops the old `Σ corpus − full-report` formula,
  which conflated the 81k-token whole report with a compact answer); pre-community graphs
  fall back to the whole corpus labelled `bounded=False`/`UNBOUNDED`. Verdict: the
  whole-corpus ceiling was **not defensible** — 552,159 tokens / 249 files on cage's own
  repo; bounded → 89,853 / 22 files, typical ≈3,007.
- Implemented: **B** — no code; a direct probe. This session runs *as* the Claude Code VS
  Code extension, so its Bash-tool subprocess PATH is the surface. Found: the interceptor
  reaches PATH only via a shell-rc append (launch-method dependent, per-machine), and the
  PATH-winning shim on this machine is a **stale `cage adopt`-era** one routing through the
  removed `cage graphify` verb (exit 1) ⇒ silent unmetered pass-through. VS Code shim
  capture is CONTINGENT; the transcript route is the reliable one there.
- Files: `cage/repoceiling.py`, `cage/graphifymodel.py`, `tests/test_graphify_forward.py`,
  `cage/explain_data.py`, `docs/FORMULAS.md`, `docs/GLOSSARY.md`, `docs/OPEN-WORK.md`
  (A/B verdicts + corrected §F table), `work/DOC-REGISTRY.md`, `docs/WORKLOG.md`.
- Tests: `just test` green (see next commit-adjacent run); `test_graphify_forward.py`
  10 passed, `test_output_spec.py` unaffected (ceiling not in a golden yet — G4 adds it).
- Next: **STOP GATE 1** — report A + B, wait for Arpit's go before C (paid calls). Then
  G4 surfaces the bounded ceiling in the `report` footer (re-blesses goldens).
- **Post-gate update:** Arpit approved C; on starting it, `cage-lab` was found **absent
  from this machine** — arm B's workspace and arm A's baseline both live in the missing
  `../cage-lab`. **C BLOCKED, 0 paid calls spent**; did not improvise a workspace (would
  fabricate a new baseline). OPEN-WORK Phase C corrected. Blocked on Arpit: restore
  cage-lab, or fold C into I.2.

## 2026-07-28 — graphify capture GC0–GC5 (usage rows · transcript detection · forward model)
- Implemented: the full graphify-capture handoff (GC0–GC5); GC6/G1 remains out of scope.
  - **GC0** — probed real logs (24 copilot-cli sessions, 145 copilot-vscode files, kiro
    token log). Verdict in [graphify-capture.plan.md §3.0](../docs/graphify-capture.plan.md):
    claude ships; copilot-cli *does* carry command+result (`tool.execution_*`,
    `arguments.command`/`result.content`) → out of scope, finding filed; copilot-vscode
    partial; kiro HONEST-LIMIT.
  - **GC1** — always-on usage breadcrumb `state/graphify-usage.jsonl` (`usagelog.py`), one
    row per graphify run at every route; doctor renders "graphify ran N×, R receipts, U
    unmeasurable"; money views byte-identical with rows present (tested).
  - **GC2** — claude transcript detection at `cage import` (`graphifytx.py`): Bash
    `graphify query|explain` (anchored on command position — `grep graphify` rejected) →
    `modeled` receipt reusing the shim counterfactual; Reads of `GRAPH_REPORT.md`/`wiki/**`
    → distinct `report-read` receipt (conf 0.3, footnoted apart). Corpus computation shared
    with GC5b (`repoceiling.py`).
  - **GC3** ([ADR 0005](../docs/adr/0005-graphify-receipt-ids-session-inclusive-cross-route-deferral.md))
    — deterministic session-inclusive ids (`graphifymeter.receipt_id`) + content-key
    deferral; shim stamps `session=""` (root-cause fix). Both acceptance tests pass: same
    query/two sessions ⇒ two receipts; shim+transcript/one session ⇒ one receipt. Added
    additive `savings_id` kwarg to `make_savings`/`savings.record` (call_id precedent).
  - **GC4** — `cage doctor` graph-staleness check (`graph.json` mtime vs HEAD, git shelled
    out, fail-open).
  - **GC5** — `graphifymodel.py`: history band (median+IQR, refuses < `MIN_ESTIMATE_N`) +
    deterministic day-one repo ceiling from `graph.json`; both composed into
    `insights verdict graphify` (pure composer, refusal intact). Golden-workspace ceiling:
    7 files ≈ 12,761 corpus tokens → ≈ 7,445 tokens/question.
- Files: NEW `cage/usagelog.py`, `cage/graphifytx.py`, `cage/repoceiling.py`,
  `cage/graphifymodel.py`; edited `graphifymeter.py`, `schema.py`, `savings.py`,
  `constants.py`, `importcmd.py`, `paths.py`, `cleanup.py`, `doctorcmd.py`, `verdict.py`;
  NEW `docs/adr/0005-*.md`; docs (FORMULAS/GLOSSARY/explain_data/PLAN/DOC-REGISTRY);
  tests `test_graphify_usage.py`, `test_graphify_transcript.py`, `test_graphify_forward.py`,
  `test_doctor.py` (check-set). Re-blessed goldens: **I2, I3** (`insights verdict graphify`
  gains the forward block; I4/`verdict fux` unchanged).
- Tests: green — 879 passed. End-to-end verified via `cage import` CLI (one receipt, one
  usage row, idempotent re-import, doctor lines).
- Next: GC6/G1 (the A/B re-run) is now runnable — capture can no longer miss graphify.
  Cage tree stays uncommitted; handoff/prompt pair kept active pending GC6.

---

## 2026-07-28 — G0.5 executed: golden workspace rebuilt with real installers, provenance recorded

- Implemented (cage-lab only, no cage code touched): rebuilt
  `cage-lab/golden/workspace/`'s tooling layer end to end — `graphify update .`
  (build verb), `graphify claude install` (CLAUDE.md steering + PreToolUse
  hook), `cage setup --claude` (`.cage/`, `bin/graphify` shim, `.mcp.json`,
  cage's own CLAUDE.md block) — via the tools' own installers only, never a
  hand-written block. Fixture (`pkg/`, `README.md`, `.kiro/settings/lsp.json`)
  preserved byte-for-byte (sha256-asserted, 9 files, before == after);
  `golden/captures/**` (148 files) and `cage/work/regression/**` (46 files)
  asserted untouched. `cage doctor` confirms the interceptor **live** (not
  merely present) once `workspace/bin` is on PATH, matching `drive.py`'s own
  `build_env()` convention for `graphify=on` cells. `workspace/SETUP.md` +
  `workspace/rebuild.sh` are the provenance artifacts; `rebuild.sh` was
  actually executed (not just authored) and reproduced byte-identical
  `CLAUDE.md`/`settings.json` output on a second pass.
- Findings that correct plan §1.1 (installed `graphifyy 0.5.0` vs. the docs
  table it was built from — all folded into the plan on contact):
  1. **The PreToolUse hook never invokes the `graphify` binary at all.** It's
     a static bash conditional (`[ -f graphify-out/graph.json ] && echo
     '<hard-coded JSON>' || true`) that injects a fixed `additionalContext`
     string on a `Glob|Grep` matcher — no subprocess, nothing for cage's
     PATH-interception shim to intercept or bypass. The PATH-bypass risk
     §1.1(a) named is real but lives downstream, only if the agent itself
     runs `graphify query|...` as a shell command per the CLAUDE.md prose.
  2. **No `--strict` flag exists** anywhere in this version (confirmed by
     reading `graphify/__main__.py`'s own arg parsing) — the plan's
     "unverified, check `--help` first" note is now resolved: it isn't there.
  3. **No per-subcommand `--help`** — `graphify claude install --help` runs
     the installer for real (idempotent no-op only if the marker is already
     present) rather than printing help.
  4. **Copilot and Kiro *do* have first-party installers** (`graphify copilot
     install`, `graphify vscode install`, `graphify kiro install`) —
     §1.1(b)'s "no copilot or kiro installer" claim was wrong. Doesn't change
     G0.5/G1 scope (claude only) but invalidates the "asymmetry" framing for
     any future copilot/kiro arm.
  5. Neither installer clobbers the other's `CLAUDE.md` block in the
     graphify→cage order (both are marker-based and additive) — verified
     empirically via before/after snapshots, not just read from source. One
     cosmetic side effect: whichever tool is first to see an absent
     `CLAUDE.md` decides whether the file gets a `# CLAUDE.md` H1 — here
     graphify went first and doesn't add one, so the previous workspace's
     title line is gone in the rebuild.
  6. (Environment note, not a cage-lab defect) an unrelated project's
     `graphify` PATH-shadowing shim was found to be dead — probes the
     removed `cage graphify` verb — corroborating a stale-shim class
     `drive.py` already guards against (`_is_stale_graphify_shim`). Not
     touched; all rebuild commands used graphify's absolute path instead.
- Files: `cage-lab/golden/workspace/{SETUP.md,rebuild.sh}` (new),
  `cage-lab/golden/{workspace-pre-g05-manifest.json,workspace-post-g05-manifest.json}`
  (new), `cage-lab/golden/README.md` (pointer + reproducibility rule),
  `cage-lab/.gitignore` (nested `workspace/.git/` ignored), `cage-lab/golden/workspace/{CLAUDE.md,.claude/,.mcp.json,graphify-out/,bin/,.cage/,.git/}`
  (re-derived) — all committed in **cage-lab only**.
  `docs/graphify-ab-steering.plan.md` (§1.1 corrections above), this file,
  `docs/WORKLOG.md`, `work/DOC-REGISTRY.md` — **cage tree stays
  uncommitted**.
- Tests: N/A (cage-lab is black-box; no cage code changed). `rebuild.sh`'s
  own verification (sha256 identity + `cage doctor` interceptor-live grep)
  is the test, and it was run twice successfully.
- Next: **G1** — run `graphify claude install`'s real condition against a
  driven claude question (~2 paid calls) and record two outcomes: did
  graphify fire, did cage see it. G0.5 predicts the shim has nothing to
  bypass at the hook layer, so G1's PATH-bypass question now hinges on
  whether the agent chooses to invoke `graphify` itself.

## 2026-08-01 — Leg D complete; gross-vs-net finding raised as OPEN-WORK §K (HIGH)

- Implemented (docs/evidence only): six leg-D cell records
  (`cage-lab/reports/cells/D1..D6`), the gross-vs-net finding
  (`FINDING-gross-vs-net-savings.md`), OPEN-WORK **§K** + phase-index row, and Task 2b
  inserted into `legd-publish.prompt.md` making the finding **blocking** for the
  benchmark.
- Headline: claude invoked graphify unprompted (2 queries, 18,456 tokens saved via the
  **transcript** route — the shim never ran); copilot and kiro did not. **And** the
  paired D1/D2 data shows the ON arm cost ≈14% more, exposing `saved` as a **gross**
  per-query counterfactual.
- Files: `cage-lab/reports/cells/*` (7 new), `docs/OPEN-WORK.md`,
  `docs/legd-publish.prompt.md`, `docs/WORKLOG.md`.
- Tests: not run (evidence + docs; no code touched).
- Next: publish leg D with §K, relabel `saved` (proposal B), then `path_globs`.

## 2026-07-30 — Docs: three implemented prompts archived; OPEN-WORK reduced to five items

- Implemented (docs only): archived `three-agent-parity.prompt.md`,
  `cage-lab-rebuild.prompt.md` and `open-work.prompt.md` to `work/archive/v0.36-*` with
  headers (all implemented and green); `docs/` root back to nine living docs with
  *Active work* empty by design; `OPEN-WORK.md` pending list rewritten to the five real
  remaining items (ledger hygiene · real-world proof of B-fix-1/3 · leg D · final
  benchmark · release + the `-e ../cage` deviation expiry).
- Files: `work/archive/v0.36-{three-agent-parity,cage-lab-rebuild,open-work-runner}.prompt.md`
  (new), `docs/README.md`, `docs/OPEN-WORK.md`, `docs/WORKLOG.md`.
- Tests: not run (documentation only).
- Next: Arpit's ledger decision, then `cage doctor` confirmation, then leg D.

## 2026-07-30 — Lab review: graphify 0.9.30 facts recorded, three stale findings corrected

- Implemented (docs only): `work/cage-lab/01-setup.md` §3/§4 rewritten to the real
  `tinyshop` fixture + the six actual questions; new **§4a** (graphify 0.9.30 hook
  reality, the absolute-path bypass, the `--strict` OFF decision, verbatim-hook-block
  rule); OFF-arm `[tools] order` exemption; `02-run.md` §1a ledger hygiene;
  `03-verify.md` ON cells now require three answers; `OPEN-WORK.md` **§J** + phase-index
  row, with §C's superseded "PATH-bypass dead" line marked.
- Files: `work/cage-lab/{01-setup,02-run,03-verify}.md`, `docs/OPEN-WORK.md`,
  `docs/WORKLOG.md`.
- Tests: not run (documentation only; no code touched).
- Next: ledger reset decision, then Arpit drives. Product question filed (doctor warning
  for absolute-path graphify hooks) — unbuilt.

## 2026-07-29 — Lab law 0: all three agents always in scope (docs swept) + parity prompt

- Implemented (docs only): `work/cage-lab/README.md` gains **law 0** (Claude Code ·
  Copilot · Kiro always in scope, `cage setup --all`, all three graphify installers,
  undriveable surfaces are `NOT AVAILABLE`/`UNPROVEN` and never dropped); conditional
  language swept from 01-setup/02-run/05-manual-cells; new
  `docs/three-agent-parity.prompt.md` to bring the existing lab to parity.
- Files: `work/cage-lab/{README,01-setup,02-run,05-manual-cells}.md`,
  `docs/three-agent-parity.prompt.md` (new), `docs/README.md`, `docs/WORKLOG.md`.
- Tests: not run (documentation only).
- Next: run the parity prompt, then Arpit drives the six questions.

## 2026-07-29 — work/cage-lab/ created: the from-scratch rebuild manual

- Implemented (docs only): `work/cage-lab/` — README + 01-setup · 02-run · 03-verify ·
  04-publish · 05-manual-cells. Makes `../cage-lab` fully disposable: everything needed
  to recreate it now lives in cage, versioned with the tool it tests. Encodes the five
  laws (zero dummy data · own `.venv` with driver-set PATH · isolated ledger ·
  reproducible workspace · rebuild config not corpus).
- Files: `work/cage-lab/*.md` (6 new), `docs/README.md`, `docs/OPEN-WORK.md`,
  `CLAUDE.md` (pointer), `docs/WORKLOG.md`.
- Tests: not run (documentation only; no code touched).
- Next: delete `../cage-lab` and rebuild from `work/cage-lab/01-setup.md`.

## 2026-07-29 — `.venv` lab isolation made standing (CLAUDE.md + OPEN-WORK §I.2a)

- Implemented (docs/steering): standing rule that every lab runs in its own `.venv`
  with PATH set explicitly by the driver (`$LAB/bin:$LAB/.venv/bin:$PATH`), the run
  proving its own PATH into the manifest and `SETUP.md` naming exact builds; the
  `-e ../cage` black-box deviation recorded with its exit condition (phase H); the
  VS-Code-subprocess limit stated explicitly.
- Files: `CLAUDE.md` (cage-lab section), `docs/OPEN-WORK.md` (§I.2a + I.2 table row +
  D.0 note + durable rules), `docs/WORKLOG.md`.
- Tests: not run (docs/steering only; no code touched).
- Next: shim-integrity prompt (publish + B-fix-1/2), then leg D. Tree uncommitted.

## 2026-07-29 — Usage-row invariant landed in CLAUDE.md; OPEN-WORK decisions recorded

- Implemented: **CLAUDE.md** gains the usage-row invariant (two lines, Must-Know
  Rules) — diagnostic-only, never priced, never read by a derived money view,
  `args_hash` never carries query text. `docs/OPEN-WORK.md` records four decisions:
  repeats = 3 (with the n=1/n=3 corpus split so the bill doesn't triple), ceiling
  surfaced beyond verdict/query as new item **G4** (report footer, gated on A,
  re-blesses goldens), manual testing **last** (D = I's final leg), cost cap still
  open and now the sole gate on I.
- Files: `CLAUDE.md`, `docs/OPEN-WORK.md`, `docs/WORKLOG.md`.
- Tests: not run (docs + steering only; no code touched — G4 is not yet built).
- Next: A (ceiling credibility) → B (VS Code shim) → C (G1). Tree uncommitted.

## 2026-07-29 — OPEN-WORK phase I added (clean-room end-to-end validation)

- Implemented (docs only): `docs/OPEN-WORK.md` gains **phase I** — cage-lab from
  scratch → drive questions → capture logs + graphify savings → verify every
  number, **with graphify and without**; I.0 ZERO-dummy-data law, I.2 scoped
  rebuild (keep captures + published reports, isolated ledger), I.3 pairing
  protocol (n≥3, OFF genuinely off), I.4 per-agent correctness bars (kiro's
  `estimated` is FINAL, not a defect), I.5 blockers, I.6 three-artifact
  deliverable. **E absorbed into I; D becomes I's manual leg** (rows kept).
- Files: `docs/OPEN-WORK.md`, `docs/README.md`, `docs/WORKLOG.md`.
- Tests: not run (documentation change; no code touched).
- Next: A + B (free) → C (~2 calls) → I on Arpit's go. Cage tree uncommitted.

## 2026-07-28 — Docs consolidation: 24 cycle docs archived → one OPEN-WORK plan

- Implemented (docs only): archived the entire v0.36 planning cycle to
  `work/archive/v0.36-*` with per-file headers; created `docs/OPEN-WORK.md` as the
  single plan of pending work (phases A–H) carrying every remainder plus the
  durable rules promoted out of the archived plans; rewrote `docs/README.md`
  (Active work is now empty by design) and added the consolidation note to
  `work/archive/README.md`.
- Files: `work/archive/v0.36-*` (24 new), `docs/OPEN-WORK.md` (new),
  `docs/README.md`, `work/archive/README.md`, `docs/WORKLOG.md`.
- Tests: not run (documentation change; no code touched).
- Next: OPEN-WORK **A** (ceiling credibility) and **B** (VS Code shim check) —
  both free — then **C** (G1, ~2 paid calls). Cage tree stays uncommitted.

## 2026-07-28 — graphify-capture packaged: plan + handoff + prompt (pre-G1)

- Implemented (docs only): the graphify-capture cycle — GC0 probe · GC1 usage
  rows · GC2 transcript-side detection · GC3 dedupe · GC4 freshness · GC5 forward
  model (history band + graph-derived ceiling + verdict composition) · GC6 = G1
  re-run. Grounded in the G0.5 finding that the PreToolUse hook spawns no process
  (PATH-bypass hypothesis dead; adoption is the surviving explanation).
- Files: `docs/graphify-capture.plan.md`, `docs/graphify-capture.handoff.md`,
  `docs/graphify-capture.prompt.md` (all new), `docs/README.md`,
  `docs/WORKLOG.md`.
- Tests: not run (documentation change; no code touched).
- Next: execute graphify-capture (**Opus**, unpaid) → G1 → archive the G0.5 pair.

## 2026-07-28 — G0.5 packaged: handoff + prompt, plan amended by the debate gate

- Implemented (docs only): the G0.5 handoff/prompt pair, plus plan **§1.2.0** —
  the layered-rebuild correction the debate gate forced (*rebuild the
  configuration, never the corpus*: fixture bytes preserved and hash-asserted;
  only the tooling layer re-derived). `graphify hook install` cut from scope as
  capture noise. Rebuild step list rewritten with hash steps 0 and 7.
- Files: `docs/graphify-ab-g05-rebuild.handoff.md` (new),
  `docs/graphify-ab-g05-rebuild.prompt.md` (rewritten),
  `docs/graphify-ab-steering.plan.md` (§1.2.0 + amended §1.2 table + §1.2.1),
  `docs/README.md`, `docs/WORKLOG.md`.
- Tests: not run (documentation change; no code touched).
- Next: execute **G0.5** (Sonnet, unpaid) in cage-lab → then **G1** (~2 paid
  calls). Cage tree stays uncommitted.

## 2026-07-28 — Graphify A/B plan completed: real installers + clean-rebuild phase (G0.5)

- Implemented (docs only, no code): graphify's actual setup surface recorded
  (`graphify claude install` = CLAUDE.md + **PreToolUse hook**; no copilot/kiro
  installer exists); the **PATH-bypass risk** named as a two-outcome measurement in
  arm B; the workspace "dump it" scoped into REBUILD / DELETE / KEEP / NEVER-DELETE;
  new phase **G0.5 clean rebuild** with recorded provenance; and the standing rule
  *a workspace is evidence only if reproducible* promoted into the golden-set plan.
- Files: `docs/graphify-ab-steering.plan.md` (phase index + §1.1, §1.2, §1.2.1,
  §1.2.2), `work/cage-lab-golden-set.plan.md` (§2.4a), `docs/WORKLOG.md`,
  `docs/README.md`.
- Tests: not run (documentation change; no code touched).
- Next: execute **G0.5** in cage-lab — rebuild `golden/workspace/` via
  `graphify claude install` + `cage setup --claude` with `SETUP.md`/`rebuild.sh`
  recorded — then **G1** (~2 paid calls). Cage tree stays uncommitted.

## 2026-07-28 — Graphify A/B diagnosed: the test workspace had no graphify steering

- Reviewed the Phase 1 benchmark's open items and inspected
  `cage-lab/golden/workspace/`. **Setup present:** `bin/graphify` (cage's
  interceptor shim + recursion guard), a **real** `graphify-out/` graph
  (GRAPH_REPORT/graph.json/cache), `[tools] order = ["graphify", …]`.
  **Absent:** any graphify mention in `workspace/CLAUDE.md` — it carries only the
  `<!-- cage:start -->` block, while cage's own repo CLAUDE.md has an explicit
  "prefer `graphify query` over grep" steering block.
- **Therefore V2/V4 measured the wrong condition:** an agent asked an architecture
  question in a repo that never advertised graphify. The finding's observation
  stands; its implication (graphify savings never materialise in real use) does
  not follow, since real graphify-enabled repos carry the steering.
- **Stakes:** that implication is the leading candidate explanation for the
  2026-07-22 "0 real receipts across 36,451 calls". Missing steering ⇒ a
  `cage setup` fix and the mystery closes; steering present and still no fire ⇒ a
  far more serious adoption finding. The evidence to date cannot distinguish them.
- **Ownership asymmetry noted:** *cage writes the shim; graphify writes the
  steering.* No component owns the half-configured state the golden workspace was
  in — a candidate finding in its own right.
- Implemented (docs/spec): `docs/graphify-ab-steering.plan.md` — phase index
  G0–G4; three arms (A unprompted/no-steering ✅ done · **B unprompted WITH
  steering ⏳ ~2 calls** · C driver-invoked, only if B is negative); a decision
  tree stating what each outcome *ships*; and the acceptance rule that the
  "0 real receipts" link must be **supported with evidence or explicitly
  withdrawn**. Arm B must be a **new run report** (a different condition, never an
  amendment to run-003).
- Files: `docs/graphify-ab-steering.plan.md` (new), `docs/{README,WORKLOG,
  IMPLEMENTATION}.md`.
- Tests: not run (docs-only; no cage source change until G4, whose shape the
  result decides).
- Next: run G1 (arm B, ~2 paid calls).


## 2026-07-28 — Phase 1 BENCHMARK authored + Phase 1 CLOSED (docs-only, derived)

- Milestone: golden-set Phase 1 closeout **§P5** — the **third artifact type**
  (run report = one run · finding doc = one defect · **benchmark = one phase**):
  *what does cage capture, and how correct is it?*, derived from run-002/run-003 +
  the five finding docs + the Kiro proxy probe. **No new number** — every cell
  cites its evidence.
- Implemented:
  - **`PHASE-1-BENCHMARK.md`** (cage-lab `golden/findings/`) — headline (3 lines) ·
    coverage up front (**6/12 cells, scripted CLI only**) · the accuracy summary
    block · a **FINAL-vs-PENDING** table (kiro tokens FINAL by vendor design;
    every VS Code cell PENDING/P3 — never blurred) · the agent×surface×field
    matrix with method tag + verdict (EXACT / HONEST-LIMIT / UNPROVEN / WRONG) +
    permanence + citation per cell · open defects. Hashed (sha256
    `58948469192c`), published byte-identical into
    `work/regression/2026-07-28-phase-1-benchmark.md` (+ `.sha256`).
  - **Verdicts:** claude CLI **EXACT** (381,813 / 565,637, 3-way) · copilot CLI
    **EXACT** post-fix (227,298 / 233,675) · kiro CLI **HONEST-LIMIT** (12/15
    credit rows, `estimated`; tokens null, FINAL) · all VS Code **UNPROVEN**.
  - **`inputs.toml`** (cage-lab root) re-pointed at `golden/captures/**` as
    **primary** inputs (9 cells); `samples/**` demoted to secondary/legacy.
  - **Phase 1 CLOSED** in the closeout plan phase index + §P5.4; benchmark
    prompt archived (`work/archive/v0.36-phase1-benchmark.prompt.md`); HISTORY +
    both regression-README indexes + docs/README Active-work updated.
- Files: cage-lab `golden/findings/PHASE-1-BENCHMARK.md`(+`.sha256`),
  `golden/findings/HISTORY.md`, `inputs.toml`; cage `work/regression/2026-07-28-phase-1-benchmark.md`(+`.sha256`),
  `work/regression/README.md`, `docs/phase1-closeout.plan.md`, `docs/README.md`,
  `work/archive/README.md`, `work/archive/v0.36-phase1-benchmark.prompt.md` (moved).
- Tests: n/a (docs/derived only; no code touched). Hash round-trip verified.
- Next: P3 (Arpit's manual VS Code/IDE sweep) answers the 6 PENDING cells; P4
  Phase-2 sweep enriches the benchmark (graphify A/B measured). Cage tree stays
  **uncommitted** per directive.

## 2026-07-28 — report-per-run Phase 7: legacy reports split (docs-only)

- Implemented (docs restructure, report-per-run.plan §7): split the pre-golden-set
  `2026-07-22-capture-report.md` into the report-per-run model.
  - **`2026-07-22-lab-run-001.md`** — the 07-22 run, self-contained: per-agent
    table, cache split, gap_ms coverage, receipts, labs, reproduce; the eight
    findings as one line + link. **No later status** (greps clean of RESOLVED /
    v0.3x / fixed in / reframed).
  - **Eight `2026-07-22-finding-<slug>.md`** (taxonomy slugs: receipts-empty,
    health-contradiction, kiro-empty, unpriced-copilot-auto,
    cache-dominated-headline, no-debug-log, gap-ms-sparse, stale-import) — each
    owns a `Status:` line + append-only history.
  - **F1 (receipts-empty)** carries the judgment call: current status
    **PARTIALLY RESOLVED** (capture-path cause — a dead interceptor verb — fixed
    v0.32.0; residual is product-level, agents don't invoke savings tools
    unprompted → linked to the golden `graphify-ab-no-fire` finding). The wrong
    first diagnosis ("graphify run directly / interceptor missing") is shown under
    an explicit *Superseded first diagnosis* heading.
  - **Corrections absorbed as history**: 07-23 → health-contradiction (v0.31.2
    off-by-one), 07-24 f1-root-cause → receipts-empty; both correction files stay
    on disk, banner-marked SUPERSEDED, and are cited from the finding docs. The
    07-24 capture-log-hook-gap diagnosis is owned as F6's deferred follow-on.
  - **Indexes**: `work/regression/README.md` (real-ledger lab-runs section +
    finding-docs table + absorbed-corrections table) and `cage-lab/golden/findings/
    HISTORY.md` (broadened to index both golden validation runs and real-ledger lab
    sweeps; lab-run-001 + lab-baseline rows added).
  - **07-25 baseline**: judged self-contained (matrix run, no embedded later
    status) — HISTORY/README row only, not split, not superseded.
- Judgment noted: the two 07-24 finding-shaped files were **not** given separate
  finding docs — capture-log-hook-gap is owned by F6 as a follow-on; field-gate-
  post-heal-check is a self-contained acceptance-analysis that owns its own status.
  Both are indexed in the README corrections table.
- Files: `work/regression/2026-07-22-lab-run-001.md`,
  `work/regression/2026-07-22-finding-*.md` (×8), banners on
  `2026-07-22-capture-report.md` / `2026-07-23-f2-correction.md` /
  `2026-07-24-f1-root-cause.md`, `work/regression/README.md`,
  `../cage-lab/golden/findings/HISTORY.md`.
- Tests: not run (docs-only; no cage source touched). No paid calls; no ledger read.
- Next: mark report-per-run.plan §7 phase-index row ✅; optionally give the two
  07-24 files formal HISTORY rows if a future run wants them as standalone runs.

## 2026-07-28 — Phase 1 BENCHMARK specced (third artifact type)

- Implemented (docs/spec): `docs/phase1-closeout.plan.md` **§P5 rewritten** —
  from "field matrix + wire-in" to **the Phase 1 benchmark** (Arpit: *what is
  being captured, and how correct is it*, before Phase 2/3) — plus
  `docs/phase1-benchmark.prompt.md` (**Model: Opus** — the doc that will be cited
  as "what cage proves"; overstating one cell is the failure mode and it's a
  per-row judgment).
- **A third artifact type, named:** run report (one run) · finding doc (one
  defect) · **phase benchmark (one phase, all runs)**. The benchmark is
  **derived, never observed** — every cell cites a run report or finding doc, and
  it introduces **no new numbers**; if the executor computes something, a run
  report is missing data and that absence is the finding.
- **Verdict vocabulary per agent × surface × field:** EXACT (3-way reconciled,
  figures cited) · HONEST-LIMIT (no such number in the source; recorded + tagged)
  · UNPROVEN (untested) · WRONG (open defect, linked) — each with a citation.
- **FINAL vs PENDING made non-negotiable:** "Kiro has no tokens" (vendor design,
  closed by the P2 probe) vs "VS Code untested" are different classes; blurring
  them is called out as the most damaging available error. Coverage must lead
  with **6/12 cells, scripted CLI only**.
- Closes with: publish hashed + HISTORY row, wire `golden/captures/**` into the
  lab's `inputs.toml`, mark Phase 1 closed.
- Files: `docs/phase1-closeout.plan.md`, `docs/phase1-benchmark.prompt.md` (new),
  `docs/{README,WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only).
- Next: run the benchmark prompt (unpaid) → Phase 1 closed → P3 manual sweep +
  Phase 2 corpus sweep.


## 2026-07-28 — report-per-run phase 7 specced: split the LEGACY reports

- Implemented (docs/spec): `docs/report-per-run.plan.md` **§7** (+ phase-index
  row 7) and `docs/report-per-run-legacy.prompt.md` (**Model: Opus** — the
  findings have *contradictory* recorded histories, so deciding each one's
  current status is judgment, not transcription).
- **What's still layered:** `2026-07-22-capture-report.md` mixes the run's
  observations, F1–F8 **inline**, and later lifecycle **baked into headings**
  (`F3/F5/F7 … ✅ RESOLVED v0.34.0`) — statuses the 07-22 run never observed.
  Its two corrections (`2026-07-23-f2-correction`, `2026-07-24-f1-root-cause`)
  live in separate files *because* the report couldn't be edited: a finding's
  history spread across three files and **owned by none**.
- **Why it matters (plan §7.4), strongest reason first:** `work/regression/` is
  what a future agent reads to learn what's broken, and today **F1's superseded
  first diagnosis outranks its real root cause** — "graphify is being run
  directly" reads as current in the report while the dead-interceptor-verb cause
  sits in a correction file. Also: the finding ids were designed as stable
  cross-run handles and can only work if each id owns a document.
- **Specced artifacts:** `2026-07-22-lab-run-001.md` (observations only —
  grep-clean of `RESOLVED`/`v0.34`/`fixed in`) · eight
  `2026-07-22-finding-<taxonomy-id>.md` each owning a `Status:` line + append-only
  history · corrections **absorbed as history inside the finding docs while
  staying on disk, cited** · HISTORY/README rows for the legacy runs · originals
  marked SUPERSEDED, nothing deleted.
- **F1 called out as the judgment call** — three partial answers on record
  (original · 07-24 correction · the golden set's "agents don't invoke graphify
  unprompted"); the prompt requires an unambiguous current status with the
  superseded diagnosis *visibly* superseded, and a STOP if the record can't
  settle it.
- Rules carried over unchanged: transcribe never recompute · no paid calls · a
  run report carries no later status · every number lands in exactly one artifact.
- Files: `docs/report-per-run.plan.md`, `docs/report-per-run-legacy.prompt.md`
  (new), `docs/{README,WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only).
- Next: execute phase 7; then Arpit's manual cells V6–V11.


## 2026-07-28 — One report per run BUILT (generator + retro-split + finding docs)

- Implemented (all phases of `docs/report-per-run.plan.md`; **cage tree uncommitted**
  per directive, cage-lab is where the code lives):
  - **P2 generator:** reworked `cage-lab/golden/publish_report.py` — publishes ONE
    run from `findings/runs/<run-id>/REPORT.md`, adds the sha256 header + marker,
    copies to `work/regression/<date>-validation-<run-id>.md` + repoints
    `latest-validation-report.md`. **Structurally can't append:** refuses if the
    source already carries the hash marker or the dated copy exists; no
    read-and-reprepend path exists.
  - **P4 findings:** 5 dated finding docs, each a standalone Status line —
    copilot-resumed-undercount (RESOLVED), graphify-shim-recursion (OPEN, mitigated),
    graphify-ab-no-fire (OPEN, product-level), kiro-cli-sqlite-credits (CLOSED),
    surface-restamp-collision (RESOLVED).
  - **P5 retro-split:** authored + published run-002 (pre-fix baseline) and run-003
    (post-fix re-run) from the layered report's own text (transcribed, not
    recomputed). Old layered file + its 3 earlier hash-versions marked SUPERSEDED via
    a banner **above** the hashed range → body/hash intact.
  - **P3 index:** `cage-lab/golden/findings/HISTORY.md` + a `## Per-run validation
    reports` table in `work/regression/README.md`, one row per run.
- Files: `cage-lab/golden/publish_report.py`, `cage-lab/golden/findings/runs/run-00{2,3}/REPORT.md`,
  `cage-lab/golden/findings/HISTORY.md`, `cage-lab/golden/findings/VALIDATION-REPORT.md`
  (SUPERSEDED banner), `cage-lab/golden/README.md`; `cage/work/regression/`
  (2 run reports + 2 sidecars, 5 finding docs, README index, latest pointer, 4 layered
  files banner-marked); `cage/docs/report-per-run.{plan,handoff}.md`,
  `cage/work/cage-lab-golden-set.plan.md`.
- Tests: verification pass green — all body hashes match sidecars (banners above the
  marker didn't move them); `latest` → run-003; grep proves neither run report holds
  the other's numbers; number-accounting shows every original figure survives across
  run-002 ∪ run-003 ∪ finding docs (shared before/after anchors — 227,298 / 233,675
  truth-vs-cage, unchanged claude, 37,510 undercount==self-heal — appear in both by
  design). No paid agent calls.
- Next: archive `report-per-run.{plan,handoff}.md` to `work/archive/` on the release
  these ride; give the manual sweep (V6–V11) its own run report when it runs.

## 2026-07-28 — One report per run specced (plan + handoff + prompt)

- Implemented (docs/spec): `docs/report-per-run.{plan,handoff,prompt}.md`
  (**Model: Opus** — the retro-split partitions published hashed evidence;
  mis-attributing a number would poison the corpus, not merely confuse a reader).
- **Trigger:** Arpit still saw conflicting numbers (§2's `227,298 · 189,788 ❌`
  vs the top's `8/8 exactly 227,298`). Both correct — of different runs. P0's
  banners had labelled the conflict rather than removed it.
- **Diagnosis:** one document was answering **three** questions — what happened in
  this run · a defect's status now · how numbers moved across runs. A wrong shape
  can't be fixed by labelling, which is why the banners didn't satisfy.
- **The split:** *run report* (this run only; **immutable** once published; never
  mentions a later run) · *finding doc* (a defect's status now; mutable; spans
  runs) · *history index* (`findings/HISTORY.md`, one row per run — where the
  pre-fix → post-fix movement now lives explicitly, each row naming its run).
- **Rules written in:** a run report never mentions a later run · before/after
  columns, superseded banners and later-dated finding statuses are **forbidden**
  in a run report · the generator must be *structurally incapable* of appending
  to an existing report · self-enforcing check: **wanting to add a banner means
  the split is wrong.**
- **Retro-split** of the layered report into run-002 (pre-fix) + run-003
  (post-fix), guarded by: **transcribe from the published text, never recompute**,
  and the acceptance test *every number in the original appears in exactly one
  split — none lost, none duplicated*. Old layered file stays, marked SUPERSEDED.
- No paid calls (restructure only).
- Files: `docs/report-per-run.plan.md`, `docs/report-per-run.handoff.md`,
  `docs/report-per-run.prompt.md` (all new), `docs/{README,WORKLOG,
  IMPLEMENTATION}.md`.
- Tests: not run (docs-only).
- Next: execute it; the manual sweep V6–V11 then gets its **own** run report.

## 2026-07-28 — Phase 1 closeout P2: Kiro proxy probe — CLOSED negative (Outcome B)

- The last untried route to *exact* Kiro tokens: put cage in the request path via
  `cage data meter` instead of reading Kiro's null-token store. **Result: does not
  work — definitively.** Kiro CLI cost stays **credit-derived `estimated`, by vendor
  design.** Closes capture-precision item #11 (specced, never executed).
- Probed first (no assumptions): kiro-cli honors **neither** `ANTHROPIC_BASE_URL`
  nor `OPENAI_BASE_URL` (the only envs `metercmd.run` sets) — it routes to AWS
  CodeWhisperer / Amazon Q (`api.codewhisperer.service`/`api.q.service`), has no
  generic proxy setting and no `--base-url`/`--endpoint` chat flag. Four independent
  blockers (base-URL, SigV4/protocol, TLS-MITM, null-tokens) documented in the
  finding.
- Empirical: two real probe turns (0.04 + 0.06 credits, both answered) under
  `cage data meter` in an **isolated** ledger recorded **0 call rows** — `cage report`
  → "No calls recorded yet." Negative is measured, not argued. Real `~/.cage` never
  named.
- Answered the open question from the code: the proxy writes call rows **directly**
  (`proxy._meter` → `metering.record_call(route="proxy")`) — **no `[sources]` entry
  needed** (that's the pull/import path). So "0 rows" is conclusive.
- Files: `cage/work/regression/2026-07-28-kiro-proxy-probe.md` (new, + README index
  row); `cage/docs/FORMULAS.md` §1.7 (new — the final credit-derived-`estimated`
  limit). **No cage source touched** (no paid calls beyond the two probe turns).
- Tests: n/a (probe + docs); no cage code changed.
- Next: docs closeout — tick phase index P0–P2.

## 2026-07-28 — Phase 1 closeout P1: §4.5 surface-collision finding RESOLVED

- Re-checked the report's §4.5 ("declared `surface` silently lost on derived-id
  collision, LOW") against fixed cage. It predates the capture-precision
  surface-restamp fix (`paths.resolve_log_sources._emit`) — a declared `surface`
  colliding with a built-in `(path, glob)` now **upgrades the built-in (declared
  wins)** instead of being dropped.
- Verified two ways, no paid calls: (1) tests green —
  `tests/test_sources.py::test_declared_surface_wins_on_builtin_collision`
  (resolution) + `::test_custom_tool_surface_restamps_alongside_agent` (import rows
  carry `surface="cli"`); (2) live reproduction — declaring `[sources.kiro]
  surface="cli"` on the shipped built-in `tokens_generated.jsonl` path resolves to
  one source with `surface='cli'` (pre-fix: `surface=''`).
- Marked §4.5 **RESOLVED (fixed 2026-07-28)** in the report; re-hashed + re-published
  append-only → `2026-07-28-validation-report-4.md` (sha `e22e6eeac5ea…`, verified
  == sidecar on all 3 copies), index row added. Original pre-fix observation retained
  as the *why*, not deleted. **No cage source touched.**
- Files: `cage-lab/golden/findings/VALIDATION-REPORT.md` (+ .sha256);
  `cage/work/regression/2026-07-28-validation-report-4.md` (+ .sha256, latest, README).
- Tests: `test_sources.py` collision + restamp tests green (3 passed).
- Next: P2 — Kiro proxy probe (last route to exact Kiro tokens).

## 2026-07-28 — Phase 1 closeout P0: validation report made un-misreadable (append-only)

- Implemented: the golden-set VALIDATION-REPORT (`cage-lab/golden/findings/`) read
  as "copilot is broken" to anyone scrolling past the post-fix divider — §1's grid
  still showed ❌, §2 the undercounted numbers, §3.1 an open HIGH finding. Added a
  one-line **BASELINE (pre-fix, superseded)** banner to §1/§2/§3.1, each linking up
  to the post-fix re-run section; rewrote the `Status:` line to "scripted cells
  CLOSED green; open = manual V6–V11 + Phase 2". **Pre-fix numbers left byte-for-byte
  unedited** — they are the evidence the fix was needed (append-only evidence artifact).
- Re-hashed + re-published append-only via `publish_report.py 2026-07-28` → new sha
  `adee806506…`, new dated copy `work/regression/2026-07-28-validation-report-3.md`
  (prior `-1`/`-2` untouched), `latest-validation-report.md{,.sha256}` refreshed,
  index row prepended. **Hash independently recomputed and verified** == sidecar on
  all three copies (lab + dated + latest).
- Files: `cage-lab/golden/findings/VALIDATION-REPORT.md` (+ .sha256);
  `cage/work/regression/2026-07-28-validation-report-3.md` (+ .sha256),
  `latest-validation-report.md` (+ .sha256), `README.md` (index row). **No cage
  source touched.**
- Tests: n/a (docs/evidence only); hash re-verification green on all 3 copies.
- Next: P1 — re-check §4.5 surface-collision finding against fixed cage.

## 2026-07-28 — model prices split into `prices.toml` (money byte-identical)

- Implemented: model prices moved out of `cage.toml` into their own
  `.cage/prices.toml` — **vendor facts move, routing decisions stay**. `prices.toml`
  holds `[prices.<provider>.<model>]`, `[credits]`, and `[meta]
  prices_version/prices_date`; `cage.toml` keeps `[alias]`, `[tools.<tool>]
  price_at`, and `[meta] cage_version/policy_version`. `[meta]` splits **per key**.
- Resolution: one point (`paths.Footprint.prices` + `resolve_prices_file`,
  `PRICES_FILENAME` the single literal), mirroring the `cage.toml` rename. Fallback:
  `prices.toml` → legacy in-`cage.toml` prices → bundled default. Both present ⇒
  `prices.toml` wins + `shadowed_prices` warning (stderr at load, `cage doctor`,
  doctor bundle). `policy.load` still returns **ONE merged dict** — no pricing
  consumer changed.
- Migration (`initcmd._migrate_prices`, project + global): scaffolds `prices.toml`
  from the bundle, writes only rows that **differ** from the current bundle as
  `# cage:custom` overrides (equal rows re-resolve from the scaffold), strips the
  price tables + price `[meta]` keys from `cage.toml` with a pointer comment.
  **Money-neutral by construction**, idempotent, fail-open.
- Writers split: `pricestoml.set_price`/`set_credit`/prices-`update_meta` → prices
  file; `set_alias`/`set_tool_route`/policy-`update_meta`/`set_wiring` → policy file.
  `pricescmd` list/sync read prices from `foot.prices`, aliases from `foot.policy`;
  meta stamping split per key. Freshness/doctor/explain readers of `prices_version`
  moved to the prices file (the mis-split-staleness hazard, fixed + tested).
- Bundle split `data/cage.toml` + `data/prices.toml` (pyproject package-data,
  zipapp-resolved); `cleanup.NEVER` protects `prices.toml`.
- **Verified numerically on the real ~40k-row global ledger**: `report`/`insights
  attrib`/`insights roi`/UNPRICED **byte-identical** before vs after (legacy
  fallback AND post-migration); 51 price tables resolve both ways; all 13 real
  model ids keep their exact/family/none `price_match` kind; `cage setup` idempotent
  (both files unchanged on re-run); a customized row survives migration.
- Files: `paths.py`, `policy.py`, `pricestoml.py`, `pricescmd.py`, `initcmd.py`,
  `adoptcmd.py`, `clicmds.py`, `doctorcmd.py`, `doctorbundle.py`, `freshness.py`,
  `explain.py`, `explain_data.py`, `cleanup.py`, `data/cage.toml` (split) +
  `data/prices.toml` (new), `pyproject.toml`; tests `test_prices_split.py` (new, 9),
  `test_prices_cli.py`, `test_output_spec.py` (P1/P3/P4 re-blessed); docs
  `FORMULAS.md`, `example/toml-config.md`, `CHANGELOG.md`, archived the
  handoff/prompt/plan trio, parked `docs/proposals/claude-md-prices-file.md`.
- Tests: **green — 855 passing** (846 pre-existing + 9 new).
- Next: Arpit reviews the parked CLAUDE.md proposal; the global-ledger question
  (plan §8) stays out of scope (ADR-level). **DO NOT COMMIT** (standing constraint).

## 2026-07-28 — P0–P2 handoff + prompt (ready to execute, unpaid)

- Implemented (docs/spec): `docs/phase1-closeout-p0p2.{handoff,prompt}.md`
  (**Model: Opus** — P2 decides whether a whole agent can ever be `measured`;
  P0 edits a hashed, published evidence artifact).
- **P0** framed as evidence integrity: the report reads "copilot is broken" past
  the divider because the re-run was prepended over an intact interim body. Rule
  written in — **label history, never rewrite it** (the pre-fix numbers are the
  evidence the fix was needed); re-hash, re-publish **append-only**, and
  **recompute the hash to verify** it against the sidecar.
- **P1** clears §4.5, whose declared-wins fix already shipped — green ⇒ mark
  RESOLVED in report + finding record (an open finding after its fix is
  doc-drift); not green ⇒ re-opened plainly, no longer LOW.
- **P2 (the valuable one)** — the proxy probe is the only remaining route from
  `estimated` to `measured` for Kiro: put cage in the request path rather than
  reading the null-filled store. Written to be answerable either way — outcome A
  documents the proxy as Kiro's recommended metering mode (`measured` on that
  path only; credits stay `estimated`); outcome B records the *specific* blocking
  reason and makes "credits-only, `estimated`, by vendor design" final in the
  field matrix + FORMULAS. **A negative is a result; do not retry until it
  passes.** Closes capture-precision #11 either way.
- Safety guardrail: STOP if P2 would require credentials, a cert override, or
  anything weakening TLS.
- Files: `docs/phase1-closeout-p0p2.handoff.md` (new),
  `docs/phase1-closeout-p0p2.prompt.md` (new), `docs/{README,WORKLOG,
  IMPLEMENTATION}.md`.
- Tests: not run (docs-only; suite last green **846**).
- Next: execute it (unpaid apart from two probe turns), then Arpit's manual
  cells; prices split can run in parallel.

## 2026-07-28 — phase1-closeout plan + the plan-index rule (CLAUDE.md)

- Implemented (docs/spec): reviewed the post-re-run VALIDATION-REPORT — scripted
  grid fully green (copilot exact, kiro honest credits, claude byte-identical,
  self-heal proven). New **`docs/phase1-closeout.plan.md`**: P0 report hygiene
  (the interim body still shows pre-fix ❌s under the green re-run header — label
  it BASELINE/superseded, never rewrite the numbers, re-hash + re-publish
  append-only) · P1 verify the shipped declared-wins fix clears §4.5 and mark it
  RESOLVED · **P2 Kiro proxy probe** — the last untried route to exact Kiro
  tokens; the one remaining item that could upgrade Kiro `estimated`→`measured`,
  and it closes capture-precision #11 (specced, never executed) · P3 manual cells
  · P4 Phase 2 sweep (Copilot blocker cleared) · P5 field matrix + wire-in +
  formal close.
- **CLAUDE.md rule (Arpit's directive, applied):** *every plan doc opens with a
  phase index* — numbered phases, one line each, with gate/status. Rationale in
  the rule: the whole shape visible before detail, staleness spottable at a
  glance. Applied to the new plan; added on contact to `prices-toml.plan.md`
  (7-step index). Existing plans gain it on contact per the fix-on-contact law.
  DOC-REGISTRY CLAUDE.md row bumped to 2026-07-28.
- Files: `CLAUDE.md`, `docs/phase1-closeout.plan.md` (new),
  `docs/prices-toml.plan.md`, `docs/{README,DOC-REGISTRY,WORKLOG,
  IMPLEMENTATION}.md`.
- Tests: not run (docs-only; suite last green **846**).
- Next: P0–P2 are cheap and unpaid — run them; P3 is Arpit's manual sweep; the
  prices split can run in parallel.

## 2026-07-28 — prices-toml handoff + prompt (ready to execute)

- Implemented (docs/spec): `docs/prices-toml.{handoff,prompt}.md` (**Model:
  Opus** — money path; a dropped price row fails *quietly*, repricing calls to
  UNPRICED or to a plausible family match).
- Both docs lead with the governing rule — **vendor facts move, routing decisions
  stay** — and name `[alias]` as staying *with its reason*, so an executor can't
  re-derive the original (wrong) "it resolves a price, so move it" conclusion.
- **Design guards written into the prompt:**
  - `policy.load` keeps returning **one merged dict** — a *file* change, not an
    API change. Explicit signal: if the executor finds itself editing a pricing
    consumer, it has gone wrong.
  - **`[meta]` splits per key**, flagged as a quiet failure mode (mis-split ⇒ a
    staleness nag silently stops firing).
- **Verification is baseline-first:** capture `report`/`attrib`/`roi`, the
  UNPRICED count and the `[prices.*]` table count on a real ledger *before* the
  change, then diff. Added a check the plan alone didn't have:
  `policy.price_match` must return the same **kind** for sampled real model ids —
  byte-identical totals wouldn't catch an `exact`→`family` degradation if two
  errors cancelled.
- **Guardrail:** a row resolving differently after the split is a **defect in the
  split**, never acceptable variance; never adjust the baseline to match.
- Files: `docs/prices-toml.handoff.md` (new), `docs/prices-toml.prompt.md` (new),
  `docs/{README,WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only; suite last green **846**).
- Next: run it, or close capture-precision with the paid 6-cell golden re-run.

## 2026-07-28 — prices-toml: three decisions settled; global-ledger question recorded

- **Decisions (Arpit):** `prices.toml` is **committed** · **`[credits]` moves,
  `[alias]` stays** · the global `~/.cage` config splits the same way.
- **The `[alias]` correction produced a better rule.** The draft moved it
  ("it resolves a price"); Arpit's call is sharper — an alias describes *your*
  environment ("this router id means that model"), not a vendor's rate card, and
  a vendor rate change never touches it, so a wholesale price sync must not wipe
  it. Plan now states the line once: **vendor facts move; routing decisions
  stay** — settling `[alias]` and `[tools.*] price_at` together.
- **Consequences recorded:** `cage prices` is a two-file writer (`set` →
  `prices.toml`; `alias`/`route-tool` → `cage.toml`); resolution is unchanged
  because `policy.price_match` walks the merged dict `policy.load` returns — the
  split is **physical, not semantic**, which is what keeps byte-identity
  achievable.
- **New plan §8 — why a global `~/.cage` exists, and the sharper question.**
  It is the sink for work outside any project (`resolve_root`:
  `--ledger`/`CAGE_BASE` → project `.cage/` → global), and pull-based capture is
  machine-wide by nature; per-project attribution needs no per-project ledger
  because `project`/`scope` are fields and `report --project` is a derived view
  (ADR 0002). **Open, deliberately out of scope:** if every import lands globally,
  a project `.cage/` may now be *config + wiring* rather than a ledger — a
  **project = config, global = ledger** model would remove a precedence tier and
  the "which ledger did this land in?" confusion behind the 2026-07-24 finding
  (5 receipts in a project ledger vs 36k calls in the global one). Needs its own
  compare doc; revisits ADR 0002.
- Files: `docs/prices-toml.plan.md`, `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only; suite last green **846**).

## 2026-07-28 — config-authority plan deleted; focused `prices-toml.plan.md` written

- Deleted `docs/config-authority.plan.md` (Arpit): its sources half had already
  shipped, so the doc would have read as pending work that was in fact done.
- New **`docs/prices-toml.plan.md`** — scoped to **model prices only**. Case made
  from the file itself: bundled `cage/data/cage.toml` is **568 lines, ~400 of them
  price rows (70%)**, so today `cage prices sync` performs text surgery inside a
  file dominated by vendor data the user never edits. After the split: sync is a
  **file replacement**, `cage.toml` drops to ~170 lines, and `cage prices sync`
  vs `cage policy sync` stop overlapping (each owns a file instead of sharing one
  `[meta]` with two version counters).
- **Moves:** `[prices.*]`, `[alias]`, `[credits]`, and **only**
  `prices_version`/`prices_date` from `[meta]`. **Stays:** everything else,
  including `cage_version`/`policy_version` and **`[tools.<tool>] price_at`** (a
  routing decision about your tool, not a vendor fact) — which makes
  **`cage prices` a two-file writer**, recorded as deliberate.
- **Both subtleties are quiet-failure risks** and are called out as such: a
  mis-split `[meta]` silently stops a staleness check firing; a dropped price row
  doesn't crash, it reprices calls to UNPRICED or to a plausible family match.
- **Acceptance is numerical:** money views byte-identical on a real ledger,
  UNPRICED count unchanged by one row, `price_match` kind unchanged on sampled
  real ids. Enabled by keeping `policy.load` returning one merged dict — a file
  change, not an API change.
- Also repaired `capture-precision.plan.md` §3.6, which a linter had reverted to
  the stale "additive only" text pointing at the deleted plan; it now records the
  as-built full removal (846 green, kill-(a)/keep-(b)).
- Files: `docs/prices-toml.plan.md` (new), `docs/config-authority.plan.md`
  (deleted), `docs/capture-precision.plan.md`, `docs/{README,WORKLOG,
  IMPLEMENTATION}.md`.
- Tests: not run (docs-only; suite last green **846**).
- Next: prices-toml handoff/prompt pair, or the paid 6-cell golden re-run first.

## 2026-07-28 — Config-authority reviewed against source: Part 2 shipped, Part 1 pending

- Reviewed the **code**, not the docs, and corrected a stale record: Directive A
  shipped as **full removal** (Arpit's choice), not the additive subset I had
  written down. Verified in source: `paths.sources_seed()` ·
  `paths.materialize_sources()` (active `# cage:sources-start/end` block) ·
  `paths.sources_drift()` in `doctor --paths` · `initcmd.sync_sources()` behind
  `cage setup --sync-sources` (regenerates only the marker region; user entries
  survive) · `resolve_log_sources` reading only `cage.toml` · loud empty-`[sources]`
  warning · harness on `tests/srcseed.py`. **846 green.**
- **kill-(a)/keep-(b) confirmed as built:** env no longer selects a path (doctor
  announces ignored home-env vars); `_expand_source` still expands `~`/`$VAR`
  *inside* a cage.toml-declared string, keeping configs portable.
- **Arpit's ask "cage.toml should have default paths on `cage setup`" is already
  implemented** — it is exactly `materialize_sources` + `sync_sources`, project
  and global, including the kiro-cli SQLite store as `format="kiro-cli"`. Reported
  rather than rebuilt.
- Docs corrected: `config-authority.plan.md` gains a STATUS banner (Part 2 SHIPPED
  / Part 1 PENDING) + an **as-built table** mapping each specified item to what
  shipped; `capture-precision.plan.md` §3.6 and its §6 question re-marked from
  "additive only" to "shipped in full".
- **New §2.4 in config-authority:** the seed is now frozen into user files at
  setup time, so its *content* is load-bearing in a way it wasn't as a runtime
  fallback. Two one-off checks recorded: every default path still correct, and
  **does the drift check actually fire** (add a seed entry → `doctor --paths`
  against an older materialized config). A mitigation that never triggers isn't one.
- **Pending after this review:** `prices.toml` split (the only open config-authority
  item) · the **paid 6-cell golden-set re-run** (needs `drive.py` updated for
  Directive A + Kiro credit checks; gated on Arpit) · manual cells V6–V11 · Phase 2.
- Files: `docs/config-authority.plan.md`, `docs/capture-precision.plan.md`,
  `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only; cage suite last green **846**).

## 2026-07-28 — Config-authority cycle specced (prices.toml split + deferred sources flip)

- Implemented (docs/spec): **`docs/config-authority.plan.md`** (new) — one cycle,
  two parts, sequenced *after* capture-precision so each change's verification is
  unambiguous.
  - **Part 1 — `.cage/prices.toml`.** Split driven by lifecycle, not tidiness:
    `cage.toml` mixes **your decisions** (budgets, tool order, human rate,
    sources — preserved across upgrades) with **the world's facts** (vendor
    rates, shipped in the bundle, wanting *wholesale replacement*). After the
    split, `cage prices sync` is a file replacement rather than text surgery
    inside a file full of user policy: policy can't be damaged by a price update,
    and a price table can't be left half-merged. Moves `[prices]`, `[alias]`,
    `[credits]`, `[meta] prices_version`; **`[tools.<tool>] price_at` stays in
    `cage.toml`** (a routing decision, not a vendor fact), making `cage prices` a
    two-file writer. Reuses the proven non-breaking pattern: one resolution point
    (`Footprint.prices`), legacy in-`cage.toml` fallback, both-present warning,
    `cage setup` migration, bundled-data split + package-data + zipapp check,
    `cleanup.NEVER`.
    **Acceptance is numerical, not structural:** on a real ledger,
    `report`/`insights attrib`/`insights roi` byte-identical before vs after and
    the UNPRICED count unchanged by one row — a silently dropped price row
    reprices calls to UNPRICED, or worse to a plausible-looking family match.
  - **Part 2 — the deferred `[sources]` exclusive-authority flip**, rule stated
    precisely: **kill (a)** env that overrides *which* path is used (a second
    decision-maker outside the config); **keep (b)** env expanded *inside* a path
    string `cage.toml` declares (the file still decides, env only parameterises —
    what keeps a config portable). Includes the ~25-file test migration from
    ambient home-env redirection to temp `cage.toml`.
- **`capture-precision` rescoped in the same pass** (§3.6, handoff DoD, prompt
  Step 4): additive parts only — active `[sources]` table, doctor drift check,
  `--sync-sources`; **resolution semantics unchanged**, out-of-scope items named
  so the executor can't drift into them. §6 env question marked RESOLVED. Reason:
  the re-run must attribute a red cell to exactly one change, and V1/V2 must stay
  byte-identical by construction.
- Files: `docs/config-authority.plan.md` (new),
  `docs/capture-precision.{plan,handoff,prompt}.md`, `docs/{README,WORKLOG,
  IMPLEMENTATION}.md`.
- Tests: not run (docs-only).
- Next: finish the capture-precision run, then spec the config-authority
  handoff/prompt pair. Open: `price_at` placement, whether `prices.toml` is
  committed (default yes), cycle order (default: prices first).

## 2026-07-28 — Step 6: Phase 1 re-run executed (failures-first) — ALL RED CELLS GREEN

- Ran the re-run with the **fixed cage** (`cage/.venv/bin/cage` = working tree, so the
  paid calls tested my code, not released 0.36.0 — verified before spending). Lab reworked
  for the new behavior (`cage-lab/golden/drive.py`): `recount_copilot` now models
  per-shutdown **deltas** independently (three-way reconcile holds at row + token level);
  kiro config-fix uses `format="kiro-cli"` + umbrella import; kiro checks 4/5/6 reflect
  credit capture (`read_ledger_credits`).
- **Failures-first, gate honored:**
  - **V3/V4 copilot → 8/8.** Fresh paid V3 run: 8/8 (recount==cage exactly). Re-importing
    the **baseline** logs with the fixed cage hits the prompt's exact numbers: **227,298**
    (V3, was 189,788) and **233,675** (V4, was 191,414); re-import idempotent (+0).
    [Gate note: the first V3 recheck showed 4/5 red *because the independent recounter
    still used last-cumulative* — a protocol fault in the check, not the fix; the token
    totals already reconciled exactly. Fixed the recounter → 8/8.]
  - **V5/V5b kiro → pass.** SQLite parser records **12 / 15 credit rows**; check 4 ✅;
    check 5 ◻ n/a (tokens null — no token total to reconcile, stated as a limit); check 2
    ◻ n/a (redacted). Exactly the planned honest outcome.
  - **V1/V2 claude → byte-identical.** 381,813 (17 rows) / 565,637 (19 rows) — nothing
    leaked into the untouched path.
- Report re-published with a "Re-run results" section, re-hashed
  (`f3c058e4…`), dated `2026-07-28-validation-report-2.md` + latest (append-only).
- **cage tree uncommitted** (per directive); cage-lab changes committed there.
- Every acceptance box in the handoff is met.

## 2026-07-28 — Directive B, self-heal proof, ADR + regression records

- **Directive B (report hashing/publish):** `cage-lab/golden/publish_report.py` — sha256
  over the report body (marker `<!-- HASH-COVERS-BELOW -->` to EOF; header excluded and
  documented in the sidecar), header prints the hash, copied into `work/regression/`
  dated + `latest-validation-report.md` + `.sha256`, index row, **append-only** (`-2`
  suffix verified). Hash reproducible (recompute == sidecar).
- **Self-heal proof (deterministic, no paid calls):** ran the fixed Copilot parser
  end-to-end on the **real** session `8073abba` — legacy row 70,071 → re-import →
  **107,581 exact** (+37,510, the exact V3 undercount) → third import **+0**. Proves V3
  goes 8/8 → **227,298** without spending on the paid re-run.
- **Records:** [ADR 0004](../docs/adr/0004-append-only-delta-rows-and-separate-by-schema.md)
  (append-only delta rows + separate-by-schema, with veto condition);
  `work/regression/2026-07-28-capture-precision-fixes.md`; proposed CLAUDE.md edits parked
  in `docs/proposals/claude-md-sources-authority.md` (**propose, don't apply**).
- **Paid re-run (Step 6):** deterministic proofs done (846 green + self-heal). The paid
  6-cell re-run needs `cage-lab/golden/drive.py` updated for Directive A + Kiro credit
  checks and real agent calls — gated on Arpit's go-ahead.
- Files (cage): `docs/adr/0004-*.md`, `work/regression/2026-07-28-*.md`,
  `docs/proposals/*.md`, `work/regression/README.md`. Files (cage-lab):
  `golden/publish_report.py`, `golden/findings/VALIDATION-REPORT.md(.sha256)`.
- Tests: **846 passing**.

## 2026-07-28 — Directive A: cage.toml is the ONLY source of log paths (§3.6)

- **Decision:** Arpit chose **full removal** (over the doctor-announced-escape-hatch
  and defer-the-flip options) after I surfaced the blast radius (25 test files + the
  lab's missing `[sources]`).
- `paths.resolve_log_sources` now reads **only** `cage.toml [sources]` — no built-in
  runtime fallback, no env consulted. The registry is a **seed** (`paths.sources_seed`)
  that `cage setup`/`initcmd` **materialize** into an active `[[sources.<name>]]` block
  (project + global `~/.cage`), including the kiro-cli SQLite store as a
  `format="kiro-cli"` custom source. Empty/absent `[sources]` captures **nothing,
  loudly** (`⚠ no [sources] …` on import; "not declared" per agent in `doctor --paths`).
- **Mandatory staleness mitigation:** `paths.sources_drift` diffs the project table vs
  the seed; `cage doctor --paths` reports drift + announces now-ignored home-env vars;
  `cage setup --sync-sources` refreshes the cage-managed marker block **preserving**
  user `[[sources.<name>]]` entries.
- **Health semantics:** an agent with no `[sources]` entry is never swept → dropped from
  capture-health (the new "disable", replacing `replace=true`+empty-paths).
- Files: `cage/paths.py` (seed/materialize/drift, resolution rewrite), `cage/initcmd.py`
  (`sync_sources`), `cage/importcmd.py` (no-sources warning, health), `cage/pathprobe.py`
  (drift/ignored-env/undeclared rendering + loads project policy), `cage/cli.py` +
  `cage/clicmds.py` (`--sync-sources`), `cage/data/cage.toml` (comment block).
- **Test harness migrated** (Arpit's mandate): `tests/srcseed.py` `mkcage()` materializes
  an env-var `[sources]` table (order-independent); ~10 pathless-sweep files migrated;
  `test_sources.py`/`test_platform_paths.py` old-contract tests rewritten to the new
  authority model; `test_zipapp`/`test_doctor_bundle` updated.
- Tests: **846 passing** (full suite). CLI smoke: setup materializes, `--sync-sources`
  idempotent (project + global), empty `[sources]` prints the loud warning.
- Next: Step 5 — hash + publish the validation report (lab-side).

## 2026-07-28 — Two smaller fixes: surface collision + shim recursion (§3.3, §3.5)

- **Surface-restamp collision (§3.5) → declared wins.** In `paths._emit`, a policy
  source whose `(path, glob)` equals a built-in's used to be dropped, silently
  discarding its declared `surface`. Now the declared value **upgrades** the colliding
  built-in (that had none) instead of vanishing — clean, append-only-safe (a resolution
  change, no row mutation). Test: `test_declared_surface_wins_on_builtin_collision`.
- **Graphify shim recursion (§3.5).** `cage/data/shims/graphify` resolved the real
  binary by stripping only its **own** dir; two stacked interceptors (fresh + stale
  `cage adopt`) resolved to *each other* → infinite recursion → hang. Now it scans PATH
  and skips **every** cage interceptor (matched by marker), refuses to fall back to the
  bare name (→ exit 127, never re-enter a shim), and adds a `CAGE_GRAPHIFY_SHIM=1`
  re-entry guard. Verified: two stacked shims + a real binary resolve to REAL with no
  hang; only-interceptors exits 127. Kept the live `cage data graphify` routing (wiring
  liveness scan green — no phantom verb from comments/echo strings).
- Files: `cage/paths.py`, `cage/data/shims/graphify`, `tests/test_sources.py`.
- Tests: **843 passing** (full suite).
- Next: Step 4 — Directive A (`cage.toml` sole path authority).

## 2026-07-28 — Kiro CLI credits parser + wiring (capture-precision §3.2–§3.4)

- **Read-only SQLite parser.** `transcript.parse_kiro_cli_credits` opens the store
  `mode=ro&immutable=1` (never writes/migrates/locks), reads only `conversations_v2`
  (never `auth_kv`) and, within each row's `value` JSON, only a **closed whitelist**
  of numeric/metadata fields — never a prompt/response body. Counts-never-content is
  hardest here (content shares the row); a test asserts no prompt/response/auth text
  reaches a row.
- **Credits are a distinct row kind, not a call.** `schema.make_credit` →
  `credits-<month>.jsonl` (own id namespace `k_cred…`, `unit="credits"`,
  `method="estimated"` — a proxy, never measured; **recorded, not priced**). A
  `tokens_in=0` call row was rejected — it would poison every average.
- **Resume without double-count.** The id folds in the turn count so a grown
  conversation appends a fresh row (append-only); `ledger.credits` collapses
  last-write-wins per session, so the grown total is never summed with its partial
  (the append-only analogue of the Copilot delta fix).
- **Import wiring:** a `[sources.<name>] format="kiro-cli"` custom source routes to
  `_ingest_credits` (separate from the call `_ingest`); default DB path resolver
  `paths.kiro_cli_db()` (`CAGE_KIRO_CLI_DB` override). Never touches call views, so
  determinism/goldens are unperturbed.
- Files: `cage/transcript.py`, `cage/schema.py` (`make_credit`+`CREDIT_FIELDS`),
  `cage/ledger.py` (`credits`), `cage/paths.py` (`kiro_cli_db*`, `_FORMAT_GLOB`),
  `cage/importcmd.py` (`_ingest_credits` + kiro-cli branch), `tests/test_transcript.py`
  (+6 tests).
- Tests: **842 passing** (full suite, no regressions; call-based views byte-identical).
- Next: Step 3 — surface-restamp collision + graphify shim recursion.

## 2026-07-28 — STEP 0 gate + Copilot delta-id fix (capture-precision §3.1)

- **STEP 0 (Kiro token probe) — DONE, gate NOT triggered.** Ran
  `kiro-cli chat --no-interactive --model claude-haiku-4.5` (explicit non-`auto`)
  from an isolated cwd, then read `data.sqlite3` read-only. Result: **every token
  field still null** (`total_tokens`/`uncached_input_tokens`/`output_tokens`/
  `cache_read_input_tokens`/`cache_write_input_tokens` = `None`); only signal is
  credits (0.0188) + `context_usage_percentage` (7.356). `telemetry.enabled` unset.
  New vs baseline: explicit model makes `model_id` a real name
  (`claude-haiku-4.5`) not `"auto"`. **Tokens not recoverable → items 2/3/5 proceed
  as specced.**
- **Copilot delta-id fix.** `transcript.parse_copilot_calls` rewritten:
  cumulative `session.shutdown` metrics now yield **per-shutdown delta rows**; id
  carries the shutdown **ordinal** (`…{i:03d}` for ord 0 — byte-identical to the
  legacy id — `…{i:03d}s{ord:03d}` after); `totalPremiumRequests` is cumulative
  too (verified 0.33→0.66 on real V3 session `8073abba`) and gets the same delta
  treatment. History self-heals: ord-0 dedupes against the legacy row, only the
  ord≥1 delta appends.
- Files: `cage/transcript.py`, `tests/test_transcript.py` (+4 tests: cumulative-sum,
  re-import-zero, **legacy self-heal**, premium-not-multi-counted).
- Tests: green — `test_transcript.py` 14/14; import/capture 63/63.
- Next: Step 2 — Kiro CLI read-only SQLite parser + counts-never-content guard.

## 2026-07-28 — Capture-precision cycle specced (plan + handoff + prompt)

- Implemented (docs/spec — build handed to Claude Code):
  `docs/capture-precision.{plan,handoff,prompt}.md` (**Model: Opus**), covering
  the full post-Phase-1 change list plus Arpit's two new directives.
- **Gate first:** Step 0 probes Kiro tokens with an explicit non-`auto` model +
  `kiro-cli settings list --all`; if tokens populate, three items (SQLite parser,
  content guard, credits row) are re-specced before any code — writing a parser to
  extract null fields is the expensive mistake to avoid.
- **Fixes:** Copilot **delta-id** (ordinal in id, **ord 0 byte-identical to the
  legacy id** so history self-heals rather than double-counts, value = per-shutdown
  delta; four tests incl. the legacy re-import case) · Kiro **read-only SQLite
  parser** + counts-never-content guard (content shares the row with metadata —
  the hardest place in cage to hold that law) · credits as a **non-call row**
  (`tokens_in=0` would poison averages), default **record don't price** ·
  surface-restamp collision made loud/winning · graphify shim recursion broken.
- **Directive A — `cage.toml` sole path authority:** `resolve_log_sources` reads
  only `cage.toml [sources]`; built-in registry demoted to a seed; `cage setup`
  materializes an active table (project + global); empty `[sources]` captures
  nothing **loudly**. Mandatory mitigation for the staleness it introduces: doctor
  **drift check** vs bundled defaults + `cage setup --sync-sources`. Env overrides
  removed from path resolution by default; survivors must be doctor-announced.
- **Directive B — reports hashed + published:** sha256 sidecar, hash in header
  (hashed byte-range documented), dated copy + `latest-` into `work/regression/`,
  index row with hash prefix, append-only.
- **Re-validation is part of the task, with exact targets:** V3/V4 exactly
  227,298 / 233,675, V5/V5b rows-or-written-limit, V1/V2 byte-identical, plus a
  non-skippable self-heal proof. "Never make a check pass by loosening it — the
  re-run exists to be able to fail."
- **Run order = FAILURES FIRST** (Arpit's follow-up; plan §4.1 + handoff DoD +
  prompt Step 6): **V3/V4 → V5/V5b → V1/V2**. Targeted cells first for the
  fastest verdict; previously-green claude last as the regression check
  (byte-identical bar). **Gated between groups** — a still-failing targeted cell
  stops the run and reports, since re-running green cells proves nothing while a
  fix is broken and every call is real spend.
- Files: `docs/capture-precision.plan.md`, `docs/capture-precision.handoff.md`,
  `docs/capture-precision.prompt.md` (all new), `docs/{README,WORKLOG,
  IMPLEMENTATION}.md`.
- Tests: not run (docs-only; cage suite last green 833).
- Next: run the capture-precision prompt (Opus). Open decisions in plan §6.

## 2026-07-28 — Phase 1 report reviewed: A/B design corrected, Kiro verbatim exception

- Reviewed `../cage-lab/golden/findings/VALIDATION-REPORT.md` (all scripted cells
  V1–V5b). Outcome: report accepted; **two plan changes + four review calls**.
- **Plan §4.1 (new) — the graphify A/B did not fire.** V2/V4 agents answered the
  architecture question without shelling out to graphify ⇒ 0 savings rows (the
  savings path itself verified correct when invoked directly:
  `raw_alternative=11,810 · actual=118 · saved=11,692`, modeled/0.6). Elevated
  from a §3.3 note to a **product-level finding**: cross-read with the 2026-07-22
  capture report ("0 real receipts / 36,451 calls"), it suggests graphify savings
  materialize only on deliberate human invocation. Phase 2 must declare which A/B
  mode it measured — agent-prompted · driver-invoked · unprompted-observed — and
  **keep reporting the unprompted zero as data**.
- **Plan §2.6a (new) — standing verbatim-capture exception for Kiro CLI.** Its
  SQLite store co-locates `auth_kv` credentials + every directory's transcript
  text with the usage metadata, so byte-exact copy is impossible; the corpus keeps
  a redacted workspace-scoped projection and marks check 2 `◻ n/a`. A future
  SQLite parser inherits the constraint: counts/ids/times only, never the `value`
  body.
- **Review calls carried into the next tasks:** (1) the suggested Copilot fix
  ("update the row") **violates append-only** — verified `call_id=
  f"c_cop{sid[:12]}{i:03d}"` (`transcript.py:387`) is session+model-index only;
  correct shape is **shutdown-ordinal in the id + store the per-shutdown delta**,
  which sums to truth and stays idempotent (`totalPremiumRequests` likely needs the
  same). (2) §4.5 (declared `surface` silently lost on derived-id collision) raised
  **LOW → MED** — silent loss of an explicit config value. (3) "Kiro tokens
  unrecoverable" not yet closed: probe an explicit non-`auto` model + `kiro-cli
  settings list --all` before concluding.
- Files: `work/cage-lab-golden-set.plan.md` (§4.1, §2.6a),
  `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: n/a (cage source untouched; suite last green 833).
- Next: Kiro token probe → `work/regression/` entries for both HIGH findings →
  Copilot delta-id fix → Phase 2. Manual cells V6–V11 pending.

## 2026-07-28 — Kiro CLI installed → resume prompt for the pending V5/V5b cells

- Implemented (docs/spec): `docs/golden-set-kiro.prompt.md` (**Opus**) — a
  **resume** prompt, deliberately not a rebuild. It reuses the existing
  `../cage-lab/golden/` driver, frozen workspace, questions and interim report,
  and runs only the two cells Phase 1 recorded as `NOT AVAILABLE`.
- Shape of the task: **discovery first** — snapshot `~/.kiro/**`, the IDE
  globalStorage path and `$TMPDIR/kiro-log/` around one real
  `kiro-cli chat --no-interactive`, cross-check with `kiro-cli chat
  --list-sessions` (sessions are per-directory, so it often points at the store),
  and quote the written shape verbatim. Then `cage import --agent kiro`, then the
  **config-only fix attempt** (`[sources.kiro] paths=… surface="cli"`, verified
  via `cage doctor --paths`): rows landing with `surface="cli"` and correct
  tokens ⇒ the gap was configuration and the stanza *is* the fix; rows that don't
  parse ⇒ the fourth-parser finding, captured and filed, **no parser written**.
- Then V5 (graphify off) and V5b (graphify on) through the same **eight checks**,
  with structurally-absent signals recorded as results rather than forced. Extra
  probe: whether `--effort low|…|max` yields a distinguishable model id (cage's
  effort-suffix family-pricing path). Explicit STOP if `kiro-cli login` is needed
  (interactive browser flow).
- Carries the standing constraints: verbatim capture, read-only sources,
  append-only corpus, gaps reported never filled, no cage source changes, no
  commits in `cage/`.
- Files: `docs/golden-set-kiro.prompt.md` (new), `docs/{README,WORKLOG,
  IMPLEMENTATION}.md`.
- Tests: not run (docs-only; cage suite last green at 833).
- Next: run it. **Separately and before Phase 2: decide the Copilot
  resumed-session undercount** (HIGH, 16.5–18%) — a full sweep would otherwise
  bake that error into every Copilot number.

## 2026-07-28 — Golden-set V5/V5b DONE: Kiro CLI logs to SQLite (4th-parser finding)

- Implemented (cage-lab only; **cage tree untouched**): `kiro-cli` 2.14.2 was
  installed, so V5/V5b were run for real (they were `NOT AVAILABLE` before). Added
  a Kiro-CLI capture path to `drive.py` — a **PII-safe SQLite extractor**, not a
  cage parser: `extract_kiro_cli` (read-only, workspace-scoped, redacted),
  `recount_kiro_cli`, `run_kiro`/`run_cell_kiro`, `--recheck` guard. Leak-tested:
  no code/content/auth in the committed extraction.
- **⚠ CAGE FINDING (HIGH): Kiro CLI logs to a SQLite DB cage cannot read.** Store =
  `~/Library/Application Support/kiro-cli/data.sqlite3`, table `conversations_v2`
  keyed by cwd; `value` JSON carries `conversation_id`, ms `created_at/updated_at`,
  `model_info.model_id="auto"`, and per-turn `request_metadata` with a full token
  schema (`total_tokens`/`uncached_input_tokens`/`output_tokens`/`cache_*`) that is
  **null on every turn incl. the large Q2** — usage is only **credits +
  `context_usage_percentage`**. `cage import --agent kiro` reads only the IDE
  `tokens_generated.jsonl`; the CLI store is invisible. Config-fix
  (`[sources.kiro] paths=[…sqlite] surface="cli"`) → **`imported 0 call(s)`**
  (`doctor --paths`: 0 parseable) — `[sources]` reuses a jsonl parser, so **config
  is NOT enough; a 4th (SQLite) parser is required.** `--effort high` did not
  surface off `model_id="auto"`.
- **⚠ FINDING (capture-architecture):** the DB co-locates an `auth_kv` credentials
  table + all-directory transcript text with the metadata → **not verbatim-
  capturable**; a cage SQLite parser must read counts/ids/times only, never the
  `value` body (counts-never-content is *harder* here). V5/V5b capture is a
  redacted projection — the one documented deviation from the golden verbatim rule.
- **Field matrix (kiro/cli):** session id ✅ (`conversation_id`), timestamps ✅
  (ms — a real gap_ms source), token counts ❌ (null), model ⚠ `"auto"`, usage =
  credits + ctx%. The CLI store is the **inverse** of the IDE store (which has
  counts but no session/timestamps) — neither gives cage a token count with a
  session boundary today.
- Checks per cell: 1✅ · 2 ◻ n/a (redacted) · 3✅ · **4❌/5❌** (0 cage rows from the
  store — the finding) · 6✅ · 7✅ · 8✅. V5 = 5 turns/0.197 credits; V5b = 7/0.2368;
  0 graphify savings rows (kiro didn't shell out either).
- Files (cage-lab): `golden/drive.py`, `golden/findings/VALIDATION-REPORT.md` (§4
  rewritten, grid + field-matrix updated), `golden/captures/*-kiro-cli-{off,on}/`.
  In cage: this entry only.
- Tests: cage suite not run (no cage code changed). Harness: `--list` zero-call ✅;
  extractor leak-test ✅; `~/.cage` untouched (all imports `--ledger` scratch).
- Next: **STOP** — all scripted cells done. Manual VS Code/IDE cells (V6–V11) await
  Arpit. Two Phase-2 gates now open: Copilot undercount + Kiro SQLite 4th parser —
  both merit `work/regression/` entries.

## 2026-07-28 — Golden-set Phase 1 EXECUTED: scripted cells done, 2 cage findings (cage-lab)

- Implemented (in `../cage-lab/golden/`, committed there — **cage tree untouched**):
  the full Phase-1 harness + the scripted validation cells. `drive.py` (stdlib-only,
  never imports cage; drives the installed `cage` + agent CLIs as subprocesses):
  per-question snapshot → settle-and-retry → diff → verbatim copy (sha both sides) →
  import into a scratch `--ledger`/`CAGE_BASE` (real `~/.cage` never named) →
  `manifest.json` + `transcript-map.json` + the **eight checks** incl. three-way
  reconciliation (log recount · cage ledger · hand count). Frozen `workspace/` toy
  package incl. a 47 KB `big_module.py` (Q2 cache-creation input); `questions/core.toml`
  (Q1/Q2/Q3) + `graphify.toml` A/B; `--list` runs with zero agent calls; `--recheck`
  recomputes checks with no re-calls; `--manual-capture --phase pre|post` verified.
- **Scripted grid:** V1/V2 **claude CLI** ±graphify — **all 8 checks green**, full
  token reconciliation (17/19 rows). V3/V4 **copilot CLI** ±graphify — check 5 **red**
  (a real finding, not a protocol bug). V5/V5b **kiro** — `NOT AVAILABLE`
  (`kiro-cli` not installed here; only Kiro IDE 0.12.333).
- **⚠ CAGE FINDING (HIGH):** Copilot `--continue` writes a **2nd cumulative**
  `session.shutdown`; `parse_copilot_calls`' session-id-derived idempotent id keeps
  the **first** and dedup-drops the second → **resumed sessions undercounted**
  (V3 189,788 vs true 227,298 = **16.5%**; V4 = 18.1%). Affects any multi-shutdown
  Copilot session (scripted resume AND VS Code chats spanning restarts). Warrants a
  `work/regression/` entry + a cage fix (update-to-last-cumulative) before a full
  sweep leans on Copilot numbers. **Filed, not patched.**
- **⚠ FINDING (MED):** stacked graphify shims recurse → hang — the fresh
  `workspace/bin/graphify` (`cage setup` → `cage data graphify`) + a stale
  `anton/bin/graphify` (old `cage adopt` → the removed `cage graphify` verb) resolve
  to each other. A dead-verb wiring-liveness artifact; `drive.py` drops it from PATH
  (safety net, not a cage fix).
- Graphify savings path **validated directly** (`explain Transformer00` → `saved
  11,692 tokens`, `method="modeled"`), but V2/V4 produced **0 savings rows** — the
  agents don't shell to graphify for a 3-sentence answer, so the A/B is
  agent-behavior-dependent (Phase 2 must force the graphify call). v0.36
  `[sources.kiro] surface="cli"` restamp confirmed on real token-log content
  (distinct rows → `surface=cli`); nuance filed: it's lost when rows collide by id
  with a built-in source.
- Files (cage-lab only): `golden/{drive.py,README.md,questions/*,manual/*,findings/VALIDATION-REPORT.md,workspace/**,captures/**}`.
  In cage: this IMPLEMENTATION.md entry only (docs).
- Tests: cage suite **not run** (no cage code changed). Harness self-check: `--list`
  zero-call ✅; eight checks evaluated per cell (reds are reported truthfully).
- Next: **STOP** — hand Arpit `manual/vscode-checklist.md` (V6–V11) + the interim
  report. Phase 2 (18-q sweep) and the manual cells await his explicit go. Consider a
  `work/regression/` entry for the Copilot undercount.

## 2026-07-28 — Golden-set pair rewritten to Phase 1 (off hold, runnable)

- Implemented (docs/spec): `docs/golden-set.{handoff,prompt}.md` fully replaced —
  the superseded ON-HOLD 4-question single-agent pilot is gone. Both now specify
  **Phase 1: the 12-cell validation matrix** (claude/copilot/kiro CLI ±graphify
  scripted; claude/copilot VS Code + kiro IDE ±graphify manual), 2–4 questions per
  cell, the **eight** checks (seven + config provenance), output
  `findings/VALIDATION-REPORT.md`.
- Prompt structure: **two hard stops** — after the scripted cells (interim report
  + hand over `manual/vscode-checklist.md`; extensions can't be driven
  headlessly), and after the validation report (Phase 2 needs Arpit's go). Setup
  requires graphify wired **and verified live** (`cage doctor`; presence ≠
  liveness — F1's root cause) plus a recorded **config baseline** (`cage.toml`;
  never hard-code `policy.toml`).
- V5 (Kiro CLI) written as the highest-value cell: discovery → record shape →
  `cage import --agent kiro` → **attempt the config-only fix in place**
  (`[sources.kiro] paths=… surface="cli"`, verified via `cage doctor --paths`) →
  fourth-parser finding filed if rows don't parse (**no parser written here**).
- The report must explicitly answer: where Kiro CLI logs (config sufficient?) ·
  whether the graphify PATH interceptor fires under the VS Code extensions ·
  whether the Claude CLI and VS Code stores are distinguishable (V1 vs V6).
- Files: `docs/golden-set.handoff.md`, `docs/golden-set.prompt.md`,
  `docs/README.md`, `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only; cage code untouched — suite last green at 833).
- Next: run `docs/golden-set.prompt.md` (Opus); Arpit performs the manual cells;
  tree stays uncommitted.

## 2026-07-27 — Golden-set plan updated for the shipped config changes (docs only)

- Implemented (docs/spec): `work/cage-lab-golden-set.plan.md` reconciled with the
  two config tasks that just went green (`surface` key; `cage.toml` rename).
  - **§2.6 Kiro gap re-scored:** suspicion 2 (hardcoded `surface="ide"`) is
    **fixed** — a source can declare `surface = "cli"`; suspicion 1 (unknown
    path) is config-fixable once the path is known; **suspicion 3 (different
    format ⇒ a 4th parser) is the only open one**, and is exactly what Phase 1
    discovery decides.
  - **V5 task list** gained step 5 (**attempt the config-only fix on the spot**:
    write `[sources.kiro] paths=… surface="cli"`, re-import, verify via
    `cage doctor --paths`; a working stanza goes in the report as *the fix*) and
    step 6 (rows that don't parse ⇒ the fourth-parser finding — capture the shape,
    file it, **don't** write a parser inside the golden-set task).
  - **New §2.7** — what v0.36 changed under this plan, with two consequences:
    config stanzas go in `cage.toml` (the driver must not hard-code
    `policy.toml`), and **every run records which config file was active** (new
    check #8 + a manifest field), because a capture whose numbers silently depend
    on a leftover legacy config is a trap.
  - Phase 1 setup now records a **config baseline**; §6 field matrix gains two
    provenance rows (*surface source*: parser-derived vs declared; *config file*
    per run).
  - Swept stale `policy.toml` references in `cage-lab-plan.md` §4 and
    `cage-lab-setup.prompt.md` (the bundled price table the lab reads as data).
- Files: `work/cage-lab-golden-set.plan.md`, `work/cage-lab-plan.md`,
  `work/cage-lab-setup.prompt.md`, `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only; cage code untouched — suite last green at 833).
- Next: rewrite the golden-set handoff/prompt pair to the phased plan (still
  ⏸ ON HOLD), then run Phase 1. Tree stays uncommitted.

## 2026-07-27 — Task B GREEN: `policy.toml` → `cage.toml` (read fallback + migration)

- Implemented (Opus, same prompt): the config filename is now `cage.toml`, with a
  never-breaking `policy.toml` read fallback.
  - **One resolution point** — `paths.Footprint.policy` resolves `cage.toml` if
    present → else `policy.toml` (fallback; releases ≤ v0.35 on PyPI wrote it) →
    else `cage.toml` (the name a fresh scaffold writes). New sibling
    `Footprint.shadowed_config` names the legacy leftover when both files coexist
    (`None` otherwise). Writers (`pricestoml`, `policysync`) already routed through
    `foot.policy`, so they followed the rename with no second literal.
  - **Bundled file** `cage/data/policy.toml` → `cage/data/cage.toml` (`git mv`);
    the six literals updated (`policy.py` ×2, `doctorbundle.py`, `pyproject.toml`
    package-data, `cleanup.NEVER` now protects **both** names, `explain_data.py`).
    `MANIFEST.in`'s `recursive-include cage/data *` still covers it; the **zipapp**
    (importlib.resources) still finds it (test_zipapp green).
  - **Migration** — `cage setup` renames a lone legacy `policy.toml` → `cage.toml`
    (`initcmd._migrate_config`, idempotent, non-destructive when both exist,
    fail-open); the CLI prints a one-line notice on every setup path.
  - **Both-present honesty** — `cage doctor` names the active config + flags the
    ignored leftover (a WARN row); a one-line stderr warning fires at the
    `clicmds._policy` load chokepoint (stdout stays byte-identical).
- Files: `cage/paths.py`, `cage/policy.py`, `cage/initcmd.py`, `cage/adoptcmd.py`,
  `cage/clicmds.py`, `cage/doctorcmd.py`, `cage/doctorbundle.py`, `cage/cleanup.py`,
  `cage/policysync.py`, `cage/explain_data.py`, `cage/data/cage.toml` (renamed),
  `pyproject.toml`, `tests/test_config_rename.py` (new, +9), `tests/test_sources.py`,
  `tests/{test_bundled_data,test_zipapp,test_pricestoml,test_policysync,`
  `test_prices_cli,test_receipt_pricing}.py`, goldens P1/P3a/P3b (filename only).
- Tests: **green** — `pytest -q` 833 passed. Scratch-repo smoke a/b/c confirmed at
  the CLI (fresh scaffold → cage.toml; legacy policy.toml reads via fallback +
  migrates; both-present warns on stderr, cage.toml wins). Goldens re-blessed **only**
  where the filename genuinely renders.
- Next: docs sweep (CHANGELOG, README, example, FORMULAS, `cage query`), propose
  CLAUDE.md edits. No commits — tree stays dirty per standing directive.

## 2026-07-27 — Task A GREEN: sources `surface` key (configurable + discoverable)

- Implemented (Opus, executing `docs/config-surfaces-and-rename.prompt.md`):
  - `LogSource` gained a trailing `surface: str = ""` field (default keeps every
    positional construction byte-identical). `resolve_log_sources` validates a
    `surface` key against the closed set (`cli|vscode|ide|""`, the same enum
    `schema.make_call` enforces) in **both** schema shapes — table-level
    (`[sources.<x>] surface = …`) and per-entry (`[[sources.<x>]] surface = …`) —
    via a new `_resolve_surface` helper threaded through `_emit`/`_dict_paths`/
    `_list_paths`. An out-of-set value → a `problems` entry, never a raise (the
    sweep stays fail-open); absent ⇒ `""` (byte-identical).
  - `importcmd._surface_restamp(parse, surface)` wraps a parser to restamp each
    row's `surface` **only when declared** — mirroring the custom-tool `agent`
    restamp. Applied in all three built-in importers (`import_claude/copilot/
    kiro`) and layered onto the custom-tool restamp. Fixes the motivating gap: a
    non-IDE Kiro store no longer inherits the parser's hardcoded `surface="ide"`.
  - Discoverability: `cage doctor --paths` now shows a `surface=<declared|parser>`
    column per source (`pathprobe`). `cage query sources` documents the key.
- Files: `cage/paths.py`, `cage/importcmd.py`, `cage/pathprobe.py`,
  `cage/explain_data.py`, `tests/test_sources.py` (+6 tests).
- Tests: **green** — `pytest -q` 824 passed (was 818; +6 surface tests). Byte-
  identity for undeclared surface asserted.
- Next: Task B — rename `policy.toml` → `cage.toml` with a read fallback + migration.

## 2026-07-25 — Config pair specced: sources `surface` key + `policy.toml` → `cage.toml`

- Implemented (docs/spec — build handed to Claude Code):
  `docs/config-surfaces-and-rename.{handoff,prompt}.md` (**Model: Opus**).
  - **A — sources:** `[sources]` path config already ships
    (`paths.resolve_log_sources`: env > policy > built-in, `paths`/`glob`/
    `replace`, custom tools via `format`). The real gap is that `LogSource`
    carries no `surface` while `transcript.parse_kiro_calls` hardcodes
    `surface="ide"` — a non-IDE Kiro store would be silently mislabelled. Spec:
    a validated `surface` key in both schema shapes, `LogSource.surface`,
    restamp **only when declared** (mirroring the existing custom-tool `agent`
    restamp), and an effective-sources listing (agent · fmt · surface · path ·
    glob · provenance · found/missing) — default via `cage doctor --paths`
    rather than a new top-level verb.
  - **B — rename:** `cage.toml` with a **`policy.toml` read fallback** (PyPI
    users have the old name — never a breaking rename), both-present ⇒
    `cage.toml` wins + warning, `cage setup` migration, writers follow the
    resolved name, `cleanup.NEVER` protects both, zipapp bundled-data path
    re-verified. Filename sized precisely: **6 literals** (`paths.py:748`,
    `policy.py:23,337`, `doctorbundle.py:81`, `cleanup.py` NEVER,
    `explain_data.py:418`, `pyproject.toml:52`).
  - **Out of scope, stated hard:** no Kiro-CLI source path or parser — the format
    is unknown until golden-set Phase 1 discovery; guessing repeats the `kind:0`
    mistake. Config supplies the knob; discovery supplies the shape.
- Files: `docs/config-surfaces-and-rename.handoff.md` (new),
  `docs/config-surfaces-and-rename.prompt.md` (new), `docs/README.md`,
  `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only milestone).
- Next: run the config prompt (Opus); tree stays uncommitted.

## 2026-07-25 — Kiro CLI is real: probable cage capture gap recorded (docs only)

- Verified from the Kiro CLI docs (not assumed): `kiro-cli` exists — non-interactive
  `kiro-cli chat --no-interactive "<q>"`, per-directory sessions auto-saved every
  turn with UUID ids, `--effort low|medium|high|xhigh|max`, storage under
  `KIRO_HOME` (default `~/.kiro`) which explicitly includes **sessions**.
- **Suspected cage gaps (to confirm/refute in golden-set Phase 1, each a finding
  if true):**
  1. `paths.agent_log_sources()` knows only the IDE token log
     (`kiro.kiroagent/dev_data/tokens_generated.jsonl`) — **Kiro CLI usage may be
     entirely uncaptured.**
  2. `transcript.parse_kiro_calls` hardcodes `surface="ide"` — a CLI-originated
     row would be mislabelled.
  3. The CLI session store may be richer than the IDE log (real session ids +
     per-turn saves), potentially fixing kiro's missing session boundary /
     timestamps / model.
- Docs updated: golden-set plan **§2.6** (evidence + the three suspicions + an
  ordered discovery task list), V5 promoted to a real cell + V5b (graphify on) →
  12-cell matrix, per-agent non-interactive driving-command table (with a
  "confirm flags from `--help` at run time" rule); `cage-lab-plan.md` M4c
  corrected (it asserted no Kiro CLI surface exists).
- Files: `work/cage-lab-golden-set.plan.md`, `work/cage-lab-plan.md`,
  `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only; **no cage code changed** — the gap is recorded as a
  finding to verify, not patched).
- Next: confirm which CLIs are installed on the machine, then Phase 1.

## 2026-07-25 — Golden set re-phased: 11-cell validation gate; execution pair ON HOLD

- Implemented (docs/spec — supersedes the pilot design below): plan §2.5 replaced
  with **three validatable phases**.
  - **Phase 1 (gating)** — setup + capture validation across **11 cells**:
    V1–V5 scripted (claude CLI ±graphify · copilot CLI ±graphify · kiro CLI ⇒
    expected `NOT AVAILABLE`), V6–V11 manual (claude VS Code · copilot VS Code ·
    kiro IDE, each ±graphify). 2–4 questions per cell (Q1 · Q2→Q3 cache pair ·
    one §4 architecture question on graphify-ON cells) ≈ 30–40 real calls. Setup
    now explicitly includes **wiring the graphify interceptor and verifying it
    live** via `cage doctor` (presence ≠ liveness — the F1 root cause). The same
    seven checks apply per cell; output `findings/VALIDATION-REPORT.md`
    (11 × 7 grid · three-way numbers · "what we learned").
  - Two unknowns Phase 1 must answer: whether the graphify PATH interceptor fires
    under the VS Code extensions at all, and whether the Claude CLI vs VS Code
    stores are distinguishable (V1 vs V6 — the cleanest test of the `surface=""`
    honest blank).
  - **Phase 2** scripted 18-question CLI sweep + graphify A/B · **Phase 3** manual
    VS Code/IDE sweep · **Phase 4** field matrix + wire into `inputs.toml`.
  - §8 build order restructured accordingly.
- `docs/golden-set.{handoff,prompt}.md` marked ⏸ **ON HOLD** (banner at the top of
  each): they describe the superseded 4-question pilot and must be rewritten to
  the phased plan before execution. Docs index updated.
- Files: `work/cage-lab-golden-set.plan.md`, `docs/golden-set.{handoff,prompt}.md`,
  `docs/README.md`, `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only milestone).
- Next: Arpit signs off the phased plan → rewrite the pair to Phase 1 → execute.

## 2026-07-25 — Golden set: pilot-first gate + execution pair (SUPERSEDED same day)

- Implemented (docs/spec): plan §2.5 **Phase 0 — the PILOT**, gating all bulk
  capture. Scope: claude CLI, four questions (Q1/Q2/Q3/Q6 with a real 90s pause),
  ~5 min. Seven checks (snapshot-diff exactness · faithful copy + unchanged
  source sha · question→bytes mapping · complete hand-counted import ·
  three-way value reconciliation · derived signals present · nothing written
  outside `captures/`). Output `PILOT-REPORT.md`; its "what we learned" list of
  missing/unexpected fields is the real deliverable. **Red pilot blocks Phase 1.**
  Build order restructured: Phase 0 pilot → Phase 1 sweep + graphify A/B +
  manual → Phase 2 field matrix + wire into the lab.
- New pair `docs/golden-set.{handoff,prompt}.md` (**Model: Opus** — capture
  protocol is diagnosis work; a flaw frozen into the corpus poisons everything
  downstream). Prompt leads with the hard gate (build → run pilot → report →
  STOP), flags the late-write/log-buffering risk (settle-and-retry; report if it
  exceeds that), and forbids making a check pass by loosening it.
  Indexed in `docs/README.md` as the **first** pair to run — it produces the
  inputs the M/G matrix consumes.
- Files: `work/cage-lab-golden-set.plan.md`, `docs/golden-set.handoff.md` (new),
  `docs/golden-set.prompt.md` (new), `docs/README.md`,
  `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only milestone).
- Next: Arpit runs the golden-set prompt (Opus) → reviews `PILOT-REPORT.md` →
  answers the three open questions → Phase 1.

## 2026-07-25 — Golden-set plan: drive the real agents, capture, build the field matrix

- Implemented (docs/spec): `work/cage-lab-golden-set.plan.md` — a driven capture
  corpus for cage-lab. `golden/drive.py` runs the **real** Claude/Copilot/Kiro
  CLIs against a curated question set in a frozen scratch workspace, snapshots the
  agent log dir before/after, copies new log files **verbatim** (no stripping —
  content-safe because we author the prompts), imports them into a scratch ledger,
  and writes `manifest.json` + `transcript-map.json` (question id → session id →
  log lines → ledger row).
  - **18-question core set** covering every capture dimension cage claims:
    minimal floor, cache creation + read, long output, tool edits, a real 90s gap
    and a real over-idle-cap gap, session title + a genuinely untitled session,
    model switch, router-alias UNPRICED, premium request, refusal, a **real
    mid-stream interrupt** (produces an authentic truncated tail), parallel
    sessions, a second project, effort tiers, rapid burst.
  - **Graphify A/B**: identical questions run with and without the interceptor, so
    the receipt's `saved` is validated against a measured A−B token difference —
    a disagreement there is a top-severity finding.
  - **Manual checklist** for Copilot Chat / Kiro IDE / Claude Code extension
    (can't be driven headlessly), with pre/post capture still mechanical
    (`drive.py --manual-capture --phase pre|post`) and a per-run record template.
  - **Deliverable**: `findings/field-matrix.md` — evidence-backed agent × surface ×
    field truth table; decides what cage can honestly build and confirms/refutes
    each honest blank (notably whether the Claude CLI and VS Code stores are
    distinguishable at all).
  - Feeds the lab: golden captures become the primary `inputs.toml` entries, and
    Q14/Q9/Q15 replace three cases currently reported `NOT COVERED`.
- Summarized into `docs/PLAN.md` §11; indexed in `docs/README.md`.
- Files: `work/cage-lab-golden-set.plan.md` (new), `docs/PLAN.md`,
  `docs/README.md`, `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only milestone).
- Next: Arpit answers §9's open questions (run cost, refresh cadence, workspace
  location); then the golden-set handoff/prompt pair — sequenced **before** the
  lab matrix, since it produces the lab's inputs.

## 2026-07-25 — cage-lab: ZERO mock data (final) — real files, in place, uncopied

- Implemented (plan §2.1 rewritten — Arpit: "not at all any mock data, we use the
  files as is"). Supersedes the two entries below, which still permitted copies
  and two synthetic artifacts:
  - **No `fixtures/` directory, no copies, no edits.** Scenarios run
    `cage import --path <real file>`; auto-discovery scenarios get **read-only
    symlinks** into the scratch `$HOME` (same inode). `inputs.toml` (scenario →
    real path) is the only input config; `lab inputs --list` prints the mapping.
  - **Untouched-source proof:** sha256 before/after each run must match; a
    write-mode open under `samples/` or a live agent log is an assertion failure.
  - **Real graphify only** (fake binary forbidden; absent ⇒ `NOT COVERED`);
    **no manufactured edge cases** (truncated-tail / untitled VS Code session
    used only if genuinely present, else `NOT COVERED`); any cell without real
    data prints `NO REAL DATA — cell not covered`.
  - Eyeball header: ORIGINAL (real path · "read in place, never modified" ·
    before/after sha) → IMPORTED (exact command) → LEDGER → MANIFEST →
    REFERENCE; `lab source <id> [--open]` jumps straight there.
- Files: `work/cage-lab-plan.md`, `work/cage-lab-setup.{handoff,prompt}.md`,
  `docs/PLAN.md` (§11 laws), `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only milestone).
- Next: execute the cage-lab setup prompt (Opus, both siblings).

## 2026-07-25 — cage-lab: synthetic data deleted, real captures only (SUPERSEDED same day)

- Implemented (plan §2.1 rewritten — Arpit: "delete the fake data, pull in the
  actual data"): **no synthetic fixtures, no authored numbers.** The sanitized
  samples already carry real token counts (content-stripped only), so fixtures
  are now **verbatim copies** of `samples/agent-artifacts/*/logs/real*/`,
  sha256-verified against source by `lab setup`. References are the lab's own
  parser's recount of those same real files — independence comes from *who
  computes*, not from fake inputs.
- New `python -m lab capture-fixtures`: pull fresh real sessions from live agent
  logs (`~/.claude/projects/**`, `~/.copilot/session-state/**`, VS Code
  `chatSessions/**`, kiro `tokens_generated.jsonl`), content-strip verified by a
  grep gate, provenance (source path, date, sha) recorded — used for any case the
  sample set lacks (e.g. an untitled Copilot VS Code session).
- Uncovered matrix cells print `NO REAL DATA — cell not covered` and are listed
  in the run summary — a gap is reported, never faked. Exactly two artifacts stay
  non-real and self-label `SYNTHETIC`: the fake graphify binary and the
  mechanically truncated real file.
- Eyeball surface now leads with **ORIGINAL** (real capture path + provenance) and
  FIXTURE (copy + sha match); new `python -m lab source <id> [--open]` prints or
  opens just those paths. The mental-math fixture rule is dropped (real numbers);
  replaced by "show every addend with its source line + a running sum".
- Files: `work/cage-lab-plan.md`, `work/cage-lab-setup.{handoff,prompt}.md`,
  `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only milestone).
- Next: execute the cage-lab setup prompt (Opus, both siblings).

## 2026-07-25 — cage-lab fixture provenance: real shapes, authored numbers (SUPERSEDED same day)

- Implemented (plan §2.1, new — triggered by Arpit's "is cage-lab data fake?"):
  fixtures must be **reduced from the sanitized real captures** in
  `samples/agent-artifacts/*/logs/real*/`, never invented. Rules: trim whole
  records to ≤ ~12; rewrite **only numeric leaves** (tokens/cache/premium) to
  mental-math values; never add/remove/rename a key; record per-fixture
  provenance; **shape-drift guard** asserts fixture key-set ⊆ source sample
  key-set. Labelled exceptions: truncated-tail file, untitled Copilot VS Code
  session (~38% of real sessions), graphify fakes.
  Rationale recorded: an invented shape yields a reference derived from the same
  wrong file → green test, zero proof (the `kind:0` near-miss). Numbers stay
  authored deliberately — that independence is what makes the check meaningful;
  the L-labs keep one foot in the unmodified real ledger.
- Propagated to `cage-lab-setup.handoff.md` (DoD boxes) and
  `cage-lab-setup.prompt.md` (build step + a STOP guardrail: no real capture to
  reduce from ⇒ ask, never author a plausible structure).
- Files: `work/cage-lab-plan.md`, `work/cage-lab-setup.{handoff,prompt}.md`,
  `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only milestone).
- Next: execute the cage-lab setup prompt (Opus, both siblings).

## 2026-07-25 — FORMULAS.md + INTERVIEW reframed as the exit interview

- Implemented (docs):
  - **`docs/FORMULAS.md` (new)** — every computed number in cage, extracted from
    source: per-call cost + the exact/alias/family/self/none match ladder ·
    input-only cost · budget · forecast · drift · quality-adjusted cost · saved +
    the unit dispatch · the call-less receipt pricing ladder · marginal
    attribution · the 2ⁿ matrix · ROI/recommend · verdict composition · human cost
    + confidence ladder · derived attention (capped gap sum) · time saved ·
    estimate band · calibration hit-rate · compare delta · study pairing · task
    correlation · token heuristic · trend · window parsing · ledger warn bytes.
    Each carries formula + code link + **method tag** + knobs. Also documents the
    non-formula semantics that change totals (id-deduped `receipts()` union,
    month partitioning, derive-time repricing) and the contract/policy/constants
    three-layer split.
  - **INTERVIEW.md reframed** as the exit interview (outgoing maintainer-model →
    every future one), with four standing sections; CLAUDE.md updated to define
    it that way and to require continuous upkeep (*any session can be the last
    before a model switch*). Added the missing *in-flight + next step* and
    *standing constraints* sections, plus two scar-tissue lessons (verify log
    shapes against real data and sweep downstream docs on a spec correction; a
    doc rule that fights the workflow gets broken silently — fix the rule).
  - CLAUDE.md also now lists FORMULAS.md in the maintained set with its trigger;
    DOC-REGISTRY + docs index updated for both.
- Files: `CLAUDE.md`, `docs/FORMULAS.md` (new),
  `docs/{INTERVIEW,DOC-REGISTRY,README,WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only milestone). FORMULAS content cross-read against
  source; next verification pass should diff it against
  `cage query --list --kind calculation`.
- Next: execute `work/cage-lab-setup.prompt.md` (Opus, both siblings).

## 2026-07-25 — cage-lab COMPLETE: 16/16 matrix green, eyeball + playground + track2, baseline published

- Implemented (in `../cage-lab`, committed there; cage tree stays uncommitted):
  - **Runner** (stdlib, zero `import cage`): `plant` (hermetic scratch HOME via
    cage's env overrides CLAUDE_CONFIG_DIR/COPILOT_HOME/CAGE_VSCODE_USER/
    KIRO_DATA_DIR), `reference` (independent 2nd parser), `pricing` (bundled
    policy.toml read as data, replicates `call_cost_usd`), `verify` (reads-twice
    determinism), `run`/`graphifyrun` (orchestrators), `eyeball`, `playground`,
    `track2`, `publish`.
  - **Matrix — all 16 green** (`lab run --all` exit 0, green TWICE byte-identical):
    M1–M6 incl. the three honest cells (claude shared-store `surface=""`, kiro
    no-CLI M4c, kiro `ide`-only), G1–G5 (graphify saving raw2000−actual100=1900;
    G5 native-shim dedupe DEFERS to the child receipt — `linked-receipt-skipped`
    asserted), MIG (migrate byte-identical receipts.jsonl + idempotent 2nd apply).
    Three-way auto-verify per scenario (lab recount · cage report/CSV/rollup
    cross-check · lab-priced USD), all reconciled to a pre-authored `reference/`.
  - **Eyeball surface** (`runs/<id>/eyeball.md` + `runs/EYEBALL-INDEX.md`,
    printed last): per-metric derivation table + cited source lines inline +
    trimmed ledger rows + paste-ready side-by-side command. M2 and G5 line-checked
    by hand. **Playground** (`lab playground`): persistent sandbox, own venv +
    planted HOME + fake graphify + `cage setup --all` + cheat sheet; runner
    provably never resolves under `playground/` (guard + disjoint-trees asserted).
  - **Track 2**: `lab regression` (R2/R4/R9/R11/R12 hermetic, all green) +
    `lab labs` (L1/L2/L4/L5 read-only on the real ledger — surfaced live findings:
    39,020 real calls across 4 agents, 0 savings receipts, 0% manifest coverage,
    L4 flagged upper-bound since lab pricing is exact-match not cage's family).
  - **Baseline published** into `work/regression/2026-07-25-cage-lab-baseline.{md,json}`
    + `latest-*` + README index row.
- **FINDING (spec-correction, NOT a cage bug):** `cage-lab-plan.md` M3/M5b call
  kiro `agent` UNPRICED; the shipped bundle **prices** it via `[prices.kiro.agent]`
  (sonnet 3/15/0.3) by design. cage is correct — the plan line is stale. Lab
  references corrected to $0.0201 for the kiro fixture. **Recommend updating
  `work/cage-lab-plan.md` M3/M5b + `docs/PLAN.md` §11 to drop the "kiro UNPRICED"
  claim.**
- Files (cage side): `docs/IMPLEMENTATION.md`, `work/regression/*` (append-only,
  uncommitted).
- Tests: `lab run --all` 16/16 green twice byte-identical; `lab regression` green.
- Next: Arpit review; fold the kiro-pricing spec correction into the plan; run
  cage-lab as the standing black-box gate before the next release.

## 2026-07-25 — cage-lab MILESTONE 2: fixtures + references authored (before cage runs)

- Implemented (in `../cage-lab`, committed there):
  - 11 hand-countable fixtures: claude cli (summary + gap_ms human turn + no-usage
    skip + truncated tail) & vscode (no-summary ⇒ cwd-basename name) sharing one
    store; copilot cli (2-model session.shutdown, premium=2 on row0, cacheWrite
    ignored) & vscode (titled via kind:1 customTitle patch + untitled ⇒ "");
    kiro flat ide log (volatile ts); fake-graphify (400-char answer citing two
    4000-char sources ⇒ raw 2000 − actual 100 = saved 1900) + native-shim
    self-metering variant + legacy-receipts seed (r_leg1 500 + r_leg2 300 = 800).
  - 16 `reference/` files (M1–M6, M4c honest-refusal .md, G1–G5, MIG) with per-row
    derivations, expected call_ids (uuid[:15] / sha1 composites, computed
    independently), USD (from the bundled 5/25/.50 · 3/15/.30 · .25/2/.025 rows via
    the `full_in=tokens_in−cached_in` formula — cache_write billed at input, not
    separately), manifest names/session counts, UNPRICED flags, and volatile-field
    lists. Every number hand-derived, never from cage output.
- Files (cage side): `docs/IMPLEMENTATION.md` (this entry).
- Tests: references validated as JSON; cage not yet run against them.
- Next: build plant/pricing/reference/run with three-way auto-verify; run M1–M3.

## 2026-07-25 — cage-lab MILESTONE 1: setup green (sibling repo scaffolded)

- Implemented (in `../cage-lab`, committed THERE; cage tree stays uncommitted):
  - Fresh `git init` sibling repo per plan §2 layout: `lab/` (stdlib-only runner),
    `fixtures/`, `reference/`, `runs/` (gitignored), `playground/` (gitignored).
  - `python -m lab setup` (idempotent): `uv build --wheel` from `../cage` →
    `runs/dist/cage_flux-0.36.0-py3-none-any.whl`, fresh py3.12 venv at
    `runs/.venv`, install, smoke `cage --version` → **green (cage 0.36.0)**.
  - Black-box boundary in place: `lab/proc.py` drives the installed `cage` binary
    in a hermetic env (scratch HOME + pinned CAGE_BASE, minimal PATH); zero
    `import cage`. `lab/paths.py` carries the `guard_not_playground` invariant.
  - Verified exact log shapes + parser field-mappings against `cage/transcript.py`.
    Two gotchas recorded for fixtures: `samples/**/derived-rows.json` is LOSSY
    (omits surface/cache_write_in/premium — assert against real make_call output),
    and kiro `ts` is import wall-clock (normalize out).
  - `README.md` + `TEST_PLAN.md` authored from the plan.
- Files (cage side): `docs/IMPLEMENTATION.md` (this entry only — append-only).
- Tests: setup smoke green. Matrix not yet implemented.
- Next: author fixtures + `reference/` files (derivations BEFORE cage runs).

## 2026-07-25 — cage-lab docs: eyeball surface strengthened, prerequisites confirmed

- Implemented (docs/spec — review pass against Arpit's 4 requirements):
  - #2 matrix, #3 graphify combos, #4 playground: already complete, no change.
  - #1 manual verification **gap closed**: eyeball reports now quote the cited
    source lines inline + the matching ledger rows (trimmed to asserted fields)
    + a paste-ready side-by-side open command; new `runs/EYEBALL-INDEX.md` (one
    row per scenario · what it proves · verdict · eyeball path, failures first
    with metric + delta) printed as the run's last line; new mental-math fixture
    rule (distinct/roundish values).
  - Always-on-name + `session_uid` assertions propagated from M6 into M1/M2/M3/
    M5b (claude no-summary fallback; copilot titled + untitled; kiro honest `""`).
  - Handoff §11 added — prerequisite status: every asserted behavior is built and
    green (818) in the uncommitted tree; `uv build` from it is correct (the lab
    verifies what is about to ship). No blockers.
- Files: `work/cage-lab-plan.md`, `work/cage-lab-setup.handoff.md`,
  `work/cage-lab-setup.prompt.md`, `docs/{WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only milestone).
- Next: execute the cage-lab setup prompt (Opus, both siblings).

## 2026-07-25 — Archive implemented pairs + rule change: archive on IMPLEMENT, not ship

- Implemented (docs/lifecycle — Arpit's directive):
  - Moved the implemented pair to
    `work/archive/v0.36-names-and-savings-migration.{handoff,prompt}.md`; added the
    one-line archive header to it **and** to the two v0.36-hookless-rebuild files
    (they were moved earlier without one). Header wording for this state:
    *"implemented for v0.36 (unreleased: built + green, release pending)"*.
  - **CLAUDE.md rule amended:** the lifecycle trigger is now **implementation
    (suite green), not release** — cage builds several features per release and
    works in long uncommitted stretches, so archive-on-ship left finished work
    sitting in `docs/` root and made the *Active work* list lie. `docs/` root must
    read as *work not yet done*. Rule now also requires the archive header and
    names the version the work rides.
  - Indexes updated: `work/archive/README.md` (new row + the trigger note),
    `docs/README.md` (Active work = not-yet-built only; built-and-archived noted
    below it), CHANGELOG v0.36.0 "Built from:" now links both pairs.
- Files: `CLAUDE.md`, `CHANGELOG.md`, `docs/README.md`, `work/archive/README.md`,
  `work/archive/v0.36-*.{handoff,prompt}.md` (moved + headers),
  `docs/{WORKLOG,DOC-REGISTRY,IMPLEMENTATION}.md`.
- Tests: not run (docs-only milestone).
- Next: only `cage-lab-setup.{handoff,prompt}` remains active — run it (Opus, both
  siblings). Tree still uncommitted.

## 2026-07-25 — Spec correction: copilot VS Code title shape (from 143 real sessions)

- Implemented (docs/spec only): the executor's verified finding folded back into
  the specs. `cage-import-ledger-plan.md` §4 — the copilot VS Code title is a
  `customTitle` patch record (`kind:1`, `k:["customTitle"]`) or
  `kind:0.v.customTitle`, fallback the first request's `generatedTitle`; 88/143
  real sessions named, so `""` is a **normal state, not a parse failure**. The
  earlier "`kind:0` record" line was wrong — parser right, plan stale. Also
  recorded the shipped manifest granularity: one row per (agent, surface,
  session) + cage-minted `session_uid` (`n_…`).
- Propagated to `cage-lab-plan.md` (fixture note + M2/M5b/M6): it carried the same
  stale assumption and would have yielded fixtures green against a shape reality
  doesn't have; added the untitled-session case and `session_uid` assertions
  (unique; never on a call row or derived view; normalized out of determinism
  byte-compares). Added a shape-warning block to `cage-lab-setup.prompt.md`.
- Files: `docs/{cage-import-ledger-plan,cage-lab-plan,cage-lab-setup.prompt,
  WORKLOG,IMPLEMENTATION}.md`.
- Tests: not run (docs-only); code unchanged — implementation already matched
  reality.
- Next: Arpit's call on the proposed CLAUDE.md union/migrate line; then run the
  cage-lab setup prompt.

## 2026-07-25 — Succession discipline: WORKLOG covers Cowork, INTERVIEW continuous

- Implemented (docs/rules — Arpit's directive):
  - CLAUDE.md: WORKLOG.md bullet now covers **every working surface** (Claude Code
    executions AND Cowork/chat strategy sessions — a chat decision is worklog
    material even when no code moved); new INTERVIEW.md bullet — maintained
    **continuously** for model-switch pickup (state of play · in-flight + next ·
    standing constraints · lessons; stale INTERVIEW at handoff = broken
    succession, same class as a missing changelog entry).
  - WORKLOG.md: appended the Cowork strategy-session entry (the whole v0.36 arc:
    removal decision → handoff pairs → three directives → cage-lab v3 → these
    rules).
  - INTERVIEW.md: state of play rewritten for pickup (uncommitted-tree status +
    817 green, in-flight = cage-lab setup, the Cowork↔Claude-Code working model,
    active standing directives); Fable/Cowork added to the maintainer line with a
    working-with-Arpit lesson.
  - DOC-REGISTRY.md: WORKLOG + INTERVIEW rows re-triggered and bumped.
- Files: `CLAUDE.md`, `docs/{WORKLOG,INTERVIEW,DOC-REGISTRY,IMPLEMENTATION}.md`.
- Tests: not run (docs-only milestone).
- Next: execute `work/cage-lab-setup.prompt.md` (Opus, both siblings); cage tree
  stays uncommitted.

## 2026-07-25 — precise savings migration (B green) — names-and-savings migration

- Implemented (Task B of `docs/names-and-savings-migration.handoff.md`):
  - `ledger.receipts()` is now an **id-deduped union** of `receipts.jsonl` with the
    `savings/<tool>/` tree (`mergeutil.union_by_id`, **tree wins** on a duplicate id),
    with id-less rows **preserved** (concatenation kept them — dropping would change a
    money total). A row in both stores now counts exactly once.
  - New `cage/migratecmd.py` + `cage data migrate-savings` (dry-run default, `--apply`):
    copies historical `tool=="graphify"` receipts **verbatim** (original id, own-`ts`
    shard) into `savings/graphify/`; `receipts.jsonl` is **never rewritten**; **refuses**
    `--apply` on a reconciliation conflict (an id in both stores with a different
    `saved`); post-apply asserts the union total is invariant. graphify only.
  - The precision bar (NOT WRONG, NOT DUPLICATED) is test-pinned: attrib/report/roi
    byte-identical before/after, dup-id-counts-once, idempotent second `--apply` = 0,
    half-completed migration reads correct totals, `receipts.jsonl` byte-identical.
- Files: `cage/ledger.py`, `cage/migratecmd.py` (new), `cage/cli.py`,
  `cage/clicmds.py`, `tests/test_migrate_savings.py` (new).
- Tests: **green** — `pytest -q` 817 passed.
- Next: docs (CHANGELOG fold, `cage query` explain entry, propose CLAUDE.md line) +
  scratch-repo smoke. **No commit** (Arpit's standing constraint).

## 2026-07-25 — session names always-on (A green) — names-and-savings migration

- Implemented (Task A of `docs/names-and-savings-migration.handoff.md`):
  - Removed `policy.session_names_enabled` + the `[capture] session_names` /
    `CAGE_SESSION_NAMES` opt-in (pre-release, no compat shim) — names are now
    **always** captured.
  - `transcript.session_name_claude` (the `summary` record) +
    `transcript.session_name_copilot_vscode` (customTitle patch/kind:0-fold →
    first-request `generatedTitle` → `""`) — both **parse-only/additive**, the
    real VS Code shape **verified against the live store** (143 sessions; the
    plan's "title on kind:0" was only 28/143 — `customTitle` patch record is the
    authoritative source). copilot CLI / kiro → honest `""`.
  - `importcmd`: run-shared `{session: name}` map threaded through the adapters
    (`_lift_names`); `_write_manifest` now emits **one row per (agent, surface,
    session)**, each with a cage-minted `session_uid` (`n_…`) and the lifted
    `session_name` (claude fallback = cwd basename / `project`).
  - `manifest.record_import` per-session (`session` + `session_uid`, name always
    stored); `graphify` manifest row now carries `session_name = task`.
  - Guarantee held: a name lives **only** in `imports.jsonl` — grep-tested off
    call/receipt rows.
- Files: `cage/policy.py`, `cage/transcript.py`, `cage/importcmd.py`,
  `cage/manifest.py`, `cage/graphifymeter.py`, `tests/test_manifest.py`.
- Tests: **green** — `pytest -q` 808 passed.
- Next: Task B — precise savings migration (`cage data migrate-savings` +
  `ledger.receipts()` id-deduped union).

## 2026-07-25 — cage-lab v3: fresh-setup plan, PLAN.md §11, execution pair

- Implemented (docs/spec only — build handed to Claude Code):
  - `work/cage-lab-plan.md` rewritten as **v3** per Arpit's four requirements:
    fresh sibling-repo setup (replaces v2's rebuild-in-place); the correctness
    matrix — M1–M3 solo (claude/copilot/kiro), M4 per-CLI (kiro = honest no-CLI
    cell), M5 per-VS Code/IDE (claude shared-store ⇒ honest `surface=""`),
    M6 kiro+copilot combined, G1–G5 graphify solo/combos (+ native-shim dedupe +
    migration-precision block); auto-verify = three independent readbacks (lab
    recount · cage report/CSV/rollup cross-check · lab-priced USD), reads run
    twice byte-identical; the **eyeball surface** (`lab eyeball` → per-scenario
    SOURCE/LEDGER/MANIFEST/REFERENCE paths + per-metric derivation table with
    source line refs — the manual side-by-side Arpit asked for); the
    **playground** (persistent, runner provably never touches it); track 2 keeps
    the R-scenarios + L-labs + finding taxonomy.
  - `docs/PLAN.md` gained **§11 cage-lab** — the durable long-term summary
    (laws, two verification modes, matrix, playground).
  - New pair `work/cage-lab-setup.{handoff,prompt}.md` (**Model: Opus**;
    references authored BEFORE cage runs; commits in cage-lab only, cage tree
    stays uncommitted). Superseded `work/cage-lab-rebuild.prompt.md` deleted;
    `docs/README.md` indexes updated (sequence: after names-and-savings-migration).
- Files: `work/cage-lab-plan.md`, `docs/PLAN.md`, `work/cage-lab-setup.handoff.md`
  (new), `work/cage-lab-setup.prompt.md` (new), `work/cage-lab-rebuild.prompt.md`
  (deleted), `docs/README.md`, `docs/IMPLEMENTATION.md`.
- Tests: not run (docs-only milestone).
- Next: run the names-and-savings-migration prompt first, then paste
  `work/cage-lab-setup.prompt.md` into Claude Code (Opus) with both siblings.

## 2026-07-25 — Arpit's revisions: names always-on, precise migration, no commits

- Implemented (docs/spec only — code handed to Claude Code):
  - Plan `docs/cage-import-ledger-plan.md` revised on three directives: §4/§7 —
    `session_name` **always captured** (opt-in flag to be removed; claude `summary` /
    VS Code `kind:0` title / `""` for CLI+kiro; manifest-only PII widening, recorded
    deliberately); §3/§7 — savings migration revised from union-only to
    **consolidate**: `cage data migrate-savings` (dry-run first, `--apply`,
    reconciled totals), copy rows with original ids into own-`ts` shards, never
    rewrite `receipts.jsonl`, `ledger.receipts()` → `mergeutil.union_by_id`
    (precision bar: NOT WRONG, NOT DUPLICATED); §7 — release note: nothing commits
    or tags yet, more work rides the uncommitted tree.
  - New execution pair `docs/names-and-savings-migration.{handoff,prompt}.md`
    (**Model: Opus** — union semantics move money; DO-NOT-COMMIT constraint baked
    into both docs). Indexed under Active work.
  - `work/cage-lab-plan.md` corrected to match: R6 asserts names always captured +
    manifest-only grep; R7 gains the migration-precision assertions (byte-identical
    receipts.jsonl + attrib, idempotent `--apply`, high-severity finding on any
    shifted dollar).
- Files: `docs/cage-import-ledger-plan.md`, `docs/names-and-savings-migration.handoff.md`
  (new), `docs/names-and-savings-migration.prompt.md` (new), `work/cage-lab-plan.md`,
  `docs/README.md`, `docs/IMPLEMENTATION.md`.
- Tests: not run (docs-only milestone).
- Next: paste `docs/names-and-savings-migration.prompt.md` into Claude Code (Opus);
  nothing gets committed until Arpit says so.

## 2026-07-25 — cage-lab v2 rebuild prompt (execution driver)

- Implemented: `work/cage-lab-rebuild.prompt.md` — the paste-ready Claude Code
  prompt executing `work/cage-lab-plan.md`: **Model: Opus**, run with both sibling
  checkouts; hard laws (black-box, hand-derived references written BEFORE running
  cage, read-only real ledger, publish into work/regression/); workflow
  (inventory→plan-pause→R1–R4 hermetic first→derive-then-assert→run regression +
  labs→log milestones); guardrail: never fix a red scenario by regenerating its
  reference from cage's own output. Indexed in `docs/README.md`.
- Files: `work/cage-lab-rebuild.prompt.md` (new), `docs/README.md`,
  `IMPLEMENTATION.md`.
- Tests: not run (docs-only milestone).
- Next: paste the prompt into Claude Code (Opus) with `cage/` + `cage-lab/` access;
  first run publishes the v2 baseline into `work/regression/`.

## 2026-07-25 — cage-lab v2 test plan (rebuild spec for the sibling suite)

- Implemented: `work/cage-lab-plan.md` — reviewed how cage-lab v1 works (black-box
  install, hand-derived reference, real-ledger labs, publish-into-`work/regression/`
  convention) and wrote the full v2 plan against the v0.36 hookless surface:
  dead-assertion map (hooks/codex/assets/receipts.jsonl), recreation verdict
  (**rebuild in place — keep repo, history, publishing convention**), R1–R13
  regression scenarios (setup-is-MCP-only, heal matrix, removed-verb directions,
  import rollup vs hand-derived totals, manifest FK integrity, savings tree +
  native-shim dedupe, pricing honesty, determinism, legacy compat, doctor/wiring,
  CSV, taskcorr-stays-caged), L1–L6 real-ledger labs (incl. the taskcorr field
  gate that decides Phase 4 activation), finding taxonomy v2
  (`receipts-empty`→`savings-empty` etc.). Indexed in `docs/README.md`.
- Files: `work/cage-lab-plan.md` (new), `docs/README.md`, `IMPLEMENTATION.md`.
- Tests: not run (docs-only milestone; cage-lab itself is the sibling repo).
- Next: execute the rebuild inside `../cage-lab` (**Opus**) per the plan; first run
  publishes the v2 baseline report into `work/regression/`.

## 2026-07-25 — Phase 4: gated task correlation (built, tested, disabled)

- Implemented (import-ledger plan §4 / Phase 4):
  - `cage/taskcorr.py` — `correlate(root, pol) -> Result`: adopts import-sourced
    (empty-`task`) calls into **closed** tasks by exactly the `taskgroup.join_rows`
    session-window join (session match, task call-span window, overlaps → smallest task
    id), tagging each `method="estimated"` at `constants.TASK_CORRELATION_CONFIDENCE`
    (0.5). **Derive-time only — never mutates the ledger** (a heuristic task written
    in-row would read as ground truth and break append-only + the method law).
  - Two guards: `policy.task_correlation_enabled` (default **off**) + a **blocking**
    `constants.MIN_TASK_CORRELATION_N` (5) min-n gate. Below either it returns an empty
    `Result` with a reason; only enabled AND at-gate yields the tagged correlations.
    No live view consumes it yet (activates on the flag, post real-data validation).
  - Constants: `MIN_TASK_CORRELATION_N`, `TASK_CORRELATION_CONFIDENCE`.
  - Activation gate recorded in the plan's decisions log (§7).
- Files: `cage/{taskcorr (new),constants}.py`, `docs/cage-import-ledger-plan.md` (§7),
  `tests/test_taskcorr.py` (new).
- Tests: `pytest -q` **804 passed** (6 new: disabled-by-default, below-gate blocks,
  at-gate estimated tag, overlap→smallest id, never-mutates-ledger, deterministic).
- Next: docs — README / CHANGELOG / __version__ bump / docs indexes / ADR; propose
  CLAUDE.md edits (do not silently apply); archive the handoff/prompt pair.

## 2026-07-25 — Phase 3: capture manifest (imports.jsonl) + import_id FK

- Implemented (import-ledger plan §4):
  - `cage/manifest.py` — the `imports.jsonl` writer: `record_import` (one row per
    (agent, surface) sweep) + `record_graphify` (one per graphify run), `new_import_id`
    (`i_…`) / `new_graphify_id` (`g_…`), `read`. Counts-only: `source_path` tilde-
    relative, `sessions` is a DISTINCT-session **count** (a sweep spans many — no single
    id), `session_name` stored only when `[capture] session_names` is on (default off).
    Fail-open; carries `cage_version` + `machine` (when enrolled). Never read by a
    derived view.
  - `paths.Footprint.imports` → `ledger/imports.jsonl` (unpartitioned audit buffer).
  - `importcmd.run` mints one `import_id` per sweep, threads it through the ingest path
    (`_ingest` stamps it on each appended call row — the FK), and writes the manifest
    per (agent, surface) from `collected` + `health` (`_write_manifest`).
  - `graphifymeter._meter` mints a `g_…` id, stamps it on the savings row (`import_id`),
    and writes a linked graphify-manifest row (`saving_id` ↔ `import_id`).
  - `policy.session_names_enabled` (default off) + `policy.task_correlation_enabled`
    (default off, for Phase 4) accessors.
- Open question resolved (handoff §10): the manifest stores session **counts** for a
  sweep (honest — a sweep is many sessions) and gates any human session *name* behind
  `[capture] session_names` (default **false**, conservative — a title is softer than a
  count). No titles are lifted yet.
- Determinism note: `import_id` is a per-sweep random capture FK (non-deterministic by
  nature, like `ts`). It is **not** read by any derived view, so the determinism law
  holds; the three cross-import byte-identity tests (fixture corpus, empty-sources,
  debug-on/off) normalize it out before comparing.
- Files: `cage/{manifest (new),paths,policy,importcmd,graphifymeter}.py`,
  `tests/{test_manifest (new),test_fixture_corpus,test_sources,test_debuglog}.py`.
- Tests: `pytest -q` **798 passed** (5 new manifest tests: FK threading, never-a-derived-
  view, tilde PII, linked graphify row, fail-open). End-to-end: an import writes an
  `imports.jsonl` row whose `import_id` matches the call row's FK; a graphify run writes a
  linked graphify-manifest row pointing at a real savings-tree row.
- Next: Phase 4 — best-effort `task` correlation against `tasks.jsonl` (gated,
  disabled-by-default; mirrors the `taskgroup` session-window join).

## 2026-07-25 — Phase 2: dedicated savings/<tool>/ tree

- Implemented (import-ledger plan §3):
  - `schema.make_savings` — a savings row factory (id/ts/import_id/tool/op/session/task/
    unit/raw_alternative/actual/**saved derived**/method/confidence/source_files/
    route_key); `tool` validated as a path-safe token (safe as a dir name); `source_files`
    is a COUNT only (PII guard); import_id/route_key additive-optional.
  - `paths.Footprint`: `savings_dir` / `savings_shard(tool, ts)` / `savings_shards()`;
    `shard` now routes a `("savings", tool)` tuple kind into `savings/<tool>/savings-<month>.jsonl`.
  - `ledger`: `append_row` accepts the tuple kind; new `savings()` reader globs the tree;
    **`receipts()` unions `receipts.jsonl` + the tree** — savings rows are receipt-
    compatible, so every attribution/roi/report surface reads them unchanged, and the
    graphify native-shim dedupe snapshot (which reads `receipts()`) covers both stores
    for free. An empty tree is byte-identical to the legacy reader (determinism holds).
  - `cage/savings.py` — `record()` writer: canonical-ledger sink (honors an explicit
    root like `_resolve_root`), non-PII `route_key`, fail-open, `CAGE_DEBUG` trace.
  - `graphifymeter._meter` routes into `savings/graphify/` (op + source_files count),
    no longer the shared receipts.jsonl. New writes go only to the tree; legacy graphify
    rows in receipts.jsonl still read via the union.
- Files: `cage/{schema,paths,ledger,savings,graphifymeter}.py`, `tests/{test_savings (new),
  test_graphifymeter,test_capture_observability}.py`.
- Tests: `pytest -q` **793 passed** (7 new savings tests + 3 graphify assertions updated:
  the wrapper's receipt is now a savings row, `op` top-level not `meta`). Scratch run:
  a graphify saving lands in `savings/graphify/savings-2026-07.jsonl`, surfaces in
  `ledger.receipts` union + `cage insights attrib`, and `receipts.jsonl` stays empty.
- Next: Phase 3 — `imports.jsonl` capture manifest + thread `import_id` onto call/savings rows.

## 2026-07-25 — Phase 1: enriched call row + loud import summary

- Implemented (import-ledger plan §2.1–§2.2):
  - `schema.make_call`: additive-optional `surface`/`cache_write_in`/`premium`/
    `import_id`, each **omitted when at its default** (byte-identical legacy row, like
    `gap_ms`); added to `CALL_FIELDS`.
  - `transcript.py`: claude splits `cache_creation_input_tokens` into `cache_write_in`
    (tokens_in semantics unchanged), surface stays `""`; copilot CLI → `surface="cli"` +
    `premium` (session `totalPremiumRequests`, stamped once); copilot VS Code →
    `surface="vscode"`; kiro → `surface="ide"`.
  - Loud import rollup (`importcmd._import_rollup`): per-agent×surface calls/tokens_in/
    cached/tokens_out/**cost**, priced via the ONE dispatch `prices.call_usd_match` — a
    row the table can't match (`copilot/auto`, kiro `agent`) reads **UNPRICED**, never a
    silent $0. Built from the run's appended rows via a new `collect` list threaded
    through `ledger.append_new`→`_ingest`→adapters→`run_agent`→`run` (no second ledger
    read). Rendered under the existing per-agent `✔ …` lines; empty import stays quiet.
- Files: `cage/{schema,transcript,ledger,importcmd}.py`, `tests/{test_transcript,
  test_import_unified}.py`, re-blessed `tests/fixtures/transcripts/**/expected.json`
  (the 5 corpora gained the additive fields — claude `cache_write_in`, copilot
  `surface`/`premium`, kiro `surface`).
- Tests: `pytest -q` **786 passed** (6 new: cache-write split, additive-omit, copilot
  surface/premium, kiro surface, rollup hand-derived reference, empty-quiet). Scratch
  import over the real ledger renders the rollup with `copilot/auto` UNPRICED.
- Next: Phase 2 — `savings/<tool>/savings-YYYY-MM.jsonl` tree + `savings.record()` +
  report union with legacy receipts.

## 2026-07-25 — Phase 0: hookless rebuild finished, suite green

- Implemented: completed the half-applied hook/asset removal (handoff §4 items 1–9).
  - `wiringscan.py`: deleted `Stale`/`_digest`/`_bundled_digest`/`stale_assets`/
    `_asset_rows`; `Scan.stale_assets` kept as an always-`[]` field; `_claude/_copilot/
    _kiro_specs` rewritten MCP-only (kiro `required=False`); `_git_hook_foreign` uses the
    module-level `_GIT_HOOK_MARKER`. Leftover/dead-verb scanning of pre-removal hooks intact.
  - `doctorcmd.py`: removed the `_hooks` check + registry row; `_metering`/`_capture_trace`/
    `_wiring` reworded to the pull-only story (MCP = wired read surface; capture = pull-based).
  - `explain_data.py`: fixed the `cage/hooks.py`→`cage/doctorcmd.py` (+ `credits.py`→
    `policy.py`) code_refs; reworded hook prose in capture-on-read/portable-wiring/
    stale-wiring/wiring-inventory/cleanup/metering/freshness/restricted-env entries.
  - CI (`python-package.yml`): dropped the skillgen/docgen `--check` steps.
  - `pyproject.toml`: package-data no longer globs `data/skills|prompts|steering`.
  - `tools/dummyrepo`: S12 launcher asserts dropped the removed hook files; S15/S16 route
    the freshness/policy notes through `report`/`doctor` (post-commit verb gone); S18 plants
    `.claude/settings.json` directly + asserts the hookless *strip* heal.
  - Docstring sweep: transcript/importcmd/exportcmd/cleanup no longer name the deleted
    `hooks` module.
  - Test triage: rewrote the capture tests off the removed hook entry points
    (`ledger.append_new` + `importcmd.run` are the surviving drivers); deleted tests that
    pinned removed surfaces (Stop/SessionEnd/post-commit hooks, wizard, skill/asset copies).
- Files: `cage/{wiringscan,doctorcmd,explain_data,ledger,importcmd,transcript,exportcmd,
  cleanup}.py`, `.github/workflows/python-package.yml`, `pyproject.toml`,
  `tools/dummyrepo/run.py`, `tests/{test_transcript,test_attention,test_import_unified,
  test_errors,test_freshness,test_debuglog,test_debug_coverage,test_bundled_data,
  test_wiringscan,test_cli_tiering,test_agents,test_doctor,test_csv,test_validation_fixes,
  test_zipapp}.py`.
- Tests: `pytest -q` **780 passed**; scratch smoke (setup --claude → import → report →
  doctor exit 0; `cage hook-stop` directs + exits 1); dummyrepo **S1–S18 all PASS**.
- Next: Phase 1 — additive `surface`/`cache_write_in`/`premium`/`import_id` call-row
  fields + the loud per-agent×surface import summary + price at import.

## 2026-07-25 — Whole-plan handoff/prompt pair + IMPLEMENTATION.md rule

- Implemented: `docs/hookless-rebuild.handoff.md` + `docs/hookless-rebuild.prompt.md`
  now cover the **whole** import-ledger plan (Phases 0–4); CLAUDE.md gained the
  standing IMPLEMENTATION.md rule; this file seeded.
- Files: `docs/hookless-rebuild.handoff.md`, `docs/hookless-rebuild.prompt.md`,
  `docs/README.md`, `CLAUDE.md`, `IMPLEMENTATION.md`.
- Tests: not run (docs-only milestone; suite known red — see 2026-07-25 removal
  entry below).
- Next: hand the prompt to Claude Code (**Opus**) to execute Phase 0.

## 2026-07-25 — Import-ledger plan updated for the hookless world

- Implemented: `docs/cage-import-ledger-plan.md` — hookless context note (import is
  the only capture chokepoint), savings redesigned to a per-source tree
  (`savings/<tool>/savings-YYYY-MM.jsonl`, §3 decision resolved), blocking Phase 0
  added to the build order, task-correlation limit (§5) weakened honestly (the
  SessionEnd task-snapshot writers are gone).
- Files: `docs/cage-import-ledger-plan.md`, `docs/README.md` (rewritten index).
- Tests: not run (docs-only milestone).
- Next: handoff/prompt pair (done — see entry above).

## 2026-07-25 — Hook machinery + rendered assets removal (PARTIAL — repo mid-surgery)

- Implemented (removal): deleted `cage/hooks.py`, `cage/gitcommithook.py`,
  `cage/pointers.py`, `cage/setupcmd.py`, `cage/wizard.py`,
  `cage/data/{skills,prompts,steering}/`, `tools/skillgen/`, `tools/docgen/`,
  all top-level `docs/*.md` except the two plans + README, and 7 hook/asset test
  files.
- Implemented (rewrites): `claudewire`/`copilotwire`/`kirowire` → MCP-only with
  heal-by-removal of pre-removal hook artifacts; `agents.py` → `install`/`status`
  only; `cli.py` → hook verbs + skill flags removed; `verbmap.py` → `hook-*` in
  `REMOVED` with "" tail (direction explains removal; heal never rewrites to "");
  `clicmds.cmd_setup` → non-interactive; `wiringscan.py` **half-edited**.
- Files: see `docs/hookless-rebuild.handoff.md` §4 for the exact done/remaining map.
- Tests: **red — repo does not import** (`wiringscan.py` references removed
  `hashlib` import and deleted modules in unedited functions). Deliberate stop:
  implementation paused on request; completion specced as Phase 0 of the handoff.
- Next: Phase 0 items 1–9 in the handoff (wiringscan finish → doctor → explain
  registry → CI workflow → packaging → dummyrepo → docstrings → test triage → green).

## 2026-08-11 — CREDITS-LEGACY-SPLIT: closed by a count, no code change

**Outcome: option (a) — leave the ledger, state the limit.** The item was blocked on a
number, not a decision. The number is **zero**.

Counted across `.cage/ledger/calls-*.jsonl`: 48,069 rows; `claude-code` 47,986 and
`copilot` 83 (vscode 57 / cli 26); 83 `(agent, session, surface, ts)` copilot groups;
**0 groups carrying more than one model**. `credits-2026-08.jsonl` holds 3 rows, all
`kiro` / `model: auto`, three distinct sessions. The double-basis defect requires a
shutdown group of ≥2 rows; none exists in either shard family.

REV-CREDITS defect 2's fix is forward-only, and with no legacy multi-model group there is
nothing for it to have left behind. **No read-side group detector and no
`cage data migrate-*` verb were built** — building either would have been code against a
number nobody had measured, the exact failure the item was filed to prevent.

**Stated limit, carried forward:** the count is *project* scope. `~/.cage` was unreachable
from the environment that ran it, so a copilot-CLI shutdown with the cwd outside any
project (the KIRO-CLI-SCOPE shape) is excluded. Evidence, reopen trigger and the re-run
script: [regression/2026-08-11-credits-legacy-split-count.md](../work/regression/2026-08-11-credits-legacy-split-count.md).

## 2026-08-11 — ADOPT-COV: closed as filed, by its own pre-committed finding

The item pre-committed to a result: *"if half B is empty there, the finding is that the
shim route is structurally unattributable — report it."* Read against the real dev ledger,
**half B is not empty and the shim route is not zero**:

- half B attributes **7 of 9 savings rows (78%)** across **two** agents (claude 6,
  copilot 1), both joined by session;
- half A's **shim route shows 2 runs** (1 receipt, 1 non-measured) — the queue's standing
  "the shim route has produced zero rows" was stale;
- the structural limit **is already reported in the tool's own output, unprompted**:
  *"the interceptor runs as a subprocess and cannot know which agent spawned it
  (structural, not a capture gap)."*

So the finding the item existed to produce is already shipping as honest output, and **no
code is owed**. Adding an `agent` field to usage rows (or an env-stamped agent hint on the
shim) remains a **capture change requiring its own proposal** — unchanged.

**Residual limit carried forward to L1-FIELD, per the removal law:** the
"attested by an L1 hook" table printed **zero rows** while the session-join produced
seven, so attestation contributes nothing to coverage today despite a non-empty
`.cage/state/attest.jsonl`. Evidence:
[regression/2026-08-11-adopt-cov-dev-ledger-read.md](../work/regression/2026-08-11-adopt-cov-dev-ledger-read.md).

## 2026-08-11 — doc hygiene: two proposals archived, two constraints rescued

`copilot-credits-integrity.proposal.md` and `review-hardening.proposal.md` were verified
built **per file, against the code** (not in aggregate, and not off OPEN-WORK's markers)
and moved to `archive/` with the `v0.49-` prefix.

Two things that existed **only** in review-hardening's prose were moved into OPEN-WORK's
*Standing constraints* before the file left `proposals/` — the failure mode the 2026-08-02
cut recorded:

1. copilot's lifecycle gaps text must say **"unverified on a real Copilot"** until
   L1-FIELD verifies (`sessionStart`/`sessionEnd` are cage's own invented names;
   `_session()` assumes Claude's payload shape).
2. **The detector is the live parser** — P1 declined the filed `verbmap.REMOVED` migration
   map because a hand-kept map goes stale in the release that renames an event. Where a
   proposal and the shipped code disagree, the code wins.

Also corrected: `compare/README.md` described v0.44 and v0.48 as *unreleased* (both
shipped) and COMMITS-WINDOW as *awaiting verdict* (decided B and built). New:
[FIELD-RUNBOOK.md](../docs/FIELD-RUNBOOK.md) — copy-paste procedures for the five hands-only
items, every command checked against `cage 0.48.0`'s real `--help`.

## 2026-08-12 — GF-LAUNCHER: verdict B accepted (decision recorded, nothing built)

Arpit accepted **option B — an unconditional interpreter arm in B5** on the
[gf-launcher-metering compare](../work/compare/gf-launcher-metering.compare.md). The compare's
status moved from *proposed verdict* to **DECIDED**; the item moved out of OPEN-WORK's
*your decision* section into a new **agent lane — buildable now**, which had been empty
since the 2026-08-11 sweep.

**No code changed.** This entry records a decision, not a build.

**What B decides:** B5's capability probe asks *"is there a `cage` command"* when it means
*"can cage run"*. Arm 2 (`python3 -m cage data graphify --help`) is reached only when arm 1
misses, so standard mode is unchanged in behaviour and latency, and the fix covers a
**superset** of launcher mode — a `cage.pyz` on `PYTHONPATH`, an unactivated venv, any
importable-but-not-on-PATH install.

**What the build inherits, carried into [open/GF-LAUNCHER.md](../docs/open/GF-LAUNCHER.md) so it
survives the compare doc:** both twins move together (ADR 0007); **D8** is a new permanent
divergence (`python3` vs `py -3` with a `python` fallback) and must be registered in the
shim contract; the **B3 marker set needs no change**, verified — `cage data graphify`
remains a substring; `doctorcmd._launcher_gap` inverts from a `_WARN` into an
importability check mirroring `kiro-mcp`; `tests/test_win_graphify_shim.py`'s B5 cases
assume *cage absent ⇒ unmetered*, which is precisely what B changes; and the compare's
invoker table is owed to `restricted-environments.md` regardless.

**The honest close is bound in advance:** *"fixed on POSIX, CI-asserted on Windows"* —
never *"fixed"*. B does nothing for the three non-shim rows (copilot VS Code, kiro, the
human bare-terminal call).

**An ADR is owed on ship** — B amends the B5 contract and adds a divergence, which is
architecturally load-bearing rather than a patch note.

**Reopen triggers survive the accept:** arm-2 probe above **250 ms** on a real target
endpoint, or a Windows install where neither `py -3` nor `python` resolves while cage is
importable — either pushes the call back toward A.

## 2026-08-12 — OPEN-WORK header: the seventh staleness, and the counts removed

`docs/OPEN-WORK.md`'s header read *"8 commits ahead of origin/main with 65
staged-uncommitted files"* and *"Next: commit and push the 65 files"* after the commit
that made those numbers **17 and 0**. Written before the commit, never revisited.

`tests/test_queue_honesty.py` passed it, **correctly** — the gate exempts counts by
design, because a count is true-at-writing and would redden on the very next commit.
That exemption is the hole this fell through.

**Fix: no count is written in the header any more.** It now states the *shape* (tree
clean; HEAD ahead of origin and unpushed) and points at
`git rev-list --count origin/main..HEAD` for the number. A number in prose is a number
with no detector; the gate's exemption is sound, so the prose had to stop making the
claim rather than the gate start checking it.
