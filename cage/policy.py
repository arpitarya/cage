"""Load `.cage/policy.toml` — prices, pipeline order, budgets, quality (plan §3.3)."""
from __future__ import annotations

import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover  (Python <3.11)
    tomllib = None

from cage import paths
from cage.constants import MODEL_FAMILY_MIN_SEGMENTS

DEFAULT_ORDER = ["graphify", "fux", "router", "compressor", "cache", "response-cache"]
_ZERO_PRICE = {"input": 0.0, "output": 0.0, "cache_read": 0.0}


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
        for section in ("prices", "tools", "budgets", "quality", "human", "ledger",
                        "capture", "debug", "credits"):
            if section in data:
                merged = {**pol.get(section, {}), **data[section]}
                pol[section] = merged
    return pol


def tool_order(pol: dict) -> list[str]:
    return list(pol.get("tools", {}).get("order") or DEFAULT_ORDER)


def _common_prefix_segments(a: list[str], b: list[str]) -> int:
    """Count of equal leading hyphen-segments shared by two split model ids."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def price_match(pol: dict, provider: str, model: str) -> tuple[dict, str, str | None]:
    """Resolve a price row *and how it matched*: ``("exact" | "family" | "none")``.

    Exact key wins. On a miss, fall back to the same-provider row sharing the most
    leading hyphen-segments with ``model`` (≥ ``MODEL_FAMILY_MIN_SEGMENTS``, so
    brand + tier must agree — an ``opus`` id never borrows a ``sonnet`` price). The
    longest shared prefix wins; ties break on the lexicographically smallest key, so
    the result is independent of dict-insertion order — deterministic and stable.

    Returns ``(row, match, matched_key)``. Never raises; a totally unknown model is
    ``(zeros, "none", None)`` so the caller can flag it UNPRICED rather than bill $0.
    """
    rows = pol.get("prices", {}).get(provider, {})
    if model in rows:
        return rows[model], "exact", model
    want = model.split("-")
    best_key, best_n = None, 0
    for key in rows:
        n = _common_prefix_segments(want, key.split("-"))
        if n < MODEL_FAMILY_MIN_SEGMENTS:
            continue
        if n > best_n or (n == best_n and (best_key is None or key < best_key)):
            best_key, best_n = key, n
    if best_key is not None:
        return rows[best_key], "family", best_key
    return dict(_ZERO_PRICE), "none", None


def price(pol: dict, provider: str, model: str) -> dict:
    """Per-million-token price row for a model, or zeros if unpriced.

    Thin wrapper over :func:`price_match` for callers that only need the row
    (matrix, ``input_cost_usd``). Exact-or-family; see ``price_match`` for the
    match-kind / matched-key signal that ``report`` and ``doctor`` surface."""
    return price_match(pol, provider, model)[0]


def human_rates(pol: dict) -> dict:
    """The `[human]` block (rate, default minutes, per-type table, confidence)."""
    return pol.get("human", {})


def human_rate_source(pol: dict) -> tuple[float, str]:
    """Resolved default $/hr and its provenance: env override beats policy (§3.2).

    Env is explicit config, not entropy — `(ledger, policy, env) ⇒ tables` holds.
    """
    env = os.environ.get("CAGE_HUMAN_RATE")
    if env:
        try:
            return (float(env), "env")
        except ValueError:
            pass
    return (float(pol.get("human", {}).get("rate_usd_per_hr", 0.0)), "policy")


def budgets(pol: dict) -> dict:
    b = pol.get("budgets", {})
    return {"session_usd": b.get("session_usd"), "daily_usd": b.get("daily_usd"),
            "on_exceed": b.get("on_exceed", "warn")}


def _flag(env_name: str, pol: dict, section: str, key: str, default: bool) -> bool:
    """A boolean switch: env override (`0/false/no/off` vs `1/true/yes/on`) beats the
    ``[section] key`` policy value, which beats ``default``. Env is explicit config, not
    entropy, so `(ledger, policy, env) ⇒ tables` still holds."""
    env = os.environ.get(env_name)
    if env is not None:
        v = env.strip().lower()
        if v in ("0", "false", "no", "off"):
            return False
        if v in ("1", "true", "yes", "on"):
            return True
    return bool(pol.get(section, {}).get(key, default))


def capture_enabled(pol: dict) -> bool:
    """Whether hook-driven `cage import` actually runs — the consumer's on/off switch
    for auto-metering, without unwiring any hooks. Env `CAGE_CAPTURE` overrides policy
    `[capture] enabled`; default on."""
    return _flag("CAGE_CAPTURE", pol, "capture", "enabled", True)


def debug_enabled(pol: dict) -> bool:
    """Whether the capture path writes its metadata-only debug log + hook heartbeat
    (`cage/debuglog.py`). Env `CAGE_DEBUG` overrides policy `[debug] enabled`; default
    **off** — observability is opt-in, never on by default ($0, no file written)."""
    return _flag("CAGE_DEBUG", pol, "debug", "enabled", False)


def default_toml() -> str:
    """The policy.toml `cage init` writes — a copy of the bundled default."""
    src = paths.bundled_data_dir() / "policy.toml"
    return src.read_text(encoding="utf-8")
