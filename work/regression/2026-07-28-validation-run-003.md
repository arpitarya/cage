# Golden-set validation — run-003 (Phase 1 re-run, post-fix, 2026-07-28 pm)

**Report sha256 (body below the marker):** `ddf8c9a993a9afc3e4938526ddd6bccd44ec78f4db7356a650cfe027fa347f18`
_Hashed range: from the newline after the marker to EOF; this header is excluded._

<!-- HASH-COVERS-BELOW -->
**Run:** run-003 · **Phase:** 1 re-run — post capture-precision fix · **Date:** 2026-07-28 (pm) · **Cells:** V1–V5b
**Machine:** darwin 25.3.0 · cage 0.36.0 (working tree, uncommitted) · Python 3.9.6 · claude 2.1.207 · copilot 1.0.70 · kiro-cli 2.14.2 (Kiro IDE 0.12.333 also present).
**Config file in use:** workspace `.cage/cage.toml` active, **no** legacy `policy.toml` shadow — clean; check 8 green on every cell.
**Isolation:** every `cage import` used `--ledger captures/<run-id>/ledger` with `CAGE_BASE` pointed at the scratch ledger; real `~/.cage` never named. Source-log shas unchanged before==after on every captured file (check 2 green throughout).
**Verdict:** scripted cells V1–V5b **CLOSED green** — copilot 8/8 exact, kiro credits captured, claude byte-identical. Full fix list: [capture-precision fixes](2026-07-28-capture-precision-fixes.md).

## 1. Results this run (post-fix)

| cell | result |
|---|---|
| **V3 copilot/off** | **8/8**; cage re-imports the logs to **exactly 227,298**; a fresh paid run also 8/8 (recount == cage) |
| **V4 copilot/on** | cage → **exactly 233,675**; re-import idempotent (+0 rows) |
| **V5 kiro/off** | **pass** — SQLite parser records **12 credit rows**; check 4 ✅; check 5 ◻ n/a (tokens null — no token total to reconcile); check 2 ◻ n/a |
| **V5b kiro/on** | **pass** — **15 credit rows**; same honest limits |
| **V1 claude/off** | **byte-identical** — 381,813, 17 rows |
| **V2 claude/on** | **byte-identical** — 565,637, 19 rows |

Copilot deltas reconcile to the token; Kiro is captured as credits (estimated, unpriced —
tokens are unrecoverable, stated as a limit, never faked); claude is untouched.

## 2. Self-heal proof (real session `8073abba`)

Legacy row 70,071 → re-import fixed parser → **107,581 exact** (+37,510) → third import
**+0**. No double count — the fix recovers exactly the lost amount and never re-adds it.

## 3. Findings status touched this run

One line each; the full lifecycle and current status live in each finding doc (linked).

- **Copilot resumed-session undercount — RESOLVED, verified here.** Fixed cage reaches
  the exact copilot totals (227,298 / 233,675, 8/8) and the self-heal (§2) is proven. →
  [finding](2026-07-28-finding-copilot-resumed-undercount.md)
- **Kiro CLI credits — captured here.** The SQLite credits parser records 12 (V5) / 15
  (V5b) credit rows; token reconciliation stays `n/a` by construction (the store holds no
  token counts). → [finding](2026-07-28-finding-kiro-cli-sqlite-credits.md)
- **Declared `[sources] surface` collision — RESOLVED.** Re-checked against fixed cage: a
  colliding declared `surface="cli"` now upgrades the built-in (declared wins). →
  [finding](2026-07-28-finding-surface-restamp-collision.md)

## 4. What this run did NOT cover, and why

- **Manual cells V6–V11** (VS Code / IDE surfaces) — extensions can't be driven
  headlessly; the human sweep (`manual/vscode-checklist.md`) is a distinct future run.
- **Phase 2** — the full multi-agent sweep awaits Arpit's go.
- **Graphify A/B through the agents** — still 0 rows because the agents don't shell out to
  graphify on their own; the driver change to force a graphify query is a Phase 2 item. →
  [finding](2026-07-28-finding-graphify-ab-no-fire.md)
