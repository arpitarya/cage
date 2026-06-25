"""Unified hookless metering — `cage import [--agent claude|codex|copilot|kiro|all]`.

One umbrella over the per-agent hookless paths. Cage targets the wire protocol, so a
metered call is the same row no matter which agent emitted it; only *how we recover it
without hooks* differs by agent:

- **claude / codex** persist a usage transcript to disk, so their hookless path is an
  on-disk **import** (`~/.claude/projects/**/*.jsonl`, `~/.codex/sessions/**/rollout-*.jsonl`).
- **copilot / kiro** expose no usage transcript (see `pointers.py`), so their hookless
  path is the **proxy** (`cage meter -- <cmd>`); `import` prints that supported fallback
  rather than silently skipping the agent.

Additive: hooks + MCP stay the default real-time path; this runs alongside them and
dedupes by call id (`hooks.append_new`), so a call seen by both a hook and an import is
counted once. Fail-open per file, idempotent on re-import, $0/stdlib, counts-never-content.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import agents, hooks, ledger, paths, transcript

# Agents that persist a usage transcript to disk (everything else → proxy fallback).
LOG_BEARING = ("claude", "codex")


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


_ADAPTERS = {"claude": import_claude, "codex": import_codex}


def proxy_line(agent: str) -> str:
    """The supported hookless path for an agent that writes no usage transcript."""
    return f"· {agent}: no on-disk usage log — meter via the proxy: cage meter -- <cmd>"


def run_agent(root: Path, agent: str, args) -> str:
    if agent in _ADAPTERS:
        n, m = _ADAPTERS[agent](root, args)
        return f"✔ {agent}: imported {n} call(s) from {m} file(s)."
    return proxy_line(agent)


def run(root: Path, agent: str, args) -> list[str]:
    """Dispatch to one agent or, for ``all`` (the default), every surface in order."""
    targets = agents.SURFACES if agent == "all" else (agent,)
    return [run_agent(root, a, args) for a in targets]
