# Finding — Kiro capture is empty in practice (`kiro-empty`)

**Severity:** HIGH · **Status:** ✅ RESOLVED (**v0.34.0**) · **Surface:** kiro capture / `cage doctor`

| field | value |
|---|---|
| Observed in | [lab-run-001](2026-07-22-lab-run-001.md) |
| Fix shipped | **v0.34.0** — `capture-quality` doctor check (`doctorcmd._capture_quality`) |

## Status now

RESOLVED. Kiro's token log is genuinely coarse and input-only, so a *thin* capture
is expected — the fix is a doctor check that distinguishes "kiro log found but ~0
tokens" from a healthy agent, and points at the higher-fidelity proxy fallback.

## Evidence (as observed 2026-07-22)

16 calls, **198 input tokens, 0 output**, from
`~/Library/Application Support/Kiro/User/globalStorage/kiro.kiroagent/dev_data/tokens_generated.jsonl`
(`files: 1`). Kiro's token log is coarse and input-only, so even what's captured
understates cost (0 output tokens ever). At observation time F2's
`captured:false` hid this behind the same flag codex and copilot (which *do* have
data) also showed.

## History

**2026-07-22 (observed, lab-run-001):** 16 calls / 198 input / 0 output from the
macOS Library Kiro globalStorage log. Proposed: doctor should distinguish "found
but empty" from healthy and recommend the proxy fallback; confirm the Library path
is the right current Kiro-on-macOS location.

**v0.34.0 (RESOLVED):**

- New `cage doctor` check (`capture-quality`, `doctorcmd._capture_quality`) flags
  any agent with calls captured but `tokens_out == 0` across all of them —
  deliberately separate from the existing `files == 0` gate, so a genuinely-empty
  kiro log stays silent (as designed) while a *thin* one now warns and points at
  `cage data meter -- <cmd>` / `cage data proxy`.
- Re-tested against this machine's real kiro log: **16 calls, 198 input, 0 output**
  — an exact match to the evidence, confirming the fix targets the actual case.
- Path question resolved: `/usr/local/bin/kiro` is a launcher shim for the same
  `Kiro.app` (a VS Code fork) — there is no separate CLI-Kiro data store. The
  `~/Library/Application Support/Kiro/...` path is the correct, current, and only
  location; no "unverified" caveat needed.
- Import-time logging added: one `debuglog.event(event="kiro-src", ...)` per import
  run recording `exists`/`bytes`/`rows_parsed`/`tokens_in`/`tokens_out` — read
  unconditionally, so "found but thin" stays visible even on a run where nothing
  changed.

## Logging that shipped for this finding

Log the resolved kiro `src`, whether it existed, byte size, rows parsed, and
tokens summed — so "found but empty" is visible (the `kiro-src` event above).
