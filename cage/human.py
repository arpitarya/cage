"""The Tier-1 human-labor resolver (design §3) — minutes/type/usd → (USD, method, conf).

A human receipt records the *input* (minutes / task_type / usd); money is **derived
here** at read time from current policy, so a rate change re-prices the backlog with
no ledger rewrite. `method` is sacred: a human cost is `estimated` unless the caller
asserts a real quote/timesheet — never `modeled`. Confidence ladders by how the
figure was obtained (§3) so round type-table guesses *read* as low-credibility.
"""
from __future__ import annotations

from cage import policy

_DEFAULT_CONF = {"measured": 0.9, "estimated": 0.7, "type_table": 0.5, "default": 0.3}


def _conf(pol: dict, key: str) -> float:
    return float(policy.human_rates(pol).get("confidence", {}).get(key, _DEFAULT_CONF[key]))


def _rate(receipt: dict, pol: dict) -> float:
    """Per-receipt rate beats the env/policy default (§3 mode 2, §3.2)."""
    meta = receipt.get("meta") or {}
    if meta.get("rate_usd_per_hr"):
        return float(meta["rate_usd_per_hr"])
    return policy.human_rate_source(pol)[0]


def _resolve(receipt: dict, pol: dict) -> tuple[float, float, str, float]:
    """`(usd, minutes, method, confidence)` — the one place the precedence chain lives.

    1 explicit USD · 2 per-receipt minutes · 3 task-type table · 4 global default.
    USD and minutes are always mutually consistent (usd = minutes/60 × the rate used).
    """
    unit = receipt.get("unit", "tokens")
    meta = receipt.get("meta") or {}
    measured = receipt.get("method") == "measured"
    est = "measured" if measured else "estimated"

    if unit == "usd":  # mode 1 — explicit dollar figure; minutes back-derived at rate
        usd = round(float(receipt.get("raw_alternative", 0.0)), 6)
        rate = _rate(receipt, pol) or 1.0
        return (usd, round(usd / rate * 60.0, 4), est, _conf(pol, est))

    if unit == "minutes":  # mode 2 — per-receipt minutes × rate
        mins = float(receipt.get("raw_alternative", 0.0))
        rate = _rate(receipt, pol)
        return (round(mins / 60.0 * rate, 6), mins, est, _conf(pol, est))

    tasks = policy.human_rates(pol).get("tasks", {})
    rate_default = policy.human_rate_source(pol)[0]
    if meta.get("task_type") in tasks:  # mode 3 — task-type table
        row = tasks[meta["task_type"]]
        rate = float(meta.get("rate_usd_per_hr") or row.get("rate_usd_per_hr") or rate_default)
        mins = float(row.get("minutes", 0))
        return (round(mins / 60.0 * rate, 6), mins, "estimated", _conf(pol, "type_table"))

    hr = policy.human_rates(pol)  # mode 4 — global default
    rate = float(meta.get("rate_usd_per_hr") or rate_default)
    mins = float(hr.get("default_minutes", 0))
    return (round(mins / 60.0 * rate, 6), mins, "estimated", _conf(pol, "default"))


def human_alternative_usd(receipt: dict, pol: dict) -> tuple[float, str, float]:
    """`(usd, method, confidence)` for a human receipt by the §3 precedence chain."""
    usd, _, method, conf = _resolve(receipt, pol)
    return (usd, method, conf)


def human_minutes(receipt: dict, pol: dict) -> float:
    """The avoided human labor in minutes (the §5b.1 time clock), consistent with USD."""
    return _resolve(receipt, pol)[1]


def minutes_to_usd(receipt: dict, pol: dict) -> float:
    """USD for a `minutes` receipt's `saved` (the convert.saved_usd dispatch path)."""
    minutes = float(receipt.get("saved", 0.0))
    return round(minutes / 60.0 * _rate(receipt, pol), 6)
