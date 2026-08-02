"""L3 — skills: one source, three deliveries, and **no skill computes a number**.

The governing rule of this layer is a content rule, so most of this file tests *prose*.
That is deliberate. MCP hands an agent a JSON number and nothing makes it say *"that is
`modeled`, not measured"*; a skill is the only layer that can carry the honesty
discipline past the CLI boundary — and the only way it can lose it is by being written
badly. So the rule is enforced mechanically (`steering.lint`) rather than trusted to
review, and the deliveries are asserted byte-equal rather than eyeballed.

Three claims:

1. **A skill never computes a number** — it names cage commands and relays what they
   say, including the refusals, verbatim.
2. **One source, three deliveries** — the body bytes are identical for claude, copilot
   and kiro; only the ~10-line host wrapper differs. A skill on one agent and not the
   others is not done.
3. **Opt-in, two-way, committed** — `cage setup --skills` installs, a plain `cage setup`
   removes, both are byte-identical on a re-run, and nothing lands in the ledger.
"""
from __future__ import annotations

import pytest

from cage import agents, cli, paths, steering

SKILLS = steering.by_layer("L3")

# The build order the design fixed. Asserted as a set + a first element rather than a
# full ordering: the order matters for *building*, and task-closer first is the load-
# bearing part (every starved surface is starved for want of closed tasks).
EXPECTED = {"cage-task-closer", "cage-analyst", "cage-doctor-triage",
            "cage-honesty-reviewer", "cage-release", "cage-lab-runner",
            "cage-windows-shim"}


def test_every_designed_skill_exists():
    assert {d.id for d in SKILLS} == EXPECTED
    assert SKILLS[0].id == "cage-task-closer"      # needs P1's write tool; feeds the rest


# ── 1 · no skill computes a number ────────────────────────────────────────────

def test_no_document_promises_to_compute(proj):
    """`steering.lint` is the mechanical form of the governing rule. A new failure mode
    is added to `BANNED`, never argued about in a review."""
    assert [p for d in steering.DOCS for p in steering.lint(d)] == []


@pytest.mark.parametrize("doc", SKILLS, ids=lambda d: d.id)
def test_every_skill_names_a_real_cage_command(doc):
    """A skill quotes cage, so it must name commands that actually parse. A skill
    teaching a dead verb is the F1 class in prose — it fails, the agent adapts, and
    nobody learns why."""
    import re
    parser_verbs = set()
    top = next((a for a in cli.build_parser()._actions
                if a.choices and a.dest == "cmd"), None)
    for verb, sub in (top.choices.items() if top else ()):
        parser_verbs.add(verb)
        nested = next((a for a in sub._actions if a.choices), None)
        for inner in (nested.choices if nested else ()):
            parser_verbs.add(f"{verb} {inner}")
    named = set(re.findall(r"`?cage ([a-z][a-z0-9-]*(?: [a-z][a-z0-9-]*)?)", doc.body))
    hits = {n for n in named if n in parser_verbs or n.split()[0] in parser_verbs}
    assert hits, f"{doc.id} names no live cage verb"
    # And nothing it names may be dead: a two-word phrase whose FIRST word is a group
    # verb must resolve as a pair.
    groups = {v.split()[0] for v in parser_verbs if " " in v}
    for n in named:
        head = n.split()[0]
        if head in groups and " " in n:
            assert n in parser_verbs, f"{doc.id} names a dead command: `cage {n}`"


def test_the_analyst_skill_relays_every_refusal_unsmoothed():
    """The refusals are what an agent is most likely to paper over, so the skill that
    reads numbers must name each one and say what it does NOT mean."""
    body = next(d for d in SKILLS if d.id == "cage-analyst").body
    for phrase in ("INSUFFICIENT DATA", "SAVING (GROSS)", "measured", "modeled",
                   "estimated", "min-n" if "min-n" in body else "closed tasks"):
        assert phrase.lower() in body.lower(), phrase
    # The two rules that are easiest to get subtly wrong.
    assert "never substitute zero" in body.lower()
    assert "double-count" in body.lower()      # savings are marginal, never summed


def test_the_task_closer_never_invents_an_outcome():
    body = next(d for d in SKILLS if d.id == "cage-task-closer").body.lower()
    assert "do not guess the outcome" in body
    assert "inflates the success rate" in body
    assert "only" in body and "write tool" in body


def test_the_release_skill_refuses_local_publishing():
    body = next(d for d in SKILLS if d.id == "cage-release").body
    assert "gh release create" in body
    for banned in ("uv publish", "twine"):
        assert banned in body           # named in order to be refused
    assert "sole publisher" in body.lower() or "CI is the sole publisher" in body


def test_the_honesty_reviewer_covers_the_method_law():
    body = next(d for d in SKILLS if d.id == "cage-honesty-reviewer").body.lower()
    for topic in ("measured", "fabricated zero", "caveat", "refusal",
                  "determinism", "counts"):
        assert topic in body, topic


def test_the_windows_shim_skill_carries_the_twin_rule():
    body = next(d for d in SKILLS if d.id == "cage-windows-shim").body
    assert "PATHEXT" in body and "exec" in body
    assert "127" in body                                   # B4
    assert "exit /b" in body                               # D-divergence, the real trap
    assert "templat" in body.lower()                       # ADR 0007: do not


# ── 2 · one source, three deliveries ──────────────────────────────────────────

@pytest.mark.parametrize("doc", SKILLS, ids=lambda d: d.id)
def test_body_bytes_are_identical_across_all_three_agents(doc):
    """The whole point of the renderer. Three hand-written copies drift; one source
    cannot."""
    rendered = {a: steering.render(a, doc) for a in agents.SURFACES}
    assert set(rendered) == set(agents.SURFACES)
    for text in rendered.values():
        assert doc.body.strip() in text
    # Only the wrapper differs — strip each host's frontmatter and the rest is one text.
    tails = {a: t.split("\n", 1)[1].split("---", 1)[-1] for a, t in rendered.items()}
    assert len({t.strip()[-400:] for t in tails.values()}) == 1


def test_each_agent_gets_its_own_idiomatic_home(proj):
    doc = SKILLS[0]
    where = steering.paths_for(proj, doc)
    assert where["claude"].as_posix().endswith(f".claude/skills/{doc.id}/SKILL.md")
    assert where["copilot"].as_posix().endswith(f".github/prompts/{doc.id}.prompt.md")
    assert where["kiro"].as_posix().endswith(f".kiro/steering/{doc.id}.md")


def test_every_host_wrapper_carries_the_trigger(proj):
    """Each host learns *when* to reach for the document in its own frontmatter field —
    a skill nobody knows to open is the same as no skill."""
    for doc in SKILLS:
        for agent in agents.SURFACES:
            text = steering.render(agent, doc)
            assert text.startswith("---\n")
            assert doc.trigger.split(".")[0] in text
            assert doc.title in text


# ── 3 · opt-in, two-way, committed, and it moves no number ────────────────────

def test_skills_are_off_by_default(proj):
    agents.install(proj)
    assert all(not p.exists() for d in SKILLS
               for p in steering.paths_for(proj, d).values())


def test_skills_install_for_all_three_and_uninstall_again(proj):
    agents.install(proj, skills=True)
    for doc in SKILLS:
        for agent, path in steering.paths_for(proj, doc).items():
            assert path.exists(), f"{doc.id} missing for {agent}"
    agents.install(proj)                       # plain re-run = the off-switch
    assert all(not p.exists() for d in SKILLS
               for p in steering.paths_for(proj, d).values())


def test_installing_skills_twice_is_byte_identical(proj):
    agents.install(proj, skills=True)
    first = {(d.id, a): p.read_bytes() for d in SKILLS
             for a, p in steering.paths_for(proj, d).items()}
    agents.install(proj, skills=True)
    assert {(d.id, a): p.read_bytes() for d in SKILLS
            for a, p in steering.paths_for(proj, d).items()} == first


def test_skills_are_independent_of_hooks(proj):
    """Separate layers, separate flags: a team may want the documents without the
    lifecycle hooks, or the reverse."""
    from cage import claudewire
    agents.install(proj, skills=True)
    assert claudewire.hook_status(proj) == 0
    assert steering.paths_for(proj, SKILLS[0])["claude"].exists()
    agents.install(proj, hooks=True)
    assert claudewire.hook_status(proj) > 0
    assert not steering.paths_for(proj, SKILLS[0])["claude"].exists()


def test_no_skill_file_is_a_bundled_asset():
    """L3 is rendered from a Python literal at setup time, NOT shipped as package data.
    That is what removes the drift-check / `--bless` / committed-copy machinery its
    predecessor needed — there is no second copy that can disagree with the source."""
    data = paths.bundled_data()
    for name in ("skills", "prompts", "steering"):
        assert not (data / name).is_dir()


def test_installing_skills_writes_nothing_to_the_ledger(proj):
    fp = paths.Footprint(proj)
    fp.ledger.mkdir(parents=True, exist_ok=True)
    before = sorted(p.name for p in fp.ledger.iterdir())
    agents.install(proj, skills=True)
    assert sorted(p.name for p in fp.ledger.iterdir()) == before
