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
## Cage — LLM cost & savings ledger

This project meters LLM traffic into `.cage/` (a *flux*: $0, deterministic).

- Spend so far: `cage report` · per-tool savings: `cage insights attrib` · budget: `cage insights budget`
- The ledger carries token *counts*, never prompt text — PII-safe by construction.
- Edit prices / budgets / pipeline order in `.cage/cage.toml`.
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


_PRICES_POINTER = (
    "# Model prices moved to prices.toml (edit with `cage prices set` / `sync`).\n"
    "# Routing decisions — [alias] and [tools.<tool>] price_at — stay here (they\n"
    "# describe your setup, not a vendor rate card). See `cage query prices-file`.\n")


def _cage_toml_has_prices(policy_path: Path) -> bool:
    """True if the policy file on disk declares a real ``[prices…]``/``[credits…]`` table
    — the signal a legacy in-``cage.toml`` project needs the price migration. A cheap
    header scan (never parses), so a `# moved to prices.toml` pointer never counts."""
    return paths._file_declares_prices(policy_path)


def _strip_price_sections(text: str) -> str:
    """Return ``text`` with every ``[prices…]``/``[credits…]`` table removed (header,
    body, and the comment block directly above it) and the ``[meta]`` price counters
    (prices_version/prices_date) dropped, with a one-line pointer left where the price
    block was. Comment-preserving text surgery — the non-price sections (and their
    comments) are untouched, so a migrated ``cage.toml`` reads exactly as before minus
    the vendor rows. Falls back to the original text if the result would not parse."""
    from cage import pricestoml
    lines = text.splitlines(keepends=True)
    n = len(lines)
    headers = [(i, pricestoml._header_path(l)) for i, l in enumerate(lines)]
    headers = [(i, p) for (i, p) in headers if p is not None]
    delete = [False] * n
    first_price_idx = None
    for k, (i, path) in enumerate(headers):
        end = headers[k + 1][0] if k + 1 < len(headers) else n
        if path and path[0] in ("prices", "credits"):
            if first_price_idx is None:
                first_price_idx = i
            for j in range(i, end):
                delete[j] = True
            j = i - 1  # swallow the comment block that documents this table
            while j >= 0 and not delete[j] and (lines[j].strip() == ""
                                                or lines[j].lstrip().startswith("#")):
                delete[j] = True
                j -= 1
        elif path == ["meta"]:
            for j in range(i + 1, end):
                if re.match(r"^\s*(prices_version|prices_date)\s*=", lines[j]):
                    delete[j] = True
    if first_price_idx is None:
        return text
    out: list[str] = []
    inserted = False
    for i in range(n):
        if delete[i]:
            if i == first_price_idx and not inserted:
                out.append(("\n" if out and out[-1].strip() else "") + _PRICES_POINTER + "\n")
                inserted = True
            continue
        out.append(lines[i])
    result = re.sub(r"\n{3,}", "\n\n", "".join(out))
    if tomllib is not None:  # never leave an unparseable cage.toml behind (fail-open)
        try:
            tomllib.loads(result)
        except (tomllib.TOMLDecodeError, ValueError):
            return text
    return result


def _migrate_prices(fp: paths.Footprint, prices_file: Path) -> str | None:
    """Move legacy in-``cage.toml`` prices into ``prices.toml`` (prices-toml plan §3).
    Money-neutral by construction: prices.toml is scaffolded from the installed bundle,
    then every project row that DIFFERS from the current bundle value is written back as
    a ``# cage:custom`` override (a row equal to the bundle resolves identically from the
    scaffold — nothing to move); the legacy tables are then stripped from ``cage.toml``.
    Idempotent (a present prices.toml ⇒ no-op — the both-present shadow warning handles
    it), fail-open (any OS/parse error leaves the config as-is, capture keeps reading the
    legacy prices via the fallback). Returns the new path string on a migration, else None."""
    if prices_file.exists() or tomllib is None:
        return None  # both-present is non-destructive; nothing to do when already split
    try:
        legacy = policy.load_project_raw(fp.policy)
    except Exception:  # noqa: BLE001 — malformed legacy config → leave it, fail-open
        return None
    try:
        prices_file.write_text(policy.default_prices_toml(), encoding="utf-8")  # scaffold
        from cage import pricestoml
        bundled = policy.bundled_raw()
        b_prices = bundled.get("prices", {})
        for prov, rows in (legacy.get("prices", {}) or {}).items():
            if not isinstance(rows, dict):
                continue
            for model, row in rows.items():
                if isinstance(row, dict) and row != b_prices.get(prov, {}).get(model):
                    pricestoml.set_price(fp.root, prov, model, row)  # differs ⇒ override
        b_credits = bundled.get("credits", {})
        for prov, rows in (legacy.get("credits", {}) or {}).items():
            if not isinstance(rows, dict):
                continue
            for model, row in rows.items():
                if isinstance(row, dict) and row != b_credits.get(prov, {}).get(model):
                    pricestoml.set_credit(fp.root, prov, model, row)
        b_meta = bundled.get("meta", {})
        p_meta = legacy.get("meta", {})
        stamp = {k: p_meta[k] for k in ("prices_version", "prices_date")
                 if k in p_meta and p_meta[k] != b_meta.get(k)}
        if stamp:
            pricestoml.update_meta(fp.root, stamp, target=prices_file)
        stripped = _strip_price_sections(fp.policy.read_text(encoding="utf-8"))
        fp.policy.write_text(stripped, encoding="utf-8")
        return str(prices_file)
    except OSError:
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
    `pricestoml` — it only ever runs right after a successful ``write_text`` above."""
    from cage import __version__, pricestoml
    pricestoml.set_table(root, ("meta",), {"cage_version": __version__}, mark_custom=False)


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
    # Prices split (prices-toml plan §3): move a legacy in-cage.toml price block into
    # prices.toml (money-neutral), else scaffold a fresh prices.toml from the bundle.
    prices_file = fp.base / paths.PRICES_FILENAME
    migrated_prices = _migrate_prices(fp, prices_file) \
        if _cage_toml_has_prices(fp.policy) else None
    if not prices_file.exists():
        prices_file.write_text(policy.default_prices_toml(), encoding="utf-8")
    synced = sync_sources(fp)  # Directive A: materialize the active [sources] table
    _gitignore(fp)
    claude_md = str(_claude_pointer(root)) if pointer else ""
    return {"footprint": str(fp.base), "policy": str(fp.policy),
            "prices": str(fp.prices), "ledger": str(fp.ledger), "claude_md": claude_md,
            "migrated_config": migrated, "migrated_prices": migrated_prices,
            "sources_synced": synced}


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
              "# Point CAGE_LEDGER at elgar to keep even the counts private (plan §10).",
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
