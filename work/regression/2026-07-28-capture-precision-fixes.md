# 2026-07-28 — Capture-precision fixes (post golden-set Phase 1)

Fixes for what golden-set Phase 1 found, plus two standing directives. Baseline report:
[`2026-07-28-validation-report.md`](2026-07-28-validation-report.md) (sha256
`3abe494f0d60…`). Spec: `docs/capture-precision.{plan,handoff}.md`. Cage tree
**uncommitted** (per directive); this entry records the fixes as built + verified.

## STEP 0 — Kiro token probe (the gate)

- Ran `kiro-cli chat --no-interactive --model claude-haiku-4.5` (explicit non-`auto`) in
  an isolated cwd, then read `data.sqlite3` read-only.
- **Result: every token field null** (`total_tokens`/`uncached_input_tokens`/
  `output_tokens`/`cache_read/write_input_tokens` = `None`); only signal is credits
  (0.0188) + `context_usage_percentage` (7.356). `telemetry.enabled` unset.
- New vs baseline: an explicit model makes `model_id` a real name, not `"auto"`.
- **Gate NOT triggered** → the SQLite parser / content-guard / credits-row items proceed.

## HIGH — Copilot resumed-session undercount (§3.1) — FIXED

- **Was:** cumulative `session.shutdown` #2 collided by id with #1 → dedup-dropped →
  16–18% undercount (V3: 189,788 vs 227,298 truth).
- **Fix:** `transcript.parse_copilot_calls` emits per-shutdown **delta** rows; id carries
  the shutdown ordinal (**ord 0 byte-identical** to the legacy id → history self-heals);
  `totalPremiumRequests` (also cumulative — verified 0.33→0.66 on real V3 `8073abba`)
  gets the same delta treatment. Append-only; no row mutated. See
  [ADR 0004](../archive/adr/0004-append-only-delta-rows-and-separate-by-schema.md).
- **Self-heal proof (real session `8073abba`, executed):** legacy row 70,071 →
  re-import fixed parser → **107,581 exact** (+37,510, the exact undercount) → third
  import **+0**. V3 would go **8/8**, tokens_in **227,298**.
- Tests: `test_transcript.py` — cumulative-sum · re-import-zero · **legacy self-heal** ·
  premium-not-multi-counted.

## HIGH — Kiro CLI usage invisible (§3.2–§3.4) — FIXED (as credits)

- **Was:** cage read 0 rows from the SQLite store (wrong location + wrong format).
- **Fix:** `transcript.parse_kiro_cli_credits` — **read-only** (`mode=ro&immutable=1`),
  reads only `conversations_v2` (never `auth_kv`) and a closed whitelist of
  numeric/metadata fields inside `value` (never a prompt/response body — a test asserts
  no content leaks). Credits are a **distinct row kind** (`credits-<month>.jsonl`,
  `schema.make_credit`, `method="estimated"`, **recorded not priced**), never a
  `tokens_in=0` call row. Wired via a `[sources] format="kiro-cli"` custom source →
  `_ingest_credits`. Resume-safe (last-write-wins per session, no double-count).
- **Honest limit (stated, not hidden):** token counts remain **unrecoverable** — the
  store holds none. Cost, if ever produced, is credit-derived and `estimated`. V5/V5b
  now capture **credit rows**; token reconciliation stays `n/a` by construction.

## MED — surface-restamp collision (§3.5) — FIXED

- A declared `[sources] surface` colliding by `(path, glob)` with a built-in was silently
  dropped. Now the **declared value wins** (upgrades the colliding entry) — resolution
  change, append-only-safe.

## MED — graphify shim recursion (§3.5) — FIXED

- Two stacked interceptors (fresh + stale `cage adopt`) each stripped only their own PATH
  dir → resolved to each other → hang. Now the shim skips **every** cage interceptor when
  resolving the real binary, refuses to fall back to the bare name (exit 127, no
  re-entry), and adds a `CAGE_GRAPHIFY_SHIM` re-entry guard. Verified: stacked shims + a
  real binary resolve to REAL, no hang; only-interceptors exits 127.

## Directive A — `cage.toml [sources]` is the ONLY path authority (§3.6) — DONE

- `resolve_log_sources` reads only `[sources]`; the registry is a **seed** materialized by
  `cage setup` (project + global). Empty `[sources]` captures **nothing, loudly**.
  Mitigation: `cage doctor --paths` drift check vs defaults + announces now-ignored env
  vars; `cage setup --sync-sources` refreshes preserving user entries. Env removed from
  path resolution; test harness migrated. (Arpit chose **full removal**.)

## Directive B — hashed validation reports published into cage (§3.7) — DONE

- `cage-lab/golden/publish_report.py`: sha256 over the report body (from the
  `<!-- HASH-COVERS-BELOW -->` marker to EOF; header excluded, documented in the sidecar),
  header prints the hash, copied here dated + `latest-validation-report.md` + `.sha256`,
  index row added, **append-only** (`-2` suffix on a same-day re-run).

## Status of the paid re-run (Step 6)

- The **deterministic** proofs are done: full suite **846 green**; the Copilot self-heal
  proof reaches the exact V3 number on real data. The **paid** 6-cell re-run (failures
  first: V3/V4 → V5/V5b → V1/V2) requires updating `cage-lab/golden/drive.py` for
  Directive A (materialize `[sources]` per cell) + the Kiro checks (credit rows now
  appear) and spending real agent calls — gated on Arpit's go-ahead.
