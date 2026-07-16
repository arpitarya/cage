"""Path resolution for the per-project `.cage/` footprint + agent homes (plan §3, §5)."""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import NamedTuple


def cage_bin() -> str:
    """Absolute path to the `cage` executable, for the commands cage writes into agent
    hook files. **GUI-launched agents** (Kiro IDE, the Copilot extension, a Codex app)
    run hooks with a minimal PATH that omits `~/.local/bin`, so a bare `cage` in a hook
    fails silently with 'command not found' and nothing is captured — the #1 reason a
    wired hook doesn't fire. Resolve it at wire time; fall back to the package's own
    console-script dir (`Scripts\\cage.exe` beside a Windows interpreter), then bare."""
    resolved = shutil.which("cage")
    if resolved:
        return resolved
    exe_dir = Path(sys.executable).parent  # same venv as the running interpreter
    for candidate in (exe_dir / "cage", exe_dir / "cage.exe",
                      exe_dir / "Scripts" / "cage.exe"):
        if candidate.exists():
            return str(candidate)
    return "cage"


def quoted_cage_bin() -> str:
    """`cage_bin()` quoted for use inside a shell-ish hook command line — a resolved
    Windows path (`C:\\Users\\Foo Bar\\...\\cage.exe`) or any install dir with spaces
    would otherwise split at the space and the hook dies with 'command not found'."""
    c = cage_bin()
    return f'"{c}"' if " " in c else c


def _split_bin(command: str) -> tuple[str, str]:
    """(executable, rest) for a hook command whose executable may be quoted —
    `shlex` is POSIX-only and mangles Windows backslashes, so split by hand."""
    command = command or ""
    if command.startswith('"'):
        end = command.find('"', 1)
        if end > 0:
            return command[1:end], command[end + 1:].strip()
    parts = command.split(None, 1)
    return (parts[0] if parts else ""), (parts[1] if len(parts) == 2 else "")


_PY_LAUNCHER = re.compile(r"^(python[0-9.]*|py)(\.exe)?$")
_PY_CAGE_TAIL = re.compile(r"^(?:-3(?:\.\d+)?\s+)?-m\s+cage(?:\s+(.*))?$")


def cage_command_tail(command: str) -> str | None:
    """The subcommand tail if ``command`` invokes cage — by binary name (`cage …`,
    `/abs/path/cage …`, the Windows `…\\cage.exe` forms, quoted), **via the
    committed shim** (`cage-run` in any host's reference form, plan §5), or **via
    the interpreter** (`python3 -m cage …` / `py -3 -m cage …` — python-launcher
    wiring mode, docs/restricted-environments.md); else None (a foreign hook —
    never touch it). The superset detector wiring/migration use;
    `reresolve_cage_command` deliberately stays binary-only so nothing can ever
    rewrite a portable shim or interpreter reference back into an absolute path."""
    bin0, sub = _split_bin(command)
    if not bin0:
        return None
    name = bin0.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if name in ("cage", "cage.exe", "cage-run", "cage-run.cmd"):
        return sub
    if _PY_LAUNCHER.match(name):
        m = _PY_CAGE_TAIL.match(sub)
        if m:
            return m.group(1) or ""
    return None


def is_cage_import_command(command: str) -> bool:
    """True if ``command`` is a cage ``import …`` hook command (any agent/flags), in
    binary, shim, or self-locating one-liner form. Lets the wiring collapse a
    superseded per-agent import (e.g. `cage import --agent codex`) into the current
    per-agent import on re-setup, instead of leaving both."""
    cmd = command or ""
    if " import" not in cmd:
        return False
    # the codex/kiro self-locating one-liner doesn't start with an executable name —
    # its shim path in the middle is the cage marker
    return cage_command_tail(cmd) is not None or "cage-run" in cmd


def reresolve_cage_command(command: str) -> str | None:
    """If ``command`` is a cage hook command (`cage …`, `/abs/path/cage …`, quoted, or
    the Windows `…\\cage.exe` forms), return it rewritten to the currently-resolved
    (quoted-if-needed) cage path, preserving the subcommand; else None. Lets `cage
    setup` *heal* a stale bare-`cage` (or moved-binary) hook on re-run — the reason a
    previously-wired hook silently stopped firing under a GUI agent's PATH."""
    bin0, sub = _split_bin(command)
    if not bin0:
        return None
    name = bin0.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if name not in ("cage", "cage.exe"):
        return None  # a foreign (non-cage) hook — never touch it
    return f"{quoted_cage_bin()} {sub}".rstrip()


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from ``start`` to the dir containing a *project* ``.cage/`` footprint.

    The machine-wide **global** base (``$CAGE_HOME/.cage``, default ``~/.cage``,
    plan §3.7) is deliberately *not* a project: it is the fallback capture sink,
    a separate tier of the resolution precedence (override → project → global).
    Without this exclusion, any dir under ``$HOME`` on a machine with a global
    ledger resolves to ``~`` as its "project" — `cage setup` then re-inits the
    global instead of scaffolding the new project's own ``.cage/``, and doctor
    mislabels the global sink as ``project (.cage/)``."""
    cur = (start or Path.cwd()).resolve()
    # Exclude the *active* global sink AND the default `~/.cage`: when CAGE_HOME
    # redirects the global elsewhere (tests, the dummyrepo runner), the real home's
    # `.cage` is still a global sink — treating it as a project made $HOME the
    # "project root" of every dir under it and routed sandbox writes into the real
    # global ledger (2026-07 manual validation).
    excluded = {global_base().resolve(), (Path.home() / ".cage").resolve()}
    for parent in [cur, *cur.parents]:
        base = parent / ".cage"
        if base.is_dir() and base.resolve() not in excluded:
            return parent
    return None


def global_home() -> Path:
    """The dir that *contains* the machine-wide global ``.cage`` — ``$CAGE_HOME`` if set,
    else ``~``. ``CAGE_HOME`` keeps the global ledger relocatable (and lets tests redirect
    it off the real home)."""
    return Path(os.environ.get("CAGE_HOME", Path.home()))


def global_base() -> Path:
    """The machine-wide global cage base (``$CAGE_HOME/.cage``, default ``~/.cage``) — the
    capture sink for the no-project user (no `.cage/` in cwd and no ``--ledger``/``CAGE_BASE``
    override). Mirrors a project ``.cage/`` so the same readers/writers work over it (§3.7)."""
    return global_home() / ".cage"


def resolve_root(start: Path | None = None) -> Path:
    """The root whose :class:`Footprint` is the **active** ledger, per the capture
    precedence (plan §3.7): ``--ledger``/``CAGE_BASE`` → nearest project ``.cage/`` from
    cwd → global ``~/.cage``. One active sink per run — never a double-write.

    A ``CAGE_BASE`` override (what ``--ledger`` sets) re-bases every ``Footprint``, so the
    root returned then only co-locates paths; the project walk and the home fallback cover
    the other two tiers. The legacy ``CAGE_LEDGER`` (a *ledger-dir* override, e.g. Orff's
    elgar store) is honored independently by ``Footprint.ledger`` and is unchanged.
    ``Footprint(global_home()).base`` is exactly ``global_base()``."""
    if os.environ.get("CAGE_BASE"):
        return (start or Path.cwd())
    proj = find_project_root(start)
    return proj if proj is not None else global_home()


def active_ledger_source(start: Path | None = None) -> str:
    """Which precedence tier the active ledger came from — for ``cage doctor`` to print
    *which* sink is live when both a project and the global ledger exist."""
    if os.environ.get("CAGE_BASE"):
        return "override (--ledger/CAGE_BASE)"
    if find_project_root(start) is not None:
        return "project (.cage/)"
    return "global (~/.cage)"


def bundled_data():
    """Seed data shipped with the cage package (default policy + skill assets).

    Returns an ``importlib.resources`` Traversable: a real directory ``Path`` under
    a wheel/editable install (identical behavior to the old ``__file__`` form), a
    zip entry when cage runs from ``cage.pyz``. Callers that need a real filesystem
    path (copying assets out) wrap items in ``importlib.resources.as_file``."""
    import importlib.resources
    return importlib.resources.files("cage") / "data"


def distribution() -> str:
    """``"zipapp"`` when cage runs from a ``.pyz`` (zipimport), else ``"wheel"``
    (which covers editable/sdist installs too — the label only ever surfaces as a
    ``(zipapp)`` suffix, never as a "(wheel)" claim)."""
    import zipimport

    import cage
    loader = getattr(getattr(cage, "__spec__", None), "loader", None) \
        or getattr(cage, "__loader__", None)
    return "zipapp" if isinstance(loader, zipimport.zipimporter) else "wheel"


def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))


def claude_project_slug(project: Path) -> str:
    """The `~/.claude/projects/<slug>` dir name Claude Code derives from a repo path:
    the absolute path with every non-alphanumeric char replaced by ``-`` (verified
    empirically against `~/.claude/projects/`)."""
    return re.sub(r"[^a-zA-Z0-9]", "-", str(project.resolve()))


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


def copilot_home() -> Path:
    """Copilot CLI home (`$COPILOT_HOME` or ~/.copilot). Holds `session-state/<id>/
    events.jsonl` (the usage log) and `hooks/` (the lifecycle hook config)."""
    return Path(os.environ.get("COPILOT_HOME", Path.home() / ".copilot"))


def _first_existing(candidates: list[Path]) -> Path:
    """The first candidate that exists on disk, else the first candidate (the
    platform-preferred default — a missing dir is a normal `_scan` no-op, and
    `cage doctor --paths` reports every candidate with a why-line)."""
    return next((c for c in candidates if c.exists()), candidates[0])


def vscode_user_candidates() -> list[Path]:
    """Every VS Code user-dir location cage will consider, in probe order:
    ``CAGE_VSCODE_USER`` override → macOS (field-validated) → Linux → Windows
    ``%APPDATA%\\Code\\User`` (the documented VS Code location; CI-tested)."""
    env = os.environ.get("CAGE_VSCODE_USER")
    if env:
        return [Path(env)]
    cands = [Path.home() / "Library" / "Application Support" / "Code" / "User",
             Path.home() / ".config" / "Code" / "User"]
    appdata = os.environ.get("APPDATA")
    if appdata:
        cands.append(Path(appdata) / "Code" / "User")
    return cands


def vscode_user_dir() -> Path:
    """VS Code user dir (Copilot chat-session store lives under it). Override
    CAGE_VSCODE_USER; else the first existing of `vscode_user_candidates()`."""
    return _first_existing(vscode_user_candidates())


def kiro_home() -> Path:
    return Path(os.environ.get("KIRO_HOME", Path.home() / ".kiro"))


def kiro_data_candidates() -> list[Path]:
    """Kiro user-data (`kiro.kiroagent` globalStorage) candidates, in probe order:
    ``KIRO_DATA_DIR`` override → macOS (field-validated) → Linux → Windows
    ``%APPDATA%\\Kiro\\User\\globalStorage\\kiro.kiroagent`` — **UNVERIFIED-LAYOUT**:
    inferred from Kiro being VS Code-family (VS Code uses %APPDATA%/<app>/User),
    not yet pinned against a real Windows Kiro install; the probe report carries
    the same label so a Windows user knows to confirm it."""
    env = os.environ.get("KIRO_DATA_DIR")
    if env:
        return [Path(env)]
    tail = Path("User") / "globalStorage" / "kiro.kiroagent"
    cands = [Path.home() / "Library" / "Application Support" / "Kiro" / tail,
             Path.home() / ".config" / "Kiro" / tail]
    appdata = os.environ.get("APPDATA")
    if appdata:
        cands.append(Path(appdata) / "Kiro" / tail)
    return cands


def kiro_token_log() -> Path:
    """Kiro's per-call usage log (`kiro.kiroagent/dev_data/tokens_generated.jsonl`):
    one JSON object per LLM call, `{model, provider, promptTokens, generatedTokens}`.
    Coarse — Kiro reports prompt tokens reliably, output tokens often 0. Override the
    containing user-data dir with KIRO_DATA_DIR (the rest of the path is appended)."""
    return _first_existing(kiro_data_candidates()) / "dev_data" / "tokens_generated.jsonl"


def _builtin_log_sources(agent: str) -> list[tuple[Path, str]]:
    """The hard-coded ``(source, glob)`` candidate log locations per agent — one list
    per agent so a new location (like Copilot's VS Code chat-session store) is added
    exactly once. For claude/codex/copilot the source is a directory + glob; for kiro
    it is the token log file itself (glob ``*`` — `_scan` treats a file source as
    itself). The policy-aware, provenance-tagged form is :func:`resolve_log_sources`."""
    if agent == "claude":
        return [(claude_home() / "projects", "**/*.jsonl")]
    if agent == "codex":
        return [(codex_home() / "sessions", "**/rollout-*.jsonl")]
    if agent == "copilot":
        return [(copilot_home() / "session-state", "*/events.jsonl"),
                (vscode_user_dir() / "workspaceStorage", "*/chatSessions/*.jsonl")]
    if agent == "kiro":
        return [(kiro_token_log(), "*")]
    return []


# ── configurable import paths: the `[sources]` policy table (plan Phase 4) ──────
# A user can add (or replace) the log locations `cage import` probes — one or more
# paths per built-in agent, plus *custom tools* that reuse a declared parser format.
# Resolution happens in ONE place (:func:`resolve_log_sources`); the import sweep and
# `cage doctor --paths` both consume its provenance-tagged form. Additive: no
# `[sources]` ⇒ the built-in registry byte-for-byte, so capture is unchanged for
# everyone who doesn't use it (docs/sources.md).

class LogSource(NamedTuple):
    """One candidate log location, tagged with where it came from. ``provenance`` is
    ``built-in`` (the hard-coded registry) · ``env`` (a built-in home an env override
    redirected, e.g. ``CLAUDE_CONFIG_DIR``) · ``policy`` (a ``[sources]`` addition).
    ``agent`` is the row stamp — a built-in agent name, or a custom tool's name;
    ``fmt`` is the parser format ∈ ``agents.SURFACES``. ``raw`` is the original
    policy string before ``~``/env expansion (``str(path)`` for built-ins) — the
    portability check reads it to tell a machine-absolute path from a ``~``/``$VAR``
    one."""
    path: Path
    glob: str
    provenance: str
    agent: str
    fmt: str
    raw: str


class SourcesResolution(NamedTuple):
    """The whole resolved picture: every ``sources`` to scan, any ``problems`` (bad
    entries — skipped, never raised: the sweep is fail-open), and the ``disabled``
    agents (a ``replace = true`` table with empty ``paths`` — capture deliberately
    silenced, shown as such in doctor, handoff §10)."""
    sources: list  # list[LogSource]
    problems: list  # list[str]
    disabled: list  # agent names disabled by replace+empty


# One canonical glob per parser format for a *policy-declared* directory (a built-in
# copilot has two globs; a policy path uses the dominant CLI form). A file source is
# taken directly (`_scan` ignores the glob for a file).
_FORMAT_GLOB = {"claude": "**/*.jsonl", "codex": "**/rollout-*.jsonl",
                "copilot": "*/events.jsonl", "kiro": "*"}
# Per-agent home env overrides — a built-in candidate is tagged ``env`` when any is set.
_AGENT_ENV = {"claude": ("CLAUDE_CONFIG_DIR",), "codex": ("CODEX_HOME",),
              "copilot": ("COPILOT_HOME", "CAGE_VSCODE_USER"),
              "kiro": ("KIRO_HOME", "KIRO_DATA_DIR")}
_GLOB_CHARS = frozenset("*?[")


def _agent_env_set(agent: str) -> bool:
    return any(os.environ.get(v) for v in _AGENT_ENV.get(agent, ()))


def _expand_source(s: str) -> str:
    """``~`` + ``$VAR`` expansion for a policy path (local filesystem only — no glob,
    no remote). Left as-is when not a string caller (validated upstream)."""
    return os.path.expandvars(os.path.expanduser(s))


def resolve_log_sources(pol: dict | None = None) -> SourcesResolution:
    """THE resolution point for import locations (plan Phase 4). Returns the
    provenance-tagged candidate list the import sweep and `cage doctor --paths` both
    consume — no second resolver anywhere.

    Precedence per built-in agent: **env override > policy `[sources]` > built-in**.
    A ``[sources.<agent>] paths = [...]`` *adds* candidates (tagged ``policy``);
    ``replace = true`` drops that agent's built-ins first (empty ``paths`` then =
    disabled). A policy path equal to a built-in path is deduped to the built-in tag.
    A ``[sources.<name>]`` whose ``<name>`` is not one of the four agents is a custom
    tool: it must declare ``format = "claude|codex|copilot|kiro"`` (the parser to
    reuse) and its rows stamp ``agent = <name>``. ``~``/``$VAR`` expand; a glob-shaped
    entry is rejected into ``problems`` (never raised — the sweep stays fail-open).

    Two schema shapes per key, branched on the parsed TOML type: a ``dict``
    (``[sources.<x>]``, the legacy table — ``paths`` + ``replace`` + an optional
    table-level ``glob`` applied to every path) or a ``list``
    (``[[sources.<x>]]``, an array-of-tables — each entry ``{path, glob?}``, additive,
    no ``replace``). An absent ``glob`` ⇒ today's ``_FORMAT_GLOB[fmt]``; an empty
    ``glob = ""`` ⇒ a problem (never a silent fallback). Fully additive: an
    empty/absent ``[sources]`` returns exactly the built-in registry."""
    from cage import agents  # lazy: agents imports paths (avoid the cycle)
    surfaces = agents.SURFACES
    src_tables = (pol or {}).get("sources", {}) if isinstance(pol, dict) else {}

    sources: list[LogSource] = []
    problems: list[str] = []
    disabled: list[str] = []

    def _resolve_glob(key: str, fmt: str, glob) -> str | None:
        """The glob for one entry: absent ⇒ the format default; a set-but-empty (or
        non-string) value ⇒ a problem (``None`` return, entry skipped) — an empty
        ``glob = ""`` is an error, never a silent ``_FORMAT_GLOB`` fallback (§8)."""
        if glob is None:
            return _FORMAT_GLOB[fmt]
        if not isinstance(glob, str) or not glob:
            problems.append(f"[sources.{key}] glob must be a non-empty string — drop "
                            f"the key to use the default {fmt} pattern {_FORMAT_GLOB[fmt]!r}")
            return None
        return glob

    def _emit(key: str, raw, glob, fmt: str, seen: set) -> None:
        """Validate + append one policy source (path + resolved glob). A glob char in
        the ``path`` is rejected with the fix (put it in ``glob =``); a bad glob is
        rejected; a ``(path, glob)`` already seen is deduped (keeps the earlier —
        built-in — tag, §8)."""
        if not isinstance(raw, str) or not raw:
            problems.append(f"[sources.{key}] each source needs a non-empty string `path`")
            return
        if _GLOB_CHARS & set(raw):
            problems.append(f"[sources.{key}] path {raw!r} contains a glob character "
                            "(*?[) — list only concrete files or directories and put "
                            "the pattern in `glob = `")
            return
        g = _resolve_glob(key, fmt, glob)
        if g is None:
            return
        p = Path(_expand_source(raw))
        if (p, g) in seen:  # policy path == a built-in path → keep the built-in tag (§8)
            return
        seen.add((p, g))
        sources.append(LogSource(p, g, "policy", key, fmt, raw))

    def _dict_paths(key: str, table: dict, fmt: str) -> None:
        raw_paths = table.get("paths", [])
        if not isinstance(raw_paths, list) or any(not isinstance(p, str) for p in raw_paths):
            problems.append(f"[sources.{key}] paths must be a list of strings")
            return
        table_glob = table.get("glob")  # optional; one glob for every path in the table
        seen = {(s.path, s.glob) for s in sources if s.agent == key}
        for raw in raw_paths:
            _emit(key, raw, table_glob, fmt, seen)

    def _list_paths(key: str, entries: list, default_fmt: str | None) -> None:
        """The ``[[sources.<x>]]`` array-of-tables form — each entry ``{path, glob?}``.
        A built-in agent's format is implicit (``default_fmt``); a custom tool has no
        table level, so each entry declares its own ``format``."""
        seen = {(s.path, s.glob) for s in sources if s.agent == key}
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                problems.append(f"[[sources.{key}]] entry #{i + 1} must be a table "
                                "(path = \"…\", optional glob = \"…\")")
                continue
            fmt = default_fmt
            if fmt is None:  # custom tool: the format lives on each entry
                fmt = entry.get("format")
                if fmt not in _FORMAT_GLOB:
                    problems.append(f"[[sources.{key}]] entry #{i + 1} is a custom tool "
                                    "— each entry needs format = \"claude|codex|copilot|kiro\"")
                    continue
            elif entry.get("format") not in (None, default_fmt):
                problems.append(f"[[sources.{key}]] format is implicit for the {key} "
                                "agent — drop the `format` key")
                continue
            _emit(key, entry.get("path"), entry.get("glob"), fmt, seen)

    # Built-in agents first, in SURFACES order: built-in/env candidates, then adds.
    for agent in surfaces:
        table = src_tables.get(agent)
        replace = bool(isinstance(table, dict) and table.get("replace"))
        if isinstance(table, dict) and table.get("format") not in (None, agent):
            problems.append(f"[sources.{agent}] is the {agent} agent table — its "
                            "format is implicit; drop the `format` key (a custom tool "
                            "uses a different name)")
        if not replace:
            prov = "env" if _agent_env_set(agent) else "built-in"
            for path, glob in _builtin_log_sources(agent):
                sources.append(LogSource(path, glob, prov, agent, agent, str(path)))
        if isinstance(table, dict):
            _dict_paths(agent, table, agent)
            if replace and not any(s.agent == agent for s in sources):
                disabled.append(agent)
        elif isinstance(table, list):
            _list_paths(agent, table, agent)

    # Custom tools: any `[sources.<name>]` whose name is not one of the four agents.
    for name in sorted(k for k in src_tables if k not in surfaces):
        table = src_tables[name]
        if isinstance(table, list):
            _list_paths(name, table, None)  # array-of-tables custom tool: format per entry
            continue
        if not isinstance(table, dict):
            problems.append(f"[sources.{name}] must be a table")
            continue
        fmt = table.get("format")
        if fmt not in _FORMAT_GLOB:
            problems.append(f"[sources.{name}] is a custom tool — it needs "
                            "format = \"claude|codex|copilot|kiro\" (the parser to reuse)")
            continue
        _dict_paths(name, table, fmt)

    return SourcesResolution(sources, problems, disabled)


def agent_log_sources(agent: str, pol: dict | None = None) -> list[LogSource]:
    """The candidate log locations for one built-in agent — the built-in registry plus
    any `[sources.<agent>]` policy additions (see :func:`resolve_log_sources`). A thin
    view over the single resolver so the import sweep and doctor share one resolution.
    Byte-identical to the legacy built-in list when ``pol`` carries no ``[sources]``."""
    return [s for s in resolve_log_sources(pol).sources if s.agent == agent]


def custom_tool_sources(pol: dict | None = None) -> list[LogSource]:
    """The `[sources.<name>]` custom-tool sources (name ∉ the four agents) — each
    reuses a declared parser ``fmt`` and stamps ``agent = <name>`` on imported rows."""
    from cage import agents
    return [s for s in resolve_log_sources(pol).sources if s.agent not in agents.SURFACES]


# ── build-time descriptor for the generated `[sources]` comment block (docgen) ──
# `tools/docgen --target policy` renders an inert, ~-relative `[sources]` block into
# the bundled policy.toml from :func:`builtin_source_docs`. It is deliberately ENV-
# and MACHINE-INDEPENDENT: it reads no environment and never calls ``Path.home()`` /
# ``_first_existing`` — the values `_builtin_log_sources` returns bake the current
# machine's home, env overrides and on-disk probing into an *absolute* path that
# differs per developer/OS, so ``str(path)``-ing them would make docgen output
# machine-specific and CI ``--check`` fail (handoff §8, the single most likely break).
# These path strings are the canonical ~-relative defaults; the *glob* and the
# per-agent source count come from `_builtin_log_sources` so a new/renamed built-in
# source can't ship without the block drifting (docgen `--check` gates it).
_SOURCE_DOC_PATHS = {
    "claude": [("~/.claude/projects",
                "every session transcript under the tree, recursively")],
    "codex": [("~/.codex/sessions",
               "rollout logs under the tree, recursively")],
    "copilot": [
        ("~/.copilot/session-state",
         "Copilot CLI usage events (one dir per session)"),
        ("~/Library/Application Support/Code/User/workspaceStorage",
         "VS Code Copilot chat sessions (macOS location shown; other OS below)"),
    ],
    "kiro": [
        ("~/Library/Application Support/Kiro/User/globalStorage/kiro.kiroagent"
         "/dev_data/tokens_generated.jsonl",
         "per-call token log — a FILE source, so the glob is ignored (macOS shown)"),
    ],
}
_SOURCE_DOC_OTHER_OS = {
    "copilot": ("Linux VS Code:   ~/.config/Code/User/workspaceStorage",
                "Windows VS Code: %APPDATA%\\Code\\User\\workspaceStorage"),
    "kiro": ("Linux:   ~/.config/Kiro/User/globalStorage/kiro.kiroagent"
             "/dev_data/tokens_generated.jsonl",
             "Windows: %APPDATA%\\Kiro\\User\\globalStorage\\kiro.kiroagent"
             "\\...\\tokens_generated.jsonl  (UNVERIFIED-LAYOUT — inferred from VS "
             "Code-family, not pinned on a real Windows Kiro)"),
}


def builtin_source_docs() -> list[dict]:
    """Env-independent, ~-relative description of the built-in log sources for the
    generated `[sources]` comment block (docgen — see the note above; never imported
    at runtime). One dict per agent in ``SURFACES`` order: ``env`` (the home-redirect
    vars from ``_AGENT_ENV``), ``sources`` (a list of ``(path, glob, meaning)`` — the
    ``glob`` pulled live from :func:`_builtin_log_sources` so the block drifts when a
    source is added/changed) and ``other_os`` (non-primary OS locations). Deterministic:
    reads no environment, never resolves ``Path.home()``. Raises loudly if the doc
    descriptor and the code registry disagree on a source count, so a new built-in
    source forces a descriptor update + regeneration."""
    from cage import agents  # lazy: agents imports paths (avoid the cycle)
    out: list[dict] = []
    for agent in agents.SURFACES:
        docs = _SOURCE_DOC_PATHS[agent]
        builtin = _builtin_log_sources(agent)  # only the globs are read (env-independent)
        if len(docs) != len(builtin):
            raise SystemExit(
                f"paths.builtin_source_docs: {agent} has {len(builtin)} built-in "
                f"source(s) but _SOURCE_DOC_PATHS lists {len(docs)} — update the "
                "descriptor in cage/paths.py, then regenerate the [sources] block "
                "(`python -m tools.docgen --target policy`)")
        srcs = [(path, glob, meaning)
                for (path, meaning), (_bp, glob) in zip(docs, builtin)]
        out.append({"agent": agent, "env": _AGENT_ENV.get(agent, ()),
                    "sources": srcs, "other_os": _SOURCE_DOC_OTHER_OS.get(agent, ())})
    return out


class Footprint:
    """The per-project ``.cage/`` layout (plan §3).

    The ledger carries token *counts*, never prompt bodies — PII-safe by
    construction (plan §10). For Orff, point ``CAGE_LEDGER`` at elgar so even the
    counts live in the private store.
    """

    def __init__(self, root: Path, base: Path | None = None):
        self.root = root
        # ``CAGE_BASE`` (set by the ``--ledger`` flag) re-bases the whole footprint —
        # ledger, state and policy all move together to one active sink (plan §3.7).
        # An explicit ``base`` arg wins (callers that target a specific store); else the
        # env override; else the legacy per-project ``<root>/.cage``.
        override = os.environ.get("CAGE_BASE")
        self.base = base or (Path(override).expanduser() if override else root / ".cage")

    @property
    def ledger(self) -> Path:
        return Path(os.environ.get("CAGE_LEDGER", self.base / "ledger"))

    @property
    def calls(self) -> Path:
        return self.ledger / "calls.jsonl"

    @property
    def receipts(self) -> Path:
        return self.ledger / "receipts.jsonl"

    @property
    def tasks(self) -> Path:
        return self.ledger / "tasks.jsonl"

    @property
    def provenance(self) -> Path:
        return self.ledger / "provenance.jsonl"

    def shard(self, kind: str, ts: str) -> Path:
        """Month-partition path for ``kind`` (``calls``/``receipts``/``tasks``) derived
        from a row's own ``ts`` — ``calls-2026-06.jsonl`` (plan §3.6.1). Determinism:
        the name comes from the row, never a write-time clock. A missing/unparseable
        ``ts`` falls back to the legacy unpartitioned file so a malformed row still lands
        somewhere readable. ``provenance`` is intentionally never partitioned (buffer)."""
        month = ts[:7] if (ts and len(ts) >= 7 and ts[4] == "-") else ""
        return self.ledger / (f"{kind}-{month}.jsonl" if month else f"{kind}.jsonl")

    def shards(self, kind: str) -> list[Path]:
        """Every readable shard for ``kind``: the legacy unpartitioned file first
        (oldest), then dated month shards in ascending — i.e. chronological — order, so
        a concatenated read keeps oldest→newest (``_latest_task`` stays correct). Same
        rows ⇒ same set ⇒ byte-identical reads. Only existing files are returned."""
        base = self.ledger
        out: list[Path] = []
        legacy = base / f"{kind}.jsonl"
        if legacy.exists():
            out.append(legacy)
        out.extend(sorted(base.glob(f"{kind}-*.jsonl")))
        return out

    @property
    def study(self) -> Path:
        """Fleet-study phase markers (`cage study start/stop`, plan §4.9) — a small
        append-only jsonl beside the ledger files (it travels inside `cage data export
        --study` bundles). Unpartitioned by design, like `provenance.jsonl`: a study
        is weeks, not years."""
        return self.ledger / "study.jsonl"

    @property
    def policy(self) -> Path:
        return self.base / "policy.toml"

    @property
    def out(self) -> Path:
        return self.base / "out"

    @property
    def state(self) -> Path:
        return self.base / "state"

    @property
    def cursors(self) -> Path:
        """Per-agent incremental-import high-water cursors (plan §3.7). Maps each
        scanned source file to its last-seen ``(size, mtime)`` so a re-import skips
        unchanged files instead of re-parsing the whole world (the ledger is 22k+ rows);
        `hooks.append_new`'s id-dedupe stays the correctness backstop. Machine-local
        state, never a derived view — never read by any table."""
        return self.state / "cursors.json"

    @property
    def limits(self) -> Path:
        """Latest-only provider quota snapshot (`cage/limits.py`) — Codex rate-limit
        windows keyed agent→window_minutes. **Overwrite, never appended; machine-local,
        never synced to refs/notes.** Quota is a decaying live gauge, not durable ledger
        truth, so it is deliberately *not* a ledger substrate (plan §3.8)."""
        return self.state / "limits.json"

    @property
    def debug_log(self) -> Path:
        """Capture-path debug log (`cage/debuglog.py`) — metadata-only, written only
        when `CAGE_DEBUG=1` / `[debug] enabled`. Override the path with `CAGE_DEBUG_LOG`."""
        return Path(os.environ.get("CAGE_DEBUG_LOG", self.state / "debug.log"))

    @property
    def hooks_seen(self) -> Path:
        """Per-(agent,event) hook heartbeat — append-only, last-write-wins on read.
        Gated by the same debug switch, so it is absent unless debug is enabled."""
        return self.state / "hooks-seen.jsonl"

    def pending_edits(self, session_id: str) -> Path:
        """Per-session buffer of uncommitted `PostToolUse` edits (plan §3.5) — a
        `post-commit` hook resolves these to a real sha and clears the file."""
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (session_id or "nosession"))
        return self.state / f"pending-{safe}.jsonl"
