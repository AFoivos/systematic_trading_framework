from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from src.utils.config import load_experiment_config
from src.utils.run_metadata import compute_config_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONFIG = (
    PROJECT_ROOT
    / "config/experiments/foundation_alpha/BEST/ethusd/trial0041_validation_suite_v2/"
    "06_feature_window_surface/model07/model07_vwap32_rov64_rz256.yaml"
)
OUTPUT_DIR = PROJECT_ROOT / "config/experiments/foundation_alpha/FTMO/v2"
ANCHOR_FILENAME = "00_ftmo_v2_train_and_cache_model07.yaml"
MODEL_NAME = "ftmo_v2_model07_vwap32_rov64_rz256"
MODEL_INSTALL_DIR = "logs/models/foundation_alpha/FTMO/v2"
ANCHOR_DATASET_ID = "ftmo_v2_model07_vwap32_rov64_rz256_anchor"
EXPECTED_FILENAMES = (
    ANCHOR_FILENAME,
    "01_ftmo_v2_cached_vectorized_parity.yaml",
    "02_ftmo_v2_risk050_stop4.yaml",
    "03_ftmo_v2_risk075_stop4.yaml",
    "04_ftmo_v2_risk100_stop4.yaml",
    "05_ftmo_v2_risk125_stop4.yaml",
    "06_ftmo_v2_risk050_stop5.yaml",
    "07_ftmo_v2_risk075_stop5.yaml",
    "08_ftmo_v2_risk100_stop5.yaml",
    "09_ftmo_v2_risk125_stop5.yaml",
    "10_ftmo_v2_risk075_stop6.yaml",
    "11_ftmo_v2_risk100_stop6.yaml",
    "12_ftmo_v2_risk075_stop5_hold16.yaml",
    "13_ftmo_v2_risk075_stop5_hold32.yaml",
    "14_ftmo_v2_after_stop_long_half.yaml",
    "15_ftmo_v2_short_ema_zone_half.yaml",
    "16_ftmo_v2_long_hours_09_15_half.yaml",
    "17_ftmo_v2_combined_min_risk075.yaml",
    "18_ftmo_v2_combined_multiply_risk075.yaml",
    "19_ftmo_v2_combined_min_risk100.yaml",
    "20_ftmo_v2_liquid_session_risk100.yaml",
    "21_ftmo_v2_combined_liquid_risk100.yaml",
    "22_ftmo_v2_harder_threshold_combined_risk100.yaml",
    "23_ftmo_v2_adverse_cost_combined_risk100.yaml",
)


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a YAML mapping: {path}")
    return payload


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=110),
        encoding="utf-8",
    )


def _disabled_diagnostics(source: dict[str, Any]) -> dict[str, Any]:
    diagnostics = deepcopy(source)
    diagnostics["enabled"] = False
    diagnostics.setdefault("baselines", {})["enabled"] = False
    diagnostics.setdefault("threshold_grid", {})["enabled"] = False
    diagnostics.setdefault("regime_performance", {})["enabled"] = False
    diagnostics.setdefault("robustness", {})["enabled"] = False
    diagnostics.setdefault("trade_path", {})["enabled"] = False
    diagnostics.setdefault("model", {})["enabled"] = False
    return diagnostics


def _cached_diagnostics(source: dict[str, Any]) -> dict[str, Any]:
    diagnostics = deepcopy(source)
    diagnostics["enabled"] = True
    diagnostics.setdefault("baselines", {})["enabled"] = False
    diagnostics.setdefault("threshold_grid", {})["enabled"] = False
    diagnostics.setdefault("regime_performance", {})["enabled"] = True
    diagnostics.setdefault("robustness", {})["enabled"] = False
    trade_path = diagnostics.setdefault("trade_path", {})
    trade_path["enabled"] = True
    trade_path["write_trade_paths"] = True
    trade_path.setdefault("plots", {})["enabled"] = False
    diagnostics.setdefault("model", {})["enabled"] = False
    return diagnostics


def build_anchor(source: dict[str, Any]) -> dict[str, Any]:
    cfg = deepcopy(source)
    cfg.pop("config_path", None)
    cfg["data"]["storage"].update(
        {
            "dataset_id": ANCHOR_DATASET_ID,
            "load_path": "data/raw/dukascopy_30m_clean/ethusd_30m.csv",
            "raw_dir": "data/raw",
            "processed_dir": "data/processed",
            "save_processed": True,
        }
    )
    cfg["model"]["final_refit"] = True
    cfg["diagnostics"] = _disabled_diagnostics(dict(cfg.get("diagnostics", {}) or {}))
    cfg["monitoring"]["enabled"] = False
    cfg["logging"].update(
        {
            "run_name": "ftmo_v2_train_and_cache_model07",
            "output_dir": "logs/experiments/foundation_alpha/FTMO/v2",
            "save_model": True,
            "install_model": True,
            "model_name": MODEL_NAME,
            "model_install_dir": MODEL_INSTALL_DIR,
            "save_predictions": True,
            "save_processed": True,
        }
    )
    cfg["strategy"].update(
        {
            "name": "ftmo_v2_train_and_cache_model07",
            "description": (
                "One-time causal anchor for FTMO v2. It retrains the selected model07 contract with the frozen "
                "purged walk-forward split, persists the final-refit bundle for forward execution, and materializes "
                "the strictly OOS prediction frame used by every cached v2 backtest."
            ),
        }
    )
    cfg["research_metadata"] = {
        "study": "foundation_alpha_ftmo_v2",
        "suite": "foundation_alpha_ftmo_v2",
        "experiment_id": "ftmo_v2_train_and_cache_model07",
        "experiment_role": "one_time_model_and_oos_cache_anchor",
        "source_candidate": "model07_vwap32_rov64_rz256",
        "source_config": str(SOURCE_CONFIG.relative_to(PROJECT_ROOT)),
        "target_frozen": True,
        "split_frozen": True,
        "thresholds_frozen": True,
        "model_params_frozen": True,
        "strict_oos_only": True,
        "final_refit_usage": "forward_or_live_inference_only",
        "historical_research_usage": "cached_walk_forward_oos_predictions_only",
        "exact_ftmo_compliance_emulation": False,
        "selection_phase": "predefined_before_execution",
    }
    return cfg


def _model_none_block() -> dict[str, Any]:
    return {
        "kind": "none",
        "outputs": {
            "pred_ret_col": "pred_ret",
            "pred_prob_col": "pred_prob",
            "pred_is_oos_col": "pred_is_oos",
        },
        "runtime": {},
        "env": {},
        "use_features": True,
        "pred_prob_col": "pred_prob",
        "pred_raw_prob_col": None,
        "pred_ret_col": "pred_ret",
        "pred_is_oos_col": "pred_is_oos",
        "returns_input_col": None,
        "signal_col": None,
        "action_col": None,
    }


def build_cached_base(
    anchor: dict[str, Any],
    *,
    anchor_hash: str,
) -> dict[str, Any]:
    cfg = deepcopy(anchor)
    cache_dataset_id = f"{ANCHOR_DATASET_ID}_{anchor_hash[:8]}"
    cache_path = f"data/processed/processed/{cache_dataset_id}/dataset.csv"
    cfg["data"]["storage"].update(
        {
            "dataset_id": cache_dataset_id,
            "load_path": cache_path,
            "save_processed": False,
        }
    )
    cfg["features"] = []
    cfg["model"] = _model_none_block()
    cfg["monitoring"]["enabled"] = False
    cfg["diagnostics"] = _cached_diagnostics(dict(anchor.get("diagnostics", {}) or {}))
    cfg["logging"].update(
        {
            "save_model": False,
            "install_model": False,
            "save_predictions": False,
            "save_processed": False,
        }
    )
    cfg["logging"].pop("model_name", None)
    cfg["logging"].pop("model_install_dir", None)
    cfg["research_metadata"] = {
        "study": "foundation_alpha_ftmo_v2",
        "suite": "foundation_alpha_ftmo_v2",
        "experiment_role": "cached_oos_backtest",
        "source_candidate": "model07_vwap32_rov64_rz256",
        "model_training_performed": False,
        "oos_cache_anchor_config": (
            "config/experiments/foundation_alpha/FTMO/v2/00_ftmo_v2_train_and_cache_model07.yaml"
        ),
        "oos_cache_anchor_config_hash_sha256": anchor_hash,
        "oos_cache_dataset_id": cache_dataset_id,
        "oos_cache_path": cache_path,
        "installed_forward_model": f"{MODEL_INSTALL_DIR}/{MODEL_NAME}.pkl",
        "target_frozen": True,
        "split_frozen": True,
        "model_params_frozen": True,
        "strict_oos_only": True,
        "exact_ftmo_compliance_emulation": False,
        "selection_phase": "predefined_before_execution",
    }
    return cfg


def _manual_backtest(
    *,
    risk_per_trade: float,
    stop_loss_r: float,
    max_holding_bars: int = 24,
    modifiers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "engine": "manual_barrier",
        "returns_col": "close_ret",
        "signal_col": "signal_structured_tail",
        "periods_per_year": 17520,
        "returns_type": "simple",
        "missing_return_policy": "raise_if_exposed",
        "min_holding_bars": 0,
        "subset": "full",
        "stop_mode": "volatility_stop",
        "vol_col": "atr_over_price_48",
        "open_col": "open",
        "high_col": "high",
        "low_col": "low",
        "close_col": "close",
        "take_profit_r": 50.0,
        "stop_loss_r": float(stop_loss_r),
        "volatility_col": None,
        "entry_price_mode": None,
        "profit_barrier_r": None,
        "stop_barrier_r": None,
        "vertical_barrier_bars": None,
        "tie_break": None,
        "event_time_remap_policy": None,
        "annualization_mode": None,
        "max_cost_r": None,
        "risk_per_trade": float(risk_per_trade),
        "max_holding_bars": int(max_holding_bars),
        "asset_params": {},
        "dynamic_exit": {},
        "strategy_path": {},
        "dynamic_exits": {"enabled": False},
        "partial_exits": {"enabled": False},
        "entry_risk_modifiers": deepcopy(modifiers or {}),
        "allow_short": True,
        "oos_mode": "strict",
        "execution_price": "next_open",
        "execution_delay_bars": 0,
        "estimated_spread_cost_per_unit_turnover": 0.0,
        "commission_per_unit_turnover": 0.0,
        "slippage_per_unit_turnover": 0.0,
        "holding_cost_per_exposed_bar": 0.0,
        "allow_cost_layering": False,
        "stop_cooldown_bars": 0,
    }


def _ftmo_risk(cost_per_turnover: float = 0.000525) -> dict[str, Any]:
    return {
        "cost_per_turnover": float(cost_per_turnover),
        "slippage_per_turnover": 0.0,
        "target_vol": None,
        "max_leverage": 1.0,
        "dd_guard": {
            "enabled": False,
            "max_drawdown": 0.2,
            "cooloff_bars": 20,
            "rearm_drawdown": 0.2,
        },
        "portfolio_guard": {
            "enabled": True,
            "daily_soft_stop": 0.01,
            "daily_soft_stop_risk_multiplier": 0.5,
            "daily_hard_stop": 0.015,
            "timezone": "Europe/Prague",
        },
        "sizing": {},
        "drawdown_sizing": {},
        "vol_col": None,
    }


def _rule_after_stop() -> dict[str, Any]:
    return {
        "name": "after_stop_long",
        "kind": "previous_stop",
        "side": "long",
        "multiplier": 0.5,
    }


def _rule_short_ema_zone() -> dict[str, Any]:
    return {
        "name": "short_ema_countertrend_zone",
        "kind": "column_range",
        "side": "short",
        "col": "close_over_ema_96",
        "min": 0.01,
        "max": 0.023,
        "multiplier": 0.5,
    }


def _rule_long_hours() -> dict[str, Any]:
    return {
        "name": "long_hours_09_15_utc",
        "kind": "local_hour",
        "side": "long",
        "hours": [9, 15],
        "timezone": "UTC",
        "multiplier": 0.5,
    }


def _modifiers(*rules: dict[str, Any], combine: str = "min") -> dict[str, Any]:
    return {"enabled": True, "combine": combine, "rules": [deepcopy(rule) for rule in rules]}


def _configure_variant(
    base: dict[str, Any],
    *,
    filename: str,
    hypothesis: str,
    risk_per_trade: float | None = None,
    stop_loss_r: float | None = None,
    max_holding_bars: int = 24,
    modifiers: dict[str, Any] | None = None,
    cost_per_turnover: float = 0.000525,
    vectorized: bool = False,
) -> dict[str, Any]:
    cfg = deepcopy(base)
    experiment_id = Path(filename).stem.removeprefix("00_").removeprefix("01_")
    cfg["logging"]["run_name"] = experiment_id
    cfg["strategy"].update(
        {
            "name": experiment_id,
            "description": hypothesis,
        }
    )
    cfg["research_metadata"].update(
        {
            "experiment_id": experiment_id,
            "hypothesis": hypothesis,
            "configured_risk_per_trade": risk_per_trade,
            "configured_stop_loss_r": stop_loss_r,
            "configured_max_holding_bars": max_holding_bars if not vectorized else None,
            "all_in_cost_per_unit_turnover": cost_per_turnover,
        }
    )
    if vectorized:
        cfg["backtest"] = deepcopy(build_anchor(_read_yaml(SOURCE_CONFIG))["backtest"])
        # The cached frame carries its own strict pred_is_oos boundary. The runner
        # recomputes the primary summary on that mask even though no model is fit.
        cfg["backtest"]["subset"] = "full"
        cfg["risk"] = deepcopy(build_anchor(_read_yaml(SOURCE_CONFIG))["risk"])
    else:
        if risk_per_trade is None or stop_loss_r is None:
            raise ValueError("Manual variants require risk_per_trade and stop_loss_r.")
        cfg["risk"] = _ftmo_risk(cost_per_turnover)
        cfg["backtest"] = _manual_backtest(
            risk_per_trade=risk_per_trade,
            stop_loss_r=stop_loss_r,
            max_holding_bars=max_holding_bars,
            modifiers=modifiers,
        )
    return cfg


def _add_liquid_session_filter(cfg: dict[str, Any]) -> None:
    cfg["features"] = [
        {
            "step": "session_context",
            "params": {
                "timezone": "UTC",
                "add_cyclical_time": True,
                "include_weekend_flag": True,
                "sessions": {"liquid_12_18_utc": [12, 18]},
            },
            "outputs": {},
            "enabled": True,
        }
    ]
    cfg["signals"]["params"]["activation_filters"].append(
        {"col": "session_liquid_12_18_utc", "op": "ge", "value": 1.0}
    )


def generate() -> list[Path]:
    source = _read_yaml(SOURCE_CONFIG)
    anchor = build_anchor(source)
    anchor_path = OUTPUT_DIR / ANCHOR_FILENAME
    _write_yaml(anchor_path, anchor)
    resolved_anchor = load_experiment_config(anchor_path)
    anchor_hash, _ = compute_config_hash(resolved_anchor)
    cached_base = build_cached_base(anchor, anchor_hash=anchor_hash)

    after_stop = _rule_after_stop()
    short_ema = _rule_short_ema_zone()
    long_hours = _rule_long_hours()
    variants: list[tuple[str, dict[str, Any]]] = []

    variants.append(
        (
            EXPECTED_FILENAMES[1],
            _configure_variant(
                cached_base,
                filename=EXPECTED_FILENAMES[1],
                hypothesis="Cache-parity control: reproduce the selected vectorized OOS result without fitting a model.",
                vectorized=True,
            ),
        )
    )
    manual_specs = [
        (2, 0.0050, 4.0, 24, None, "Risk frontier: 0.50% risk with the existing 4 ATR catastrophe stop."),
        (3, 0.0075, 4.0, 24, None, "Risk frontier: 0.75% risk with the existing 4 ATR catastrophe stop."),
        (4, 0.0100, 4.0, 24, None, "Risk frontier: 1.00% risk with the existing 4 ATR catastrophe stop."),
        (5, 0.0125, 4.0, 24, None, "Risk frontier: 1.25% risk with the existing 4 ATR catastrophe stop."),
        (6, 0.0050, 5.0, 24, None, "Wide-stop frontier: 0.50% risk with a 5 ATR catastrophe stop."),
        (7, 0.0075, 5.0, 24, None, "Wide-stop frontier: 0.75% risk with a 5 ATR catastrophe stop."),
        (8, 0.0100, 5.0, 24, None, "Wide-stop frontier: 1.00% risk with a 5 ATR catastrophe stop."),
        (9, 0.0125, 5.0, 24, None, "Wide-stop frontier: 1.25% risk with a 5 ATR catastrophe stop."),
        (10, 0.0075, 6.0, 24, None, "Tail-stop frontier: 0.75% risk with a 6 ATR catastrophe stop."),
        (11, 0.0100, 6.0, 24, None, "Tail-stop frontier: 1.00% risk with a 6 ATR catastrophe stop."),
        (12, 0.0075, 5.0, 16, None, "Test whether a shorter 16-bar time exit removes adverse late paths."),
        (13, 0.0075, 5.0, 32, None, "Test whether a 32-bar time exit preserves slow winners behind a wide stop."),
        (14, 0.0100, 5.0, 24, _modifiers(after_stop), "Halve risk only for the next long after a completed stop exit."),
        (15, 0.0100, 5.0, 24, _modifiers(short_ema), "Halve countertrend-short risk inside the diagnosed EMA96 distance zone."),
        (16, 0.0100, 5.0, 24, _modifiers(long_hours), "Halve long risk at the diagnosed 09:00 and 15:00 UTC signal hours."),
        (
            17,
            0.0075,
            5.0,
            24,
            _modifiers(after_stop, short_ema, long_hours, combine="min"),
            "Combine the three path-risk modifiers with a non-stacking minimum multiplier.",
        ),
        (
            18,
            0.0075,
            5.0,
            24,
            _modifiers(after_stop, short_ema, long_hours, combine="multiply"),
            "Stress-test multiplicative stacking when multiple path-risk flags coincide.",
        ),
        (
            19,
            0.0100,
            5.0,
            24,
            _modifiers(after_stop, short_ema, long_hours, combine="min"),
            "Higher-return version of the non-stacking combined path-risk overlay.",
        ),
    ]
    for index, risk, stop, hold, modifiers, hypothesis in manual_specs:
        filename = EXPECTED_FILENAMES[index]
        variants.append(
            (
                filename,
                _configure_variant(
                    cached_base,
                    filename=filename,
                    hypothesis=hypothesis,
                    risk_per_trade=risk,
                    stop_loss_r=stop,
                    max_holding_bars=hold,
                    modifiers=modifiers,
                ),
            )
        )

    liquid = _configure_variant(
        cached_base,
        filename=EXPECTED_FILENAMES[20],
        hypothesis="Hard session ablation: trade only 12:00-18:00 UTC while keeping the alpha forecast frozen.",
        risk_per_trade=0.0100,
        stop_loss_r=5.0,
    )
    _add_liquid_session_filter(liquid)
    variants.append((EXPECTED_FILENAMES[20], liquid))

    combined_liquid = _configure_variant(
        cached_base,
        filename=EXPECTED_FILENAMES[21],
        hypothesis="Combine the three soft path-risk modifiers with the 12:00-18:00 UTC hard session filter.",
        risk_per_trade=0.0100,
        stop_loss_r=5.0,
        modifiers=_modifiers(after_stop, short_ema, long_hours, combine="min"),
    )
    _add_liquid_session_filter(combined_liquid)
    variants.append((EXPECTED_FILENAMES[21], combined_liquid))

    harder_threshold = _configure_variant(
        cached_base,
        filename=EXPECTED_FILENAMES[22],
        hypothesis="Raise both alpha thresholds before applying the combined soft path-risk overlay.",
        risk_per_trade=0.0100,
        stop_loss_r=5.0,
        modifiers=_modifiers(after_stop, short_ema, long_hours, combine="min"),
    )
    harder_threshold["signals"]["params"].update({"upper": 0.85, "lower": -1.0})
    variants.append((EXPECTED_FILENAMES[22], harder_threshold))

    adverse_cost = _configure_variant(
        cached_base,
        filename=EXPECTED_FILENAMES[23],
        hypothesis="Adverse execution stress at 32.5 bp round-trip crossing cost with the combined soft overlay.",
        risk_per_trade=0.0100,
        stop_loss_r=5.0,
        modifiers=_modifiers(after_stop, short_ema, long_hours, combine="min"),
        cost_per_turnover=0.001625,
    )
    variants.append((EXPECTED_FILENAMES[23], adverse_cost))

    written = [anchor_path]
    for filename, cfg in variants:
        cfg["research_metadata"]["comparison_control_config"] = (
            "config/experiments/foundation_alpha/FTMO/v2/08_ftmo_v2_risk100_stop5.yaml"
        )
        path = OUTPUT_DIR / filename
        _write_yaml(path, cfg)
        written.append(path)
    if tuple(path.name for path in written) != EXPECTED_FILENAMES:
        raise RuntimeError("Generated FTMO v2 filenames do not match the declared matrix.")
    return written


if __name__ == "__main__":
    for generated_path in generate():
        print(generated_path.relative_to(PROJECT_ROOT))
