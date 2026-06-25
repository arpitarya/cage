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
    assert names == {"tool", "footprint", "policy", "pricing", "hooks", "metering",
                     "interceptor", "ledger"}
    assert all(c["level"] in {"ok", "warn", "fail"} for c in res["checks"])


def test_metering_matrix_lists_all_four_agents(proj):
    from cage import agents
    detail = next(c["detail"] for c in doctorcmd.run(proj)["checks"] if c["name"] == "metering")
    for a in agents.SURFACES:  # every surface is first-class — none silently dropped
        assert a in detail
    assert "cage import --agent claude" in detail   # log-bearing → import
    assert "cage meter -- <cmd>" in detail            # copilot/kiro → proxy


def test_metering_matrix_shows_wired_backfill_mechanism(proj):
    # Once SessionStart-backfill is wired, the matrix names the actual mechanism.
    from cage import agents
    initcmd.run(proj)
    agents.install(proj, ("claude",))
    detail = next(c["detail"] for c in doctorcmd.run(proj)["checks"] if c["name"] == "metering")
    assert "SessionStart-backfill" in detail
