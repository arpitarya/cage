"""One source text, three deliveries — the agent-facing prose layer (L1 steering, L3
skills).

**The rule this module exists to enforce:** a document that lands on one agent and not
the others is not done, and three hand-maintained copies drift. So every document is
authored **once** as a :class:`Doc` and rendered into each agent's idiomatic home by
:func:`install`. The bodies are byte-identical across the three; only the host wrapper
(frontmatter shape and file location) differs, and that wrapper is ~10 lines of code
rather than a build step.

**Why in code rather than a bundled asset.** The predecessor (`tools/skillgen`, deleted
in v0.36) rendered these into `cage/data/{skills,prompts,steering}/`, which meant a
CI drift-check, a `--bless` gate, and a committed copy that could disagree with its
source. Rendering at `cage setup` time from a Python literal removes the whole class:
there is no second copy to drift, nothing to re-bless, and no bundled asset — which is
why `tests/test_floor.py` still asserts those data directories do not exist.

**The governing rule for the CONTENT, which no future edit may relax:**

    A cage document never computes a number. It runs cage and quotes it.

Method tags (`measured` / `modeled` / `estimated`) are relayed verbatim, refusals
(`INSUFFICIENT DATA`, `SAVING (GROSS)`, a `MIN_COMPARE_N` block) are passed through
unsmoothed, and no document performs arithmetic of its own. A document that added two
of cage's numbers together would be a second, unversioned implementation of the
attribution engine, tagged by nobody. :func:`lint` checks this mechanically and
`tests/test_steering.py` runs it over every document.

Everything here is **opt-in and committed**: `cage setup --hooks` writes the L1
steering doc, `cage setup --skills` the L3 skills, and a project that asks for neither
is byte-identical to one that never heard of them.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from cage import agents


class Doc(NamedTuple):
    """One authored document. ``body`` is the single source: the same bytes reach all
    three agents. ``trigger`` is the one-line "when should you read this" every host
    puts in its own frontmatter field."""
    id: str
    title: str
    trigger: str
    body: str
    layer: str = "L1"      # "L1" steering (with --hooks) or "L3" skill (with --skills)


# Where each agent's documents live. **Committed, project-relative, no machine path** —
# `tests/test_floor.py` lists all three so a bare project is asserted free of them.
HOMES = {
    "claude": ".claude/skills/{id}/SKILL.md",
    "copilot": ".github/prompts/{id}.prompt.md",
    "kiro": ".kiro/steering/{id}.md",
}

# Phrases a document may never contain: each one is a promise to do arithmetic cage has
# already done, or to soften something cage deliberately said plainly. Checked by
# `lint`, which the test suite runs over every document — the honesty rule is enforced
# mechanically rather than trusted to review.
BANNED = (
    "calculate the", "compute the total", "add up", "sum the", "estimate the cost yourself",
    "approximate", "roughly", "ignore the caveat", "omit the caveat", "simplify the number",
)


def _frontmatter(agent: str, doc: Doc) -> str:
    """The host wrapper. This is the ONLY per-agent difference — deliberately, so that
    "one source, three deliveries" is a property of the code and not a discipline."""
    if agent == "claude":
        return (f"---\nname: {doc.id}\ndescription: {doc.trigger}\n---\n\n"
                f"# {doc.title}\n\n")
    if agent == "copilot":
        return f"---\nmode: agent\ndescription: {doc.trigger}\n---\n\n# {doc.title}\n\n"
    # Kiro steering: `manual` inclusion — the agent pulls it in with `#<id>` rather than
    # having it forced into every context window. A cost tool that silently taxed every
    # prompt with its own prose would be an especially poor joke.
    return (f"---\ninclusion: manual\n---\n\n# {doc.title}\n\n"
            f"> {doc.trigger}\n\n")


def render(agent: str, doc: Doc) -> str:
    """The document as that agent receives it. Body bytes are identical across agents;
    only the wrapper differs (asserted in `tests/test_steering.py`)."""
    return _frontmatter(agent, doc) + doc.body.strip() + "\n"


def lint(doc: Doc) -> list[str]:
    """Every way this document breaks the governing rule. Empty list = clean.

    Mechanical, not stylistic: it looks for language that promises cage's job rather
    than quoting cage's answer. A new failure mode is added here, not argued about in
    review."""
    problems = []
    low = doc.body.lower()
    for phrase in BANNED:
        if phrase in low:
            problems.append(f"{doc.id}: says {phrase!r} — a document quotes cage's "
                            f"numbers, it never produces its own")
    if "cage " not in low:
        problems.append(f"{doc.id}: names no cage command — a document that quotes "
                        f"nothing has nothing to quote")
    return problems


def paths_for(root: Path, doc: Doc) -> dict[str, Path]:
    """Where this document lands, per agent. Always all three — the parity rule is
    structural here, not a checklist item."""
    return {a: root / HOMES[a].format(id=doc.id) for a in agents.SURFACES}


def install(root: Path, docs, surfaces: tuple[str, ...] | None = None) -> dict[str, int]:
    """Write every document to every picked agent's home. Byte-compared before writing,
    so `cage setup` twice produces no diff. Returns ``{agent: count}``."""
    picked = surfaces or agents.SURFACES
    written = {a: 0 for a in picked}
    for doc in docs:
        for agent, path in paths_for(root, doc).items():
            if agent not in written:
                continue
            text = render(agent, doc)
            if path.exists() and path.read_text(encoding="utf-8") == text:
                written[agent] += 1
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written[agent] += 1
    return written


def uninstall(root: Path, docs, surfaces: tuple[str, ...] | None = None) -> int:
    """Remove cage's documents (the off-switch — every layer above L0 is two-way).
    Only files cage would itself have written are touched; a directory is removed only
    when cage emptied it."""
    picked = surfaces or agents.SURFACES
    removed = 0
    for doc in docs:
        for agent, path in paths_for(root, doc).items():
            if agent in picked and path.exists():
                path.unlink()
                removed += 1
                parent = path.parent
                # `.claude/skills/<id>/` is cage's own directory; the other two homes
                # are shared, so only an empty one is cleaned up.
                try:
                    if not any(parent.iterdir()):
                        parent.rmdir()
                except OSError:
                    pass
    return removed


def by_layer(layer: str) -> list[Doc]:
    return [d for d in DOCS if d.layer == layer]


# ── the documents ────────────────────────────────────────────────────────────
# Authored once, here. Add to this list to add a document to all three agents at once;
# there is no other place to edit and no second copy to keep in step.

_L1_STEERING = Doc(
    id="cage-context",
    title="Cage — what it is and what to ask it",
    trigger=("Read before answering what something cost, whether a tool is worth "
             "keeping, or whether spend is within budget."),
    layer="L1",
    body="""
This project meters its LLM traffic with **cage** — a deterministic attribution ledger.
It costs nothing to query: every view is arithmetic over an append-only log, with no
model call on the read path.

## The one rule when you use it

**Never produce a cage number yourself. Run cage and quote what it says.**

- Copy **method tags** through verbatim. `measured` is an invoice. `modeled` and
  `estimated` are reconstructions. They are not interchangeable, and dropping the tag
  turns a reconstruction into a claim.
- **Relay refusals; never smooth them.** `INSUFFICIENT DATA` means cage declines to
  answer — report that, do not substitute zero or "no savings". `SAVING (GROSS)` means
  the cost of *using* the tool is excluded and unknown, so it is not a proven saving.
  A blocked comparison means too few closed tasks, not "no difference".
- Do no arithmetic on cage's output. If two numbers need combining, there is a cage
  view that already does it correctly.

## What to run

| question | command |
|---|---|
| what has this cost? | `cage report --by agent --since 7d` |
| which tool actually saved anything? | `cage insights attrib` |
| is tool X worth keeping? | `cage insights verdict <tool>` |
| did the stack with X really cost less? | `cage insights compare` |
| are we over budget? | `cage insights budget` |
| do the agents actually use the tools? | `cage insights adoption` |
| why is this number what it is? | `cage query "how is attribution calculated"` |

If MCP is wired, the same views are available as tools (`cage_report`, `cage_attrib`,
`cage_verdict`, `cage_compare`, …) and return the same text — quote it the same way.

## Close your tasks

`compare`, `estimate` and `calibration` can say nothing about work nobody closed. When
a unit of work finishes, close it: `cage task outcome <task>` (or the `cage_task_outcome`
MCP tool, the only write tool cage exposes). One short label, never a sentence or a path.

## What cage never has

Prompt text. The ledger carries token *counts* only, so no cage output can leak what
anyone wrote — and no cage command will produce it for you if asked.
""",
)

_SKILL_TASK_CLOSER = Doc(
    id="cage-task-closer",
    title="Close a cage task",
    trigger=("Use when a unit of work finishes. compare / estimate / calibration can "
             "say nothing about tasks nobody closed."),
    layer="L3",
    body="""
Closing a task is what turns a pile of metered calls into a comparable unit of work.
`cage insights compare`, `cage insights estimate` and `cage insights calibration` all
read **closed** tasks only — they are not thin because cage is bad at statistics, they
are thin because nobody closes anything.

## Do this

```bash
cage task outcome <task-id>              # the work succeeded
cage task outcome <task-id> --redo       # it had to be redone
cage task outcome <task-id> --label bugfix
```

With MCP wired, `cage_task_outcome` does the same thing. It is the **only** write tool
cage exposes — if a job seems to need a second one, it does not.

## The label rule

One short token: letters, digits, `.`, `_`, `-`, at most 32 characters. It is a
**grouping key** for `cage insights compare --by label`, not a description. Never a
sentence, a file path, or a commit message — cage will reject those, and the rejection
is correct rather than an obstacle to work around.

## What you must not do

- **Do not guess the outcome.** `ok` means the work stood up; `--redo` means it did not.
  If you genuinely cannot tell, leave the task open and say so — an invented `ok`
  inflates the success rate `cage task quality` reports, permanently and silently.
- **Do not close a task twice to change your mind about it.** Re-closing appends a
  superseding row; the earlier one stays on disk. That is by design, not a bug to route
  around.
- A session-end hook may already have closed the task as `outcome=auto` — which means
  *closed for cost comparison, no success claimed*. Replacing that with a real verdict
  is useful; replacing it with a guessed one is not.
""",
)

_SKILL_ANALYST = Doc(
    id="cage-analyst",
    title="Answer a cost or savings question from the cage ledger",
    trigger=("Use for 'what did this cost', 'which tool earned its keep', 'are we over "
             "budget'. Quote cage; never compute."),
    layer="L3",
    body="""
## The rule that outranks the question being asked

**Run cage and quote it. Never produce the number yourself.** Every view below is
already correct, already tagged, and already refuses when it should. Anything you
calculate on top is an untagged second implementation of the attribution engine.

## Pick the view

| the question | the command |
|---|---|
| what did we spend? | `cage report --by agent --since 7d` (`--by route/model/day`) |
| what did each tool save? | `cage insights attrib` |
| is tool X worth keeping? | `cage insights verdict <tool>` |
| did the stack with X really cost less? | `cage insights compare` |
| what would other tool combinations have cost? | `cage insights matrix` |
| are we over budget? | `cage insights budget` |
| do the agents actually invoke the tools? | `cage insights adoption` |
| where did this one number come from? | `cage insights why <call-id>` |
| how is this calculated? | `cage query "how is attribution calculated"` |

Add `--csv` to hand over a spreadsheet; the CSV carries the same method tags as columns.

## Relaying the answer

- **Method tags are part of the number.** `measured` is an invoice. `modeled` and
  `estimated` are reconstructions. Carry the word through into your sentence — "$4.10,
  modeled" is honest; "$4.10" is not.
- **`SAVING (GROSS)` is not a saving.** It means the cost of *using* the tool is
  excluded and unknown. Say so. `COSTING` has no such qualifier and can be stated flat,
  because the omitted term only makes it more negative.
- **`INSUFFICIENT DATA` is the answer, not the absence of one.** Report the refusal and
  what would lift it (usually: close more tasks). Never substitute zero, never write
  "no savings", never fall back to a different view that happens to produce a number.
- **A blocked comparison means too few closed tasks**, not "no difference between the
  stacks". The block prints its own `n`; quote that.
- **Do not add cage's numbers together.** Savings across tools are marginal against a
  fixed pipeline order — summing them double-counts. `cage insights attrib` already did
  the arithmetic correctly.

## If a number looks wrong

`cage insights why <call-id>` shows the call and every receipt against it, and
`cage query <topic>` prints the live formula with this project's actual policy values
interpolated. Between them there is no number in cage you have to take on faith — so
do not guess at one, and do not explain one you have not looked up.
""",
)

_SKILL_DOCTOR_TRIAGE = Doc(
    id="cage-doctor-triage",
    title="Diagnose why cage captured nothing",
    trigger=("Use when cage reports no spend, no savings, or a suspiciously empty view "
             "— capture failures are silent by nature."),
    layer="L3",
    body="""
Cage's write paths are **fail-open**: they never raise into your turn. The cost of that
is that a broken capture path looks exactly like an idle one. Work the ladder in order
rather than guessing.

```bash
cage doctor              # every check, with the failing one named
cage doctor --paths      # every log location probed on THIS machine, and why one missed
cage doctor --wiring     # per-artifact inventory: current / stale / dead / foreign
cage doctor --bundle     # one redacted archive to hand over (counts, never content)
```

## Read the results in this order

1. **`wiring` fails** — an installed command names a verb that no longer exists. This is
   the one that hurts: a dead verb exits 1 with its output going nowhere, so it is
   **indistinguishable from cage not being installed**. `cage setup` heals it.
2. **`interceptor`** — existence is not liveness. A `bin/graphify` that exists, is on
   PATH, and probes a removed verb will silently run the unmetered binary. Doctor
   checks the verb, not just the file. On Windows, a project carrying only the twin
   that OS cannot resolve is a **failure**, not a tick.
3. **`kiro-mcp`** — the path-free MCP entry depends on which `python3` resolves. If that
   interpreter cannot import cage, Kiro starts no server and reports nothing.
4. **`timeline` / `capture-quality`** — per-source, per-mode: when each agent's log was
   last read. An agent that never appears was never captured, and that is a different
   problem from one whose rows are thin.

## The distinction to keep straight

**"cage is not installed" ≠ "cage is installed and broken".** The first is fine and
silent by design; the second is also silent, which is why doctor exists. Never report
"capture is working" on the strength of a file existing.

## Never do

- Do not conclude anything from an empty `cage report` alone. Run `cage doctor` first.
- Do not fix a capture gap by editing the ledger. The ledger is append-only and every
  view derives from it; a hand-edited row is a fabricated invoice.
- Do not set `CAGE_DEBUG=1` and then quote the debug log as evidence of spend. It is a
  diagnostic trace, never a record.
""",
)

_SKILL_HONESTY_REVIEWER = Doc(
    id="cage-honesty-reviewer",
    title="Review a diff for method-law violations",
    trigger=("Use when reviewing changes to cage or anything that renders its numbers. "
             "Checks honesty, not style."),
    layer="L3",
    body="""
Cage's product *is* the honesty of its numbers. These are the ways that gets lost, in
the order they actually happen. Review a diff against them specifically — this is not a
general code review.

## 1. A projection rendered as an invoice

Only the configuration actually run is `measured`. A reconstructed counterfactual is
`modeled` or `estimated`. **Every cell carries its tag.** Look for: a new render path
that drops the `method` column, a summary line that states a modeled figure without the
word, a CSV that keeps the number and loses the tag.

## 2. A fabricated zero

An unknown must render as `—` or be **omitted**, never as `0`. A zero is a measurement.
Look for: `or 0`, `get(..., 0)`, `float(x or 0)` on a field that can legitimately be
absent — particularly latency, cost, and anything priced.

## 3. A dropped caveat

`SAVING (GROSS)`, `UNPRICED`, the observational note on a comparison delta, a min-n
block, the CLI-only limit on a hook-derived fact. These travel **with** the number, into
every surface: text, CSV, MCP, and any summary. A refusal that reaches one surface and
not another is the bug.

## 4. A refusal turned into a value

`INSUFFICIENT DATA` must not become `0`, `""`, an empty table, or a silently skipped
section. Look for an `except` that swallows a refusal, an `if not data: return` that
renders nothing where the CLI would have explained itself, and any default that fills a
gap the code could not fill honestly.

## 5. Two implementations of one number

Text and CSV must render from **one** data structure. A second computation is a second
answer waiting to disagree. Look for arithmetic inside a renderer.

## 6. Determinism lost

No clock, no randomness, on any read path. Same ledger + same policy ⇒ same bytes. Look
for `datetime.now()`, `Math.random`-equivalents, dict iteration that is not sorted, and
anything that makes output depend on when it ran.

## 7. Content where only counts belong

The ledger carries token counts, never prompt bodies. A new field holding a query, a
path, a commit message, or a file list is a PII regression. Hashes and counts are fine;
the text is not.

## How to check, rather than argue

Two of the seven are checkable rather than debatable, so check them:

```bash
cage query <topic>       # the LIVE formula, with this project's policy interpolated —
                         # compare it against what the diff now computes
just test                # the golden fixtures are the per-command output contract;
                         # a rendered shape that changed without a re-bless is #1 or #3
```

If the diff changes a rendered shape deliberately, the golden must be re-blessed in the
same change. A re-bless that quietly drops a tag or a caveat is finding #1 or #3
wearing a green suite.

## How to report what you find

Quote the line, name which of the seven it is, and state the failure concretely — what
a reader of the output would be told that is not true. Do not soften it, and do not
report a style preference as an honesty finding; that dilutes the ones that matter.
""",
)

_SKILL_RELEASE = Doc(
    id="cage-release",
    title="Cut a cage release",
    trigger="Use when releasing a new cage version. Publishing from a laptop is refused.",
    layer="L3",
    body="""
## The one true flow

```bash
# 1. bump cage/__init__.py __version__
# 2. CHANGELOG.md: full notes, newest first, no skipped versions
# 3. README "What's new": 1-2 lines, REPLACING the previous entry (not appended)
# 4. refresh the "N tests passing" count in README + CLAUDE.md
just test                      # must be green before anything below
git commit && git push origin main
git tag vX.Y.Z && git push origin vX.Y.Z
gh release create vX.Y.Z       # <- THIS is the publish trigger
```

Creating the GitHub release fires `.github/workflows/publish.yml`, which builds and
publishes to PyPI over OIDC trusted publishing — no stored token, nothing to leak. It
also runs the independent `build-pyz` → `smoke-pyz` (3-OS) → `release-pyz` chain that
attaches `cage.pyz` + `SHA256SUMS`.

## Refuse these

- **`uv publish`, `twine upload`, or any hand upload.** CI is the sole publisher. A
  version on PyPI with no matching GitHub release is a release bug, not a shortcut that
  worked. If asked to publish locally, decline and point at `gh release create`.
- **A release with no changelog entry.** That is a release bug of the same class.
- **A release on a red suite.** Not "probably unrelated" — green, or no release.
- Uploading a locally built `cage.pyz`. `just pyz` is a smoke check only.

## Easy to forget

- The README keeps **only the latest** version's "What's new"; history lives in the
  changelog. Replace, do not append.
- `[meta] cage_version` derives from `__version__` at read time — nothing to hand-edit.
- `[meta] policy_version` is deliberately **not** coupled to the release: it is a
  content counter driving the `cage policy sync` recommendation. Bumping it per release
  would tell every project its defaults are stale when nothing changed.
- Archive any implemented `docs/*.{handoff,prompt}.md` pair into `docs/archive/` and
  link it from the changelog entry.
""",
)

_SKILL_LAB_RUNNER = Doc(
    id="cage-lab-runner",
    title="Run a cage-lab regression cell",
    trigger=("Use when running black-box regression or per-agent capture labs in the "
             "sibling cage-lab repo."),
    layer="L3",
    body="""
`cage-lab` is the out-of-tree **black-box** suite: it installs the shipped `cage` and
never imports it, which is the only way to catch packaging, entry-point and bundled-data
failures the in-tree suite structurally cannot see.

## The standing rule: every lab runs in its own venv, always

```bash
python3 -m venv .venv
# install cage + graphify into it, PINNED
export PATH="$LAB/bin:$LAB/.venv/bin:$PATH"     # explicit, in the driver
command -v graphify                              # written into the run manifest
```

**Never rely on shell activation.** A stale interceptor in an unrelated project once won
on PATH from *inside* cage-lab and silently unmetered every run — the experiment was
measuring the wrong binary and looked fine. The run must **prove its own PATH** and
`SETUP.md` must name the exact builds:

```bash
cage --version                # which cage is actually under test (marks a zipapp run)
cage doctor --paths           # every log location THIS lab's cage will read
```

Both go into the run manifest. A lab that cannot say which binary it exercised has not
measured anything, however green it looks.

A local `-e ../cage` install is allowed only while a release is pending, and must be
recorded as a **declared deviation** from the black-box rule.

## After every run, publish

Drop the dated report plus a prioritized `*-fixes.md` into `docs/regression/` in the
cage repo and add the row to its README index — that directory is append-only: publish
new findings, edit nothing existing.

```bash
CAGE_REAL_LEDGER=~/.cage python ../cage-lab/labs/run_all.py
```

## What a lab result may and may not say

- A green lab run on macOS is **not** Windows coverage. The PATH proof covers the POSIX
  twin only.
- VS Code extension subprocesses inherit VS Code's launch environment, so they are not
  covered by the driver's PATH and stay per-machine-verified.
- Report what the cell measured, not what it suggests. `unmeasurable` is a result.
""",
)

_SKILL_WINDOWS_SHIM = Doc(
    id="cage-windows-shim",
    title="Change a graphify interceptor twin",
    trigger=("Use before touching data/shims/graphify or graphify.cmd — they are a twin "
             "pair against one written contract."),
    layer="L3",
    body="""
The interceptor is **two implementations of one contract**
(`docs/shim-contract.md`): `data/shims/graphify` (POSIX sh) and `data/shims/graphify.cmd`
(Windows). Windows resolves a bare name only through `PATHEXT`, which has no
extensionless entry — so the sh shim alone could never be *found* there, and the shim
capture route was structurally absent on Windows until the twin existed.

## The rule

**Change a twin ⇒ change the contract, the other twin, and `pathshim._INTERCEPTOR`
together.** The marker set has three copies by necessity (sh `grep -E`, cmd
`findstr /C:`, Python regex). Drift there silently disables liveness detection *and*
re-enables the stacked-shim recursion — a failure with no error message.

## The behaviours both twins owe (B1–B8)

1. Re-entry guard, **both directions**.
2. PATH scan that skips **every** interceptor, not just this one.
3. Self-identification by **content, never filename**.
4. No real binary ⇒ exit **127**. Never fall back to a bare name.
5. Meter only if `cage data graphify --help` succeeds.
6. Transparent passthrough of args, stdin, stdout, stderr and exit code.
7. No leaked state.
8. A bounded walk.

## The divergences that cannot be removed (D1–D7)

Chiefly: **cmd has no `exec`**, so the real binary runs as a *child* — `call` followed by
`exit /b` **on its own line**. The one-line `& exit /b %ERRORLEVEL%` form expands at
parse time and reports the wrong exit code. And `<` / `>` inside a `rem` line are shell
redirections in batch, not text.

## Do not

- **Do not templatize the pair.** They are hand-paired on purpose
  (`docs/adr/0007`); templating stays off the table until a *third* interceptor exists
  and shares a syntax family with an existing one.
- Do not "fix" the 127 exit into a bare-name fallback. That reintroduces the recursion.
- Do not add a marker to one twin and plan to do the other later.
""",
)

DOCS: tuple[Doc, ...] = (
    _L1_STEERING,
    # L3, in the build order the design fixed: the write tool's skill first (it feeds
    # every starved surface), then reading, then diagnosis, then the repo disciplines.
    _SKILL_TASK_CLOSER, _SKILL_ANALYST, _SKILL_DOCTOR_TRIAGE, _SKILL_HONESTY_REVIEWER,
    _SKILL_RELEASE, _SKILL_LAB_RUNNER, _SKILL_WINDOWS_SHIM,
)
