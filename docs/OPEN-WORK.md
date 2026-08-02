# OPEN-WORK — the one plan of pending work

**Next (your hands):** **NET-1** — does graphify actually pay? (n=5 per arm).
**It is no longer gated on anything.** Its only gate was ID-ENTROPY, closed 2026-08-02.
**Next (agent lane):** **tier 2** — four fabricated numbers, batchable in one green
run (REV-CREDITS · REV-HARDEN P2 · COPILOT-PREMIUM-DEAD inside it · CLI-GAPS(a)).
**Tiers 0 and 1 are both gone** — everything that accrued damage or was armed to fire
later closed 2026-08-02/03 (REV-TS · ID-ENTROPY · REV-DOGFOOD-DATE · REV-HARDEN P1).
**CHATS-AUTHOR, which they unblocked, is CLOSED and RELEASED 2026-08-03** (v0.46.0,
1462/0); HR-COPILOT-JOIN and HR-FIELD remain open.
**Nothing is blocked, and the two lanes run at the same time.**

**How this queue is ordered (2026-08-02).** It has **two resources, not one** — *your
hands* (NET-1 · the three field-verifications · the four steering decisions) and *agent
sessions* (every fix). They were previously sequenced against each other, which is a
category error: they never compete. Inside the agent lane the rule is **damage that
ACCRUES with elapsed time outranks damage that is merely present** — only REV-TS
(`originrecord` freezes rows by idempotency key) and ID-ENTROPY (a collision silently
drops a row; widening later never heals ids already written) had that property, and
**both are now closed**, which is why tier 0 is gone. Every remaining wrong number here
is equally wrong in three weeks and costs nothing to have waited on. Tiers below;
per-item build detail in §Implementation.
Every code claim in it was re-verified against HEAD on 2026-08-02 — **not** read off
this file's own markers.

**State: v0.44.1 is released** — `v0.44.1` tagged, `__version__ = "0.44.1"`
(`cage/__init__.py:19`); COPILOT-CREDITS + DOGFOOD shipped in v0.44.0. *(Corrected
2026-08-02: this header previously claimed v0.44 was unreleased and `__version__`
deliberately unbumped — both false at HEAD, carried forward unchecked. That is the
second time this header has gone stale in two days; its own markers are not ground
truth.)*
**State: v0.46.1 is released** — `v0.46.1` tagged, `__version__ = "0.46.1"`
(`cage/__init__.py:19`). v0.46.1 is the CI-S18 fix (harness only, no product code);
v0.46.0 shipped CHATS-AUTHOR. **Nothing is unreleased in tree.**
**The `build` gate was RED on all nine legs from v0.45.0 to v0.46.0** and two releases
shipped through it — fixed in v0.46.1. `publish-pypi` has no `needs` link to `build`
(deliberate), so no published artifact was affected. *(This header has gone stale three times in three days; re-read
`git tag --sort=-v:refname` and `cage/__init__.py` before trusting it again.)*
Suite: **1462 pass / 0 fail / 11 skipped** — re-run and printed 2026-08-03 (+20 over the
1442 baseline are CHATS-AUTHOR's own tests).

## Pending

### Tier 2 — what is LEFT of the review: three decisions and two phases, no quick wins

All of tier 2's *buildable* work shipped 2026-08-03. What remains are calls that were
deliberately **not** made inside a fix commit, each with its evidence already written,
plus REV-HARDEN's two later phases.

| # | what | next action |
|---|---|---|
| **COPILOT-PREMIUM-DEAD** | ⚠️ **this row's old premise was FALSE and is corrected here.** It said `premium` "now has no reader" — it has **two**: `chats.py` sums it into a rendered column *and* a CSV column, pinned by goldens I10a/b/d. So this is not removing a dead field, it is removing a **user-visible column that can only ever print 0** (`totalPremiumRequests` is fractional, `int()` floors it, `make_call` drops the key). Widening to float is not the alternative — it would duplicate `credits` exactly, the same counter | decide: (a) remove the field **and** its chats column, re-bless goldens · (b) keep the column but render `credits` in it · (c) leave it. A `CALL_FIELDS` edit either way. [finding](research/2026-08-02-copilot-credit-fields-real-stores.md) |
| **REV-CREDITS defect 2** | multi-model shutdowns: GitHub computes `totalPremiumRequests` over **all** models in the shutdown, so pricing one row by credits while its siblings price by tokens is neither basis. Defect 1 + every guard gap shipped 2026-08-03; this is the genuine fork | reopen [copilot-pricing-basis.compare.md](compare/copilot-pricing-basis.compare.md) — split pro-rata, or one basis per shutdown. **Never decided inside a fix commit** |
| **OTEL-SEMCONV-PIN** | `gen_ai.system` is deprecated (renamed `gen_ai.provider.name` in semconv **v1.37.0**, *before* cage's pinned 1.42.0) — but verifying it surfaced that the GenAI conventions **moved to their own repository**, so `OTEL_SEMCONV_VERSION = "1.42.0"` may not name what cage thinks it names. Renaming the attribute alone fixes a symptom and leaves `cage.meta` making an uncheckable claim | three options + a recommendation in [research](research/2026-08-03-otel-genai-semconv-pin.md); pick one. `otelout` and the pin are untouched |
| **REV-HARDEN P3/P4** | **P0 · P1 · P2 all shipped** (P2's `gen_ai.system` item became OTEL-SEMCONV-PIN above). **P3** wiring hygiene: `.gitattributes` LF pin on the POSIX twin · kiro's L1 hook has no Windows twin and no named gap · copilot's invented `sessionStart`/`sessionEnd` are unverified while status claims auto-close is wired · non-dict hook entries crash `cage setup` · four `wiringscan` bookkeeping bugs. **P4** durable joins & scale: full shas + prefix-match · `commitview` has no default window (one full `git show` per commit, O(n²)) · `_uncovered` judges coverage over other repos' edits · unthrottled session-end sweep · quoted-path line matching · Edit context lines counted as `suggested` · two `cigraphify` checks that assert nothing | [proposal](proposals/review-hardening.proposal.md) P3–P4, each independently landable. P4's short-sha item is the same merge-by-identity family as the shipped ID-ENTROPY |
| **CLI-GAPS(b)** | (a) shipped 2026-08-03 (and the front door is now gated bidirectionally against the live parser). (b): `prices`/`study`/`policy` take their action as a **positional choice, not a subparser**, so `cage prices set --help` renders the group's help and the group's flags are a flat union (`--input` shows on `list`) | a **front-door change** — converting the three re-blesses goldens and touches `test_cli_tiering`'s help fixture. Decide whether the asymmetry is worth keeping |

### Tier 3 — your lane · one sitting (~30 min)

**One item, four edits** — the four held CLAUDE.md edits were merged into a single
proposal on 2026-08-03 (CHATS-AUTHOR added a fifth the same day), since they patch one
file and need one decision sitting.

Re-verified against CLAUDE.md at HEAD: **none of the remaining four is applied** (E, the test count, shipped with v0.46.0). Until they are,
every agent session reads a CLAUDE.md that is behind the code.

**Both source proposals' test-count sections had gone stale** — they asked for 1354 and
1391 against a file already at 1401 (suite now 1462), so either would have *regressed*
it. The merged proposal replaces the number with a rule.

**DOC-LINK-CHECK rides this sitting** — it needs a policy call from you before it can be
written at all (see its row).

| # | what | next action |
|---|---|---|
| **STEERING-EDITS** | **four** CLAUDE.md edits raised by five programs (E applied in the v0.46.0 release and deleted), all held because the prompts forbid rewriting a steering file without a human read. Re-verified at HEAD 2026-08-03 — **none applied**: no `Authorship, per commit` bullet · no `[billing.<agent>]` text · `:674–676` still omits `FORMULAS.md` · no Dogfood section · the chats bullet still states the law amendment as **one** carve-out when there are now two. Merged into one file 2026-08-03 (they patch one file and need one sitting); **F added 2026-08-03 by CHATS-AUTHOR** | read [steering-edits-pending.proposal.md](proposals/steering-edits-pending.proposal.md) once, decide five times; its head table carries a verdict box each. **An applied section is deleted from it**, and the file goes when the table empties. Its item **E** — the `just test` count — is now a *rule* (set it to what `just test` prints that day), because both source proposals hardcoded targets and both went stale below the file they patch |
| **DOC-LINK-CHECK** | DOC-CASE's dangling-link class (case-broken doc citations, invisible on a case-insensitive filesystem) would be caught by a link-checker test, same class as `test_cli_reference.py` catching a dead verb in prose — recommended in the DOC-CASE handoff but explicitly scoped out of that change | **scope measured 2026-08-02: 112 dangling `.md` links tree-wide**, nearly all history in WORKLOG/PLAN/INTERVIEW pointing at pairs that gained a `vX.Y-` prefix when archived. So the test cannot simply be added — it goes red on 112 links on day one. Decide the policy first (exempt `archive/`+history, or bulk-repair, or warn-not-fail), then write the case-sensitive walker over `git ls-files` |

### Tier 4 — evidence · runs CONCURRENTLY with the fix tiers, not after them

This is the whole point of the two-lane split, and as of 2026-08-02 **every item here is unblocked**. NET-1's only gate was ID-ENTROPY (a dropped row inside an n=5 comparison is not noise, it is the result) and HR-FIELD's was REV-TS (it would otherwise have measured the four-bucket split through a skewed join and wasted the evidence). Both closed the same day.

| # | what | next action |
|---|---|---|
| **NET-1** | ④ prove graphify pays — n=1, gate 5 | [proposal](proposals/net-positive-evidence-run.proposal.md) — **your hands** |
| **ADOPT-COV** | is half B's per-agent coverage real, or too thin? | measure on a lab run first |
| **HR-FIELD** | the four-bucket split has only been read on **cage's own repo**, whose history is unusually doc- and artifact-heavy (80% `unattributed`) | run `cage insights commits` on a second, code-heavy repo; if `unattributed` still dominates, the per-file table is the surface that needs work, not the buckets |
| **L1-FIELD** | **Claude leg field-verified 2026-08-02** (`just wire` → `cage setup --claude --hooks`, one of three — Copilot/Kiro untouched by design, no install available here). `PreToolUse`/`Bash` confirmed **host-fired, live, unprompted**: two ordinary Bash tool calls invoking `./bin/graphify` produced new rows in `.cage/state/attest.jsonl` with no manual step. The pre-existing hand-written graphify `Glob\|Grep` hook in `.claude/settings.json` survived the merge untouched, and every committed `.cage/` file is grep-clean of absolute paths/usernames. `SessionEnd`/auto-close is a **verified negative**, not an assumption: manually invoking the exact wired command with this session's real id showed `skip_reason: no-open-task-in-session` in the debug log — correct, because **no call in this ledger has ever carried a non-empty `task` field** (grep-confirmed across all 40k+ rows; no `tasks.jsonl` exists), so `_open_tasks` structurally cannot find anything to close under plain transcript capture. Source confirms the write path uses `outcome="auto"`, never `"ok"`, but a live **positive** case (a real auto-closed task) could not be produced without seeding a task, which was out of scope. True host-triggered `SessionEnd`/`SessionStart` firing (as opposed to a manual same-payload replay) was **not observed** — this session never actually ended. Also surprising: the `PreToolUse` firing happened inside a session whose own system prompt says "VSCode native extension environment," in tension with `attest.LIMIT`'s "hooks do not fire under a VS Code extension" claim ([finding](regression/2026-08-02-finding-hooks-fire-in-vscode-extension.md)) | wire one real machine each for Copilot and Kiro, confirm the hook fires and `cage setup --status` agrees; separately, resolve the `attest.LIMIT` tension the finding raises, and — independently — someone with a real task-tagged session should confirm the positive auto-close case actually writes `outcome="auto"` |
| **CIGF-HERMETIC** | `tools/cigraphify` **cannot be run on a developer machine** — it builds its sandbox as a sibling of the repo, so on a dev box that path is under `$HOME`, and `paths.resolve_root` walks up and adopts the real `~/.cage`. `cage setup --project-only` then scaffolds into the *home* root and 3 of 7 checks fail (`setup`, `intercept`, `doctor-dead`). CI has no ancestor `.cage`, so it is green there and the gap is invisible — the same class as the cage-lab PATH rule: **a lab that is not hermetic against the developer's machine cannot be verified before pushing**. ⚠️ Running it from under `$HOME` **writes to the real `~/.cage`** (idempotent and non-destructive — ledger untouched, doctor green — but it is the user's live config) | make the sandbox hermetic against an ancestor `.cage`: build it under `tempfile.gettempdir()`, or have `_env` pin the root explicitly. Found 2026-08-03 while fixing CI-S18 | 
| **KIRO-MCP-FIELD** | the committed path-free `python3 -m cage mcp` has never started on a real Kiro | open Kiro on a wired repo; if it does not start, **report it** — do not fall back to a gitignored absolute path |

### Tier 5 — blocked, gated or parked · do not pick up before the trigger fires

| # | what | next action |
|---|---|---|
| **HR-COPILOT-JOIN** | copilot-vscode has per-request timestamps but stamps **no `project`**, so every one of its calls is excluded as *unconfirmable* — the join is built and cannot fire for it | **unblocked 2026-08-02** (was sequenced after REV-TS): stamp `project` on the vscode chat-store parse (the claude `cwd` precedent), then it window-joins for free. Still a capture change |
| **GF-LAUNCHER** | under `--python-launcher` neither twin meters (B5) | a decision — must move both twins |
| **TOOL-SDK** | the paved road: next tool ≠ 34 modules; fux is the proof | [proposal](proposals/tool-integration-contract.proposal.md) — builds on [shim-contract](shim-contract.md) |
| **KIRO-CLI-SCOPE** | kiro-CLI credits captured while the cwd sits outside any project reach only a *machine-ledger* sweep. Nothing is lost (the store is re-read), but a user who never runs a project-less `cage import` never sees them | carried forward from K2 — **revisit if it turns out to be common**; no action until then |
| **COPILOT-SIDECAR** | the deferred half of COPILOT-CREDITS: `agentHostUsage/<session>.jsonl` carries per-call `cacheReadTokens` (the vscode `cached` column is honestly empty without it) + the **real routed model** behind `copilot/auto`. Debug-gated and deleted with its session | trigger R3 of the [compare](compare/copilot-pricing-basis.compare.md) — parked, not lost. **Note the old OPEN-WORK phrasing said `elapsedMs`→`gap_ms`: `gap_ms` was removed with the human axis in v0.36, so that half is void, not pending** |

## Implementation — the open fix tiers

Verified against HEAD 2026-08-02 before being ranked. Enough to write a pair from; the
pair still owns the edge cases ([doc-size discipline](doc-size-discipline.md) rule 2 —
this file is the decider's, not the executor's).

**REV-HARDEN P2 · adoption `--since`** · half A row-filters (`adoption.py:105`,
`ledger.since(...)`); half B (`:188`) uses `ledger.receipts(root, since=…)` → `read_kind`,
which skips **whole months** and applies **no row filter**. One `--since` therefore
answers two different questions in one table. Wrap half B in `ledger.since(...)`. The
masking test's stale row sits in a fully-skipped month — move it in-month or it keeps
passing.

**REV-HARDEN P2 · the fabricated `$0`** — *the review pointed at the wrong module.*
`otelout._savings_row` (`:102–104`) **already omits correctly** on `None`. The hard
`0.0` is `convert.py:35–36`. Fix it there with an Optional-returning variant that owns
the unpriced-vs-genuinely-zero distinction; fixing it in `otelout` would put a **second
copy of the pricing ladder** there, and the credits rung already drifted between two
copies once.

**REV-CREDITS defect 1** · `transcript.py:446–447` advances `prev_cred`, then `:459`
`if not (din or dout): continue` runs **before** `:466` `credits=cred_delta if i == 0`.
First-listed model idles ⇒ delta on the floor, no row carries it, no debug log, billed
spend permanently undercounted. Stamp the delta on a row the loop actually emits
(deterministic pick, never dict order). **Defect 2 (multi-model double-counting) is not
landable here** — it is a real basis fork and belongs in
[copilot-pricing-basis.compare.md](compare/copilot-pricing-basis.compare.md). Do not
decide it inside a fix commit.

**CLI-GAPS** · (a) `cage --help` lists seven of `data`'s eight commands —
`migrate-savings` is unadvertised: one-line fix + golden re-bless, rides tier 3's
sitting. **(b) stays parked** — converting `prices`/`study`/`policy` to real subparsers
re-blesses goldens and touches `test_cli_tiering`'s help fixture; it is a front-door
change and earns its own decision, not a ride-along.

**ADOPT-COV — the trigger and the guard rail** (this was the only home for it). Half B
attributes only rows whose `call` or `session` resolves, and **the shim route can never
be one of them**; on the dev ledger that route has produced *zero* rows, so the view has
never been exercised against the path most real invocations take. Measured: **3 of 6**
savings rows attributable by session, **6 of 6** once legacy `call`-linked rows count —
one of which is a `cage demo` seed. That is n≈1 and proves nothing about the shim.
**Run** a lab cell that invokes graphify through the **PATH interceptor** for each of the
three agents, then read `cage insights adoption`. **If half B is empty there, the finding
is *the shim route is structurally unattributable* — report it.** Adding an `agent` field
to usage rows (or an env-stamped agent hint on the shim) is a **capture change and needs
its own proposal**; it must not be slipped in as a fix to a number nobody has measured.

**Gates for all of the above.** Each tier lands as its own change with its own green
run; **no tier is a phase of a program** (a percentage against this queue is meaningless
— the queue grows as work is found). **Every tier-0/1/2 fix ships with a test that fails
before it**: all of them were confirmed against a green suite, so "green after" proves
nothing on its own. Any item whose verify contradicts this section — **the code wins**,
and this section gets corrected.

**The strongest case against this order.** Ship NET-1 first and let the fixes wait: cage
exists to answer whether the tooling pays, and correctness work is infinitely available
in a way that expands to fill whatever time it is given. It survived only because the two
lanes never compete — NET-1 was asked to wait for one line of ID-ENTROPY and nothing
more, **and that line landed 2026-08-02, so the objection is now moot**: NET-1 is
unblocked and the fix tiers cost it nothing. Where the objection still lands: tiers 3–5
must not grow on enthusiasm.

## Standing constraints

Everything else that used to sit below this line was **completed work**, and completed
work is removed, not ticked (CLAUDE.md *Documentation discipline*). Each block was
checked against its record before deletion — all fifteen are in
[IMPLEMENTATION.md](IMPLEMENTATION.md); README-FIX's record is the v0.37.2 entry in
[CHANGELOG.md](../CHANGELOG.md). What survives here is only what still **binds future
work**.

**Three agents at every tier is a gate, not an aspiration** — claude · copilot · kiro,
or the gap is *named in output*. Shapes differ and matter: copilot hooks CAN be committed
(`.github/hooks/*.json` is repo-level and portable); both sources **combine**, so wiring
both double-fires; kiro's hook file is one hook per file with no session-start.

**Adding or removing a layer must change no number** — enforced by
[tests/test_floor.py](../tests/test_floor.py), which installs every layer cage ships onto
an already-captured project and asserts ledger shards **and** seven derived views'
stdout byte-identical, then strips the wiring and asserts it again, per agent. A new
layer is wired in by adding its artifacts to `_WIRING_ARTIFACTS` — **never** by relaxing
an assertion.

**Every piece of wiring is committed; only the *records* are not** —
`ledger/`/`out/`/`state/` are gitignored and team numbers come from
`refs/notes/cage-ledger` (ADR 0001). Every layer's wiring must work for a teammate on
another machine.

**`attest.LIMIT` says hooks are CLI-only — and that claim is now in dispute.** A
`PreToolUse` hook fired unprompted inside a session whose own system prompt says VS Code
([finding](regression/2026-08-02-finding-hooks-fire-in-vscode-extension.md)). Until
**L1-FIELD** resolves it, do not present L1's agent identity or auto task-close as "cage
knows which agent ran" — and do not delete the limit either.

**Auto-close writes `outcome="auto"`, never `ok`** — closed for cost comparison,
invisible to `cage task quality`. A session ending is not a job well done.

**No unverified host event name is ever invented** — copilot gets identity + auto-close
but no pre-tool hook, named in `agents.HOOK_GAPS`.

**The lab corpus is FROZEN (decided 2026-08-01).** `tinyshop` is never mutated; a new
question gets a **new named corpus alongside** it, and every result is labelled by the
corpus that produced it, so old evidence stays valid forever. Whether tinyshop is too
*small* is a separate filed question: [proposal](proposals/larger-lab-corpus.proposal.md).

**Budget ceilings are opt-in via `cage.toml`** (decided 2026-08-01) — the bundle ships
`[budgets]` commented out, with no constant fallback.

**Binds the next lab run:** F2's copilot-VS-Code receipt limit is **UNTESTED** — never
claim it confirmed. **Record the prompt count per cell as it runs** — D3/D4 are
UNVERIFIED without it.

**Windows is CI-executed but still not field-validated** (the README says so). The kiro
MCP default is `python3` because a committed file can carry only one spelling; doctor
points a Windows machine at `cage setup --python-launcher` for the `py -3` form. A stated
limit, not a bug.

**Corrections worth not re-learning:** `tests/test_portable_wiring.py` — cited by
CLAUDE.md and by past prompts — **has never existed**; the greps live in `test_agents.py`
and `test_mcp_layer.py`. And **ADOPT-COV is not closed by L1 attestation** — that fixed
adoption's half A only; half B's `NO_LINK` is still structurally true.


## How this file is maintained

Continuously; completed items **deleted, not ticked**; its own markers are never
evidence. Full law: [`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*.
Done work: [IMPLEMENTATION.md](IMPLEMENTATION.md) · evidence: [regression/](regression/).
