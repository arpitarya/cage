"""Path resolution for the per-project `.cage/` footprint + agent homes (ADR-LAWS)."""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import NamedTuple


def cage_bin() -> str:
    """Absolute path to the `cage` executable, for the commands cage writes into agent
    hook files. **GUI-launched agents** (Kiro IDE, the Copilot extension) run hooks
    with a minimal PATH that omits `~/.local/bin`, so a bare `cage` in a hook
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
    committed shim** (`cage-run` in any host's reference form, ADR-GRAPHIFY), or **via
    the interpreter** (`python3 -m cage …` / `py -3 -m cage …` — python-launcher
    wiring mode, work/restricted-environments.md); else None (a foreign hook —
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


# Kiro's self-locating one-liner (`runshim.selflocating_command`) doesn't
# start with an executable name — it resolves the git root first, so the shim path
# sits mid-command. The one-liner names the shim TWICE (`[ -x "…cage-run" ]` then
# `exec "…cage-run" <tail>`), so the leading `.*` is deliberately greedy: it anchors
# on the LAST reference, the one that actually runs. `; exit 0` is trimmed after.
_SELFLOCATING = re.compile(r'.*cage-run(?:\.cmd)?["\']?\s+(.+)$')


def _selflocating_tail(command: str) -> str | None:
    """The subcommand tail of the self-locating shim one-liner, else None."""
    m = _SELFLOCATING.search(command or "")
    if not m:
        return None
    return m.group(1).split(";")[0].strip()


def cage_tail_any(command: str) -> str | None:
    """The subcommand tail for **any** cage command shape — the binary/shim/interpreter
    forms `cage_command_tail` handles, *plus* the self-locating one-liner. Detection
    superset only: `cage_command_tail` stays deliberately narrower because the migration
    paths rewrite through it, and rewriting a self-locating one-liner into a plain shim
    reference would throw away its git-root resolution."""
    tail = cage_command_tail(command)
    return tail if tail is not None else _selflocating_tail(command)


def cage_verb_path(command: str) -> tuple[str, ...]:
    """The verb tokens of a cage command — `()` for a foreign (non-cage) command.

    ``cage insights chats --csv`` → ``("insights", "chats")``; ``cage import --agent
    claude`` → ``("import",)``. Stops at the first flag, and keeps at most two levels
    (cage's parser is two deep: a group verb plus its subcommand)."""
    tail = cage_tail_any(command)
    if tail is None:
        return ()
    verbs: list[str] = []
    for token in tail.split():
        if token.startswith("-") or len(verbs) == 2:
            break
        verbs.append(token)
    return tuple(verbs)


def is_cage_import_command(command: str) -> bool:
    """True if ``command`` is a cage ``import …`` hook command (any agent/flags), in
    binary, shim, or self-locating one-liner form. Lets the wiring collapse a
    superseded per-agent import (e.g. `cage import --agent claude`) into the current
    per-agent import on re-setup, instead of leaving both.

    Deliberately **exact** on the verb (not the old `" import"` substring): a dead
    hyphenated `import-<agent>` is no longer caught here but by
    `wiringscan.is_dead_cage_command`, and the wiring filters take the union of the
    two. Same commands healed, non-accidental reason — see tests/test_wiringscan.py."""
    return cage_verb_path(command)[:1] == ("import",)


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
    ADR-LAWS Law 2) is deliberately *not* a project: it is the fallback capture sink,
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
    precedence (ADR-LAWS Law 2): ``--ledger``/``CAGE_BASE`` → nearest project ``.cage/`` from
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


def canonical_ledger(start: Path | None = None, *, pol: dict | None = None) -> Path:
    """THE one ledger resolver push *and* pull both call (capture-architecture §3.1).

    Byte-for-byte :func:`resolve_root` — the same precedence (``--ledger``/``CAGE_BASE``
    → nearest project ``.cage/`` from cwd → global ``~/.cage``) — but named as the single
    convergence point so no push path calls ``resolve_root`` directly, and every
    resolution logs *which* ledger it picked and *why* under ``CAGE_DEBUG``. That trace is
    the exact diagnostic for the stranded-saving class this design fights (a graphify
    receipt and a later read resolving different ledgers). Fail-open: the debug
    log is best-effort and never perturbs resolution."""
    root = resolve_root(start)
    try:
        from cage import debuglog
        debuglog.event(root, pol=pol, event="ledger-resolve", resolved_root=str(root),
                       source=active_ledger_source(start),
                       route_key=routing_key(root))
    except Exception:  # noqa: BLE001 — resolution must never depend on its own tracing
        pass
    return root


def kiro_ledger(root: Path) -> Path:
    """THE sink for kiro **IDE** rows ([ADR 0006](work/archive/adr/0006-kiro-rows-are-machine-facts-not-project-facts.md)).

    Kiro's IDE log (`dev_data/tokens_generated.jsonl`) is ONE global append-only file
    carrying no project, no session and no timestamp, so every ledger that imports it
    reads the same turns — a per-project kiro cost was never a fact. Kiro-IDE rows
    therefore belong to the **machine**: they land in the global ledger (`~/.cage`), so
    one copy exists per machine and double-counting is impossible by construction rather
    than by warning.

    The ONE exception is an explicit ``--ledger``/``CAGE_BASE`` override: the user named a
    sink, and cage never routes around an explicit instruction (cage-lab's isolation
    depends on it). This is the only place the rule lives — callers ask
    :func:`kiro_routed`, they never re-derive it.

    Scope: the **IDE** store only. Kiro's *CLI* store (`conversations_v2`) is keyed by cwd
    and carries a real conversation id and timestamp, so it is genuinely
    project-attributable and gets the opposite treatment (scoped by cwd, `project`
    stamped) — see `transcript.parse_kiro_cli_credits`."""
    if os.environ.get("CAGE_BASE"):
        return root  # explicit override wins (ADR 0006, "Decision")
    return global_home()


def kiro_routed(root: Path) -> Path | None:
    """The kiro-IDE sink when it **differs** from ``root``'s ledger, else ``None`` (kiro is
    just part of the normal sweep). The one predicate the import sweep branches on, so the
    "does kiro route elsewhere?" question is answered in exactly one place.

    Compared on the resolved **ledger dir**, not the root: that collapses both overrides
    for free — ``CAGE_BASE`` re-bases the whole footprint and ``CAGE_LEDGER`` re-points the
    ledger dir alone, and under either the two sinks are the same files, so there is
    nothing to route and no second lock to take (which is also what keeps a same-process
    double-lock impossible)."""
    sink = kiro_ledger(root)
    if Footprint(sink).ledger.resolve() == Footprint(root).ledger.resolve():
        return None
    return sink


def kiro_cli_workspace(root: Path) -> str:
    """The cwd **tree** that scopes kiro *CLI* credits for a sweep into ``root``, or ``""``
    for "read every conversation on the machine".

    The exact opposite of :func:`kiro_ledger`, on purpose (ADR 0006 *Scope*). Kiro's CLI
    store keys every conversation by the cwd it ran in and carries a real conversation id
    and timestamp, so it **is** project-attributable — routing it to the machine ledger
    would destroy attribution the source genuinely supports. Its double-count came from
    the opposite defect: the importer read with no workspace filter at all, so every
    ledger pulled every conversation on the machine.

    Precedence: a project root (the tree the conversations belong to) → an explicitly
    named sink's own tree (``--ledger``/``CAGE_BASE``: you ran the import from here, so
    scope to here — this is what keeps cage-lab's ledger isolated) → ``""`` for the
    machine ledger, whose job **is** the whole machine.

    The tree, not the directory: a conversation started in ``repo/sub`` is still that
    project's work (`transcript.parse_kiro_cli_credits` prefix-matches)."""
    proj = find_project_root(root)
    if proj is not None:
        return str(proj.resolve())
    if os.environ.get("CAGE_BASE"):
        return str(Path(root).resolve())
    return ""


def routing_key(root: Path) -> str:
    """A stable, **non-PII** project routing key: a hash of the resolved ledger-root path,
    **not** the basename (capture-architecture §9.6 Q1). Stamped on pushed receipts so a
    read can *reclaim* a stray graphify/fux saving by **exact key match only** — never a
    blind union that would over-attribute (two repos named ``api`` share a basename but
    never a full path).

    OS-stable by construction: the path is resolved to absolute, back/forward separators
    are folded to ``/``, and case is folded, so the same logical ledger yields the same
    key whether push and read run from Windows or POSIX shells on one machine. It is a
    one-way hash — the path itself (a PII surface) never travels in the row, only its
    digest — and is **never part of any id**. Empty string is never returned; a global
    ledger hashes its own resolved path, distinct from every project key."""
    import hashlib
    norm = str(Path(root).resolve()).replace("\\", "/").casefold()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def active_ledger_source(start: Path | None = None) -> str:
    """Which precedence tier the active ledger came from — for ``cage doctor`` to print
    *which* sink is live when both a project and the global ledger exist."""
    if os.environ.get("CAGE_BASE"):
        return "override (--ledger/CAGE_BASE)"
    if find_project_root(start) is not None:
        return "project (.cage/)"
    return "global (~/.cage)"


# ── the graphify interceptor twins ──────────────────────────────────────────────
#
# One behaviour contract (docs/adr/0007_graphify.md), two implementations: the
# extensionless POSIX `graphify` and the Windows `graphify.cmd`. The names live here,
# with the rest of "where things live", so the writer (`adoptcmd`) and every read
# surface (`pathshim`, `wiringscan`, `doctorcmd`) share one enumeration — a read
# surface that knew about only one twin is precisely how a silently-unmetered
# interceptor stays invisible (F1).

#: The savings tools cage itself writes, for documentation and tests. **Deliberately NOT
#: the enumeration the reader walks** — `savings_shards` globs and excludes
#: `_RESERVED_LEDGER_DIRS` instead, so a THIRD-PARTY tool (fux's zero-dep shim is the
#: worked example, and any `[sources.<name>]` tool could be another) files rows that are
#: read back without cage knowing its name in advance. An allowlist here would make every
#: unknown tool write-only — rows on disk that no view ever returns, with nothing failing.
SAVINGS_TOOLS = ("graphify", "fux", "compress", "responsecache")

#: Directory names under `ledger/` that a savings tool may NOT take (P4 / decision 10.5).
#:
#: After P1 and P4, `ledger/` is a **flat namespace shared by agents, consumers and
#: tools**. A custom `[sources.<name>]` tool — or a future agent — named the same as a
#: savings tool would land two different row kinds in one directory, and every reader of
#: either would silently see the other's rows.
#:
#: **Flat + reserved was chosen over `ledger/tools/<tool>/`** because it keeps the
#: one-dir-per-producer shape the whole program is for, and it makes the collision
#: *impossible* rather than unlikely — at the cost of one enumeration, checked at write
#: time. Nesting tools one level deeper would have re-created exactly the asymmetry P4
#: removes.
_RESERVED_LEDGER_DIRS = frozenset({
    # the three agents (kept as literals, not imported: `agents` imports `paths`, and a
    # cycle here would break the write path this guard protects)
    "claude", "copilot", "kiro",
    # non-agent producers
    "consumer", "provenance", "savings",
    # non-directory ledger kinds, so a tool can never shadow a shard-name prefix
    "calls", "credits", "receipts", "tasks", "study", "imports",
})


def reserve_tool_name(tool: str) -> str:
    """Return ``tool`` if it may be a directory under `ledger/`, else raise.

    **Validated at WRITE time, and refused with a named error** rather than silently
    renamed or suffixed. A collision is a design mistake in whatever declared the name; a
    write path that quietly disambiguates would bury it, and the rows would keep landing
    somewhere plausible-looking forever.

    Raises `ValueError` — and `savings.record` is fail-open, so a refused write is traced
    under `CAGE_DEBUG` and returns ``""``. It never propagates into the tool being metered:
    a bad *name* must not break the *tool*."""
    name = str(tool or "")
    if name in _RESERVED_LEDGER_DIRS:
        raise ValueError(
            f"savings tool {name!r} collides with a reserved ledger directory "
            f"({', '.join(sorted(_RESERVED_LEDGER_DIRS))}) — two row kinds would share "
            f"one directory. Rename the tool.")
    return name


GRAPHIFY_SHIMS = ("graphify", "graphify.cmd")


def graphify_shim_name() -> str:
    """The twin this OS actually resolves from a bare `graphify`. Windows resolves only
    through PATHEXT, which has no extensionless entry — so there, only the `.cmd` can
    ever run."""
    return "graphify.cmd" if os.name == "nt" else "graphify"


def graphify_shims(root: Path) -> list[Path]:
    """Both twins under `<root>/bin`, **platform-primary first** — so a caller that
    reports just one reports the one that matters."""
    order = sorted(GRAPHIFY_SHIMS, key=lambda n: n != graphify_shim_name())
    return [root / "bin" / n for n in order]


def bundled_data():
    """Seed data shipped with the cage package (default cage.toml/prices.toml,
    the graphify shim twin pair, assets). No skill/prompt/steering asset ships —
    that machinery went with the hook machinery in v0.36 (`tests/test_floor.py`
    pins its absence).

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


def kiro_cli_db_candidates() -> list[Path]:
    """Kiro **CLI** SQLite store (`kiro-cli/data.sqlite3`) candidates, in probe order:
    ``CAGE_KIRO_CLI_DB`` override → macOS → Linux → Windows ``%APPDATA%`` (the last two
    **UNVERIFIED-LAYOUT**, inferred from the macOS layout — the CLI store is distinct
    from the IDE `kiro.kiroagent` globalStorage). Distinct from `kiro_data_candidates`
    (the IDE token log); this is the CLI's per-directory conversation DB."""
    env = os.environ.get("CAGE_KIRO_CLI_DB")
    if env:
        return [Path(env)]
    name = Path("kiro-cli") / "data.sqlite3"
    cands = [Path.home() / "Library" / "Application Support" / name,
             Path.home() / ".local" / "share" / name]
    appdata = os.environ.get("APPDATA")
    if appdata:
        cands.append(Path(appdata) / name)
    return cands


def kiro_cli_db() -> Path:
    """The first existing Kiro CLI SQLite store, else the top candidate (so a doctor probe
    still names a concrete path). Read **read-only** by `transcript.parse_kiro_cli_credits`."""
    return _first_existing(kiro_cli_db_candidates())


def kiro_token_log() -> Path:
    """Kiro's per-call usage log (`kiro.kiroagent/dev_data/tokens_generated.jsonl`):
    one JSON object per LLM call, `{model, provider, promptTokens, generatedTokens}`.
    Coarse — Kiro reports prompt tokens reliably, output tokens often 0. Override the
    containing user-data dir with KIRO_DATA_DIR (the rest of the path is appended)."""
    return _first_existing(kiro_data_candidates()) / "dev_data" / "tokens_generated.jsonl"


def kiro_devdata_db() -> Path:
    """Kiro IDE's SQLite twin of `kiro_token_log` (KIRO-METRICS handoff §4.2):
    `kiro.kiroagent/dev_data/devdata.sqlite`, table `tokens_generated` — the SAME
    counter, plus a `timestamp` and a cursorable `id` the jsonl never carried. Same
    `KIRO_DATA_DIR` override semantics as the jsonl. **UNVERIFIED-COLUMNS**: the exact
    column list beyond `(id, tokens_prompt, tokens_generated, timestamp)` is pending
    the real-store probe (research 2026-08-13 §6) — `transcript.parse_kiro_ide_metrics`
    SELECTs only those four, explicit, so an unread extra column never breaks capture.

    Deliberately **not** added to `_builtin_log_sources`/`sources_seed` — the calls
    sweep must not start parsing a SQLite file with the jsonl parser; the kiro-metrics
    leg (`importcmd.import_kiro`) resolves this path directly, single-file, no glob."""
    return _first_existing(kiro_data_candidates()) / "dev_data" / "devdata.sqlite"


def _builtin_log_sources(agent: str) -> list[tuple[Path, str, tuple[str, ...]]]:
    """The **seed** ``(source, glob, path_globs)`` log locations per agent
    (capture-precision §3.6, Directive A). No longer a runtime fallback — `cage setup`
    freezes these into an active ``[sources]`` table via :func:`sources_seed`, and
    :func:`resolve_log_sources` reads ONLY that table. One list per agent so a new
    location is added exactly once. For claude/copilot the source is a directory + glob;
    for kiro it is the token-log file (glob ``*`` — `_scan` treats a file source as
    itself).

    Two globs, two jobs (path-globs handoff §5). ``glob`` is **anchored** to the declared
    ``path`` and drives every normal import. ``path_globs`` is **root-agnostic**
    (``**/…``) and is used ONLY when `cage import --path`/`--project` replaces the
    location with a user-provided root: an anchored pattern reused there matches nothing
    (`*/chatSessions/*.jsonl` under a `chatSessions` directory), which was the copilot
    `--path` bug. Copilot names both known store shapes explicitly rather than a blanket
    ``**/*.jsonl`` — only copilot-shaped files can match, safe by construction rather
    than by the accident of a foreign file parsing to zero rows."""
    if agent == "claude":
        return [(claude_home() / "projects", "**/*.jsonl", ("**/*.jsonl",))]
    if agent == "copilot":
        return [(copilot_home() / "session-state", "*/events.jsonl",
                 ("**/events.jsonl",)),
                (vscode_user_dir() / "workspaceStorage", "*/chatSessions/*.jsonl",
                 ("**/chatSessions/*.jsonl",)),
                # Two more chatSessions roots (research 2026-08-13 §"Deltas"/5):
                # empty-window chats and sessions transferred between windows are
                # invisible to the `workspaceStorage/*/chatSessions` glob above.
                # `no-workspace/chatSessions/` is already matched by that glob —
                # it is not a fourth tuple. Calls capture gains these chats too;
                # `importcmd._is_chat_session_file` fixes the dispatch they'd
                # otherwise mis-route into (neither sits in a `chatSessions/` dir).
                (vscode_user_dir() / "globalStorage" / "emptyWindowChatSessions", "*.jsonl",
                 ("**/emptyWindowChatSessions/*.jsonl",)),
                (vscode_user_dir() / "globalStorage" / "transferredChatSessions", "*.jsonl",
                 ("**/transferredChatSessions/*.jsonl",))]
    if agent == "kiro":
        return [(kiro_token_log(), "*", ("*",))]
    return []


def _portable(p: str) -> str:
    """Render a path home-relative (``~/…``) when it sits under ``$HOME`` — so a
    materialized ``[sources]`` table is portable across machines (same discipline as the
    committed-wiring shim). Paths outside home are left absolute."""
    home = str(Path.home())
    if p == home:
        return "~"
    if p.startswith(home + os.sep):
        return "~" + p[len(home):]
    return p


def sources_seed() -> list[dict]:
    """The default sources cage materializes into an active ``[sources]`` table (Directive
    A, capture-precision §3.6). The built-in registry is a **seed**, not a runtime
    fallback: `cage setup` freezes these into ``cage.toml`` and `resolve_log_sources`
    reads only that. Each entry: ``{name, path (portable ~), glob, path_globs, format?}``.
    Includes the Kiro-CLI SQLite credits store as a ``format="kiro-cli"`` custom source
    (§3.2) — it carries no ``path_globs`` because ``--path`` never reaches a custom tool,
    so the key's absence there is a statement, not an omission."""
    from cage import agents  # lazy: agents imports paths
    seed: list[dict] = []
    for agent in agents.SURFACES:
        for path, glob, path_globs in _builtin_log_sources(agent):
            seed.append({"name": agent, "path": _portable(str(path)), "glob": glob,
                         "path_globs": list(path_globs)})
    seed.append({"name": "kirocli", "path": _portable(str(kiro_cli_db())),
                 "glob": "*", "format": "kiro-cli"})
    return seed


SOURCES_START = "# cage:sources-start"
SOURCES_END = "# cage:sources-end"


def sources_drift(pol: dict | None = None) -> tuple[list[str], list[str]]:
    """Compare the project's declared ``[sources]`` against the built-in seed — the
    **mandatory mitigation** for Directive A's cost (capture-precision §3.6): freezing
    defaults into a user's file means a cage upgrade that adds or corrects a default path
    no longer reaches them (the silent-staleness class the dead-verb bug was). Returns
    ``(missing, stale)``: seed paths the project lacks (a new/changed default not yet
    picked up), and declared paths cage no longer ships. `cage doctor` reports both;
    `cage setup --sync-sources` refreshes. Empty/empty ⇒ in sync."""
    def _norm(name: str, path, glob) -> tuple:
        return (name, str(Path(_expand_source(str(path)))), glob or _FORMAT_GLOB.get(name, "*"))
    seed = {_norm(e["name"], e["path"], e.get("glob")) for e in sources_seed()}
    declared = {_norm(s.agent, s.path, s.glob) for s in resolve_log_sources(pol).sources}
    missing = [f"{n}: {p} ({g})" for (n, p, g) in sorted(seed - declared)]
    stale = [f"{n}: {p} ({g})" for (n, p, g) in sorted(declared - seed)]
    return missing, stale


def sources_toml(seed: list[dict] | None = None) -> str:
    """Render the active ``[sources]`` table cage materializes into ``cage.toml`` — a
    cage-managed marker block (`# cage:sources-start … end`) of ``[[sources.<name>]]``
    array-of-tables entries. `cage setup --sync-sources` regenerates ONLY this block, so
    user-added ``[[sources.<name>]]`` entries outside it are preserved."""
    seed = sources_seed() if seed is None else seed
    lines = [SOURCES_START,
             "# [sources] — the ONLY place cage looks for agent logs (Directive A, §3.6).",
             "# Materialized by `cage setup`; refresh with `cage setup --sync-sources`.",
             "# An empty/absent [sources] table captures NOTHING — by design; `cage doctor`",
             "# reports it (a silent 'no sources' would look exactly like broken capture).",
             "# `glob` is anchored to `path` (normal imports); `path_globs` is root-agnostic",
             "# and is used ONLY by `cage import --path`/`--project` (path-globs handoff §5)."]
    # A raw Windows `\` is a TOML basic-string escape (`\A`, `\U`… are invalid
    # sequences) — normalise every written path to `/` first, same as `path_globs`
    # on read (`_resolve_path_globs`); Path.glob()/pathlib accept `/` on every OS.
    slash = "\\"

    def _p(s: str) -> str:
        return s.replace(slash, "/")

    for e in seed:
        lines.append("")
        lines.append(f"[[sources.{e['name']}]]")
        lines.append(f'path = "{_p(e["path"])}"')
        if e.get("glob"):
            lines.append(f'glob = "{_p(e["glob"])}"')
        if e.get("path_globs"):
            pg = ", ".join(f'"{_p(p)}"' for p in e["path_globs"])
            lines.append(f"path_globs = [{pg}]")
        if e.get("format"):
            lines.append(f'format = "{e["format"]}"')
    lines.append(SOURCES_END)
    return "\n".join(lines) + "\n"


def materialize_sources(text: str, seed: list[dict] | None = None) -> str:
    """Return ``text`` with its cage-managed sources block replaced by (or, if absent,
    with the freshly rendered block appended after) the active table. Idempotent — the
    marker block is regenerated wholesale, so re-running produces stable bytes."""
    block = sources_toml(seed)
    start = text.find(SOURCES_START)
    if start != -1:
        end = text.find(SOURCES_END, start)
        if end != -1:
            end += len(SOURCES_END)
            # swallow a trailing newline so we don't accrete blank lines on re-sync
            tail = text[end:]
            if tail.startswith("\n"):
                tail = tail[1:]
            return text[:start] + block + tail
    sep = "" if text.endswith("\n") else "\n"
    return text + sep + "\n" + block


# ── configurable import paths: the `[sources]` policy table (plan Phase 4) ──────
# A user can add (or replace) the log locations `cage import` probes — one or more
# paths per built-in agent, plus *custom tools* that reuse a declared parser format.
# Resolution happens in ONE place (:func:`resolve_log_sources`); the import sweep and
# `cage doctor --paths` both consume its provenance-tagged form. Additive: no
# `[sources]` ⇒ the built-in registry byte-for-byte, so capture is unchanged for
# everyone who doesn't use it. Explained live by `cage query sources`.
# NB: this 'byte-for-byte fallback' wording predates Directive A — reconcile when
# CMD-SYNC lands (work/archive/v0.39-claude-md-sources-authority.proposal.md).

class LogSource(NamedTuple):
    """One candidate log location, tagged with where it came from. ``provenance`` is
    ``built-in`` (the hard-coded registry) · ``env`` (a built-in home an env override
    redirected, e.g. ``CLAUDE_CONFIG_DIR``) · ``policy`` (a ``[sources]`` addition).
    ``agent`` is the row stamp — a built-in agent name, or a custom tool's name;
    ``fmt`` is the parser format ∈ ``agents.SURFACES``. ``raw`` is the original
    policy string before ``~``/env expansion (``str(path)`` for built-ins) — the
    portability check reads it to tell a machine-absolute path from a ``~``/``$VAR``
    one. ``surface`` is the optional ``[sources]`` declaration (``cli`` | ``vscode``
    | ``ide`` | ``""``): when non-empty, `importcmd` restamps every imported row's
    ``surface`` to it (a non-IDE Kiro store, say, must not inherit the parser's
    hardcoded ``ide``); ``""`` ⇒ the parser-derived value stands, byte-identical.
    ``path_globs`` is the **root-agnostic** counterpart of ``glob`` (path-globs handoff
    §5), used only when `cage import --path`/`--project` replaces this entry's ``path``
    with a user-provided root — :func:`path_globs_for` unions an agent's entries into
    the pattern list `importcmd` scans with. Empty ⇒ ``--path`` matches nothing for this
    agent, said loudly: there is no code fallback, by design."""
    path: Path
    glob: str
    provenance: str
    agent: str
    fmt: str
    raw: str
    surface: str = ""
    path_globs: tuple = ()  # tuple[str, ...] — root-agnostic, `--path` only


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
_FORMAT_GLOB = {"claude": "**/*.jsonl",
                "copilot": "*/events.jsonl", "kiro": "*",
                # kiro-cli is a SQLite store, not jsonl — its parser
                # (`transcript.parse_kiro_cli_credits`) yields *credits* rows, not calls
                # (capture-precision §3.2–§3.4). A file source: the glob is `*`.
                "kiro-cli": "*"}
# The closed set a `[sources.<x>] surface = …` may declare — the same enum
# `schema.make_call` validates (cli/vscode/ide/""). Absent ⇒ "" ⇒ the parser's
# own value stands (no restamp), so an unset surface is byte-identical.
_SURFACE_SET = frozenset({"cli", "vscode", "ide", ""})
# Per-agent home env overrides — a built-in candidate is tagged ``env`` when any is set.
_AGENT_ENV = {"claude": ("CLAUDE_CONFIG_DIR",),
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
    A ``[sources.<name>]`` whose ``<name>`` is not one of the three agents is a custom
    tool: it must declare ``format = "claude|copilot|kiro"`` (the parser to
    reuse) and its rows stamp ``agent = <name>``. ``~``/``$VAR`` expand; a glob-shaped
    entry is rejected into ``problems`` (never raised — the sweep stays fail-open).

    Two schema shapes per key, branched on the parsed TOML type: a ``dict``
    (``[sources.<x>]``, the legacy table — ``paths`` + ``replace`` + an optional
    table-level ``glob`` applied to every path) or a ``list``
    (``[[sources.<x>]]``, an array-of-tables — each entry ``{path, glob?}``, additive,
    no ``replace``). An absent ``glob`` ⇒ today's ``_FORMAT_GLOB[fmt]``; an empty
    ``glob = ""`` ⇒ a problem (never a silent fallback). An optional ``surface``
    (``cli|vscode|ide``, table-level or per-entry) restamps the imported rows'
    surface — an out-of-set value is a problem, an absent one keeps the parser's
    own value (byte-identical). Fully additive: an empty/absent ``[sources]``
    returns exactly the built-in registry."""
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

    def _resolve_surface(key: str, surface) -> str | None:
        """The client-surface stamp for one entry: absent ⇒ ``""`` (the parser's own
        value stands downstream — byte-identical). A set value must be in the closed
        set (cli/vscode/ide); anything else is a problem (``None`` return, entry
        skipped) — the sweep stays fail-open, never raises (§ acceptance)."""
        if surface is None:
            return ""
        if not isinstance(surface, str) or surface not in _SURFACE_SET:
            problems.append(f"[sources.{key}] surface must be one of cli/vscode/ide "
                            f"(or drop the key) — got {surface!r}")
            return None
        return surface

    def _resolve_path_globs(key: str, value) -> tuple | None:
        """The root-agnostic ``--path`` patterns for one entry: absent ⇒ ``()`` (this
        entry contributes nothing to `--path`). A set value must be a list of non-empty
        strings; anything else is a problem (``None`` return, entry skipped) — never a
        silent fallback to the anchored ``glob``, which is exactly the bug this key
        exists to close. Windows separators are normalised to ``/`` so a hand-authored
        ``**\\chatSessions\\*.jsonl`` still matches (``Path.glob`` is ``/``-only)."""
        if value is None:
            return ()
        if (not isinstance(value, list) or not value
                or any(not isinstance(p, str) or not p for p in value)):
            problems.append(f"[sources.{key}] path_globs must be a non-empty list of "
                            "non-empty strings (drop the key if this source should not "
                            "be reachable by `cage import --path`)")
            return None
        return tuple(p.replace("\\", "/") for p in value)

    def _emit(key: str, raw, glob, fmt: str, seen: set, surface=None,
              path_globs=None) -> None:
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
        sf = _resolve_surface(key, surface)
        if sf is None:
            return
        pg = _resolve_path_globs(key, path_globs)
        if pg is None:
            return
        p = Path(_expand_source(raw))
        if (p, g) in seen:  # policy path == a built-in path
            # Silent-surface-loss fix (capture-precision §3.5): a declared `surface` on a
            # path that collides with a built-in used to be dropped with the whole entry,
            # so the explicit config value vanished. Now the **declared value wins** — it
            # upgrades the colliding built-in that carried no surface (an already-declared
            # surface is left as the earlier winner; declaring two conflicting surfaces for
            # one path is a config error, not something to silently reorder).
            # `path_globs` follows the same rule for the same reason: the colliding entry
            # is dropped wholesale, so its declared `--path` patterns would vanish with
            # it. They are merged onto the winner (order-preserving, deduped) rather than
            # lost — a duplicated path declaring an extra pattern is additive, never a
            # silent drop.
            for idx, s in enumerate(sources):
                if (s.path, s.glob) == (p, g) and s.agent == key:
                    if sf and not s.surface:
                        s = sources[idx] = s._replace(surface=sf)
                    extra = tuple(x for x in pg if x not in s.path_globs)
                    if extra:
                        sources[idx] = s._replace(path_globs=s.path_globs + extra)
                    break
            return
        seen.add((p, g))
        sources.append(LogSource(p, g, "policy", key, fmt, raw, sf, pg))

    def _dict_paths(key: str, table: dict, fmt: str) -> None:
        raw_paths = table.get("paths", [])
        if not isinstance(raw_paths, list) or any(not isinstance(p, str) for p in raw_paths):
            problems.append(f"[sources.{key}] paths must be a list of strings")
            return
        table_glob = table.get("glob")  # optional; one glob for every path in the table
        table_surface = table.get("surface")  # optional; one surface for every path in the table
        table_pg = table.get("path_globs")  # optional; one `--path` pattern set for the table
        seen = {(s.path, s.glob) for s in sources if s.agent == key}
        for raw in raw_paths:
            _emit(key, raw, table_glob, fmt, seen, table_surface, table_pg)

    def _list_paths(key: str, entries: list, default_fmt: str | None) -> None:
        """The ``[[sources.<x>]]`` array-of-tables form — each entry
        ``{path, glob?, surface?}``. A built-in agent's format is implicit
        (``default_fmt``); a custom tool has no table level, so each entry declares
        its own ``format``."""
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
                                    "— each entry needs format = \"claude|copilot|kiro\"")
                    continue
            elif entry.get("format") not in (None, default_fmt):
                problems.append(f"[[sources.{key}]] format is implicit for the {key} "
                                "agent — drop the `format` key")
                continue
            _emit(key, entry.get("path"), entry.get("glob"), fmt, seen,
                  entry.get("surface"), entry.get("path_globs"))

    # Built-in agents, in SURFACES order. **Directive A (capture-precision §3.6): no
    # built-in fallback, no env.** Sources come ONLY from the `[sources]` table cage
    # materializes into `cage.toml`. An agent with no `[sources.<agent>]` entry captures
    # nothing (surfaced loudly by the import sweep + `cage doctor`, never silent).
    for agent in surfaces:
        table = src_tables.get(agent)
        if isinstance(table, dict) and table.get("format") not in (None, agent):
            problems.append(f"[sources.{agent}] is the {agent} agent table — its "
                            "format is implicit; drop the `format` key (a custom tool "
                            "uses a different name)")
        if isinstance(table, dict):
            _dict_paths(agent, table, agent)
        elif isinstance(table, list):
            _list_paths(agent, table, agent)

    # Custom tools: any `[sources.<name>]` whose name is not one of the three agents.
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
                            "format = \"claude|copilot|kiro\" (the parser to reuse)")
            continue
        _dict_paths(name, table, fmt)

    return SourcesResolution(sources, problems, disabled)


def agent_log_sources(agent: str, pol: dict | None = None) -> list[LogSource]:
    """The candidate log locations for one built-in agent — the built-in registry plus
    any `[sources.<agent>]` policy additions (see :func:`resolve_log_sources`). A thin
    view over the single resolver so the import sweep and doctor share one resolution.
    Byte-identical to the legacy built-in list when ``pol`` carries no ``[sources]``."""
    return [s for s in resolve_log_sources(pol).sources if s.agent == agent]


def path_globs_for(agent: str, pol: dict | None = None) -> list[str]:
    """THE lookup `cage import --path`/`--project` scans with (path-globs handoff §5):
    the **root-agnostic** patterns declared for ``agent``, unioned across its
    ``[sources.<agent>]`` entries in declaration order, deduped.

    Why a second key rather than reusing ``glob``: ``glob`` is anchored to its declared
    ``path`` (``*/chatSessions/*.jsonl`` under ``workspaceStorage``), so pointing
    ``--path`` at a ``chatSessions`` directory with it matches nothing — the reported
    copilot bug, relocated rather than fixed. Two keys, two jobs.

    Empty list ⇒ ``--path`` scans nothing for this agent. That is deliberate and must be
    said out loud by the caller: sources come only from ``cage.toml`` (Directive A), so a
    project that has never run `cage setup --sync-sources` has no patterns, and a silent
    code fallback here would recreate the two-places problem the key exists to close.
    ``replace = true`` on a ``[sources.<agent>]`` therefore replaces that agent's
    ``path_globs`` too — same table, same entries, same semantics."""
    out: list[str] = []
    for s in resolve_log_sources(pol).sources:
        if s.agent != agent:
            continue
        out += [p for p in s.path_globs if p not in out]
    return out


def path_globs_missing(pol: dict | None = None) -> list[str]:
    """Agents that declare ``[sources]`` entries but no ``path_globs`` on any of them —
    the **stale-materialization** advisory (`cage doctor --paths`, handoff §10). Same
    class as :func:`sources_drift`: a project materialized before this key existed keeps
    importing normally and only loses `--path`, which would otherwise be a silent
    surprise at the moment someone reaches for the escape hatch."""
    from cage import agents
    declared = {s.agent for s in resolve_log_sources(pol).sources}
    return [a for a in agents.SURFACES
            if a in declared and not path_globs_for(a, pol)]


def custom_tool_sources(pol: dict | None = None) -> list[LogSource]:
    """The `[sources.<name>]` custom-tool sources (name ∉ the three agents) — each
    reuses a declared parser ``fmt`` and stamps ``agent = <name>`` on imported rows."""
    from cage import agents
    return [s for s in resolve_log_sources(pol).sources if s.agent not in agents.SURFACES]


def copilot_metric_sources() -> list[tuple[Path, str, str]]:
    """The three **opt-in, per-model-call** Copilot metrics stores (COPILOT-METRICS
    handoff §4.2, §5): sidecar / debuglog / otel. ``(path, glob, source-tag)`` — the
    tag matches `schema.COPILOT_METRIC_SOURCES` and picks the parser in
    `importcmd.import_copilot`.

    **Deliberately NOT in `agent_log_sources`/`_builtin_log_sources`** — those feed
    the *calls* parser, and none of these three stores is call-shaped (they only ever
    yield `copilot` metrics rows). Each is gated behind a VS Code setting named in
    `cage doctor`'s `copilot-metrics` check; absence of a gated store is a state, not
    a fault. Windows layouts for all three are UNVERIFIED-LAYOUT (inferred from the
    VS Code user-dir convention, not pinned on a real install)."""
    user = vscode_user_dir()
    return [(user / "agentHostUsage", "*.jsonl", "sidecar"),
            (user / "workspaceStorage", "*/GitHub.copilot-chat/debug-logs/*/*.jsonl",
             "debuglog"),
            (user / "globalStorage" / "github.copilot-chat", "agent-traces.db", "otel")]


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
                for (path, meaning), (_bp, glob, _pg) in zip(docs, builtin)]
        out.append({"agent": agent, "env": _AGENT_ENV.get(agent, ()),
                    "sources": srcs, "other_os": _SOURCE_DOC_OTHER_OS.get(agent, ())})
    return out


# THE prices-file name — the single project-prices filename literal (prices-toml
# ADR-LAWS, mirror of the ``cage.toml`` rename). `Footprint.prices` /
# `Footprint.shadowed_prices` and `resolve_prices_file` are the only places it lives;
# the bundled-seed name (`data/prices.toml`) is a separate literal in `policy.py`,
# exactly as the bundled `data/cage.toml` name sits beside `Footprint.policy`.
PRICES_FILENAME = "prices.toml"
_PRICE_HEADER = re.compile(r"^\s*\[(prices|credits)\b")


def resolve_prices_file(base: Path, policy_file: Path) -> Path:
    """THE project price-overrides resolver (prices-toml plan §3) — the one place the
    ``prices.toml`` name is chosen. ``prices.toml`` if it sits beside ``policy_file``,
    else the resolved ``policy_file`` itself (legacy in-``cage.toml`` prices — releases
    ≤ v0.35 wrote prices inline, and they are on PyPI, so those must keep resolving
    untouched). The bundled default is layered underneath by `policy.load`, never here.
    Mirrors `Footprint.policy`'s ``cage.toml`` → ``policy.toml`` fallback exactly."""
    prices = base / PRICES_FILENAME
    return prices if prices.exists() else policy_file


def _file_declares_prices(path: Path) -> bool:
    """True if ``path`` on disk actually declares a ``[prices…]``/``[credits…]`` table
    (a real header, not a `# moved to prices.toml` pointer comment). A cheap text scan —
    paths.py stays tomllib-free and never raises; a read error ⇒ False (nothing shadowed)."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if _PRICE_HEADER.match(line):
                return True
    except OSError:
        return False
    return False


class Footprint:
    """The per-project ``.cage/`` layout (ADR-LAWS).

    The ledger carries token *counts*, never prompt bodies — PII-safe by
    construction (ADR-LAWS Law 4). For Orff, point ``CAGE_LEDGER`` at elgar so even the
    counts live in the private store.
    """

    def __init__(self, root: Path, base: Path | None = None):
        self.root = root
        # ``CAGE_BASE`` (set by the ``--ledger`` flag) re-bases the whole footprint —
        # ledger, state and policy all move together to one active sink (ADR-LAWS Law 2).
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
    def provenance_legacy(self) -> Path:
        """The pre-P3c authorship buffer, `ledger/provenance.jsonl` — **read forever,
        never written, never rewritten, never deleted.**

        Renamed from `provenance` in P3c (v0.51) rather than left pointing at the old
        file: every call site had to be visited, and a property that silently returns a
        *subset* of the rows is the failure this rename exists to make impossible. Frozen
        rows are never backfilled — `residual_lines`' absent-vs-recorded-`0` version gate
        for `agent%` depends on exactly that."""
        return self.ledger / "provenance.jsonl"

    @property
    def provenance_dir(self) -> Path:
        """The month-partitioned authorship tree (P3c, v0.51):
        ``ledger/provenance/provenance-<month>.jsonl``.

        **⟲ THIS REVERSES AN EXPLICIT IN-CODE DECISION.** `shard()`'s docstring said, in
        as many words, *"`provenance` is intentionally never partitioned (buffer)"* — the
        reasoning being that the local file is a buffer whose canonical home is
        `refs/notes/cage-provenance` (CI-sole-writer, merged by row id), so bounding it
        did not matter.

        **What overturned it: nothing prunes the buffer.** `cleanup.NEVER` covers
        `ledger/`, and no cleanup class touches this file, so the "buffer" is an unbounded
        append-only log that every read scans end to end. Partitioning gives it the same
        bounded `--since` re-scan every other long-lived log already has. The original
        sentence is recorded above rather than deleted, per the house rule that a reversal
        is written down.

        Uses the **directory** mechanism (`savings_dir`/`copilot_dir` style), which
        `paths.py` already calls *"smallest diff, precedent already tested"* — not a
        generalization of `shard()`'s flat naming."""
        return self.ledger / "provenance"

    def provenance_shard(self, ts: str) -> Path:
        """Month-partition path for a provenance row, from the **row's own `ts`** — never
        a write-time clock (the determinism law). A missing or unparseable `ts` falls back
        to the legacy unpartitioned name, exactly as `shard()` already does, so a
        malformed row still lands somewhere readable rather than being dropped."""
        month = ts[:7] if (ts and len(ts) >= 7 and ts[4] == "-") else ""
        name = f"provenance-{month}.jsonl" if month else "provenance.jsonl"
        return self.provenance_dir / name

    def provenance_shards(self) -> list[Path]:
        """Every readable provenance shard — **the legacy unpartitioned file first**
        (it is strictly older), then the dated month shards in ascending order, so a
        concatenated read stays oldest→newest. Names match `ledger._SHARD_MONTH`, so
        ``--since`` month-skipping is free. Only existing files are returned."""
        out: list[Path] = []
        if self.provenance_legacy.exists():
            out.append(self.provenance_legacy)
        base = self.provenance_dir
        if base.is_dir():
            out.extend(sorted(base.glob("provenance*.jsonl")))
        return out

    @property
    def imports(self) -> Path:
        """The capture manifest (import-ledger plan §4): one append-only row per import
        sweep (per agent×surface) and per graphify run — an audit trail of what cage
        captured, when, from where, and how much.

        **Moved to `state/` in P3a (v0.51).** It was `ledger/imports.jsonl`, and its
        behaviour had already been a state file's for two releases: never read by a
        derived view, supplying **labels only** to `cage insights chats` and moving zero
        numeric cells when deleted (pinned by
        `test_chats.py::test_deleting_manifest_changes_zero_numeric_cells`). It is an
        audit trail, not ledger data. This is consistent with the state law rather than in
        tension with it — that law says a state file cannot change a reported *number*.

        **⚠ The move loses `cleanup.NEVER`'s `"ledger/"` umbrella**, which protected this
        file purely by location. `imports.jsonl` is therefore named in `NEVER` explicitly,
        and must stay named there: cleanup is a closed allowlist, so nothing would fail
        until someone added a `state/` class years from now — and an audit trail that
        quietly becomes cleanup-eligible is a silent data-loss path.

        `CAGE_IMPORTS_LOG` overrides the path, matching `capture_log`/`attest_log`.
        The legacy location is still READ (`imports_legacy`) and never rewritten."""
        return Path(os.environ.get("CAGE_IMPORTS_LOG", self.state / "imports.jsonl"))

    @property
    def imports_legacy(self) -> Path:
        """The pre-P3a manifest home, `ledger/imports.jsonl` — **read forever, never
        written, never deleted**.

        Every real install has rows here (208 in the maintainer's own ledger). A one-way
        move would make every existing chat title fall back to a session id on the next
        read: not a crash, not an error — just names quietly disappearing.

        **Deliberately NOT the `cage.toml`/`policy.toml` shape, and the difference is why
        no doctor warning exists here.** Those two *shadow* each other — one wins, the
        other is ignored, and a user who edits the ignored one is confused, so doctor says
        so. These two homes are **both read, and their rows are disjoint** (the old file
        stopped being appended the moment the new one started). There is no wrong file to
        edit and nothing to disambiguate, so a warning would be noise — and worse, it would
        read as *delete this*, which is the one thing that loses data here. It is protected
        by `cleanup.NEVER` under both names."""
        return self.ledger / "imports.jsonl"

    @property
    def savings_dir(self) -> Path:
        """The **legacy** per-source savings tree, ``ledger/savings/<tool>/`` — read
        forever, never written since P4 (v0.51), never rewritten or deleted.

        A savings row is **unrecoverable**: nothing reconstructs it the way a cursor or a
        debug-log row can be reconstructed, which is why `test_cleanup.py` pins its
        survival at `days=0`. New rows go to `ledger/<tool>/` (`tool_dir`)."""
        return self.ledger / "savings"

    def tool_dir(self, tool: str) -> Path:
        """A savings tool's own directory: ``ledger/<tool>/savings-<month>.jsonl``.

        P4 (v0.51) lifted the savings tree up one level so every producer owns exactly one
        directory under `ledger/` — `claude/` `copilot/` `kiro/` `consumer/` `provenance/`
        `graphify/` `fux/` `compress/` `responsecache/` — rather than tools living one
        level deeper than everything else.

        **All four savings sources moved together (10.6), not just graphify.** A
        graphify-only move would have left one row kind in two shapes permanently, which is
        the inconsistency this program exists to remove.

        ``tool`` is validated by `reserve_tool_name` before it can become a directory."""
        return self.ledger / reserve_tool_name(tool)

    def savings_shard(self, tool: str, ts: str) -> Path:
        """Month-partition path for a savings row of ``tool``, from the row's own ``ts``
        (`<tool>/savings-2026-07.jsonl`). Same determinism as `shard`: the name comes from
        the row, never a write-time clock. ``tool`` is a validated path-safe token
        (`schema.make_savings`) **and** a non-reserved one (`reserve_tool_name`)."""
        month = ts[:7] if (ts and len(ts) >= 7 and ts[4] == "-") else ""
        name = f"savings-{month}.jsonl" if month else "savings.jsonl"
        return self.tool_dir(tool) / name

    def savings_shards(self) -> list[Path]:
        """Every readable savings shard across **both** trees, sorted for a deterministic
        concatenated read: the legacy `savings/<tool>/` tree first (it is strictly older),
        then the per-tool dirs at `ledger/<tool>/`. Only existing files are returned.

        The new tree is found by **globbing `ledger/*/savings*.jsonl` and excluding
        `_RESERVED_LEDGER_DIRS`** — the same table `reserve_tool_name` refuses against, so
        the write guard and the read filter can never disagree about what a tool directory
        is. An allowlist of known tool names was the first attempt and was wrong: it made
        any third-party tool's rows **write-only**, landing on disk and never returned by
        any view, with nothing failing. Excluding the reserved set inverts that safely —
        an unknown directory is assumed to be a tool's, and a future *kind* must add itself
        to the reserved set anyway, or it would collide with a tool name."""
        out: list[Path] = []
        base = self.savings_dir
        if base.is_dir():
            out.extend(sorted(base.glob("*/savings.jsonl")))
            out.extend(sorted(base.glob("*/savings-*.jsonl")))
        if self.ledger.is_dir():
            for d in sorted(self.ledger.iterdir()):
                if not d.is_dir() or d.name in _RESERVED_LEDGER_DIRS:
                    continue
                out.extend(sorted(d.glob("savings.jsonl")))
                out.extend(sorted(d.glob("savings-*.jsonl")))
        return out

    @property
    def consumer_dir(self) -> Path:
        """The consumer-metrics ledger sub-dir (P1, v0.51):
        ``ledger/consumer/calls-<month>.jsonl``. A directory via the `savings_dir`
        mechanism — the same precedent `copilot_dir` names, for the same reason (smallest
        diff, already tested), and NOT a generalization of `shard()`.

        Named `consumer/` to match [ADR-CONSUMERS](../docs/adr/0006_consumer.md)'s own
        vocabulary rather than `lib/`: the *default* agent name is `lib`, but a caller may
        stamp any name (a proxy row, a named application), and the directory is the
        producer's home, not one agent's."""
        return self.ledger / "consumer"

    def consumer_shard(self, ts: str) -> Path:
        """Month-partition path for a consumer-metrics row, from the row's own ``ts``
        (`consumer/calls-2026-08.jsonl`) — mirrors `copilot_shard`.

        The basename is `calls-` rather than `chats-` on purpose: the three agent kinds
        are chat-grained and this one is call-grained, and a shard name that says `chats`
        over per-call rows would be a small lie a reader has to un-learn."""
        month = ts[:7] if (ts and len(ts) >= 7 and ts[4] == "-") else ""
        name = f"calls-{month}.jsonl" if month else "calls.jsonl"
        return self.consumer_dir / name

    def consumer_shards(self) -> list[Path]:
        """Every readable consumer-metrics shard (`consumer/calls-*.jsonl`), sorted for a
        deterministic concatenated read. Names match `ledger._SHARD_MONTH`, so ``--since``
        month-skipping is free. Only existing files are returned."""
        base = self.consumer_dir
        if not base.is_dir():
            return []
        return sorted(base.glob("calls*.jsonl"))

    @property
    def copilot_dir(self) -> Path:
        """The Copilot-metrics ledger sub-dir (COPILOT-METRICS handoff §4.2):
        ``ledger/copilot/chats-<month>.jsonl``. A directory via the `savings_dir`
        mechanism (smallest diff, precedent already tested), not a generalization of
        `shard()` — this kind is a capture-only sibling to `savings/`, never a
        second `calls`-shaped tree."""
        return self.ledger / "copilot"

    def copilot_shard(self, ts: str) -> Path:
        """Month-partition path for a copilot-metrics row, from the row's own ``ts``
        (`copilot/chats-2026-08.jsonl`) — mirrors `savings_shard`."""
        month = ts[:7] if (ts and len(ts) >= 7 and ts[4] == "-") else ""
        name = f"chats-{month}.jsonl" if month else "chats.jsonl"
        return self.copilot_dir / name

    def copilot_shards(self) -> list[Path]:
        """Every readable copilot-metrics shard (`copilot/chats-*.jsonl`), sorted for a
        deterministic concatenated read. Names match `ledger._SHARD_MONTH`, so
        ``--since`` month-skipping is free. Only existing files are returned."""
        base = self.copilot_dir
        if not base.is_dir():
            return []
        return sorted(base.glob("chats*.jsonl"))

    @property
    def kiro_dir(self) -> Path:
        """The Kiro-metrics ledger sub-dir (KIRO-METRICS handoff §4.2):
        ``ledger/kiro/chats-<month>.jsonl``. Same `savings_dir`-style mechanism
        `copilot_dir` uses — a capture-only sibling tree, never a second `calls`-shaped
        kind. Routing (which ledger this lands in — the sink vs the sweep root) is
        decided by the caller (ADR 0006), not by this path."""
        return self.ledger / "kiro"

    def kiro_metric_shard(self, ts: str) -> Path:
        """Month-partition path for a kiro-metrics row, from the row's own ``ts``
        (`kiro/chats-2026-08.jsonl`) — mirrors `copilot_shard`."""
        month = ts[:7] if (ts and len(ts) >= 7 and ts[4] == "-") else ""
        name = f"chats-{month}.jsonl" if month else "chats.jsonl"
        return self.kiro_dir / name

    def kiro_metric_shards(self) -> list[Path]:
        """Every readable kiro-metrics shard (`kiro/chats-*.jsonl`), sorted for a
        deterministic concatenated read. Names match `ledger._SHARD_MONTH`, so
        ``--since`` month-skipping is free. Only existing files are returned."""
        base = self.kiro_dir
        if not base.is_dir():
            return []
        return sorted(base.glob("chats*.jsonl"))

    @property
    def claude_dir(self) -> Path:
        """The Claude-metrics ledger sub-dir (CLAUDE-METRICS handoff §4.2):
        ``ledger/claude/chats-<month>.jsonl``. Same `savings_dir`-style mechanism
        `copilot_dir`/`kiro_dir` use — a capture-only sibling tree, never a second
        `calls`-shaped kind."""
        return self.ledger / "claude"

    def claude_shard(self, ts: str) -> Path:
        """Month-partition path for a claude-metrics row, from the row's own ``ts``
        (`claude/chats-2026-08.jsonl`) — mirrors `copilot_shard`/`kiro_metric_shard`."""
        month = ts[:7] if (ts and len(ts) >= 7 and ts[4] == "-") else ""
        name = f"chats-{month}.jsonl" if month else "chats.jsonl"
        return self.claude_dir / name

    def claude_shards(self) -> list[Path]:
        """Every readable claude-metrics shard (`claude/chats-*.jsonl`), sorted for a
        deterministic concatenated read. Names match `ledger._SHARD_MONTH`, so
        ``--since`` month-skipping is free. Only existing files are returned."""
        base = self.claude_dir
        if not base.is_dir():
            return []
        return sorted(base.glob("chats*.jsonl"))

    def shard(self, kind: str, ts: str) -> Path:
        """Month-partition path for ``kind`` (``calls``/``receipts``/``tasks``) derived
        from a row's own ``ts`` — ``calls-2026-06.jsonl`` (ADR-LAWS). Determinism:
        the name comes from the row, never a write-time clock. A missing/unparseable
        ``ts`` falls back to the legacy unpartitioned file so a malformed row still lands
        somewhere readable.

        **⟲ REVERSED in P3c (v0.51).** This line used to end: *"`provenance` is
        intentionally never partitioned (buffer)."* It is now partitioned, through the
        directory branch below. The reason the original held — the local file is only a
        buffer, canonical storage being `refs/notes/cage-provenance` — was true and
        insufficient: **nothing prunes the buffer**, so it grew without bound and every
        read scanned all of it. The sentence is recorded here rather than deleted; see
        `provenance_dir` for the full reversal.

        ``kind`` may be a ``("savings", tool)`` tuple, which routes into the per-source
        savings tree via `savings_shard` (import-ledger plan §3). The plain strings
        ``"copilot"``/``"kiro"``/``"claude"``/``"consumer"``/``"provenance"`` route into
        their own per-producer trees via `copilot_shard`/`kiro_metric_shard`/
        `claude_shard`/`consumer_shard`/`provenance_shard` (COPILOT-METRICS handoff §4.2,
        KIRO-METRICS handoff §4.2, CLAUDE-METRICS handoff §4.2, P1 and P3c of the ledger
        restructure), the same mechanism."""
        if isinstance(kind, tuple) and kind and kind[0] == "savings":
            return self.savings_shard(kind[1], ts)
        if kind == "provenance":
            return self.provenance_shard(ts)
        if kind == "consumer":
            return self.consumer_shard(ts)
        if kind == "copilot":
            return self.copilot_shard(ts)
        if kind == "kiro":
            return self.kiro_metric_shard(ts)
        if kind == "claude":
            return self.claude_shard(ts)
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
        """Fleet-study phase markers (`cage study start/stop`, ADR-CONSUMERS) — a small
        append-only jsonl beside the ledger files (it travels inside `cage data export
        --study` bundles). Unpartitioned by design, like `provenance.jsonl`: a study
        is weeks, not years."""
        return self.ledger / "study.jsonl"

    @property
    def policy(self) -> Path:
        """THE single project-config path resolver — never a second place that knows
        the filename (CLAUDE.md law). ``cage.toml`` is canonical; ``policy.toml`` is
        read as a back-compat fallback (releases ≤ v0.35 wrote it, and they are on
        PyPI — a real user's on-disk `policy.toml` must keep working untouched).
        Resolution: ``cage.toml`` if present → else ``policy.toml`` if present →
        else ``cage.toml`` (the name a fresh scaffold writes). Both present ⇒
        ``cage.toml`` wins; :attr:`shadowed_config` names the ignored file so doctor
        and the load boundary can warn."""
        new = self.base / "cage.toml"
        if new.exists():
            return new
        old = self.base / "policy.toml"
        if old.exists():
            return old
        return new

    @property
    def shadowed_config(self) -> Path | None:
        """The legacy ``policy.toml`` when it sits *beside* a ``cage.toml`` that wins —
        the ignored leftover doctor flags and the load path warns about. ``None``
        unless both files exist (the only case where a config is silently ignored)."""
        new = self.base / "cage.toml"
        old = self.base / "policy.toml"
        return old if (new.exists() and old.exists()) else None

    @property
    def prices(self) -> Path:
        """THE project price-overrides path (prices-toml plan §3) — model rate rows,
        ``[credits]``, and the ``[meta] prices_version/prices_date`` counters. Vendor
        facts, split from ``cage.toml`` (routing decisions) so a wholesale price sync
        can't damage user policy. Resolution: ``prices.toml`` if present → else the
        resolved policy file (legacy in-``cage.toml`` prices) → (bundled default is
        layered by `policy.load`). Both present ⇒ ``prices.toml`` wins;
        :attr:`shadowed_prices` names the ignored legacy block."""
        return resolve_prices_file(self.base, self.policy)

    @property
    def shadowed_prices(self) -> Path | None:
        """The legacy in-``cage.toml`` (or ``policy.toml``) price block that a present
        ``prices.toml`` overrides — the ignored leftover doctor flags and the load path
        warns about. ``None`` unless a ``prices.toml`` exists *and* the policy file still
        declares real ``[prices…]``/``[credits…]`` tables (a migrated policy file, whose
        prices are gone, shadows nothing)."""
        prices = self.base / PRICES_FILENAME
        pol = self.policy
        if not prices.exists() or not pol.exists() or prices == pol:
            return None
        return pol if _file_declares_prices(pol) else None

    @property
    def out(self) -> Path:
        return self.base / "out"

    @property
    def output(self) -> Path:
        """The `--export` artifact directory (`cage/viewexport.py`) — dated, per-run
        folders of exported reports and insights.

        **Deliberately not :attr:`out`.** That one is `cage data serve`'s docroot: a
        stdlib `http.server` is pointed straight at it, so every file inside is served
        on the loopback port. An exported artifact is a *record*, not a page, and
        sharing one directory would mean starting the dashboard quietly published every
        report anyone had ever exported. Two homes, two purposes, no overlap."""
        return self.base / "output"

    @property
    def state(self) -> Path:
        return self.base / "state"

    @property
    def cursors(self) -> Path:
        """Per-agent incremental-import high-water cursors (ADR-LAWS Law 1). Maps each
        scanned source file to its last-seen ``(size, mtime)`` so a re-import skips
        unchanged files instead of re-parsing the whole world (the ledger is 22k+ rows);
        `hooks.append_new`'s id-dedupe stays the correctness backstop. Machine-local
        state, never a derived view — never read by any table."""
        return self.state / "cursors.json"

    @property
    def debug_log(self) -> Path:
        """Capture-path debug log (`cage/debuglog.py`) — metadata-only, written only
        when `CAGE_DEBUG=1` / `[debug] enabled`. Override the path with `CAGE_DEBUG_LOG`."""
        return Path(os.environ.get("CAGE_DEBUG_LOG", self.state / "debug.log"))

    @property
    def capture_log(self) -> Path:
        """Always-on capture breadcrumb (`cage/capturelog.py`) — one line per agent per
        real import run, counts-only. Unlike `debug_log`, this is **never** gated on
        `CAGE_DEBUG` — it's the standing proof-of-capture. Override the path with
        `CAGE_CAPTURE_LOG`; size-managed by the `capture-log` cleanup class."""
        return Path(os.environ.get("CAGE_CAPTURE_LOG", self.state / "capture.log"))

    @property
    def usage_log(self) -> Path:
        """Always-on graphify usage breadcrumb (`cage/usagelog.py`, graphify-capture
        plan GC1) — one line per graphify run (shim / native / transcript-detected),
        `{op, args_hash, exit, ms, outcome}`, counts-never-content. Diagnostic only:
        never priced, never read by a derived money view (so a usage row can't move a
        reported number — the same invariant the `state/` home guarantees by
        construction). Size-managed by the `usage-log` cleanup class."""
        return Path(os.environ.get("CAGE_USAGE_LOG", self.state / "graphify-usage.jsonl"))

    @property
    def attest_log(self) -> Path:
        """L1 agent attestations (`cage/attest.py`) — `{kind, agent, session|tool+
        args_hash, ts}`, one row per hook firing. **Stamped, never inferred**: a hook
        runs *inside* an agent, so it is the only place cage learns which agent did
        something without guessing. Counts-never-content (a command is hashed, never
        stored) and, like every `state/` file, **never read by a derived money view** —
        only the deleted `cage insights adoption`; nothing reads it today. Absent unless
        the opt-in L1 hooks are wired; size-managed by the `attest-log` cleanup class."""
        return Path(os.environ.get("CAGE_ATTEST_LOG", self.state / "attest.jsonl"))

    @property
    def hooks_seen(self) -> Path:
        """Per-(agent,event) hook heartbeat — append-only, last-write-wins on read.
        Gated by the same debug switch, so it is absent unless debug is enabled."""
        return self.state / "hooks-seen.jsonl"

    def pending_edits(self, session_id: str) -> Path:
        """Per-session buffer of uncommitted `PostToolUse` edits (ADR-AUTHORSHIP) — a
        `post-commit` hook resolves these to a real sha and clears the file."""
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (session_id or "nosession"))
        return self.state / f"pending-{safe}.jsonl"
