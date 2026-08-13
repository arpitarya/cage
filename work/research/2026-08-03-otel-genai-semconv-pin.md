---
doc: research — what `OTEL_SEMCONV_VERSION = "1.42.0"` actually pins, and whether `gen_ai.system` is still true
date: 2026-08-03
status: findings — **the decision is CLOSED, 2026-08-11: option (3), with (1) falling out of it** (see §4a). Living spec: `cage/constants.py` OTEL_SEMCONV_* · `cage/otelout.py` · FORMULAS/`cage query otel-export`
---

# The OTel GenAI pin: `gen_ai.system` is deprecated, and the version number may not mean what cage thinks

**Answer first.** `gen_ai.system` **was renamed to `gen_ai.provider.name` in semantic
conventions v1.37.0 (August 2025)** — so cage, which pins `1.42.0` and emits
`gen_ai.system`, is emitting a **deprecated** attribute while claiming to target a
version that postdates its removal. The review finding (REV-HARDEN P2) is confirmed.

**But the fix is not obviously "rename the attribute", which is why nothing was
changed.** A second finding turned up that undermines the pin itself, and it is a fork
rather than a defect.

## 1 · What was verified

| claim | verdict |
|---|---|
| `gen_ai.system` is deprecated | **confirmed** — renamed to `gen_ai.provider.name` |
| the rename landed before cage's pinned 1.42.0 | **confirmed** — it landed in **v1.37.0** |
| cage emits the deprecated name | **confirmed** — [otelout.py:59](../../cage/otelout.py#L59) |
| cage pins 1.42.0 | **confirmed** — [constants.py:211](../../cage/constants.py#L211) |

## 2 · The finding that makes this a fork

**The GenAI conventions moved to their own repository**
(`open-telemetry/semantic-conventions-genai`), and every `gen_ai.*` attribute, metric,
event and span previously defined in the main `semantic-conventions` repo is deprecated
there and now lives in the new one.

That means the string `"1.42.0"` is ambiguous in cage's own `cage.meta` block:

- If it names a **main-repo** release, then as of the split it says almost nothing
  about the `gen_ai.*` names cage emits — the main repo no longer defines them.
- If it is meant to name a **GenAI-repo** release, the number is probably not
  `1.42.0` at all, and the two repos version independently from the split onward.

CLAUDE.md already treats this pin with `prices_version` discipline — *"a spec bump is a
deliberate, changelog'd change, never a silent drift"*. The same discipline says a pin
whose referent is unclear must be resolved deliberately, not patched around.

## 3 · Why the attribute was NOT renamed in this pass

Renaming `gen_ai.system` → `gen_ai.provider.name` in isolation would make the emitted
document internally consistent with *one* reading of the pin while leaving the pin
itself ambiguous — and it would silently change a field every existing consumer of
cage's OTel export reads. Ecosystem guidance during the transition is aimed at
**consumers** (*recognise both, coalesce with precedence, never sum the pair*); it does
not license a producer to invent a hybrid.

Emitting **both** names was considered and rejected for exactly that reason: a consumer
that sums rather than coalesces would double-count, and cage would be shipping a shape
no version of the spec defines.

## 4 · The open decision (for a compare doc or a one-line call)

1. **Rename to `gen_ai.provider.name`** and keep the pin at 1.42.0 — correct for a
   post-1.37 target, breaks existing consumers of cage's export, needs a changelog
   entry and a stated migration.
2. **Emit both** during a transition window — maximally compatible, but ships a shape
   no spec defines and risks double-counting.
3. **Re-point the pin at the GenAI repo's own versioning** and derive the attribute set
   from *that* — the only option that fixes the ambiguity in §2 rather than working
   around it, and the largest.

Recommendation: **(3), with (1) falling out of it.** The attribute name is a symptom;
the pin's referent is the actual defect, and fixing the symptom alone would leave
`cage.meta` making a claim nobody can check.

## 4a · The decision (2026-08-11) — and the fact that reshaped option 3

**Taken: (3), with (1) falling out of it.** Implemented the same day; `cage/otelout.py`
and the constants block are no longer untouched.

**The new fact, verified 2026-08-11:** `open-telemetry/semantic-conventions-genai`
**has no tagged release at all** — its releases page is empty, its changelog holds only
an `## Unreleased` section, and every span, metric, event and attribute in it is still
`Status: Development`. The split itself is dated: main-repo **v1.42.0, 2026-06-12**,
which deprecated `model/gen-ai/`, `model/openai/` and `model/mcp/` there and moved them.

That kills option 3 *as written* — there is no GenAI-repo version to re-point the pin at
— but it resolves the ambiguity in §2 completely, which was option 3's actual goal:

| what cage now stamps | value | why it is checkable |
|---|---|---|
| `semconv` | `1.42.0` | the **last main-repo release that defined `gen_ai.*`** — a dated, verifiable fact |
| `semconv_means` | that sentence, verbatim | the referent is stated, so the number cannot be read the wrong way |
| `semconv_source` | `open-telemetry/semantic-conventions-genai` | where the names live *now* |
| `semconv_status` | `pre-stable (Development; source repo untagged)` | maturity **stated**, not given a fabricated version |

**No number was invented for the GenAI repo**, which is the whole discipline: a pin that
cites an unverifiable version is worse than one that says why it cannot.

**(1) fell out:** `gen_ai.system` → `gen_ai.provider.name`. It was deprecated five
releases *before* the pinned one, so once the pin's referent is stated the old spelling
is simply wrong. **Emitting both was rejected** on §3's grounds — a consumer that sums
rather than coalesces would double-count. This is a **breaking change** for anything
reading cage's `--otel` output; it is in the changelog with the migration.

**The pin's trigger:** re-point `OTEL_SEMCONV_VERSION` at the GenAI repo's own scheme
the moment that repo cuts its **first tagged release**. Not on an argument, not on a
blog post — on a tag.

## 5 · What did not change *(as of 2026-08-03 — superseded by §4a)*

At the time of writing, `cage/otelout.py` and `constants.OTEL_SEMCONV_VERSION` were
untouched. The other four REV-HARDEN P2 items shipped in v0.45.0; this one was filed
here instead, in the same shape as REV-CREDITS defect 2 (a basis fork routed to a
compare doc rather than decided inside a fix commit). **Both were decided and built on
2026-08-11** — §4a above for this one.

## Sources

- [Gen AI attribute registry — OpenTelemetry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)
- [semantic-conventions releases](https://github.com/open-telemetry/semantic-conventions/releases)
- [spring-ai #6668 — `gen_ai.system` deprecated, renamed to `gen_ai.provider.name`](https://github.com/spring-projects/spring-ai/issues/6668)
- [The state of the OpenTelemetry GenAI semantic conventions (July 2026)](https://john-hodge.com/blog/opentelemetry-genai-semantic-conventions/)

### Added 2026-08-11 (the §4a verification)

- [open-telemetry/semantic-conventions-genai — releases](https://github.com/open-telemetry/semantic-conventions-genai/releases) — empty; no tag exists to pin
- [OpenTelemetry's GenAI semantic conventions are NOT stable yet — what actually shipped in 2026](https://dev.to/azena-ai/opentelemetrys-genai-semantic-conventions-are-not-stable-yet-heres-what-actually-shipped-in-2026-3mke) — dates the split at main-repo v1.42.0, 2026-06-12
- [Inside the LLM Call: GenAI Observability with OpenTelemetry](https://opentelemetry.io/blog/2026/genai-observability/)
