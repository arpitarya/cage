"""Test helper for Directive A (capture-precision §3.6): `cage.toml [sources]` is the
ONLY source of log paths — the built-in registry is a seed, not a runtime fallback.

Pathless import tests used to rely on that fallback, with agent homes env-redirected by
the conftest autouse fixture (and often re-redirected per test). Now they must declare an
active `[sources]` table. `mkcage(root)` scaffolds `.cage/` and materializes a table whose
paths are the **env-var forms** of the built-in registry (`$CLAUDE_CONFIG_DIR/projects`,
`$COPILOT_HOME/session-state`, …). `resolve_log_sources` expands `$VAR` at import time
(`paths._expand_source`), so the table tracks whatever home a test sets — even *after*
`mkcage` runs — which the production frozen-absolute seed cannot. It replaces the old
`(root / ".cage").mkdir(...)` one-liner.
"""
from __future__ import annotations

from pathlib import Path

from cage import initcmd, metering, paths, policy

# Env-var forms of the built-in registry (paths.py `_builtin_log_sources`) — expanded at
# resolution time so a late `monkeypatch.setenv(...)` still takes effect.
_ENV_SEED = [
    {"name": "claude", "path": "$CLAUDE_CONFIG_DIR/projects", "glob": "**/*.jsonl",
     "path_globs": ["**/*.jsonl"]},
    {"name": "copilot", "path": "$COPILOT_HOME/session-state", "glob": "*/events.jsonl",
     "path_globs": ["**/events.jsonl"]},
    {"name": "copilot", "path": "$CAGE_VSCODE_USER/workspaceStorage",
     "glob": "*/chatSessions/*.jsonl", "path_globs": ["**/chatSessions/*.jsonl"]},
    # COPILOT-METRICS: two more chatSessions roots (`_builtin_log_sources`'s new
    # copilot tuples) — kept in sync so a test can exercise them via `mkcage`.
    {"name": "copilot", "path": "$CAGE_VSCODE_USER/globalStorage/emptyWindowChatSessions",
     "glob": "*.jsonl", "path_globs": ["**/emptyWindowChatSessions/*.jsonl"]},
    {"name": "copilot", "path": "$CAGE_VSCODE_USER/globalStorage/transferredChatSessions",
     "glob": "*.jsonl", "path_globs": ["**/transferredChatSessions/*.jsonl"]},
    {"name": "kiro", "path": "$KIRO_DATA_DIR/dev_data/tokens_generated.jsonl", "glob": "*",
     "path_globs": ["*"]},
]


def mkcage(root: Path) -> Path:
    """Scaffold ``root/.cage`` with an active env-var ``[sources]`` table (Directive A) and
    clear the policy cache so the fresh config is read. Returns ``root``."""
    fp = paths.Footprint(root)
    fp.base.mkdir(parents=True, exist_ok=True)
    fp.ledger.mkdir(parents=True, exist_ok=True)
    if not fp.policy.exists():
        fp.policy.write_text(policy.default_toml(), encoding="utf-8")
    fp.policy.write_text(paths.materialize_sources(fp.policy.read_text(encoding="utf-8"),
                                                   seed=_ENV_SEED), encoding="utf-8")
    metering._policy_for.cache_clear()
    return root
