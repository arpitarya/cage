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

Three artifact classes, three checks:

  1. **commands** — hook/MCP entries, git hooks, the committed shim references. Tail via
     `paths.cage_verb_path`, verb checked against the parser.
  2. **`bin/graphify`** — a shell script, not a config: regex its `cage <tail>`
     occurrences out of the text, then the same parser check.
  3. **assets** (skills / prompts / steering) — prose telling an agent which verbs to
     run, so a stale copy makes the agent issue dead commands. Not parseable as a
     command; hash-compared against `paths.bundled_data()` instead.

Scanning is **read-only and side-effect-free by construction**: no artifact is ever
executed, no `cage import` runs, nothing is written. Executing a probe could not
distinguish "verb dead" from "cage absent" anyway — that ambiguity is the whole bug.

Scope note: this scans **user-level** artifacts too (`~/.copilot/hooks`,
`~/.codex/config.toml`, `.git/hooks`, the global skill/prompt/steering copies). Both
real-world failures were user-level, so a liveness check that skipped them would miss
its own reason to exist. `doctorcmd._portability` stays committed-only — it answers a
different question (what ships to teammates).

PII: paths, verbs and hashes only — never file contents, never a diff.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import NamedTuple

from cage import cfgio, paths, verbmap

# `cage <verb>` inside a shell script (the graphify interceptor) — this is what finds
# the `cage data graphify --help` capability probe that gates the whole shim.
_SHELL_CAGE = re.compile(r"(?:^|[\s|&;(])cage\s+([a-z][a-z0-9-]*(?:\s+[a-z][a-z0-9-]*)?)")
# A `#` at start-of-line or after whitespace opens a shell comment. Comments MUST be
# stripped before the verb scan: the shim's own prose ("# cage absent → identical,
# unmetered behaviour") otherwise reads as a `cage absent` invocation and reports a
# dead verb that nothing ever runs. Only executable lines are evidence.
_SHELL_COMMENT = re.compile(r"(?:^|\s)#.*$", re.MULTILINE)


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


class Stale(NamedTuple):
    """One installed asset whose bytes differ from the bundled original."""
    artifact: str
    agent: str


class Scan(NamedTuple):
    dead: list[Dead]
    stale_assets: list[Stale]
    interceptor_dead: bool   # bin/graphify probes a verb that no longer exists

    @property
    def clean(self) -> bool:
        return not self.dead and not self.stale_assets


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
    """Top-level verbs that own subcommands (`insights`, `data`, `human`, …) — for
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
    `import-claude`/`import-codex` healing after the substring predicate was retired."""
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

def _display(path: Path) -> str:
    """Render a path with the home prefix as `~` (PII: no user name in output)."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _hook_commands(path: Path, key: str = "command") -> list[str]:
    """Commands from a `{"hooks": {<event>: [{"hooks": [...]}]}}` config."""
    out = []
    for entries in cfgio.load_json(path).get("hooks", {}).values():
        for e in entries:
            if isinstance(e, dict) and "hooks" in e:      # claude/codex nesting
                out += [h.get(key, "") for h in e.get("hooks", [])]
            elif isinstance(e, dict):                      # copilot flat entries
                out.append(e.get(key, ""))
    return out


def committed_artifacts(root: Path) -> list[tuple[str, str]]:
    """(display-path, command) for every **project-committed** wired file. This is the
    set `doctorcmd._portability` also walks — it stays committed-only because its
    question is "what ships to a teammate", not "does this still run"."""
    out: list[tuple[str, str]] = []
    for rel in (".claude/settings.json", ".codex/hooks.json"):
        out += [(rel, c) for c in _hook_commands(root / rel)]
    for rel, key in ((".mcp.json", "mcpServers"), (".vscode/mcp.json", "servers")):
        srv = cfgio.load_json(root / rel).get(key, {}).get("cage", {})
        if srv.get("command"):
            out.append((rel, srv["command"]))
    for hook in sorted((root / ".kiro" / "hooks").glob("*.kiro.hook")):
        cmd = cfgio.load_json(hook).get("then", {}).get("command", "")
        out.append((f".kiro/hooks/{hook.name}", cmd))
    return out


def user_artifacts(root: Path) -> list[tuple[str, str]]:
    """(display-path, command) for every **user-level / per-machine** wired file —
    deliberately included (both real F1 failures were user-level)."""
    out: list[tuple[str, str]] = []
    claude = paths.claude_home() / "settings.json"
    out += [(_display(claude), c) for c in _hook_commands(claude)]
    copilot = paths.copilot_home() / "hooks" / "cage.json"
    out += [(_display(copilot), c) for c in _hook_commands(copilot, key="bash")]
    kiro_mcp = paths.kiro_home() / "settings" / "mcp.json"
    srv = cfgio.load_json(kiro_mcp).get("mcpServers", {}).get("cage", {})
    if srv.get("command"):
        out.append((_display(kiro_mcp), " ".join([srv["command"], *srv.get("args", [])])))
    codex_cfg = paths.codex_home() / "config.toml"
    if codex_cfg.exists():
        try:
            text = codex_cfg.read_text(encoding="utf-8")
        except OSError:
            text = ""
        m = re.search(r'\[mcp_servers\.cage\]\ncommand = "([^"\n]*)"\nargs = \[([^\]\n]*)\]',
                      text)
        if m:
            args = " ".join(a.strip().strip('"') for a in m.group(2).split(","))
            out.append((_display(codex_cfg), f"{m.group(1)} {args}".strip()))
    git_hooks = root / ".git" / "hooks"
    for name in ("post-commit", "prepare-commit-msg"):
        path = git_hooks / name
        if not path.exists():
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "# cage-managed-hook" not in body:
            continue     # a foreign git hook — never ours to judge
        out += [(f".git/hooks/{name}", ln.strip())
                for ln in body.splitlines()
                if ln.strip() and not ln.startswith("#!") and not ln.startswith("#")]
    return out


def interceptor_verbs(root: Path) -> list[tuple[str, ...]]:
    """The `cage <verb>` invocations inside `<root>/bin/graphify`. The shim is a shell
    script, so its verbs are text, not a config value — but the same parser check
    applies, and this is what replaces doctor's existence+PATH false ✅."""
    shim = root / "bin" / "graphify"
    if not shim.exists():
        return []
    try:
        text = shim.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    return [tuple(m.split())
            for m in _SHELL_CAGE.findall(_SHELL_COMMENT.sub("", text))]


# ── assets ──────────────────────────────────────────────────────────────────────

def _digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _bundled_digest(rel: tuple[str, ...]) -> str:
    """sha256 of a bundled asset addressed by its path parts (importlib Traversable —
    never `Path(__file__)`, so this still works from inside `cage.pyz`)."""
    node = paths.bundled_data()
    for part in rel:
        node = node / part
    try:
        return hashlib.sha256(node.read_bytes()).hexdigest()
    except (OSError, FileNotFoundError):
        return ""


def stale_assets() -> list[Stale]:
    """Installed skill/prompt/steering copies whose bytes differ from the bundled
    original — the surface `cage setup` overwrites but nothing ever *detected*. Prose,
    not commands, so a hash-compare (not a parser check) is the right instrument; a
    user who hand-edited their own copy is reported advisory, never as a failure."""
    out: list[Stale] = []
    for name, base in (("claude", paths.claude_home()), ("codex", paths.codex_home())):
        for skill in ("cage", "cage-doctor"):
            installed = base / "skills" / skill / "SKILL.md"
            if installed.exists() and _digest(installed) != _bundled_digest(
                    ("skills", skill, "SKILL.md")):
                out.append(Stale(_display(installed), name))
    for stem in ("cage", "cage-doctor"):
        prompt = paths.vscode_user_dir() / "prompts" / f"{stem}.prompt.md"
        if prompt.exists() and _digest(prompt) != _bundled_digest(
                ("prompts", f"{stem}.prompt.md")):
            out.append(Stale(_display(prompt), "copilot"))
        steer = paths.kiro_home() / "steering" / f"{stem}.md"
        if steer.exists() and _digest(steer) != _bundled_digest(
                ("steering", f"{stem}.md")):
            out.append(Stale(_display(steer), "kiro"))
    return out


# ── the scan ────────────────────────────────────────────────────────────────────

def run(root: Path, *, assets: bool = True) -> Scan:
    """Scan every artifact for a dead verb. Read-only; never executes anything.

    Fail-open on a per-artifact basis: an unreadable or malformed file contributes
    nothing rather than raising — a diagnostic must never be the thing that breaks."""
    dead: list[Dead] = []
    for artifact, command, committed in (
            [(a, c, True) for a, c in committed_artifacts(root)]
            + [(a, c, False) for a, c in user_artifacts(root)]):
        verbs = paths.cage_verb_path(command)
        if verbs and not is_live_verb(verbs):
            dead.append(Dead(artifact, " ".join(verbs), remediation(verbs), committed))

    interceptor_dead = False
    for verbs in interceptor_verbs(root):
        if not is_live_verb(verbs):
            interceptor_dead = True
            dead.append(Dead("bin/graphify", " ".join(verbs), remediation(verbs), True))

    return Scan(dead=dead,
                stale_assets=stale_assets() if assets else [],
                interceptor_dead=interceptor_dead)
