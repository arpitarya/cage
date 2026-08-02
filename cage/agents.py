"""Multi-agent integration orchestrator (plan §5, §6, §9.5-6).

One ledger contract, three surfaces. Cage targets the wire protocol, so the *meter*
is universal (transcript import — pull-based, no hooks) and the *read* surface is
universal (MCP) — each agent has **its own wire file** that wires that agent's
idiomatic config to those universals:

  claude  → claudewire.py   (.mcp.json)
  copilot → copilotwire.py  (.vscode/mcp.json)
  kiro    → kirowire.py     (.kiro/settings/mcp.json)

**Convention: one `<agent>wire.py` per agent** — a new agent gets its own wire file
exposing `install` / `status`, and is added to `SURFACES` + the dispatch map below.
Hook wiring was removed with the hook machinery; each wire module's `install` heals
(strips/deletes) any hook artifacts a previous version wrote.
"""
from __future__ import annotations

from pathlib import Path

from cage import claudewire, copilotwire, kirowire, runshim

SURFACES = ("claude", "copilot", "kiro")

# The parser stamps a *format* agent on each ledger row (transcript.py) — identical to
# the surface name for copilot/kiro, but claude rows stamp ``claude-code``. This
# maps a ledger row's agent back to its SURFACES name, so a row-presence check (capture
# health's gate 3) matches the surface. Custom-tool rows stamp their own name (not a
# surface) and fall through unchanged — harmless (they never match a surface).
_ROW_AGENT_SURFACE = {"claude-code": "claude"}


def row_surface(row_agent: str | None) -> str | None:
    """The SURFACES name for a ledger row's ``agent`` field (``claude-code`` → ``claude``;
    everything else is identity). A custom-tool name passes through as itself."""
    return _ROW_AGENT_SURFACE.get(row_agent, row_agent)


# The wire module for each surface — add a row here when integrating a new agent.
_WIRE = {"claude": claudewire, "copilot": copilotwire, "kiro": kirowire}

# ── L1 hook capability, per agent — ONE table, read by the wiring AND by output ──────
#
# The three hosts are NOT equivalent here, and the differences are load-bearing rather
# than incidental. This table is the single place they live, so `cage setup --status`,
# `cage doctor` and the wire modules can never describe a different set of capabilities
# from the one actually installed.
#
# Two rules govern what may appear here:
#   1. **Only a host event cage has itself written and tested is listed.** Where an
#      event's name or payload is unverified, the capability is ABSENT and appears in
#      `HOOK_GAPS` — an invented event name fails silently, which is the one outcome
#      this project has already paid for twice.
#   2. **Every absence is named**, never left for a user to discover as "nothing
#      happened". `hook_gap_lines()` renders them and is called by every surface that
#      reports L1 status.
HOOK_EVENTS: dict[str, tuple[str, ...]] = {
    "claude": ("session-start", "session-end", "tool", "budget"),
    "copilot": ("session-start", "session-end"),
    "kiro": ("session-end",),
}

# Why each agent is missing what it is missing. Keyed by agent; a missing key means the
# agent has the full set. These are *platform* facts, not cage defects.
HOOK_GAPS: dict[str, str] = {
    "copilot": ("no per-tool attestation and no budget block — cage has never written "
                "or tested a Copilot pre-tool hook, and an unverified event name fails "
                "silently; session identity and auto task-close are wired"),
    "kiro": ("no session-start trigger exists, so the single `agentStop` hook carries "
             "no session id — cage attests the agent but DECLINES to auto-close a task "
             "rather than closing the most recent one by proximity"),
}

# The limit that applies to all three, always — see `attest.LIMIT`.
HOOK_SURFACE_LIMIT = ("hooks are CLI-only: they do not fire under a VS Code extension, "
                      "so every L1 fact is a CLI-session fact")


def hook_gap_lines() -> list[str]:
    """One line per agent that cannot do everything L1 offers, plus the limit that
    binds all three. Rendered wherever L1 status is shown — a capability silently
    absent for one agent is exactly the failure the three-agent invariant exists to
    prevent."""
    lines = [f"{a}: {HOOK_GAPS[a]}" for a in SURFACES if a in HOOK_GAPS]
    return lines + [f"all agents: {HOOK_SURFACE_LIMIT}"]


def install(root: Path, surfaces: tuple[str, ...] | None = None,
            *, hooks: bool = False, skills: bool = False) -> dict:
    """Wire the picked agents. ``hooks=False`` is the default and the floor: `cage setup`
    stays hookless unless asked (`--hooks`), because L1 must remain opt-in — a layer that
    installed itself would stop being removable, and removability is what the floor test
    proves. ``hooks=False`` also *removes* any cage hook file a previous `--hooks` run
    wrote, so the flag is a two-way switch rather than a one-way door."""
    from cage import paths, policy
    picked = surfaces or SURFACES
    # The wiring mode is project policy (`[wiring] python_launcher`, restricted
    # endpoints) — re-read on every install so a plain re-run of `cage setup`
    # preserves the persisted mode with no flag repeated.
    launcher = policy.python_launcher(policy.load(paths.Footprint(root).policy))
    # Every surface's committed wiring references the committed shim instead of an
    # absolute cage path (plan §5) — write it first so the references always resolve.
    runshim.write(root, python_launcher=launcher)
    out: dict[str, dict] = {}
    for name in (s for s in SURFACES if s in picked):
        out[name] = _WIRE[name].install(root, python_launcher=launcher, hooks=hooks)
    # L1's other half: the steering document. One source, three deliveries
    # ([steering.py](steering.py)) — and, like the hooks, a two-way switch: `hooks=False`
    # removes it, so plain `cage setup` returns the project to the hookless floor.
    # Each layer's documents ride that layer's flag, and each flag is a two-way switch —
    # `hooks=False` / `skills=False` REMOVE what a previous run wrote, so a plain
    # `cage setup` always returns the project to the hookless, skill-less floor.
    from cage import steering
    picked_t = tuple(s for s in SURFACES if s in picked)
    for layer, on, label in (("L1", hooks, "steering doc"), ("L3", skills, "skill")):
        docs = steering.by_layer(layer)
        if on:
            for name, n in steering.install(root, docs, picked_t).items():
                if n:
                    out.setdefault(name, {})[label] = f"{n} {label}(s)"
        else:
            steering.uninstall(root, docs, picked_t)
    # Heal an already-installed graphify interceptor whose capability probe names a
    # verb removed in v0.28.0 (it would exec the real binary unmetered, silently —
    # the F1 root cause). Refresh-only: never scaffolds a shim into a project that
    # doesn't have one. Wired here, not in `adoptcmd.run`, so `cage setup --wire-only`
    # heals it too — the path a user re-runs when doctor reports it dead.
    from cage import adoptcmd
    if adoptcmd.refresh_shim(root):
        out.setdefault("graphify", {})["shim"] = "refreshed bin/graphify → current verb"
    # B-fix-2: the interceptor that actually RUNS is whichever `graphify` PATH resolves
    # first, and an adopt-era one can sit in a *different* project's bin/ — dead, silent,
    # and invisible to the root-scoped refresh above. Heal it only when it is dead AND
    # lives in a cage-managed root (`pathshim.healable`); outside one cage never writes,
    # because silently editing another project's files is the one thing this fix must not
    # become. Fail-open — a write path never raises on a diagnostic's account.
    try:
        from cage import pathshim
        ps = pathshim.classify(root)
        if ps.healable and ps.managed_root != str(root) \
                and adoptcmd.refresh_shim(Path(ps.managed_root)):
            out.setdefault("graphify", {})["path_shim"] = (
                f"refreshed {ps.winner} → current verb "
                "(PATH-winning interceptor, cage-managed root)")
    except Exception as exc:  # noqa: BLE001
        from cage import debuglog
        debuglog.exception(root, "agents.install: PATH-winning shim heal", exc)
    return out


def status(root: Path) -> dict:
    return {name: wire.status(root) for name, wire in _WIRE.items()}
