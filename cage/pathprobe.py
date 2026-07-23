"""`cage doctor --paths` — which log locations cage looked at, which missed, and why.

A read-only diagnostic (plan §3.7 troubleshooting): for every agent × candidate log
location on *this* machine it reports found/missing, files matched, parseable row
count, cursor state, and one `why` line per miss — then the active ledger sink and
the precedence chain that chose it. Filesystem-dependent output by design (it is a
diagnostic, not a derived view) but it **writes nothing**: no cursor updates, no
debug events, no ledger rows. Counts-never-content: paths and counts only.

The same facts stream into `debug.log` as ``probe`` events during a real
`CAGE_DEBUG=1 cage import`; this report is the on-demand, exportable rendering
(`cage doctor --bundle` includes it, home-prefix redacted like every member).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from cage import agents, importcmd, paths, transcript

# Location candidates that exist in cage's tables but have never been pinned against
# a real install on that OS — the report must say so rather than imply verification.
_UNVERIFIED_WINDOWS_KIRO = "UNVERIFIED-LAYOUT (inferred from VS Code-family; not pinned on a real Windows Kiro)"


def _parse_rows(agent: str, f: Path) -> int:
    """Parseable row count for one file — read-only, fail-open to 0."""
    try:
        if agent == "claude":
            return len(transcript.parse_calls(f, session=f.stem))
        if agent == "copilot":
            return len(importcmd._parse_copilot_any(f))
        if agent == "kiro":
            return len(transcript.parse_kiro_calls(f))
    except Exception:  # noqa: BLE001 — a broken file is a why-line, not a crash
        return 0
    return 0


def _cursor_map(root: Path) -> dict:
    try:
        raw = json.loads(paths.Footprint(root).cursors.read_text(encoding="utf-8"))
        return {k: v for k, v in raw.items() if isinstance(v, dict)}
    except (OSError, ValueError):
        return {}


def _why(exists: bool, n_files: int, pattern: str, rows: int, fresh: int) -> str:
    if not exists:
        return "location absent (agent not installed, never ran, or a different layout — see candidates)"
    if n_files == 0:
        return f"no files match {pattern}"
    if rows == 0:
        return "parse: 0 rows — unknown format? run CAGE_DEBUG=1 cage import and see debug.log"
    if fresh == 0:
        return "cursor: already imported (nothing new)"
    return ""


def _probe_source(fmt: str, cursor_key: str, src: Path, pattern: str,
                  cursors: dict) -> dict:
    """One candidate's found/missing/parse/cursor facts. ``fmt`` selects the parser
    (a custom tool reuses a declared format); ``cursor_key`` is the row-stamp name the
    cursor bucket is keyed on (the tool/agent name, which for a custom tool ≠ fmt)."""
    exists = src.exists()
    if src.is_dir():
        files = sorted(src.glob(pattern))
    elif src.is_file():
        files = [src]
    else:
        files = []
    rows = sum(_parse_rows(fmt, f) for f in files)
    agent_cursor = cursors.get(cursor_key, {})
    fresh = sum(1 for f in files
                if agent_cursor.get(str(f)) != importcmd._file_sig(f))
    return {"src": str(src), "pattern": pattern, "exists": exists,
            "files": len(files), "rows": rows, "fresh_files": fresh,
            "why": _why(exists, len(files), pattern, rows, fresh)}


def _candidate_lines(label: str, env_var: str, candidates: list[Path],
                     chosen: Path, note_last: str = "") -> list[str]:
    env = os.environ.get(env_var)
    out = [f"    {label} candidates (env {env_var}: {'set' if env else 'unset'}):"]
    for i, c in enumerate(candidates):
        mark = "✔" if c.exists() else "✗"
        tags = []
        if c == chosen:
            tags.append("chosen")
        if note_last and i == len(candidates) - 1 and not env and os.environ.get("APPDATA"):
            tags.append(note_last)
        tag = f"  [{' · '.join(tags)}]" if tags else ""
        out.append(f"      {mark} {c}{tag}")
    return out


def _git_tracked(root: Path, path: Path) -> bool:
    """Fail-open: is ``path`` git-tracked under ``root``? (Shelled, never imported —
    the tasks.py rule; any failure ⇒ False, no portability note.)"""
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch",
                            str(path)], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:  # noqa: BLE001 — diagnostics only
        return False


def _machine_absolute(raw: str) -> bool:
    """A policy source path that a teammate's clone can't resolve — an absolute
    filesystem path, *not* a portable ``~``/``$VAR`` form (plan Phase 4 portability
    guard). ``~/x`` and ``$HOME/x`` resolve per-machine; ``/Users/me/x`` does not."""
    if not raw or raw.startswith("~") or "$" in raw:
        return False
    import re as _re
    return raw.startswith("/") or bool(_re.match(r"[A-Za-z]:[\\/]", raw))


def probe(root: Path, pol: dict | None = None) -> dict:
    """The probe data — read-only over the single `paths.resolve_log_sources` (built-in
    + `[sources]` policy, provenance-tagged). Never writes (cursors are read, not
    updated). Groups sources by agent/tool in SURFACES-then-custom order; surfaces the
    resolver's ``problems``/``disabled``, cross-agent path overlaps, and — for a
    committed *project* policy — machine-absolute source paths that break clones."""
    cursors = _cursor_map(root)
    res = paths.resolve_log_sources(pol)
    groups: dict[str, list] = {a: [] for a in agents.SURFACES}  # SURFACES first, in order
    for s in res.sources:
        d = _probe_source(s.fmt, s.agent, s.path, s.glob, cursors)
        d.update(provenance=s.provenance, raw=s.raw, fmt=s.fmt,
                 custom=s.agent not in agents.SURFACES)
        groups.setdefault(s.agent, []).append(d)

    from collections import defaultdict
    by_path: dict[str, set] = defaultdict(set)
    for s in res.sources:
        by_path[str(s.path)].add(s.agent)
    overlaps = {p: sorted(a) for p, a in by_path.items() if len(a) > 1}

    # Portability: a committed *project* policy carrying a machine-absolute source path
    # ships one dev's filesystem to the team. Global policy (~/.cage) is per-machine by
    # nature — exempt. `~`/`$VAR` paths are portable — exempt.
    port_warns: list[str] = []
    src_from = paths.active_ledger_source(root)
    if src_from.startswith("project"):
        pol_path = paths.Footprint(paths.resolve_root(root)).policy
        if _git_tracked(root, pol_path):
            for s in res.sources:
                if s.provenance == "policy" and _machine_absolute(s.raw):
                    port_warns.append(
                        f"[sources.{s.agent}] {s.raw} is a machine-absolute path in a "
                        "committed project policy — teammates' clones will probe a path "
                        "that doesn't exist; move it to ~/.cage/policy.toml or use ~/…")

    return {"platform": sys.platform, "agents": groups,
            "problems": res.problems, "disabled": res.disabled,
            "overlaps": overlaps, "portability": port_warns,
            "active_root": str(paths.resolve_root(root)),
            "active_source": src_from,
            "precedence": "override (--ledger/CAGE_BASE) → project (.cage/) → global (~/.cage)"}


def render_paths(root: Path, data: dict) -> str:
    lines = [f"Path probe · {data['platform']} · per agent × candidate log location", ""]
    from cage import agents
    disabled = set(data.get("disabled", []))
    for agent, sources in data["agents"].items():
        custom = bool(sources) and sources[0].get("custom")
        label = f"{agent}  (custom tool, format={sources[0]['fmt']})" if custom else agent
        lines.append(label)
        if agent in disabled:
            lines.append("  · disabled by policy ([sources] replace = true, paths = []) "
                         "— capture silenced for this agent")
        for s in sources:
            mark = "✔" if s["exists"] and s["rows"] else ("·" if s["exists"] else "✗")
            head = (f"  {mark} {s['src']}  ({s['pattern']})  [{s['provenance']}]  "
                    f"{s['files']} file(s) · {s['rows']} parseable row(s) · "
                    f"{s['fresh_files']} not yet imported")
            lines.append(head)
            if s["why"]:
                lines.append(f"      why: {s['why']}")
        if agent == "copilot":
            lines.extend(_candidate_lines("VS Code user dir", "CAGE_VSCODE_USER",
                                          paths.vscode_user_candidates(),
                                          paths.vscode_user_dir()))
        if agent == "kiro":
            lines.extend(_candidate_lines("Kiro user data", "KIRO_DATA_DIR",
                                          paths.kiro_data_candidates(),
                                          _kiro_chosen(), _UNVERIFIED_WINDOWS_KIRO))
    if data.get("overlaps"):
        lines.append("")
        for p, ags in sorted(data["overlaps"].items()):
            lines.append(f"⚠ overlap: {p} is declared for {', '.join(ags)} — "
                         "double-import is deduped by id, but this is likely a typo")
    if data.get("portability"):
        lines.append("")
        lines.extend(f"⚠ {w}" for w in data["portability"])
    if data.get("problems"):
        lines.append("")
        lines.extend(f"⚠ ignored: {p}" for p in data["problems"])
    lines += ["", "provenance: built-in (registry) · env (a home an env override "
              "redirected) · policy ([sources] in policy.toml)",
              f"active ledger: {data['active_source']} → {data['active_root']}",
              f"precedence:    {data['precedence']}"]
    return "\n".join(lines)


def _kiro_chosen() -> Path:
    return paths._first_existing(paths.kiro_data_candidates())


def run(root: Path, pol: dict | None = None) -> str:
    return render_paths(root, probe(root, pol))
