# 2026-08-15 — External precedent for a tool-combination token/cost matrix

**Take-away:** the "cost cell per tool-combination" shape has real precedent (Aider's
leaderboard; tag/metadata-based segmentation in Langfuse, Helicone, LangSmith), and the
gross-vs-net / measured-vs-modeled split cage already enforces internally has a direct
analog in how prompt-caching and prompt-compression tools report their own savings.
OpenTelemetry's GenAI semantic conventions are the closest existing standard for
per-span token attribution — useful as a reference point, not an integration target, for
a purely-tokens matrix.

Evidence for the `MATRIX-REVIVAL` fork,
[work/compare/tool-combination-matrix.compare.md](../compare/tool-combination-matrix.compare.md).
**Findings, not spec.**

Web research only — no local probe, no code run. Sourced 2026-08-15.

---

## 1 · Cost/token reporting broken down by tool-combination

- [Aider LLM Leaderboards](https://aider.chat/docs/leaderboards/) — a public table
  reporting cost alongside pass/completion rate per model/config; the closest mainstream
  precedent for "a cost cell per configuration," though its axis is model choice, not
  tool combination.
- [Langfuse — Tags](https://langfuse.com/docs/observability/features/tags) /
  [Metadata](https://langfuse.com/docs/observability/features/metadata) — traces tagged
  by which tools fired, then segmented by cost/tokens in the UI and Metrics API. Closest
  analog to cage's *observed* stack signature: the tag is attached per-trace, not
  configured ahead of time.
- [Helicone — Custom Properties](https://docs.helicone.ai/features/advanced-usage/custom-properties) —
  arbitrary per-request properties used to group usage/cost dashboards by active
  feature/tool.
- [LangSmith — cost tracking](https://docs.langchain.com/langsmith/cost-tracking) +
  [tags/metadata](https://docs.langchain.com/langsmith/add-metadata-tags) — same
  tag-then-segment pattern, paired with per-trace token/cost accounting.

## 2 · Gross-vs-net, measured-vs-modeled savings from compression/caching tools

- [LLMLingua (arXiv:2310.05736)](https://arxiv.org/abs/2310.05736) /
  [microsoft/LLMLingua](https://github.com/microsoft/LLMLingua) — reports compression
  ratio and token reduction as a raw, measured figure against original prompt length,
  kept separate from any end-to-end cost accounting — the same gross framing
  `cage/savings.py`'s `GROSS_NOTE` already commits to.
- [Anthropic — prompt caching docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) —
  splits cache-write cost from cache-read discount explicitly; a real-world example of a
  savings figure that only nets out correctly once both legs are counted, i.e. a
  documented gross/net split in a shipped product.
- [Anthropic — token-saving updates](https://www.anthropic.com/news/token-saving-updates) —
  vendor-quantified measured token reduction from context-management features.

## 3 · OpenTelemetry GenAI semantic conventions (token attribution standard)

- [Gen AI attribute registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/) —
  canonical `gen_ai.usage.input_tokens` / `output_tokens` span attributes.
- [gen-ai-spans.md](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md) —
  how token counts attach per-call-span, the unit a tool-combination rollup would
  aggregate over if cage ever exported spans (it doesn't — `otelout.py` was deleted in
  SURFACE-CUT; named here as reference only, not a live integration).
- [Inside the LLM Call: GenAI Observability with OpenTelemetry](https://opentelemetry.io/blog/2026/genai-observability/) —
  walkthrough of token/cost attribution composing across nested agent → tool → LLM spans,
  directly analogous to a stack-signature rollup.

---

## Why it was asked

`MATRIX-REVIVAL`'s proposed verdict claims the "cost per tool-combination" shape and the
measured/modeled discipline cage already enforces are not idiosyncratic — both have
precedent elsewhere. This doc grounds that claim rather than asserting it.
