# Foundation Alpha Experiments

These configs isolate the ETHUSD 30m, 24-bar forecast candidate identified by
local walk-forward research. They do not reuse existing strategy rules.

- `ethusd_30m_chronos_bolt_h24_tail_alpha_v1.yaml` is the primary zero-shot
  foundation-model experiment.
- `ethusd_30m_timesfm_2p5_h24_tail_alpha_v1.yaml` is the TimesFM comparison.
- `ethusd_30m_patchtst_h24_tail_alpha_baseline_v1.yaml` is a local neural
  sequence baseline for environments without Chronos/TimesFM dependencies.

The intended trading shape is tail-only directional exposure on 24-bar forward
return forecasts, evaluated only on OOS test rows with explicit costs and a
24-bar minimum holding window.
