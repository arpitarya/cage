# Handoff: ship everything built so far, then the remaining roadmap

**One-liner:** Get all committed-but-unshipped work (v0.31.4 + v0.32.0) live on PyPI, apply the
two approved CLAUDE.md edits, then execute the remaining capture-fix roadmap in order — each item
as its own investigate→debate→build cycle, not one blind run.

**Owner / executor:** Claude Code
**Status:** Phase 0 (ship) is decided and executable now. Phases 1+ are the roadmap — each needs
its own session; do NOT batch their execution.

**Why this shape:** every fix in this arc (F2, F1, stale-wiring) landed correctly because it was
investigated and debated before code was written — and the report's stated cause was wrong more
than once. Codex removal and the capture.log anomaly are not mechanical; blindly executing them
here would discard the discipline that's been working. So Phase 0 ships; the rest is sequenced,
not auto-run.

---

## Phase 0 — Ship everything built so far (DECIDED, execute now)

**State (verified):**
- `main` is **ahead of origin by 2**, unpushed: `0ffd02a` (v0.31.4) + `cfb74f6` (v0.32.0).
- Neither is tagged. Latest pushed tag is `v0.31.3`.
- PyPI `cage-flux` is likely at **0.31.2** (last confirmed publish); 0.31.3/0.31.4/0.32.0 all
  unpublished.
- Two CLAUDE.md edits from the v0.32.0 work are **proposed, not applied** (verified: grep = 0).

**0a. Apply the two approved CLAUDE.md edits.** Both reviewed and approved — apply verbatim:
1. The **Wiring liveness (`wiringscan.py`, v0.32.0)** paragraph in the *Adapters & agents*
   section (parser-is-the-detector, user-level scan, tiered severity, `cage query stale-wiring`).
2. The Must-Know rule **"A renamed or removed verb is a wiring migration, not just a CLI
   change"** (the `verbmap.REMOVED` + writer-sweep + dev-tooling-sweep requirement, guarded by
   `test_cli_tiering.py`). This one is high-value — it's the lesson that `install.sh`/`just demo`
   were broken for four versions because nothing checked.
Commit as a small docs commit (`docs: apply v0.32.0 CLAUDE.md steering — wiring liveness`).

**0b. Verify the pipeline is healthy before publishing** (READ-ONLY):
- `pip index versions cage-flux` (dist is `cage-flux`, NOT `cage`).
- `gh run list --workflow=publish.yml -L 3` — did the last `publish-pypi` conclude success?
- If the last run **failed**, STOP and report — fix the pipeline before stacking more releases
  (`skip-existing: true` makes re-runs safe).

**0c. Push + tag.** Push `main`. Tag `v0.31.4` (`0ffd02a`) and `v0.32.0` (`cfb74f6`); push both
tags. (`v0.31.3` is already tagged/pushed.) Tag pushes do not publish.

**0d. Publish v0.32.0 — Arpit has pre-authorized this** (his instruction: "publish everything
built so far"). Create the GitHub release for **v0.32.0** only — it is cumulative, so it carries
0.31.3/0.31.4's changes too. `gh release create v0.32.0` with notes from the README "What's new"
v0.32.0 entry. This fires `publish.yml` → PyPI (`cage-flux`) via OIDC.
- 0.31.3 and 0.31.4 stay **tags-only** (history); they do not each need a PyPI publish, and
  tag-without-release is not a release-bug (only PyPI-without-release/tag is). If Arpit later
  wants each on PyPI, that's a separate call.
- **Do not** run `uv publish`/`twine`/any local publish — the workflow is the sole publisher.

**0e. Confirm it landed.** Watch the new `publish.yml` run; confirm `cage-flux 0.32.0` appears on
PyPI (may lag a minute). Report the job conclusion and the live version. If it lags, say so.

**0f. Housekeeping.** `.claude/` stays untracked (deferred to Phase 2). Delete any remaining
throwaway prompt docs in `docs/` root — but **keep** `capture-architecture.{handoff,prompt}.md`
(Phase 2 live spec) and everything in `docs/archive/` and `docs/regression/`.

**Phase 0 Definition of done:**
- [ ] CLAUDE.md edits applied + committed
- [ ] `main` pushed; `v0.31.4` + `v0.32.0` tagged and pushed
- [ ] v0.32.0 GitHub release created; `publish-pypi` green; `cage-flux 0.32.0` live on PyPI
- [ ] Housekeeping done; `git status` clean apart from untracked `.claude/`

---

## The roadmap (Phases 1+) — each its OWN session, in this order

Do **not** execute these in the Phase 0 prompt. They are listed so the whole plan lives in one
place; each gets its own handoff/prompt when reached.

### Phase 1 — Remove Codex completely · plan **Opus**, execute **Sonnet** · NEXT
Arpit's standing decision (product/scope call, not a capture failure — Codex was actually one of
the healthier agents). Now unblocked and sequenced first: the v0.32.0 wiring inventory makes it
mechanical.
- **Nature:** needs a plan/design pass first (Opus) — it rewrites a product invariant ("four
  agents" → three: Claude Code · Copilot · Kiro), touches every wire surface, `agents.SURFACES`,
  `codexwire.py`, `paths` codex sources, `transcript.parse_codex_calls`, `importcmd.import_codex`,
  skill/steering assets (skillgen), tests, `tools/dummyrepo`, and `CLAUDE.md`'s "Four agents,
  always" rule.
- **Known consequences to decide in the plan:** `cage data limits` loses its **only** provider
  (Codex `rate_limits`) — decide if the feature dies with it. `MODEL_ROUTE_PREFIXES`/openai price
  rows may orphan. And the stale-wiring boundary: a post-removal `.codex/hooks.json` has a *live*
  verb but no owning surface — an **orphan** the liveness scanner reports clean; that cleanup
  belongs here.
- **Memory:** `cage-remove-codex` holds the surface map. Fold codex-removal into this plan.

### Phase 2 — Diagnose the `capture.log`/Jul-24 append anomaly · **Opus**
The last silent capture path: calls were appended to `~/.cage` on 2026-07-24 **without going
through `importcmd.run`** (so no `capture.log` line). CC's lead: the dead global Claude hook (now
fixed by v0.32.0) left `capture-on-read` (`importcmd.ensure_captured`) as the plausible sole live
appender — check whether `ensure_captured` actually reaches `_record_capture_log`
(`importcmd.run:495`). Investigate→propose→stop, like F1.

### Phase 3 — Deferred low-priority findings · **Sonnet** each, bundleable
- **F3** kiro thin log (coarse/input-only — partly inherent; doctor should distinguish "found but
  ~empty" and recommend the proxy).
- **F5** cache-split reporting (headline is 98% cache reads — add a cached-vs-fresh line to
  `report --usd`).
- **F7** `gap_ms` coverage (~1% of rows — verify `transcript.parse` stamps it broadly).

### Phase 4 — BLOCKED: Phase 2 hook deletion (capture-architecture)
Decisions made, change-map verified (`docs/capture-architecture.{handoff,prompt}.md`). Gated on
**field evidence** (`docs/phase2-field-gate.md`): a hooks-on vs hooks-off ledger comparison over
the same work. Needs imports running regularly to accrue — do not build until the gate passes.

---

## Non-negotiables (all phases)
- `$0`/stdlib-only; deterministic (derived views byte-identical); fail-open on capture writes,
  every swallow logged under `CAGE_DEBUG`; counts-never-content PII guard; `method` never reads
  `measured` for a projection.
- Every release: changelog + README "What's new" (replace) + `__version__` + test-count refresh;
  **GitHub release is the sole publish trigger**; never publish from a laptop.
- Handoff/prompt lifecycle: archive the pair on the release that ships it, link from CHANGELOG.
- CLAUDE.md steering edits are **proposed for review**, never silently rewritten — except the
  mechanical test-count line the rule mandates.

## Open questions
- **Phase 0:** publish 0.31.3/0.31.4 to PyPI individually, or v0.32.0-only (cumulative)?
  Recommendation: v0.32.0 only. (Arpit can override.)
- **Phase 1:** does `cage data limits` survive codex removal? Decide in the Phase 1 plan.
