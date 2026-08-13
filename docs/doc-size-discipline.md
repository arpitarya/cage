---
doc: document size discipline
status: ⏳ TRIAL — expires 2026-09-01
audience: any agent authoring a doc in this repo
---

# Document size discipline — the full spec

**⏳ TRIAL. Expires 2026-09-01. Lapses if unreviewed.** Summary rule lives in
[`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*; this is the detail an
executing agent needs. If the two disagree, CLAUDE.md wins.

**Why it exists:** Arpit stopped reading the plans. A plan nobody reads is not a
plan — it is a record of intentions with no reader, which is worse than no plan
because it *looks* like coordination.

---

## The four rules

### 1. Lead with the answer

First ~5 lines: what's next · what's blocked · what changed. A reader who stops
there has the useful part. Detail follows, never precedes.

- **Not** background → context → history → *then* the point.
- A plan's first table row should be the thing to do next.

### 2. One audience per doc

Three audiences exist and they want different things:

| audience | wants | lives in |
|---|---|---|
| **Arpit (decider)** | what to decide, what's blocked | the plan |
| **executing agent** | how to build it, constraints, edge cases | handoff + prompt |
| **future reader** | why it was done this way | ADR, design doc |

Writing for all three at once is what makes a doc unreadable to all three. Pick one.

### 3. Evidence lives elsewhere, always

State the claim, link the proof.

- **Bad:** `saved` is mislabelled — D2 (ON) cost ~14% more than D1 (OFF): +37% calls,
  +29% tokens in, +78% out, while cage recorded 18,456 saved, because `saved` is a
  per-query counterfactual that never nets the query turn or the hook tax…
- **Good:** `saved` is mislabelled (gross, not net) — [finding](../work/regression/2026-08-01-finding-saved-is-gross.md)

The homes already exist: `regression/` (measurements) · `archive/` (shipped specs) ·
`IMPLEMENTATION.md` (what was built) · `adr/` (why).

### 4. A hard budget

- A **plan** fits one screen — **~40 lines**.
- A **table row** is *genuinely* one line — **≤120 characters of *rendered* text**.
  "One line each" means one line, not a paragraph in a cell. This is the rule most
  often broken.
  **Measure rendered, not raw** — strip markdown link targets, `*`, and backticks
  before counting. A `[finding](regression/2026-08-01-finding-….md)` link costs ~60
  raw characters and zero reading burden, so counting raw punishes exactly the
  linking that rule 3 requires. *(Trial amendment, 2026-08-01 — found on the first
  application of the rule; the check below is the measurement.)*

```bash
python3 - <<'EOF'
import re,sys
for l in open(sys.argv[1] if len(sys.argv)>1 else 'work/OPEN-WORK.md'):
    if l.startswith('|') and '---' not in l:
        r=re.sub(r'\[([^\]]*)\]\([^)]*\)',r'\1',l).replace('*','').replace('`','').rstrip()
        if len(r)>120: print(f"OVER {len(r)}: {r[:70]}")
EOF
```
- Over budget ⇒ **move content out**, never compress in place. Shrinking prose to
  fit produces dense unreadable text, which is the original problem wearing a
  smaller coat.

**Exemption:** reference docs — `CLAUDE.md`, `PLAN.md`, the design docs — are exempt
from **rule 4 only**. They are dense on purpose and CLAUDE.md is loaded into every
agent's context, where density is load-bearing. Rules 1–3 bind them fully.

---

## Fixing an over-budget doc

1. **Find the audience violations first** — usually 60% of the bulk is build detail
   or rationale sitting in a plan. Move it, don't summarize it.
2. **Then the evidence** — replace inlined numbers with a link to the doc that owns
   them. If no doc owns them, that's a missing finding doc, not a reason to inline.
3. **Then rewrite rows to one line.** If a row can't say it in 120 chars, the item
   is really two items, or it needs its own section below the index.
4. **Re-check rule 1** — after cutting, is the first thing a reader sees still the
   most useful thing?

Never delete content that has no other home. Move it, then link it.

---

## The trial: how it ends

**On 2026-09-01 this must be explicitly retained, amended, or removed.** Unreviewed
⇒ it lapses. That asymmetry is deliberate — a trial that silently persists is just a
rule that was never tested.

Judge it on evidence, not preference:

| question | evidence to check |
|---|---|
| Did it work? | Does Arpit read the plan without complaint? That was the whole point |
| Did anything get lost? | Did a session have to hunt through links for something it needed inline? |
| Is it enforceable? | Count rule-4 violations since 2026-08-01. A rule agents routinely break isn't a rule |
| Did it cost quality? | Any decision made worse because context moved out of the doc? |

**Outcomes:** retain as-is · retain minus a rule that didn't earn its place · widen
(e.g. drop the reference-doc exemption) · remove entirely.

**Optional enforcement**, only if the trial is retained: a grep test for table rows
over 120 chars in plan docs — same class as the README test-count rule. Not built
during the trial on purpose; enforcing a rule before knowing it works is backwards.
