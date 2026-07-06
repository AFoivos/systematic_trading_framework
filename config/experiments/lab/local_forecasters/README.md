# Local Forecaster Lab

This pack contains local-training forecast experiments only. It deliberately excludes
pretrained/foundation forecasters such as Chronos and TimesFM.

Run with:

```bash
python -m src.experiments.runner config/experiments/lab/local_forecasters/01_spx500_lightgbm_return_h8.yaml
```

All configs use 30-minute input bars. The `hN` suffix means forecast horizon in
clock hours, not the input timeframe. For example, `h8` on 30-minute data uses
`horizon_bars: 16`.

## Experiment Map

| File | Object to forecast | Model | Why this pairing |
| --- | --- | --- | --- |
| `01_spx500_lightgbm_return_h8.yaml` | 8-hour vol-normalized return | `lightgbm_regressor` | Strong tabular baseline for mixed trend, momentum, range, and vol features. |
| `02_xauusd_garch_vol_h8.yaml` | near-term conditional volatility | `garch_forecaster` | Purpose-built risk/volatility baseline with explicit `pred_vol`. |
| `03_us100_lstm_momentum_h12.yaml` | 12-hour momentum continuation | `lstm_forecaster` | Sequence model for ordered momentum and pullback states. |
| `04_eurusd_sarimax_mean_reversion_h6.yaml` | 6-hour return mean reversion | `sarimax_forecaster` | Interpretable autoregressive baseline for FX micro-cycles. |
| `05_ethusd_patchtst_tail_h24.yaml` | 24-hour tail return | `patchtst_forecaster` | Patch sequence model with quantile outputs for noisy crypto moves. |
| `06_ger40_tft_regime_h16.yaml` | 16-hour regime-conditioned return | `tft_forecaster` | Sequence model with variable selection for regime shifts. |
| `07_panel_lightgbm_cross_asset_h8.yaml` | 8-hour panel return across five assets | `lightgbm_regressor` | Cross-asset structured model with asset id and common features. |
| `08_us30_lightgbm_trend_h24.yaml` | 24-hour trend persistence | `lightgbm_regressor` | Tree model for nonlinear trend/range filters. |
| `09_btcusd_lstm_vol_adjusted_h16.yaml` | 16-hour vol-adjusted directional return | `lstm_forecaster` | Sequence model plus quantile spread as risk proxy. |
| `10_xagusd_sarimax_vol_overlay_h12.yaml` | 12-hour return with GARCH overlay risk | `sarimax_forecaster` | Statistical return baseline plus local GARCH risk overlay. |

## Guardrails

- All splits are chronological/purged where horizon overlap matters.
- All targets are built inside the experiment pipeline, not precomputed outside
  the split.
- Feature selectors are explicit and avoid target, signal, and prediction columns.
- Heavy neural configs use small lab defaults. Increase epochs/folds only after
  the baseline OOS diagnostics look sane.
