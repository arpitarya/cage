"""Unified hookless metering — `cage import [--agent claude|codex|copilot|kiro|all]`.

One umbrella over the per-agent hookless paths. Cage targets the wire protocol, so a
metered call is the same row no matter which agent emitted it; only *how we recover it
without hooks* differs by agent:

All four agents now persist a usage log to disk, so the hookless path is an on-disk
**import** for every one of them:

- **claude / codex / copilot** — `~/.claude/projects/**/*.jsonl`,
  `~/.codex/sessions/**/rollout-*.jsonl`, `~/.copilot/session-state/*/events.jsonl`.
- **kiro** — `kiro.kiroagent/dev_data/tokens_generated.jsonl` (coarse: prompt tokens are
  reliable, output tokens often 0, model frequently the generic `"agent"`). The proxy
  (`cage data meter -- <cmd>`) stays the higher-fidelity fallback when Kiro's log is too thin.

Additive: hooks + MCP stay the default real-time path; this runs alongside them and
dedupes by call id (`hooks.append_new`), so a call seen by both a hook and an import is
counted once. Fail-open per file, idempotent on re-import, $0/stdlib, counts-never-content.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import json
from pathlib import Path

from cage import agents, debuglog, hooks, ledger, limits, lockutil, paths, policy, transcript

# Agents that persist a usage log to disk (everything else → proxy fallback).
LOG_BEARING = ("claude", "codex", "copilot", "kiro")


@contextlib.contextmanager
def _import_lock(foot: paths.Footprint, pol: dict | None = None):
    """Serialize concurrent import sweeps so two of them can't both snapshot the
    ledger's ``seen`` set *before* either appends — the window that let a single turn
    land twice under two racing hooks (a Stop hook + a SessionStart sweep firing at
    once). Holding an exclusive lock across the read-check-append section means the
    second sweep rebuilds ``seen`` only after the first has committed, so id-dedupe
    catches it. **Fail-open** via `lockutil.locked` (fcntl → msvcrt → unlocked): if
    the lock can't be taken, proceed — `hooks.append_new`'s id-dedupe stays the
    backstop, exactly as before this lock existed. Never raises into capture."""

    def _miss(exc):
        # Fail-open but never silent: an untakeable lock means the id-dedupe backstop
        # is carrying dedupe alone — attributable under CAGE_DEBUG=1.
        if exc is None:
            debuglog.event(foot.root, pol=pol, event="import",
                           skip="no-lock-primitive-on-platform")
        else:
            debuglog.exception(foot.root, "import.lock", exc, pol=pol)

    with lockutil.locked(foot.state / "import.lock", on_miss=_miss):
        yield


def _mtime_utc(f: Path):
    try:
        return _dt.datetime.fromtimestamp(f.stat().st_mtime, _dt.timezone.utc)
    except OSError:
        return None


# ── incremental high-water cursors (plan §3.7) ──────────────────────────────
# The ledger is 22k+ rows and the no-daemon model means manual `cage import`,
# `export`'s import-first refresh, and the `cage data watch` loop all re-run the scan
# repeatedly. Re-parsing every transcript + reloading the whole ledger per file each
# run is O(all logs × ledger). The cursor records each source file's last-seen
# (size, mtime) so an unchanged file is skipped *before* parsing; `append_new`'s
# id-dedupe stays the correctness backstop for grown/new files, never the throughput
# plan. Machine-local state, never a derived view.

def _load_cursors(foot: paths.Footprint) -> dict:
    try:
        return json.loads(foot.cursors.read_text(encoding="utf-8")) if foot.cursors.exists() else {}
    except (ValueError, OSError) as e:  # fail-open: a corrupt cursor file ⇒ full re-scan
        debuglog.exception(foot.root, "import.cursors-load", e)
        return {}


def _save_cursors(foot: paths.Footprint, cur: dict) -> None:
    try:
        foot.cursors.parent.mkdir(parents=True, exist_ok=True)
        foot.cursors.write_text(json.dumps(cur), encoding="utf-8")
    except OSError as e:  # fail-open: a cursor that can't persist just means a fuller re-scan next run
        debuglog.exception(foot.root, "import.cursors-save", e)


def _file_sig(f: Path):
    try:
        st = f.stat()
        return [st.st_size, st.st_mtime]
    except OSError:
        return None


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def last_import(root: Path) -> str | None:
    """ISO timestamp of the last `cage import` run over this ledger, or ``None`` if it has
    never run. Capture is pull-based (no daemon), so `cage doctor`/`cage report` surface
    this as "last import: N ago" and nudge when stale (plan §3.7)."""
    return _load_cursors(paths.Footprint(root)).get("_last_import")


def _scan(root: Path, agent: str, src: Path, pattern: str, since,
          *, pol: dict | None = None, agent_cursor: dict | None = None) -> list[Path]:
    """The files to ingest, honoring ``--since`` and the incremental cursor. Files whose
    (size, mtime) match the cursor are dropped — already fully ingested, nothing new to
    parse. Records observational ``skip=since-filtered`` / ``skip=cursor-unchanged`` debug
    events when files existed but were all dropped (a common "why nothing captured?" cause).
    ``agent_cursor=None`` (the standalone import-claude/-codex commands) ⇒ no skip.
    Every candidate source gets a metadata-only ``probe`` event (path, exists, files
    matched) so `CAGE_DEBUG=1` answers "which locations did cage look at, and which
    missed" — the raw feed behind `cage doctor --paths`."""
    if src.is_dir():
        raw = sorted(src.glob(pattern))
    elif src.is_file():
        raw = [src]  # a file source (kiro's token log, an explicit --path file)
    else:
        raw = []  # absent location — a normal miss, recorded by the probe event
    debuglog.event(root, pol=pol, event="probe", agent=agent, src=str(src),
                   pattern=pattern, exists=src.exists(), files_matched=len(raw))
    cut = ledger.since_cutoff(since)  # reuses constants.SINCE_WINDOW_DAYS — no new literal
    if cut is None:
        files = raw
    else:
        files = [f for f in raw if _mtime_utc(f) is not None and _mtime_utc(f) >= cut]
        if raw and not files:
            debuglog.event(root, pol=pol, event="import", agent=agent, skip="since-filtered",
                           src=str(src), candidates=len(raw))
    if agent_cursor is not None and files:
        fresh = [f for f in files if _file_sig(f) != agent_cursor.get(str(f))]
        if not fresh:
            debuglog.event(root, pol=pol, event="import", agent=agent, skip="cursor-unchanged",
                           src=str(src), candidates=len(files))
        files = fresh
    return files


def _ingest(root: Path, agent: str, src: Path, files: list[Path], parse,
            *, pol: dict | None = None, seen: set | None = None,
            agent_cursor: dict | None = None) -> int:
    """Parse + dedupe-append each file; returns #appended. Records a metadata-only
    import-detail event (src, #files, #parsed, #appended, #deduped) and turns the
    previously-silent per-file `except` into a recorded `debuglog.exception` — still
    fail-open (a broken transcript never aborts the scan), but the traceback survives.

    ``seen`` (the run-shared, already-known call-id set) is threaded into `append_new`
    so the 22k-row ledger is read once per run, not once per file. After a file ingests
    cleanly its (size, mtime) is written to ``agent_cursor`` so the next run skips it."""
    total = parsed = 0
    for f in files:
        try:
            rows = parse(f)
            if not rows and f.is_file() and f.stat().st_size > 0:
                # A non-empty log parsing to 0 rows is the format-drift signature
                # (handoff §8) — recorded so "why nothing captured?" is answerable.
                debuglog.event(root, pol=pol, event="import", agent=agent,
                               skip="parsed-zero-rows", file=str(f), bytes=f.stat().st_size)
            parsed += len(rows)
            total += hooks.append_new(root, rows, seen)
            if agent_cursor is not None:
                sig = _file_sig(f)
                if sig is not None:
                    agent_cursor[str(f)] = sig
        except Exception as e:  # fail-open: a broken/unreadable transcript never aborts the scan
            debuglog.exception(root, "import.ingest", e, pol=pol, agent=agent, file=str(f))
            continue
    debuglog.event(root, pol=pol, event="import", agent=agent, result="ok", src=str(src),
                   files=len(files), parsed=parsed, appended=total, deduped=parsed - total)
    return total


def import_claude(root: Path, args, *, pol: dict | None = None, seen: set | None = None,
                  agent_cursor: dict | None = None) -> tuple[int, int]:
    """Meter Claude Code from the transcripts it already writes to ~/.claude/projects."""
    if getattr(args, "path", None):
        sources = [(Path(args.path), "**/*.jsonl")]
    elif getattr(args, "project", None):
        sources = [(paths.claude_home() / "projects"
                    / paths.claude_project_slug(Path(args.project)), "**/*.jsonl")]
    else:
        sources = [(s.path, s.glob) for s in paths.agent_log_sources("claude", pol)]
    total_rows = total_files = 0
    for src, pattern in sources:
        files = _scan(root, "claude", src, pattern, getattr(args, "since", None), pol=pol,
                      agent_cursor=agent_cursor)
        total_rows += _ingest(root, "claude", src, files,
                              lambda f: transcript.parse_calls(f, session=f.stem),
                              pol=pol, seen=seen, agent_cursor=agent_cursor)
        total_files += len(files)
    return total_rows, total_files


def import_codex(root: Path, args, *, pol: dict | None = None, seen: set | None = None,
                 agent_cursor: dict | None = None) -> tuple[int, int]:
    """Meter Codex from its on-disk rollouts (~/.codex/sessions/**/rollout-*.jsonl)."""
    sources = ([(Path(args.path), "**/rollout-*.jsonl")] if getattr(args, "path", None)
               else [(s.path, s.glob) for s in paths.agent_log_sources("codex", pol)])
    total_rows = total_files = 0
    for src, pattern in sources:
        files = _scan(root, "codex", src, pattern, getattr(args, "since", None), pol=pol,
                      agent_cursor=agent_cursor)
        total_rows += _ingest(root, "codex", src, files,
                              lambda f: transcript.parse_codex_calls(f, session=f.stem),
                              pol=pol, seen=seen, agent_cursor=agent_cursor)
        total_files += len(files)
        # Latest-only Codex quota snapshot — a machine-local state file, NOT a ledger row
        # (plan §3.8). Fail-open: never blocks the import; a renamed/absent block writes nothing.
        limits.snapshot_codex(root, files)
    return total_rows, total_files


def _parse_copilot_any(f: Path) -> list[dict]:
    """Dispatch on the on-disk store: VS Code chat-session files (extension) parse via
    `parse_copilot_vscode_calls`; everything else is the CLI `events.jsonl` format."""
    if f.parent.name == "chatSessions":
        return transcript.parse_copilot_vscode_calls(f, session=f.stem)
    return transcript.parse_copilot_calls(f, session=f.parent.name)


# The parser to reuse per declared `[sources.<name>] format` (plan Phase 4). The four
# built-in import fns above inline the same callables; a custom tool routes through
# here by its declared format so no new parser is ever written for a custom source.
_PARSERS = {"claude": lambda f: transcript.parse_calls(f, session=f.stem),
            "codex": lambda f: transcript.parse_codex_calls(f, session=f.stem),
            "copilot": _parse_copilot_any,
            "kiro": lambda f: transcript.parse_kiro_calls(f)}


def import_custom_tools(root: Path, args, *, pol: dict | None = None,
                        seen: set | None = None, cursors: dict | None = None) -> list[str]:
    """Meter every `[sources.<name>]` custom tool (a name that is not one of the four
    agents, plan Phase 4). Each reuses its declared-format parser and stamps
    ``agent = <name>`` on the rows, so `cage report`/`attrib` split it out naturally.
    Same `_scan`/`_ingest`/cursor/dedupe/fail-open path as the built-ins; a custom
    tool gets its own cursor bucket (keyed on the resolved file path, like every
    other source). Returns one summary line per tool that imported anything."""
    by_tool: dict[str, list] = {}
    for s in paths.custom_tool_sources(pol):
        by_tool.setdefault(s.agent, []).append(s)
    out: list[str] = []
    for name in sorted(by_tool):
        n = m = 0
        agent_cursor = cursors.setdefault(name, {}) if cursors is not None else None
        for s in by_tool[name]:
            files = _scan(root, name, s.path, s.glob, getattr(args, "since", None),
                          pol=pol, agent_cursor=agent_cursor)
            base_parse = _PARSERS[s.fmt]
            # Reuse the declared format's parser, then restamp `agent` to the tool name
            # (the parser stamps its own format's agent, e.g. "claude-code").
            parse = lambda f, _p=base_parse, _n=name: [{**r, "agent": _n} for r in _p(f)]
            n += _ingest(root, name, s.path, files, parse,
                         pol=pol, seen=seen, agent_cursor=agent_cursor)
            m += len(files)
        if m:
            out.append(f"✔ {name} (custom, format={by_tool[name][0].fmt}): "
                       f"imported {n} call(s) from {m} file(s).")
    return out


def import_copilot(root: Path, args, *, pol: dict | None = None, seen: set | None = None,
                   agent_cursor: dict | None = None) -> tuple[int, int]:
    """Meter Copilot from both stores it actually writes:

    - CLI: `~/.copilot/session-state/*/events.jsonl` (usage in `session.shutdown`;
      the session dir name is the session id);
    - VS Code extension: `<vscode-user>/workspaceStorage/*/chatSessions/*.jsonl` —
      the extension's own transcripts dir carries no usage event, so the per-request
      counts come from VS Code's chat-session store (plan §3.7; `CAGE_VSCODE_USER`
      overrides the user dir for tests)."""
    sources = ([(Path(args.path), "*/events.jsonl")] if getattr(args, "path", None)
               else [(s.path, s.glob) for s in paths.agent_log_sources("copilot", pol)])
    total_rows = total_files = 0
    for src, pattern in sources:
        files = _scan(root, "copilot", src, pattern, getattr(args, "since", None), pol=pol,
                      agent_cursor=agent_cursor)
        total_rows += _ingest(root, "copilot", src, files, _parse_copilot_any,
                              pol=pol, seen=seen, agent_cursor=agent_cursor)
        total_files += len(files)
    return total_rows, total_files


def import_kiro(root: Path, args, *, pol: dict | None = None, seen: set | None = None,
                agent_cursor: dict | None = None) -> tuple[int, int]:
    """Meter Kiro from its append-only usage log (kiro.kiroagent/dev_data/
    tokens_generated.jsonl) — a single file, not a glob. Best-effort and idempotent."""
    sources = ([(Path(args.path), "*")] if getattr(args, "path", None)
               else [(s.path, s.glob) for s in paths.agent_log_sources("kiro", pol)])
    total_rows = total_files = 0
    for src, pattern in sources:
        files = _scan(root, "kiro", src, pattern, getattr(args, "since", None), pol=pol,
                      agent_cursor=agent_cursor)
        total_rows += _ingest(root, "kiro", src, files, lambda f: transcript.parse_kiro_calls(f),
                              pol=pol, seen=seen, agent_cursor=agent_cursor)
        total_files += len(files)
    return total_rows, total_files


_ADAPTERS = {"claude": import_claude, "codex": import_codex,
             "copilot": import_copilot, "kiro": import_kiro}


def proxy_line(agent: str) -> str:
    """The supported hookless path for an agent that writes no usage transcript."""
    return f"· {agent}: no on-disk usage log — meter via the proxy: cage data meter -- <cmd>"


def run_agent(root: Path, agent: str, args, *, pol: dict | None = None,
              seen: set | None = None, agent_cursor: dict | None = None) -> str:
    if agent in _ADAPTERS:
        n, m = _ADAPTERS[agent](root, args, pol=pol, seen=seen, agent_cursor=agent_cursor)
        return f"✔ {agent}: imported {n} call(s) from {m} file(s)."
    debuglog.event(root, pol=pol, event="import", agent=agent, result="proxy",
                   note="no on-disk usage log")
    return proxy_line(agent)


def _load_policy(root: Path) -> dict:
    """Load policy fail-open: a malformed `policy.toml` (e.g. a duplicate `[debug]` table
    that makes `tomllib` raise) must degrade to the bundled default + a recorded debug
    event, never traceback out of the capture path (plan §3.7)."""
    try:
        return policy.load(paths.Footprint(root).policy)
    except Exception as e:  # fail-open: a broken project policy never aborts capture
        debuglog.exception(root, "import.policy", e)
        return {}


def run(root: Path, agent: str, args) -> list[str]:
    """Dispatch to one agent or, for ``all`` (the default), every surface in order.

    Capture is global by default (plan §3.7): ``root`` is the resolved active sink
    (``--ledger``/``CAGE_BASE`` → project ``.cage/`` → global ``~/.cage``), so an import
    fired anywhere — including a user-level Copilot hook in a repo with no ``.cage/`` —
    lands in the one resolved ledger and never scatters a stray local footprint. Honors the
    consumer's capture switch (`[capture] enabled` / `CAGE_CAPTURE`): when off, hooks still
    fire but this no-ops, pausing metering without unwiring anything. The ledger ``seen``
    set and the per-agent cursors are built once and shared across every agent (one ledger
    read per run, unchanged files skipped). Fail-open on a malformed policy."""
    pol = _load_policy(root)
    debuglog.heartbeat(root, agent, "import", str(root), pol=pol)
    debuglog.event(root, pol=pol, event="import", agent=agent, resolved_root=str(root),
                   capture_enabled=policy.capture_enabled(pol))
    if not policy.capture_enabled(pol):
        debuglog.event(root, pol=pol, event="import", agent=agent, skip="capture-disabled",
                       resolved_root=str(root))
        return ["· capture disabled ([capture] enabled=false or CAGE_CAPTURE=0) — import skipped"]
    targets = agents.SURFACES if agent == "all" else (agent,)
    foot = paths.Footprint(root)
    # Serialize the read-check-append section: two sweeps racing here (two hooks, or a
    # hook + a manual import) must not both build `seen` before either commits, or the
    # same turn lands twice. Fail-open — an untakeable lock just falls back to the
    # id-dedupe backstop (see `_import_lock`).
    # Fail-open: a malformed `[sources]` entry is a debug-logged skip, never an error
    # (plan Phase 4). Doctor --paths / `cage query sources` surface these loudly.
    for problem in paths.resolve_log_sources(pol).problems:
        debuglog.event(root, pol=pol, event="import", agent=agent,
                       skip="bad-source", detail=problem)
    with _import_lock(foot, pol):
        cursors = _load_cursors(foot)
        seen = {c.get("id") for c in ledger.calls(root)}  # one ledger read shared across agents
        lines = [run_agent(root, a, args, pol=pol, seen=seen,
                           agent_cursor=cursors.setdefault(a, {})) for a in targets]
        # Custom tools ([sources.<name>], plan Phase 4) sweep on the umbrella `all`
        # import — the global capture path that grabs the whole stack.
        if agent == "all":
            lines += import_custom_tools(root, args, pol=pol, seen=seen, cursors=cursors)
        cursors["_last_import"] = _now_iso()  # pull-based staleness signal for doctor/report
        _save_cursors(foot, cursors)
    # Piggybacked state maintenance (plan §3.6.4): every hook/watch/export sweep
    # converges here — the one chokepoint. Throttled + fail-open inside; cage
    # installs no scheduler, so this is the only auto path cleanup ever gets.
    from cage import cleanup
    cleanup.maybe_run(root, pol)
    return lines
