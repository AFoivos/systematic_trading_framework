# QMS EURUSD M30 model experiments

This directory documents four independent model hypotheses and a five-step alpha
ablation ladder built from the causal
Quantitative Market State features. The YAML files live in
`config/experiments/qms_eurusd_m30_models/` and are intentionally not claimed to have
empirical alpha before nested walk-forward evaluation.

## Experiments

1. `01_eurusd_30m_qms_future_volatility_lgbm_v1.yaml` predicts 16-bar future realized
   volatility. It is a diagnostic forecast intended for volatility targeting or trade
   suppression and emits a flat signal.
2. `02_eurusd_30m_qms_multi_horizon_normalized_return_lgbm_v1.yaml` fits independent
   8-, 16-, and 48-bar ATR-normalized return forecasts. Separate models avoid treating
   horizon as an unordered feature and make horizon-specific failure visible.
3. `03_eurusd_30m_qms_candidate_meta_logreg_v1.yaml` creates a point-in-time union of
   KDS pullback and LMDS exhaustion events, then estimates their directional
   triple-barrier success probability. The meta-model can only accept or reject the
   candidate side. Opposite simultaneous candidates fail closed.
4. `04_eurusd_30m_qms_ppo_risk_sizing_exits_v1.yaml` exposes the QMS state to a
   walk-forward PPO risk environment. An action selects direction, ATR stop distance,
   and take-profit R; fixed fractional risk converts the stop choice into position size.
5. `05_eurusd_30m_qms_trend_pullback_oos_baseline_v1.yaml` is the candidate-only
   control. KDS pullback events must agree with signed KADX, and the shared reduced
   volatility model is used only to establish an identical strict-OOS evaluation mask.
6. `06_eurusd_30m_qms_trend_pullback_atr_gate_v1.yaml` adds a causal ATR/price regime
   gate between the shifted past-only 60th and 95th percentiles.
7. `07_eurusd_30m_qms_trend_pullback_forecast_vol_gate_v1.yaml` replaces the ATR gate
   with an OOS volatility-expansion forecast gate. Expected future volatility must be
   at least 1.10 times slow RLV sigma, while past-only upper quantiles suppress extremes.
8. `08_eurusd_30m_qms_trend_pullback_forecast_vol_sized_v1.yaml` keeps the forecast
   gate and scales exposure by the shifted rolling OOS forecast median divided by the
   current forecast. Weights are reduce-only and clipped to `[0.25, 1.0]`.
9. `09_eurusd_30m_qms_trend_pullback_forecast_vol_meta_v1.yaml` adds a delayed purged
   logistic meta-label stage. Its training candidates already depend on cross-fitted
   volatility forecasts, avoiding in-sample stacking. The classifier consumes the
   policy-stage OOS expansion ratio rather than a raw `pred_*` column, preserving the
   global feature-target leakage contract.

## Alpha-ladder comparison contract

- Experiments 05-09 share the same reduced six-feature volatility model, forecast
  split, KDS candidate definition, KADX alignment, barriers, holding period, costs,
  and leverage cap.
- The volatility model starts with 26,280 training bars and produces ten expanding
  4,380-bar test folds. All policy candidates require its explicit OOS mask.
- The policy transform fails closed on missing inputs. Rolling gate and sizing
  thresholds are shifted by one bar and forecast histories include OOS predictions only.
- Experiment 09 starts its meta split later than the volatility split. This gives the
  classifier a training history of genuinely cross-fitted, forecast-gated candidates.
- Experiment 05 is the required baseline for candidate quality; 06 tests an observable
  ATR regime; 07 isolates forecast selection value; 08 isolates sizing value; and 09
  isolates candidate-conditioned model value.

## Causality and evaluation contract

- QMS features and candidate thresholds use information available at the current bar;
  adaptive quantiles are shifted by one bar.
- Supervised labels use future data only inside the target builder. Purge and embargo
  are at least as large as the corresponding label horizon.
- Every supervised prediction consumed by a signal is gated by its explicit OOS mask.
- The QMS candidate policy never reverses candidate direction, never sizes above one,
  and never uses in-sample forecasts in rolling forecast thresholds.
- RL observations are available at bar close and actions execute at the next bar open.
- Environment costs are disabled in the outer backtest for the PPO experiment to avoid
  charging the same transaction twice.
- Model selection, probability thresholds, and any later ensemble weights must be tuned
  inside training folds. A final untouched holdout is still required before an alpha
  claim or production use.

The accompanying smoke tests only validate config loading, feature/target construction,
candidate construction, and one RL environment step. They do not fit a model or run a
backtest.
