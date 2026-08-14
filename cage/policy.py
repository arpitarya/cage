"""Load `.cage/cage.toml` (legacy `policy.toml` read as a fallback) — pipeline order,
capture switches, cleanup and authorship settings (plan §3.3). The resolved filename
lives in one place, `paths.Footprint.policy`; this module never hard-codes it for the
project.

**This module survived USAGE-ONLY (ADR 0011) and its price surface did not.** 60+
modules import it, so deleting it was never an option; what went is everything that
existed to turn a token count into a dollar — `price_match`/`price`, the `[prices]`,
`[credits]` and `[billing]` sections, the `prices.toml` two-file merge, the model-id
normalization (`normalize_model`) and `[alias]` that only ever fed price matching, and
`prices_stale_days`/`display_usd`. What remains is routing and behaviour."""
from __future__ import annotations

import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover  (Python <3.11)
    tomllib = None

from cage import paths

DEFAULT_ORDER = ["graphify", "fux", "router", "compressor", "cache", "response-cache"]


# The bundled-seed filename (the ONLY place this literal lives — parallel to
# `Footprint.policy`, the project-side resolver). `data/prices.toml` was the vendor
# rate-card half of this pair until USAGE-ONLY (ADR 0011) deleted the money subsystem;
# there is one bundled file again.
_BUNDLED_POLICY = "cage.toml"


def _parse_bundled(name: str) -> dict:
    # is_file(), not exists(): bundled_data() is a Traversable (no .exists() in the
    # ABC) so the bundled data keeps loading when cage runs from cage.pyz.
    src = paths.bundled_data() / name
    if tomllib is None or not src.is_file():
        return {}
    with src.open("rb") as fh:
        return tomllib.load(fh)


def _bundled() -> dict:
    """The bundled default (`data/cage.toml`).

    ``[meta] cage_version`` is derived here, never read from a file: the bundle ships
    no such key (a hand-maintained literal drifted eleven releases before this), so
    every caller of `bundled_raw()`/`load()` always sees the *running* package version
    — a freshly scaffolded project's stamp derives
    from this one point. A project's own stamp (once scaffolded) is history and is
    never rewritten (`initcmd.run`)."""
    base = _parse_bundled(_BUNDLED_POLICY)
    from cage import __version__  # deferred: avoid any import-order coupling
    base.setdefault("meta", {})["cage_version"] = __version__
    return base


# Sections whose values are per-provider tables of rows: merge one level deeper so a
# project row shadows that one key without wiping the provider's bundled siblings.
# `[prices]`/`[credits]`/`[billing]`/`[alias]` were the members until USAGE-ONLY
# (ADR 0011). `[alias]` went with them: aliasing existed solely to route a router
# pseudo-model (`copilot/auto`) onto a real *price* row, and with no price table it
# resolves nothing. Nothing is two-level any more; the tuple stays because
# `_merge_section` is the one merge and a future per-provider section would rejoin it.
_TWO_LEVEL: tuple[str, ...] = ()
_SECTIONS = ("tools", "budgets", "quality", "ledger",
             "capture", "debug", "meta", "cleanup", "wiring",
             "display", "sources", "authorship")

# `[prices]`, `[credits]`, `[billing]` and `[alias]` are GONE (USAGE-ONLY, ADR 0011),
# and with them the two-file split this loader used to perform. A project that still has a
# `.cage/prices.toml` on disk keeps it — cage never deletes a user's file — but nothing
# reads it, and `cage doctor` says so rather than leaving it looking live.


def _merge_section(pol: dict, data: dict, section: str) -> None:
    """Merge one section of ``data`` onto ``pol`` in place — two-level deep for the
    per-provider row tables, a flat overlay otherwise. No-op when ``data`` lacks it."""
    if section not in data:
        return
    if section in _TWO_LEVEL:
        merged = dict(pol.get(section, {}))
        for prov, table in data[section].items():
            base = merged.get(prov)
            if isinstance(table, dict) and isinstance(base, dict):
                merged[prov] = {**base, **table}
            else:
                merged[prov] = table
        pol[section] = merged
    else:
        pol[section] = {**pol.get(section, {}), **data[section]}


def load(policy_path: Path | None = None) -> dict:
    """Project policy merged over the bundled default, returned as ONE merged dict.

    One file again since USAGE-ONLY (ADR 0011): the price sections that used to be read
    from a sibling `prices.toml` no longer exist, so there is nothing left to split and
    `[meta]` merges wholesale rather than per key. Tolerant of missing files; a
    no-project load returns the bundled default unchanged."""
    pol = _bundled()
    if tomllib is None or policy_path is None:
        return pol
    pdata = load_project_raw(policy_path)
    for section in _SECTIONS:
        _merge_section(pol, pdata, section)
    return pol


def bundled_raw() -> dict:
    """The bundled policy alone (no project merge) — origin attribution for
    `cage policy sync`/`doctor`, which need to know which side a value came from;
    :func:`load` deliberately erases that."""
    return _bundled()


def load_project_raw(policy_path: Path | None) -> dict:
    """The project policy.toml alone, un-merged; ``{}`` when absent. Parse errors
    propagate — the caller chooses fail-open (capture path) vs CageError (CLI)."""
    if not policy_path or not policy_path.exists() or tomllib is None:
        return {}
    with policy_path.open("rb") as fh:
        return tomllib.load(fh)


def tool_order(pol: dict) -> list[str]:
    return list(pol.get("tools", {}).get("order") or DEFAULT_ORDER)


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


def python_launcher(pol: dict) -> bool:
    """Persisted wiring mode (work/restricted-environments.md): shims + user-level
    wiring resolve cage through the interpreter only (`python3 -m cage` /
    `py -3 -m cage`), never probing or executing a `cage`/`cage.exe` binary — for
    endpoints where unknown exes are blocked. Policy ``[wiring] python_launcher``;
    default off (standard mode). Deliberately NOT env-overridable: `CAGE_RUN_PYTHON`
    is the *shim-runtime* no-rewire escape hatch, never a write-time mode switch —
    `cage setup`'s output must not depend on the caller's environment."""
    return bool(pol.get("wiring", {}).get("python_launcher", False))


def capture_enabled(pol: dict) -> bool:
    """Whether hook-driven `cage import` actually runs — the consumer's on/off switch
    for auto-metering, without unwiring any hooks. Env `CAGE_CAPTURE` overrides policy
    `[capture] enabled`; default on."""
    return _flag("CAGE_CAPTURE", pol, "capture", "enabled", True)


def capture_on_read_enabled(pol: dict) -> bool:
    """Whether a read (report / insights / MCP read tools) lazily sweeps the log registry
    before answering — the capture-on-read primary path (capture-architecture Phase 1).
    Env `CAGE_CAPTURE_ON_READ` (0/1) overrides policy `[capture] on_read`; default **on**.
    A *separate* switch from `capture_enabled`: `CAGE_CAPTURE=0` pauses ALL capture
    (explicit `cage import` included), while this pauses only the read-triggered sweep —
    the knob the determinism/golden suite pins off so a read never mutates the ledger
    under a fixed-ledger test. `--no-import` is the per-invocation equivalent."""
    return _flag("CAGE_CAPTURE_ON_READ", pol, "capture", "on_read", True)


def read_throttle_secs(pol: dict) -> int:
    """Seconds within which a second read won't re-sweep (capture-on-read throttle,
    keyed on the `_last_import` cursor — no new state file). Policy `[capture]
    read_throttle_secs` wins; `constants.CAPTURE_ON_READ_THROTTLE_SECS` covers an unset
    key (the DEFAULT_CONFIDENCE policy-preferred pattern); `0` disables the throttle."""
    from cage.constants import CAPTURE_ON_READ_THROTTLE_SECS
    try:
        return int(pol.get("capture", {}).get("read_throttle_secs",
                                              CAPTURE_ON_READ_THROTTLE_SECS))
    except (TypeError, ValueError):
        return CAPTURE_ON_READ_THROTTLE_SECS


def debug_enabled(pol: dict) -> bool:
    """Whether the capture path writes its metadata-only debug log + hook heartbeat
    (`cage/debuglog.py`). Env `CAGE_DEBUG` overrides policy `[debug] enabled`; default
    **off** — observability is opt-in, never on by default ($0, no file written)."""
    return _flag("CAGE_DEBUG", pol, "debug", "enabled", False)


def task_correlation_enabled(pol: dict) -> bool:
    """Whether the best-effort `task` backfill (plan §4 / Phase 4) runs — correlating an
    import against `tasks.jsonl` by session/time window. Default **off**: it ships
    disabled until validated against real correlated data (handoff §3), and its output is
    always its own `method`/confidence-tagged, never ground truth. Env
    `CAGE_TASK_CORRELATION` overrides policy `[capture] task_correlation`."""
    return _flag("CAGE_TASK_CORRELATION", pol, "capture", "task_correlation", False)


def cleanup_enabled(pol: dict) -> bool:
    """Whether the **automatic** state-dir sweep (`cleanup.maybe_run`, piggybacked on
    import) may run at all. Env `CAGE_CLEANUP` overrides policy `[cleanup] enabled`;
    default on. `enabled=false` means the auto path does nothing — no reminder — but
    is deliberately NOT consulted by a manually-typed `cage data cleanup` /
    `--apply`: an explicit command is always honored (the safer of the two readings —
    see `cleanup.py`'s module docstring). Cleanup only ever touches the closed
    state/ allowlist — never the ledger or policy — and since v0.37 the auto path
    never deletes anything either way; see `cleanup_warn`."""
    return _flag("CAGE_CLEANUP", pol, "cleanup", "enabled", True)


def cleanup_warn(pol: dict) -> bool:
    """Whether the auto sweep prints its stderr reminder when `cleanup_enabled` is
    true (it never deletes — `cage data cleanup --apply` is the only path that does).
    Env `CAGE_CLEANUP_WARN` overrides policy `[cleanup] warn`; default on."""
    return _flag("CAGE_CLEANUP_WARN", pol, "cleanup", "warn", True)


def cleanup_days(pol: dict) -> int:
    """Retention window for the cleanable state/ classes. Policy `[cleanup] days`
    wins; `constants.CLEANUP_DEFAULT_DAYS` covers an unset key (the
    DEFAULT_CONFIDENCE policy-preferred pattern)."""
    from cage.constants import CLEANUP_DEFAULT_DAYS
    try:
        return int(pol.get("cleanup", {}).get("days", CLEANUP_DEFAULT_DAYS))
    except (TypeError, ValueError):
        return CLEANUP_DEFAULT_DAYS


def import_stale_hours(pol: dict) -> int:
    """Age threshold (hours) past which the report footer's `last import: N ago`
    advice line renders (plan Phase 1.6) — it's advice, not a banner. Policy
    `[capture] import_stale_hours` wins; `constants.IMPORT_STALE_HOURS` covers an
    unset key (the DEFAULT_CONFIDENCE policy-preferred pattern). `0` restores the
    always-on line (documented opt-out of the gate)."""
    from cage.constants import IMPORT_STALE_HOURS
    try:
        return int(pol.get("capture", {}).get("import_stale_hours", IMPORT_STALE_HOURS))
    except (TypeError, ValueError):
        return IMPORT_STALE_HOURS


def authorship_capture(pol: dict) -> bool:
    """Whether the import sweep runs the **authorship pass** at all — reading each
    Claude transcript for the text of its proposed edits and matching it, transiently,
    against the added lines of the commits those edits fall inside (v2 P1).

    This is the one capture path that reads a repository's *diffs*, which is the widest
    PII surface cage has (plan §3.5 justifies repo-relative file paths; the line bodies
    themselves never persist). So it gets its own switch, separate from
    `capture_enabled`: someone can meter their spend and still decline to have cage
    look at their code. Off ⇒ no provenance row is ever written, every commit reads
    `unknown` by absence, and not one token or cost number moves.

    Env `CAGE_AUTHORSHIP` overrides policy `[authorship] capture`; default on."""
    return _flag("CAGE_AUTHORSHIP", pol, "authorship", "capture", True)


def authorship_estimate_hours(pol: dict) -> bool:
    """Whether the commit views may render an **estimated** human-hours figure
    (agent-vs-human v2 §4). The estimator is `wall-clock − agent turn-span`, floored
    at 0 — an inference, always shown with `~` and with its method named in the view's
    own footnote, never a measurement and never multiplied by a rate.

    This is the kill-switch the v1 removal bought: `false` and the column renders
    `— not recorded` unless a human attested it with `cage task time`. Env
    `CAGE_AUTHORSHIP_ESTIMATE` overrides policy `[authorship] estimate_hours`;
    default on (`constants.AUTHORSHIP_ESTIMATE_HOURS`)."""
    from cage.constants import AUTHORSHIP_ESTIMATE_HOURS
    return _flag("CAGE_AUTHORSHIP_ESTIMATE", pol, "authorship", "estimate_hours",
                 AUTHORSHIP_ESTIMATE_HOURS)


def authorship_max_est_gap(pol: dict) -> str:
    """The commit gap past which the hours estimate is **refused** rather than printed
    (`—`, with the reason named). Beyond it the wall clock has stopped describing the
    work — an overnight or weekend gap would read as hours at the keyboard — and fog is
    not rendered. A `--since`-shaped window string (`4h` / `2d`); policy
    `[authorship] max_est_gap` wins, `constants.AUTHORSHIP_MAX_EST_GAP` covers an
    unset key (the DEFAULT_CONFIDENCE policy-preferred pattern). An unparseable value
    falls back to the constant rather than disabling the guard — a malformed cap must
    never widen it."""
    from cage import ledger
    from cage.constants import AUTHORSHIP_MAX_EST_GAP
    v = pol.get("authorship", {}).get("max_est_gap", AUTHORSHIP_MAX_EST_GAP)
    v = str(v).strip() if v is not None else ""
    return v if ledger.valid_since(v) and v else AUTHORSHIP_MAX_EST_GAP


def import_before_export(pol: dict) -> bool:
    """Whether `cage data export` runs the all-agent import sweep before bundling, so a
    capture-only machine (hooks never fire under a VS Code extension) still ships a
    complete bundle. Policy `[capture] import_before_export`; the `--no-import`
    flag wins per invocation, and `CAGE_CAPTURE=0` / `[capture] enabled=false`
    already skip the sweep inside `importcmd.run` (precedence: flag > env > policy)."""
    return bool(pol.get("capture", {}).get("import_before_export", True))


def default_toml() -> str:
    """The `cage.toml` `cage setup` writes — a copy of the bundled default."""
    src = paths.bundled_data() / _BUNDLED_POLICY
    return src.read_text(encoding="utf-8")
