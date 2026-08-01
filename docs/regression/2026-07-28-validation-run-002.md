# Golden-set validation — run-002 (Phase 1 baseline, pre-fix, 2026-07-28 am)

**Report sha256 (body below the marker):** `3b11bc8b61f74e26bebca02f068984e9157b048aab3224f53582ea34b8591197`
_Hashed range: from the newline after the marker to EOF; this header is excluded._

<!-- HASH-COVERS-BELOW -->
**Run:** run-002 · **Phase:** 1 — scripted grid, pre-fix baseline · **Date:** 2026-07-28 (am) · **Cells:** V1–V5b
**Machine:** darwin 25.3.0 · cage 0.36.0 · Python 3.9.6 · claude 2.1.207 · copilot 1.0.70 · kiro-cli 2.14.2 (installed 2026-07-28; Kiro IDE 0.12.333 also present).
**Config file in use:** workspace `.cage/cage.toml` active, **no** legacy `policy.toml` shadow — clean; check 8 green on every cell.
**Isolation:** every `cage import` used `--ledger captures/<run-id>/ledger` with `CAGE_BASE` pointed at the scratch ledger; real `~/.cage` never named. Source-log shas unchanged before==after on every captured file (check 2 green throughout).
**Verdict:** V1/V2 (claude) 8/8 · V3/V4 (copilot) check 5 red (undercount) · V5/V5b (kiro CLI) checks 4–5 red (0 rows). Five findings observed (§3).

## 1. The scripted grid — cells × the eight checks

| cell | agent / graphify | 1 diff | 2 copy | 3 map | 4 import | 5 reconcile | 6 signals | 7 isol | 8 config |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **V1** | claude / off | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **V2** | claude / on  | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **V3** | copilot / off | ✅ | ✅ | ✅ | ✅ | **❌** | ✅ | ✅ | ✅ |
| **V4** | copilot / on  | ✅ | ✅ | ✅ | ✅ | **❌** | ✅ | ✅ | ✅ |
| **V5** | kiro / off | ✅ | ◻ | ✅ | **❌** | **❌** | ✅ | ✅ | ✅ |
| **V5b** | kiro / on | ✅ | ◻ | ✅ | **❌** | **❌** | ✅ | ✅ | ✅ |

- **V1/V2 (claude): all eight green.** Full three-way reconciliation (log recount ==
  cage ledger == hand count) to the token.
- **V3/V4 (copilot): check 5 red — a real cage finding, not a protocol bug** (§3.1).
  Row *count* reconciles (check 4 green); token *totals* drift because cage
  undercounts a resumed session.
- **V5/V5b (kiro CLI): checks 4 & 5 red — the fourth-parser finding** (§3.4). cage
  reads **0** rows from the SQLite store (wrong location *and* wrong format). Check 2
  is **◻ n/a**: the raw DB carries `auth_kv` + all-directory content, so verbatim copy
  was **refused**; a redacted, workspace-scoped projection was captured instead (a
  documented deviation from the verbatim rule, §3.4).

The red cells are reported, not hidden. Per the phase rule, "a red cell that tells the
truth is the entire point."

## 2. The numbers this run produced (log recount · cage ledger)

| cell | rows (hand=cage) | tokens_in (truth · cage) | tokens_out | cached_in | cache_write_in |
|---|---|---|---|---|---|
| V1 claude/off | 17 = 17 | 381,813 · 381,813 ✅ | 3,395 · 3,395 | 290,384 · 290,384 | 91,193 · 91,193 |
| V2 claude/on  | 19 = 19 | 565,637 · 565,637 ✅ | 5,292 · 5,292 | 465,631 · 465,631 | 99,968 · 99,968 |
| V3 copilot/off | 3 = 3 | **227,298 · 189,788** ❌ | 1,995 · 1,808 | 186,864 · 151,603 | 0 · 0 |
| V4 copilot/on  | 3 = 3 | **233,675 · 191,414** ❌ | 2,337 · 1,879 | 210,513 · 173,812 | 0 · 0 |
| V5 kiro/off | 5 turns · **0 cage** ❌ | **null in store · 0** | null · 0 | null · 0 | null · 0 |
| V5b kiro/on | 7 turns · **0 cage** ❌ | **null in store · 0** | null · 0 | null · 0 | null · 0 |

- Copilot undercount this run: V3 **37,510 tokens (16.5%)**, V4 **42,261 tokens
  (18.1%)** — the drift equals exactly the second cumulative `session.shutdown` of the
  Q2→Q3 (`--continue`) session that cage drops (finding §3.1).
- **Kiro CLI records no token counts at all** — usage is **credits + context %** (V5:
  0.197 credits / 5 turns; V5b: 0.2368 / 7). cage's ledger gets **0** rows from this
  store. There is no number to reconcile because the store holds none (finding §3.4).

## 3. Findings observed in this run

One line each; each defect's full lifecycle and current status live in its own finding
doc (linked). This report does not restate them.

- **§3.1 Copilot resumed sessions are undercounted (HIGH).** cage records 189,788 for a
  session that consumed 227,298 (16.5%); the dropped 2nd cumulative `session.shutdown`
  is lost to id-dedup. → [finding](2026-07-28-finding-copilot-resumed-undercount.md)
- **§3.2 Stacked graphify shims recurse → hang (MED).** A fresh `cage setup` shim and a
  stale `cage adopt` shim on PATH resolve to each other → infinite recursion → the
  wrapped call hits the 2-min cap. → [finding](2026-07-28-finding-graphify-shim-recursion.md)
- **§3.3 Graphify savings path works, but the A/B didn't fire (product-level).** Direct
  `cage data graphify` filed a real 11,692-token saving, but V2/V4 produced 0 rows —
  the agents answered without shelling out to graphify. → [finding](2026-07-28-finding-graphify-ab-no-fire.md)
- **§3.4 Kiro CLI logs to a SQLite DB cage can't read (HIGH).** `data.sqlite3`
  (`conversations_v2` keyed by cwd) is unseen by cage; config alone can't bridge it
  (jsonl parser reads 0 rows); the DB co-locates auth + transcript text so it is not
  verbatim-capturable. → [finding](2026-07-28-finding-kiro-cli-sqlite-credits.md)
- **§3.5 Declared `[sources] surface` lost on built-in collision (LOW).** On the IDE
  token log a declared `surface="cli"` is silently dropped when it collides by
  `(path, glob)` with a built-in. → [finding](2026-07-28-finding-surface-restamp-collision.md)

## 4. Per-field capture truth (scripted surfaces, this run)

| field | claude/cli | copilot/cli | **kiro/cli (SQLite store)** |
|---|---|---|---|
| tokens_in | ✅ exact | ✅ exact* | ❌ **null** (schema exists, never filled) |
| tokens_out | ✅ | ✅ | ❌ **null** |
| cached_in | ✅ (Q3 read) | ✅ (`cacheReadTokens`) | ❌ null (`cache_read_input_tokens` field, null) |
| cache_write_in | ✅ (Q2 create) | ❌ absent in store | ❌ null (field present, null) |
| model | ✅ `claude-opus-4-8` | ✅ `claude-haiku-4.5` + `gpt-5-mini` (mixed) | ⚠ `"auto"` (server-routed; `--effort` not surfaced) |
| gap_ms | ✅ present (4,416 ms turn gap) | ❌ (no per-turn timestamps) | ✅ **derivable** — ms `created_at`/`updated_at` present |
| session id | ✅ uuid per turn | ✅ uuid per session | ✅ **`conversation_id` uuid, per-directory** |
| session name | ⚠ `summary` record | ❌ | ❌ (none; `latest_summary` null) |
| usage proxy | — | — | **credits + `context_usage_percentage`** (the only usage signal) |
| surface | `""` (honest blank) | `"cli"` (store-derived) | would be `"cli"` **iff** a parser existed |
| surface source | parser (`""`) | parser (`cli`) | DECLARED-only (`[sources.kiro] surface="cli"`), but **0 rows parse** |
| config file | cage.toml | cage.toml | cage.toml |

\* copilot `tokens_in` is exact *per shutdown* — the undercount (§3.1) is the dropped 2nd
shutdown, not a per-value error.

**The Kiro CLI store is the inverse of the IDE store.** The IDE `tokens_generated.jsonl`
has token *counts* but no session id / no timestamps / model `"agent"`. The CLI SQLite
store has **session ids + ms timestamps** (a real upside) but its token fields are
**null**; the only usage signal is credits + context %. Neither store, today, gives cage
a token count with a session boundary.

- **Q1 floor is not zero-cache.** Even `Reply with exactly: ok` shows
  `cache_write_in`/`cached_in` on claude — Claude Code caches the system prompt + tool
  schema. The "floor" call already exercises the cache fields.
- **claude `surface=""` confirmed** at the CLI. The clean VS Code-vs-CLI test is this
  cell (`20260727-1850-claude-cli-off`) vs the manual V6 — deferred (§5).

## 5. What this run did NOT cover, and why

- **Manual cells V6–V11** (VS Code / IDE surfaces) — extensions can't be driven
  headlessly; they are the human sweep (`manual/vscode-checklist.md`), a distinct future
  run.
- **Does the graphify PATH interceptor fire under the VS Code extensions?** — cannot be
  tested headlessly; deferred to the manual cells (V7/V9/V11). Caveat: it is a PATH
  interception, so an extension that never shells out to a terminal will not hit it. The
  scripted CLI A/B additionally showed the agents don't invoke graphify on their own
  (§3.3).
- **Claude CLI vs VS Code distinguishability** — the CLI side is answered here
  (`surface=""`, store `~/.claude/projects/<slug>/*.jsonl`); the VS Code side is the
  manual V6 (V1-vs-V6 on identical questions is the clean test).
- **Phase 2** — awaits the two HIGH findings (§3.1, §3.4) being acted on.
