"""Canonical ledger + routing key (capture-architecture Phase 1, §3.1/§9.6).

The load-bearing property, made permanent: a saving *pushed* from a repo subdirectory is
seen by a repo-root read, because push and pull resolve the SAME canonical ledger. Plus:
the routing key is stable, OS-stable, non-PII, absent by default (legacy byte-identity),
never part of an id; and the read-time reclaim backstop matches on the EXACT key only.
"""
from __future__ import annotations

from cage import ledger, metering, paths, policy, schema


# ── the verify-first test, made permanent: subdir push → repo-root read ────────

def test_subdir_push_is_seen_by_repo_root_read(tmp_path, monkeypatch):
    proj = tmp_path / "repo"
    (proj / ".cage").mkdir(parents=True)
    deep = proj / "pkg" / "deep"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)  # graphify/fux run from a subdirectory, not the repo root
    monkeypatch.delenv("CAGE_BASE", raising=False)

    # A push (record_receipt) from the subdir resolves UP to the project .cage/ …
    rid = metering.record_receipt(tool="graphify", unit="tokens",
                                  raw_alternative=900, actual=100)
    assert rid  # landed somewhere
    assert paths.canonical_ledger() == proj  # push and pull converge on the repo root

    # … and a repo-root read sees it — the "stranded saving" is a phantom here.
    monkeypatch.chdir(proj)
    seen = ledger.receipts(proj)
    assert any(r.get("id") == rid for r in seen)
    assert not (deep / ".cage").exists()  # no stray footprint scattered in the subdir


# ── routing key: stable, OS-stable, non-PII, absent-by-default, never in an id ─

def test_routing_key_stable_and_non_pii(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    k1 = paths.routing_key(root)
    k2 = paths.routing_key(root)
    assert k1 == k2                      # stable across calls
    assert k1 and len(k1) == 16          # a fixed-width hex digest
    assert str(root) not in k1           # non-PII: the path never travels, only its hash
    assert k1 != paths.routing_key(tmp_path / "other")  # distinct roots → distinct keys


def test_routing_key_os_stable_normalization(tmp_path):
    # Separator/case folding makes push and pull agree regardless of the shell that
    # resolved the path — a CI property (the class that breaks on Windows).
    root = tmp_path / "Repo"
    root.mkdir()
    import hashlib
    norm = str(root.resolve()).replace("\\", "/").casefold()
    assert paths.routing_key(root) == hashlib.sha256(norm.encode()).hexdigest()[:16]


def test_route_key_absent_by_default_and_never_in_id():
    legacy = schema.make_receipt(tool="graphify", raw_alternative=10, actual=4)
    assert "route_key" not in legacy      # additive: unset ⇒ byte-identical legacy row
    stamped = schema.make_receipt(tool="graphify", raw_alternative=10, actual=4,
                                  route_key="deadbeefcafef00d")
    assert stamped["route_key"] == "deadbeefcafef00d"
    assert "deadbeefcafef00d" not in stamped["id"]  # never part of the id
    assert stamped["id"].startswith("r")


def test_record_receipt_stamps_the_resolved_key(tmp_path, monkeypatch):
    proj = tmp_path / "repo"
    (proj / ".cage").mkdir(parents=True)
    monkeypatch.chdir(proj)
    monkeypatch.delenv("CAGE_BASE", raising=False)
    metering.record_receipt(tool="graphify", raw_alternative=50, actual=10)
    rows = ledger.receipts(proj)
    assert rows and rows[0]["route_key"] == paths.routing_key(proj)


# ── read-time reclaim: exact key only, never a blind union ─────────────────────

def _stray_global_receipt(route_key: str, saved: int = 100):
    """A graphify saving pushed to the GLOBAL ledger (tool ran outside the tree),
    tagged with an explicit routing key."""
    return metering.record_receipt(tool="graphify", unit="tokens", raw_alternative=saved,
                                   actual=0, root=paths.global_home(), route_key=route_key)

# ── The route_key RECLAIM backstop is GONE (SURFACE-CUT, 2026-08-14) ──────────
# `report.read_receipts` folded a global→project reclaim into every read: a saving
# pushed while the tool ran outside this project's tree was pulled back by EXACT
# route_key. It was called from nowhere but `report.summarize`/`render_overview`, so it
# died with `cage report` and no surviving view ever had it. The WRITE half above still
# stamps `route_key` on every pushed receipt, so the data to reclaim is still being
# recorded — only the reader is missing. Filed in work/OPEN-WORK.md; do not re-add a
# blind global→project union in its place (two repos sharing a basename would
# over-attribute, which is exactly what the exact-key match existed to prevent).
