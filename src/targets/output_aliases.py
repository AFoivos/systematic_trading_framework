from __future__ import annotations

from typing import Any


TARGET_OUTPUT_KEYS = frozenset(
    {
        "label_col",
        "fwd_col",
        "raw_fwd_col",
        "normalizer_col",
        "risk_distance_col",
        "realized_vol_col",
        "mfe_col",
        "mae_col",
        "beta_col",
        "benchmark_fwd_col",
        "event_ret_col",
        "candidate_out_col",
        "r_col",
        "oriented_r_col",
        "trade_r_col",
        "entry_price_col",
        "exit_price_col",
        "stop_price_col",
        "take_profit_price_col",
        "exit_reason_col",
        "bars_held_col",
        "hit_step_col",
        "hit_type_col",
        "meta_candidate_col",
        "gross_return_col",
        "net_return_col",
        "gross_r_col",
        "net_r_col",
        "mfe_r_col",
        "mae_r_col",
        "holding_bars_col",
        "positive_label_col",
        "min_025_label_col",
        "min_050_label_col",
        "min_100_label_col",
        "upper_barrier_col",
        "lower_barrier_col",
        "meta_side_col",
        "oriented_ret_col",
        "vol_source_col",
    }
)


def apply_target_output_aliases(target_cfg: dict[str, Any] | None) -> dict[str, Any]:
    """
    Apply the registered ``apply_target_output_aliases`` target transformation.
    
    This target uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        target:
          kind: apply_target_output_aliases
          params:
            outputs: <configured>
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    outputs:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    """
    cfg = dict(target_cfg or {})
    outputs = cfg.get("outputs")
    if outputs in (None, {}):
        return cfg
    if not isinstance(outputs, dict):
        raise ValueError("target.outputs must be a mapping when provided.")
    for key, value in outputs.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("target.outputs keys must be non-empty strings.")
        if key not in TARGET_OUTPUT_KEYS:
            allowed = ", ".join(sorted(TARGET_OUTPUT_KEYS))
            raise ValueError(f"target.outputs.{key} is not supported. Allowed keys: {allowed}.")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"target.outputs.{key} must be a non-empty string.")
        if cfg.get(key) in (None, ""):
            cfg[key] = value
    return cfg


__all__ = ["TARGET_OUTPUT_KEYS", "apply_target_output_aliases"]
