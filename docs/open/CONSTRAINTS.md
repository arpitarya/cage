# Standing constraints — what binds future work, regardless of which item you pick up

Not open work. Rules that survive their originating item. Split out of `OPEN-WORK.md`
2026-08-11 so the queue could become an index.

**Three agents at every tier is a gate, not an aspiration** — claude · copilot · kiro, or
the gap is *named in output*. Shapes differ and matter: copilot hooks CAN be committed
(`.github/hooks/*.json` is repo-level and portable); both sources **combine**, so wiring
both double-fires; kiro's hook file is one hook per file with no session-start.

**Adding or removing a layer must change no number** — enforced by
[tests/test_floor.py](../../tests/test_floor.py). A new layer is wired in by adding its
artifacts to `_WIRING_ARTIFACTS` — **never** by relaxing an assertion. If a phase cannot
meet the gate, the phase is wrong; the number is never what gets adjusted.

**Every piece of wiring is committed; only the *records* are not** — `ledger/`/`out/`/
`state/` are gitignored and team numbers come from `refs/notes/cage-ledger`
([ADR 0001](../adr/0001-ledger-team-aggregation-notes-not-external-sink.md)). Every
layer's wiring must work for a teammate on another machine.

**`attest.LIMIT` says hooks are CLI-only — and that claim is in dispute.** A `PreToolUse`
hook fired unprompted inside a session whose own system prompt says VS Code
([finding](../regression/2026-08-02-finding-hooks-fire-in-vscode-extension.md)). Until
[L1-FIELD](L1-FIELD.md) resolves it, do not present L1's agent identity or auto task-close
as "cage knows which agent ran" — **and do not delete the limit either.**

**Copilot's lifecycle gaps text must say "unverified on a real Copilot"** until
[L1-FIELD](L1-FIELD.md) verifies. *(Rescued 2026-08-11 from the archived review-hardening
proposal P3, where it was the only copy.)* `copilotwire.py` / `agents.py`:
`sessionStart`/`sessionEnd` are cage's **own invented names** and `_session()` assumes
Claude's `session_id` payload shape, while status output claims auto-close is wired. This
is the no-invented-event-names rule applied to output honesty — a green wire-up does not
retire it, a *verified* one does.

**The detector is the live parser — never a hand-kept migration map.** *(Rescued
2026-08-11 from the same archived proposal.)* REV-HARDEN P1 as filed asked for a
`verbmap.REMOVED`-style row of old event spellings; the build **declined it**, because a
hand-kept map goes stale in the very release that renames an event. Fix-hints derive from
live `hookcmd.EVENTS`. **Where a proposal and the shipped code disagree, the code wins.**

**Auto-close writes `outcome="auto"`, never `ok`** — closed for cost comparison, invisible
to `cage task quality`. A session ending is not a job well done.

**No unverified host event name is ever invented** — copilot gets identity + auto-close
but no pre-tool hook, named in `agents.HOOK_GAPS`.

**`cage setup --hooks` is OFF by default and re-running `cage setup` WITHOUT it removes
the hooks again.** Any mid-test re-run silently unwires you.

**The lab corpus is FROZEN (2026-08-01).** `tinyshop` is never mutated; a new question
gets a **new named corpus alongside** it, and every result is labelled by the corpus that
produced it, so old evidence stays valid forever. Whether tinyshop is too *small* is a
separate filed question: [proposal](../proposals/larger-lab-corpus.proposal.md).

**Budget ceilings are opt-in via `cage.toml`** (2026-08-01) — the bundle ships
`[budgets]` commented out, with no constant fallback.

**Binds the next lab run:** F2's copilot-VS-Code receipt limit is **UNTESTED** — never
claim it confirmed. **Record the prompt count per cell as it runs** — D3/D4 are UNVERIFIED
without it.

**Windows is CI-executed but still not field-validated.** The kiro MCP default is
`python3` because a committed file can carry only one spelling; doctor points a Windows
machine at `cage setup --python-launcher` for the `py -3` form. A stated limit, not a bug.

**Corrections worth not re-learning:** `tests/test_portable_wiring.py` — cited by
CLAUDE.md and by past prompts — **has never existed**; the greps live in `test_agents.py`
and `test_mcp_layer.py`.

**The standing gate.** Each item lands as its own change with its own green run; **no item
is a phase of a program** (a percentage against this queue is meaningless — the queue
grows as work is found). **Every fix ships with a test that fails before it**: everything
here was confirmed against a green suite, so "green after" proves nothing on its own. Any
item whose verify contradicts a doc — **the code wins**, and the doc gets corrected.
