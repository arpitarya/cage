# Handoff Spec — Port graphify's skill+hook pattern to cage & fux

**Status:** spec for review (you chose: all 4 pieces · both repos in parallel · spec-first)
**Author:** builder pass, 2026-06-29
**Scope:** replicate graphify's (1) build-time skillgen renderer, (2) behavioral-nudge hooks, (3) always-on block generation, (4) platform breadth — onto **cage** and **fux**, adapted to each repo's existing infra. **Plus (§11–§13): enhance the existing hooks, skills, and CLI in both repos** — not just add the renderer.

> **Two parts.** Part A (§0–§10) is the *port* of graphify's pattern. Part B (§11–§13) is the *enhancement* of what cage/fux already have. The renderer (Part A) is the delivery mechanism for several Part-B enhancements (single-sourced hook payloads, multi-host skills), so build the renderer first — but the enhancements stand on their own value and several need no renderer.

---

## 0. The one decision that shapes everything

graphify's pattern is **"one human-edited source → N machine-rendered, drift-guarded agent artifacts."** The renderer (`tools/skillgen/`) is the spine; hooks, always-on blocks, and platform breadth are all just *artifact families* that the same renderer emits and the same `--check` guards.

So the port is **not** four independent features. It's **one renderer per repo** that happens to emit four artifact families. Build the renderer first; the other three pieces are its outputs.

**Principal call up front (read before costing this):** cage and fux are *not* symmetric targets.

- **fux is a near-perfect fit.** It's a knowledge engine that answers questions an agent would otherwise grep for. graphify's "you MUST query the tool before reading raw files" nudge maps 1:1. Port all four pieces faithfully.
- **cage is a partial fit.** cage is a *passive cost ledger* — it does not answer questions that replace grep/Read, so a graphify-style "use cage before X" PreToolUse nudge would be **cargo-culting**. cage already has the cleaner half of the pattern (4 first-class agents via `<agent>wire.py` + `_WIRE`). For cage, port pieces **1, 3, 4 faithfully**, and **redefine piece 2** to fit what cage actually is (budget/spend nudge, not a query nudge). Details in §4.2.

Don't skip §4.2 — forcing graphify's exact hook into cage is the most likely way this port goes wrong.

---

## 1. What graphify actually does (the reference, condensed)

Build-time only, **never shipped in the wheel**:

```
tools/skillgen/
  platforms.toml        # manifest: one [platform.<key>] table per target host
  gen.py                # renderer + 6 validators + CLI (--check/--bless/--audit-…)
  fragments/            # the ONLY human-edited source
    core/core.md        #   shared skill template with @@SLOT@@ placeholders
    dispatch/*.md       #   per-host "how to fan out subagents" deltas
    shell/*.md          #   posix vs powershell install snippet
    extra/*.md          #   optional tail sections (per-host)
    always-on/*.md      #   CLAUDE.md / AGENTS.md / steering blocks (source)
    references/…         #   the progressive-disclosure sidecar bodies
  expected/             # blessed golden snapshots (flat, fully tracked)
```

**Committed outputs** (what the wheel ships, what installers copy):
```
graphify/skill*.md                 # one rendered SKILL.md per platform
graphify/skills/<host>/references/ # rendered sidecar per split platform
graphify/always_on/*.md            # rendered always-on blocks
```

**Render model** (`gen.py`):
- `load_platforms()` → `Platform` records from TOML.
- Two buckets: `split` (lean core + `references/` sidecar, progressive disclosure) and `monolith` (single inline body, legacy hosts).
- `_render_core()` reads `core/<core>.md`, fills `@@FRONTMATTER@@ @@INSTALL@@ @@DISPATCH@@ @@QUERY_STUB@@ @@HOOKS_TARGET@@ @@EXTRA@@` from per-platform fragments; raises if any `@@SLOT@@` is left unfilled.
- `render_always_on()` emits the always-on blocks through the **same** drift guard.
- `check()` byte-diffs the live render against both the committed artifacts **and** `expected/`; exits 1 on any drift. `bless()` rewrites `expected/`.
- Extra validators: `--audit-coverage` (every heading of the host's prior body single-homes in the render), `--schema-singleton`, `--monolith-roundtrip`, `--always-on-roundtrip`. These are graphify-migration-specific; **cage/fux only need `--check` + `--bless`** on day one.

**Installer side** (`__main__.py`): `graphify install` / `graphify <platform> install` copies the rendered SKILL.md to the host's skills dir, injects the always-on block into `CLAUDE.md`/`AGENTS.md` via `_replace_or_append_section` (idempotent, marker-fenced), wires the `PreToolUse` hook into `.claude/settings.json`, and stamps `.graphify_version` for stale-install warnings.

**The behavioral nudge** (the actual product mechanism): two `PreToolUse` hooks on `Bash` (catches `grep|rg|find|fd|ack|ag`) and `Read|Glob`. When `graphify-out/graph.json` exists, they inject `additionalContext`: *"MANDATORY: run `graphify query` before grepping/reading raw files."* Fail-open, nudge-not-block.

---

## 2. Naming the shared concept (do this once, in both repos)

Both repos already have the install plumbing; what's missing is the **rendered-from-one-source** discipline. Use identical structure in both so the pattern is learnable once:

| graphify | cage | fux |
|---|---|---|
| `tools/skillgen/` | `tools/skillgen/` | `tools/skillgen/` |
| `platforms.toml` | `platforms.toml` | `platforms.toml` |
| `gen.py` | `gen.py` | `gen.py` |
| `fragments/` | `fragments/` | `fragments/` |
| `expected/` | `expected/` | `expected/` |
| rendered → `graphify/skill*.md` | rendered → `cage/data/skills/…` | rendered → `fux/data/skills/…` |
| `graphify/always_on/*.md` | `cage/data/steering/…` + always-on | `fux/data/…` always-on |

**Constraint inherited from both repos:** `$0`, stdlib-only, deterministic. graphify's `gen.py` is already pure stdlib (`tomllib`, `re`, `pathlib`) — it ports without adding a dependency. Keep it that way; this is non-negotiable in cage (`dependencies = []`) and fux.

---

## 3. Piece 1 — the skillgen renderer (build first, both repos)

### 3.1 What you're replacing
- **cage today:** `cage/data/skills/{cage,cage-doctor}/SKILL.md`, `data/prompts/*.prompt.md`, `data/steering/*.md` are **hand-authored per agent**. The cage skill body for claude, the codex skill, the copilot prompt, and the kiro steering doc drift independently. That's the problem the renderer fixes.
- **fux today:** `fux/data/skills/<name>/SKILL.md` (plan/adr/trace/critic/fux/…) hand-authored; `data/copilot/prompts/` separate. Same drift risk across surfaces.

### 3.2 Target
One `core.md` per *skill* with `@@SLOT@@`s for the per-host deltas (trigger syntax, dispatch idiom, install snippet, steering-vs-skill framing), rendered into every host's committed artifact, guarded by `expected/` + `--check`.

### 3.3 Concrete steps (per repo)
1. Copy graphify's `tools/skillgen/{gen.py,platforms.toml}` as the starting skeleton. Strip the graphify-migration validators (`--audit-coverage`, `--monolith-roundtrip`, `--schema-singleton`, `--*-roundtrip`) — keep only `render_all`, `write_artifacts`, `check`, `bless`, and `main`. This cuts gen.py from ~1100 lines to ~250.
2. Rewrite `platforms.toml` for the repo's real targets (see §6 breadth table). Each `[platform.<key>]` declares: `bucket`, `skill_dst`, `core`, `refs_dst` (split only), `name`, `description` (**verbatim per host — this is the trigger string, never auto-edit it**), `dispatch`, `shell`, `claude_md`/steering flag, `hooks_variant`.
3. Author `fragments/core/core.md` from the *current* hand-written skill body, replacing the per-host bits with `@@SLOT@@`s. For cage, one core per skill: `cage`, `cage-doctor`. For fux, one core per skill you want unified (start with `fux`, then `critic`, `distill` — not all 12 at once).
4. Author the delta fragments (`dispatch/`, `shell/`, `extra/`).
5. `python -m tools.skillgen --bless` to write the first `expected/`. **Manually diff the render against the prior hand-written bodies** before blessing — the bless is only as good as your eyeball pass here.
6. Wire `python -m tools.skillgen --check` into pre-commit **and** CI (cage already has a CI gate; fux has `fux build && fux check` — add skillgen alongside).

### 3.4 Determinism requirement
`render_all` sorts references by name and fills slots positionally — already deterministic. Keep `_normalise()` (LF newlines) so `--check` never false-positives on CRLF. Tests assert byte-exact render (mirror graphify's approach; fux/cage both already gate on determinism).

### 3.5 Done when
`--check` is green in CI, every committed skill artifact is reproducible from `fragments/`, and editing a shared line in `core.md` updates every host in one `--bless`.

---

## 4. Piece 2 — behavioral-nudge hooks

### 4.1 fux (faithful port — high value)
fux's hooks today are **capture/context** (SessionStart injects INDEX, UserPromptSubmit `hook-recall`). graphify's missing ingredient is the **enforcement nudge**: a `PreToolUse` hook that fires when the agent is about to grep/Read source and a `.fux/` substrate exists, injecting:

> *"MANDATORY: `.fux/` exists. Run `fux refs <path>` / `fux why <id>` / `fux recall \"<q>\"` before answering architecture/decision/governance questions or reading ruled files. Only grep to modify/debug specific lines."*

- **Matchers:** `Bash` (inspect command string for `grep|rg|find|fd|ack|ag`) and `Read|Glob` (inspect path; fire only for ruled/source files, suppress reads under `.fux/out/`). Copy graphify's `_SETTINGS_HOOK` + `_READ_SETTINGS_HOOK` near-verbatim, swap the payload + the existence check (`.fux/` instead of `graphify-out/graph.json`).
- Fail-open, POSIX, python3 parser (fux requires 3.11+, already a dep-free assumption).
- Wire into `fux hooks install` (`hookinstall.py` already owns `.claude/settings.json`) as a new `PreToolUse` entry alongside the existing SessionStart/PostToolUse/Stop.
- Render the hook payload text from a fragment so it's drift-guarded like graphify's.

### 4.2 cage (REDEFINED — do not cargo-cult)
**cage must not get a "query before grep" nudge** — cage answers no question that replaces grep, so the nudge would be noise the agent learns to ignore (and erodes trust in the whole hook surface). Two honest options, pick one:

- **(Recommended) Budget/spend nudge.** A `PreToolUse`/`SessionStart` nudge that fires only when `cage budget` is over threshold: *"You are at N% of this period's LLM budget (`cage report`)."* This is a real signal tied to what cage knows. Gate it behind `policy.toml [budget]` so silence = under budget.
- **(Minimal) No new nudge.** Keep cage's hooks capture-only; the port for cage is pieces 1, 3, 4 only. Defensible — cage's existing 4-agent capture wiring is already the strong part.

Either way, cage's hook fragments still flow through the renderer + `--check` so the wording stays single-sourced. Flag this divergence explicitly in `cage/docs/` (cage's constitution requires doc-sync).

### 4.3 Done when
fux: a fresh agent session that tries to grep a ruled file gets the nudge; nudge text lives in one fragment. cage: chosen option implemented, divergence documented.

---

## 5. Piece 3 — always-on blocks

graphify generates 6 always-on blocks (`claude-md`, `agents-md`, `gemini-md`, `vscode-instructions`, `antigravity-rules`, `kiro-steering`) from `fragments/always-on/*.md`, renders to `*/always_on/*.md`, and the installer injects them into the host steering file via a **marker-fenced idempotent replace** (`_replace_or_append_section`).

### 5.1 fux
- fux already injects an INDEX at SessionStart, but has **no committed always-on CLAUDE.md/AGENTS.md block generated from one source**. Add `fragments/always-on/{claude-md,agents-md}.md` → render → inject via the existing `hookinstall` path. Content: the "When to reach for Fux" + core-commands table that's currently hand-maintained in each project's CLAUDE.md.
- Reuse graphify's `_replace_or_append_section` (marker-fenced, idempotent) verbatim — stdlib, no deps.

### 5.2 cage
- cage already ships `data/steering/{cage,cage-doctor}.md` (kiro) and `data/prompts/` (copilot). Promote these to **rendered-from-fragment** outputs, and add a `claude-md`/`agents-md` always-on block cage currently lacks (the "Cage — LLM cost & savings ledger" stanza that's hand-pasted into every project's CLAUDE.md — including anton's — becomes a generated, injectable block).
- `cage setup` already copies steering/prompts; add the always-on inject step to `cage setup` (project scope) + a `cage <agent> install`-style CLAUDE.md/AGENTS.md writer mirroring graphify's `claude_install`.

### 5.3 Done when
Editing one fragment updates the CLAUDE.md stanza for every project on next `install`; injection is idempotent (re-running changes nothing); marker fences survive surrounding hand edits.

---

## 6. Piece 4 — platform breadth

graphify supports ~20 hosts. **Do not port all 20 blindly** — port the ones each tool's users actually run, and inherit graphify's per-host deltas for them. Recommended target set:

| Host | graphify | cage today | fux today | port? |
|---|---|---|---|---|
| claude | ✅ | ✅ | ✅ | keep |
| codex | ✅ | ✅ | ✅ | keep |
| copilot | ✅ | ✅ | ✅ | keep |
| kiro | ✅ | ✅ | ❌ | **add to fux** |
| agents (generic AGENTS.md) | ✅ | ❌ | ❌ | **add to both** (highest leverage — one target covers amp/droid/many) |
| gemini | ✅ | ❌ | ❌ | add (cheap: installs claude body + refs) |
| opencode | ✅ | ❌ | ❌ | optional |
| windows (powershell) | ✅ | ❌ | ❌ | add only if Windows users exist |
| droid / kilo / trae / amp / aider / devin / vscode / pi / claw | ✅ | ❌ | ❌ | defer — add per real demand |

**Sequencing:** the `agents` generic target is the single highest-leverage add for both repos (the spec'd `~/.agents/skills` + `./.agents/skills` covers every AGENTS.md-reading framework at once). Do that before the long tail. Each new host = one `[platform.<key>]` table + its delta fragments + a `bless` — that's the whole point of the renderer.

---

## 7. Build order (both repos in parallel)

Because the renderer is shared structure, build it once conceptually and apply to both:

1. **Renderer skeleton** in both repos (§3.3 steps 1–2). Verify `gen.py` imports + `--help` run with stdlib only.
2. **Unify the flagship skill** first: cage→`cage`, fux→`fux`. Author `core.md`, bless, eyeball-diff. (§3.3 steps 3–5)
3. **Wire `--check`** into pre-commit + CI in both. (§3.6) — *now the discipline is enforced; everything after is additive.*
4. **Always-on blocks** (§5) — fragment + inject + idempotency test.
5. **fux behavioral nudge** (§4.1) + **cage budget nudge or no-op** (§4.2).
6. **Breadth:** add `agents` generic target to both, then `kiro` to fux, then `gemini`. (§6)
7. **Docs + tests** in the *same* commits throughout (constitutional — see §8).

Steps 1–3 are the load-bearing slice. If you ship only those, you've captured 70% of the value (single-sourced, drift-guarded skills). 4–6 are incremental.

---

## 8. Constitutional / risk checklist (both repos enforce doc-sync)

- **Doc-sync is constitutional in both.** Every code change ships matching doc updates *in the same commit*: cage → `docs/cage-plan.md` + CHANGELOG + README test-count; fux → `docs/fux-plan.md` + `docs/fux-implementation.md` + README. The renderer itself needs a `docs/skillgen.md` design-of-record in each.
- **`tools/skillgen/` must NOT ship in the wheel.** graphify excludes it; replicate the packaging exclusion (`pyproject.toml`) so build-time source never lands in `cage`/`fux-engine` PyPI artifacts. Verify with a wheel-content test.
- **`description` strings are triggers, not prose.** They decide whether the skill fires. Preserve verbatim per host; never let the renderer normalize them. (graphify hard-codes them per `[platform]` for exactly this reason.)
- **cage release discipline:** cage's CLAUDE.md forbids hand-publishing and requires a CHANGELOG entry + README "What's new" + test-count bump per release. Any skillgen work that bumps `__version__` follows that flow.
- **`$0`/stdlib/determinism:** gen.py stays stdlib; no LLM on any maintenance path; `--check` is reproducible. This is already true of graphify's gen.py — don't regress it.
- **Devil's-advocate flags:**
  - *cage piece-2 mismatch* (§4.2) — the single biggest risk; resolved by redefining, not copying.
  - *Skill sprawl in fux* — fux has 12 skills; do **not** unify all 12 cores at once. Start with 1–3, prove the pattern, expand. Unifying a rarely-edited skill into the renderer is cost with no payoff.
  - *expected/ rot* — a blessed-but-wrong snapshot passes `--check` forever. Mitigate: the first bless requires a manual diff review (§3.3 step 5); add a test that the render still contains each skill's non-negotiable lines (graphify's `--audit-coverage` is the heavyweight version; a simple "contains these anchors" test suffices for v1).

---

## 9. Definition of done

**Per repo:**
- `tools/skillgen/` renders every committed skill/steering/always-on artifact from `fragments/`; `--check` green in pre-commit + CI; `--bless` is the only way artifacts change.
- Editing one shared line propagates to all hosts in one command.
- Always-on block injects idempotently into CLAUDE.md/AGENTS.md.
- fux: behavioral nudge fires on grep/Read of ruled files. cage: budget nudge (or documented no-op).
- `agents` generic host added; fux additionally has `kiro`.
- `tools/skillgen/` excluded from the wheel (test-verified).
- Docs-of-record + CHANGELOG updated in the same commits; tests added.

**Cross-repo:** the three `tools/skillgen/` layouts are structurally identical, so the pattern is learn-once.

---

# PART B — Enhancing the existing hooks, skills & CLI

The renderer is necessary but not sufficient — it makes the artifacts *single-sourced*, it doesn't make them *better*. Below are concrete upgrades grounded in what each repo ships today. The unifying lens is graphify's design principle that's strongest in graphify and weakest in cage/fux: **design for the agent-as-user** — typed/JSON output, structured hook envelopes, explicit errors, discoverable help.

---

## 11. fux — enhance hooks, skills, CLI

### 11.1 Current state (verified)
- **Hooks** (`fux/hooks.py`, wired by `hookinstall.py` into git + claude/codex/copilot): `session_start`→inject INDEX, `post_tool_use`→drift reminder *after* editing a governed file, `stop`→validate (exit 2 only in strict mode), `session_end_propose`, `user_prompt_recall`. They `print()` plain text to stdout.
- **Skills** (11): adr, critic, debate, distill, fetch-rules, fux, ingest, plan, propose-rules, savings, trace. Single-platform bodies.
- **CLI** (~50 subcommands) with grouped help (`fux help`), `how`, `query/path/explain`, `gate`, `lint`, `stats`.

### 11.2 Hook enhancements
1. **Structured output envelope.** `session_start` prints raw text (fine for SessionStart), but `user_prompt_recall` and the new pre-read nudge (§4.1) inject into events where Claude Code expects the JSON envelope `{"hookSpecificOutput":{"hookEventName":...,"additionalContext":...}}`. Plain stdout there is silently dropped on some hosts. **Add a `hookio.emit(event, context)` helper** that picks raw-vs-envelope by event, and route every injecting hook through it. (graphify's hooks always use the envelope — copy that discipline.)
2. **Pre-edit nudge, not just post-edit reminder.** `post_tool_use` fires *after* an edit to flag drift. Add a `PreToolUse(Edit|Write)` nudge: when the target file is governed by a rule, inject *"`fux why <id>` before editing — this file is governed by [ids]."* Catches the mistake before it happens, not after.
3. **Recall receipt → cage.** `user_prompt_recall` already writes a receipt (`_emit_recall_receipt`). Make that a `cage`-formatted token-saving receipt (fux↔cage integration already exists via `fux/cage_receipt.py`) so the recall's context-injection win shows up in `cage attrib`.
4. **Render hook payload text from a fragment** (§4.1) so wording is drift-guarded and identical across all wired agents.

### 11.3 Skill enhancements
1. **Render all 11 through skillgen** (§3) — but stage it: `fux`, `critic`, `distill` first (most-used, most-edited), then the rest. Each skill's per-host trigger/dispatch becomes a fragment delta.
2. **Add a frontmatter `triggers:` discipline.** The skill `description` is the firing signal; audit all 11 for sharp, non-overlapping descriptions (you literally have a `recall-skill-audit` skill for exactly this — run it against the fux skill set).
3. **`references/` progressive disclosure.** Long skills (plan, debate) should split into a lean core + `references/` sidecar like graphify's split bucket, so the always-loaded body stays small.

### 11.4 CLI enhancements
1. **`--json` on every read command** (`why`, `refs`, `recall`, `stats`, `coverage`, `impact`, `query`, `path`, `explain`). Agents consume fux as a tool; typed JSON beats scraping formatted text. This is the single highest-leverage CLI change for the agent-era bet.
2. **`fux doctor`** — fux has `check` (substrate validity) but no setup-health command. Add `fux doctor` mirroring `cage doctor`: are hooks wired in each agent? is the skill installed + current? version drift? `.fux/` present and building? One command that says "your fux install is healthy / here's what's broken."
3. **Version stamping + stale warning.** On `fux setup`/`fux hooks install`, stamp `.fux_version` in each installed skill dir; warn on `doctor`/`setup` when the installed skill predates the package (graphify's `_check_skill_version` is the reference — copy it).
4. **Exit-code contract.** Document and enforce: `0` ok, `2` blocking (gate/strict stop), `1` error. fux already uses 2 for blocking — make it uniform and documented in `docs/cli.md`.

---

## 12. cage — enhance hooks, skills, CLI

### 12.1 Current state (verified)
- **Hooks** (`cage/hooks.py`, wired by `<agent>wire.py`): `session_start`→spend banner, `stop`→token capture, `session_end`, `post_tool_use`→provenance edit buffer, `post_commit`, `prepare_commit_msg`. All fail-open, exit 0. Capture-oriented.
- **Skills** (2): cage, cage-doctor + copilot prompts + kiro steering.
- **CLI** (~40 subcommands): report/attrib/matrix/budget/roi/human/trend/why/quality/regression/recommend/forecast, capture (proxy/meter/import/export/watch), setup wizard, doctor, query (explain).

### 12.2 Hook enhancements
1. **Threshold budget nudge (the honest piece-2, §4.2).** `session_start` already prints a spend banner unconditionally. Upgrade: when `cage budget` crosses a `policy.toml [budget]` threshold, emit it through the structured envelope as `additionalContext` (not just a banner) so the agent *sees* it mid-session and can self-throttle. Silence under threshold. This is cage's legitimate behavioral nudge — tied to what cage actually knows.
2. **Regression nudge.** cage already computes `cage regression` (cost-per-call drift). Surface it as a `session_start` warning when a regression is detected: *"cost-per-call up N% vs baseline (`cage regression`)."*
3. **Keep capture hooks as-is.** Do **not** add a "use cage before grep" nudge (§4.2 / §8). Document the deliberate divergence from graphify in `docs/cage-plan.md`.

### 12.3 Skill enhancements
1. **Render cage + cage-doctor through skillgen** (§3) so the claude skill, codex skill, copilot prompt, and kiro steering stop drifting. cage's per-agent framing (skill vs prompt vs steering) becomes the per-host delta — this is the cleanest skillgen fit of either repo because the 4 surfaces already exist and only the wrapper differs.
2. **`cage` skill gains a `--json`-aware usage section** so an agent invoking the skill knows to ask for machine output.

### 12.4 CLI enhancements
1. **`--json` consistency audit.** Several read commands likely already emit structured data via MCP; ensure the *CLI* has `--json` parity on `report`, `budget`, `attrib`, `roi`, `human`, `forecast`, `regression`. (MCP read server and CLI should share one formatter.)
2. **`cage doctor` → check the nudge + threshold wiring** it gains in §12.2 (does the project have a budget set? are thresholds sane?).
3. **Version stamping** of installed skill/steering/prompt assets (`.cage_version`) + stale warning in `cage doctor`/`cage setup` — graphify parity.
4. **`cage setup` already a wizard** — extend it to offer the always-on CLAUDE.md/AGENTS.md inject (§5.2) as a step.

---

## 13. Cross-cutting enhancements (both repos, do once)

1. **One hook-output helper, copied to both.** A `hookio.emit(event, text)` that knows which Claude Code events take raw stdout vs the `{"hookSpecificOutput":{...}}` envelope, plus the fail-open contract (never raise, exit 0 unless an intentional blocking 2). fux has `hookio.py` already — generalize it; give cage the same.
2. **`--json` everywhere a machine reads.** The agent-as-user principle. Both repos expose read surfaces to agents; typed JSON out is the compounding bet.
3. **Version-stamp + stale-install warning** (graphify's `_check_skill_version` + `_refresh_all_version_stamps`) ported to both `doctor`/`setup`.
4. **`status` parity across every wired surface.** cage has `status`/`backfill_status`/`realtime_status`; fux has `status`. Make both print a single "here's what's wired and whether it's current" table.
5. **All payload/nudge text rendered from fragments** so wording is single-sourced and `--check`-guarded — the through-line that ties Part B back to Part A.

---

## 14. Revised build order (Parts A + B)

1. Renderer skeleton, both repos (§3.3 1–2).
2. Unify flagship skill + wire `--check` into CI (§3.3 3–6) — *load-bearing slice; everything else additive.*
3. Cross-cutting `hookio.emit` + `--json` formatter, both repos (§13.1–13.2) — unblocks the hook + CLI enhancements.
4. Hook enhancements: fux pre-read + pre-edit nudges (§4.1, §11.2); cage threshold + regression nudges (§12.2).
5. Always-on blocks (§5).
6. CLI enhancements: `fux doctor`, version stamping, exit-code contract, `--json` audit (§11.4, §12.4, §13.3–13.4).
7. Skill enhancements: render remaining skills, audit descriptions, progressive `references/` (§11.3, §12.3).
8. Breadth: `agents` generic target both; `kiro` for fux; `gemini` (§6).
9. Docs-of-record + CHANGELOG + tests in the *same* commits throughout (§8 — constitutional).

Steps 1–3 are still the foundation. Steps 4–6 are where the *enhancement* value lands.

---

## 15. Definition of done (updated for Parts A + B)

**Part A (port):** as §9 — renderer green in CI, single-sourced artifacts, idempotent always-on inject, breadth targets added, `tools/skillgen/` wheel-excluded.

**Part B (enhancements):**
- Every injecting hook uses the correct output envelope via the shared `hookio.emit`.
- fux gains pre-read + pre-edit nudges; cage gains threshold + regression nudges (and *no* query-nudge, documented).
- `--json` on every agent-read CLI command in both repos.
- `fux doctor` exists; both `doctor`s check version-drift + wiring.
- Installed assets are version-stamped; stale installs warn.
- All nudge/hook/skill text is rendered from fragments and `--check`-guarded.
- Docs-of-record + CHANGELOG + tests updated in the same commits.

---

## 16. Suggested next step

This is ready to become two `implementation-handoff` packets (one per repo), each sequenced as §14. I'd scope the **first** packet per repo to steps 1–3 (renderer + `hookio`/`--json` foundation) so you ship the single-sourced, drift-guarded base and review it before the nudge/CLI/skill enhancements land. Say the word and I'll generate both — or tell me to start building step 1 directly in one repo.
