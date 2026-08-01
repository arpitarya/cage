"""Agent hooks that invoke graphify by an absolute path — the interceptor bypass (B-fix-3).

**The mirror image of `pathshim`.** There, the wrong `graphify` wins on PATH. Here, no
`graphify` on PATH is consulted at all: graphify ≥0.9.30's claude installer writes its
PreToolUse hook with the **absolute** exe path (`_resolve_graphify_exe()`), so the command
never traverses PATH and cage's interceptor cannot see it. A hook is not a Bash tool call
either, so the transcript route is equally blind. Both cage capture routes miss it
(OPEN-WORK §J).

**This is ADVISORY, never a doctor failure**, and the distinction is load-bearing:

  a dead cage shim (`pathshim`)  →  *cage's own wiring is broken*      →  FAILURE
  an absolute-path graphify hook →  *graphify works exactly as designed,
                                     cage simply cannot observe that path*  →  advisory

Crying failure on a correctly-functioning third-party integration is how a check gets
ignored, and an ignored check is how the nine-day silent capture loss happened in the
first place. So the message says what is true and no more: the nudge is invisible; an
explicit `graphify query` on the same machine is still metered normally.

**`--strict` is the exception that earns stronger words.** With `hook-guard read
--strict` (or `GRAPHIFY_HOOK_STRICT` in the environment) the read hook *denies* the first
raw read per session and redirects. The avoided read is a real saving that may never
produce a metered query — unmeterable by **any** current cage route, not merely unseen.

**Never modified.** graphify owns this artifact; cage reports, explains, and stops — the
same rule as a `foreign` winner in `pathshim`. Foreign (non-cage-written) hooks are read
here deliberately, unlike `wiringscan`, which skips them because *its* question is only
ever about cage's own commands.

Read-only; nothing is executed. PII: paths only, never a hook's surrounding config.
"""
from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import NamedTuple

from cage import cfgio, paths, pathshim, wiringscan

_STRICT_ENV = "GRAPHIFY_HOOK_STRICT"
# An env value that reads as "off" — an exported-but-disabled flag must not escalate the
# wording, or the strong message stops meaning anything.
_OFF = ("", "0", "false", "no", "off")


class Bypass(NamedTuple):
    """One hook command that reaches graphify without passing the interceptor."""
    artifact: str      # display path of the hook file (home rendered as ~)
    exe: str           # the graphify path the hook invokes
    strict: bool       # the command (or the environment) enables strict mode

    @property
    def line(self) -> str:
        base = (f"{self.artifact}: graphify's hook invokes `{self.exe}` directly — "
                "cage's PATH interceptor is bypassed, so any saving on that path is "
                "invisible. Savings from an explicit `graphify query` are unaffected")
        if self.strict:
            base += ("; strict mode — savings on this path are unmeterable by any "
                     "current route")
        return base


def _unquote(tok: str) -> str:
    """Strip one matching pair of surrounding quotes — `shlex`'s non-posix mode (used on
    Windows, below) preserves backslashes literally for a native `C:\\...` path, but
    unlike posix mode it does NOT remove the quote marks themselves."""
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in ("'", '"'):
        return tok[1:-1]
    return tok


def _tokens(command: str) -> list[str]:
    """Argv-ish tokens of a hook command. `shlex` so a quoted path stays one token;
    fail-open to a plain split on unbalanced quotes (a diagnostic never raises).
    Non-posix mode on Windows (`os.name == "nt"`) so an unquoted native `C:\\...` path
    keeps its backslashes — posix mode treats `\\` as an escape and mangles it — but
    that mode leaves quote marks on a quoted token, so `_unquote` strips them after."""
    try:
        toks = shlex.split(command, posix=(os.name != "nt"))
    except ValueError:
        toks = command.split()
    return [_unquote(t) for t in toks] if os.name == "nt" else toks


def _graphify_path(command: str) -> str:
    """The graphify **path** a command invokes, or "" if it doesn't invoke one by path.

    A bare `graphify` token is *not* a bypass: it traverses PATH, so the interceptor sees
    it (whether the interceptor is healthy is `pathshim`'s question, not this one). Only a
    token that carries a directory separator names a specific file and skips resolution —
    which is precisely what graphify's installer writes."""
    for tok in _tokens(command):
        name = tok.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if name.split(".")[0] != "graphify":
            continue
        if "/" not in tok and "\\" not in tok:
            return ""          # bare name → PATH-resolved → the interceptor can see it
        return tok
    return ""


def _is_bypass(exe: str) -> bool:
    """True unless the hook's absolute path happens to point at a cage interceptor —
    if it does, cage sees the call after all and there is nothing to report."""
    return not pathshim.is_interceptor(Path(os.path.expanduser(exe)))


def _strict(command: str, env: dict[str, str] | None) -> bool:
    return ("--strict" in _tokens(command)
            or (env or os.environ).get(_STRICT_ENV, "").strip().lower() not in _OFF)


def _artifacts(root: Path) -> list[tuple[str, str]]:
    """(display-path, command) for every agent hook that could name graphify.

    Claude project + local + user-level settings, and kiro's one-hook-per-file
    `*.kiro.hook`. Foreign hooks are included on purpose — the whole point is that this
    one is written by somebody else."""
    out: list[tuple[str, str]] = []
    for rel in (".claude/settings.json", ".claude/settings.local.json"):
        out += [(rel, c) for c in wiringscan.hook_commands(root / rel)]
    claude = paths.claude_home() / "settings.json"
    out += [(wiringscan.display_path(claude), c)
            for c in wiringscan.hook_commands(claude)]
    for hook in sorted((root / ".kiro" / "hooks").glob("*.kiro.hook")):
        cmd = cfgio.load_json(hook).get("then", {}).get("command", "")
        if cmd:
            out.append((f".kiro/hooks/{hook.name}", cmd))
    return out


def scan(root: Path, env: dict[str, str] | None = None) -> list[Bypass]:
    """Every hook command that reaches graphify without passing cage's interceptor.

    Fail-open per artifact (an unreadable or malformed hook contributes nothing) and
    deduped by (file, exe): one hook block commonly repeats the same command across
    several matchers, and reporting it three times would be noise, not evidence."""
    out: list[Bypass] = []
    seen: set[tuple[str, str]] = set()
    for artifact, command in _artifacts(root):
        exe = _graphify_path(command or "")
        if not exe or not _is_bypass(exe) or (artifact, exe) in seen:
            continue
        seen.add((artifact, exe))
        out.append(Bypass(artifact, exe, _strict(command, env)))
    return out
