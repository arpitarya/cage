# Golden-set Phase 1 — Validation Report (INTERIM: all scripted cells done)

> **⛔ SUPERSEDED — split into [run-002 (pre-fix)](2026-07-28-validation-run-002.md) + [run-003 (post-fix)](2026-07-28-validation-run-003.md).** An earlier hash-version of the layered validation report; preserved unedited below as evidence, not current. (Body/hash unchanged — banner is above the hashed range.)

**Report sha256 (body below the marker):** `f3c058e4b1ec55b5fe2f402231c4d8324c3168d40d570c15f5675b594a08e624`
_Hashed range: from the newline after the marker to EOF; this header is excluded._

<!-- HASH-COVERS-BELOW -->
## Re-run results (post-fix, 2026-07-28) — capture-precision cycle

The fixes from `cage/docs/capture-precision.plan.md` were built and re-validated with the
fixed cage (working tree, uncommitted). **Failures first** (V3/V4 → V5/V5b → V1/V2):

| cell | before | after fix |
|---|---|---|
| **V3 copilot/off** | 7/8 (undercount 189,788) | **8/8**; fixed cage re-imports the baseline logs to **exactly 227,298**; a fresh paid run also 8/8 (recount==cage) |
| **V4 copilot/on** | 7/8 (191,414) | fixed cage → **exactly 233,675**; re-import idempotent (+0 rows) |
| **V5 kiro/off** | 4,5 ✗ (0 rows) | **pass** — SQLite parser records **12 credit rows**; check 4 ✅; check 5 ◻ n/a (tokens null — no token total to reconcile); check 2 ◻ n/a |
| **V5b kiro/on** | 4,5 ✗ | **pass** — **15 credit rows**; same honest limits |
| **V1 claude/off** | 8/8 (381,813) | **byte-identical** — 381,813, 17 rows |
| **V2 claude/on** | 8/8 (565,637) | **byte-identical** — 565,637, 19 rows |

**Self-heal proof (real session `8073abba`):** legacy row 70,071 → re-import fixed parser →
**107,581 exact** (+37,510, the exact undercount) → third import **+0**. No double count.

Copilot deltas reconcile to the token; Kiro is captured as credits (estimated, unpriced —
tokens are unrecoverable, stated as a limit, never faked); claude is untouched. Full fix
list: `cage/work/regression/2026-07-28-capture-precision-fixes.md`.

---

**Status:** **all** scripted cells V1–V5b executed (V5/V5b run 2026-07-28 once
`kiro-cli` was installed). Manual cells V6–V11 handed to Arpit
(`manual/vscode-checklist.md`). **STOP point reached** — Phase 2 and the manual
sweep await Arpit's go.
**Machine:** darwin 25.3.0 · cage 0.36.0 · Python 3.9.6 · claude 2.1.207 ·
copilot 1.0.70 · **kiro-cli 2.14.2** (installed 2026-07-28; Kiro IDE 0.12.333 also present).
**Headline (V5):** Kiro CLI logs to a **SQLite DB** cage has never seen and cannot
parse — the **fourth-parser finding**, confirmed. Details §4.
**Config baseline:** workspace `.cage/cage.toml` active, **no** legacy
`policy.toml` shadow (clean; check 8 green on every cell).
**Isolation:** every `cage import` used `--ledger captures/<run-id>/ledger` and
`CAGE_BASE` pointed at the scratch ledger; real `~/.cage` never named. Source-log
shas unchanged before==after on every captured file (check 2 green throughout).

---

## 1. The scripted grid — cells × the eight checks

| cell | agent / graphify | 1 diff | 2 copy | 3 map | 4 import | 5 reconcile | 6 signals | 7 isol | 8 config |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **V1** | claude / off | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **V2** | claude / on  | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **V3** | copilot / off | ✅ | ✅ | ✅ | ✅ | **❌** | ✅ | ✅ | ✅ |
| **V4** | copilot / on  | ✅ | ✅ | ✅ | ✅ | **❌** | ✅ | ✅ | ✅ |
| **V5** | kiro / off | ✅ | ◻ | ✅ | **❌** | **❌** | ✅ | ✅ | ✅ |
| **V5b** | kiro / on | ✅ | ◻ | ✅ | **❌** | **❌** | ✅ | ✅ | ✅ |

- **V1/V2 (claude): all eight green.** Full three-way reconciliation
  (log recount == cage ledger == hand count) to the token.
- **V3/V4 (copilot): check 5 red — a real cage finding, not a protocol bug** (§3.1).
  Row *count* reconciles (check 4 green); token *totals* drift because cage
  undercounts a resumed session.
- **V5/V5b (kiro CLI): checks 4 & 5 red — the fourth-parser finding** (§4). cage
  reads **0** rows from the SQLite store (wrong location *and* wrong format).
  Check 2 is **◻ n/a**: the raw DB carries `auth_kv` + all-directory content, so
  verbatim copy was **refused**; a redacted, workspace-scoped projection was
  captured instead (§4, a documented deviation from the verbatim rule).

The red cells are reported, not hidden. Per the phase rule, "a red cell that tells
the truth is the entire point."

## 2. The numbers, side by side (log · cage ledger)

| cell | rows (hand=cage) | tokens_in (truth · cage) | tokens_out | cached_in | cache_write_in |
|---|---|---|---|---|---|
| V1 claude/off | 17 = 17 | 381,813 · 381,813 ✅ | 3,395 · 3,395 | 290,384 · 290,384 | 91,193 · 91,193 |
| V2 claude/on  | 19 = 19 | 565,637 · 565,637 ✅ | 5,292 · 5,292 | 465,631 · 465,631 | 99,968 · 99,968 |
| V3 copilot/off | 3 = 3 | **227,298 · 189,788** ❌ | 1,995 · 1,808 | 186,864 · 151,603 | 0 · 0 |
| V4 copilot/on  | 3 = 3 | **233,675 · 191,414** ❌ | 2,337 · 1,879 | 210,513 · 173,812 | 0 · 0 |
| V5 kiro/off | 5 turns · **0 cage** ❌ | **null in store · 0** | null · 0 | null · 0 | null · 0 |
| V5b kiro/on | 7 turns · **0 cage** ❌ | **null in store · 0** | null · 0 | null · 0 | null · 0 |

- V3 undercount: **37,510 tokens (16.5%)**. V4: **42,261 tokens (18.1%)**.
- The drift equals exactly the second cumulative `session.shutdown` of the
  Q2→Q3 (`--continue`) session that cage drops (§3.1).
- **Kiro CLI records no token counts at all** — usage is **credits + context %**
  (V5: 0.197 credits / 5 turns; V5b: 0.2368 / 7). cage's ledger gets **0** rows
  from this store. There is no number to reconcile because the store holds none
  (§4).

## 3. What we learned — every field / behavior that surprised us

### 3.1 ⚠ CAGE FINDING (HIGH) — Copilot resumed sessions are undercounted

- **Mechanism.** `copilot -p --continue` (our Q2→Q3 same-session pair) appends a
  **second** `session.shutdown` whose `modelMetrics` are **cumulative** (they
  already include the earlier turn). Verified in V3 session `8073abba`:
  shutdown-1 `inputTokens=70,071`, shutdown-2 `inputTokens=107,581`.
- **Cage keeps the FIRST.** `parse_copilot_calls` derives the call id from the
  session id (idempotent by design, so re-imports don't double-count). Inside one
  grown file that means the 2nd (higher, cumulative) shutdown is **deduped as a
  duplicate id and dropped** — cage records 70,071 for a session that actually
  consumed 107,581. Q3's entire marginal cost is lost.
- **Blast radius.** Any Copilot session that shuts down more than once —
  `--continue` scripting **and** a VS Code chat that spans app restarts/reloads.
  16–18% here; unbounded in principle (longer resumed sessions lose more).
- **This is a finding, filed — not patched.** No cage source touched. Suggested
  fix direction (for a later cage task, not this one): on re-seeing a session id,
  *update* the row to the max/last cumulative shutdown rather than dedup-drop.
- **Independent-recount note:** `drive.py`'s `recount_copilot` was itself wrong at
  first (it summed all shutdowns / read the pre-`data` shape). Both were driver
  bugs, fixed, re-verified — which is exactly why the reconciliation is *three*-way:
  a two-way check would have shared the recounter's failure mode.

### 3.2 ⚠ CAGE / WIRING FINDING (MED) — stacked graphify shims recurse → hang

- Two graphify interceptors on this machine's PATH: the **fresh** one
  `cage setup` wrote (`workspace/bin/graphify` → `cage data graphify`) and a
  **stale** one from an old `cage adopt` (`~/my_programs/anton/bin/graphify` →
  the **removed** `cage graphify` verb).
- Each shim removes only *its own* dir before resolving the "real" graphify, so
  with both on PATH they resolve to **each other** → infinite mutual recursion →
  the wrapped call hangs (hit our 2-min cap).
- The stale `anton/bin/graphify` is itself a dead-verb wiring-liveness artifact
  (`cage graphify --help` fails now; it falls through to the real binary, but its
  *presence on PATH* is what closes the recursion loop).
- `drive.py` now drops any PATH dir whose `graphify` shim names the removed verb
  (a safety net for the ON cells, filed here — **not** a cage fix).

### 3.3 Graphify savings path works; the A/B did not fire through the agents

- **Path validated directly:** `cage data graphify -- <graphify> explain
  Transformer00` cited `pkg/big_module.py` and filed a real savings row —
  `raw_alternative=11,810 · actual=118 · saved=11,692 · method="modeled" ·
  confidence=0.6` into `savings/graphify/savings-2026-07.jsonl`. The capture
  mechanism is live and correct.
- **But V2/V4 (graphify ON) produced 0 savings rows.** `claude -p` / `copilot -p`
  answered the 3-sentence architecture question **without shelling out to
  graphify**, so the interceptor never fired. The A/B is therefore
  **agent-behavior-dependent** — Phase 2 must either prompt explicitly for a
  graphify query or have the driver invoke graphify to measure A−B honestly.
- **Threshold honesty:** a graphify query over the *small* toy modules yields an
  answer larger than the cited files ⇒ `no-saving-to-claim` (correct). Only
  large-file citations (big_module.py) produce a saving. Expected, not a bug.

### 3.4 Per-field capture truth (scripted surfaces)

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

\* copilot `tokens_in` is exact *per shutdown* — the undercount is the dropped
2nd shutdown, not a per-value error.

**The Kiro CLI store is the inverse of the IDE store.** The IDE
`tokens_generated.jsonl` has token *counts* but no session id / no timestamps /
model `"agent"`. The CLI SQLite store has **session ids + ms timestamps** (a real
upside — it would fix two of Kiro's four weaknesses) but its token fields are
**null**; the only usage signal is credits + context %. Neither store, today,
gives cage a token count with a session boundary.

- **Q1 floor is not zero-cache.** Even `Reply with exactly: ok` shows
  `cache_write_in`/`cached_in` on claude — Claude Code caches the system prompt +
  tool schema. Worth knowing: the "floor" call already exercises the cache fields.
- **claude `surface=""` confirmed** at the CLI. The VS Code-vs-CLI
  distinguishability test is V1 (`20260727-1850-claude-cli-off`) vs the manual
  **V6** — the cleanest check of the honest blank.

## 4. ⚠ CAGE FINDING (HIGH) — Kiro CLI logs to a SQLite DB cage can't read (V5)

*(This is the resolved version of the previously-open discovery — `kiro-cli` was
installed 2026-07-28 and V5/V5b were run for real.)*

### 4.1 Where it logs (discovery, verbatim)

- **Store:** `~/Library/Application Support/kiro-cli/data.sqlite3` — a **SQLite
  database**, found by a broad `find -newer` diff around one real turn (not one of
  cage's three candidate roots). `~/.kiro` holds **no** sessions;
  `$TMPDIR/kiro-log/kiro-chat.log` is a debug log only, not usage.
- **Schema:** table `conversations_v2(key, conversation_id, value TEXT,
  created_at, updated_at)` — `key` is the **cwd** (per-directory sessions),
  `value` is the conversation JSON, `created_at`/`updated_at` are **ms epoch
  timestamps**. (Also present: an `auth_kv` credentials table and `history` — see
  4.4.)
- **The usage payload, quoted real (Q2, a large-input turn):**
  ```
  history[1].request_metadata = {
    total_tokens: null, uncached_input_tokens: null, output_tokens: null,
    cache_read_input_tokens: null, cache_write_input_tokens: null,
    context_usage_percentage: 2.8723 }
  user_turn_metadata.usage_info = [ {value: 0.0468, unit: "credit"} ]
  model_info = { model_id: "auto", model_name: "auto", rate_multiplier: 1.0 }
  ```
- **The token schema exists but is NEVER populated.** Null on the Q1 floor call
  **and** on the large Q2 (`big_module.py`, context % 1.47→2.87). Usage is
  expressed only as **credits** and **`context_usage_percentage`**. `--effort
  high` did not change `model_id` off `"auto"` — the effort tier is not persisted,
  so cage's effort-suffix family pricing has nothing to match.

### 4.2 Does cage see it? — No.

- `cage import --agent kiro` reads cage's **one** known Kiro path (the IDE
  `tokens_generated.jsonl`, 16 old `model="agent"` rows) — it never looks at
  `data.sqlite3`. Every kiro-cli turn we ran is **invisible** to cage.

### 4.3 Was config enough? — No. Fourth parser required.

- Config-fix attempted on the spot: `[sources.kiro] paths =
  ["…/kiro-cli/data.sqlite3"], surface = "cli"` → re-import →
  **`✔ kiro: imported 0 call(s) from 1 file(s)`**; `cage doctor --paths` lists the
  source as `[policy] surface=cli · 0 parseable row(s)`.
- **`[sources]` only reuses an existing jsonl parser** (`format =
  claude|copilot|kiro`), and a jsonl parser reads a SQLite binary as **0 rows**.
  Config cannot bridge a format gap. **A fourth (SQLite) parser is required** —
  filed, **not written here** (out of scope).
- **What a parser would need to read** (from 4.1): `conversations_v2` rows keyed
  by cwd → `conversation_id` (session), `created_at`/`updated_at` (ts + a real
  gap_ms source), `model_info.model_id`, and per-turn `request_metadata`. It would
  gain session boundaries + timestamps, **but still could not recover token
  counts** (null) — at best it maps credits/context% to an *estimated* cost, a
  method-tag question of its own.

### 4.4 ⚠ Second finding (capture-architecture) — the store is not verbatim-capturable

- `data.sqlite3` co-locates an **`auth_kv` credentials table** and **every
  directory's full conversation text** (prompts + responses) with the usage
  metadata. Unlike the jsonl session stores, it **cannot be copied verbatim** into
  a shareable corpus, and a cage SQLite parser must read **counts/ids/times only,
  never the `value` transcript body** — the counts-never-content law is *harder*
  to hold here because content sits in the same file/row as the metadata.
- **Deviation recorded:** for V5/V5b the driver captured a **redacted,
  workspace-scoped projection** (`logs/kiro-cli/conversations.redacted.json` —
  conversation_id, timestamps, model, the null token schema, credits, and per-turn
  *character lengths* only; leak-tested: no class names, no code, no auth). Check 2
  is therefore **◻ n/a** rather than a verbatim-copy pass. This is the one
  place the golden set departs from "copy bytes," and it is forced by the store's
  shape, not a shortcut.

### 4.5 The IDE-store config nuance still holds (LOW)

- Separately confirmed on the IDE token log: the v0.36 `surface="cli"` restamp
  works on **distinct** content (rows → `surface="cli"`), but is silently lost
  when a declared source's rows **collide by derived id** with a built-in source.
  Only bites in the overlap case; a genuinely distinct store wouldn't collide.

## 5. The three questions Phase 1 had to answer

1. **Where does Kiro CLI log — was config alone enough?** → **RESOLVED (§4).**
   It logs to `~/Library/Application Support/kiro-cli/data.sqlite3` (a SQLite DB,
   `conversations_v2` keyed by cwd). **cage does not see it, and config alone is
   NOT enough** — `[sources]` reuses a jsonl parser, which reads the SQLite binary
   as 0 rows. **A fourth (SQLite) parser is required.** Even with one, token counts
   are null in the store (credits + context% only); the upside is real session ids
   + ms timestamps. Second finding: the DB mixes auth + all-project content, so it
   is not verbatim-capturable (counts-never-content is harder here).
2. **Does the graphify PATH interceptor fire under the VS Code extensions?** →
   **DEFERRED to the manual cells** (V7/V9/V11); it cannot be tested headlessly.
   Caveat recorded: it is a PATH interception, so an extension that never shells
   out to a terminal will not hit it. The scripted CLI A/B additionally showed the
   agents don't invoke graphify on their own (§3.3).
3. **Are the Claude CLI and VS Code stores distinguishable?** → **CLI side
   answered:** `surface=""`, store =
   `~/.claude/projects/<slug>/*.jsonl`. The VS Code side is the manual **V6**;
   V1-vs-V6 on identical questions is the clean test. Deferred with the data
   staged.

## 6. Handover

- **Scripted corpus (all 6 cells captured):**
  `captures/*-{claude,copilot}-cli-{off,on}/` (verbatim `logs/`) and
  `captures/*-kiro-cli-{off,on}/` (**redacted** `logs/kiro-cli/…`, §4.4). Each
  carries `manifest.json`, `transcript-map.json`, scratch `ledger/`, `checks.json`.
- **Manual cells:** `manual/vscode-checklist.md` (V6–V11) + `manual/_template.md`;
  capture via `drive.py --manual-capture --phase pre|post` (verified working).
- **Recheck any cell without re-calling an agent:** `python drive.py --recheck
  <run-id>` (or `all`); kiro cells show stored inline checks.
- **Gates for Phase 2 (Arpit), two cage findings that warrant `work/regression/`
  entries + likely cage work before a full sweep leans on these agents:**
  1. **Copilot resumed-session undercount** (§3.1) — a fix (update-to-last-cumulative).
  2. **Kiro CLI SQLite store** (§4) — a fourth parser (session ids + timestamps are
     the prize; token counts are unrecoverable, so cost would be credit-derived and
     `estimated`), plus the counts-never-content guard for a store that mixes auth +
     transcript text. Until then, **all Kiro CLI usage is uncaptured** (cage sees
     only the thin IDE token log).
