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


def test_init_gitignores_state_dir(proj):
    initcmd.run(proj)
    gi = (proj / ".cage" / ".gitignore").read_text()
    assert "state/" in gi   # machine-local hook buffers must never be committed
    assert "ledger/" in gi


def test_gitignore_heals_older_footprint(proj):
    # An older footprint missing `state/` gets healed on re-init, idempotently.
    fp = proj / ".cage"
    fp.mkdir(parents=True)
    (fp / ".gitignore").write_text("ledger/\nout/\n", encoding="utf-8")
    initcmd.run(proj)
    body = (fp / ".gitignore").read_text()
    assert "state/" in body
    initcmd.run(proj)  # re-run adds no duplicate
    assert (fp / ".gitignore").read_text().count("state/") == 1


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
        assert f"cage import --agent {a}" in detail  # all four now have an import path


def test_metering_matrix_shows_realtime_mechanism_when_wired(proj):
    # Once the agent is wired, the matrix names the real-time Stop capture path.
    from cage import agents
    initcmd.run(proj)
    agents.install(proj, ("claude", "codex"))
    detail = next(c["detail"] for c in doctorcmd.run(proj)["checks"] if c["name"] == "metering")
    assert "real-time Stop + backfill ✔" in detail
    assert "SessionStart-backfill" in detail  # named as the safety net in the summary
