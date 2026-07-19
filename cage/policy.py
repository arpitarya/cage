"""Load `.cage/policy.toml` — prices, pipeline order, budgets, quality (plan §3.3)."""
from __future__ import annotations

import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover  (Python <3.11)
    tomllib = None

from cage import paths
from cage.constants import (MODEL_EFFORT_SUFFIXES, MODEL_FAMILY_MIN_SEGMENTS,
                            MODEL_ROUTE_PREFIXES)

DEFAULT_ORDER = ["graphify", "fux", "router", "compressor", "cache", "response-cache"]
_ZERO_PRICE = {"input": 0.0, "output": 0.0, "cache_read": 0.0}


def _bundled() -> dict:
    # is_file(), not exists(): bundled_data() is a Traversable (no .exists() in the
    # ABC) so the bundled prices keep loading when cage runs from cage.pyz.
    src = paths.bundled_data() / "policy.toml"
    if tomllib is None or not src.is_file():
        return {}
    with src.open("rb") as fh:
        return tomllib.load(fh)


# Sections whose values are per-provider tables of rows: merge one level deeper so
# a project `[prices.anthropic."x"]` row shadows that one key without wiping the
# provider's bundled siblings. (Shallow provider-level replace was the pre-0.19
# behavior — a partial project table silently dropped every bundled row for that
# provider. Nothing legitimate relied on it: removing a row only ever meant falling
# back to family/none, and `cage setup` copies carry the full table anyway.)
_TWO_LEVEL = ("prices", "credits", "alias")
_SECTIONS = ("prices", "tools", "budgets", "quality", "human", "ledger",
             "capture", "debug", "credits", "alias", "meta", "cleanup", "wiring",
             "display", "sources")


def load(policy_path: Path | None = None) -> dict:
    """Project policy merged over the bundled default. Tolerant of a missing file."""
    pol = _bundled()
    if policy_path and policy_path.exists() and tomllib is not None:
        with policy_path.open("rb") as fh:
            data = tomllib.load(fh)
        for section in _SECTIONS:
            if section not in data:
                continue
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
    return pol


def bundled_raw() -> dict:
    """The bundled policy alone (no project merge) — origin attribution for
    `cage prices list`/`sync`/`doctor`, which need to know which side a row
    came from; :func:`load` deliberately erases that."""
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


def _common_prefix_segments(a: list[str], b: list[str]) -> int:
    """Count of equal leading hyphen-segments shared by two split model ids."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def normalize_model(model: str) -> str:
    """Canonical form for family matching: strip a known router prefix
    (`copilot/claude-opus-4.6` → `claude-opus-4.6`), fold `.` to `-` (Copilot's
    dotted ids vs Anthropic's dashed rows), drop trailing effort-tier segments
    (`…-codex-high` → `…-codex` — vendors bill every tier at the same rate).
    The route-prefix list is closed: an unknown `<x>/` prefix stays as-is so an
    unrecognized router surfaces UNPRICED, never silently priced."""
    m = model
    for pre in MODEL_ROUTE_PREFIXES:
        if m.startswith(pre):
            m = m[len(pre):]
            break
    segs = m.replace(".", "-").split("-")
    while len(segs) > 1 and segs[-1] in MODEL_EFFORT_SUFFIXES:
        segs.pop()
    return "-".join(segs)


def _alias_target(pol: dict, provider: str, model: str) -> str | None:
    """The `[alias.<provider>."<model>"] to = "prov/model"` route, if configured."""
    entry = pol.get("alias", {}).get(provider, {}).get(model)
    if isinstance(entry, dict):
        entry = entry.get("to")
    return entry if isinstance(entry, str) and entry else None


def price_match(pol: dict, provider: str, model: str) -> tuple[dict, str, str | None]:
    """Resolve a price row *and how it matched*:
    ``("exact" | "alias" | "family" | "none")``.

    A raw exact key wins. Next an explicit ``[alias]`` route (router pseudo-models
    like ``copilot/auto``) — explicit routing beats every heuristic; a dangling
    alias (target row missing) is ``none``, an explicit-but-broken route must
    surface UNPRICED rather than fall through to a guess. Then the family
    fallback over :func:`normalize_model`-canonical ids: the same-provider row
    sharing the most leading segments (≥ ``MODEL_FAMILY_MIN_SEGMENTS``, so brand +
    tier must agree — an ``opus`` id never borrows a ``sonnet`` price). The longest
    shared prefix wins; ties break on the lexicographically smallest key, so the
    result is independent of dict-insertion order — deterministic and stable.
    Method law: a match through normalization renders ``family`` even when the
    canonical forms are identical — only a byte-equal key is ``exact``.

    Returns ``(row, match, matched_key)`` — ``matched_key`` is the winning price-row
    key (for ``alias``, the ``prov/model`` target string). Never raises; a totally
    unknown model is ``(zeros, "none", None)`` so the caller can flag it UNPRICED
    rather than bill $0.
    """
    rows = pol.get("prices", {}).get(provider, {})
    if model in rows:
        return rows[model], "exact", model
    target = _alias_target(pol, provider, model)
    if target is not None:
        tprov, _, tmodel = target.partition("/")
        trow = pol.get("prices", {}).get(tprov, {}).get(tmodel)
        if trow is not None:
            return trow, "alias", target
        return dict(_ZERO_PRICE), "none", None
    want = normalize_model(model).split("-")
    best_key, best_n = None, 0
    for key in rows:
        n = _common_prefix_segments(want, normalize_model(key).split("-"))
        if n < MODEL_FAMILY_MIN_SEGMENTS:
            continue
        if n > best_n or (n == best_n and (best_key is None or key < best_key)):
            best_key, best_n = key, n
    if best_key is not None:
        return rows[best_key], "family", best_key
    return dict(_ZERO_PRICE), "none", None


def price(pol: dict, provider: str, model: str) -> dict:
    """Per-million-token price row for a model, or zeros if unpriced.

    Thin wrapper over :func:`price_match` for callers that only need the row
    (matrix, ``input_cost_usd``). Exact-or-family; see ``price_match`` for the
    match-kind / matched-key signal that ``report`` and ``doctor`` surface."""
    return price_match(pol, provider, model)[0]


def human_rates(pol: dict) -> dict:
    """The `[human]` block (rate, default minutes, per-type table, confidence)."""
    return pol.get("human", {})


def human_rate_source(pol: dict) -> tuple[float, str]:
    """Resolved default $/hr and its provenance: env override beats policy (§3.2).

    Env is explicit config, not entropy — `(ledger, policy, env) ⇒ tables` holds.
    """
    env = os.environ.get("CAGE_HUMAN_RATE")
    if env:
        try:
            return (float(env), "env")
        except ValueError:
            pass
    return (float(pol.get("human", {}).get("rate_usd_per_hr", 0.0)), "policy")


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
    """Persisted wiring mode (docs/restricted-environments.md): shims + user-level
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


def cleanup_enabled(pol: dict) -> bool:
    """Whether the state-dir maintenance sweep (`cage/cleanup.py`) may run — auto
    (piggybacked on import) and manual `cage data cleanup --apply` both honor it. Env
    `CAGE_CLEANUP` overrides policy `[cleanup] enabled`; default on. Cleanup only
    ever touches the closed state/ allowlist — never the ledger or policy."""
    return _flag("CAGE_CLEANUP", pol, "cleanup", "enabled", True)


def cleanup_days(pol: dict) -> int:
    """Retention window for the cleanable state/ classes. Policy `[cleanup] days`
    wins; `constants.CLEANUP_DEFAULT_DAYS` covers an unset key (the
    DEFAULT_CONFIDENCE policy-preferred pattern)."""
    from cage.constants import CLEANUP_DEFAULT_DAYS
    try:
        return int(pol.get("cleanup", {}).get("days", CLEANUP_DEFAULT_DAYS))
    except (TypeError, ValueError):
        return CLEANUP_DEFAULT_DAYS


def prices_stale_days(pol: dict) -> int:
    """Age threshold (days) past which the bundled prices count as stale
    (`cage/freshness.py`). Policy `[prices] stale_days` wins;
    `constants.PRICES_STALE_DAYS` covers an unset key (the DEFAULT_CONFIDENCE
    policy-preferred pattern). `0` disables the age signal — documented opt-out."""
    from cage.constants import PRICES_STALE_DAYS
    v = pol.get("prices", {}).get("stale_days", PRICES_STALE_DAYS)
    try:
        return int(v)
    except (TypeError, ValueError):
        return PRICES_STALE_DAYS


def display_usd(pol: dict) -> bool:
    """Whether `report`/`matrix`/the bare overview render dollar columns by default
    (plan Phase 2.5): tokens are the measurement, dollars an interpretation you ask
    for. Precedence: the per-invocation `--usd` flag (handled at the CLI) > env
    `CAGE_USD` > policy `[display] usd` > off. Display-only — pricing always
    computes underneath (budget guards, UNPRICED detection), and money-native
    views (budget/roi/verdict/compare/estimate) never consult this."""
    return _flag("CAGE_USD", pol, "display", "usd", False)


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


def import_before_export(pol: dict) -> bool:
    """Whether `cage data export` runs the all-agent import sweep before bundling, so a
    capture-only machine (hooks never fire under a VS Code extension) still ships a
    complete bundle. Policy `[capture] import_before_export`; the `--no-import`
    flag wins per invocation, and `CAGE_CAPTURE=0` / `[capture] enabled=false`
    already skip the sweep inside `importcmd.run` (precedence: flag > env > policy)."""
    return bool(pol.get("capture", {}).get("import_before_export", True))


def default_toml() -> str:
    """The policy.toml `cage setup` writes — a copy of the bundled default."""
    src = paths.bundled_data() / "policy.toml"
    return src.read_text(encoding="utf-8")
