# OPEN-WORK — the one plan of pending work

**Next:** **NET-1** — does graphify actually pay? (your hands, n=5 per arm).
Nothing is blocked. **State: v0.43.0 is released** — tagged, GitHub release created,
publish.yml fired (PyPI via OIDC) alongside the cross-OS `cage.pyz` chain. Every version
through v0.43.0 is tagged and released; there is no unreleased work in tree.
(Verified against `git tag` + `gh release list` on 2026-08-02 — an earlier revision of
this header claimed v0.40–v0.42 were unreleased, which was false and had been carried
forward unchecked. Its own markers are not ground truth.)
Suite: **1401 pass / 0 fail / 10 skipped** (dev machine, macOS/posix path only; the 10
skips are the Windows-only shim behaviour tier and run on CI).

**In tree, unreleased: v0.44 (COPILOT-CREDITS + DOGFOOD)** — billed credits + the
copilot pricing ladder, plus cage's own ledger published as a dated snapshot; both
built and green 2026-08-02; CHANGELOG entry covers COPILOT-CREDITS only (DOGFOOD ships
nothing user-facing, by design). `__version__` deliberately **not** bumped (bumping is
a release action, and it would propagate an unreleased stamp into every scaffolded
project's `[meta] cage_version`). The header sentence above — "there is no unreleased
work in tree" — was true through v0.43.0 and is no longer.

## Pending

| # | what | next action |
|---|---|---|
| **GF-LAUNCHER** | under `--python-launcher` neither twin meters (B5) | a decision — must move both twins |
| **ADOPT-COV** | is half B's per-agent coverage real, or too thin? | measure on a lab run first |
| **NET-1** | ④ prove graphify pays — n=1, gate 5 | [proposal](proposals/net-positive-evidence-run.md) — **your hands** |
| **TOOL-SDK** | the paved road: next tool ≠ 34 modules; fux is the proof | [proposal](proposals/tool-integration-contract.md) — builds on [shim-contract](shim-contract.md) |
| **CC-CLAUDEMD-DOCCASE** | `docs/claude-md-doc-case.proposed.md` is written and **deliberately not applied** — CLAUDE.md's ALL-CAPS entry-point list omits `FORMULAS.md` now that DOC-CASE renamed it | review [claude-md-doc-case.proposed.md](claude-md-doc-case.proposed.md): apply, amend or decline, then delete it and bump the CLAUDE.md DOC-REGISTRY row |
| **CLAUDE-DOGFOOD** | `docs/claude-md-dogfood.proposed.md` is written and **deliberately not applied** — a short "Dogfood snapshot" section mirroring "Regression & capture reports" | review [claude-md-dogfood.proposed.md](claude-md-dogfood.proposed.md): apply, amend or decline, then delete it and bump the CLAUDE.md DOC-REGISTRY row |
| **DOC-LINK-CHECK** | DOC-CASE's dangling-link class (case-broken doc citations, invisible on a case-insensitive filesystem) would be caught by a link-checker test, same class as `test_cli_reference.py` catching a dead verb in prose — recommended in the DOC-CASE handoff but explicitly scoped out of that change | design a minimal test walking `docs/*.md` links against `git ls-files`, case-sensitive |
| **L1-FIELD** | L1 hook shapes are unit/CI-tested but never run on a real Claude Code / Copilot / Kiro install | wire one machine per agent, confirm the hook fires and `cage setup --status` agrees |
| **KIRO-MCP-FIELD** | the committed path-free `python3 -m cage mcp` has never started on a real Kiro | open Kiro on a wired repo; if it does not start, **report it** — do not fall back to a gitignored absolute path |
| **ID-ENTROPY** | `ids.new_id` has **16 bits** of randomness per millisecond, and every merge path dedupes by id — so a collision **silently drops a row**. Measured: **874 dupes in 200,000** sequential ids (~1 in 229); it turned main red once already (`test_study`, 37 vs 38) | widen the random field 4→8 hex (32 bits, ~65,000× safer) and correct `transcript._composite_id`'s stale "same 15-char shape" comment. [finding](regression/2026-08-02-finding-call-id-collisions.md) |
| **HR-CLAUDEMD** | the CLAUDE.md architecture bullet for HR1 is written but **deliberately not applied** — the prompt forbids silently rewriting steering files | review [claude-md-hr1.proposed.md](claude-md-hr1.proposed.md): apply, amend or decline, then delete it and correct the CLAUDE.md DOC-REGISTRY row |
| **HR-FIELD** | the four-bucket split has only been read on **cage's own repo**, whose history is unusually doc- and artifact-heavy (80% `unattributed`) | run `cage insights commits` on a second, code-heavy repo; if `unattributed` still dominates, the per-file table is the surface that needs work, not the buckets |
| **HR-COPILOT-JOIN** | copilot-vscode has per-request timestamps but stamps **no `project`**, so every one of its calls is excluded as *unconfirmable* — the join is built and cannot fire for it | stamp `project` on the vscode chat-store parse (the claude `cwd` precedent), then it window-joins for free |
| **CC-CLAUDEMD** | the CLAUDE.md bullets for the copilot pricing ladder are written and **deliberately not applied** — the prompt forbids silently rewriting steering files | review [claude-md-copilot-credits.proposed.md](claude-md-copilot-credits.proposed.md): apply, amend or decline, then delete it and bump the CLAUDE.md DOC-REGISTRY row |
| **COPILOT-PREMIUM-DEAD** | `premium` is an int, but `totalPremiumRequests` is fractional in every real sample (`0.33`) — so `int()` floors it and `make_call` drops the key. **Confirmed: 13 copilot-CLI rows in the real ledger, not one carrying it.** Pricing no longer depends on it (COPILOT-CREDITS stamps a float `credits` instead), but the field is still written and still exported, and it is structurally wrong for its own source | decide: widen it to float, or **remove it** — it now has no reader. Removal is the cleaner call and is a substrate change, so it needs the same care as any `CALL_FIELDS` edit. [finding](research/2026-08-02-copilot-credit-fields-real-stores.md) |
| **COPILOT-SIDECAR** | the deferred half of COPILOT-CREDITS: `agentHostUsage/<session>.jsonl` carries per-call `cacheReadTokens` (the vscode `cached` column is honestly empty without it) + the **real routed model** behind `copilot/auto`. Debug-gated and deleted with its session | trigger R3 of the [compare](compare/copilot-pricing-basis.compare.md) — parked, not lost. **Note the old OPEN-WORK phrasing said `elapsedMs`→`gap_ms`: `gap_ms` was removed with the human axis in v0.36, so that half is void, not pending** |
| **CLI-GAPS** | two front-door inconsistencies, found writing [CLI.md](CLI.md): (a) `cage --help` lists **seven of `data`'s eight** commands — `migrate-savings` runs but is unadvertised; (b) `prices`/`study`/`policy` take their action as a **positional choice, not a subparser**, so `cage prices set --help` renders the group's help and the group's flags are a flat union (`--input` shows on `list`) | (a) is a one-line front-door fix + a golden re-bless. (b) is a **front-door change**: converting the three to real subparsers re-blesses goldens and touches `test_cli_tiering`'s help fixture — decide whether the asymmetry is worth keeping |

**AGENT SURFACE re-designed from scratch 2026-08-02 (Arpit: clean slate).** The old
`cage-skills` proposal is **superseded** — its premise (*"cage already ships one skill"*)
was pre-hookless and false; no code writes a skill file anywhere. New design of record:
[agent-surface-layers.md](archive/v0.41-agent-surface-layers.proposal.md) — a **four-layer ladder**,
each optional and strictly additive: **L0 hookless** (the floor, must work perfectly
alone, forever) → **L1 hooks+steering** → **L2 MCP** → **L3 skills**.
Three findings drove it: **L1 mostly fixes problems that already exist** (auto task-close
unblocks compare/estimate/calibration/NET-1, all starved because nobody runs
`cage task outcome`; and a hook *knows which agent fired it* — exactly what ADOPT-COV
cannot get from a shim subprocess); **L2 ships six read tools but not `verdict`/`compare`,
the two that answer the product question**; and **only L3 can carry the honesty
discipline** (MCP hands over a JSON number, nothing makes an agent say *"that's modeled,
not measured"*). Order: **L0 → L2 → L1 → L3**, and **all four phases are specced in one program**
with a gate between each. **ALL FOUR BUILT 2026-08-02 — the program is complete
(1024/0 ⇒ 1125/0), and the proposal + pair are archived.** Nothing remains but the two
field-verification residuals below.
**Everything committed, multi-user (Arpit, 2026-08-02)** — every layer's wiring is
committed and must work for a teammate on another machine. **Every piece of wiring is committed;
only the *records* are not** (`ledger/`/`out/`/`state/` gitignored; team numbers come
from `refs/notes/cage-ledger`, ADR 0001 — never committed records).
✅ **The Kiro MCP blocker is resolved and BUILT in P1** — `kirowire.PATH_FREE`
(`python3 -m cage mcp`) is the committed default, the gitignore exception is gone, and
doctor's new `kiro-mcp` check asks the resolved interpreter to import cage. **One
residual, carried forward: [KIRO-MCP-FIELD]** — the path-free form is CI- and
unit-tested but **not yet verified on a real Kiro install**; that can only close on a
machine with Kiro (the prompt's stop-condition). **Windows is a stated limit, not a
bug:** `python3` is often absent there and a *committed* file can carry one spelling, so
the default is `python3` and doctor points a Windows machine at `cage setup
--python-launcher` for the `py -3` form.
**Three agents at every tier is a gate, not an aspiration** — claude · copilot · kiro,
or the gap is *named in output*. Shapes differ and matter: **copilot hooks CAN be
committed** — `.github/hooks/*.json` is repo-level and portable (a 2026-08-02 correction:
an earlier draft called them user-level-only; cage's own `_strip_legacy_hooks` cleans
`.github/hooks/cage.json`). Both sources **combine**, so wiring both double-fires ·
kiro's hook file is
**one hook per file with no session-start**. ⚠️ **Hooks are CLI-only — they don't fire under a VS Code extension**, so
L1's agent identity and auto task-close are CLI-session only and must never be presented
as "cage knows which agent ran".
✅ **P0 landed 2026-08-02 (1024/0 ⇒ 1039/0).** The gate that matters — **adding or removing
a layer must change no number** — is now a *test*, not an intention:
[tests/test_floor.py](../tests/test_floor.py) installs every layer cage ships onto an
already-captured project and asserts the ledger shards **and** seven derived views'
stdout byte-identical, then strips the wiring and asserts it again, per agent. **P1–P3
are judged against it.** A new layer is wired in by adding its artifacts to
`_WIRING_ARTIFACTS` — never by relaxing an assertion. Residue cleared with it: the
README's three skill claims (one *"all four agents"*, live on PyPI), PLAN §5.1's dead
`tools/skillgen` section, CLAUDE.md's `hooks+MCP` wiring bullet, `docs/example/setup.md`.
✅ **P1 landed 2026-08-02 (1039/0 ⇒ 1059/0).** `cage_verdict` + `cage_compare` +
`cage_task_outcome` ([mcpserver.py](../cage/mcpserver.py)); kiro's MCP committed
path-free; new `kiro-mcp` doctor check. **The refusals are asserted as *equality with
the CLI's stdout*, not substring presence** — a wrapper that printed `INSUFFICIENT DATA`
and dropped the note beneath it would pass a substring test, so it must fail this one.
`cage_task_outcome` is the ladder's only write tool (`mcpserver.WRITE_TOOLS`), sharing
`clicmds.close_task` with the CLI verb so the label guard cannot be laxer on the
agent-facing side. **Correction to the spec:** `tests/test_portable_wiring.py`, cited by
CLAUDE.md and the prompt, **has never existed** — the greps live in `test_agents.py` and
`test_mcp_layer.py`.
✅ **P2 landed 2026-08-02 (1059/0 ⇒ 1096/0).** `cage hook <event>`
([hookcmd.py](../cage/hookcmd.py)) + attestation ([attest.py](../cage/attest.py)) + auto
task-close + budget blocking + steering ([steering.py](../cage/steering.py)), **opt-in**
via `cage setup --hooks` and two-way (plain `cage setup` removes it). **Gate met the hard
way:** the floor test was *extended* to install hooks too and still asserts ledger bytes
and seven views byte-identical in both directions. Two calls worth keeping: **auto-close
writes `outcome="auto"`, never `ok`** (closed for cost comparison, invisible to `cage
task quality` — a session ending is not a job well done), and **no unverified host event
name was invented** (copilot gets identity + auto-close but no pre-tool hook, named in
`agents.HOOK_GAPS`). **ADOPT-COV is NOT closed by this** — attestation fixes adoption's
half A only; half B's `NO_LINK` is still structurally true.
**Residual carried forward: [L1-FIELD]** — the hook file shapes come from cage's own
prior implementations, not fresh vendor verification; field-verify on a real Claude
Code / Copilot / Kiro install.
✅ **P3 landed 2026-08-02 (1096/0 ⇒ 1125/0) — the program is COMPLETE.** Seven skills
through `steering.py`'s one-source renderer (task-closer · analyst · doctor-triage ·
honesty-reviewer · release · lab-runner · windows-shim), `cage setup --skills`, opt-in
and two-way. *No skill computes a number* is enforced **mechanically** (`steering.lint`)
and every `cage …` a document names is checked against the **live parser** — a skill
teaching a dead verb is the F1 class in prose. **The single best fact from the whole
program: the floor test passes with every layer installed.** Three layers added, no
derived number moved, either direction, all three agents.
**Archived:** [proposal](archive/v0.41-agent-surface-layers.proposal.md) ·
[handoff](archive/v0.41-agent-surface.handoff.md) ·
[prompt](archive/v0.41-agent-surface.prompt.md). Living spec: `CLAUDE.md`'s
agent-surface bullets · `cage query agent-layers` · [FORMULAS.md §2.12](FORMULAS.md).

**ADOPT closed 2026-08-02 — `cage insights adoption` shipped, 995/0 ⇒ 1024/0.** Two
halves, never blended: **A** invocations + outcomes (exact, **agent-blind** — a usage row
has no `agent` field, verified against `usagelog.record` before designing); **B**
per-agent, from savings rows joined to `calls.agent`. **The spec was corrected twice
more during the build.** (1) A linked **`call` id** resolves the agent *directly* — a
stronger join than the session — so it is tried first and labelled per row. (2) **"No
evidence of invocation" needed a second, weaker strength**: it is sound only at 100%
attribution, because otherwise an unattributed row could belong to the very agent being
named; below that the view says *no savings row attributed to them*. Decision recorded:
**an empty half B renders its refusal, never vanishes.** Living spec:
[cage/adoption.py](../cage/adoption.py) · [FORMULAS.md §2.12](FORMULAS.md) ·
`cage query tool-adoption`. Archived:
[proposal](archive/v0.40-insights-adoption.proposal.md) ·
[handoff](archive/v0.40-insights-adoption.handoff.md) ·
[prompt](archive/v0.40-insights-adoption.prompt.md).
**Residual carried forward → ADOPT-COV** (above); nothing else is open from it.

**ADOPT-COV — the coverage question the build could not answer.** Half B attributes only
rows whose `call` or `session` resolves; **the shim route can never be one of them**, and
on the dev ledger the shim route has produced *zero* rows, so the view has never been
exercised against the path most real invocations take. Measured today: **3 of 6** savings
rows attributable by session (all graphify, all `claude-code`), **6 of 6** once the
legacy `call`-linked rows count — one of which is a `cage demo` seed. That is n≈1 and
proves nothing about the shim.
**The trigger and the guard rail:** run a lab cell that invokes graphify through the
**PATH interceptor** for each of the three agents, then read `cage insights adoption`.
If half B is empty there, the finding is *the shim route is structurally unattributable*
— report it. **Adding an `agent` field to usage rows (or an env-stamped agent hint on the
shim) is a capture change and needs its own proposal**; it must not be slipped in as a fix
to a number nobody has measured yet.

**WIN-CI closed 2026-08-02 — and it earned its keep.** The first-ever Windows run was
**red**, on two independent bugs neither reasoning nor macOS could have found:
(1) **in the shim** — a `rem` comment inside the nested `for` block contained
`"<candidate>"`, and cmd.exe tokenizes redirection characters *inside comments nested in
a `(...)` block*, corrupting the block into a recursion abort on every invocation;
(2) **in the test harness** — `_run()` wiped `PATH` so the shim's own
`findstr.exe`/`where.exe` could not resolve. Five pushes; two earlier hypotheses were
real improvements that did not fix the failure, and the CHANGELOG diagnosis was
**corrected** rather than left standing. Both facts are now in
[shim-contract.md](shim-contract.md) as **B8a** + a test-harness corollary, and B8's
superseded diagnosis is marked as such — the contract is what TOOL-SDK's future
interceptors inherit, so the lesson had to live there, not in a changelog.
**Windows is now CI-executed; still not field-validated** (the README says so).

**Graphify-works track (decided 2026-08-01)** — the distribution plays were declined
and removed (a `uvx` push, ccusage interop); the OTel export (below, now built) was the
only one that shipped. The priority is **graphify
end-to-end, then a paved road for more tools**. ①② are done; **ADOPT** shows whether
agents invoke it · **NET-1** proves value. **fux is the second tool** (its receipt shim
already exists) — the [tool-integration-contract](proposals/tool-integration-contract.md)
ships only when two tools use it, and now has its first artifact to build on
([shim-contract.md](shim-contract.md)).

**CMD-SYNC closed 2026-08-02** — one proposal applied, one declined, both independently
re-verified against code at execution time (not just carried forward from the handoff).
✅ `claude-md-prices-file` **applied**: the flow diagram + Must-Know bullets now name
`prices.toml` as the vendor rate card home, `cage.toml` keeping order/budgets/routing
(`grep -c prices.toml CLAUDE.md` 0 → 10). ❌ `claude-md-sources-authority` **declined** —
`paths.resolve_log_sources`'s docstring still reads *"an empty/absent `[sources]`
returns exactly the built-in registry"*, which is what CLAUDE.md already said; the
proposal described a Directive A end-state that never shipped. Zero code changes.
995/0 (unchanged — docs only). Pair archived to `docs/archive/v0.39-claude-md-sync.*`;
both proposals archived to `docs/archive/v0.39-claude-md-{prices-file,sources-authority}.proposal.md`.

**OTEL closed 2026-08-02** — `cage data export --otel` ships: one-way GenAI-conformant
JSON, exactly like `--csv` (never an import source; `--study` stays jsonl), stdlib only
(no OTel SDK — `dependencies = []` unchanged). Calls map to `gen_ai.system` ·
`gen_ai.request.model` · `gen_ai.usage.input_tokens`/`output_tokens` ·
`gen_ai.client.operation.duration` (omitted, never zero, when `latency_ms` is unknown).
**Decision: receipts/savings have no GenAI equivalent, so they're cage-namespaced**
(`cage.savings[].cage.*` — `cage.saved` GROSS, `cage.saved_usd` priced via the existing
`receiptprice` ladder and omitted, never `$0`, on an UNPRICED refusal or a non-money
unit) — no `gen_ai.*` name invented. **The convention is pre-stable**
(`constants.OTEL_SEMCONV_VERSION = "1.42.0"`, stamped in every document's `cage.meta`
block); a spec bump is a deliberate, changelog'd change, same discipline as
`prices_version`. New module `cage/otelout.py`; `cage query otel-export` explains it.
982/0 ⇒ 995/0. Pair archived to `docs/archive/v0.39-otel-export.*`.

**DEBT closed 2026-08-01** — Part 1 **landed**: the `paths.py` splits-on-contact rule is
in `CLAUDE.md` (seams `routing`/`logsources`/`agenthomes`/`footprint`, plus CODEX-OUT's
earned clause *a deletion and a move never share a diff*). Part 2 stays **declined** —
re-verified a third time, independently, by the agent that executed the prompt: bare
`cage` runs `cmd_overview` (`cli.py:651`), already prints tokens · calls · unpriced ·
last-import, `_ROOT_HELP` only shows on `--help`, and the capture-on-read is deliberate
(`cli.py:114`). No code changes. Pair archived to `docs/archive/v0.39-structural-debt.*`.

**CODEX-OUT closed 2026-08-01** — the agent's residue is gone (`codex_home` +
`CODEX_HOME` · `wiringscan`'s `~/.codex/config.toml` scan and `.codex/hooks.json`
enumeration · doctor's read · the bundle env entry · six prose enumerations);
`grep -riI codex cage/` now returns only the OpenAI model rows. **The category-2 trap
held**: `data/prices.toml` is byte-identical and a new guard prices a Copilot call on
every `gpt-5.x-codex` id, so the next blind grep fails loudly. The accepted trade — a
pre-v0.33 `~/.codex/config.toml` keeps a dead `cage` verb undetected — is named in the
CHANGELOG `Removed` entry. `paths.py` deliberately not split; `agenthomes` and the
earned clause *a deletion and a move never share a diff* live in `CLAUDE.md`'s
split-on-contact rule (promoted there by the concurrent DEBT session). Pair archived to `docs/archive/v0.39-codex-purge.*`. 983/0 ⇒ 982/0.
**Carried forward:** nothing — DEBT's `agenthomes` move stays its own fix-on-contact item.

**GF-DEBT closed 2026-08-01** — v0.38's code was sound; its honesty surface wasn't, and
all six gaps are closed in the same change, before commit. `docs/restricted-environments.md`
restored (8 citing files now resolve) with a new GF-LAUNCHER section; the README
Platforms line and `cage doctor`'s new `launcher-gap` check both state the same gap;
`cage query graphify-shims` explains the twin pair, live-interpolated;
[ADR 0007](adr/0007-graphify-twin-pair-hand-paired-not-templated.md) records the three
decisions (both twins/every OS · hand-paired not templated · contract outside package
data); `docs/cage-lab/{01-setup,03-verify}.md` now state POSIX-twin-only coverage; the
corpus-sizing rule is written into `tools/cigraphify.py` and pinned by 4 new tests
(`tests/test_cigraphify.py` — the vacuous-corpus check was already enforced in code, it
just lacked a regression test). 979/0 ⇒ 983/0. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--v0380-gf-debt--the-six-honesty-debts-win-gfci-gf-left-behind).
Archived pair: [handoff](archive/v0.38-graphify-honesty-debts.handoff.md) ·
[prompt](archive/v0.38-graphify-honesty-debts.prompt.md). GF-LAUNCHER stays open above —
this documented it, it did not fix it.

**CI-GF + WIN-GF closed 2026-08-01 (v0.38.0, unreleased)** — `graphify.cmd` ships as
bundled text against one written [behaviour contract](shim-contract.md) (B1–B8 binding,
D1–D7 divergences documented — cmd has no `exec`); both twins install on every OS;
`pathshim`/`wiringscan`/`doctor` learned PATHEXT liveness, so an interceptor this OS
cannot resolve is now a doctor **failure** rather than a green tick. CI grew a `$0`
`present` leg on 3 OSes (`tools/cigraphify.py`, corpus `tests/fixtures/cicorpus/`) whose
Windows assertion shipped already flipped. 962/0 ⇒ 979/0. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--v0380-win-gf-the-graphifycmd-twin--ci-gf-the-graphify-ci-axis).
Archived pairs: [WIN-GF](archive/v0.38-win-graphify-shim.handoff.md) ·
[CI-GF](archive/v0.38-ci-graphify-matrix.handoff.md). Residuals carried forward above as
**WIN-CI** and **GF-LAUNCHER**.

**CLEAN closed 2026-08-01** — retention **30 → 90 days**; the auto sweep (piggybacked on
`cage import`) now only **warns** on stderr — count, reclaimable KB, the exact fix,
silent when nothing's eligible, throttled 24h — and never deletes; only `cage data
cleanup --apply` deletes, and it runs regardless of `[cleanup] enabled` (decided: an
explicit command is always honored, `enabled=false` only silences the automatic
reminder). New `[cleanup] warn` switch, default true, env `CAGE_CLEANUP_WARN`. Tool
savings (`ledger/savings/<tool>/`) get the never-per-tool invariant stated at
`cleanup.NEVER` and tested surviving `prune` at `days=0`. 956/0 ⇒ 961/0. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--cleanup-becomes-advisory-90d-default-warn-only-never-per-tool).
[Archived pair](archive/v0.36-cleanup-safety.handoff.md).

**SUITE closed 2026-08-01** — **G-SAV**: `savings.record()` was missing `ts` from its
signature; added and forwarded (kept `**_ignore` for the shim callers), plus a
kwarg-parity guard test. **BUD-V-TEST**: the five sync tests re-pointed from
`[budgets]` (opt-in, commented out by BUD-V) to `[quality] signal` — a table the
bundle actually ships. Same mechanics, different worked example. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--suite-green-g-sav-fixed-bud-v-test-re-pointed-9496--9560).

**SYNC-GUARD closed 2026-08-01** — **guard now, fixture later.** The pain was
*diagnosis*, not repair — 5 budget-unrelated failures with no obvious cause. The
borrowed table/key (`[quality] signal`) now lives in one constant in
`test_policysync.py` (re-point is a one-line edit) and a new guard test fails with the
exact fix if it's ever removed from the bundle. The synthetic-bundle refactor stays
filed with a trigger — a **third** removal: [proposal](proposals/policysync-synthetic-bundle.md).
961/0 ⇒ 962/0. Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--sync-guard-name-the-sync-tests-borrowed-table-guard-its-removal).
[Archived prompt](archive/v0.36-sync-guard.prompt.md).

**README-FIX closed 2026-08-01** — shipped as **v0.37.2** (committed and tagged): the
human-axis claims replaced with the real capabilities (gross/net + adoption), the
gross-vs-net honesty line added to the story, the Windows shim gap stated in Platforms —
and **closed one version later** by WIN-GF, above. Full accounting: the v0.37.2 entry in
[CHANGELOG.md](../CHANGELOG.md). The mooted grep gate for removed-feature claims is
deliberately **not** filed; raise it again if a second such claim ever ships.

**HR1 closed 2026-08-02** — agent-vs-human v2 built end to end (P1–P4), 1148/0 ⇒ 1354/0. Capture was genuinely orphaned and now writes; the window join is **measured sound** (68.7% verbatim match inside proposed files, [dogfood](regression/2026-08-02-p1-authorship-dogfood.md)); `MIN_MATCH_CHARS` frozen at 4 with a sweep. **One design correction:** the three-bucket split became four — `unattributed` had to be separated from `human~`, because a single human bucket printed 76.6% here, 89% of it one commit of generated JSON. Living spec: [ADR 0008](adr/0008-line-match-authorship-counts-persisted-content-transient.md) · [FORMULAS §2.14](FORMULAS.md) · [CLI.md](CLI.md). Residuals carried forward above as **HR-FIELD** and **HR-COPILOT-JOIN**.

**BUD-V closed 2026-08-01** — verified via `just test` on the dev machine (Python
3.14): the bundle change needs no code fix; `cage policy sync` does not try to re-add
`[budgets]` (an active table buckets as `project_own`, untouched). Goldens P5/P6a/P6b
re-blessed (only the in-sync key count moved, 11→8). Full report:
[IMPLEMENTATION.md](IMPLEMENTATION.md#2026-08-01--budget-ceilings-become-opt-in-bundle-only--verified-bud-v-closed).
**NET-1 needs no code** — `insights compare` is gated at `MIN_COMPARE_N = 5`.

**KIRO-CLI-SCOPE** (carried forward from K2) — kiro-CLI credits captured while the cwd
sits outside any project reach only a *machine-ledger* sweep. Nothing is lost (the store
is re-read), but a user who never runs a project-less `cage import` never sees them.
Revisit if that turns out to be common.

## Decisions open

1. ~~Corpus refresh cadence~~ — **decided 2026-08-01: the corpus is FROZEN.** `tinyshop`
   is never mutated; a new question gets a **new named corpus alongside** it and every
   result is labelled by the corpus that produced it. Old evidence stays valid forever.
   Whether tinyshop is too *small* is a separate, filed question:
   [proposal](proposals/larger-lab-corpus.md).
2. ~~Cost cap for paid legs~~ — **decided: opt-in via `cage.toml`**, bundle ships
   `[budgets]` commented out, no constant fallback. **Verified 2026-08-01 (BUD-V)** —
   see [IMPLEMENTATION.md](IMPLEMENTATION.md). Test-debt closed 2026-08-01 (SUITE,
   re-pointed at `[quality]`); the residual coupling is closed 2026-08-01 (`SYNC-GUARD`,
   above) — the synthetic-bundle fixture itself stays a parked
   [proposal](proposals/policysync-synthetic-bundle.md) behind a third-removal trigger.

## Binds the next lab run

- **F2's copilot-VS-Code receipt limit is UNTESTED** — never claim it confirmed.
- **Record the prompt count per cell as it runs** — D3/D4 are UNVERIFIED without it.

## How this file is maintained

Continuously; completed items **deleted, not ticked**; its own markers are never
evidence. Full law: [`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*.
Done work: [IMPLEMENTATION.md](IMPLEMENTATION.md) · evidence: [regression/](regression/).
