from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import yaml

REPO_ROOT = Path("/workspace")
BASE = (
    REPO_ROOT
    / "config/experiments/foundation_alpha/ethusd/v3_7_validation/"
      "ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_ablation_normalized_vol_only.yaml"
)
OUT = (
    REPO_ROOT
    / "config/experiments/foundation_alpha/ethusd/v3_7_validation/"
      "rolling_windows_normalized_rank"
)

PREFIX = "ethusd_30m_lightgbm_h24_v37_roll"
TRAIN_WINDOWS = {
    "2y": 35_040,   # 2 * 365 * 48 half-hour bars
    "3y": 52_560,   # 3 * 365 * 48 half-hour bars
}
SIDES = {
    "long": False,
    "short": True,
}
TRADE_RATES = {
    "q05": 0.05,
    "q10": 0.10,
}


def main() -> None:
    base = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    for window_name, train_size in TRAIN_WINDOWS.items():
        for side, allow_short in SIDES.items():
            for rate_name, trade_rate in TRADE_RATES.items():
                cfg = deepcopy(base)
                name = f"{PREFIX}_{window_name}_{side}_{rate_name}"

                cfg["strategy"]["name"] = name
                cfg["strategy"]["description"] = (
                    f"Rolling {window_name} LightGBM, separately fitted {side}-side run, "
                    "normalized/rank volatility model inputs and causal rolling "
                    f"top-{trade_rate:.0%} probability-conviction selection."
                )
                cfg["data"]["storage"]["dataset_id"] = name
                cfg["data"]["storage"]["save_processed"] = False

                cfg["model"]["split"].update(
                    train_size=train_size,
                    test_size=4_380,
                    step_size=4_380,
                    expanding=False,
                    max_folds=12,
                    purge_bars=24,
                    embargo_bars=24,
                )

                # The base normalized-vol config already excludes:
                # atr_48, atr_pct, vol_rolling_*, and raw bollinger_bandwidth
                # from model.feature_cols. atr_48 remains only as an internal
                # target scaler / feature-engineering intermediate.
                forbidden = {
                    "atr_48",
                    "atr_pct",
                    "vol_rolling_24",
                    "vol_rolling_48",
                    "vol_rolling_96",
                    "vol_rolling_192",
                    "bollinger_bandwidth",
                }
                cfg["model"]["feature_cols"] = [
                    col for col in cfg["model"]["feature_cols"] if col not in forbidden
                ]

                side_filter = (
                    {"col": "pred_prob", "op": "ge", "value": 0.5}
                    if side == "long"
                    else {"col": "pred_prob", "op": "lt", "value": 0.5}
                )
                cfg["signals"] = {
                    "kind": "probability_vol_adjusted",
                    "params": {
                        "prob_col": "pred_prob",
                        "vol_col": "atr_over_price_48",
                        "signal_col": "signal_structured_tail",
                        "prob_center": 0.5,
                        "upper": None,
                        "lower": None,
                        "vol_target": None,
                        "clip": 1.0,
                        "vol_floor": 1.0e-6,
                        "min_signal_abs": 0.0,
                        "activation_filters": [
                            {"col": "atr_pct_rank_192", "op": "ge", "value": 0.20},
                            {"col": "atr_pct_rank_192", "op": "le", "value": 0.90},
                            {
                                "col": "bollinger_bandwidth_rank_192",
                                "op": "ge",
                                "value": 0.25,
                            },
                            side_filter,
                        ],
                        # Causal rolling quantile: threshold is shifted one bar.
                        "max_trade_rate": trade_rate,
                        "top_quantile_window": 4_380,
                    },
                    "outputs": {},
                }

                cfg["backtest"]["allow_short"] = allow_short
                cfg["diagnostics"]["baselines"].update(
                    enabled=True,
                    random_seed=7,
                )
                cfg["diagnostics"]["threshold_grid"]["enabled"] = False
                cfg["diagnostics"]["regime_performance"]["enabled"] = True
                cfg["diagnostics"]["forecast"]["volatility_col"] = "atr_pct_rank_192"
                cfg["diagnostics"]["robustness"].update(
                    enabled=True,
                    cost_multipliers=[1.0, 2.0, 3.0, 5.0],
                    entry_delay_bars=[1, 2],
                    strict_no_remap=True,
                )

                cfg["logging"].update(
                    run_name=name,
                    save_processed=False,
                    save_predictions=True,
                )

                path = OUT / f"{name}.yaml"
                path.write_text(
                    yaml.safe_dump(
                        cfg,
                        sort_keys=False,
                        allow_unicode=True,
                        width=1000,
                    ),
                    encoding="utf-8",
                )

                parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
                assert parsed["model"]["split"]["expanding"] is False
                assert parsed["model"]["split"]["train_size"] == train_size
                assert forbidden.isdisjoint(parsed["model"]["feature_cols"])
                assert parsed["diagnostics"]["regime_performance"]["enabled"] is True
                written.append(str(path.relative_to(REPO_ROOT)))

    print({"ok": True, "count": len(written), "written": written})


if __name__ == "__main__":
    main()
