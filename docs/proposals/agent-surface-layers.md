---
doc: proposal — the agent-surface layer ladder
status: proposed
raised: 2026-08-02 (Arpit — clean slate; supersedes cage-skills.md entirely)
supersedes: cage-skills.md (written against the pre-hookless world; premise false)
---

# Proposal — four layers, each optional, each strictly additive

**Designed from nothing.** Nothing built before is assumed, and anything surviving from
an older version is **removed, not extended**. The floor is hookless; every layer above
it is opt-in and adds capability without being required by anything below.

**Why the old proposal is void:** `cage-skills.md` opened with *"cage already ships one
skill (`/cage`)"*. It does not — the hookless rebuild deleted the skill/steering
machinery, and no code writes a skill file anywhere. Its whole premise was pre-rebuild.

## The ladder

| | layer | optional | what it is | if absent |
|---|---|---|---|---|
| **L0** | **Hookless** | **no — the floor** | pull capture (transcript import, capture-on-read) · PATH interceptor · every CLI view | nothing works; this *is* cage |
| **L1** | **Hooks + steering** | yes | agent lifecycle events; passive text the agent reads | L0 works, just staler and blinder |
| **L2** | **MCP** | yes | the agent *pulls* cage mid-session | the agent can't see its own cost |
| **L3** | **Skills** | yes | procedural knowledge — when and why, not just what | tools without judgement |

**Binding rule: L0 must work perfectly, alone, forever.** Every layer above degrades to
"absent" without breaking capture, determinism, or any number. No layer may become a
dependency of a lower one.

## What each layer uniquely unlocks

| capability | L0 | +L1 | +L2 | +L3 |
|---|---|---|---|---|
| Token capture | ✅ at import/read | ✅ **real-time** | — | — |
| Savings receipts | ✅ shim + transcript | ✅ **agent identity at capture** | — | — |
| Task open/close | ⚠️ manual | ✅ **auto on session boundary** | ✅ agent closes its own | ✅ closes *with a label* |
| Provenance | ⚠️ transcript only | ✅ post-commit | — | — |
| Budget | ⚠️ advisory | ✅ **blocks before a paid call** | ✅ agent self-checks | ✅ re-plans under budget |
| Tool awareness | ❌ | ✅ steering text | — | ✅ **knows when it's worth it** |
| Agent reads its numbers | ❌ | ❌ | ✅ read tools | ✅ interprets them |
| Method-tag honesty relayed | ❌ | ❌ | ⚠️ raw JSON | ✅ **refusals relayed, never smoothed** |
| Proactive behaviour | ❌ | ⚠️ passive nudge | ❌ | ✅ "check the graph first" |
| Multi-step workflows | ❌ | ❌ | ❌ | ✅ triage · release · lab-run |

## Three findings that shaped this

1. **L1 mostly fixes problems that already exist.** Automatic task-close feeds *every*
   starved surface — `compare`, `estimate`, `calibration` and NET-1 are all blocked on
   nobody running `cage task outcome`. And a hook **knows which agent fired it**, which
   is exactly the attribution [ADOPT-COV](../OPEN-WORK.md) cannot get from a shim
   subprocess. These are not new features; they are shipped features that don't work.
2. **L2 exists and is under-used.** Six read tools ship — but **`verdict` and `compare`,
   the two that answer "is this tool worth it", are not among them.** The product
   question is invisible to agents.
3. **Only L3 can carry the honesty discipline.** MCP hands an agent a JSON number;
   nothing makes it say *"that's `modeled`, not measured"*. A skill can be instructed to
   relay method tags verbatim and never smooth a refusal. Without L3 the discipline stops
   at the CLI boundary.

## Old residue to remove (not extend)

| where | what | why |
|---|---|---|
| `README.md` ×3 | "wires skill + hooks" · `--no-skill` · "the `cage` skill on **all four agents**" | **live on PyPI, wrong twice** — no skill exists, and it has been three agents since v0.33 |

`claudewire._strip_stale_hooks` **stays** — it removes *old* hook entries from user
configs. That is migration, not residue.

## Sequencing

**L0 → L2 → L1 → L3.** Finish L0 (nearly there), then close the L2 gap (cheap, and it is
the product question). L1 before L3 because hooks unblock the evidence pipeline that
makes L3's advice worth taking. L3 last — a skill interpreting numbers you cannot yet
trust is premature.

## Deliberately not proposed

Making any layer mandatory · reviving the deleted skill machinery as-is (rebuild from
this design, or not at all) · a fourth agent · anything that puts a network or a
dependency in L0.
