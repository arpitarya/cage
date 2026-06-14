"""Wire Cage into Codex CLI: register the MCP read server in ~/.codex/config.toml.

Codex metering is the proxy (`cage meter -- codex …`) or best-effort rollout import
(`cage import-codex`); the MCP server is the read surface. tomllib is read-only, so
the `[mcp_servers.cage]` block is appended as text, guarded for idempotency.
"""
from __future__ import annotations

from pathlib import Path

from cage import paths

_BLOCK = '\n[mcp_servers.cage]\ncommand = "cage"\nargs = ["mcp"]\n'
_MARKER = "[mcp_servers.cage]"


def _config(root: Path | None) -> Path:
    return paths.codex_home() / "config.toml"


def install(root: Path | None = None) -> dict:
    cfg = _config(root)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    if _MARKER not in text:
        cfg.write_text(text.rstrip() + "\n" + _BLOCK if text else _BLOCK.lstrip(),
                       encoding="utf-8")
    return {"config": str(cfg)}


def status(root: Path | None = None) -> bool:
    cfg = _config(root)
    return cfg.exists() and _MARKER in cfg.read_text(encoding="utf-8")
