# Claude Code prompt: the ADR correctness sweep

**Model:** **Sonnet.** Every change is decided and carries an exact change map — the diagnosis is
already done, and nothing here touches the substrate contract, a fail-open path, or a deletion
with entanglements. The one item that would need Opus is deliberately out of scope.
**Progress:** 0% — not started. Five phases (P0–P4).

---

You are making `cage`'s ten ADRs **true**. A full audit against `595cb05` found **20+ factual
errors across seven records** — wrong counts, superseded measurements, dead boxes in diagrams,
and a claimed guarantee that does not hold. The full spec is **`work/adr-correctness-sweep.handoff.md`**.
Read it first and treat its **Phase index**, **Decisions locked**, **Change map** and
**Non-negotiables** as binding.

## ⛔ Before anything else

1. **A concurrent session was mid-flight when this was written** (2026-08-14T19:30Z). Its work
   landed as **`22072bf`**, and **every finding here was re-confirmed present at that commit** —
   it fixed one row (ADR-CLI's dead `cage task quality`) and grew ADR-CLI by 444 lines without
   touching a single count. A further ~77 files were staged-but-uncommitted at the time.
   Run `git log --oneline -5` and `git status --porcelain`. **Do not start on a dirty tree you
   did not make** — if that staged work is still sitting there, stop and say so.
2. **Re-verify every line number in the change map.** The quoted strings are the anchors; the line
   numbers are hints from a moving tree. A row whose quoted string is already gone was fixed by
   that session — **drop the row, note it in the commit, do not re-introduce it.**
3. **Every mermaid edit lands with its ASCII twin in the same diff.** The house rule is exact
   agreement. Fixing one alone creates a new defect of exactly the class you are here to close.
4. **Do not fix a finding by deleting the claim.** A wrong count becomes the right count; a wrong
   table cell becomes the right cell with its reason. An erased sentence loses the decision.

## P0 — write the gate, and watch it fail

`tests/test_adr_counts.py`. **It must be RED on the current tree.** That failure is the proof P2
and P4 landed; a gate written green asserts nothing.

Three assertions, each re-derived from code, none reading prose:

1. the ADR set size, in `docs/adr/README.md`'s frontmatter and `CLAUDE.md`'s "The set is …"
   sentence, equals `len(sorted(Path("docs/adr").glob("0*.md")))`;
2. every `## \`cage <group>\` — N commands` heading in ADR-CLI, plus its group count and total,
   equals what `cli.build_parser()` says;
3. the MCP read-tool count in ADR-CLI and `CLAUDE.md` equals
   `len(mcpserver.TOOLS) - len(mcpserver.WRITE_TOOLS)`.

In the module docstring, **state what it does not cover** — `test_cli_reference.py` covers
existence, `test_adr_output_blocks.py` covers fenced output, this covers arithmetic about the
parser, and nothing covers prose. A gate that implies coverage it lacks is the failure it exists
to stop.

## P1 — the three agent diagrams

- **ADR-CLAUDE:** delete the `ledger.join_table` box (line 53) and its ASCII twin branch (68).
  Arpit's call — it is ADR-CONSUMERS' subject matter (`metering.py:81`) and it hangs off a writer
  P5 retired (`importcmd.py:593`). Mark the surviving `parse_calls → calls-*` branch as **history,
  not a live writer**. Leave §2's lines 168/288/358/360 — they are correct in context.
- **ADR-COPILOT:** delete the `calls row + credits verbatim` box (58, 74, 75) and move
  **`+ credits verbatim`** onto `ledger/copilot/`. Both arrows are dead (`importcmd.py:985`);
  credits are still verbatim, on the metric row (`transcript.py:1087, 1151`). Do not touch the
  `chat + cli-delta ONLY` spine arrow.
- **ADR-KIRO:** re-parent credits from a **sibling** of `ledger/kiro/` to a **projection** of it
  (56, 71). `ledger.credits()` projects `cli-conv` rows (`ledger.py:288`); `chats.py:259` reads
  that. Leave the `token spine: NONE` node and whatever the concurrent session did to the
  `ide-log` box.

## P2 — ADR-CLI

Seven errors, six of them the document contradicting itself. The handoff's table has each line,
each claim and each truth. The headline: **"9 read tools" is 1**; `data` is named as a live group
and was deleted; `task`/`authorship` command counts are one high each; "five groups"/"twenty-seven"
contradict its own diagrams' six/28; the money cull is dated v0.51 and was v0.50; `--hooks` still
advertises budget blocking that no longer exists.

**Line 467 needs care.** It claims every example "is checked to parse". It is not —
`test_cli_reference.py:177-195` never calls `parse_args`. *(The two examples that proved it,
`cage study start` / `cage study join`, went with the whole fleet study in v0.51 — STUDY-CUT.
**The gap is unchanged**: the gate still checks existence only, and the next missing positional
will ship just as silently.)* **Narrow the sentence to what the gate checks** (existence). Do not
promise the parse check unless you build it — and building it is a separate phase, not this one.

Sweep the same two bugs out of `cage/verbmap.py` (`:127` v0.51→v0.50; `:132-134` points at the
dead `cage task quality`).

## P3 — the other five records

Work the handoff's tables. In order of what they buy:

- **ADR-COVERAGE** — the copilot-CLI **Chat title** cell says `N/A honest empty` and the parser
  exists (`session_name_copilot_cli`, wired `importcmd.py:945-958`). This is **strike 3**; record
  it. Also: `exactly 2×` → **1.979×**, `44.3%` → **85.2%**, the ⚠️/❌ legend drift, "four ✅
  cells", and the three IDE interceptor cells marked ✅ while the same section calls them
  UNPROBED — mark those ‡, do not close a gap with an argument.
- **ADR-AUTHORSHIP** — "five integers **and nothing else**" is six, and "nothing else" is false:
  a row also persists `files`, repo-relative **paths** (`schema.py:798`). **Add `files` to the
  record that owns it** — it is the widest PII surface here and is currently unmentioned. Also
  `44.3%` → **85.2%**, both diagram twins still say `provenance.jsonl` after P3c sharded it, and
  the `declared` row at 90 needs a not-built mark.
- **ADR-CONSUMERS** — the *Where they sit* diagram pair (48, 67) still shows the pre-P1 single
  write; P1 dual-writes (`metering.py:64-65`). Its own §1 prose already says so.
- **ADR-GRAPHIFY** — D4 "three findstr literals" is four; B7/D6 "either/both" `%*` lines is four.
  Counts only; the behaviour claims hold.
- **ADR-LAWS** — "MCP is the only surface cage wires" overstates (`--hooks`, `--skills`). Narrow
  to the substance, which holds: no hook writes usage.
- **ADR-INTEGRITY** — `22,751` appears in no source (use **22,802**, which the record itself uses
  23 lines later); "22k+" understates ~4×; `BY_DESIGN` is five entries not two; a lock miss taints
  the **file entry**, stickily and for every tracked file, not one segment. **Leave lines 17-19
  and 88 alone** — the code is what is wrong there, and it is out of scope.

## P4 — the index and the stale comments

`docs/adr/README.md` says **nine** records and lists ten. `CLAUDE.md` says **SEVEN**, and its
"MCP surface = 5 read tools" is wrong the other way. Then four stale code docstrings —
`integrity.py:15,133` (claims `cage doctor` checkpoints; it does not — the ADR is right and the
comment is the stale copy), `savings.py:52`, `graphifytx.py:617`, `mcpserver.py:47-48` — plus
`graphifymeter.py:74` citing an ADR by number. Bump every touched `work/DOC-REGISTRY.md` row.

## Out of scope — file, do not fix

- **`doctorcmd.py:1140` passes the unresolved root to `_integrity()`** while every other ledger
  check uses `paths.resolve_root` (`:1103`). A project-less user's global `altered-history` is
  invisible to `cage doctor`. Verified by execution. Behaviour fix, needs the suite and an
  ADR-INTEGRITY update — **add it to `work/OPEN-WORK.md` under ADR-INTEGRITY**.
- **The ADR-CLI parse-check gap** — add it to OPEN-WORK too, named as the reason P2 narrowed the
  sentence rather than strengthening the gate.
- AUTHORSHIP-CODE-CATCHUP's three code items. P3 marks item (c) not-built; it builds nothing.

## When you are done

1. `just test` green — check `test_adr_counts.py`, `test_cli_reference.py`, `test_adr_ownership.py`,
   `test_adr_output_blocks.py`, `test_output_spec.py` by name.
2. Every touched record's `status:` line and DOC-REGISTRY row current.
3. `work/IMPLEMENTATION.md` outcome entry, `work/WORKLOG.md` session entry ending in a `Cost:`
   line (`Cost: unmeasured — <why>` is the honest entry; `cage report` is deleted).
4. Two items carried into `work/OPEN-WORK.md`, per *Out of scope*.
5. Archive this pair to `work/archive/v0.51-adr-correctness-sweep.{handoff,prompt}.md` with the
   one-line header, update the `docs/README.md` and `work/archive/README.md` indexes, and link
   them from the CHANGELOG entry's *Built from:*.

**Two questions go to Arpit, not to you.** COVERAGE-STRIKE-2's threshold is passed and its named
remedy would not have caught any of the three strikes — whether to close it as a prose failure is
his call. And whether the counts gate wants a fourth assertion over ADR-COVERAGE's own two tables
is that record's decision, not this sweep's. **Report both; decide neither.**
