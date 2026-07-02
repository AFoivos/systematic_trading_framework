from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

from src.market_making.moment_dataset import assert_no_target_leakage


class MomentDependencyError(RuntimeError):
    """Raised when the optional MOMENT research dependencies are unavailable."""


@dataclass(frozen=True)
class MomentModelConfig:
    backend: str = "deterministic_fixture"
    checkpoint: str = "AutonLab/MOMENT-1-large"
    frozen_encoder: bool = True
    fine_tune: bool = False
    random_seed: int = 42
    target_horizon: str = "h5"
    batch_size: int = 8
    device: str = "cpu"


class MomentResearchModel:
    """Small research wrapper around MOMENT or a deterministic fixture baseline."""

    def __init__(self, config: MomentModelConfig) -> None:
        self.config = config
        self.feature_columns_: list[str] = []
        self.buy_mean_: float = 0.0
        self.sell_mean_: float = 0.0
        self.buy_scale_: float = 1.0
        self.sell_scale_: float = 1.0
        self._moment_model: object | None = None

    def fit(self, frame: pd.DataFrame, *, feature_columns: Sequence[str]) -> "MomentResearchModel":
        assert_no_target_leakage(feature_columns)
        self.feature_columns_ = list(feature_columns)
        np.random.seed(int(self.config.random_seed))
        if self.config.backend == "moment":
            self._load_moment_dependencies()
        horizon = self.config.target_horizon
        buy_target = pd.to_numeric(frame.get(f"buy_markout_bps_{horizon}", 0.0), errors="coerce").dropna()
        sell_target = pd.to_numeric(frame.get(f"sell_markout_bps_{horizon}", 0.0), errors="coerce").dropna()
        self.buy_mean_ = float(buy_target.mean()) if not buy_target.empty else 0.0
        self.sell_mean_ = float(sell_target.mean()) if not sell_target.empty else 0.0
        self.buy_scale_ = float(buy_target.std(ddof=0)) if len(buy_target) > 1 else 1.0
        self.sell_scale_ = float(sell_target.std(ddof=0)) if len(sell_target) > 1 else 1.0
        if self.buy_scale_ == 0.0:
            self.buy_scale_ = 1.0
        if self.sell_scale_ == 0.0:
            self.sell_scale_ = 1.0
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not self.feature_columns_:
            raise ValueError("model must be fit before predict")
        out = pd.DataFrame(index=frame.index)
        imbalance = pd.to_numeric(frame.get("book_imbalance_1", 0.5), errors="coerce").fillna(0.5)
        slope = pd.to_numeric(frame.get("recent_mid_slope", 0.0), errors="coerce").fillna(0.0)
        volatility = pd.to_numeric(frame.get("recent_volatility", 0.0), errors="coerce").fillna(0.0)
        spread = pd.to_numeric(frame.get("book_spread_bps", 0.0), errors="coerce").fillna(0.0)
        directional_signal = ((imbalance - 0.5) * 10.0) + (slope * 1_000.0)
        out["moment_buy_score"] = self.buy_mean_ + directional_signal
        out["moment_sell_score"] = self.sell_mean_ - directional_signal
        out["moment_uncertainty"] = (volatility * 10_000.0).abs().clip(lower=0.0) / (spread.abs() + 1.0)
        out["model_backend"] = self.config.backend
        out["checkpoint"] = self.config.checkpoint
        return out

    def _load_moment_dependencies(self) -> None:
        try:
            import torch  # noqa: F401
            from transformers import AutoModel  # noqa: F401
        except Exception as exc:
            raise MomentDependencyError(
                "MOMENT backend requires optional Hugging Face dependencies. "
                "Install torch/transformers and provide access to the configured checkpoint "
                f"({self.config.checkpoint})."
            ) from exc

        try:
            from transformers import AutoModel

            self._moment_model = AutoModel.from_pretrained(self.config.checkpoint, trust_remote_code=True)
        except Exception as exc:
            raise MomentDependencyError(
                f"Unable to load MOMENT checkpoint {self.config.checkpoint!r}. "
                "Check local cache/network access and dependency versions."
            ) from exc

    def metadata(self) -> dict[str, object]:
        return {
            "model_name": "MOMENT research quote filter",
            "checkpoint": self.config.checkpoint,
            "backend": self.config.backend,
            "frozen_encoder": bool(self.config.frozen_encoder),
            "fine_tune": bool(self.config.fine_tune),
            "target_horizon": self.config.target_horizon,
            "feature_columns": list(self.feature_columns_),
        }


__all__ = ["MomentDependencyError", "MomentModelConfig", "MomentResearchModel"]
