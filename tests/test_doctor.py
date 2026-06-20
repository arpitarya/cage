"""`cage doctor` — the setup health check. Deterministic, writes nothing real."""
from __future__ import annotations

from cage import doctorcmd, initcmd


def _level(res, name):
    return next(c["level"] for c in res["checks"] if c["name"] == name)


def test_fresh_project_fails_on_footprint(proj):
    res = doctorcmd.run(proj)
    assert _level(res, "footprint") == "fail"
    assert res["status"] == "fail"  # worst level wins


def test_after_init_footprint_and_policy_pass(proj):
    initcmd.run(proj)
    res = doctorcmd.run(proj)
    assert _level(res, "footprint") == "ok"
    assert _level(res, "policy") == "ok"
    assert res["status"] != "fail"  # no hard failure once scaffolded


def test_ledger_roundtrip_always_ok(proj):
    # The round-trip uses a throwaway temp ledger, so it passes regardless of project.
    assert _level(doctorcmd.run(proj), "ledger") == "ok"


def test_doctor_records_nothing_in_the_project(proj):
    initcmd.run(proj)
    doctorcmd.run(proj)
    # No receipts.jsonl is created in the project — the smoke write is isolated.
    assert not (proj / ".cage" / "ledger" / "receipts.jsonl").exists()


def test_every_check_has_a_known_level(proj):
    res = doctorcmd.run(proj)
    names = {c["name"] for c in res["checks"]}
    assert names == {"tool", "footprint", "policy", "hooks", "interceptor", "ledger"}
    assert all(c["level"] in {"ok", "warn", "fail"} for c in res["checks"])
