"""L1 — hooks + steering: opt-in, three agents, and **it changes no number**.

This is the phase the floor test was built to judge, so the assertions here are written
against the failure modes rather than the features:

- **Opt-in** — `cage setup` without `--hooks` writes no hook file, and re-running it
  *removes* one, so the layer is a two-way switch rather than a one-way door.
- **No number moves.** Wiring the layer over a fixed ledger leaves every derived view's
  stdout byte-identical (`test_floor.py` owns the general form; here it is asserted for
  hooks specifically, in both directions).
- **No double capture.** The hook runs the same sweep every other trigger runs, so a
  turn captured by a hook and then by a pull import is one row, not two.
- **Fail-open, absolutely.** Every failure mode a hook can have exits 0 — a broken cage
  must never break someone's session. The one non-zero is a deliberate budget block.
- **Identity is stamped, never inferred**, and every gap is *named*: an agent that
  cannot do something appears in `agents.HOOK_GAPS`, and a fact derived from hooks
  carries the CLI-only limit wherever it is shown.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cage import (adoption, agents, attest, cfgio, cli, clicmds, hookcmd, ledger,
                  paths, schema, steering, tasks, usagelog, wiringscan)

_MODEL = dict(route="chat", provider="anthropic", model="claude-opus-4-8",
              agent="claude-code")


@pytest.fixture
def proj_at(proj, monkeypatch):
    """A scaffolded project that is also the cwd — the hook entrypoint resolves its root
    exactly as the CLI does (`paths.resolve_root`), so without a `.cage/` here a hook
    would correctly land in the global ledger and this file would be testing that."""
    paths.Footprint(proj).ledger.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(proj)
    return proj


def _args(event, **kw):
    base = {"event": event, "agent": "claude", "session": "", "command": ""}
    base.update(kw)
    return SimpleNamespace(**base)


def _call(root, task, session, ts="2026-06-10T10:00:00Z"):
    ledger.append_row(root, "calls", schema.make_call(
        tokens_in=1_000, tokens_out=100, task=task, session=session, ts=ts, **_MODEL))


def _hook_files(root):
    return {".claude/settings.json": (root / ".claude" / "settings.json").exists(),
            ".github/hooks/cage.json": (root / ".github" / "hooks" / "cage.json").exists(),
            ".kiro/hooks/cage.kiro.hook":
                (root / ".kiro" / "hooks" / "cage.kiro.hook").exists()}


# ── opt-in, and a two-way switch ──────────────────────────────────────────────

def test_setup_is_hookless_by_default(proj_at):
    agents.install(proj_at)
    assert not any(_hook_files(proj_at).values()), "the default install wired a hook"
    assert all(w.hook_status(proj_at) == 0 for w in
               (__import__("cage.claudewire", fromlist=["x"]),
                __import__("cage.copilotwire", fromlist=["x"]),
                __import__("cage.kirowire", fromlist=["x"])))


def test_unwiring_leaves_no_residue_behind(proj_at):
    """`hook_status == 0` is necessary and not sufficient: the off-switch used to route
    through a stripper that left `"hooks": {}` and the file itself behind, so unwiring
    showed up as a committed diff forever. Assert **absence**, not just a zero count."""
    import json
    from cage import claudewire
    settings = proj_at / ".claude" / "settings.json"
    agents.install(proj_at, hooks=True)
    assert claudewire.hook_status(proj_at) > 0 and settings.exists()

    agents.install(proj_at)                       # plain setup = the off-switch
    assert claudewire.hook_status(proj_at) == 0
    assert not settings.exists(), (
        "cage reduced this file to nothing but left it on disk: "
        + settings.read_text(encoding="utf-8"))


def test_unwiring_never_touches_someone_elses_hook(proj_at):
    """The other half: the file is only removed when *nothing of anyone's* is left."""
    import json
    from cage import claudewire
    settings = proj_at / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    foreign = {"hooks": {"PreToolUse": [{"matcher": "Bash",
                                         "hooks": [{"type": "command",
                                                    "command": "echo not-cage"}]}]}}
    settings.write_text(json.dumps(foreign, indent=2), encoding="utf-8")

    agents.install(proj_at, hooks=True)
    agents.install(proj_at)
    assert claudewire.hook_status(proj_at) == 0
    data = json.loads(settings.read_text(encoding="utf-8"))
    cmds = [h["command"] for entries in data["hooks"].values()
            for e in entries for h in e["hooks"]]
    assert cmds == ["echo not-cage"]
    assert data["hooks"] != {}, "an emptied table must be dropped, not left as {}"


def test_hooks_wire_on_all_three_agents(proj_at):
    from cage import claudewire, copilotwire, kirowire
    agents.install(proj_at, hooks=True)
    assert all(_hook_files(proj_at).values()), "an agent was left without its hook file"
    # Every agent gets the layer; the SIZE of what it gets differs and that difference
    # is declared in one table, not discovered per agent.
    assert claudewire.hook_status(proj_at) == len(agents.HOOK_EVENTS["claude"])
    assert copilotwire.hook_status(proj_at) == len(agents.HOOK_EVENTS["copilot"])
    assert kirowire.hook_status(proj_at) == len(agents.HOOK_EVENTS["kiro"])


def test_hooks_are_a_two_way_switch(proj_at):
    from cage import claudewire, copilotwire, kirowire
    agents.install(proj_at, hooks=True)
    assert any(_hook_files(proj_at).values())
    agents.install(proj_at)                       # plain re-run = the off-switch
    # Claude's settings.json is a SHARED file, so the assertion is that cage's entries
    # are gone, not that the file is — the two are different promises and only the
    # first one is cage's to make.
    assert all(w.hook_status(proj_at) == 0
               for w in (claudewire, copilotwire, kirowire))
    assert not (proj_at / ".github" / "hooks" / "cage.json").exists()
    assert not (proj_at / ".kiro" / "hooks" / "cage.kiro.hook").exists()
    assert steering.paths_for(proj_at, steering.DOCS[0])["kiro"].exists() is False


def test_wiring_hooks_twice_is_byte_identical(proj_at):
    """Two teammates running `cage setup --hooks` must not churn a committed diff."""
    agents.install(proj_at, hooks=True)
    first = {p: (proj_at / p).read_bytes() for p, on in _hook_files(proj_at).items() if on}
    agents.install(proj_at, hooks=True)
    assert {p: (proj_at / p).read_bytes() for p, on in _hook_files(proj_at).items() if on} \
        == first


def test_committed_hook_files_carry_no_machine_path(proj_at, monkeypatch):
    """A hook file is a committed file, so the no-absolute-path rule binds it exactly as
    it binds the MCP configs — the F1 class starts with a path that only exists on the
    machine that wrote it."""
    monkeypatch.setattr("cage.paths.cage_bin", lambda: "/machine/only/cage")
    agents.install(proj_at, hooks=True)
    for rel, on in _hook_files(proj_at).items():
        assert on
        text = (proj_at / rel).read_text(encoding="utf-8")
        assert "/machine/only/cage" not in text
        assert "cage-run" in text, f"{rel} does not reference the portable shim"


def test_every_wired_hook_verb_is_live_in_the_parser(proj_at):
    """The F1 lesson, applied before the fact: a hook naming a renamed verb exits 1 into
    a void, indistinguishable from cage not being installed. `wiringscan` checks every
    wired command against the LIVE parser, so this turns red the day `cage hook` moves."""
    agents.install(proj_at, hooks=True)
    scan = wiringscan.run(proj_at)
    assert scan.dead == [], [d.line for d in scan.dead]
    inv = wiringscan.inventory(proj_at)
    hook_rows = [i for i in inv.items if i.kind == "hooks" and i.status != "absent"]
    assert {i.agent for i in hook_rows} == set(agents.SURFACES)


# ── the acceptance criterion: the layer changes no number ─────────────────────

_VIEWS = (["report", "--by", "agent"], ["insights", "attrib"], ["insights", "roi"],
          ["insights", "adoption"], ["task", "quality"], ["insights", "budget"])


def _render(root, capsys):
    out = {}
    for argv in _VIEWS:
        assert cli.main([*argv, "--no-import"]) == 0
        text = capsys.readouterr().out
        for raw in {str(root.resolve()), str(root)}:
            text = text.replace(raw, "<project>")
        out[" ".join(argv)] = text
    return out


def test_wiring_hooks_moves_no_number_in_either_direction(proj_at, capsys):
    _call(proj_at, "t1", "s1")
    fp = paths.Footprint(proj_at)
    shards = lambda: {k: b"".join(p.read_bytes() for p in fp.shards(k))  # noqa: E731
                      for k in ("calls", "receipts", "tasks")}
    before_led, before_views = shards(), _render(proj_at, capsys)

    agents.install(proj_at, hooks=True)
    capsys.readouterr()
    assert shards() == before_led, "wiring hooks wrote to the ledger"
    assert _render(proj_at, capsys) == before_views, "wiring hooks moved a number"

    agents.install(proj_at)                       # …and back down to the floor
    capsys.readouterr()
    assert shards() == before_led
    assert _render(proj_at, capsys) == before_views, "unwiring hooks moved a number"


def test_attestations_are_absent_until_a_hook_fires(proj_at, capsys):
    """Installing the layer records nothing; only a hook *firing* does. The distinction
    is what makes 'the layer changes no number' true at all."""
    agents.install(proj_at, hooks=True)
    assert attest.read(proj_at) == []
    assert paths.Footprint(proj_at).attest_log.exists() is False


# ── no double capture ─────────────────────────────────────────────────────────

def test_hook_capture_and_pull_capture_do_not_double_record(proj_at, monkeypatch, capsys):
    """The hook runs the SAME sweep every other trigger runs — it is not a second write
    path — so a turn seen by both is one row. Proven on the bytes, not on a count."""
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")
    fp = paths.Footprint(proj_at)
    _call(proj_at, "t1", "s1")
    before = b"".join(p.read_bytes() for p in fp.shards("calls"))
    assert hookcmd.run(_args("session-start")) == 0
    assert clicmds.cmd_import(SimpleNamespace(agent="all", path=None, project=None,
                                              since=None)) == 0
    assert hookcmd.run(_args("session-end", session="s1")) == 0
    after = b"".join(p.read_bytes() for p in fp.shards("calls"))
    assert after == before, "a turn was recorded twice across the hook and pull paths"


# ── fail-open ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("event", hookcmd.EVENTS)
def test_every_event_exits_zero_when_everything_fails(event, proj_at, monkeypatch):
    """A hook runs inside someone's turn. Whatever breaks underneath it — the ledger,
    the policy, the sweep — the answer is exit 0."""
    def boom(*a, **k):
        raise RuntimeError("underlying failure")
    for target in ("cage.importcmd.ensure_captured", "cage.ledger.calls",
                   "cage.attest.record_session", "cage.attest.record_tool",
                   "cage.budget.check", "cage.tasks.read"):
        monkeypatch.setattr(target, boom, raising=False)
    assert hookcmd.run(_args(event, session="s1")) == 0


def test_missing_agent_never_guesses_and_never_fails(proj_at, capsys):
    """Identity is the whole point of this layer, so a hook with no `--agent` records
    nothing — but it still exits 0, and says why on stderr."""
    assert hookcmd.run(_args("session-start", agent="")) == 0
    assert "stamped, never inferred" in capsys.readouterr().err
    assert attest.read(proj_at) == []


def test_unknown_event_is_swallowed(proj_at):
    assert hookcmd.run(_args("not-an-event")) == 0


# ── fail-open at the BOUNDARY, not just inside `hookcmd.run` ──────────────────
#
# `hookcmd.run` never returns non-zero by accident — but argparse stands in front of
# it and exits **2** on any usage error, and 2 IS the block verdict (`hookcmd.BLOCK`,
# wired to PreToolUse/Bash). So a stale wired event name — exactly what a rename
# produces — used to block EVERY Bash call in the session, silently: a blocked tool
# call reads to the user as the agent refusing, not as cage failing.

def test_a_stale_hook_event_exits_zero_instead_of_blocking_every_tool_call(capsys):
    assert hookcmd.BLOCK == 2                      # the collision this guards
    assert cli.main(["hook", "not-an-event", "--agent", "claude"]) == 0


def test_an_incomplete_hook_invocation_also_fails_open(capsys):
    assert cli.main(["hook"]) == 0                 # missing event AND --agent
    assert cli.main(["hook", "session-start"]) == 0            # missing --agent


def test_the_stale_event_direction_is_derived_from_the_live_events(capsys):
    """A hand-maintained map of renamed events would go stale in the very release that
    renames one — `wiringscan`'s own lesson, applied to the fix-hint."""
    cli.main(["hook", "not-an-event", "--agent", "claude"])
    err = capsys.readouterr().err
    assert "not-an-event" in err and "cage setup --hooks" in err
    for event in hookcmd.EVENTS:
        assert event in err


def test_the_interception_is_scoped_to_hook_and_nothing_else():
    """Every other verb keeps argparse's exit 2 — this fix buys fail-open for the one
    verb where 2 has a second meaning, not a CLI that stops reporting usage errors."""
    with pytest.raises(SystemExit) as e:
        cli.main(["insights", "not-a-subcommand"])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        cli.main(["hook", "--help"])               # --help is exit 0, never swallowed
    assert e.value.code == 0


def test_a_real_block_still_reaches_the_host_through_the_same_boundary(proj_at, capsys):
    """The fix must swallow the *accidental* 2 without swallowing the deliberate one.
    Asserted through `cli.main` — the path the host actually invokes — because that is
    where both codes travel; `hookcmd.run` alone could not tell them apart."""
    _call(proj_at, "t1", "s1")
    _budgets(proj_at, 0.0001, "block")
    assert cli.main(["hook", "budget", "--agent", "claude",
                     "--session", "s1"]) == hookcmd.BLOCK


# ── agent identity: stamped, never inferred ───────────────────────────────────

def test_session_hook_attests_the_agent(proj_at):
    assert hookcmd.run(_args("session-start", agent="copilot", session="s9")) == 0
    rows = attest.read(proj_at)
    assert [r["agent"] for r in rows] == ["copilot"]
    assert rows[0]["kind"] == attest.SESSION and rows[0]["session"] == "s9"


def test_tool_hook_hashes_the_command_and_never_stores_it(proj_at):
    secret = 'graphify query "what does the payroll module do for employee 4471"'
    assert hookcmd.run(_args("tool", command=secret)) == 0
    raw = paths.Footprint(proj_at).attest_log.read_text(encoding="utf-8")
    assert "payroll" not in raw and "4471" not in raw and "query" not in raw
    row = json.loads(raw.splitlines()[0])
    assert row["tool"] == "graphify" and row["agent"] == "claude"
    assert row["args_hash"] == usagelog.args_hash(
        ["query", "what does the payroll module do for employee 4471"])


def test_only_argv_zero_names_the_tool(proj_at):
    """A command that merely *mentions* graphify is not an invocation of it — cage does
    not keep a log of everything an agent runs."""
    for command in ("echo graphify", "grep -r graphify src/", "ls"):
        assert hookcmd.run(_args("tool", command=command)) == 0
    assert attest.read(proj_at) == []


def test_a_hash_two_agents_claim_resolves_to_unknown(proj_at):
    """Identical queries from two agents are indistinguishable. Picking one would be
    exactly the guess this layer exists to replace."""
    for agent in ("claude", "copilot"):
        assert hookcmd.run(_args("tool", agent=agent, command="graphify query x")) == 0
    claims = attest.tool_agents(proj_at, "graphify")
    assert set(claims.values()) == {attest.UNKNOWN}


# ── adoption gains an agent breakdown — and its limit ─────────────────────────

def _usage(root, argv, outcome="receipt"):
    usagelog.record(root, op="query", args_hash=usagelog.args_hash(argv), exit=0, ms=5,
                    outcome=outcome, route="shim")


def test_adoption_is_byte_identical_without_attestations(proj_at):
    """L1 off ⇒ half A is agent-blind exactly as before. No empty table, no heading."""
    _usage(proj_at, ["query", "x"])
    text = adoption.render_adoption(adoption.summarize(proj_at))
    assert "by agent" not in text
    assert adoption.summarize(proj_at)["usage"]["by_agent"]["present"] is False


def test_adoption_names_the_agent_once_a_hook_attested_it(proj_at):
    _usage(proj_at, ["query", "x"])
    assert hookcmd.run(_args("tool", agent="claude", command="graphify query x")) == 0
    data = adoption.summarize(proj_at)
    assert data["usage"]["by_agent"] == {"present": True, "unattested": 0,
                                         "agents": [{"agent": "claude", "runs": 1}]}
    text = adoption.render_adoption(data)
    assert "by agent" in text and "claude" in text
    # The limit travels with the number, always.
    assert "VS Code" in text and "CLI sessions only" in text


def test_unattested_runs_are_never_read_as_nobody(proj_at):
    _usage(proj_at, ["query", "x"])
    _usage(proj_at, ["query", "unseen"])
    assert hookcmd.run(_args("tool", agent="claude", command="graphify query x")) == 0
    text = adoption.render_adoption(adoption.summarize(proj_at))
    assert "Not evidence that no agent ran them" in text


def test_adoption_csv_carries_the_attested_split(proj_at):
    _usage(proj_at, ["query", "x"])
    assert hookcmd.run(_args("tool", agent="kiro", command="graphify query x")) == 0
    csv_text = adoption.render_csv(adoption.summarize(proj_at))
    assert "usage,agent,kiro,kiro,graphify,1,attest" in csv_text
    assert "agent-unattested" in csv_text          # CSV never gates a caveat away


def test_adoption_still_prints_no_currency(proj_at):
    _usage(proj_at, ["query", "x"])
    assert hookcmd.run(_args("tool", agent="claude", command="graphify query x")) == 0
    assert "$" not in adoption.render_adoption(adoption.summarize(proj_at))


# ── auto task-close: closes, but never claims success ─────────────────────────

def test_session_end_closes_this_sessions_open_tasks(proj_at):
    _call(proj_at, "t-open", "s1")
    _call(proj_at, "t-other", "s2")
    assert hookcmd.run(_args("session-end", session="s1")) == 0
    rows = tasks.read(proj_at)
    assert rows["t-open"]["outcome"] == hookcmd.AUTO
    assert "t-other" not in rows, "a task from another session was closed"


def test_auto_close_is_not_a_success_claim(proj_at):
    """`compare`/`estimate`/`calibration` need a *closed* task; `cage task quality` needs
    a *judged* one. Stamping `ok` because a session ended would inflate the success rate
    of every session that merely finished."""
    from cage import policy, quality, taskgroup
    _call(proj_at, "t1", "s1")
    assert hookcmd.run(_args("session-end", session="s1")) == 0
    assert "t1" in taskgroup.closed_tasks(proj_at)              # eligible for cost comparison
    q = quality.summarize(proj_at, pol=policy.load(None))
    assert q["ok"] == 0 and q["redo"] == 0                # invisible to the quality axis


def test_session_end_with_no_session_declines_rather_than_guessing(proj_at):
    """Kiro's per-turn hook carries no session id. Closing "the most recent open task"
    would be attribution by proximity — forbidden everywhere else in this codebase."""
    _call(proj_at, "t1", "s1")
    assert hookcmd.run(_args("session-end", agent="kiro", session="")) == 0
    assert tasks.read(proj_at) == {}
    assert attest.agents_seen(proj_at) == {"kiro"}        # identity still recorded


def test_an_already_closed_task_is_not_reopened_or_relabelled(proj_at):
    _call(proj_at, "t1", "s1")
    assert clicmds.cmd_outcome(SimpleNamespace(task="t1", redo=True, label="")) == 0
    assert hookcmd.run(_args("session-end", session="s1")) == 0
    assert tasks.read(proj_at)["t1"]["outcome"] == "redo"  # the human's verdict stands


# ── budget: the first real caller of budget.check ─────────────────────────────

def _budgets(root, cap, on_exceed):
    fp = paths.Footprint(root)
    fp.base.mkdir(parents=True, exist_ok=True)
    fp.policy.write_text(f'[budgets]\nsession_usd = {cap}\ndaily_usd = {cap}\n'
                         f'on_exceed = "{on_exceed}"\n', encoding="utf-8")


def test_budget_hook_blocks_only_when_policy_says_block(proj_at, capsys):
    _call(proj_at, "t1", "s1")                    # a real, priced call
    _budgets(proj_at, 0.0001, "block")
    assert hookcmd.run(_args("budget", session="s1")) == hookcmd.BLOCK
    err = capsys.readouterr().err
    assert "BLOCKED" in err and "on_exceed" in err and "cage insights budget" in err


def test_budget_hook_is_advisory_under_warn(proj_at, capsys):
    _call(proj_at, "t1", "s1")
    _budgets(proj_at, 0.0001, "warn")
    assert hookcmd.run(_args("budget", session="s1")) == 0
    assert "not blocking" in capsys.readouterr().err


def test_budget_hook_is_silent_under_the_ceiling(proj_at, capsys):
    _call(proj_at, "t1", "s1")
    _budgets(proj_at, 1000.0, "block")
    assert hookcmd.run(_args("budget", session="s1")) == 0
    assert capsys.readouterr().err == ""


# ── every gap is named, never silently two-of-three ───────────────────────────

def test_every_agent_missing_a_capability_says_so(proj_at):
    lines = agents.hook_gap_lines()
    for agent, gap in agents.HOOK_GAPS.items():
        assert any(line.startswith(f"{agent}:") for line in lines), agent
        assert gap
    # The limit that binds all three is always the last word.
    assert lines[-1].startswith("all agents:") and "VS Code" in lines[-1]


def test_the_posix_shell_limit_is_named_for_all_three(proj_at):
    """P2.2. Every wired hook command is POSIX shell — claude's uses
    `${CLAUDE_PROJECT_DIR:-.}` expansion, copilot's and kiro's are
    `runshim.selflocating_command`'s `git rev-parse … ; exit 0` one-liner — and only
    copilot's schema declares an interpreter (`bash`). kiro's declares none, so on a
    Windows host with no POSIX shell its hook does not run.

    It is asserted as an **all-agents** line rather than a `HOOK_GAPS` key on purpose,
    and both halves of that are load-bearing: it is not per-agent (all three are
    POSIX-shaped), and `HOOK_GAPS` structurally cannot hold it — a full-event-set agent
    must stay disjoint from that table, and claude has the full set. Twinning kiro's
    document is the other non-option: it is a committed file that must be byte-identical
    on every machine."""
    lines = agents.hook_gap_lines()
    shell = [ln for ln in lines if ln.startswith("all agents:") and "POSIX" in ln]
    assert len(shell) == 1, lines
    assert "Windows" in shell[0]
    assert "kiro" in shell[0]          # the agent whose schema names no interpreter
    # Capture must not be implicated: L1 is not for capture, and a reader who thinks a
    # Windows host loses tokens will go looking for a capture bug that does not exist.
    assert "Capture is unaffected" in shell[0]
    # And it is NOT smuggled into the per-agent table.
    assert not any("POSIX" in gap for gap in agents.HOOK_GAPS.values())


def test_copilot_never_claims_session_identity_or_auto_close(proj_at):
    """P2.3. `hookcmd._session` reads `session_id` from *Claude Code's* stdin payload
    shape and nothing else, so on copilot it returns `""`, `_open_tasks` finds nothing,
    and `_session_end` closes zero tasks. The gap text used to end "session identity and
    auto task-close are wired" — the precise overclaim this table exists to prevent."""
    from cage import copilotwire
    gap = agents.HOOK_GAPS["copilot"]
    assert "are wired" not in gap
    assert "DECLINES to auto-close" in gap
    # And the event names are stated as cage's own, not as vendor facts.
    assert "unverified" in gap

    # The mechanism, not just the prose. Copilot's wired command carries no `--session`
    # (`copilotwire._hook_command`) and cage parses no session id out of a Copilot
    # payload, so a real end-event arrives session-less: the task stays OPEN, and the
    # attestation still lands. Same refusal as kiro's, which is what the gap now says.
    assert "--session" not in copilotwire._hook_command("session-end")
    _call(proj_at, "t1", "s1")
    assert hookcmd.run(_args("session-end", agent="copilot", session="")) == 0
    assert tasks.read(proj_at) == {}, "copilot closed a task it cannot identify"
    assert "copilot" in attest.agents_seen(proj_at)   # identity is still recorded


def test_setup_status_never_prints_an_unqualified_hook_count_for_a_limited_agent(
        proj_at, capsys, monkeypatch):
    """P2.3, second half — the one the gap text alone does not fix. `cage setup --status`
    prints `L1 hooks ×N` straight from the wired file's CONTENTS, independent of
    `HOOK_GAPS`, so rewording the table left `copilot … [L1 hooks ×2]` reading as a
    working auto-close. The qualifier is derived from the same one table."""
    from cage import cli
    agents.install(proj_at, hooks=True)
    monkeypatch.chdir(proj_at)
    # Through the LIVE parser, not a hand-built namespace — `--status` is a real front
    # door and this assertion is about what a user actually sees.
    args = cli.build_parser().parse_args(["setup", "--status"])
    assert args.fn(args) == 0
    out = capsys.readouterr().out

    seen = 0
    for surface in agents.SURFACES:
        line = next((ln for ln in out.splitlines()
                     if surface in ln and "L1 hooks" in ln), "")
        if not line:
            continue
        seen += 1
        if surface in agents.HOOK_GAPS:
            assert "limited" in line, f"{surface} claims full L1: {line!r}"
        else:
            assert "limited" not in line, f"{surface} has no gap but is marked: {line!r}"
    assert seen == len(agents.SURFACES), out
    assert "L1 limits:" in out


def test_the_capability_table_is_the_only_source_of_capabilities(proj_at):
    """Every agent appears in the table, and every event it lists is a real one — so
    output describing L1 cannot drift from what is actually installed."""
    assert set(agents.HOOK_EVENTS) == set(agents.SURFACES)
    for events in agents.HOOK_EVENTS.values():
        assert events and set(events) <= set(hookcmd.EVENTS)
    assert set(agents.HOOK_GAPS) <= set(agents.SURFACES)
    # An agent with the full event set must NOT claim a gap, and vice versa.
    full = {a for a, e in agents.HOOK_EVENTS.items() if set(e) == set(hookcmd.EVENTS)}
    assert full.isdisjoint(agents.HOOK_GAPS)
    assert set(agents.HOOK_EVENTS) - full == set(agents.HOOK_GAPS)


# ── steering: one source, three deliveries ────────────────────────────────────

def test_steering_lands_on_all_three_agents_from_one_source(proj_at):
    agents.install(proj_at, hooks=True)
    doc = steering.by_layer("L1")[0]
    written = steering.paths_for(proj_at, doc)
    assert set(written) == set(agents.SURFACES)
    bodies = {}
    for agent, path in written.items():
        assert path.exists(), f"{agent} did not receive the steering doc"
        text = path.read_text(encoding="utf-8")
        bodies[agent] = text.split("---", 2)[-1]
    # Only the host wrapper differs; the substance is one text, never three copies.
    assert doc.body.strip() in bodies["claude"]
    assert all(doc.body.strip() in b for b in bodies.values())


def test_every_document_obeys_the_never_compute_rule(proj_at):
    """Mechanical, not stylistic — a document that promised to do cage's arithmetic
    would be an untagged second implementation of the attribution engine."""
    problems = [p for doc in steering.DOCS for p in steering.lint(doc)]
    assert problems == []


def test_steering_says_to_relay_refusals_verbatim(proj_at):
    body = steering.by_layer("L1")[0].body
    for phrase in ("INSUFFICIENT DATA", "SAVING (GROSS)", "measured", "modeled",
                   "never produce a cage number yourself"):
        assert phrase.lower() in body.lower(), phrase


def test_steering_is_byte_identical_on_a_second_install(proj_at):
    agents.install(proj_at, hooks=True)
    doc = steering.by_layer("L1")[0]
    first = {a: p.read_bytes() for a, p in steering.paths_for(proj_at, doc).items()}
    agents.install(proj_at, hooks=True)
    assert {a: p.read_bytes()
            for a, p in steering.paths_for(proj_at, doc).items()} == first


# ── P3.3: session-end sweeps unthrottled; session-start does not ──────────────

def _capture_on(root, monkeypatch, **capture):
    """Turn capture-on-read on with an explicit throttle, so the sweep gates are the
    ones actually under test. `conftest` pins `CAGE_CAPTURE_ON_READ=0` for the whole
    suite (the determinism/golden law), and the ENV wins over policy — so opting back
    in means unsetting it, not just writing the toml."""
    from cage import paths
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")
    pol = paths.Footprint(root).policy
    pol.parent.mkdir(parents=True, exist_ok=True)
    opts = "\n".join(f"{k} = {v}" for k, v in capture.items())
    pol.write_text(f"[capture]\nenabled = true\non_read = true\n{opts}\n",
                   encoding="utf-8")


def _sweeps(monkeypatch):
    """Record whether the underlying pull sweep actually RAN.

    `ensure_captured`'s return value cannot answer this: it is `None` both when the
    throttle blocked the sweep and when the sweep ran and found nothing new ("zero new
    ⇒ silent"). Those are the two states this defect is about telling apart, so the
    observation has to be one level down."""
    from cage import importcmd
    ran = []
    real = importcmd.run
    monkeypatch.setattr(importcmd, "run",
                        lambda root, agent, args: (ran.append(1), real(root, agent, args))[1])
    return ran


def test_force_skips_the_read_throttle(proj_at, monkeypatch):
    """The mechanism, end to end: a second sweep inside the throttle window does not
    run, and the same call with `force=True` does."""
    from cage import importcmd
    _capture_on(proj_at, monkeypatch, read_throttle_secs=3600)
    ran = _sweeps(monkeypatch)

    importcmd.ensure_captured(proj_at)
    assert len(ran) == 1                     # first read: no prior stamp, sweeps
    importcmd.ensure_captured(proj_at)
    assert len(ran) == 1, "the throttle did not block the second sweep"
    importcmd.ensure_captured(proj_at, force=True)
    assert len(ran) == 2, "force did not skip the throttle"


def test_session_end_sweeps_even_inside_the_read_throttle(proj_at, monkeypatch):
    """`_session_end` sweeps BEFORE `_open_tasks`, and `ensure_captured` returns None
    inside `read_throttle_secs` — so any read in the preceding window meant the
    session's calls were never imported and its final tasks were silently un-closable.
    A session ends exactly once; there is no later trigger to make up for it."""
    from cage import importcmd
    _capture_on(proj_at, monkeypatch, read_throttle_secs=3600)
    importcmd.ensure_captured(proj_at)        # a read, moments before the session ends
    ran = _sweeps(monkeypatch)

    assert hookcmd.run(_args("session-end", session="s1")) == 0
    assert ran, "session-end was throttled out of its own capture sweep"


def test_session_start_stays_throttled_on_purpose(proj_at, monkeypatch):
    """The divergence is deliberate and pinned so a reviewer cannot "tidy" it away:
    session-start has no deadline (the session's calls do not exist yet) and the next
    read — or the session's own end — sweeps anyway. Forcing both would re-scan a warm
    ledger on every turn."""
    from cage import importcmd
    _capture_on(proj_at, monkeypatch, read_throttle_secs=3600)
    importcmd.ensure_captured(proj_at)
    ran = _sweeps(monkeypatch)

    assert hookcmd.run(_args("session-start", session="s1")) == 0
    assert not ran, "session-start swept unthrottled"


def test_force_never_overrides_the_consumer_master_switch(proj_at):
    """`force` skips the throttle, NOT `capture.enabled` — pausing metering has to
    actually pause it — and not `--no-import` either. Both are decisions a user made;
    the throttle is only an optimisation."""
    from cage import importcmd, paths
    pol = paths.Footprint(proj_at).policy
    pol.parent.mkdir(parents=True, exist_ok=True)
    pol.write_text("[capture]\nenabled = false\non_read = true\n", encoding="utf-8")

    assert importcmd.ensure_captured(proj_at, force=True) is None
    assert importcmd.ensure_captured(proj_at, _args("session-end", no_import=True),
                                     force=True) is None
