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
        if agent == "codex":
            return len(transcript.parse_codex_calls(f, session=f.stem))
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


def _probe_source(agent: str, src: Path, pattern: str, cursors: dict) -> dict:
    exists = src.exists()
    if src.is_dir():
        files = sorted(src.glob(pattern))
    elif src.is_file():
        files = [src]
    else:
        files = []
    rows = sum(_parse_rows(agent, f) for f in files)
    agent_cursor = cursors.get(agent, {})
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


def probe(root: Path) -> dict:
    """The probe data — read-only over `paths.agent_log_sources` + the candidate
    lists behind them. Never writes (cursors are read, not updated)."""
    cursors = _cursor_map(root)
    per_agent = {a: [_probe_source(a, src, pattern, cursors)
                     for src, pattern in paths.agent_log_sources(a)]
                 for a in agents.SURFACES}
    return {"platform": sys.platform, "agents": per_agent,
            "active_root": str(paths.resolve_root(root)),
            "active_source": paths.active_ledger_source(root),
            "precedence": "override (--ledger/CAGE_BASE) → project (.cage/) → global (~/.cage)"}


def render_paths(root: Path, data: dict) -> str:
    lines = [f"Path probe · {data['platform']} · per agent × candidate log location", ""]
    for agent, sources in data["agents"].items():
        lines.append(agent)
        for s in sources:
            mark = "✔" if s["exists"] and s["rows"] else ("·" if s["exists"] else "✗")
            head = (f"  {mark} {s['src']}  ({s['pattern']})  "
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
    lines += ["", f"active ledger: {data['active_source']} → {data['active_root']}",
              f"precedence:    {data['precedence']}"]
    return "\n".join(lines)


def _kiro_chosen() -> Path:
    return paths._first_existing(paths.kiro_data_candidates())


def run(root: Path) -> str:
    return render_paths(root, probe(root))
