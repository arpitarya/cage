"""Stage-2 human resolver: precedence chain + confidence ladder (criteria 1,2,2b,5)."""
from __future__ import annotations

import pytest

from cage import human, policy, schema


def _rcpt(**kw):
    kw.setdefault("tool", "human")
    kw.setdefault("actual", 0.0)
    return schema.make_receipt(**kw)


# ── criterion 1 — substrate: minutes validates, unknown unit raises, saved derived
def test_minutes_unit_validates_and_derives_saved():
    r = _rcpt(raw_alternative=90, unit="minutes")
    assert r["unit"] == "minutes" and r["saved"] == 90.0
    with pytest.raises(ValueError):
        _rcpt(raw_alternative=1, unit="bananas")


# ── criterion 2 — one test per precedence branch, exact figures + confidence ladder
def test_mode1_explicit_usd_measured():
    pol = policy.load(None)
    r = _rcpt(raw_alternative=150, unit="usd", method="measured", confidence=0.9)
    assert human.human_alternative_usd(r, pol) == (150.0, "measured", 0.9)


def test_mode1_explicit_usd_estimated():
    pol = policy.load(None)
    r = _rcpt(raw_alternative=150, unit="usd", method="estimated")
    assert human.human_alternative_usd(r, pol) == (150.0, "estimated", 0.7)


def test_mode2_minutes_with_receipt_rate():
    pol = policy.load(None)
    r = _rcpt(raw_alternative=90, unit="minutes", method="estimated",
              meta={"rate_usd_per_hr": 80})
    # 90 min / 60 * $80 = $120.00
    assert human.human_alternative_usd(r, pol) == (120.0, "estimated", 0.7)


def test_mode3_task_type_table():
    pol = policy.load(None)
    r = _rcpt(raw_alternative=0, unit="tokens", method="estimated",
              meta={"task_type": "feature"})
    # [human.tasks.feature] = 120 min @ $90/hr = $180.00, type-table confidence 0.5
    assert human.human_alternative_usd(r, pol) == (180.0, "estimated", 0.5)


def test_mode4_global_default():  # also criterion 5
    pol = policy.load(None)
    r = _rcpt(raw_alternative=0, unit="tokens", method="estimated")
    # [human] default 60 min @ $80/hr = $80.00, lowest confidence 0.3, never measured
    usd, method, conf = human.human_alternative_usd(r, pol)
    assert (usd, method, conf) == (80.0, "estimated", 0.3)
    assert method != "measured"


# ── criterion 2b — CAGE_HUMAN_RATE supersedes policy; provenance; determinism
def test_env_rate_supersedes_policy(monkeypatch):
    pol = policy.load(None)
    assert policy.human_rate_source(pol) == (80.0, "policy")
    monkeypatch.setenv("CAGE_HUMAN_RATE", "120")
    assert policy.human_rate_source(pol) == (120.0, "env")
    # mode-4 default now prices at the env rate: 60 min @ $120/hr = $120.00
    r = _rcpt(raw_alternative=0, unit="tokens")
    assert human.human_alternative_usd(r, pol)[0] == 120.0


def test_env_rate_determinism(monkeypatch):
    monkeypatch.setenv("CAGE_HUMAN_RATE", "100")
    pol = policy.load(None)
    r = _rcpt(raw_alternative=30, unit="minutes")
    a = human.human_alternative_usd(r, pol)
    b = human.human_alternative_usd(r, pol)
    assert a == b == (50.0, "estimated", 0.7)  # 30/60 * 100


def test_bad_env_rate_falls_back_to_policy(monkeypatch):
    monkeypatch.setenv("CAGE_HUMAN_RATE", "not-a-number")
    pol = policy.load(None)
    assert policy.human_rate_source(pol) == (80.0, "policy")


# ── criterion 7 (partial) — minutes_to_usd agrees with convert.saved_usd path
def test_minutes_to_usd_matches_resolver():
    pol = policy.load(None)
    r = _rcpt(raw_alternative=90, unit="minutes", meta={"rate_usd_per_hr": 80})
    # saved == raw_alternative (actual=0); both should yield $120.
    assert human.minutes_to_usd(r, pol) == 120.0
