"""ADR-OWNERSHIP — every module in `cage/` is claimed by exactly one ADR.

**The rule this enforces** (Arpit, 2026-08-14): *the ADRs are kept up to date, and a
change to the code does not land without its ADR updated in the same change.* That rule
is unusable unless "which ADR owns this file?" has an answer, so `docs/adr/README.md`
carries an ownership map and this test keeps it honest.

**What it actually catches, and why that is the useful moment.** A brand-new module in
`cage/` that no record claims is precisely a new decision being made with nothing to hold
it — the failure the rule exists to prevent, caught at the instant it is introduced rather
than on the next reader's confusion. It also catches the reverse: a record claiming a
module that no longer exists, which is a doc quietly describing deleted code.

**Deliberately NOT tested: whether an ADR was edited in the same commit as a code change.**
A test sees a snapshot, not a diff, so it cannot know. Pretending otherwise would be a
green check asserting nothing — the exact class of failure `test_cli_reference`'s
fence-blind code-span scan turned out to be. That half of the rule is carried by prose and
by review, and this file says so rather than implying coverage it does not have.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ADR_DIR = REPO / "docs" / "adr"

#: `module stem → the record that owns it`. Mirrors the *Which record owns what* table in
#: `docs/adr/README.md`; that table is for humans, this is the executable copy.
OWNERS: dict[str, str] = {
    # ADR-LAWS — the substrate the laws are about
    "ledger": "0001_laws", "schema": "0001_laws", "savings": "0001_laws",
    "units": "0001_laws", "paths": "0001_laws", "constants": "0001_laws",
    "errors": "0001_laws", "mergeutil": "0001_laws", "ids": "0001_laws",
    # ADR-CLI — the surface and how a view reaches a terminal
    "cli": "0002_cli", "clicmds": "0002_cli", "cliutil": "0002_cli",
    "verbmap": "0002_cli", "render": "0002_cli", "display": "0002_cli",
    "csvout": "0002_cli", "viewexport": "0002_cli", "runstamp": "0002_cli",
    "explain": "0002_cli", "explain_data": "0002_cli", "explain_types": "0002_cli",
    "chats": "0002_cli", "commitview": "0002_cli",
    # ADR-CLAUDE — the claude parser and its wiring, and nothing about authorship
    "claudewire": "0003_claude",
    # ADR-COPILOT / ADR-KIRO — thin wiring; their parsers live in the shared `transcript`
    "copilotwire": "0004_copilot",
    "kirowire": "0005_kiro",
    # ADR-CONSUMERS — the non-agent capture paths
    "metering": "0006_consumer", "usageparse": "0006_consumer",
    "usagelog": "0006_consumer", "manifest": "0006_consumer",
    "machine": "0006_consumer", "study": "0006_consumer",
    # ADR-AUTHORSHIP — who wrote which lines; cross-agent by decision, not claude's
    "authorcapture": "0009_authorship", "linematch": "0009_authorship",
    "commitjoin": "0009_authorship", "provenance": "0009_authorship",
    "origin": "0009_authorship", "originrecord": "0009_authorship",
    "notessync": "0009_authorship", "verifycmd": "0009_authorship",
    # ADR-GRAPHIFY — the interceptor and the tier-0 savings emitters
    "graphifychat": "0007_graphify", "graphifymeter": "0007_graphify",
    "graphifymodel": "0007_graphify", "graphifytx": "0007_graphify",
    "pathshim": "0007_graphify", "runshim": "0007_graphify",
    "adoptcmd": "0007_graphify", "compress": "0007_graphify",
    "responsecache": "0007_graphify",
}

#: Claimed by MORE than one record, on purpose. `transcript.py` is one file holding three
#: vendors' parsers; routing a copilot change to the claude record would send it to the
#: wrong reviewer, and splitting the file is a different decision than this test.
SHARED: dict[str, tuple[str, ...]] = {
    "transcript": ("0003_claude", "0004_copilot", "0005_kiro", "0009_authorship"),
    "importcmd": ("0003_claude", "0004_copilot", "0005_kiro", "0006_consumer",
                  "0009_authorship"),
    "agents": ("0003_claude", "0004_copilot", "0005_kiro"),
}

#: Infrastructure with no decision of its own — claimed **explicitly, never by silence**,
#: each with the reason it needs no record. Adding a name here is a claim that the module
#: encodes no decision; if it does, it belongs in `OWNERS` instead.
NO_RECORD: dict[str, str] = {
    "__init__": "package metadata and the version literal",
    "__main__": "`python -m cage` entry point",
    "attest": "L1 attestation store — behaviour is stated in CLAUDE.md's agent-surface ladder",
    "capturelog": "always-on capture breadcrumb; counts only, read by no view",
    "cfgio": "TOML/JSON read helpers",
    "cleanup": "state pruning; an allowlist, and never a ledger path",
    "debuglog": "the CAGE_DEBUG sink",
    "demo": "seeds the plan's worked example",
    "doctorbundle": "redacted diagnostics archive",
    "doctorcmd": "diagnoses the capture paths; owns no decision of its own",
    "freshness": "import-staleness advice line",
    "hookbypass": "L1 re-entry guard",
    "hookcmd": "L1 hook entry point — the ladder is CLAUDE.md's",
    "initcmd": "scaffolds .cage/",
    "lockutil": "the one fail-open cross-process lock helper",
    "mcpserver": "L2 surface — the tool list is CLAUDE.md's",
    "outcomes": "the task-outcome store",
    "pathprobe": "read-only path probe for doctor",
    "policy": "policy resolution",
    "policysync": "policy sync writer",
    "repoceiling": "repo-root resolution",
    "steering": "L1/L3 document rendering",
    "taskcorr": "task correlation helper",
    "taskgroup": "the one closed-task join",
    "tasks": "the task record",
    "tomledit": "the one comment-preserving TOML writer",
    "wiringscan": "wiring liveness detector",
}


def _modules() -> set[str]:
    return {p.stem for p in (REPO / "cage").glob("*.py")}


def _records() -> set[str]:
    return {p.stem for p in ADR_DIR.glob("0*.md")}


def test_every_module_is_claimed_by_a_record_or_explicitly_exempt():
    """A module claimed by nobody is a decision with nowhere to live."""
    unclaimed = sorted(_modules() - set(OWNERS) - set(SHARED) - set(NO_RECORD))
    assert not unclaimed, (
        "these modules are claimed by no ADR and are not on the explicit no-record list:\n  "
        + "\n  ".join(unclaimed)
        + "\n\nA new module is a new decision. Claim it in docs/adr/README.md's ownership "
          "table and in OWNERS here, or add it to NO_RECORD *with its reason*.")


def test_no_record_claims_a_module_that_no_longer_exists():
    """The reverse rot: a record describing code that was deleted."""
    modules = _modules()
    ghosts = sorted(
        {m for m in OWNERS if m not in modules}
        | {m for m in SHARED if m not in modules}
        | {m for m in NO_RECORD if m not in modules})
    assert not ghosts, (
        "these modules are claimed but do not exist — a record is describing deleted "
        "code:\n  " + "\n  ".join(ghosts))


def test_every_claimed_record_exists():
    """An ownership entry pointing at a record that was renamed or removed."""
    records = _records()
    named = set(OWNERS.values()) | {r for rs in SHARED.values() for r in rs}
    missing = sorted(named - records)
    assert not missing, (
        "ownership names records that do not exist in docs/adr/:\n  " + "\n  ".join(missing))


def test_the_readme_carries_the_human_copy_of_the_ownership_map():
    """Two copies exist by design — one executable, one readable. This pins them together
    at the level that matters: every record that owns code appears in the table."""
    readme = (ADR_DIR / "README.md").read_text(encoding="utf-8")
    assert "## Which record owns what" in readme, (
        "docs/adr/README.md must carry the ownership table this test mirrors")
    for record in sorted(set(OWNERS.values())):
        assert record in readme, (
            f"{record} owns modules but is absent from the ownership table in "
            "docs/adr/README.md")


def test_the_standing_rule_is_written_down():
    """The half of the rule no test can enforce must at least be stated."""
    readme = (ADR_DIR / "README.md").read_text(encoding="utf-8")
    assert "## The standing rule" in readme
    assert "no ADR affected" in readme, (
        "the rule needs its stated escape — without one it decays into ritual edits")
