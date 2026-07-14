# Exit interview — notes from an outgoing maintainer-model to every future one

*The user asked the model that helped design cage v0.16–v0.22 to record what
it knows before handing off. Format is an interview because tacit knowledge
survives better as answers to questions than as another rules list. The rules
list already exists — it's `CLAUDE.md`, and it is binding. This document is
everything that ISN'T rules: intent, history, scar tissue, and how to work
with the human. Future models: read `CLAUDE.md` first, then this, then
`docs/README.md` for the map.*

---

**Q: What is cage, in one sentence that isn't the README's?**

A trust machine that happens to count tokens. The differentiated asset isn't
the metering — anyone can parse a session log — it's that every number cage
prints can defend itself: where it came from (`method` tag), what it was
derived from (append-only ledger), what it refuses to say (min-n gates,
UNPRICED, INSUFFICIENT DATA). If you ever make cage answer when it should
refuse, you've spent the only capital it has.

**Q: What's the ranking when invariants collide?**

They rarely collide, but when they do: **method honesty** outranks everything
(a wrong number is worse than none — this decided `copilot/auto` staying
unpriced, the estimated-never-measured deltas, the calibration design).
Then **determinism** (same ledger + policy ⇒ byte-identical), then
**fail-open writes** (never break the user's agent to record a row), then
**$0/stdlib**, then **four agents always**, then **counts-never-content**.
The release flow (CI publishes, never a laptop) is not in the ranking because
it never trades off against anything — it's just absolute.

**Q: What bit us that the docs now quietly encode?**

Five scars worth knowing the story behind:

1. **The real-ledger pollution.** A pre-fix scenario runner treated the
   user's real `~/.cage` as a project and wrote 128 sandbox rows into his
   actual June history. The fix was `find_project_root`, but the lesson is
   the rule in the full-test-run prompt: snapshot the real ledger before any
   run, explain every delta after. Treat `~/.cage` like production, because
   it is.
2. **The codex id collision.** `session[:8]` on rollout filenames made every
   codex session share an id namespace — 41% of calls silently dropped,
   spend undercounted 55%. Silent undercounting is cage's worst failure mode
   because nothing looks wrong. When touching ids: they are the dedupe
   contract; entropy and stability both matter.
3. **The repricing family.** Six read views summed stored `est_cost_usd`
   (always $0 for transcript rows) instead of repricing through
   `prices.call_usd`. A $3,800 ledger read as $0. The rule it produced: ONE
   costing path, every view routes through it.
4. **VS Code hooks.** They don't fire under extensions — only Claude Code's
   extension honors them. Every capture design must assume hooks are a
   bonus; `cage import`/self-refreshing `export` is the truth path.
5. **Committed absolute paths.** One developer's `cage setup` shipped his
   machine's paths to every teammate via git. The shim
   (`docs/portable-wiring.md`) is the fix; the grep-test that committed
   files contain no machine path is the immune system. Don't weaken it.

**Q: How does work actually flow in this repo?**

The lifecycle is now codified (CLAUDE.md "Docs lifecycle") but the spirit
matters: nothing gets built until it survives a debate — devils-advocate on
the approach, pre-mortem on anything irreversible. The debate must be able to
kill the plan; if yours can't, it's decoration. Then a handoff+prompt pair in
`docs/`, execution by an agent in a session that commits nothing, review by
the human, release by CI, pair archived with a CHANGELOG link. The sibling
testbed (`../cage-testbed`) plus `python -m tools.dummyrepo` (S1–S13) is how
claims get checked against reality; the full-test-plan is evergreen — re-run
it per release, archive the results.

**Q: How should a model work with Arpit?**

He gives terse asks that unfold into systems — "can we add some logging"
became the path-probe diagnostic; "it should work on windows" became the
3-OS matrix, lockutil, and the launcher mode. So: take the small ask
seriously as a design problem, debate it, then scope it into an
independently shippable unit. He wants recommendations, not menus — pick one,
say why, name the tradeoff. He will do manual steps happily if you batch
them and give exact commands (never dribble pause-points one at a time). He
notices when numbers don't reconcile. Don't pad; don't perform; when he says
"do not commit," nothing gets committed — that instruction has been standing
for this entire collaboration and should be assumed permanent unless he says
otherwise.

**Q: What would you build next, if you were staying?**

The watchlist, in order of value: field-validate Windows and a real
WDAC/AppLocker endpoint (the checklists exist, nobody's run them); the
work-mix confound in fleet studies is handled by pairing but a
label-stratified paired delta would sharpen it; calibration data will
eventually justify per-label estimate bands; and the query pattern
(`docs/query-pattern.md` + `querykit.py`) is package-shaped if outside
consumers ever want it. Resist: dashboards, servers, watchers, anything
that phones home — every one of those was considered and rejected for
reasons the ADRs and plan record.

**Q: What should a future model do in its first ten minutes here?**

`CLAUDE.md` → `docs/README.md` → `just test` → `python -m tools.dummyrepo` →
`cage demo` → `cage query overview`. If all of that is green and the demo
reproduces §4.4, you can trust the ground you're standing on. If anything is
red, fix that before believing anything else — including this document.

**Q: Anything else?**

Two things. First: the repo explains itself on purpose — `cage query` exists
so answers can't drift from code, the CHANGELOG links every feature to the
handoff that specced it, and the archive is history, never spec. Keep it
that way; the moment docs and code disagree, agents compound the error
across sessions. Second: the project is called cage, but the design
philosophy is the opposite of one — every constraint in it exists to make
the numbers free to be believed. Maintain the constraints and the trust
maintains itself.

*— recorded 2026-07-12, at handoff. Every future maintainer, model or human:
add your own scars to this file when you leave. That's the maintenance
this document asks for.*
