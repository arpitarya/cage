# Claude Code prompt — make reliable hookless capture the default in `cage setup`

Self-contained. Paste into Claude Code from the cage repo root.

## The finding (why this exists)

Field-tested on a fresh repo: Claude Code's **`SessionEnd` hook is unreliable** — it
only fires on certain clean terminations (`/exit`, logout, clear). On a killed
terminal, an idle session, or a crash it never fires, so `cage hook-session-end` never
records and the ledger stays empty even after a real session. Proof: an already-ended
session's transcript (28 usage rows) was still absent from the ledger until
`cage import-claude --project .` was run by hand, which imported it correctly and
priced it ($0.50, family-fallback working).

Conclusion: the transcript is **always on disk** regardless of how the session ends,
and `cage import-claude` is idempotent (dedupes by call id). So the reliable capture
trigger is **`SessionStart` backfill** — import the *previous* session on the next
start — not `SessionEnd`. Promote hookless import from "fallback" to a **default-on**
capture path wired by `cage setup`, for all four agents where a reliable trigger
exists.

## Hard invariants

- **All four agents first-class** — Claude Code, Codex, Copilot, Kiro. Each must have a
  documented reliable-capture story after this change.
- **Additive, never a replacement** — keep `SessionEnd`/`hook-session-end` wired (it's
  harmless and idempotent); this *adds* the SessionStart backfill, doesn't remove
  anything. Both running is safe (dedupe by id).
- **$0 / stdlib, fail-open, idempotent, deterministic, counts-never-content** — as ever.

## What to build

1. **Wire SessionStart backfill for Claude Code.** In the Claude wiring
   (`claudewire.py` / `agents.install` / wherever `cage setup` writes
   `.claude/settings.json`), add `cage import-claude --project .` as a SessionStart
   hook command, ordered **before** `cage hook-session-start` so the banner reflects
   the just-backfilled spend. Idempotent install (don't duplicate the command on
   re-run; detect the existing entry). Reference shape:
   ```json
   "SessionStart": [{"hooks": [
     {"type": "command", "command": "cage import-claude --project ."},
     {"type": "command", "command": "cage hook-session-start"}
   ]}]
   ```
2. **Per-agent reliable-capture parity.** Verify each agent's options and wire the best
   reliable trigger `cage setup` can install:
   - **Codex** — if Codex CLI exposes a session/start lifecycle hook, wire
     `cage import-codex` analogously; if it does not, `cage setup` must print the
     reliable fallback (scheduled/manual `cage import-codex`, or proxy). Verify
     empirically — don't assume.
   - **Copilot / Kiro** — no transcript (proxy is their path); `cage setup` must state
     that plainly and emit the exact proxy command. No silent gap.
3. **`cage doctor` reflects it.** The four-agent metering matrix shows, per agent, the
   capture mechanism actually wired (SessionStart-backfill / SessionEnd / proxy /
   manual) and flags any agent left without a reliable trigger.
4. **Docs.** Update the agents/wiring doc and any "metering" concept entry to state
   that SessionEnd is best-effort and SessionStart-backfill is the reliable default;
   note import idempotency makes running both safe.

## Acceptance

- `cage setup` / the Claude wiring writes the SessionStart backfill ahead of the
  banner, idempotently (re-running setup doesn't duplicate it); a test asserts the
  resulting `settings.json` shape and the no-duplicate-on-reinstall behavior.
- Per-agent: tests assert Claude gets the backfill hook; Codex gets either a wired
  trigger or the printed fallback; Copilot/Kiro get the proxy instruction — never a
  silent skip.
- `cage doctor` matrix shows the wired mechanism per agent.
- Existing hook entrypoints and import commands unchanged and still passing.
- `just test` green; no existing plan-number assertion changes; bump `__version__`,
  add a README "What's new" line, and refresh the test count (release-hygiene rule in
  CLAUDE.md).

## Working agreement

Plan before code (files touched, the per-agent wiring decisions, the idempotency
mechanism, the test list) and stop for my review. Empirically verify Codex's hook
surface before claiming it has or lacks one. Don't start until I approve the plan.

## Out of scope

The org gateway; removing or redesigning SessionEnd; any network or daemon. If an
agent has no reliable trigger `cage setup` can install, document the manual/proxy path
rather than faking automation.
