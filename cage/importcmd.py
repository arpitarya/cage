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
  (`cage meter -- <cmd>`) stays the higher-fidelity fallback when Kiro's log is too thin.

Additive: hooks + MCP stay the default real-time path; this runs alongside them and
dedupes by call id (`hooks.append_new`), so a call seen by both a hook and an import is
counted once. Fail-open per file, idempotent on re-import, $0/stdlib, counts-never-content.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import agents, hooks, ledger, paths, policy, transcript

# Agents that persist a usage log to disk (everything else → proxy fallback).
LOG_BEARING = ("claude", "codex", "copilot", "kiro")


def _mtime_utc(f: Path):
    try:
        return _dt.datetime.fromtimestamp(f.stat().st_mtime, _dt.timezone.utc)
    except OSError:
        return None


def _scan(src: Path, pattern: str, since) -> list[Path]:
    files = sorted(src.glob(pattern)) if src.is_dir() else [src]
    cut = ledger.since_cutoff(since)  # reuses constants.SINCE_WINDOW_DAYS — no new literal
    if cut is not None:
        files = [f for f in files if _mtime_utc(f) is not None and _mtime_utc(f) >= cut]
    return files


def _ingest(root: Path, files: list[Path], parse) -> int:
    total = 0
    for f in files:
        try:
            total += hooks.append_new(root, parse(f))
        except Exception:  # fail-open: a broken/unreadable transcript never aborts the scan
            continue
    return total


def import_claude(root: Path, args) -> tuple[int, int]:
    """Meter Claude Code from the transcripts it already writes to ~/.claude/projects."""
    if getattr(args, "path", None):
        src = Path(args.path)
    elif getattr(args, "project", None):
        src = paths.claude_home() / "projects" / paths.claude_project_slug(Path(args.project))
    else:
        src = paths.claude_home() / "projects"
    files = _scan(src, "**/*.jsonl", getattr(args, "since", None))
    n = _ingest(root, files, lambda f: transcript.parse_calls(f, session=f.stem))
    return n, len(files)


def import_codex(root: Path, args) -> tuple[int, int]:
    """Meter Codex from its on-disk rollouts (~/.codex/sessions/**/rollout-*.jsonl)."""
    src = Path(args.path) if getattr(args, "path", None) else paths.codex_home() / "sessions"
    files = _scan(src, "**/rollout-*.jsonl", getattr(args, "since", None))
    n = _ingest(root, files, lambda f: transcript.parse_codex_calls(f, session=f.stem))
    return n, len(files)


def import_copilot(root: Path, args) -> tuple[int, int]:
    """Meter Copilot CLI from its per-session usage log
    (~/.copilot/session-state/*/events.jsonl). The session dir name is the session id,
    so usage is recorded under that even though the file itself is always `events.jsonl`."""
    src = Path(args.path) if getattr(args, "path", None) else paths.copilot_home() / "session-state"
    files = _scan(src, "*/events.jsonl", getattr(args, "since", None))
    n = _ingest(root, files, lambda f: transcript.parse_copilot_calls(f, session=f.parent.name))
    return n, len(files)


def import_kiro(root: Path, args) -> tuple[int, int]:
    """Meter Kiro from its append-only usage log (kiro.kiroagent/dev_data/
    tokens_generated.jsonl) — a single file, not a glob. Best-effort and idempotent."""
    src = Path(args.path) if getattr(args, "path", None) else paths.kiro_token_log()
    files = _scan(src, "*", getattr(args, "since", None))
    n = _ingest(root, files, lambda f: transcript.parse_kiro_calls(f))
    return n, len(files)


_ADAPTERS = {"claude": import_claude, "codex": import_codex,
             "copilot": import_copilot, "kiro": import_kiro}


def proxy_line(agent: str) -> str:
    """The supported hookless path for an agent that writes no usage transcript."""
    return f"· {agent}: no on-disk usage log — meter via the proxy: cage meter -- <cmd>"


def run_agent(root: Path, agent: str, args) -> str:
    if agent in _ADAPTERS:
        n, m = _ADAPTERS[agent](root, args)
        return f"✔ {agent}: imported {n} call(s) from {m} file(s)."
    return proxy_line(agent)


def run(root: Path, agent: str, args) -> list[str]:
    """Dispatch to one agent or, for ``all`` (the default), every surface in order.

    No-ops outside a cage project (no `.cage/`): the user-level Copilot hook is global
    and fires in every repo, so this guard keeps it from scattering stray ledgers — it
    captures only where `cage init`/`cage setup` has run, scoped to cwd. Also honors the
    consumer's capture switch (`[capture] enabled` / `CAGE_CAPTURE`): when off, hooks
    still fire but this becomes a no-op, pausing metering without unwiring anything."""
    if not (root / ".cage").is_dir():
        return ["· no .cage here — run `cage init` first; import skipped"]
    if not policy.capture_enabled(policy.load(paths.Footprint(root).policy)):
        return ["· capture disabled ([capture] enabled=false or CAGE_CAPTURE=0) — import skipped"]
    targets = agents.SURFACES if agent == "all" else (agent,)
    return [run_agent(root, a, args) for a in targets]
