# Finding — declared `[sources] surface` lost on collision with a built-in

**Severity:** LOW · **Status:** ✅ RESOLVED (fixed 2026-07-28) · **Surface:**
config / `[sources]` resolution (kiro IDE token log)

| field | value |
|---|---|
| Observed in | [run-002](2026-07-28-validation-run-002.md) (IDE token-log nuance) |
| Fix shipped | [capture-precision-fixes §MED surface-restamp](2026-07-28-capture-precision-fixes.md) |

## What happened (pre-fix)

- On the IDE token log the v0.36 `surface="cli"` restamp worked on **distinct**
  content (rows → `surface="cli"`), but was **silently lost** when a declared source
  collided with a built-in source. Only bit in the overlap case; a genuinely
  distinct store wouldn't collide.

## The fix + re-check (2026-07-28, fixed cage 0.36.0 working tree)

- The collision is a source-**definition** collision by `(path, glob)` resolved in
  `paths.resolve_log_sources._emit`. A colliding declared `surface` now **upgrades
  the built-in entry — declared wins** — instead of dropping the whole entry.
- Verified two ways:
  1. unit + import tests green —
     `tests/test_sources.py::test_declared_surface_wins_on_builtin_collision`
     (resolution: declared wins) and
     `::test_custom_tool_surface_restamps_alongside_agent` (import: rows actually
     carry `surface="cli"`);
  2. live reproduction — declaring `[sources.kiro] surface="cli"` on the shipped
     built-in `tokens_generated.jsonl` path now resolves to one source with
     `surface='cli'` (pre-fix it resolved with `surface=''`).
- No longer LOW-open; a closed finding.
