from __future__ import annotations

from typing import Any

import pandas as pd

from src.models.garch import make_garch_fold_predictor


def resolve_garch_overlay(
    df: pd.DataFrame,
    *,
    model_cfg: dict[str, Any],
    returns_col: str | None,
) -> tuple[pd.DataFrame, object | None, dict[str, Any], dict[str, Any]]:
    """
    Resolve optional model.overlay configuration into a fold predictor and normalized params.
    """
    overlay_cfg = dict(model_cfg.get("overlay", {}) or {})
    if not overlay_cfg:
        return df, None, {}, {}

    kind = str(overlay_cfg.get("kind", ""))
    if kind != "garch":
        raise ValueError(f"Unsupported model.overlay.kind: {kind}")

    overlay_params = dict(overlay_cfg.get("params", {}) or {})
    target_cfg = dict(model_cfg.get("target", {}) or {})
    returns_input_col = str(
        overlay_params.get("returns_input_col")
        or overlay_cfg.get("returns_input_col")
        or returns_col
        or "close_ret"
    )
    overlay_params["returns_input_col"] = returns_input_col
    overlay_params.setdefault("mean_model", "zero")

    work_df = df
    if returns_input_col not in work_df.columns:
        price_col = str(target_cfg.get("price_col", "close"))
        if price_col not in work_df.columns:
            raise KeyError(
                f"GARCH overlay returns_input_col '{returns_input_col}' not found and price_col '{price_col}' is missing."
            )
        work_df = work_df.copy()
        work_df[returns_input_col] = work_df[price_col].pct_change()

    overlay_meta = {
        "kind": kind,
        "params": overlay_params,
        "returns_input_col": returns_input_col,
    }
    return work_df, make_garch_fold_predictor(returns_input_col=returns_input_col), overlay_params, overlay_meta


__all__ = ["resolve_garch_overlay"]
