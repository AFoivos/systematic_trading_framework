# ETHUSD Meta-Model Comparison

Final verdict: **meta-model adds no value**.

## Final Architecture
- Primary alpha remains the existing ETHUSD 30m LightGBM regressor and is not replaced.
- Primary threshold candidates are built only from OOS primary `pred_ret` rows.
- Path-dependent labels are candidate-only and use the same manual-barrier TP/SL/max-holding convention.
- The stacked meta layer trains only on older completed candidates, with 24-bar purge and 24-bar embargo metadata.
- Fold-local preprocessing is fitted on each meta training fold. Sigmoid calibration, where used, is fitted only on the most recent internal slice of that training fold.
- Final signal equals `primary_candidate_side` only when `meta_pred_is_oos=true` and `meta_pred_prob >= threshold`; otherwise it is flat.

## Inputs
| Artifact | Path |
| --- | --- |
| Locked baseline config | C:\Users\LAB1\Desktop\systematic_trading_framework\config\experiments\foundation_alpha\BEST\ethusd\BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0054_manual_barrier.yaml |
| Processed OHLC/features | C:\Users\LAB1\Desktop\systematic_trading_framework\data\processed\processed\ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_179ecc87_trial_0054\dataset.csv |
| OOS primary predictions | C:\Users\LAB1\Desktop\systematic_trading_framework\logs\experiments\ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0041_0058_20260710_111948_120452_ecc3f515\artifacts\diagnostics\prediction_distribution.csv |
| Meta prediction CSV | C:\Users\LAB1\Desktop\systematic_trading_framework\reports\ethusd_meta_model_predictions.csv |

## Candidate Dataset
| Metric | Value |
| --- | --- |
| OOS rows | 43800 |
| Candidate rows | 1876 |
| Valid completed candidates | 1876 |
| Positive label rate, +0.50R | 0.343284 |
| Final untouched fold | 10 |

## Selected Model
| Field | Value |
| --- | --- |
| selected_model | logistic_meta_filter |
| selected_threshold | 0.750000 |
| validation_selection_reason | lowest practical threshold on validation plateau |
| best_threshold_by_score | 0.750000 |

## Main Metrics
| Experiment | Cumulative return | Annualized return | Annualized vol | Sharpe | Sortino | Calmar | Max DD | Profit factor | Hit rate | Trades | Avg net R | Median net R | R std | Turnover | Cost/gross | Avg holding | TP rate | SL rate | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Primary baseline all OOS | 0.306364 | 0.043890 | 0.071682 | 0.612285 | 1.122530 | 0.364473 | -0.120420 | 1.175792 | 0.433460 | 526 | 0.087304 | -0.554297 | 1.311024 | 567.679486 | 0.178644 | 14.382129 | 0.155894 | 0.486692 | 0.357414 |
| Primary baseline validation folds | 0.188630 | 0.028163 | 0.067302 | 0.418459 | 0.752108 | 0.233874 | -0.120420 | 1.126210 | 0.429167 | 480 | 0.062223 | -0.572606 | 1.291775 | 520.094212 | 0.232407 | 14.479167 | 0.145833 | 0.489583 | 0.364583 |
| Primary baseline untouched final fold | 0.099050 | 0.015296 | 0.024673 | 0.619931 | 1.359665 | 0.506950 | -0.030172 | 1.738369 | 0.478261 | 46 | 0.349014 | -0.050191 | 1.487810 | 47.585274 | 0.049531 | 13.369565 | 0.260870 | 0.456522 | 0.282609 |
| logistic_meta_filter selected all OOS @ 0.75 | 0.099852 | 0.015415 | 0.024455 | 0.630323 | 1.356519 | 0.327855 | -0.047017 | 1.704549 | 0.500000 | 56 | 0.294979 | -0.002390 | 1.360770 | 47.821986 | 0.046973 | 15.553571 | 0.214286 | 0.392857 | 0.392857 |
| logistic_meta_filter selected validation @ 0.75 | 0.095828 | 0.014817 | 0.024400 | 0.607234 | 1.304019 | 0.315136 | -0.047017 | 1.679826 | 0.500000 | 54 | 0.294565 | -0.023795 | 1.384320 | 47.084706 | 0.048017 | 15.240741 | 0.222222 | 0.407407 | 0.370370 |
| logistic_meta_filter selected untouched final fold @ 0.75 | 0.003672 | 0.000589 | 0.001639 | 0.359508 | 3.714209 | 1.489053 | -0.000396 | 10.282847 | 0.500000 | 2 | 0.306141 | 0.306141 | 0.526228 | 0.737281 | 0.019674 | 24.000000 | 0.0 | 0.0 | 1.000000 |
| lightgbm_meta_filter selected all OOS @ 0.65 | 0.034891 | 0.005527 | 0.020776 | 0.266055 | 0.522806 | 0.115629 | -0.047804 | 1.306951 | 0.459459 | 37 | 0.154655 | -1.007595 | 1.435027 | 32.553080 | 0.085207 | 14.891892 | 0.216216 | 0.513514 | 0.270270 |
| lightgbm_meta_filter selected validation @ 0.65 | 0.041212 | 0.006512 | 0.020633 | 0.315626 | 0.632943 | 0.136228 | -0.047804 | 1.379082 | 0.472222 | 36 | 0.187059 | -0.613856 | 1.441588 | 31.839404 | 0.072245 | 14.777778 | 0.222222 | 0.500000 | 0.277778 |
| lightgbm_meta_filter selected untouched final fold @ 0.65 | -0.006071 | -0.000978 | 0.002434 | -0.401932 | -0.401932 | -0.161138 | -0.006071 | 0.0 | 0.0 | 1 | -1.011895 | -1.011895 |  | 0.713676 | 0.011895 | 19.000000 | 0.0 | 1.000000 | 0.0 |
| lightgbm_calibrated_meta_filter selected all OOS @ 0.65 | 0.045705 | 0.007209 | 0.012179 | 0.591910 | 1.312887 | 0.323421 | -0.022290 | 2.426959 | 0.647059 | 17 | 0.524012 | 0.419302 | 1.282442 | 17.910575 | 0.038155 | 16.823529 | 0.176471 | 0.294118 | 0.529412 |
| lightgbm_calibrated_meta_filter selected validation @ 0.65 | 0.036895 | 0.005840 | 0.011693 | 0.499460 | 1.063623 | 0.262017 | -0.022290 | 2.158437 | 0.625000 | 16 | 0.468259 | 0.376883 | 1.303049 | 16.652287 | 0.043456 | 16.375000 | 0.187500 | 0.312500 | 0.500000 |
| lightgbm_calibrated_meta_filter selected untouched final fold @ 0.65 | 0.008496 | 0.001361 | 0.003406 | 0.399485 | 0.0 | 0.0 | 0.0 | 0.0 | 1.000000 | 1 | 1.416055 | 1.416055 |  | 1.258288 | 0.014594 | 24.000000 | 0.0 | 0.0 | 1.000000 |

## Threshold Sweep
| Model | Threshold | Validation trades | Validation return | Validation Calmar | Validation PF | Validation avg R | Test trades | Test return | Test Calmar | Test PF | Test avg R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightgbm_calibrated_meta_filter | 0.500000 | 66 | 0.022386 | 0.060147 | 1.127038 | 0.080018 | 11 | 0.015141 | 0.136748 | 1.475452 | 0.233564 |
| lightgbm_calibrated_meta_filter | 0.550000 | 50 | -0.027155 | -0.080946 | 0.823206 | -0.072279 | 6 | 0.017301 | 0.446633 | 2.159729 | 0.482683 |
| lightgbm_calibrated_meta_filter | 0.600000 | 31 | -0.002920 | -0.014807 | 0.974552 | 0.008984 | 1 | 0.007587 | 0.0 | 0.0 | 1.264536 |
| lightgbm_calibrated_meta_filter | 0.650000 | 16 | 0.036895 | 0.262017 | 2.158437 | 0.468259 | 1 | 0.008496 | 0.0 | 0.0 | 1.416055 |
| lightgbm_calibrated_meta_filter | 0.700000 | 11 | -0.006461 | -0.046663 | 0.794896 | -0.075251 | 0 | 0.0 | 0.0 | 0.0 |  |
| lightgbm_calibrated_meta_filter | 0.750000 | 2 | 0.007278 | 0.190855 | 2.204543 | 0.722537 | 0 | 0.0 | 0.0 | 0.0 |  |
| lightgbm_meta_filter | 0.500000 | 103 | 0.031116 | 0.059131 | 1.105235 | 0.057526 | 7 | 0.037129 | 0.966011 | 4.030203 | 0.876946 |
| lightgbm_meta_filter | 0.550000 | 77 | 0.012098 | 0.021450 | 1.058301 | 0.024289 | 3 | 0.016873 | 0.443559 | 3.782469 | 0.938522 |
| lightgbm_meta_filter | 0.600000 | 54 | 0.040452 | 0.088852 | 1.243730 | 0.121250 | 1 | -0.006071 | -0.161138 | 0.0 | -1.011895 |
| lightgbm_meta_filter | 0.650000 | 36 | 0.041212 | 0.136228 | 1.379082 | 0.187059 | 1 | -0.006071 | -0.161138 | 0.0 | -1.011895 |
| lightgbm_meta_filter | 0.700000 | 23 | 0.001739 | 0.006986 | 1.031984 | 0.008985 | 0 | 0.0 | 0.0 | 0.0 |  |
| lightgbm_meta_filter | 0.750000 | 15 | 0.008858 | 0.059037 | 1.187745 | 0.103861 | 0 | 0.0 | 0.0 | 0.0 |  |
| logistic_meta_filter | 0.500000 | 264 | 0.198158 | 0.215942 | 1.240379 | 0.117514 | 28 | 0.077380 | 0.618911 | 2.095896 | 0.450437 |
| logistic_meta_filter | 0.550000 | 211 | 0.102584 | 0.130678 | 1.162889 | 0.086066 | 19 | 0.042497 | 0.321344 | 1.924142 | 0.370968 |
| logistic_meta_filter | 0.600000 | 153 | 0.079199 | 0.108394 | 1.173765 | 0.086925 | 10 | 0.060529 | 1.561859 | 5.722101 | 0.987186 |
| logistic_meta_filter | 0.650000 | 106 | 0.053080 | 0.088609 | 1.175039 | 0.088718 | 4 | 0.012463 | 0.308237 | 2.936345 | 0.521774 |
| logistic_meta_filter | 0.700000 | 78 | 0.081889 | 0.146584 | 1.376524 | 0.174416 | 2 | 0.003672 | 1.489053 | 10.282847 | 0.306141 |
| logistic_meta_filter | 0.750000 | 54 | 0.095828 | 0.315136 | 1.679826 | 0.294565 | 2 | 0.003672 | 1.489053 | 10.282847 | 0.306141 |

## Untouched Test Comparison
| Experiment | Cumulative return | Annualized return | Annualized vol | Sharpe | Sortino | Calmar | Max DD | Profit factor | Hit rate | Trades | Avg net R | Median net R | R std | Turnover | Cost/gross | Avg holding | TP rate | SL rate | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Primary baseline untouched final fold | 0.099050 | 0.015296 | 0.024673 | 0.619931 | 1.359665 | 0.506950 | -0.030172 | 1.738369 | 0.478261 | 46 | 0.349014 | -0.050191 | 1.487810 | 47.585274 | 0.049531 | 13.369565 | 0.260870 | 0.456522 | 0.282609 |
| logistic_meta_filter untouched final fold @ 0.75 | 0.003672 | 0.000589 | 0.001639 | 0.359508 | 3.714209 | 1.489053 | -0.000396 | 10.282847 | 0.500000 | 2 | 0.306141 | 0.306141 | 0.526228 | 0.737281 | 0.019674 | 24.000000 | 0.0 | 0.0 | 1.000000 |

## Breakdowns For Selected Model
### By Year
| Year | Trades | Avg R | Median R | Hit rate | Profit factor | TP | SL | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | 40 | 0.595233 | 0.251525 | 0.575000 | 2.669409 | 0.300000 | 0.325000 | 0.375000 |
| 2023 | 12 | -0.693206 | -1.022573 | 0.166667 | 0.113777 | 0.0 | 0.750000 | 0.250000 |
| 2024 | 4 | 0.256990 | 0.207838 | 0.750000 | 16.584952 | 0.0 | 0.0 | 1.000000 |

### By Quarter
| Quarter | Trades | Avg R | Median R | Hit rate | Profit factor | TP | SL | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022Q2 | 8 | 1.135750 | 1.714288 | 0.750000 | 5.520453 | 0.500000 | 0.250000 | 0.250000 |
| 2022Q3 | 21 | 0.325047 | -0.157072 | 0.476190 | 1.792280 | 0.190476 | 0.380952 | 0.428571 |
| 2022Q4 | 11 | 0.717938 | 0.350888 | 0.636364 | 3.233864 | 0.363636 | 0.272727 | 0.363636 |
| 2023Q1 | 5 | -0.479781 | -1.010404 | 0.200000 | 0.259493 | 0.0 | 0.600000 | 0.400000 |
| 2023Q2 | 3 | -1.023194 | -1.024012 | 0.0 | 0.0 | 0.0 | 1.000000 | 0.0 |
| 2023Q3 | 4 | -0.712496 | -1.029992 | 0.250000 | 0.083964 | 0.0 | 0.750000 | 0.250000 |
| 2024Q1 | 2 | 0.207838 | 0.207838 | 1.000000 |  | 0.0 | 0.0 | 1.000000 |
| 2024Q3 | 2 | 0.306141 | 0.306141 | 0.500000 | 10.282847 | 0.0 | 0.0 | 1.000000 |

### By Walk-Forward Fold
| Fold | Trades | Avg R | Median R | Hit rate | Profit factor | TP | SL | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2.000000 | 25 | 0.711640 | 0.181512 | 0.600000 | 3.341798 | 0.320000 | 0.280000 | 0.400000 |
| 3.000000 | 11 | 0.478143 | 0.321538 | 0.545455 | 2.247203 | 0.272727 | 0.363636 | 0.363636 |
| 4.000000 | 9 | -0.182241 | -1.010404 | 0.333333 | 0.577591 | 0.111111 | 0.555556 | 0.333333 |
| 5.000000 | 3 | -1.023194 | -1.024012 | 0.0 | 0.0 | 0.0 | 1.000000 | 0.0 |
| 6.000000 | 4 | -0.712496 | -1.029992 | 0.250000 | 0.083964 | 0.0 | 0.750000 | 0.250000 |
| 8.000000 | 1 | 0.192425 | 0.192425 | 1.000000 |  | 0.0 | 0.0 | 1.000000 |
| 9.000000 | 1 | 0.223252 | 0.223252 | 1.000000 |  | 0.0 | 0.0 | 1.000000 |
| 10.000000 | 2 | 0.306141 | 0.306141 | 0.500000 | 10.282847 | 0.0 | 0.0 | 1.000000 |

### Long/Short
| Side | Trades | Avg R | Median R | Hit rate | Profit factor | TP | SL | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| long | 37 | 0.404544 | 0.181512 | 0.567568 | 1.983879 | 0.243243 | 0.378378 | 0.378378 |
| short | 19 | 0.081614 | -0.157072 | 0.368421 | 1.220783 | 0.157895 | 0.421053 | 0.421053 |

### Volatility Regime
| Regime | Trades | Avg R | Median R | Hit rate | Profit factor | TP | SL | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| high | 14 | 0.287932 | 0.063233 | 0.500000 | 1.912131 | 0.142857 | 0.285714 | 0.571429 |
| low | 16 | 0.387037 | -0.023795 | 0.500000 | 1.769911 | 0.312500 | 0.437500 | 0.250000 |
| mid | 26 | 0.242121 | 0.006101 | 0.500000 | 1.581736 | 0.192308 | 0.423077 | 0.384615 |

### Primary Forecast Decile
| Decile | Trades | Avg R | Median R | Hit rate | Profit factor | TP | SL | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.000000 | 9 | -0.003249 | -1.020696 | 0.333333 | 1.019245 | 0.222222 | 0.555556 | 0.222222 |
| 2.000000 | 4 | -0.442234 | -1.015617 | 0.250000 | 0.449925 | 0.0 | 0.750000 | 0.250000 |
| 3.000000 | 3 | 0.358641 | 0.566995 | 0.666667 | 7.354721 | 0.0 | 0.0 | 1.000000 |
| 4.000000 | 3 | 0.757642 | -0.065958 | 0.333333 | 11.191095 | 0.333333 | 0.0 | 0.666667 |
| 5.000000 | 4 | -0.395871 | -1.008621 | 0.250000 | 0.478528 | 0.0 | 0.750000 | 0.250000 |
| 6.000000 | 5 | -0.169483 | -0.159958 | 0.400000 | 0.365428 | 0.0 | 0.200000 | 0.800000 |
| 7.000000 | 6 | 0.069178 | -0.411749 | 0.500000 | 1.136740 | 0.166667 | 0.500000 | 0.333333 |
| 8.000000 | 9 | 0.780824 | 1.149450 | 0.666667 | 3.098777 | 0.333333 | 0.333333 | 0.333333 |
| 9.000000 | 7 | 0.508297 | 0.223252 | 0.714286 | 2.763013 | 0.285714 | 0.285714 | 0.428571 |
| 10.000000 | 6 | 1.066411 | 1.714042 | 0.666667 | 4.175121 | 0.500000 | 0.333333 | 0.166667 |

### Meta Probability Decile
| Decile | Trades | Avg R | Median R | Hit rate | Profit factor | TP | SL | Time exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.000000 | 6 | -0.316385 | -0.390880 | 0.500000 | 0.379215 | 0.0 | 0.500000 | 0.500000 |
| 2.000000 | 6 | -0.818630 | -1.015769 | 0.166667 | 0.038666 | 0.0 | 0.833333 | 0.166667 |
| 3.000000 | 5 | 1.355642 | 2.475313 | 0.800000 | 7.568908 | 0.600000 | 0.200000 | 0.200000 |
| 4.000000 | 6 | 0.460866 | -0.087363 | 0.333333 | 2.245492 | 0.333333 | 0.333333 | 0.333333 |
| 5.000000 | 5 | 0.450911 | -0.159958 | 0.400000 | 2.200620 | 0.200000 | 0.200000 | 0.600000 |
| 6.000000 | 6 | 0.254652 | -0.115945 | 0.500000 | 1.588109 | 0.166667 | 0.500000 | 0.333333 |
| 7.000000 | 5 | 0.542516 | 0.937510 | 0.600000 | 2.344967 | 0.200000 | 0.400000 | 0.400000 |
| 8.000000 | 6 | -0.089631 | -0.583188 | 0.333333 | 0.831646 | 0.166667 | 0.500000 | 0.333333 |
| 9.000000 | 5 | 0.485522 | 0.321538 | 0.800000 | 3.396732 | 0.200000 | 0.200000 | 0.600000 |
| 10.000000 | 6 | 0.900103 | 0.817268 | 0.666667 | 5.408375 | 0.333333 | 0.166667 | 0.500000 |

## Feature Diagnostics
### logistic_meta_filter Feature Importance
| Feature | Mean importance | Fold count |
| --- | --- | --- |
| primary_candidate_side | 0.610152 | 9 |
| oriented_supersmoother_slope_over_atr | 0.568853 | 9 |
| oriented_macd_hist | 0.382501 | 9 |
| pred_ret_rolling_mean_4 | 0.369251 | 9 |
| oriented_instantaneous_trendline_slope_over_atr | 0.343541 | 9 |
| rolling_price_r2_96 | 0.319732 | 9 |
| vol_rolling_24 | 0.314093 | 9 |
| atr_pct_rank_192 | 0.313179 | 9 |
| bollinger_bandwidth | 0.312453 | 9 |
| oriented_decycler_slope_over_atr | 0.307730 | 9 |
| distance_from_ema96_atr | 0.293432 | 9 |
| bollinger_percent_b | 0.282936 | 9 |
| oriented_ema_trend_48_192 | 0.260849 | 9 |
| close_over_bb_upper_192 | 0.251791 | 9 |
| oriented_distance_from_ema96_atr | 0.243193 | 9 |
| distance_from_ema24_atr | 0.243081 | 9 |
| vol_rolling_96 | 0.234706 | 9 |
| atr_over_price_48 | 0.234555 | 9 |
| vol_ratio_24_192 | 0.221586 | 9 |
| vol_rolling_192 | 0.220734 | 9 |

### logistic_meta_filter Permutation Importance
| Feature | Mean log-loss delta | Fold count |
| --- | --- | --- |
| vol_rolling_96 | 0.044027 | 9 |
| oriented_supersmoother_slope_over_atr | 0.035762 | 9 |
| atr_over_price_48 | 0.034435 | 9 |
| oriented_instantaneous_trendline_slope_over_atr | 0.032195 | 9 |
| oriented_decycler_slope_over_atr | 0.025667 | 9 |
| vol_rolling_192 | 0.022181 | 9 |
| bollinger_percent_b | 0.015421 | 9 |
| oriented_macd_hist | 0.011499 | 9 |
| pred_ret_rolling_mean_4 | 0.009182 | 9 |
| distance_from_ema96_atr | 0.008209 | 9 |
| bollinger_bandwidth | 0.006916 | 9 |
| oriented_ema_trend_48_192 | 0.005938 | 9 |
| atr_pct_rank_192 | 0.005235 | 9 |
| primary_candidate_side | 0.003308 | 9 |
| vol_ratio_24_192 | -9.641504e-05 | 9 |
| distance_from_ema24_atr | -0.000858 | 9 |
| oriented_distance_from_ema96_atr | -0.001043 | 9 |
| vol_rolling_24 | -0.002268 | 9 |
| rolling_price_r2_96 | -0.005280 | 9 |
| close_over_bb_upper_192 | -0.020312 | 9 |

### logistic_meta_filter Top-Feature Stability
| Feature | Top-5 fold count | Share of fit folds |
| --- | --- | --- |
| oriented_supersmoother_slope_over_atr | 8 | 0.888889 |
| primary_candidate_side | 7 | 0.777778 |
| pred_ret_rolling_mean_4 | 6 | 0.666667 |
| oriented_macd_hist | 5 | 0.555556 |
| oriented_instantaneous_trendline_slope_over_atr | 4 | 0.444444 |
| atr_pct_rank_192 | 2 | 0.222222 |
| pred_ret_rolling_zscore_192 | 2 | 0.222222 |
| rolling_price_r2_96 | 2 | 0.222222 |
| atr_over_price_48 | 1 | 0.111111 |
| bollinger_bandwidth | 1 | 0.111111 |
| bollinger_percent_b | 1 | 0.111111 |
| distance_from_ema96_atr | 1 | 0.111111 |
| oriented_decycler_slope_over_atr | 1 | 0.111111 |
| oriented_distance_from_ema96_atr | 1 | 0.111111 |
| oriented_roofing_filter_over_atr | 1 | 0.111111 |
| pred_ret | 1 | 0.111111 |
| vol_rolling_24 | 1 | 0.111111 |

### lightgbm_meta_filter Feature Importance
| Feature | Mean importance | Fold count |
| --- | --- | --- |
| bollinger_bandwidth | 52.444444 | 9 |
| dominant_cycle_period | 51.444444 | 9 |
| atr_pct_rank_192 | 38.222222 | 9 |
| vol_ratio_24_192 | 37.666667 | 9 |
| oriented_macd_hist | 37.000000 | 9 |
| oriented_ema_trend_48_192 | 36.444444 | 9 |
| rolling_price_r2_96 | 33.333333 | 9 |
| oriented_mama_minus_fama_over_atr | 31.444444 | 9 |
| vol_rolling_48 | 31.333333 | 9 |
| vol_rolling_192 | 29.888889 | 9 |
| vol_rolling_96 | 29.222222 | 9 |
| oriented_frama_slope_over_atr | 28.222222 | 9 |
| pred_ret_rolling_std_8 | 27.333333 | 9 |
| distance_from_ema96_atr | 26.555556 | 9 |
| signed_trend_quality_96 | 25.333333 | 9 |
| close_over_bb_upper_192 | 23.777778 | 9 |
| oriented_supersmoother_slope_over_atr | 23.555556 | 9 |
| dominant_cycle_phase_normalized | 22.888889 | 9 |
| rolling_price_r2_48 | 21.888889 | 9 |
| rolling_price_slope_96_atr | 20.333333 | 9 |

### lightgbm_meta_filter Permutation Importance
| Feature | Mean log-loss delta | Fold count |
| --- | --- | --- |
| vol_rolling_48 | 0.007173 | 9 |
| atr_pct_rank_192 | 0.004454 | 9 |
| vol_rolling_96 | 0.004078 | 9 |
| dominant_cycle_period | 0.001905 | 9 |
| pred_ret_rolling_std_8 | 0.000354 | 9 |
| rolling_price_slope_96_atr | 0.000253 | 9 |
| signed_trend_quality_96 | -1.617118e-06 | 9 |
| rolling_price_r2_48 | -0.000295 | 9 |
| dominant_cycle_phase_normalized | -0.000350 | 9 |
| rolling_price_r2_96 | -0.001340 | 9 |
| close_over_bb_upper_192 | -0.001569 | 9 |
| oriented_mama_minus_fama_over_atr | -0.001735 | 9 |
| oriented_macd_hist | -0.004370 | 9 |
| oriented_ema_trend_48_192 | -0.004462 | 9 |
| oriented_supersmoother_slope_over_atr | -0.004553 | 9 |
| distance_from_ema96_atr | -0.004801 | 9 |
| oriented_frama_slope_over_atr | -0.005887 | 9 |
| vol_ratio_24_192 | -0.007701 | 9 |
| bollinger_bandwidth | -0.011655 | 9 |
| vol_rolling_192 | -0.011970 | 9 |

### lightgbm_meta_filter Top-Feature Stability
| Feature | Top-5 fold count | Share of fit folds |
| --- | --- | --- |
| dominant_cycle_period | 9 | 1.000000 |
| bollinger_bandwidth | 7 | 0.777778 |
| atr_pct_rank_192 | 4 | 0.444444 |
| oriented_ema_trend_48_192 | 4 | 0.444444 |
| oriented_macd_hist | 4 | 0.444444 |
| vol_rolling_48 | 4 | 0.444444 |
| vol_ratio_24_192 | 3 | 0.333333 |
| vol_rolling_96 | 3 | 0.333333 |
| distance_from_ema96_atr | 2 | 0.222222 |
| oriented_mama_minus_fama_over_atr | 2 | 0.222222 |
| rolling_price_r2_96 | 2 | 0.222222 |
| signed_trend_quality_96 | 1 | 0.111111 |

### lightgbm_calibrated_meta_filter Feature Importance
| Feature | Mean importance | Fold count |
| --- | --- | --- |
| bollinger_bandwidth | 51.888889 | 9 |
| dominant_cycle_period | 50.222222 | 9 |
| atr_pct_rank_192 | 44.777778 | 9 |
| oriented_macd_hist | 35.777778 | 9 |
| oriented_mama_minus_fama_over_atr | 33.666667 | 9 |
| vol_ratio_24_192 | 32.777778 | 9 |
| rolling_price_r2_96 | 31.444444 | 9 |
| oriented_ema_trend_48_192 | 27.777778 | 9 |
| vol_rolling_192 | 26.666667 | 9 |
| oriented_frama_slope_over_atr | 25.444444 | 9 |
| oriented_supersmoother_slope_over_atr | 24.777778 | 9 |
| distance_from_ema96_atr | 24.222222 | 9 |
| bollinger_bandwidth_rank_192 | 22.222222 | 9 |
| dominant_cycle_phase_normalized | 22.222222 | 9 |
| rolling_price_r2_48 | 21.888889 | 9 |
| signed_trend_quality_96 | 21.777778 | 9 |
| vol_rolling_48 | 21.666667 | 9 |
| primary_candidate_threshold_distance | 21.333333 | 9 |
| vol_rolling_96 | 20.000000 | 9 |
| pred_ret_rolling_std_8 | 19.444444 | 9 |

### lightgbm_calibrated_meta_filter Permutation Importance
| Feature | Mean log-loss delta | Fold count |
| --- | --- | --- |
| rolling_price_r2_96 | 0.003559 | 9 |
| oriented_macd_hist | 0.003107 | 9 |
| dominant_cycle_period | 0.002236 | 9 |
| bollinger_bandwidth_rank_192 | 0.000890 | 9 |
| oriented_mama_minus_fama_over_atr | 0.000685 | 9 |
| rolling_price_r2_48 | 0.000434 | 9 |
| pred_ret_rolling_std_8 | 0.000173 | 9 |
| oriented_supersmoother_slope_over_atr | 0.000124 | 9 |
| oriented_ema_trend_48_192 | -6.403993e-05 | 9 |
| vol_rolling_48 | -8.884231e-05 | 9 |
| vol_ratio_24_192 | -0.000111 | 9 |
| primary_candidate_threshold_distance | -0.000407 | 9 |
| oriented_frama_slope_over_atr | -0.000470 | 9 |
| vol_rolling_96 | -0.000480 | 9 |
| dominant_cycle_phase_normalized | -0.000641 | 9 |
| vol_rolling_192 | -0.001004 | 9 |
| bollinger_bandwidth | -0.001205 | 9 |
| signed_trend_quality_96 | -0.001332 | 9 |
| atr_pct_rank_192 | -0.002480 | 9 |
| distance_from_ema96_atr | -0.003868 | 9 |

### lightgbm_calibrated_meta_filter Top-Feature Stability
| Feature | Top-5 fold count | Share of fit folds |
| --- | --- | --- |
| dominant_cycle_period | 8 | 0.888889 |
| atr_pct_rank_192 | 6 | 0.666667 |
| bollinger_bandwidth | 6 | 0.666667 |
| oriented_macd_hist | 6 | 0.666667 |
| vol_ratio_24_192 | 4 | 0.444444 |
| oriented_ema_trend_48_192 | 2 | 0.222222 |
| oriented_mama_minus_fama_over_atr | 2 | 0.222222 |
| vol_rolling_48 | 2 | 0.222222 |
| bollinger_bandwidth_rank_192 | 1 | 0.111111 |
| close_over_bb_mid_192 | 1 | 0.111111 |
| distance_from_ema96_atr | 1 | 0.111111 |
| dominant_cycle_phase_normalized | 1 | 0.111111 |
| pred_ret_rolling_std_8 | 1 | 0.111111 |
| rolling_price_r2_48 | 1 | 0.111111 |
| rolling_price_r2_96 | 1 | 0.111111 |
| signed_trend_quality_96 | 1 | 0.111111 |
| vol_rolling_96 | 1 | 0.111111 |

## Leakage Checks
- Candidate rows with non-OOS primary predictions are rejected before training.
- Training rows are completed candidates only.
- For each meta fold, `train_max_pos < test_start_pos - purge_bars` by construction.
- Calibration rows are split from the training fold only and never from test rows.
- `meta_*` target/outcome/prediction columns are rejected from the feature matrix.

SHAP summary: not produced in this run; the local environment does not include `shap`, and the permutation/LightGBM gain diagnostics above are the committed feature diagnostics.
