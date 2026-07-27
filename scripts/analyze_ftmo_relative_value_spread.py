"""Diagnose BTC/ETH price-level mean reversion without running a trading backtest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint


def _finite(value: float | int | np.floating) -> float:
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"Non-finite diagnostic value: {result}")
    return result


def _half_life(spread: pd.Series) -> tuple[float | None, float]:
    lagged = spread.shift(1).rename("lagged")
    change = spread.diff().rename("change")
    regression = pd.concat([change, lagged], axis=1).dropna()
    fit = sm.OLS(regression["change"], sm.add_constant(regression["lagged"])).fit()
    reversion_coefficient = _finite(fit.params["lagged"])
    if reversion_coefficient >= 0.0:
        return None, reversion_coefficient
    return _finite(-np.log(2.0) / reversion_coefficient), reversion_coefficient


def _segment_diagnostics(frame: pd.DataFrame, label: str) -> dict[str, object]:
    btc = frame["btc_log_close"]
    eth = frame["eth_log_close"]
    design = sm.add_constant(eth)
    fit = sm.OLS(btc, design).fit()
    spread = btc - fit.predict(design)
    coint_stat, coint_pvalue, _ = coint(btc, eth)
    adf_stat, adf_pvalue, *_ = adfuller(spread, autolag="AIC")
    half_life, reversion_coefficient = _half_life(spread)
    return {
        "label": label,
        "rows": len(frame),
        "start_utc": frame.index.min().isoformat(),
        "end_utc": frame.index.max().isoformat(),
        "alpha": _finite(fit.params["const"]),
        "beta": _finite(fit.params["eth_log_close"]),
        "r_squared": _finite(fit.rsquared),
        "cointegration_statistic": _finite(coint_stat),
        "cointegration_pvalue": _finite(coint_pvalue),
        "adf_statistic": _finite(adf_stat),
        "adf_pvalue": _finite(adf_pvalue),
        "half_life_hours": half_life,
        "reversion_coefficient": reversion_coefficient,
    }


def analyze_spread(
    frame: pd.DataFrame,
    *,
    formation_hours: int = 720,
    zscore_hours: int = 168,
) -> tuple[dict[str, object], pd.DataFrame]:
    required = {"btc_log_close", "eth_log_close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if len(frame) < max(formation_hours, zscore_hours) * 2:
        raise ValueError("Dataset is too short for the requested rolling diagnostics.")

    chronological_segments = np.array_split(frame, 3)
    segments = [_segment_diagnostics(frame, "full_sample")]
    segments.extend(
        _segment_diagnostics(segment, f"chronological_third_{index}")
        for index, segment in enumerate(chronological_segments, start=1)
    )

    btc = frame["btc_log_close"]
    eth = frame["eth_log_close"]
    eth_mean = eth.rolling(formation_hours).mean().shift(1)
    btc_mean = btc.rolling(formation_hours).mean().shift(1)
    beta = eth.rolling(formation_hours).cov(btc).shift(1) / eth.rolling(formation_hours).var().shift(1)
    alpha = btc_mean - beta * eth_mean
    residual = btc - (alpha + beta * eth)
    residual_mean = residual.rolling(zscore_hours).mean().shift(1)
    residual_std = residual.rolling(zscore_hours).std(ddof=0).shift(1)
    zscore = (residual - residual_mean) / residual_std

    series = pd.DataFrame(
        {
            "btc_log_close": btc,
            "eth_log_close": eth,
            "rolling_alpha_lagged": alpha,
            "rolling_beta_lagged": beta,
            "spread_residual": residual,
            "spread_zscore_lagged": zscore,
        },
        index=frame.index,
    )
    valid_beta = beta.dropna()
    valid_zscore = zscore.replace([np.inf, -np.inf], np.nan).dropna()
    signs = np.sign(valid_zscore)
    zero_crossings = int(((signs * signs.shift(1)) < 0).sum())
    rolling_summary = {
        "formation_hours": formation_hours,
        "zscore_hours": zscore_hours,
        "valid_beta_rows": len(valid_beta),
        "valid_zscore_rows": len(valid_zscore),
        "beta_quantiles": {
            str(quantile): _finite(value)
            for quantile, value in valid_beta.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).items()
        },
        "zscore_above_positive_2_rows": int((valid_zscore > 2.0).sum()),
        "zscore_below_negative_2_rows": int((valid_zscore < -2.0).sum()),
        "zscore_zero_crossings": zero_crossings,
    }
    full_pvalue = float(segments[0]["cointegration_pvalue"])
    stable_segment_count = sum(float(segment["cointegration_pvalue"]) < 0.05 for segment in segments[1:])
    verdict = {
        "price_level_cointegration_supported_full_sample_5pct": full_pvalue < 0.05,
        "chronological_thirds_supporting_cointegration_5pct": stable_segment_count,
        "sufficient_for_plain_price_level_mean_reversion_baseline": full_pvalue < 0.05
        and stable_segment_count >= 2,
    }
    diagnostics = {
        "analysis": "ftmo_btc_eth_price_level_mean_reversion_diagnostics",
        "rows": len(frame),
        "segments": segments,
        "rolling": rolling_summary,
        "verdict": verdict,
    }
    return diagnostics, series


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/processed/ftmo_relative_value/btc_eth_h1.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/ftmo_relative_value/spread_diagnostics"),
    )
    parser.add_argument("--formation-hours", type=int, default=720)
    parser.add_argument("--zscore-hours", type=int, default=168)
    args = parser.parse_args()

    frame = pd.read_csv(args.dataset, parse_dates=["timestamp_utc"]).set_index("timestamp_utc")
    diagnostics, series = analyze_spread(
        frame,
        formation_hours=args.formation_hours,
        zscore_hours=args.zscore_hours,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_path = args.output_dir / "diagnostics.json"
    series_path = args.output_dir / "spread_series.csv"
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
    series.to_csv(series_path, float_format="%.10g")
    verdict = diagnostics["verdict"]["sufficient_for_plain_price_level_mean_reversion_baseline"]
    full = diagnostics["segments"][0]
    print(
        f"cointegration_pvalue={full['cointegration_pvalue']:.6f} "
        f"half_life_hours={full['half_life_hours']:.2f} "
        f"plain_mean_reversion_supported={verdict}"
    )
    print(f"diagnostics={diagnostics_path}")
    print(f"series={series_path}")


if __name__ == "__main__":
    main()

