# Changelog

Full release notes. The README keeps a one-line summary per version; the detail lives here.

## v0.10.2 — Kiro hook format fixed (it never fired before)

Kiro's Agent Hook file is **one hook per file** — the file *is* the hook object (`{name, version, description, when:{type}, then:{type, command}}`), not the `{"version":"v1","hooks":[…]}` container with `trigger`/`action` keys that Cage was writing. That wrong shape (plus a `SessionStart` trigger **Kiro doesn't have** — its events are `agentStop`/`promptSubmit`/`pre|postToolUse`/`file*`/`pre|postTaskExecution`/manual) meant the Kiro hook silently never ran. `cage setup` now writes a single **`agentStop`** hook in the correct format; because each fire re-imports Kiro's whole usage log (deduped by call id), that one hook is both the real-time and the backfill path — the next turn covers anything the prior one missed (the same self-backfilling pattern Copilot uses). The file is cage-owned, so re-running setup overwrites it wholesale and heals any old-format install. Re-run `cage setup --wire-only` to pick up the working hook.

## v0.10.1 — release process codified: GitHub release is the publish trigger, never publish from local

Releases now ship a **GitHub release**, and the GitHub release *is* the PyPI publish: creating it fires `.github/workflows/publish.yml` (`on: release: published`), which builds and uploads via **OIDC trusted publishing** (no stored token, nothing to leak). The one true flow — bump `__version__` + changelog, push `main`, tag `vX.Y.Z`, push the tag, `gh release create vX.Y.Z` — is now a durable rule in `CLAUDE.md`. **No more `uv publish`/`twine` from a laptop;** CI is the sole publisher (`skip-existing: true` keeps it idempotent). A version on PyPI with no matching GitHub release/tag is a release bug.

## v0.10.0 — real-time per-turn capture (Stop hook), repo-level skills, `state/` gitignored

Claude Code **and Codex** spend now lands *as each turn ends*, not only when you open the next chat. For Claude, `cage setup` wires a **Stop** hook (`cage hook-stop`) that imports the just-finished turn from the live transcript; for Codex it wires a turn-scoped **Stop** hook in `.codex/hooks.json` that re-imports the rollouts Codex writes to disk. Both are idempotent (deduped by call id / turn uuid), so they stack safely on top of the SessionStart-backfill safety net and (Claude) the best-effort SessionEnd. Before this, the only reliable trigger was the *next* session's SessionStart-backfill, so a session's tokens stayed "pending" until you started a new chat. `cage doctor`'s metering matrix now shows `real-time Stop + backfill ✔` for both log-bearing agents.

**Copilot CLI is now metered too** — it persists a per-session usage log (`~/.copilot/session-state/*/events.jsonl`, whose `session.shutdown` event carries `modelMetrics`), so `cage import --agent copilot` records its spend (per-model usage nests under `modelMetrics.<model>.usage`; on this machine Copilot runs `claude-haiku-4.5`) and `cage setup` wires `agentStop`/`sessionStart`/`sessionEnd` hooks at the **user level** (`~/.copilot/hooks/cage.json` — verified the only location the local CLI fires from; repo `.github/hooks/` does not fire even when committed), moving Copilot off proxy-only onto a real import path. Because Copilot writes its `session.shutdown` (the usage) *after* its own hooks fire, a session's tokens land on the **next** Copilot run — its `sessionStart`/`agentStop` import picks up the prior session's shutdown (the standard backfill pattern; cage never sweeps another agent's data from a hook).

**Kiro is now metered too, completing the four-agent set** — Kiro persists a coarse usage log (`kiro.kiroagent/dev_data/tokens_generated.jsonl`: one object per call, prompt tokens reliable, output often 0, model the generic `"agent"`) and supports Agent Hooks, so `cage setup` wires a real-time **Stop** Agent Hook (`.kiro/hooks/cage.kiro.hook` → `cage import --agent kiro`) and `cage import --agent kiro` records it. With this, **every surface in `agents.SURFACES` is now log-bearing** — none is proxy-only. And the hook coverage is now **symmetric across all four**: each agent gets both a real-time per-turn hook (Claude/Codex/Kiro `Stop`, Copilot `agentStop`) *and* a SessionStart-style backfill safety net, so `cage doctor`'s matrix reads `real-time Stop + backfill ✔` for every one.

**Hooks and MCP servers are now wired with the *resolved absolute* `cage` path, not a bare `cage`** — GUI-launched agents (the Kiro IDE, the Copilot extension, a Codex app) run hooks with a minimal PATH that omits `~/.local/bin`, so a bare `cage` failed silently with "command not found" and nothing was captured (only Claude Code, terminal-launched, worked). `cage setup` now resolves the binary at wire time and **heals** an existing bare-`cage` install in place (no duplicate entries) — re-run `cage setup` once to upgrade.

**Each agent's hook imports only its own log** (`cage import --agent <itself>`) — cage never sweeps another agent's data from a hook, so capture stays scoped and predictable (re-running setup migrates any older all-agent-sweep command back to the per-agent import). The `cage setup` wizard now **defaults to setting up *all* agents** (`cage setup --all` non-interactively) rather than making you pick one — wiring every agent is a single step. Internally, agent wiring is now **one `<agent>wire.py` per agent** (`claudewire`/`codexwire`/`copilotwire`/`kirowire`, each exposing `install`/`status`/`backfill_status`/`realtime_status`), dispatched from `agents.py` — a standing convention so integrating a new agent means adding one wire file, nothing more.

Finally, a **consumer on/off switch for auto-capture**: `[capture] enabled = false` in `policy.toml` (or `CAGE_CAPTURE=0`, which overrides policy) makes the hook-driven `cage import` a no-op — pause metering without unwiring any hooks; `CAGE_CAPTURE=1` forces it back on for a single run. The proxy stays the higher-fidelity fallback where Kiro's log is too thin.

**Pricing refreshed for all four agents' models** — the bundled `policy.toml` now carries current Anthropic rates (Opus 4.8 corrected from a stale $15/$75 to $5/$25; Sonnet 4.6, Haiku 4.5) for Claude Code + Kiro, and the OpenAI `gpt-5` family (`gpt-5`, `gpt-5-mini`, `gpt-5.5`, `gpt-5.4`, `gpt-5.3-codex`) for Codex + Copilot, so their traffic costs out instead of reading `UNPRICED`. Two Codex metering bugs fixed in the same pass: the model id (declared once in a `turn_context` record) is now carried onto the usage events instead of coming through empty, and per-turn usage reads `last_token_usage` instead of summing the cumulative `total_token_usage` — which had inflated a real ~12M-token session to a bogus 210M.

**The /cage skill can now be installed repo-level instead of machine-wide** — `cage setup --repo-skill` (or pick "project" in the wizard) writes the skill into the repo (`.claude/skills/`, `.codex/skills/`, `.github/prompts/`, `.kiro/steering/`) so it's committed and the whole team gets it, with nothing in your home dir; global stays the default. Also: the `.cage/.gitignore` now excludes `state/` (machine-local hook buffers — pending edits, session state), and `cage init`/`cage setup` heals older footprints that were missing it. Re-run `cage setup --wire-only` in an existing project to pick up the Stop hook.

## v0.9.0 — ledger scale: partitions, scope, team aggregation

The ledger now survives heavy/multi-dev/monorepo use. Writers append to month-partitioned shards (`calls-YYYY-MM.jsonl`, same for receipts/tasks) chosen from each row's own `ts`; readers glob + concatenate (legacy single files still read), and `--since` skips whole below-cutoff months instead of re-scanning a year. Calls/receipts carry an optional counts-safe `scope` (top-level changed dir, same PII guard as tasks); `report`/`attrib`/`budget`/`matrix --scope <dir>` slice a monorepo component (no flag ⇒ byte-identical). `cage ledger-sync` distributes local rows into `refs/notes/cage-ledger` (dry-run by default, CI-sole-writer like `notes-sync`), and `report`/`attrib --team` read the merged team view (falling back to local when empty) — rolled up by `scope`, never per-person. A one-line stderr warning fires when the ledger crosses a derived size (≈2 heavy solo-years; `[ledger] warn_mb` overrides) — warn-only, never blocks a derive.

Also in this release: **reliable hookless capture is now the default** — `cage setup` wires a **SessionStart-backfill** for the two transcript agents (Claude Code's `.claude/settings.json` and Codex's `.codex/hooks.json`, which share a hook schema) that imports the *previous* session on the next start, ordered before the spend banner. SessionEnd stays wired but is best-effort (it never fires on a killed/crashed/idle session); running both is safe because `cage import` dedupes by call id. Copilot/Kiro have no transcript, so their reliable path stays the proxy. `cage doctor`'s metering matrix now names the mechanism actually wired per agent (SessionStart-backfill / SessionEnd / proxy) and flags any log-bearing agent left without a reliable trigger. All four agents stay first-class.

## v0.8.0 — one hookless front door for all four agents

`cage import [--agent claude|codex|copilot|kiro|all]` (default `all`) unifies hookless metering: Claude Code and Codex import the usage transcripts they write to disk, while Copilot and Kiro — which expose no usage log — print their supported proxy fallback (`cage meter -- <cmd>`) instead of being silently skipped. Additive to hooks/MCP and deduped by call id (a turn seen by both a hook and an import counts once); the old `import-claude`/`import-codex` stay as aliases. `cage doctor` now renders a four-agent metering matrix (hook / import / proxy per agent).

## v0.7.1 — docs + the four-agents invariant

README "What's new" and test counts brought current, and a durable rule recorded for every agent (`CLAUDE.md` + `AGENTS.md`): Cage keeps **Claude Code · Codex · Copilot · Kiro** first-class on every surface, and each release must update this changelog.

## v0.7.0 — one front door + hookless metering

`cage setup` is now the single onboarding command: `--project-only` (scaffold + graphify, no global skill), `--wire-only` (agent wiring only), and `--status` (report wiring) absorb the old `adopt`/`hooks` verbs, which are gone. Internal `hook-*` entrypoints are hidden from `--help`. Ships alongside hookless transcript metering (`cage import-claude`), a per-call pricing fallback, and the bare-`cage` spent-and-saved headline. All four agents (Claude Code · Codex · Copilot · Kiro) stay first-class.

## v0.6.0 — authorship attribution

`cage origin <sha>` answers *who wrote which files in which commit* — a fourth append-only record captured by a `PostToolUse` hook (transcript fallback), with `hooked`/`transcript`/`heuristic` method ranks and `human`/`agent`/`agent-autonomous` origins. `unknown` is read-derived from absence, never a stored row; `origin=human` only via explicit attestation. Distributed over `refs/notes/cage-provenance` (CI is the sole writer); `cage verify` is report-only and never gates the build.

## v0.5.0 — DX + concept explainers

A constants/query-help layer and `cage query` concept topics: ask *how cage works*, not just *how a number is computed*, all deterministic and `$0`.

## v0.3.0 — the Tier-1 human axis

`cage human` / `cage trend` price agent-vs-human in **dollars and hours**, anchored to a git-aware task record; a `minutes` unit, a `[human]` rate table with confidence laddering, and `CAGE_HUMAN_RATE`. Third-party tools join via the external adapter (`cage graphify`).

## v0.2.0 — attribution + the counterfactual matrix

Marginal-by-fixed-order attribution, the 2ⁿ permutation table, ROI per tool, and the `measured`/`modeled`/`estimated` discipline — the differentiator.

## v0.1.0 — substrate + meter

The call/receipt contract, the append-only ledger, `policy.toml`, and `cage report`.
