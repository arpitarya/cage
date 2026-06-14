"""Load `.cage/policy.toml` — prices, pipeline order, budgets, quality (plan §3.3)."""
from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover  (Python <3.11)
    tomllib = None

from cage import paths

DEFAULT_ORDER = ["graphify", "fux", "router", "compressor", "cache", "response-cache"]


def _bundled() -> dict:
    src = paths.bundled_data_dir() / "policy.toml"
    if tomllib is None or not src.exists():
        return {}
    with src.open("rb") as fh:
        return tomllib.load(fh)


def load(policy_path: Path | None = None) -> dict:
    """Project policy merged over the bundled default. Tolerant of a missing file."""
    pol = _bundled()
    if policy_path and policy_path.exists() and tomllib is not None:
        with policy_path.open("rb") as fh:
            data = tomllib.load(fh)
        for section in ("prices", "tools", "budgets", "quality"):
            if section in data:
                merged = {**pol.get(section, {}), **data[section]}
                pol[section] = merged
    return pol


def tool_order(pol: dict) -> list[str]:
    return list(pol.get("tools", {}).get("order") or DEFAULT_ORDER)


def price(pol: dict, provider: str, model: str) -> dict:
    """Per-million-token price row for a model, or zeros if unpriced."""
    row = pol.get("prices", {}).get(provider, {}).get(model)
    return row or {"input": 0.0, "output": 0.0, "cache_read": 0.0}


def budgets(pol: dict) -> dict:
    b = pol.get("budgets", {})
    return {"session_usd": b.get("session_usd"), "daily_usd": b.get("daily_usd"),
            "on_exceed": b.get("on_exceed", "warn")}


def default_toml() -> str:
    """The policy.toml `cage init` writes — a copy of the bundled default."""
    src = paths.bundled_data_dir() / "policy.toml"
    return src.read_text(encoding="utf-8")
