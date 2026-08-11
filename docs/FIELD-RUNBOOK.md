# FIELD-RUNBOOK — the five things only Arpit's hands can do

Every open item in [OPEN-WORK.md](OPEN-WORK.md) needs a **real machine** or **real
accumulated usage**; none is agent-buildable. This file removes the setup cost from each
so a spare twenty minutes at the right machine closes one.

**Every command here was run against `cage 0.48.0`'s actual `--help` on 2026-08-11 — no
flag below is invented.** Where a step can only be verified by eye, it says so.

**The standing rule that governs all of them:** a run that fails is a *result*, not a
false start. Publish it to [regression/](regression/) either way. A negative with a named
cause outranks a rerun-until-green.

---

## 1 · L1-FIELD — the copilot and kiro legs (claude is done)

**Status:** claude leg field-verified 2026-08-02. Copilot and kiro have **never** been
wired on a real machine. Also open, and new as of 2026-08-11: the attested-by-hook table
prints **zero rows** on the dev ledger while the session-join produces seven
([evidence](regression/2026-08-11-adopt-cov-dev-ledger-read.md) §3).

    # on a machine with a real Copilot install, in a wired repo
    python3 -m cage setup --copilot --hooks
    python3 -m cage setup --status          # must list copilot as wired

    # now do ~10 minutes of ORDINARY work in Copilot — do not script it
    wc -l .cage/state/attest.jsonl          # non-zero == the hook fired unprompted

    # same, on a real Kiro
    python3 -m cage setup --kiro --hooks
    python3 -m cage setup --status

**What counts as the result**

| observation | what it means |
|---|---|
| `attest.jsonl` grows during ordinary work | hook is host-fired and live — the claim holds |
| file unchanged after real use | hook is **not** firing — report it, do not re-wire and retry |
| `--status` says wired but nothing fires | the honesty defect: status is asserting, not checking |

**Do not skip:** `cage setup --hooks` is OFF by default and *re-running `cage setup`
without `--hooks` removes them again*. If you re-run setup for any other reason mid-test,
you have silently unwired yourself.

**Carry-forward constraint (rescued from the archived review-hardening proposal, P3):**
until this verifies, `copilotwire`'s gaps text **must** say *"unverified on a real
Copilot"* — `sessionStart`/`sessionEnd` are cage's own invented names and `_session()`
assumes Claude's payload shape. That is the no-invented-event-names rule applied to
output honesty; do not let a green wire-up quietly delete it.

**The open tension:** `attest.LIMIT` says hooks are CLI-only, but a `PreToolUse` hook
fired inside a VS Code session
([finding](regression/2026-08-02-finding-hooks-fire-in-vscode-extension.md)). Resolve it
here or leave it standing — **do not delete the limit** on one green run.

---

## 2 · KIRO-MCP-FIELD — does the path-free MCP actually start?

**One question, one answer, five minutes.** The committed wiring is `python3 -m cage mcp`
because a committed file can carry only one spelling.

    # open Kiro on a wired repo. Then:
    python3 -m cage setup --status
    python3 -m cage doctor --wiring

**If it does not start: REPORT IT.** Do **not** fall back to a gitignored absolute path —
that is the failure this item exists to prevent. On Windows the documented answer is
`cage setup --python-launcher` (the `py -3` form), not a hand-edited path.

---

## 3 · GFX-KIRO-RATE — the number that reopens ADR 0009's veto

**The field run was n=2** (1 filed, 1 refused) — enough to prove both branches execute,
not enough to be a rate. [ADR 0009](adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md)
reopens the design **below a 10% file rate**.

**This one cannot be forced.** It needs *accumulated ordinary kiro-cli graphify usage* —
scripting it produces a rate for synthetic queries, which is not the question.

    # after real use has accumulated, re-run the field script in:
    #   docs/regression/2026-08-07-gfx-cov-kiro-field-run.md
    python3 -m cage insights adoption

**Publish the rate to `regression/` before any code change.** If typical `query` output
sits above kiro's ~2000-token stdout cap, *report-read-only may be the honest kiro
answer* — that is a legitimate outcome, not a defeat.

---

## 4 · HR-FIELD — the four-bucket split on a repo that isn't cage

**The bias is known and named:** the split has only ever been read on cage's own repo,
which is unusually doc- and artifact-heavy — **80% `unattributed`**.

    # in a SECOND, code-heavy repo you actually work in
    python3 -m cage setup --claude
    # ... work normally for a while, then:
    python3 -m cage insights commits
    python3 -m cage insights commit <sha>    # the per-file detail

**The pre-committed reading — decide it before you look:**

- `unattributed` **drops** on a code-heavy repo → the buckets are fine, cage's own repo
  was the outlier. Close HR-FIELD.
- `unattributed` **still dominates** → the buckets are not the problem; **the per-file
  table is the surface that needs work**. That is the finding, and it re-scopes the item
  rather than closing it.

---

## 5 · NET-1 — does graphify actually pay?

**The only item that answers cage's own reason for existing.** No code, no gate — its
last gate (ID-ENTROPY) closed 2026-08-02. Protocol:
[proposal](proposals/net-positive-evidence-run.proposal.md).

- **n = 5 closed tasks per arm**, arms = with-graphify / without.
- **Outcomes pre-committed before the runs** — write down what "pays" means first.
- Corpus is **frozen**: `tinyshop` is never mutated. A new question gets a new named
  corpus alongside it, and every result is labelled by the corpus that produced it.

    python3 -m cage insights verdict     # the one-line answer, per tool
    python3 -m cage insights roi

**The pre-committed branch:** still net-negative at n=5 → that is the trigger for
[larger-lab-corpus](proposals/larger-lab-corpus.proposal.md) (tinyshop ~43 KB may
understate graphify), **not** a reason to re-run until it turns positive.

**Record the prompt count per cell as it runs** — D3/D4 are UNVERIFIED without it, and
F2's copilot-VS-Code receipt limit is **UNTESTED**; never claim it confirmed.
