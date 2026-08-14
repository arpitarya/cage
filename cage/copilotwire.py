"""Wire Cage into GitHub Copilot: the MCP read server (`.vscode/mcp.json`), plus the
**opt-in** L1 hooks (`.github/hooks/cage.json`).

Capture itself is **pull-based** (`cage import --agent copilot` over
`~/.copilot/session-state/*/events.jsonl` and the VS Code `chatSessions/` store) and
needs no hooks at all — L1 exists for agent identity and auto task-close, not capture.
`install` heals either way: the user-level `~/.copilot/hooks/cage.json` a pre-v0.36 cage
wrote is **always deleted** (Copilot loads repo *and* user hooks and combines them, so
leaving it would double-fire every event), and cage's repo-level entries are stripped
whenever hooks are off — which makes `--hooks` a two-way switch, not a one-way door.
Foreign entries inside `.github/hooks/cage.json` are never touched.

**Portability (ADR-COPILOT):** `.vscode/mcp.json` is project-committed, so it
references the committed shim via `${workspaceFolder}/.cage/bin/cage-run` —
VS Code documents predefined-variable substitution in MCP server config.
"""
from __future__ import annotations

import sys
from pathlib import Path

from cage import cfgio, paths, runshim


# ── L1 hooks (opt-in, `cage setup --hooks`) ──────────────────────────────────────────
# **Repo-level, not user-level** — `.github/hooks/cage.json` is committed and portable,
# so it rides the same `.cage/bin/cage-run` shim every other committed file does and a
# teammate gets it on clone. Copilot loads hooks from BOTH the repo and `~/.copilot/hooks`
# and **combines** them, so wiring both would double-fire every event; cage wires the
# repo one only, and `install` continues to delete the user-level file a pre-v0.36 cage
# wrote. (Repo hooks apply to the coding agent only from the DEFAULT BRANCH — a
# feature-branch wiring will not fire until merged.)
#
# The shape (`{"hooks": {"<event>": [{"bash": "..."}]}}`) and the `sessionStart` event
# name are cage's OWN, from the v0.10 implementation this module still cleans up and
# `tests/test_agents.py` still pins. **No unverified event name is
# invented here** — that is why Copilot has no per-tool attestation and no budget block
# (`agents.HOOK_GAPS` says so in output rather than leaving a user to discover silence).
_HOOK_EVENTS = (("sessionStart", "session-start"), ("sessionEnd", "session-end"))
_HOOKS_REL = ".github/hooks/cage.json"


def _hook_command(sub: str) -> str:
    # The self-locating one-liner, same as Kiro: Copilot documents no repo variable for
    # hook commands and no guaranteed hook cwd, so the command resolves the git root
    # itself and exits 0 when either the repo or the shim is missing. Machine-
    # independent (no path from this machine) and fail-open by construction.
    return runshim.selflocating_command(f"hook {sub} --agent copilot")


def _wire_hooks(root: Path, enable: bool) -> int:
    """Write (or clear) cage's repo-level hook entries. Foreign entries in the same
    file are preserved; the file is removed only when nothing of anyone's is left.

    **"Nothing left to preserve" and "a shape I don't understand" are different
    branches, and conflating them was a data-loss bug.** The old code coerced a non-dict
    `hooks` value to `{}` and fell straight through to `path.unlink()` — on the *default*
    (`enable=False`) `cage setup` path, so an unrecognised file cost the user every
    top-level key it held. Emptiness is a conclusion cage may only draw about a shape it
    read; an unreadable shape means cage knows nothing, least of all that the file is
    disposable. Refuse, and say so."""
    path = root / ".github" / "hooks" / "cage.json"
    data = cfgio.load_json(path)
    raw = data.get("hooks")
    if raw is not None and not isinstance(raw, dict):
        # Branch 1 — unreadable. cage never wrote this; do not strip, do not wire, and
        # above all do not unlink. Fail-open and NOT silent (`cage doctor --wiring`
        # cannot see this file at all today, so stderr is the only channel).
        print(f"· cage: left {path} alone — its `hooks` value is a "
              f"{type(raw).__name__}, not a table cage wrote or understands",
              file=sys.stderr)
        return 0
    hooks = raw or {}
    for event in list(hooks):                       # strip cage's own first: idempotent,
        entries = hooks[event]                      # and makes `--hooks` a two-way switch
        if not isinstance(entries, list):
            continue                                # same refusal, per event: preserve
        # A non-dict entry is foreign by construction — cage only ever writes
        # `{"bash": …}` — so it is KEPT, not skipped and not crashed on. `.get` on a
        # bare string is what took `cage setup` and `cage doctor --wiring` down.
        kept = [h for h in entries
                if not isinstance(h, dict)
                or paths.cage_tail_any(h.get("bash", "")) is None]
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    wired = 0
    if enable:
        for event, sub in _HOOK_EVENTS:
            hooks.setdefault(event, []).append({"bash": _hook_command(sub)})
            wired += 1
    if hooks:
        data["hooks"] = hooks
        cfgio.save_json(path, data)
    else:
        # Branch 2 — read, understood, and genuinely empty. The FILE is cage's (it is
        # named `cage.json`); only the entries inside it can be foreign. With no entries
        # left there is nothing to preserve — remove it rather than leaving an empty
        # shell in a teammate's diff. Reachable ONLY through the readable path above.
        path.unlink(missing_ok=True)
    return wired


def hook_status(root: Path) -> int:
    """How many cage L1 hook entries are wired here (0 = hookless, the default)."""
    hooks = cfgio.load_json(root / ".github" / "hooks" / "cage.json").get("hooks", {})
    if not isinstance(hooks, dict):
        return 0
    # Both `isinstance` guards are load-bearing, not defensive noise: a hand-edited
    # `{"sessionStart": ["cage import"]}` took this function — and `cage setup --status`
    # through it — down with an AttributeError on a bare string.
    return sum(1 for entries in hooks.values() if isinstance(entries, list)
               for h in entries if isinstance(h, dict)
               and paths.cage_tail_any(h.get("bash", "")) is not None)


def install(root: Path, *, python_launcher: bool = False, hooks: bool = False) -> dict:
    del python_launcher  # committed file references the shim; the shim *is* the mode
    mcp = root / ".vscode" / "mcp.json"
    data = cfgio.load_json(mcp)
    # Documented VS Code variable substitution — committed file, no absolute path.
    portable = f"${{workspaceFolder}}/{runshim.SHIM_REL}"
    old = data.get("servers", {}).get("cage", {}).get("command")
    data.setdefault("servers", {})["cage"] = {"type": "stdio", "command": portable,
                                              "args": ["mcp"]}
    cfgio.save_json(mcp, data)
    out = {"mcp": str(mcp)}
    if old is not None and old != portable:
        out["migrated"] = "migrated 1 legacy entry → shim"
    # The USER-level file is cage-owned and is deleted either way: hooks live at repo
    # level so a teammate gets them on clone, and both sources combine — leaving the
    # user-level copy in place would double-fire every event.
    if (user := paths.copilot_home() / "hooks" / "cage.json").exists():
        try:
            user.unlink()
            out["hooks-removed"] = "removed the user-level ~/.copilot/hooks/cage.json " \
                                   "(repo-level is the wired one; both would combine)"
        except OSError:
            pass
    if hooks:
        n = _wire_hooks(root, True)
        out["hooks"] = f"wired {n} L1 hook entr{'y' if n == 1 else 'ies'} ({_HOOKS_REL})"
    else:
        # Hookless is the default, so this one call is BOTH the `--hooks` off-switch and
        # the pre-v0.36 heal: it strips cage's entries wherever they came from.
        _wire_hooks(root, False)
    return out


def status(root: Path) -> bool:
    mcp = root / ".vscode" / "mcp.json"
    return mcp.exists() and "cage" in cfgio.load_json(mcp).get("servers", {})
