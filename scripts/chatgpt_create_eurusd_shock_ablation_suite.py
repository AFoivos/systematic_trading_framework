from pathlib import Path

BASE = Path("config/experiments/foundation_alpha/eurusd_m30_downside_shock_mfe_mae/eurusd_m30_downside_shock_mfe_mae_v1.yaml")
OUT = BASE.parent / "ablations"

def one(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f"replace count={text.count(old)} for {old[:60]!r}")
    return text.replace(old, new, 1)

def build(base, name, version, desc, signal, run_name, strategy_type):
    text = one(base, "  name: EURUSD M30 Downside-Shock MFE-MAE Reversion\n  version: 1\n",
               f"  name: {name}\n  version: {version}\n")
    old_desc = """  description: >
    Independent causal EURUSD 30m mean-reversion strategy. It creates broad
    long candidates after statistically extreme downside shocks away from a
    trailing EMA. Two separate regressors predict maximum favorable excursion
    and maximum adverse excursion in R units before execution.
"""
    new_desc = "  description: >\n" + "\n".join("    " + x for x in desc.splitlines()) + "\n"
    text = one(text, old_desc, new_desc)
    a = text.index("signals:\n")
    b = text.index("\ntarget: {}\n", a)
    text = text[:a] + signal.rstrip() + "\n" + text[b:]
    text = one(text, "  run_name: eurusd_m30_downside_shock_mfe_mae_v1\n", f"  run_name: {run_name}\n")
    text = one(text, "  output_dir: logs/experiments/eurusd_m30_downside_shock_mfe_mae\n",
               "  output_dir: logs/experiments/eurusd_m30_downside_shock_mfe_mae/ablations\n")
    text = one(text, "  strategy_type: ml_selected_contrarian_shock_reversion\n",
               f"  strategy_type: {strategy_type}\n")
    return text

def main():
    base = BASE.read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    variants = [
        ("eurusd_m30_downside_shock_raw_v2.yaml",
         "EURUSD M30 Downside-Shock Raw Candidate Baseline", 2,
         "Controlled ablation baseline. Every downside-shock candidate in the\nshared OOS window becomes a long entry. MFE and MAE predictions are\ncomputed for diagnostics but do not filter trades.",
         """signals:
  kind: forecast_threshold_candidate
  params:
    forecast_col: shock_down_candidate
    pred_is_oos_col: pred_mfe_is_oos
    signal_col: signal_eurusd_shock_reversion
    upper: 1.0
    lower: -999.0
    inclusive: true
    mode: long_only
    activation_filters: []
    candidate_col: accepted_shock_candidate
    side_col: accepted_shock_side
    strength_col: accepted_raw_shock
    threshold_distance_col: accepted_raw_shock_margin
""",
         "eurusd_m30_downside_shock_raw_v2",
         "raw_contrarian_shock_reversion"),
        ("eurusd_m30_downside_shock_mfe_only_v3.yaml",
         "EURUSD M30 Downside-Shock MFE-Only Filter", 3,
         "Controlled ablation using only the OOS MFE forecast as the ML gate.\nThe MAE model is retained for identical training and diagnostics but\ndoes not participate in the entry decision.",
         """signals:
  kind: forecast_threshold_candidate
  params:
    forecast_col: pred_mfe_r
    pred_is_oos_col: pred_mfe_is_oos
    signal_col: signal_eurusd_shock_reversion
    upper: 0.75
    lower: -999.0
    inclusive: true
    mode: long_only
    activation_filters:
    - col: shock_down_candidate
      op: ge
      value: 1.0
    candidate_col: accepted_shock_candidate
    side_col: accepted_shock_side
    strength_col: accepted_predicted_mfe_r
    threshold_distance_col: accepted_mfe_margin
""",
         "eurusd_m30_downside_shock_mfe_only_v3",
         "mfe_filtered_contrarian_shock_reversion"),
        ("eurusd_m30_downside_shock_mae_only_v4.yaml",
         "EURUSD M30 Downside-Shock MAE-Only Filter", 4,
         "Controlled ablation using only the OOS MAE forecast as the ML gate.\nThe MFE model is retained for identical training and diagnostics but\ndoes not participate in the entry decision.",
         """signals:
  kind: forecast_threshold_candidate
  params:
    forecast_col: pred_mae_r
    pred_is_oos_col: pred_mae_is_oos
    signal_col: signal_eurusd_shock_reversion
    upper: -0.75
    lower: -999.0
    inclusive: true
    mode: long_only
    activation_filters:
    - col: shock_down_candidate
      op: ge
      value: 1.0
    candidate_col: accepted_shock_candidate
    side_col: accepted_shock_side
    strength_col: accepted_predicted_mae_r
    threshold_distance_col: accepted_mae_margin
""",
         "eurusd_m30_downside_shock_mae_only_v4",
         "mae_filtered_contrarian_shock_reversion"),
        ("eurusd_m30_downside_shock_combined_v5.yaml",
         "EURUSD M30 Downside-Shock Combined MFE-MAE Filter", 5,
         "Controlled combined-filter reference. A downside shock is accepted\nonly when both the OOS MFE and OOS MAE thresholds pass. This preserves\nthe original v1 entry logic under a dedicated ablation run name.",
         """signals:
  kind: forecast_threshold_candidate
  params:
    forecast_col: pred_mfe_r
    pred_is_oos_col: pred_mfe_is_oos
    signal_col: signal_eurusd_shock_reversion
    upper: 0.75
    lower: -999.0
    inclusive: true
    mode: long_only
    activation_filters:
    - col: shock_down_candidate
      op: ge
      value: 1.0
    - col: pred_mae_r
      op: ge
      value: -0.75
    - col: pred_mae_is_oos
      op: ge
      value: 1.0
    candidate_col: accepted_shock_candidate
    side_col: accepted_shock_side
    strength_col: accepted_predicted_mfe_r
    threshold_distance_col: accepted_mfe_margin
""",
         "eurusd_m30_downside_shock_combined_v5",
         "combined_mfe_mae_contrarian_shock_reversion"),
    ]
    for fn, name, ver, desc, sig, rn, st in variants:
        p = OUT / fn
        p.write_text(build(base, name, ver, desc, sig, rn, st), encoding="utf-8")
        print(p)

if __name__ == "__main__":
    main()
