"""`cage setup` — scaffold the `.cage/` footprint (policy + gitignored ledger)."""
from __future__ import annotations

import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover  (Python <3.11)
    tomllib = None

from cage import paths, policy

POINTER_START = "<!-- cage:start -->"
POINTER_END = "<!-- cage:end -->"
_POINTER = f"""{POINTER_START}
## Cage — LLM usage & savings ledger

This project meters LLM traffic into `.cage/` (a *flux*: $0, deterministic).

- Per chat: `cage insights chats` · graphify savings: `cage insights graphify` · per commit: `cage insights commits`
- Tokens and credits are recorded as *counts* — cage measures usage, never cost.
- The ledger carries token counts, never prompt text — PII-safe by construction.
- Edit pipeline order / capture switches in `.cage/cage.toml`.
{POINTER_END}"""


def _migrate_config(fp: paths.Footprint) -> str | None:
    """Rename a legacy ``policy.toml`` to ``cage.toml`` when it is the only config
    present. Idempotent (a `cage.toml` already there ⇒ no-op) and never destructive
    when both exist (the caller-visible warning names the leftover instead). Returns
    the new path string when a rename happened, else ``None``. Fail-open: an OS error
    on the rename is swallowed — capture keeps reading `policy.toml` via the fallback."""
    new = fp.base / "cage.toml"
    old = fp.base / "policy.toml"
    if old.exists() and not new.exists():
        try:
            old.rename(new)
            return str(new)
        except OSError:
            return None
    return None


def _stamp_cage_version(root: Path) -> None:
    """A freshly scaffolded ``cage.toml`` records which cage version created it — a
    historical fact, stamped once and never rewritten (the bundle itself carries no
    ``cage_version`` literal; `policy._bundled` derives it live, this just copies that
    live value at the moment of creation). ``mark_custom=False``: this is a version
    stamp, not a user edit — an unmarked ``[meta]`` header keeps reading as a plain
    bundled-shape table (`cage policy sync`'s ``_walk`` skips ``[meta]`` regardless,
    but a stray custom mark would still be a false "you edited this" signal). Fail-open
    would hide a real scaffold bug, so this raises like every other write in
    `tomledit` — it only ever runs right after a successful ``write_text`` above."""
    from cage import __version__, tomledit
    tomledit.set_table(root, ("meta",), {"cage_version": __version__}, mark_custom=False)


def run(root: Path, pointer: bool = True) -> dict:
    """Scaffold the `.cage/` footprint at ``root``. ``pointer=False`` skips writing the
    `CLAUDE.md` pointer — used by `cage setup --global`, which inits ``~/.cage`` and must
    never edit the user's home `CLAUDE.md`."""
    fp = paths.Footprint(root)
    fp.base.mkdir(parents=True, exist_ok=True)
    fp.ledger.mkdir(parents=True, exist_ok=True)
    migrated = _migrate_config(fp)  # legacy policy.toml → cage.toml (idempotent)
    if not fp.policy.exists():
        fp.policy.write_text(policy.default_toml(), encoding="utf-8")
        _stamp_cage_version(fp.root)
    # No prices.toml is ever scaffolded any more (USAGE-ONLY, ADR 0011). An existing
    # one from a pre-0.51 project is LEFT WHERE IT IS — cage never deletes a user's
    # file — and is simply no longer read; `cage doctor` says so.
    synced = sync_sources(fp)  # Directive A: materialize the active [sources] table
    _gitignore(fp)
    claude_md = str(_claude_pointer(root)) if pointer else ""
    return {"footprint": str(fp.base), "policy": str(fp.policy),
            "ledger": str(fp.ledger), "claude_md": claude_md,
            "migrated_config": migrated, "sources_synced": synced}


def sync_sources(fp: paths.Footprint) -> bool:
    """Materialize (or refresh) the cage-managed active ``[sources]`` block in this
    footprint's ``cage.toml`` from the built-in seed (capture-precision §3.6, Directive A).
    Regenerates ONLY the ``# cage:sources-start … end`` marker region, so user-added
    ``[[sources.<name>]]`` entries outside it survive. Returns True when the file changed.
    Fail-open: an OS error leaves the config as-is (capture just stays unconfigured, which
    doctor reports). ``cage setup --sync-sources`` calls this on an existing footprint."""
    try:
        if not fp.policy.exists():
            return False
        text = fp.policy.read_text(encoding="utf-8")
        new = paths.materialize_sources(text)
        if new != text:
            fp.policy.write_text(new, encoding="utf-8")
            return True
    except OSError:
        return False
    return False


def _gitignore(fp: paths.Footprint) -> None:
    gi = fp.base / ".gitignore"
    fresh = not gi.exists()
    lines = (gi.read_text(encoding="utf-8").splitlines() if not fresh else
             ["# Append-only event log — machine-local, may carry holdings counts.",
              "# Point CAGE_LEDGER at elgar to keep even the counts private (ADR-LAWS Law 4).",
              "ledger/",
              "# Generated dashboards.",
              "out/"])
    # Heal older footprints: state/ holds machine-local hook buffers (pending edits,
    # session state) — never commit them. Idempotent on re-run.
    needs_state = "state/" not in lines
    if needs_state:
        lines += ["# Machine-local hook buffers (pending edits, session state).", "state/"]
    # Same heal for output/: `--export` artifacts (`cage/viewexport.py`). They are
    # regenerable views of a machine-local ledger and every one carries a wall-clock
    # stamp, so committing them would churn a diff on every run for no shared value.
    needs_output = "output/" not in lines
    if needs_output:
        lines += ["# Exported report/insight artifacts (`--export`).", "output/"]
    if fresh or needs_state or needs_output:
        gi.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _claude_pointer(root: Path) -> Path:
    path = root / "CLAUDE.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# CLAUDE.md\n"
    if POINTER_START in text:
        head, _, rest = text.partition(POINTER_START)
        _, _, tail = rest.partition(POINTER_END)
        text = head + _POINTER + tail
    else:
        text = text.rstrip() + "\n\n" + _POINTER + "\n"
    path.write_text(text, encoding="utf-8")
    return path
