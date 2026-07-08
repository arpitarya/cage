"""Path resolution for the per-project `.cage/` footprint + agent homes (plan §3, §5)."""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path


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


def is_cage_import_command(command: str) -> bool:
    """True if ``command`` is a cage ``import …`` hook command (any agent/flags). Lets the
    wiring collapse a superseded per-agent import (e.g. `cage import --agent codex`) into
    the current per-agent import on re-setup, instead of leaving both."""
    return reresolve_cage_command(command) is not None and " import" in (command or "")


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
    ledger resolves to ``~`` as its "project" — `cage init` then re-inits the
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


def bundled_data_dir() -> Path:
    """Seed data shipped with the cage package (default policy + skill assets)."""
    return Path(__file__).parent / "data"


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


def agent_log_sources(agent: str) -> list[tuple[Path, str]]:
    """The single registry of candidate ``(source, glob)`` log locations per agent —
    what `importcmd` scans and `cage doctor --paths` probes. One list per agent so a
    new location (like Copilot's VS Code chat-session store) is added exactly once.
    For claude/codex/copilot the source is a directory + glob; for kiro it is the
    token log file itself (glob ``*`` — `_scan` treats a file source as itself)."""
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
        append-only jsonl beside the ledger files (it travels inside `cage export
        --study` bundles). Unpartitioned by design, like `provenance.jsonl`: a study
        is weeks, not years."""
        return self.ledger / "study.jsonl"

    @property
    def policy(self) -> Path:
        return self.base / "policy.toml"

    @property
    def out(self) -> Path:
        return self.base / "out"

    def out_file(self, name: str) -> Path:
        self.out.mkdir(parents=True, exist_ok=True)
        return self.out / name

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
