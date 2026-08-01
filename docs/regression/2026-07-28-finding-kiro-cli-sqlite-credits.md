# Finding — Kiro CLI logs to a SQLite DB cage couldn't read

**Severity:** HIGH · **Status:** ✅ CLOSED (credits parser shipped; exact-token
route closed by the P2 proxy probe) · **Surface:** kiro CLI

| field | value |
|---|---|
| Observed in | [run-002](2026-07-28-validation-run-002.md) (V5/V5b checks 4–5 red, 0 rows) |
| Verified captured in | [run-003](2026-07-28-validation-run-003.md) (12/15 credit rows) |
| Fixes / closure | [capture-precision-fixes §Kiro](2026-07-28-capture-precision-fixes.md) · [kiro proxy probe (P2)](2026-07-28-kiro-proxy-probe.md) |

## Where it logs (discovery)

- **Store:** `~/Library/Application Support/kiro-cli/data.sqlite3` — a **SQLite
  database**, found by a broad `find -newer` diff around one real turn (not one of
  cage's three candidate roots). `~/.kiro` holds **no** sessions;
  `$TMPDIR/kiro-log/kiro-chat.log` is a debug log only.
- **Schema:** `conversations_v2(key, conversation_id, value TEXT, created_at,
  updated_at)` — `key` is the **cwd** (per-directory sessions), `value` is the
  conversation JSON, `created_at`/`updated_at` are **ms epoch timestamps**. Also
  present: an `auth_kv` credentials table and `history`.
- **Usage payload, quoted real (Q2, a large-input turn):**
  ```
  history[1].request_metadata = {
    total_tokens: null, uncached_input_tokens: null, output_tokens: null,
    cache_read_input_tokens: null, cache_write_input_tokens: null,
    context_usage_percentage: 2.8723 }
  user_turn_metadata.usage_info = [ {value: 0.0468, unit: "credit"} ]
  model_info = { model_id: "auto", model_name: "auto", rate_multiplier: 1.0 }
  ```
- **The token schema exists but is NEVER populated** — null on the Q1 floor call
  and on the large Q2 (context % 1.47→2.87). Usage is expressed only as **credits**
  and **`context_usage_percentage`**. `--effort high` did not move `model_id` off
  `"auto"` — the effort tier is not persisted.

## Config alone was not enough

- `[sources.kiro] paths=["…/data.sqlite3"], surface="cli"` → re-import →
  `✔ kiro: imported 0 call(s) from 1 file(s)`. `[sources]` only reuses an existing
  **jsonl** parser, which reads a SQLite binary as **0 rows**. Config cannot bridge
  a format gap — a fourth (SQLite) parser was required.

## Second finding — the store is not verbatim-capturable

- `data.sqlite3` co-locates an **`auth_kv` credentials table** and **every
  directory's full conversation text** with the usage metadata. It **cannot be
  copied verbatim** into a shareable corpus; a cage SQLite parser must read
  counts/ids/times only, never the `value` transcript body — counts-never-content
  is *harder* here because content sits in the same row as the metadata.
- **Deviation recorded (run-002):** the driver captured a **redacted,
  workspace-scoped projection** (`logs/kiro-cli/conversations.redacted.json` —
  conversation_id, timestamps, model, the null token schema, credits, per-turn
  *character lengths* only; leak-tested: no class names, code, or auth). Check 2 is
  therefore ◻ n/a rather than a verbatim-copy pass — the one place the golden set
  departs from "copy bytes," forced by the store's shape.

## Closure

- **Credits parser shipped** (capture-precision-fixes): `parse_kiro_cli_credits`
  reads `conversations_v2` **read-only**, a closed whitelist of numeric/metadata
  fields, never `auth_kv` or a prompt/response body. Credits are a **distinct row
  kind** (`credits-<month>.jsonl`, `schema.make_credit`, `method="estimated"`,
  recorded not priced). run-003 captured **12** credit rows (V5) / **15** (V5b).
- **Exact-token route CLOSED** ([P2 proxy probe](2026-07-28-kiro-proxy-probe.md)):
  kiro-cli routes to AWS CodeWhisperer/Q — no base-URL env, wrong protocol, cage's
  proxy can't MITM TLS, and no tokens in the response anyway. Kiro CLI cost is
  **credit-derived and `estimated`, by vendor design**. There is no `measured` path.
- **Honest limit:** token counts remain unrecoverable; token reconciliation stays
  `n/a` by construction — never faked.
