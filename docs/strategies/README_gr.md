# Strategy Documentation Index (GR)

Αυτός ο κατάλογος συνδέει τα ελληνικά strategy docs που δημιουργήθηκαν από τα checked-in YAML configs και τα διαθέσιμα logged runs.

| Family | Docs | Configs | Logged runs | Περιγραφή |
|---|---|---:|---:|---|
| `foundation_alpha` | [Foundation Alpha και Structured Tail Forecasting](foundation_alpha_gr.md) | 25 | 25 | ETHUSD 30m forecast-driven tail alpha με LightGBM/XGBoost/deep/foundation forecasters. |
| `vwap_rms_ppo_vwap` | [VWAP/RMS/PPO/EMA50 Regime Pullback Strategies](vwap_rms_ppo_vwap_gr.md) | 32 | 5 | Κανόνες pullback/continuation γύρω από VWAP, RMS/PPO momentum και EMA50 regime filter. |
| `london_ny_orb` | [London/NY Opening Range Breakout v3](london_ny_orb_gr.md) | 42 | 0 | Session breakout research για XAU/indices με raw, tree meta και stacked overlay layers. |
| `ehlers` | [Ehlers Cycle, Decycler και Trend Pullback Strategies](ehlers_strategies_gr.md) | 13 | 0 | Cycle/trend signal research με Ehlers filters, semiscalp, decycler continuation και meta overlays. |
| `roc_long_only` | [ROC Long-Only XGBoost R-Multiple Filter](roc_long_only_gr.md) | 0 | 3 | Long-only momentum candidate με XGBoost quality filter και R-multiple target. |
| `quote_flow_scalp` | [Quote Flow Proxy Scalp Strategies](quote_flow_scalp_gr.md) | 22 | 0 | Scalp research με proxy microstructure/toxicity filters πάνω σε 5m/30m US100 diagnostics. |
| `market_making` | [Market Making Moment Research](market_making_gr.md) | 4 | 6 | Research-only market-making pipeline με order-book replay, MOMENT features και toxicity/markout diagnostics. |
| `forecast_lab` | [Forecast Lab και Local Forecaster Benchmarks](forecast_lab_gr.md) | 21 | 11 | Lab configs για Chronos/TimesFM/local forecasters, prediction diagnostics και forecast-to-signal experiments. |
| `codex_research` | [Codex Research Strategies](codex_research_gr.md) | 2 | 2 | Μικρές reproducible strategy candidates που δημιουργήθηκαν ως isolated Codex research experiments. |
| `others` | [Other Strategy Families και Legacy Research Surfaces](other_strategy_families_gr.md) | 14 | 2 | Shock meta, FTMO swing, dense return forecasting, PPO trend και λοιπά standalone configs. |
| `misc` | [Miscellaneous Logged Runs](misc_strategy_runs_gr.md) | 0 | 24 | Runs που δεν χαρτογραφήθηκαν καθαρά σε checked-in strategy family. |

## Κάλυψη

- Συνολικά YAML configs που εντοπίστηκαν: **175**.
- Συνολικά logged runs με `summary.json` που εντοπίστηκαν: **78**.
- Τα docs χρησιμοποιούν τα run artifacts που υπάρχουν τοπικά στο workspace. Αν ένα run έγινε από temporary Optuna config, καταγράφεται ως logged run αλλά δεν θεωρείται canonical config definition εκτός αν υπάρχει checked-in YAML.