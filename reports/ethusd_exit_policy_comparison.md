# ETHUSD Exit Policy Comparison

Recommendation: **adopt new fixed exit; E. Partial exit rejected by validation stability gate (turnover_ok=True, expectancy_ok=True, stability_ok=True, calmar_ok=False).**

## Locked Inputs
| Field | Value |
| --- | --- |
| base_config | /Users/foivosampatzis/Projects/personal/systematic_trading_framework/config/experiments/foundation_alpha/BEST/ethusd/BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0054_manual_barrier.yaml |
| meta_config | /Users/foivosampatzis/Projects/personal/systematic_trading_framework/config/experiments/foundation_alpha/BEST/ethusd/meta_filter/ethusd_meta_lightgbm_filter.yaml |
| processed_dataset | /Users/foivosampatzis/Projects/personal/systematic_trading_framework/data/processed/processed/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_e7881346_trial_0149/dataset.csv |
| prediction_csv | /Users/foivosampatzis/Projects/personal/systematic_trading_framework/logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0054_manual_barrier_trial_0149_20260710_040612_104038_08aefadd/artifacts/diagnostics/prediction_distribution.csv |
| saved_trade_paths_trade_count | 666 |
| locked_primary_entry_long | 0.700000 |
| locked_primary_entry_short | -0.850000 |
| locked_meta_model_name | logistic_meta_filter |
| locked_meta_model | logistic_regression_clf |
| locked_meta_scaler | robust |
| locked_meta_calibration | none |
| locked_meta_threshold | 0.750000 |
| locked_meta_feature_count | 50 |
| diagnostic_meta_config_declared_model | lightgbm_clf |
| locked_meta_source | reports/ethusd_meta_model_comparison.md selected model |

## Validation Comparison
| Policy | Cum ret | Ann ret | Sharpe | Sortino | Calmar | Max DD | PF | Trades | Avg R | Median R | R skew | Tail R | Avg hold | Turnover | Costs | Giveback | MFE capture |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A. Existing fixed exit validation | 0.054088 | 0.008502 | 0.336563 | 0.629420 | 0.279731 | -0.030395 | 1.289569 | 65 | 0.147104 | 0.028206 | 0.713627 | -1.026437 | 14.400000 | 54.744063 | 0.005605 | 1.021539 | 0.542830 |
| B. Best validation fixed exit validation | 0.085290 | 0.013242 | 0.619516 | 1.194415 | 0.652784 | -0.020285 | 1.626327 | 60 | 0.233664 | 0.160115 | 0.362437 | -1.021267 | 17.116667 | 42.761359 | 0.004276 | 0.813077 | 0.576013 |
| C. Forecast-decay exit validation | 0.057408 | 0.009012 | 0.387359 | 0.709538 | 0.287099 | -0.031391 | 1.330083 | 67 | 0.138512 | 0.028206 | 0.622761 | -1.026396 | 12.388060 | 55.858952 | 0.005649 | 0.861095 | 0.577100 |
| D. Forecast + trend-break exit validation | 0.070918 | 0.011073 | 0.438861 | 0.854959 | 0.352758 | -0.031391 | 1.399368 | 65 | 0.176091 | 0.028206 | 0.701664 | -1.026437 | 13.646154 | 55.415153 | 0.005604 | 0.991826 | 0.542720 |
| E. Partial exit validation | 0.055944 | 0.008788 | 0.420108 | 0.691842 | 0.279303 | -0.031462 | 1.319555 | 67 | 0.134273 | 0.028206 | 0.477529 | -1.026396 | 12.388060 | 56.486633 | 0.005649 | 0.865333 | 0.572860 |

## Untouched Final Test
| Policy | Cum ret | Ann ret | Sharpe | Sortino | Calmar | Max DD | PF | Trades | Avg R | Median R | R skew | Tail R | Avg hold | Turnover | Costs | Giveback | MFE capture |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A. Existing fixed exit untouched test | -0.002530 | -0.000407 | -0.137038 | -0.163983 | -0.061935 | -0.006573 | 0.618906 | 3 | -0.139210 | -0.065958 | -0.382075 | -0.933516 | 21.000000 | 2.531968 | 0.000253 | 0.939292 | 0.282571 |
| B. Best validation fixed exit untouched test | 0.008182 | 0.001311 | 0.530037 | 10.325626 | 4.139618 | -0.000317 | 26.798681 | 3 | 0.453771 | 0.542592 | -0.822502 | 0.006769 | 24.000000 | 2.025574 | 0.000203 | 0.496844 | 0.495847 |
| C. Forecast-decay exit untouched test | -0.002530 | -0.000407 | -0.137038 | -0.163983 | -0.061935 | -0.006573 | 0.618906 | 3 | -0.139210 | -0.065958 | -0.382075 | -0.933516 | 21.000000 | 2.531968 | 0.000253 | 0.939292 | 0.282571 |
| D. Forecast + trend-break exit untouched test | -0.002530 | -0.000407 | -0.137038 | -0.163983 | -0.061935 | -0.006573 | 0.618906 | 3 | -0.139210 | -0.065958 | -0.382075 | -0.933516 | 21.000000 | 2.531968 | 0.000253 | 0.939292 | 0.282571 |
| E. Partial exit untouched test | -0.002530 | -0.000407 | -0.137038 | -0.163983 | -0.061935 | -0.006573 | 0.618906 | 3 | -0.139210 | -0.065958 | -0.382075 | -0.933516 | 21.000000 | 2.531968 | 0.000253 | 0.939292 | 0.282571 |

## Selected Policy
| Field | Value |
| --- | --- |
| selected_policy | B. Best validation fixed exit |
| family | new fixed exit |
| params | max_holding_bars: 24<br>selection_reason: validation plateau with strongest neighboring Calmar median<br>stop_loss_r: 2.5<br>take_profit_r: 5.0 |
| selection_basis | validation stability gates and neighboring-parameter robustness; final test not used for selection |

## Fixed Exit Grid Stability
| Selected | SL R | TP R | Max hold | Trades | Calmar | PF | Avg R | Turnover | Giveback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | 2.500000 | 4.000000 | 24 | 63 | 0.750726 | 1.724200 | 0.254088 | 44.925187 | 0.737342 |
| True | 2.500000 | 5.000000 | 24 | 60 | 0.652784 | 1.626327 | 0.233664 | 42.761359 | 0.813077 |
| False | 1.000000 | 4.000000 | 8 | 94 | 0.502297 | 1.482975 | 0.240378 | 115.418230 | 1.223618 |
| False | 2.500000 | 2.000000 | 24 | 69 | 0.497720 | 1.412688 | 0.126802 | 45.420961 | 0.621319 |
| False | 1.500000 | 4.000000 | 24 | 76 | 0.481396 | 1.506727 | 0.290496 | 78.816744 | 1.169926 |
| False | 2.000000 | 4.000000 | 24 | 69 | 0.400621 | 1.374706 | 0.180968 | 58.100280 | 0.939221 |
| False | 1.000000 | 5.000000 | 8 | 92 | 0.396218 | 1.411132 | 0.195251 | 112.733113 | 1.279211 |
| False | 2.500000 | 3.000000 | 24 | 65 | 0.384798 | 1.399670 | 0.142444 | 44.162761 | 0.781589 |
| False | 1.500000 | 3.000000 | 24 | 77 | 0.293695 | 1.319834 | 0.176653 | 76.660784 | 1.152765 |
| False | 1.000000 | 4.000000 | 24 | 84 | 0.286662 | 1.275325 | 0.206369 | 104.118275 | 1.559990 |
| False | 2.000000 | 5.000000 | 24 | 65 | 0.279731 | 1.289569 | 0.147104 | 54.744063 | 1.021539 |
| False | 2.500000 | 2.000000 | 16 | 72 | 0.277251 | 1.323027 | 0.096192 | 46.928144 | 0.601648 |

## Forecast-Decay Grid Stability
| Selected | Long exit | Short exit | Trades | Calmar | PF | Avg R | Turnover | Giveback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | 0.100000 | 0.0 | 67 | 0.296346 | 1.343536 | 0.142954 | 55.858952 | 0.858714 |
| True | 0.200000 | 0.0 | 67 | 0.287099 | 1.330083 | 0.138512 | 55.858952 | 0.861095 |
| False | 0.100000 | -0.100000 | 68 | 0.264361 | 1.297323 | 0.125731 | 56.562097 | 0.854010 |
| False | 0.300000 | 0.0 | 67 | 0.261313 | 1.301330 | 0.126053 | 55.858952 | 0.854038 |
| False | 0.200000 | -0.100000 | 68 | 0.255123 | 1.284739 | 0.121354 | 56.562097 | 0.856356 |
| False | 0.0 | 0.0 | 67 | 0.239120 | 1.269735 | 0.115403 | 55.858952 | 0.886264 |
| False | 0.300000 | -0.100000 | 68 | 0.229363 | 1.256955 | 0.109079 | 56.562097 | 0.849403 |
| False | 0.100000 | -0.200000 | 68 | 0.223054 | 1.252001 | 0.106044 | 56.562097 | 0.856969 |
| False | 0.200000 | -0.200000 | 68 | 0.213828 | 1.239842 | 0.101667 | 56.562097 | 0.859315 |
| False | 0.0 | -0.100000 | 68 | 0.207192 | 1.227487 | 0.098586 | 56.562097 | 0.881156 |
| False | 0.300000 | -0.200000 | 68 | 0.188102 | 1.212097 | 0.089391 | 56.562097 | 0.852362 |
| False | 0.100000 | -0.300000 | 68 | 0.185398 | 1.210408 | 0.087963 | 56.569354 | 0.860846 |

## Forecast + Trend-Break Grid Stability
| Selected | Long weakening | Short weakening | Trades | Calmar | PF | Avg R | Turnover | Giveback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | 0.0 | 0.0 | 65 | 0.352758 | 1.399368 | 0.176091 | 55.415153 | 0.991826 |
| False | 0.0 | -0.100000 | 65 | 0.352758 | 1.399368 | 0.176091 | 55.415153 | 0.991826 |
| False | 0.100000 | 0.0 | 65 | 0.352758 | 1.399368 | 0.176091 | 55.415153 | 0.991826 |
| False | 0.100000 | -0.100000 | 65 | 0.352758 | 1.399368 | 0.176091 | 55.415153 | 0.991826 |
| False | 0.200000 | 0.0 | 65 | 0.352758 | 1.399368 | 0.176091 | 55.415153 | 0.991826 |
| False | 0.200000 | -0.100000 | 65 | 0.352758 | 1.399368 | 0.176091 | 55.415153 | 0.991826 |
| False | 0.300000 | 0.0 | 65 | 0.337554 | 1.393848 | 0.168419 | 55.348246 | 0.966105 |
| False | 0.300000 | -0.100000 | 65 | 0.337554 | 1.393848 | 0.168419 | 55.348246 | 0.966105 |
| False | 0.0 | -0.200000 | 65 | 0.273984 | 1.309740 | 0.136922 | 55.423212 | 1.001896 |
| False | 0.100000 | -0.200000 | 65 | 0.273984 | 1.309740 | 0.136922 | 55.423212 | 1.001896 |
| False | 0.200000 | -0.200000 | 65 | 0.273984 | 1.309740 | 0.136922 | 55.423212 | 1.001896 |
| False | 0.0 | -0.300000 | 65 | 0.271140 | 1.306134 | 0.135510 | 55.423212 | 1.003308 |

## Meta-Probability Decay Exit
Excluded. The current stacked meta model is trained and predicted only on candidate entry rows; `meta_pred_prob` is not a position-state probability for every held bar. A held-position meta-probability decay exit would require a separate position-state model.

## Partial Exit Gate
| Field | Value |
| --- | --- |
| partial_experiments_enabled | True |
| baseline_validation_mfe_ge_1r_rate | 0.446154 |
| baseline_validation_mfe_ge_2r_rate | 0.230769 |
| baseline_validation_avg_giveback | 1.021539 |

### Partial Exit Validation Results
| Name | Trigger R | Remainder | Trades | Calmar | PF | Avg R | Turnover | Costs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| partial_50pct_at_1_5r | 1.500000 | original_tp | 65 | 0.164103 | 1.160594 | 0.082987 | 56.052442 | 0.005605 |
| partial_50pct_at_1_5r | 1.500000 | forecast_decay | 67 | 0.215458 | 1.246924 | 0.102812 | 56.486633 | 0.005649 |
| partial_50pct_at_2_0r | 2.000000 | original_tp | 65 | 0.272928 | 1.263730 | 0.134079 | 56.052442 | 0.005605 |
| partial_50pct_at_2_0r | 2.000000 | forecast_decay | 67 | 0.279303 | 1.319555 | 0.134273 | 56.486633 | 0.005649 |

## Trade-Path Distributions For Locked Baseline
### All/Winners/Losers
| Bucket | Trades | Avg R | Median R | Tail R | Avg MFE | Median MFE | Avg MAE | Median MAE | Median bar MFE | Median bar MAE | Avg giveback | Avg hold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | 68 | 0.134472 | -0.018876 | -1.027364 | 1.152382 | 0.862447 | -0.884713 | -0.832924 | 4.500000 | 4.500000 | 1.017910 | 14.691176 |
| winners | 34 | 1.232722 | 1.126036 | 0.149519 | 1.847368 | 1.679979 | -0.448713 | -0.411958 | 13.000000 | 2.500000 | 0.614646 | 21.000000 |
| losers | 34 | -0.963778 | -1.010558 | -1.032215 | 0.457396 | 0.323216 | -1.320713 | -1.145023 | 0.500000 | 5.000000 | 1.421174 | 8.382353 |

### Long/Short
| Bucket | Trades | Avg R | Median R | Tail R | Avg MFE | Median MFE | Avg MAE | Median MAE | Median bar MFE | Median bar MAE | Avg giveback | Avg hold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| long | 45 | 0.087458 | -1.003704 | -1.019152 | 1.097179 | 0.827017 | -0.912698 | -1.003495 | 4.000000 | 4.000000 | 1.009721 | 14.266667 |
| short | 23 | 0.226457 | 0.179766 | -1.035835 | 1.260389 | 0.880214 | -0.829960 | -0.803677 | 5.000000 | 6.000000 | 1.033932 | 15.521739 |

### Year
| Bucket | Trades | Avg R | Median R | Tail R | Avg MFE | Median MFE | Avg MAE | Median MAE | Median bar MFE | Median bar MAE | Avg giveback | Avg hold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | 52 | 0.226112 | 0.180608 | -1.018812 | 1.232793 | 0.994573 | -0.845629 | -0.811498 | 4.500000 | 4.000000 | 1.006681 | 14.884615 |
| 2023 | 13 | -0.168928 | -1.017509 | -1.037099 | 0.912042 | 0.660019 | -1.038248 | -1.069433 | 4.000000 | 6.000000 | 1.080970 | 12.461538 |
| 2024 | 3 | -0.139210 | -0.065958 | -0.933516 | 0.800082 | 0.805074 | -0.896850 | -0.783268 | 9.000000 | 14.000000 | 0.939292 | 21.000000 |

### Fold
| Bucket | Trades | Avg R | Median R | Tail R | Avg MFE | Median MFE | Avg MAE | Median MAE | Median bar MFE | Median bar MAE | Avg giveback | Avg hold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2.000000 | 34 | 0.097814 | -0.611910 | -1.011884 | 1.197828 | 0.934007 | -0.856178 | -0.933418 | 3.500000 | 3.500000 | 1.100015 | 13.676471 |
| 3.000000 | 15 | 0.443515 | 0.321538 | -1.021875 | 1.289176 | 1.038344 | -0.701866 | -0.716171 | 7.000000 | 5.000000 | 0.845661 | 17.466667 |
| 4.000000 | 8 | -0.190577 | -1.013939 | -1.033002 | 0.843341 | 0.674483 | -1.428464 | -1.084486 | 3.500000 | 6.000000 | 1.033918 | 13.125000 |
| 5.000000 | 3 | 1.306934 | 2.466641 | -0.672356 | 1.997607 | 2.596897 | -0.628956 | -0.667228 | 14.000000 | 5.000000 | 0.690672 | 14.333333 |
| 6.000000 | 4 | -0.710255 | -1.025511 | -1.036223 | 0.569550 | 0.599082 | -1.094849 | -1.077458 | 2.000000 | 4.000000 | 1.279805 | 9.250000 |
| 7.000000 | 1 | 0.028206 | 0.028206 | 0.028206 | 0.880214 | 0.880214 | -0.137900 | -0.137900 | 4.000000 | 1.000000 | 0.852009 | 24.000000 |
| 10.000000 | 3 | -0.139210 | -0.065958 | -0.933516 | 0.800082 | 0.805074 | -0.896850 | -0.783268 | 9.000000 | 14.000000 | 0.939292 | 21.000000 |

### Volatility Regime
| Bucket | Trades | Avg R | Median R | Tail R | Avg MFE | Median MFE | Avg MAE | Median MAE | Median bar MFE | Median bar MAE | Avg giveback | Avg hold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| high | 23 | -0.281886 | -1.003865 | -1.024265 | 0.862850 | 0.747326 | -1.101934 | -1.058931 | 4.000000 | 6.000000 | 1.144736 | 14.782609 |
| low | 17 | 0.533556 | 0.398244 | -1.026191 | 1.382573 | 1.101515 | -0.796461 | -0.645152 | 4.000000 | 2.000000 | 0.849017 | 13.470588 |
| mid | 28 | 0.234180 | 0.213888 | -1.029179 | 1.250454 | 0.888559 | -0.759862 | -0.690629 | 5.000000 | 2.500000 | 1.016274 | 15.357143 |

### Meta Probability Buckets
| Bucket | Trades | Avg R | Median R | Tail R | Avg MFE | Median MFE | Avg MAE | Median MAE | Median bar MFE | Median bar MAE | Avg giveback | Avg hold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| q1_low | 17 | 0.352806 | -1.012884 | -1.036796 | 1.358771 | 0.880214 | -0.910046 | -1.014880 | 4.000000 | 6.000000 | 1.005965 | 14.176471 |
| q2 | 17 | -0.103775 | 0.179766 | -1.026779 | 0.857247 | 0.827017 | -1.018198 | -0.829907 | 9.000000 | 5.000000 | 0.961022 | 14.941176 |
| q3 | 17 | 0.181037 | 0.259682 | -1.011059 | 1.181611 | 1.038344 | -0.749223 | -0.783268 | 5.000000 | 4.000000 | 1.000575 | 16.823529 |
| q4_high | 17 | 0.107822 | -1.003704 | -1.011191 | 1.211901 | 0.786823 | -0.861384 | -1.030894 | 3.000000 | 4.000000 | 1.104079 | 12.823529 |

## Selected Policy Stability
### Year
| Bucket | Trades | Avg R | Median R | Win rate | PF | Giveback | MFE capture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | 48 | 0.318264 | 0.268970 | 0.604167 | 1.949321 | 0.791941 | 0.588646 |
| 2023 | 12 | -0.104734 | -0.480774 | 0.416667 | 0.792747 | 0.897620 | 0.505255 |

### Quarter
| Bucket | Trades | Avg R | Median R | Win rate | PF | Giveback | MFE capture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2022Q2 | 9 | 0.430021 | 0.422611 | 0.555556 | 1.964125 | 0.712119 | 0.767019 |
| 2022Q3 | 25 | 0.198909 | 0.074676 | 0.560000 | 1.621253 | 0.886827 | 0.478094 |
| 2022Q4 | 14 | 0.459553 | 0.346483 | 0.714286 | 2.579357 | 0.673818 | 0.662208 |
| 2023Q1 | 5 | -0.608275 | -1.008294 | 0.200000 | 0.170018 | 1.063150 | 0.273927 |
| 2023Q2 | 4 | 0.646053 | 0.811952 | 0.500000 | 2.887199 | 0.703466 | 0.732400 |
| 2023Q3 | 2 | -0.411105 | -0.411105 | 0.500000 | 0.202052 | 0.980113 | 0.182946 |
| 2023Q4 | 1 | 0.022564 | 0.022564 | 1.000000 |  | 0.681607 | 0.032044 |

### Fold
| Bucket | Trades | Avg R | Median R | Win rate | PF | Giveback | MFE capture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2.000000 | 31 | 0.286103 | 0.176417 | 0.548387 | 1.805530 | 0.856390 | 0.561296 |
| 3.000000 | 14 | 0.370280 | 0.334743 | 0.714286 | 2.276636 | 0.675394 | 0.631481 |
| 4.000000 | 8 | -0.227228 | -0.810217 | 0.375000 | 0.612040 | 0.915666 | 0.520703 |
| 5.000000 | 3 | 1.201380 | 1.973313 | 0.666667 | 11.314985 | 0.454473 | 0.795874 |
| 6.000000 | 3 | -0.614047 | -1.019929 | 0.333333 | 0.101542 | 1.136891 | 0.132733 |
| 7.000000 | 1 | 0.022564 | 0.022564 | 1.000000 |  | 0.681607 | 0.032044 |

### Long/Short
| Bucket | Trades | Avg R | Median R | Win rate | PF | Giveback | MFE capture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| long | 42 | 0.206609 | 0.068511 | 0.523810 | 1.528088 | 0.787223 | 0.601560 |
| short | 18 | 0.296792 | 0.192307 | 0.666667 | 1.933270 | 0.873403 | 0.525387 |

### Volatility Regime
| Bucket | Trades | Avg R | Median R | Win rate | PF | Giveback | MFE capture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| high | 18 | -0.181736 | -0.613490 | 0.444444 | 0.649383 | 0.953537 | 0.436119 |
| low | 17 | 0.534192 | 0.623012 | 0.647059 | 2.681427 | 0.623272 | 0.736000 |
| mid | 25 | 0.328393 | 0.257230 | 0.600000 | 2.105642 | 0.841014 | 0.534809 |

### Meta Probability Buckets
| Bucket | Trades | Avg R | Median R | Win rate | PF | Giveback | MFE capture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| q1_low | 15 | 0.244161 | 0.022564 | 0.533333 | 1.544436 | 0.834576 | 0.642071 |
| q2 | 15 | -0.024899 | 0.062345 | 0.533333 | 0.935180 | 0.794034 | 0.467059 |
| q3 | 15 | 0.314936 | 0.324122 | 0.666667 | 2.366612 | 0.804050 | 0.487394 |
| q4_high | 15 | 0.400459 | 0.318595 | 0.533333 | 1.967194 | 0.819648 | 0.667565 |

## Untouched Test Path Snapshot For Selected Policy
| Bucket | Trades | Avg R | Median R | Tail R | Avg MFE | Median MFE | Avg MAE | Median MAE | Median bar MFE | Median bar MAE | Avg giveback | Avg hold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | 3 | 0.453771 | 0.542592 | 0.006769 | 0.950614 | 0.675743 | -0.717480 | -0.626615 | 22.000000 | 14.000000 | 0.496844 | 24.000000 |

## Leakage And Timing Controls
- Primary predictions are precomputed OOS rows and are not refit in this step.
- Meta-filter training remains candidate-only with the locked feature set, model kind, label, purge, embargo, and threshold.
- Exit search uses only validation folds; signals near the final-fold boundary are excluded when their maximum holding period could spill into the final fold.
- The final fold is evaluated after policy selection, for the selected comparison policies only.
- Forecast-decay and trend-break decisions at bar `t` execute at next open `t+1` when available; TP/SL barriers on bar `t` retain priority.
- Trend-break is never indicator-only: it requires forecast weakening plus at least two disagreeing trend indicators.
