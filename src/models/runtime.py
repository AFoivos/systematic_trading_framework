from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable, Mapping, Sequence

import os
import re
import subprocess
import sys

import pandas as pd

from src.models.lightgbm_baseline import default_feature_columns


_FEATURE_SELECTOR_OPERATORS = {"exact", "startswith", "endswith", "contains", "regex"}
_FEATURE_SELECTOR_ALLOWED_KEYS = {"profile", "families", "exact", "include", "exclude", "strict", "drift_filter"}
_FEATURE_FAMILY_ORDER = (
    "returns_lags",
    "volatility",
    "trend",
    "momentum",
    "regime",
    "session_time",
    "atr_adx_range",
    "cross_asset",
)
_FEATURE_SELECTOR_PROFILES: dict[str, tuple[str, ...]] = {
    "ftmo_fx_intraday_balanced_v1": (
        "returns_lags",
        "volatility",
        "trend",
        "momentum",
        "regime",
        "session_time",
        "atr_adx_range",
    ),
    "ftmo_fx_intraday_regime_v1": (
        "returns_lags",
        "volatility",
        "trend",
        "regime",
        "session_time",
        "atr_adx_range",
    ),
    "ftmo_fx_intraday_momentum_v1": (
        "returns_lags",
        "volatility",
        "trend",
        "momentum",
        "session_time",
        "atr_adx_range",
    ),
}


@lru_cache(maxsize=1)
def probe_lightgbm_runtime() -> tuple[bool, str | None]:
    code = """
import numpy as np
from lightgbm import LGBMClassifier
X = np.random.randn(32, 4).astype("float32")
y = (np.random.rand(32) > 0.5).astype("int32")
model = LGBMClassifier(
    n_estimators=4,
    learning_rate=0.1,
    num_leaves=15,
    n_jobs=1,
    random_state=7,
)
model.fit(X, y)
print("ok")
"""
    env = os.environ.copy()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, "child process probe timed out after 30s"
    if proc.returncode == 0:
        return True, None
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    detail = stderr or stdout or f"child process exited with code {proc.returncode}"
    return False, detail


@lru_cache(maxsize=1)
def probe_xgboost_runtime() -> tuple[bool, str | None]:
    """
    Probe whether the local Python/XGBoost runtime can complete a tiny fit safely.

    Some sandboxed or partially provisioned environments import xgboost successfully but abort
    during the first OpenMP-backed fit. We isolate the probe in a child process so the caller can
    degrade gracefully instead of taking down the parent experiment process.
    """
    code = """
import numpy as np
from xgboost import XGBClassifier
X = np.random.randn(32, 4).astype("float32")
y = (np.random.rand(32) > 0.5).astype("int32")
model = XGBClassifier(
    n_estimators=2,
    max_depth=2,
    learning_rate=0.1,
    tree_method="hist",
    objective="binary:logistic",
    eval_metric="logloss",
    n_jobs=1,
    seed=7,
)
model.fit(X, y)
print("ok")
"""
    env = os.environ.copy()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, "child process probe timed out after 30s"
    if proc.returncode == 0:
        return True, None
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    detail = stderr or stdout or f"child process exited with code {proc.returncode}"
    return False, detail


def ensure_lightgbm_runtime_available() -> None:
    available, detail = probe_lightgbm_runtime()
    if available:
        return
    raise RuntimeError(
        "LightGBM runtime is unavailable in the current environment. "
        f"Probe failure: {detail}"
    )


def ensure_xgboost_runtime_available() -> None:
    available, detail = probe_xgboost_runtime()
    if available:
        return
    raise RuntimeError(
        "XGBoost runtime is unavailable in the current environment. "
        f"Probe failure: {detail}"
    )


def resolve_runtime_for_model(
    model_cfg: dict[str, Any],
    model_params: dict[str, Any],
    *,
    estimator_family: str,
) -> dict[str, Any]:
    """
    Resolve reproducibility- and threading-related runtime settings for a model family.
    """
    runtime_cfg = dict(model_cfg.get("runtime", {}) or {})

    seed = runtime_cfg.get("seed", model_params.get("random_state", 7))
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("model.runtime.seed must be an integer >= 0.")

    deterministic = runtime_cfg.get("deterministic", True)
    if not isinstance(deterministic, bool):
        raise ValueError("model.runtime.deterministic must be a boolean.")

    repro_mode = runtime_cfg.get("repro_mode", "strict")
    if repro_mode not in {"strict", "relaxed"}:
        raise ValueError("model.runtime.repro_mode must be 'strict' or 'relaxed'.")

    threads = runtime_cfg.get("threads")
    if threads is not None and (not isinstance(threads, int) or threads <= 0):
        raise ValueError("model.runtime.threads must be null or a positive integer.")
    if repro_mode == "strict" and threads is None:
        threads = 1

    model_params.setdefault("random_state", seed)
    if estimator_family == "lightgbm":
        model_params.setdefault("seed", seed)
        if deterministic:
            model_params.setdefault("deterministic", True)
            model_params.setdefault("force_col_wise", True)
            model_params.setdefault("feature_fraction_seed", seed)
            model_params.setdefault("bagging_seed", seed)
            model_params.setdefault("data_random_seed", seed)
    if estimator_family == "xgboost":
        model_params.setdefault("seed", seed)
        if deterministic:
            model_params.setdefault("subsample", model_params.get("subsample", 1.0))
            model_params.setdefault("colsample_bytree", model_params.get("colsample_bytree", 1.0))

    if threads is not None:
        model_params.setdefault("n_jobs", threads)

    return {
        "seed": seed,
        "deterministic": deterministic,
        "threads": model_params.get("n_jobs", threads),
        "repro_mode": repro_mode,
    }


def _as_non_empty_string_list(value: Any, *, field: str) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        values = list(value)
    else:
        raise TypeError(f"{field} must be a non-empty string or list[str].")

    out: list[str] = []
    for idx, raw in enumerate(values):
        if not isinstance(raw, str) or not raw.strip():
            raise TypeError(f"{field}[{idx}] must be a non-empty string.")
        out.append(raw)
    if not out:
        raise ValueError(f"{field} must not be empty.")
    return out


def _iter_selector_rules(raw_rules: Any, *, field: str) -> list[tuple[str, list[str], str]]:
    if raw_rules in (None, []):
        return []
    if not isinstance(raw_rules, list):
        raise TypeError(f"{field} must be a list of selector mappings.")

    rules: list[tuple[str, list[str], str]] = []
    for idx, raw_rule in enumerate(raw_rules):
        rule_field = f"{field}[{idx}]"
        if not isinstance(raw_rule, Mapping):
            raise TypeError(f"{rule_field} must be a selector mapping.")
        if len(raw_rule) != 1:
            allowed = ", ".join(sorted(_FEATURE_SELECTOR_OPERATORS))
            raise ValueError(f"{rule_field} must contain exactly one selector operator: {allowed}.")
        operator, value = next(iter(raw_rule.items()))
        if operator not in _FEATURE_SELECTOR_OPERATORS:
            allowed = ", ".join(sorted(_FEATURE_SELECTOR_OPERATORS))
            raise ValueError(f"{rule_field}.{operator} is not supported. Allowed operators: {allowed}.")
        rules.append((str(operator), _as_non_empty_string_list(value, field=f"{rule_field}.{operator}"), rule_field))
    return rules


def _match_selector(columns: Sequence[str], *, operator: str, values: Sequence[str]) -> list[str]:
    if operator == "exact":
        return [col for col in values if col in columns]
    if operator == "startswith":
        return [col for col in columns if any(col.startswith(prefix) for prefix in values)]
    if operator == "endswith":
        return [col for col in columns if any(col.endswith(suffix) for suffix in values)]
    if operator == "contains":
        return [col for col in columns if any(token in col for token in values)]
    if operator == "regex":
        patterns = [re.compile(pattern) for pattern in values]
        return [col for col in columns if any(pattern.search(col) for pattern in patterns)]
    raise ValueError(f"Unsupported feature selector operator: {operator}")


def _dedupe_preserve_order(columns: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for col in columns:
        if col in seen:
            continue
        seen.add(col)
        out.append(col)
    return out


def classify_feature_family(column: str) -> str | None:
    name = str(column)
    if name in {
        "close_logret",
        "close_ret",
    } or name.startswith(("lag_close_logret_", "lag_close_ret_")):
        return "returns_lags"
    if name.startswith(("vol_rolling_", "vol_ewma_")):
        return "volatility"
    if name.startswith(
        (
            "close_over_sma_",
            "close_over_ema_",
            "close_trend_regime_",
            "close_trend_state_",
        )
    ):
        return "trend"
    if name.startswith(
        (
            "roc_",
            "close_rsi_",
            "close_mom_",
            "close_logret_mom_",
            "close_ret_mom_",
            "close_logret_norm_mom_",
            "close_ret_norm_mom_",
        )
    ):
        return "momentum"
    if name.startswith(
        (
            "regime_vol_ratio_",
            "regime_high_vol_state_",
            "regime_low_vol_state_",
            "regime_trend_ratio_",
            "regime_trend_state_",
            "regime_absret_z_",
        )
    ):
        return "regime"
    if (
        name in {"hour_sin_24", "hour_cos_24", "day_of_week_sin_7", "day_of_week_cos_7", "is_weekend"}
        or name.startswith("session_")
    ):
        return "session_time"
    if name.startswith(("atr_over_price_", "plus_di_", "minus_di_", "adx_", "bb_percent_b_", "bb_width_")):
        return "atr_adx_range"
    if name.startswith(
        (
            "cross_asset_",
            "currency_exposure_",
            "fx_base_",
            "fx_quote_",
            "usd_exposure_",
            "eur_exposure_",
            "gbp_exposure_",
            "jpy_exposure_",
            "aud_exposure_",
        )
    ):
        return "cross_asset"
    return None


def _resolve_enabled_feature_families(selectors: Mapping[str, Any]) -> list[str]:
    profile_raw = selectors.get("profile")
    families_raw = selectors.get("families")

    enabled: list[str] = []
    if profile_raw is not None:
        if not isinstance(profile_raw, str) or not profile_raw.strip():
            raise TypeError("feature_selectors.profile must be a non-empty string when provided.")
        profile = str(profile_raw).strip()
        if profile not in _FEATURE_SELECTOR_PROFILES:
            allowed = ", ".join(sorted(_FEATURE_SELECTOR_PROFILES))
            raise ValueError(
                f"Unsupported feature_selectors.profile: {profile!r}. Allowed profiles: {allowed}."
            )
        enabled = list(_FEATURE_SELECTOR_PROFILES[profile])

    if families_raw in (None, {}):
        return enabled
    if not isinstance(families_raw, Mapping):
        raise TypeError("feature_selectors.families must be a mapping when provided.")

    allowed_families = set(_FEATURE_FAMILY_ORDER)
    for family, raw_enabled in families_raw.items():
        if family not in allowed_families:
            allowed = ", ".join(_FEATURE_FAMILY_ORDER)
            raise ValueError(
                f"Unsupported feature_selectors.families key: {family!r}. Allowed families: {allowed}."
            )
        if not isinstance(raw_enabled, bool):
            raise TypeError(f"feature_selectors.families[{family!r}] must be boolean.")
        if raw_enabled and family not in enabled:
            enabled.append(str(family))
        if not raw_enabled and family in enabled:
            enabled.remove(str(family))
    return enabled


def _match_feature_family(columns: Sequence[str], family: str) -> list[str]:
    return [col for col in columns if classify_feature_family(col) == family]


def describe_feature_set(
    feature_cols: Sequence[str],
    *,
    feature_selectors: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selectors = dict(feature_selectors or {})
    enabled_families = _resolve_enabled_feature_families(selectors) if selectors else []
    family_counts: dict[str, int] = {family: 0 for family in _FEATURE_FAMILY_ORDER}
    family_counts["unclassified"] = 0
    selected_by_family: dict[str, list[str]] = {family: [] for family in _FEATURE_FAMILY_ORDER}
    selected_by_family["unclassified"] = []

    for feature in feature_cols:
        family = classify_feature_family(feature) or "unclassified"
        family_counts[family] += 1
        selected_by_family[family].append(str(feature))

    return {
        "profile": selectors.get("profile"),
        "enabled_families": enabled_families,
        "drift_filter": dict(selectors.get("drift_filter", {}) or {}),
        "family_counts": {key: value for key, value in family_counts.items() if value > 0 or key in enabled_families},
        "selected_by_family": {key: value for key, value in selected_by_family.items() if value},
        "resolved_feature_count": int(len(feature_cols)),
    }


def resolve_feature_selectors(
    df: pd.DataFrame,
    feature_selectors: Mapping[str, Any],
) -> list[str]:
    """
    Resolve model feature selectors after feature computation.

    This keeps configs stable when Optuna changes feature windows and therefore changes emitted
    column names (for example close_rsi_14 -> close_rsi_21). Explicit selector rules are resolved
    against the current DataFrame, and missing selector matches fail fast to avoid silent feature
    drops.
    """
    selectors = dict(feature_selectors or {})
    allowed_keys = _FEATURE_SELECTOR_ALLOWED_KEYS
    unknown = sorted(set(selectors) - allowed_keys)
    if unknown:
        allowed = ", ".join(sorted(allowed_keys))
        raise ValueError(f"feature_selectors has unsupported keys: {unknown}. Allowed keys: {allowed}.")

    columns = [str(col) for col in df.columns]
    selected: list[str] = []

    for family in _resolve_enabled_feature_families(selectors):
        selected.extend(_match_feature_family(columns, family))

    exact_values = selectors.get("exact")
    if exact_values is not None:
        exact = _as_non_empty_string_list(exact_values, field="feature_selectors.exact")
        missing_exact = [col for col in exact if col not in df.columns]
        if missing_exact:
            raise KeyError(f"Missing exact feature selector columns: {missing_exact}")
        selected.extend(exact)

    for operator, values, field in _iter_selector_rules(selectors.get("include"), field="feature_selectors.include"):
        matches = _match_selector(columns, operator=operator, values=values)
        if operator == "exact":
            missing = [col for col in values if col not in df.columns]
            if missing:
                raise KeyError(f"{field} exact selector is missing columns: {missing}")
        if not matches:
            raise KeyError(f"{field} matched no feature columns.")
        selected.extend(matches)

    if not selected:
        raise ValueError("feature_selectors must select at least one feature column.")

    excluded: set[str] = set()
    for operator, values, _ in _iter_selector_rules(selectors.get("exclude"), field="feature_selectors.exclude"):
        excluded.update(_match_selector(columns, operator=operator, values=values))

    selected = [col for col in _dedupe_preserve_order(selected) if col not in excluded]
    if not selected:
        raise ValueError("feature_selectors selected no feature columns after excludes.")

    strict = selectors.get("strict", {}) or {}
    if not isinstance(strict, Mapping):
        raise TypeError("feature_selectors.strict must be a mapping when provided.")
    min_count = strict.get("min_count")
    if min_count is not None:
        if isinstance(min_count, bool) or not isinstance(min_count, int) or min_count < 0:
            raise ValueError("feature_selectors.strict.min_count must be an integer >= 0.")
        if len(selected) < int(min_count):
            raise ValueError(
                "feature_selectors resolved too few feature columns: "
                f"{len(selected)} < min_count={int(min_count)}."
            )
    return selected


def infer_feature_columns(
    df: pd.DataFrame,
    explicit_cols: Sequence[str] | None = None,
    feature_selectors: Mapping[str, Any] | None = None,
    exclude: Iterable[str] | None = None,
) -> list[str]:
    """
    Infer usable numeric feature columns when the config does not pin them explicitly.
    """
    if explicit_cols or feature_selectors:
        exclude_set = set(exclude or [])
        explicit = list(explicit_cols or [])
        selected: list[str] = []
        missing = [c for c in explicit if c not in df.columns]
        if missing:
            raise KeyError(f"Missing feature columns: {missing}")
        selected.extend(explicit)
        if feature_selectors:
            selected.extend(resolve_feature_selectors(df, feature_selectors))
        return [col for col in _dedupe_preserve_order(selected) if col not in exclude_set]

    inferred = default_feature_columns(df)
    if inferred:
        return inferred

    exclude_set = set(exclude or [])
    exclude_set.update({"open", "high", "low", "close", "adj_close", "volume"})

    numeric_cols = df.select_dtypes(include=["number"]).columns
    features: list[str] = []
    for col in numeric_cols:
        if col in exclude_set:
            continue
        if col.startswith(("signal_", "pred_", "target_")):
            continue
        features.append(col)
    return features


__all__ = [
    "classify_feature_family",
    "describe_feature_set",
    "ensure_lightgbm_runtime_available",
    "ensure_xgboost_runtime_available",
    "infer_feature_columns",
    "probe_lightgbm_runtime",
    "probe_xgboost_runtime",
    "resolve_feature_selectors",
    "resolve_runtime_for_model",
]
