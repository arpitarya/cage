"""Wiring liveness — is an installed artifact's cage command still a command? (F1)

v0.28.0 renamed 30 top-level verbs (`verbmap.REMOVED`). Every wiring artifact written
before that still names the old verb, so it exits 1 — and because hook/shim stdout goes
nowhere and both shims fail open to `exit 0`, **a dead verb is indistinguishable from
cage not being installed**. A real machine's `bin/graphify` probed the pre-rename
`graphify` verb and silently exec'd the unmetered binary for 9 days while `cage doctor`
reported ✅, because `_interceptor` checked existence + PATH, not liveness. That is the
root cause behind F1's empty receipts.

**The detector is the live parser, not `verbmap.REMOVED`.** `cli.build_parser()` is the
same code the CLI runs, so it is ground truth for "will this exit 1"; `REMOVED` only
supplies the *replacement* tail. The distinction is load-bearing: `cage adopt` was
deleted outright rather than renamed, so it is dead, still installed on real machines,
and **not in `REMOVED`** — a grep against `REMOVED` would miss it. Detector = parser,
fix-hint = verbmap.

Two artifact classes, two checks (the rendered skill/prompt/steering assets were
removed with the hook machinery — leftover copies surface as leftover rows):

  1. **commands** — MCP entries, leftover hook/git-hook entries from pre-removal
     installs, the committed shim references. Tail via `paths.cage_verb_path`,
     verb checked against the parser.
  2. **`bin/graphify`** — a shell script, not a config: regex its `cage <tail>`
     occurrences out of the text, then the same parser check.

Scanning is **read-only and side-effect-free by construction**: no artifact is ever
executed, no `cage import` runs, nothing is written. Executing a probe could not
distinguish "verb dead" from "cage absent" anyway — that ambiguity is the whole bug.

Scope note: this scans **user-level** artifacts too (`~/.copilot/hooks`, `.git/hooks`,
the global skill/prompt/steering copies). Both
real-world failures were user-level, so a liveness check that skipped them would miss
its own reason to exist. `doctorcmd._portability` stays committed-only — it answers a
different question (what ships to teammates).

PII: paths, verbs and hashes only — never file contents, never a diff.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from cage import cfgio, paths, verbmap

# The marker the (removed) git-commit-hook writer stamped into `.git/hooks/*` —
# kept as a literal so leftover cage-managed git hooks are still recognized.
_GIT_HOOK_MARKER = "# cage-managed-hook"

# `cage <verb>` inside a shell script (the graphify interceptor) — this is what finds
# the `cage interceptor graphify --help` capability probe that gates the whole shim.
_SHELL_CAGE = re.compile(r"(?:^|[\s|&;(])cage\s+([a-z][a-z0-9-]*(?:\s+[a-z][a-z0-9-]*)?)")
# A `#` at start-of-line or after whitespace opens a shell comment. Comments MUST be
# stripped before the verb scan: the shim's own prose ("# cage absent → identical,
# unmetered behaviour") otherwise reads as a `cage absent` invocation and reports a
# dead verb that nothing ever runs. Only executable lines are evidence.
_SHELL_COMMENT = re.compile(r"(?:^|\s)#.*$", re.MULTILINE)
# The same rule for the Windows twin (`data/shims/graphify.cmd`), whose comments are
# `rem` lines: "rem … when a cage command resolves …" would otherwise report a dead
# `cage command` verb and fail doctor on prose. Anchored at statement start, where
# `rem` is unambiguously a comment in batch — a shell line can never begin with it.
_BATCH_COMMENT = re.compile(r"^[ \t]*@?rem\b.*$", re.MULTILINE | re.IGNORECASE)


class Dead(NamedTuple):
    """One artifact naming a verb the parser rejects."""
    artifact: str          # display path (home rendered as ~)
    command: str           # the verb path as written, e.g. "import-claude"
    fix: str               # the replacement tail, or "" when none is known
    committed: bool        # a project-committed file (vs user-level/per-machine)

    @property
    def line(self) -> str:
        fix = f" → `cage {self.fix}`" if self.fix else " (no replacement — removed outright)"
        return f"{self.artifact}: `cage {self.command}` is not a command{fix}"


class Scan(NamedTuple):
    dead: list[Dead]
    # Retained as an always-empty field so doctor code and `Scan(...)` construction
    # keep their shape after the rendered skill/prompt/steering assets (and their
    # byte-digest staleness check) were removed with the hook machinery. Nothing
    # populates it anymore — a stale *asset* is no longer a concept.
    stale_assets: list  # always []
    interceptor_dead: bool   # ANY twin probes a verb that no longer exists
    # Which twins specifically — `{"graphify.cmd"}` when only the Windows one is stale.
    #
    # The bool above is a genuine question ("is graphify metering broken anywhere?") and
    # `doctorcmd._receipts` is right to ask it — a dead twin on either OS explains an
    # empty receipts table. But it was ALSO being consumed as if it described *this*
    # file: the inventory stamped BOTH twins `dead` when one was, and doctor's message
    # named the twin this OS resolves regardless of which one carried the dead verb —
    # so the fix instruction pointed at the wrong file. Hence a set beside the bool
    # rather than in place of it; they answer different questions.
    #
    # Defaulted so `Scan(...)` construction elsewhere keeps its shape (it is public).
    dead_interceptors: frozenset[str] = frozenset()

    @property
    def clean(self) -> bool:
        return not self.dead


# ── the liveness oracle ─────────────────────────────────────────────────────────

_PARSER_VERBS: frozenset[tuple[str, ...]] | None = None


def _parser_verbs() -> frozenset[tuple[str, ...]]:
    """Every verb path the current CLI accepts, as 1- and 2-tuples.

    `cli` is imported **lazily**: `cli` → `clicmds` → `doctorcmd` → this module, so a
    module-level import would be circular. Memoized — building the parser is ~5ms and
    a scan asks many times."""
    global _PARSER_VERBS
    if _PARSER_VERBS is None:
        from cage import cli
        out: set[tuple[str, ...]] = set()
        top = next((a for a in cli.build_parser()._actions
                    if a.choices and a.dest == "cmd"), None)
        for verb, sub in (top.choices.items() if top else ()):
            out.add((verb,))
            nested = next((a for a in sub._actions if a.choices), None)
            for inner in (nested.choices if nested else ()):
                out.add((verb, inner))
        _PARSER_VERBS = frozenset(out)
    return _PARSER_VERBS


def _groups() -> frozenset[str]:
    """Top-level verbs that own subcommands (`insights`, `data`, `task`, …) — for
    those the *pair* must be valid; for a leaf verb a trailing token is just a
    positional argument and says nothing about liveness."""
    return frozenset(v[0] for v in _parser_verbs() if len(v) == 2)


def is_live_verb(verbs: tuple[str, ...]) -> bool:
    """Does the current CLI accept this verb path? Empty (a foreign command) is not
    our business — reported live so nothing foreign is ever flagged or touched."""
    if not verbs:
        return True
    known = _parser_verbs()
    if verbs[:1] not in known:
        return False                      # the top-level verb itself is gone
    if len(verbs) == 1 or verbs[0] not in _groups():
        return True                       # leaf verb: any trailing token is an arg
    return verbs in known                 # group verb: the pair must resolve


def is_dead_cage_command(command: str) -> bool:
    """True if ``command`` invokes cage with a verb the parser rejects. False for a
    foreign command (never ours to judge) and for every live cage command.

    This is the staleness half of the wiring filters; `paths.is_cage_import_command`
    is the collapse half. The wire modules take the **union**, which is what preserves
    `import-claude` healing after the substring predicate was retired."""
    verbs = paths.cage_verb_path(command)
    return bool(verbs) and not is_live_verb(verbs)


def remediation(verbs: tuple[str, ...]) -> str:
    """The replacement tail for a dead verb path, from `verbmap.REMOVED`; "" when the
    verb was removed outright (`adopt`) and no replacement exists. Heal never guesses:
    an empty remediation means report it, leave it alone."""
    return verbmap.REMOVED.get(verbs[0], "") if verbs else ""


def heal_tail(tail: str) -> str:
    """A command tail with its dead head verb rewritten to the current form; unchanged
    when the verb is live or has no known replacement. `import-claude --project .` →
    `import --agent claude --project .`."""
    parts = (tail or "").split(None, 1)
    if not parts or is_live_verb((parts[0],)):
        return tail
    fix = verbmap.REMOVED.get(parts[0], "")
    if not fix:
        return tail
    return f"{fix} {parts[1]}".rstrip() if len(parts) > 1 else fix


# ── artifact enumeration ────────────────────────────────────────────────────────

def display_path(path: Path) -> str:
    """Render a path with the home prefix as `~` (PII: no user name in output).

    Public because `hookbypass` renders the same user-level paths; one renderer keeps
    the home-redaction rule in a single place."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def hook_commands(path: Path, key: str = "command") -> list[str]:
    """Commands from a `{"hooks": {<event>: [{"hooks": [...]}]}}` config.

    Public because `hookbypass` reads the same artifacts for a different question — is a
    *third-party* command in there bypassing cage's interceptor — and the enumeration
    must not be forked."""
    out = []
    for entries in cfgio.load_json(path).get("hooks", {}).values():
        for e in entries:
            if isinstance(e, dict) and "hooks" in e:      # claude's nested form
                out += [h.get(key, "") for h in e.get("hooks", [])]
            elif isinstance(e, dict):                      # copilot flat entries
                out.append(e.get(key, ""))
    return out


def committed_artifacts(root: Path) -> list[tuple[str, str]]:
    """(display-path, command) for every **project-committed** wired file. This is the
    set `doctorcmd._portability` also walks — it stays committed-only because its
    question is "what ships to a teammate", not "does this still run"."""
    out: list[tuple[str, str]] = []
    out += [(".claude/settings.json", c)
            for c in hook_commands(root / ".claude" / "settings.json")]
    # Copilot's L1 hook is **repo-level** (`copilotwire`: repo-level so a teammate gets
    # it on clone), so it is committed and belongs here. It was missed, which meant a
    # dead verb in it was invisible to the headline `wiring` check — the one failure
    # class this whole module exists to catch, in the file a teammate inherits.
    out += [(".github/hooks/cage.json", c)
            for c in hook_commands(root / ".github" / "hooks" / "cage.json", key="bash")]
    for rel, key in ((".mcp.json", "mcpServers"), (".vscode/mcp.json", "servers")):
        srv = cfgio.load_json(root / rel).get(key, {}).get("cage", {})
        if srv.get("command"):
            out.append((rel, srv["command"]))
    # Kiro's MCP entry is committed too (path-free `python3 -m cage mcp`, v0.41) and
    # takes the `command` + `args` idiom `user_artifacts` already uses for the
    # user-level copy of the same file — the two halves must enumerate alike.
    kiro_mcp = cfgio.load_json(root / ".kiro" / "settings" / "mcp.json")
    srv = kiro_mcp.get("mcpServers", {}).get("cage", {})
    if srv.get("command"):
        out.append((".kiro/settings/mcp.json",
                    " ".join([srv["command"], *srv.get("args", [])])))
    for hook in sorted((root / ".kiro" / "hooks").glob("*.kiro.hook")):
        cmd = cfgio.load_json(hook).get("then", {}).get("command", "")
        out.append((f".kiro/hooks/{hook.name}", cmd))
    return out


def user_artifacts(root: Path) -> list[tuple[str, str]]:
    """(display-path, command) for every **user-level / per-machine** wired file —
    deliberately included (both real F1 failures were user-level)."""
    out: list[tuple[str, str]] = []
    claude = paths.claude_home() / "settings.json"
    out += [(display_path(claude), c) for c in hook_commands(claude)]
    copilot = paths.copilot_home() / "hooks" / "cage.json"
    out += [(display_path(copilot), c) for c in hook_commands(copilot, key="bash")]
    kiro_mcp = paths.kiro_home() / "settings" / "mcp.json"
    srv = cfgio.load_json(kiro_mcp).get("mcpServers", {}).get("cage", {})
    if srv.get("command"):
        out.append((display_path(kiro_mcp), " ".join([srv["command"], *srv.get("args", [])])))
    git_hooks = root / ".git" / "hooks"
    for name in ("post-commit", "prepare-commit-msg"):
        path = git_hooks / name
        if not path.exists():
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _GIT_HOOK_MARKER not in body:
            continue     # a foreign git hook — never ours to judge
        out += [(f".git/hooks/{name}", ln.strip())
                for ln in body.splitlines()
                if ln.strip() and not ln.startswith("#!") and not ln.startswith("#")]
    return out


def verbs_in_shell(text: str) -> list[tuple[str, ...]]:
    """The `cage <verb>` invocations in a shim's **executable** lines — sh `#` comments
    and batch `rem` comments alike are stripped first, because prose is not evidence.

    Split out from `interceptor_verbs` so `pathshim` can apply the identical scan to a
    shim found anywhere on PATH rather than re-deriving one — the detector must have a
    single implementation, or the PATH-winning check and the root check could disagree
    about the same file. Both twins go through this one function for the same reason."""
    return [tuple(m.split())
            for m in _SHELL_CAGE.findall(
                _SHELL_COMMENT.sub("", _BATCH_COMMENT.sub("", text)))]


def interceptor_verbs(root: Path) -> list[tuple[str, ...]]:
    """The `cage <verb>` invocations inside `<root>/bin/graphify` **and its `.cmd`
    twin**. A shim is a script, so its verbs are text, not a config value — but the same
    parser check applies, and this is what replaces doctor's existence+PATH false ✅.

    Both twins are scanned on every OS, not just the resolvable one: `bin/` is committed
    and shared, so a dead verb in the twin this machine cannot run is still a dead verb
    on a teammate's machine — and staying silent about it is the same silence that let
    F1 run for nine days.

    Root-scoped by design; the shim that actually *runs* is whichever `graphify` PATH
    resolves first, which can live outside every scanned root — that is `pathshim`."""
    out: list[tuple[str, ...]] = []
    for shim in paths.graphify_shims(root):
        if not shim.exists():
            continue
        try:
            out += verbs_in_shell(shim.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return out


# ── the scan ────────────────────────────────────────────────────────────────────

def run(root: Path, *, assets: bool = True) -> Scan:
    """Scan every artifact for a dead verb. Read-only; never executes anything.

    Fail-open on a per-artifact basis: an unreadable or malformed file contributes
    nothing rather than raising — a diagnostic must never be the thing that breaks.

    ``assets`` is accepted for call-site compatibility but inert: the rendered
    skill/prompt/steering assets were removed with the hook machinery, so there is
    no longer a stale-*asset* concept — ``Scan.stale_assets`` is always ``[]``."""
    del assets
    dead: list[Dead] = []
    for artifact, command, committed in (
            [(a, c, True) for a, c in committed_artifacts(root)]
            + [(a, c, False) for a, c in user_artifacts(root)]):
        verbs = paths.cage_verb_path(command)
        if verbs and not is_live_verb(verbs):
            dead.append(Dead(artifact, " ".join(verbs), remediation(verbs), committed))

    # Per-twin, so the finding names the file to fix rather than a generic
    # "bin/graphify" that may not even be the copy carrying the dead verb.
    dead_shims: set[str] = set()
    for shim in paths.graphify_shims(root):
        if not shim.exists():
            continue
        try:
            text = shim.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for verbs in verbs_in_shell(text):
            if not is_live_verb(verbs):
                dead_shims.add(shim.name)
                dead.append(Dead(f"bin/{shim.name}", " ".join(verbs),
                                 remediation(verbs), True))

    return Scan(dead=dead, stale_assets=[], interceptor_dead=bool(dead_shims),
                dead_interceptors=frozenset(dead_shims))


# ── inventory (`cage doctor --wiring`) ───────────────────────────────────────────
#
# A browsable itemization of the same data `run()` already computes — renders the
# enumeration + liveness, forks none of it. Two extra questions `run()` doesn't
# answer: which artifact belongs to which *agent* (for grouping + a per-agent
# rollup), and what's *missing* from a partially-wired agent (`run()` only sees
# what's on disk, never what should be).


class Artifact(NamedTuple):
    """One inventory row."""
    agent: str      # "claude" | "copilot" | "kiro" | "" (shared)
    kind: str       # "mcp" | "git-hook" (foreign only) | "shim" | "other"
    scope: str      # "project" | "global"
    display: str
    status: str     # "current" | "stale" | "dead" | "foreign"
    detail: str = ""


class AgentRollup(NamedTuple):
    """Per-agent verdict; `doctorcmd.render_wiring_text` formats it into the display
    line the same way for both this and the `--json` dict form."""
    agent: str
    verdict: str            # "fully wired" | "partially wired" | "not wired"
    missing: tuple[str, ...] = ()
    dead: int = 0
    stale: int = 0


class Inventory(NamedTuple):
    items: list[Artifact]
    rollups: list[AgentRollup]


class _Spec(NamedTuple):
    """One artifact a full `cage setup --wire-only --<agent>` writes. `required=False`
    marks a piece that is normal to be missing, so its absence never reads as a partial
    install (handoff §8). **Nothing is optional today** — Kiro's project
    `.kiro/settings/mcp.json` was the only holder of that flag, and it lost it when the
    entry went path-free and therefore committable (kirowire.py). The flag stays because
    the next optional layer (L1 hooks are opt-in) will need it."""
    kind: str
    scope: str
    display: str
    required: bool
    present: bool
    commands: tuple[str, ...] = ()


def _spec_status(display: str, commands: tuple[str, ...], committed: bool) -> tuple[str, str]:
    """(status, detail) for a *present* artifact — dead beats current; an MCP command's
    prose is not byte-tracked, so the only non-current status a spec can carry is dead."""
    for c in commands:
        verbs = paths.cage_verb_path(c)
        if verbs and not is_live_verb(verbs):
            return "dead", Dead(display, " ".join(verbs), remediation(verbs), committed).line
    return "current", ""


# Each `_<agent>_specs` is the one place that agent's expected artifact shape lives —
# built from the wire module's own `status`/config presence (never a re-derived
# presence check), so it can't drift from what `install()` writes. A new agent needs a
# row here too (mirrors the "add a row" convention in `agents.py`/`_WIRE`) — but the
# AGENT LIST itself always comes from `agents.SURFACES`, never from this table's keys
# (see `inventory()`).

# Capture is pull-based, so MCP is the only **required** wired surface. The opt-in L1
# hooks are `required=False` — absent is the default and must never read as a partial
# install — but when present they are scanned exactly like any other artifact.
#
# **That scan is the point, not a bonus.** A hook whose command names a renamed verb
# exits 1 with its output going nowhere, which is indistinguishable from cage not being
# installed; that is the F1 failure, and it cost nine silent days. Every hook command
# cage writes therefore goes into a spec's `commands` tuple and is checked against the
# **live parser** — so `cage hook <event>` cannot be renamed without this turning red.

def _hook_spec(display: str, n: int, commands: tuple[str, ...]) -> _Spec:
    return _Spec("hooks", "project", display, False, bool(n), commands)


def _claude_specs(root: Path) -> list[_Spec]:
    from cage import claudewire
    mcp = root / ".mcp.json"
    mcp_cmd = cfgio.load_json(mcp).get("mcpServers", {}).get("cage", {}).get("command", "")
    settings = cfgio.load_json(root / ".claude" / "settings.json").get("hooks") or {}
    # `hook_commands` above already guards this shape; these two spec builders did not,
    # so a hand-edited entry took `cage doctor --wiring` down as well as `cage setup`.
    hook_cmds = tuple(h.get("command", "") for entries in settings.values()
                      if isinstance(entries, list) for e in entries
                      if isinstance(e, dict)
                      for h in (e.get("hooks") if isinstance(e.get("hooks"), list) else [])
                      if isinstance(h, dict)
                      and paths.cage_command_tail(h.get("command", "")) is not None)
    return [_Spec("mcp", "project", ".mcp.json", True, bool(mcp_cmd),
                  (mcp_cmd,) if mcp_cmd else ()),
            _hook_spec(".claude/settings.json (L1 hooks)",
                       claudewire.hook_status(root), hook_cmds)]


def _copilot_specs(root: Path) -> list[_Spec]:
    from cage import copilotwire
    mcp = root / ".vscode" / "mcp.json"
    mcp_cmd = cfgio.load_json(mcp).get("servers", {}).get("cage", {}).get("command", "")
    hooks = cfgio.load_json(root / ".github" / "hooks" / "cage.json").get("hooks") or {}
    if not isinstance(hooks, dict):
        hooks = {}
    hook_cmds = tuple(h.get("bash", "") for entries in hooks.values()
                      if isinstance(entries, list) for h in entries
                      if isinstance(h, dict)
                      and paths.cage_tail_any(h.get("bash", "")) is not None)
    return [_Spec("mcp", "project", ".vscode/mcp.json", True, bool(mcp_cmd),
                  (mcp_cmd,) if mcp_cmd else ()),
            _hook_spec(".github/hooks/cage.json (L1 hooks)",
                       copilotwire.hook_status(root), hook_cmds)]


def _kiro_specs(root: Path) -> list[_Spec]:
    # `required=True` since the entry went **path-free** (`python3 -m cage mcp`,
    # kirowire.py): it is committed and byte-identical like the other two, so a missing
    # one is a genuinely partial install again. It was `required=False` only while the
    # file had to carry a machine-absolute path and was gitignore-advised.
    mcp = root / ".kiro" / "settings" / "mcp.json"
    srv = cfgio.load_json(mcp).get("mcpServers", {}).get("cage", {})
    mcp_cmd = " ".join([srv.get("command", ""), *srv.get("args", [])]).strip()
    from cage import kirowire
    hook = cfgio.load_json(root / ".kiro" / "hooks" / "cage.kiro.hook")
    hook_cmd = hook.get("then", {}).get("command", "")
    return [_Spec("mcp", "project", ".kiro/settings/mcp.json", True,
                  kirowire.status(root), (mcp_cmd,) if mcp_cmd else ()),
            _hook_spec(".kiro/hooks/cage.kiro.hook (L1 hook)",
                       kirowire.hook_status(root),
                       (hook_cmd,) if hook_cmd else ())]


_SPECS = {"claude": _claude_specs, "copilot": _copilot_specs, "kiro": _kiro_specs}


def _agent_inventory(agent: str, specs: list[_Spec], stale: int = 0) -> tuple[list[Artifact], AgentRollup]:
    """Build this agent's rows + rollup. ``stale`` is retained (always 0 now that the
    rendered assets are gone) so the "needs healing" verdict keeps its shape; a dead
    command still drives it."""
    items: list[Artifact] = []
    missing: list[str] = []
    dead = 0
    any_present = False
    for s in specs:
        if not s.present:
            if s.required:
                missing.append(s.kind)
            continue
        any_present = True
        status, detail = _spec_status(s.display, s.commands, s.scope == "project")
        if status == "dead":
            dead += 1
        items.append(Artifact(agent, s.kind, s.scope, s.display, status, detail))
    # Four mutually-exclusive verdicts (DoD §2) — "needs healing" takes priority over
    # "fully wired" when something present is broken; a "not wired" agent stays purely
    # informational (no missing-list nag) even if it happens to have a dead leftover.
    if dead or stale:
        verdict = "needs healing"
    elif not any_present:
        verdict = "not wired"
    elif missing:
        verdict = "partially wired"
    else:
        verdict = "fully wired"
    return items, AgentRollup(agent, verdict,
                              tuple(missing) if verdict == "partially wired" else (),
                              dead, stale)


def _git_hook_foreign(root: Path) -> list[Artifact]:
    """A `.git/hooks/{post-commit,prepare-commit-msg}` that exists but isn't cage's —
    `user_artifacts()` deliberately never returns these (never ours to judge), so this
    is the one place they're surfaced: shown, never acted on. (Cage no longer writes
    git hooks; a marked one is a pre-removal leftover, handled by `user_artifacts`.)"""
    out: list[Artifact] = []
    for name in ("post-commit", "prepare-commit-msg"):
        path = root / ".git" / "hooks" / name
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _GIT_HOOK_MARKER not in text:
            out.append(Artifact("", "git-hook", "project", f".git/hooks/{name}",
                                "foreign", "not cage-managed"))
    return out


def _base_display(display: str) -> str:
    """A spec display with any trailing annotation stripped — `".claude/settings.json
    (L1 hooks)"` ⇒ `".claude/settings.json"`.

    `covered` is matched against the RAW enumeration (`committed_artifacts` /
    `user_artifacts`), whose displays are bare paths, but hook specs annotate theirs. A
    suffixed key therefore never matched, and **every wired hook command re-listed as an
    unexplained "other" leftover** — reproduced against this repo: four phantom
    `.claude/settings.json` rows plus kiro's.

    It strips **any** trailing parenthetical, not the literal `" (L1 hooks)"`, and that
    is not defensiveness: kiro's display is `" (L1 hook)"` — **singular** — so the
    obvious literal `removesuffix` fixes claude and copilot and leaves kiro silently
    broken, which is the same two-of-three failure the whole `HOOK_GAPS` discipline
    exists to prevent."""
    return re.sub(r"\s*\([^()]*\)\s*$", "", display)


def _leftover(root: Path, covered: set[str]) -> list[Artifact]:
    """Anything the raw enumeration finds that isn't part of a known agent's expected
    set — an orphaned pre-removal hook artifact or a stray cage command in an
    unanticipated slot. Never invented, never silently dropped."""
    out: list[Artifact] = []
    for display, command, committed in (
            [(d, c, True) for d, c in committed_artifacts(root)]
            + [(d, c, False) for d, c in user_artifacts(root)]):
        if display in covered:
            continue
        verbs = paths.cage_verb_path(command)
        if not verbs:
            continue  # a foreign command at a shared-looking location — not ours to judge
        status = "current" if is_live_verb(verbs) else "dead"
        detail = (Dead(display, " ".join(verbs), remediation(verbs), committed).line
                  if status == "dead" else "")
        out.append(Artifact(_leftover_agent(display), "other",
                            "project" if committed else "global", display, status, detail))
    return out


def _leftover_agent(display: str) -> str:
    """A cosmetic label for a leftover row — e.g. a lingering global
    `~/.claude/settings.json` no current wire module writes. Never used for the
    expected-set/rollup computation (that's `_SPECS` keyed on `agents.SURFACES`
    alone) — display only, so it can't misclassify what counts as "wired"."""
    low = display.lower()
    for tag in ((".claude", "claude"), ("copilot", "copilot"), (".kiro", "kiro")):
        if tag[0] in low:
            return tag[1]
    return ""


def inventory(root: Path) -> Inventory:
    """The full per-artifact installed inventory (`cage doctor --wiring`), grouped by
    scope + agent. The agent list is `agents.SURFACES` — never hand-written here, so
    adding or removing an agent updates this automatically. Read-only: builds
    entirely on `run()`'s enumeration; nothing is executed or healed."""
    from cage import agents

    scan = run(root)
    items: list[Artifact] = []
    rollups: list[AgentRollup] = []
    covered: set[str] = set()

    for agent in agents.SURFACES:
        build = _SPECS.get(agent)
        specs = build(root) if build else []
        agent_items, rollup = _agent_inventory(agent, specs)
        items += agent_items
        rollups.append(rollup)
        covered |= {_base_display(s.display) for s in specs if s.present}

    items += _git_hook_foreign(root)
    items += _leftover(root, covered)

    # Both twins are listed when present — the inventory's job is to show what is
    # installed, and "the copy this OS cannot run" is exactly the fact a Windows user
    # upgrading a POSIX-scaffolded project needs to see.
    primary = root / "bin" / paths.graphify_shim_name()
    for shim in paths.graphify_shims(root):
        if not shim.exists():
            continue
        # Per-twin, not the global bool: one stale twin used to stamp BOTH rows `dead`,
        # so a healthy copy was reported broken and the reader had no way to tell which
        # file to fix. `tests/test_win_graphify_shim.py` pinned `scan.dead` but never
        # these rendered rows, which is how it stayed green.
        this_dead = shim.name in scan.dead_interceptors
        detail = ("probes a removed verb — every graphify call falls through UNMETERED "
                  "and silently" if this_dead else
                  "" if shim == primary else
                  f"the other twin — this OS resolves bin/{primary.name}, not this copy")
        items.append(Artifact("", "shim", "project", f"bin/{shim.name}",
                              "dead" if this_dead else "current", detail))
    items += _path_winner(root, primary)

    return Inventory(items=items, rollups=rollups)


def _path_winner(root: Path, shim: Path) -> list[Artifact]:
    """The graphify PATH resolves first, when it is **not** this root's own shim.

    An inventory that lists only in-root artifacts would omit the single file that
    decides whether graphify is metered at all — and that omission is precisely how a
    dead interceptor in another project stayed invisible. Lazy import: `pathshim`
    imports this module for its liveness oracle. Read-only, like everything here."""
    from cage import pathshim
    try:
        ps = pathshim.classify(root)
    except Exception:  # noqa: BLE001 — an inventory row is never worth a crash
        return []
    if not ps.winner or ps.winner == str(shim):
        return []
    status, detail = {
        "dead": ("dead", "PATH-winning interceptor probes a removed verb — every "
                         "graphify call falls through UNMETERED and silently"),
        "live": ("current", "PATH-winning interceptor, naming live verbs"),
        # A shadowing winner may be another cage interceptor or the real binary — the
        # status must follow which, or the inventory would call an unmetered binary
        # "current" simply because it happens to win.
        "shadowed": ("current" if ps.interceptor else "foreign",
                     f"wins on PATH over this project's {shim}"),
        "foreign": ("foreign", "not a cage interceptor — graphify runs unmetered"),
    }[ps.state]
    return [Artifact("", "shim", "global", display_path(Path(ps.winner)), status, detail)]
