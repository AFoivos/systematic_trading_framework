# ETHUSD Path-Dependent Candidate Target Report

This report evaluates an OOS-only candidate target layer for the existing ETHUSD 30m LightGBM strategy.
The primary model target, features, thresholds, activation filters, and manual-barrier trade management are read from the locked baseline YAML and are not modified by this report.

## Inputs
| Artifact | Path |
| --- | --- |
| Locked baseline config | C:\Users\LAB1\Desktop\systematic_trading_framework\config\experiments\foundation_alpha\BEST\ethusd\BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0054_manual_barrier.yaml |
| Processed OHLC/features | C:\Users\LAB1\Desktop\systematic_trading_framework\data\processed\processed\ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_179ecc87_trial_0054\dataset.csv |
| OOS prediction artifact | C:\Users\LAB1\Desktop\systematic_trading_framework\logs\experiments\ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0041_0058_20260710_111948_120452_ecc3f515\artifacts\diagnostics\prediction_distribution.csv |
| Candidate/outcome CSV | C:\Users\LAB1\Desktop\systematic_trading_framework\reports\ethusd_path_dependent_target_dataset.csv |

## Strategy Contract
| Parameter | Value |
| --- | --- |
| signal.kind | forecast_threshold |
| forecast_col | pred_ret |
| upper | 0.700000 |
| lower | -0.850000 |
| mode | long_short |
| activation_filters | [{'col': 'atr_pct_rank_192', 'op': 'ge', 'value': 0.25}, {'col': 'atr_pct_rank_192', 'op': 'le', 'value': 0.85}, {'col': 'range_to_atr', 'op': 'ge', 'value': 0.8999999999999999}, {'col': 'bollinger_bandwidth_rank_192', 'op': 'ge', 'value': 0.4}] |
| backtest.engine | manual_barrier |
| stop_mode | volatility_stop |
| vol_col | atr_over_price_48 |
| take_profit_r | 5.000000 |
| stop_loss_r | 2.000000 |
| max_holding_bars | 24 |
| risk_per_trade | 0.006000 |
| allow_short | True |
| cost_per_turnover | 0.000100 |
| slippage_per_turnover | 0.0 |

Causal convention: signal at close t, entry at open t+1, then future high/low/close path is evaluated up to the configured max holding. Same-bar TP/SL ties use the conservative manual-barrier convention.

## Overall Summary
| Metric | Value |
| --- | --- |
| OOS prediction rows | 43800 |
| Candidate rows | 1876 |
| Valid labeled candidates | 1876 |
| Invalid/unavailable candidates | 0 |
| Long candidates | 1108 |
| Short candidates | 768 |
| Win rate, net R > 0 | 0.446162 |
| Mean net R | 0.104755 |
| Median net R | -0.373555 |

## Net R and Path Distribution
| Metric | Rows | Mean | Median | Q05 | Q25 | Q75 | Q95 | Positive rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| meta_net_r | 1876 | 0.104755 | -0.373555 | -1.033494 | -1.019180 | 0.986049 | 2.485148 | 0.446162 |
| meta_gross_r | 1876 | 0.124791 | -0.352169 | -1.000000 | -1.000000 | 0.999258 | 2.500000 | 0.447228 |
| meta_mfe_r | 1876 | 1.221003 | 0.982801 | 0.042743 | 0.337947 | 1.893325 | 3.016422 | 0.993070 |
| meta_mae_r | 1876 | -0.921361 | -0.939133 | -1.966356 | -1.234675 | -0.449079 | -0.080808 | 0.0 |

## Label Balance
| Label | Rows | Class 0 | Class 1 | Positive rate |
| --- | --- | --- | --- | --- |
| meta_label_positive | 1876 | 1039 | 837 | 0.446162 |
| meta_label_min_0_25r | 1876 | 1144 | 732 | 0.390192 |
| meta_label_min_0_50r | 1876 | 1232 | 644 | 0.343284 |
| meta_label_min_1_00r | 1876 | 1415 | 461 | 0.245736 |

## Exit Reasons
| Exit reason | Count |
| --- | --- |
| max_holding_close | 688 |
| stop_and_target_same_bar_stop_first | 1 |
| stop_loss | 892 |
| take_profit | 295 |

## Invalid or Tail Candidates
_None_

## Long/Short Breakdown
| Side | OOS rows | Candidates | Valid labels | Mean net R | Median net R | Win rate | TP | Stop | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| long | 1108 | 1108 | 1108 | 0.041613 | -0.560355 | 0.424188 | 155 | 544 | 409 |
| none | 41924 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| short | 768 | 768 | 768 | 0.195850 | -0.164404 | 0.477865 | 140 | 349 | 279 |

## By Year
| Year | OOS rows | Candidates | Valid labels | Mean net R | Median net R | Win rate | TP | Stop | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | 13966 | 741 | 741 | 0.113905 | -0.322687 | 0.464238 | 101 | 346 | 294 |
| 2023 | 17386 | 751 | 751 | 0.014711 | -0.789605 | 0.408788 | 114 | 375 | 262 |
| 2024 | 12448 | 384 | 384 | 0.263199 | -0.154229 | 0.484375 | 80 | 172 | 132 |

## By Walk-Forward Fold
| Fold | OOS rows | Candidates | Valid labels | Mean net R | Median net R | Win rate | TP | Stop | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.000000 | 4380 | 196 | 196 | 0.029259 | -1.010730 | 0.418367 | 26 | 103 | 67 |
| 2.000000 | 4380 | 276 | 276 | 0.299042 | 0.060975 | 0.518116 | 52 | 115 | 109 |
| 3.000000 | 4380 | 213 | 213 | 0.115405 | -0.086970 | 0.492958 | 22 | 92 | 99 |
| 4.000000 | 4380 | 256 | 256 | 0.013556 | -1.010124 | 0.421875 | 41 | 130 | 85 |
| 5.000000 | 4380 | 134 | 134 | 0.015982 | -1.014849 | 0.395522 | 22 | 70 | 42 |
| 6.000000 | 4380 | 201 | 201 | -0.046136 | -0.575394 | 0.373134 | 27 | 97 | 77 |
| 7.000000 | 4380 | 204 | 204 | -0.093186 | -1.017402 | 0.392157 | 20 | 107 | 77 |
| 8.000000 | 4380 | 172 | 172 | 0.050955 | -1.010632 | 0.418605 | 27 | 91 | 54 |
| 9.000000 | 4380 | 92 | 92 | 0.496949 | 0.266788 | 0.565217 | 25 | 31 | 36 |
| 10.000000 | 4380 | 132 | 132 | 0.392850 | 0.018186 | 0.507576 | 33 | 57 | 42 |

## Manual-Barrier Agreement Check
The check reruns `run_manual_barrier_backtest` on valid candidate rows only and compares executed, non-overlapping trades with their target rows.
| Check | Value |
| --- | --- |
| executed_trades | 526 |
| matched_target_rows | 526 |
| missing_target_rows | 0 |
| max_abs_trade_r_diff | 1.156134e-07 |
| max_abs_entry_price_diff | 0.0 |
| max_abs_exit_price_diff | 0.0 |
| max_abs_bars_held_diff | 0.0 |
| exit_reason_mismatches | 0 |

## Notes
- Labels are populated only on OOS rows that become primary candidates and have a complete future path.
- Non-candidate rows keep NaN `meta_*` outcomes and NaN labels in the target output.
- The compact CSV includes all OOS prediction rows, candidate metadata, path outcomes, and label columns.
