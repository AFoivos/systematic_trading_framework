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
    lookback_length: int = 512
    batch_size: int = 8
    device: str = "cpu"
    ridge_alpha: float = 1.0
    max_fit_rows: int | None = None
    local_files_only: bool = False


class MomentResearchModel:
    """Small research wrapper around MOMENT embeddings or a deterministic fixture baseline."""

    def __init__(self, config: MomentModelConfig) -> None:
        self.config = config
        self.feature_columns_: list[str] = []
        self.buy_mean_: float = 0.0
        self.sell_mean_: float = 0.0
        self.buy_scale_: float = 1.0
        self.sell_scale_: float = 1.0
        self._moment_model: object | None = None
        self._torch: object | None = None
        self._buy_readout: np.ndarray | None = None
        self._sell_readout: np.ndarray | None = None
        self._moment_embedding_dim: int | None = None
        self._moment_fit_rows: int = 0

    def fit(self, frame: pd.DataFrame, *, feature_columns: Sequence[str]) -> "MomentResearchModel":
        assert_no_target_leakage(feature_columns)
        self.feature_columns_ = list(feature_columns)
        np.random.seed(int(self.config.random_seed))
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
        if self.config.backend == "moment":
            self._fit_moment_readouts(frame, horizon=horizon)
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not self.feature_columns_:
            raise ValueError("model must be fit before predict")
        if self.config.backend == "moment":
            return self._predict_moment(frame)
        return self._predict_deterministic(frame)

    def _predict_deterministic(self, frame: pd.DataFrame) -> pd.DataFrame:
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

    def _predict_moment(self, frame: pd.DataFrame) -> pd.DataFrame:
        fallback = self._predict_deterministic(frame)
        embeddings = self._moment_embeddings(frame)
        out = pd.DataFrame(index=frame.index)
        if self._buy_readout is None:
            out["moment_buy_score"] = fallback["moment_buy_score"]
        else:
            out["moment_buy_score"] = _predict_ridge(embeddings, self._buy_readout)
        if self._sell_readout is None:
            out["moment_sell_score"] = fallback["moment_sell_score"]
        else:
            out["moment_sell_score"] = _predict_ridge(embeddings, self._sell_readout)
        out["moment_uncertainty"] = fallback["moment_uncertainty"]
        out["model_backend"] = self.config.backend
        out["checkpoint"] = self.config.checkpoint
        return out

    def _fit_moment_readouts(self, frame: pd.DataFrame, *, horizon: str) -> None:
        if self.config.fine_tune:
            raise MomentDependencyError(
                "MOMENT fine_tune=True is not implemented in this research wrapper. "
                "Use frozen_encoder=True/fine_tune=False for frozen embeddings plus a ridge readout."
            )
        self._load_moment_dependencies()
        if not self.feature_columns_:
            raise ValueError("MOMENT backend requires at least one leakage-safe feature column")
        fit_frame = self._fit_frame(frame)
        embeddings = self._moment_embeddings(fit_frame)
        self._moment_fit_rows = int(len(fit_frame))
        self._moment_embedding_dim = int(embeddings.shape[1]) if embeddings.ndim == 2 else None
        self._buy_readout = _fit_ridge(
            embeddings,
            _target_values(fit_frame, f"buy_markout_bps_{horizon}"),
            alpha=float(self.config.ridge_alpha),
        )
        self._sell_readout = _fit_ridge(
            embeddings,
            _target_values(fit_frame, f"sell_markout_bps_{horizon}"),
            alpha=float(self.config.ridge_alpha),
        )

    def _fit_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        max_rows = self.config.max_fit_rows
        if max_rows is None or int(max_rows) <= 0 or len(frame) <= int(max_rows):
            return frame.copy()
        return frame.tail(int(max_rows)).copy()

    def _load_moment_dependencies(self) -> None:
        try:
            import torch
            from momentfm import MOMENTPipeline
        except Exception as exc:
            raise MomentDependencyError(
                "MOMENT backend requires optional dependencies. "
                "Install torch and momentfm, then provide access to the configured checkpoint "
                f"({self.config.checkpoint})."
            ) from exc

        try:
            kwargs = {"task_name": "embedding"}
            pretrained_kwargs = {"model_kwargs": kwargs}
            if self.config.local_files_only:
                pretrained_kwargs["local_files_only"] = True
            model = MOMENTPipeline.from_pretrained(self.config.checkpoint, **pretrained_kwargs)
            model.init()
            if hasattr(model, "to"):
                model.to(self.config.device)
            if hasattr(model, "eval"):
                model.eval()
            if self.config.frozen_encoder and hasattr(model, "parameters"):
                for parameter in model.parameters():
                    parameter.requires_grad = False
            self._moment_model = model
            self._torch = torch
        except Exception as exc:
            raise MomentDependencyError(
                f"Unable to load MOMENT checkpoint {self.config.checkpoint!r}. "
                "Check local cache/network access and dependency versions."
            ) from exc

    def _moment_embeddings(self, frame: pd.DataFrame) -> np.ndarray:
        if self._moment_model is None or self._torch is None:
            raise MomentDependencyError("MOMENT backend has not been loaded; call fit before predict.")
        values = _feature_matrix(frame, self.feature_columns_)
        batch_size = max(1, int(self.config.batch_size))
        outputs: list[np.ndarray] = []
        torch = self._torch
        with torch.no_grad():
            for start in range(0, len(values), batch_size):
                stop = min(start + batch_size, len(values))
                x_np, mask_np = _window_batch(values, start=start, stop=stop, lookback=int(self.config.lookback_length))
                x = torch.as_tensor(x_np, dtype=torch.float32, device=self.config.device)
                input_mask = torch.as_tensor(mask_np, dtype=torch.float32, device=self.config.device)
                result = self._moment_model(x_enc=x, input_mask=input_mask)
                embeddings = getattr(result, "embeddings", None)
                if embeddings is None and isinstance(result, dict):
                    embeddings = result.get("embeddings")
                if embeddings is None:
                    raise MomentDependencyError("MOMENT embedding mode did not return an embeddings tensor.")
                if embeddings.ndim > 2:
                    embeddings = embeddings.reshape(embeddings.shape[0], -1)
                outputs.append(embeddings.detach().cpu().numpy())
        if not outputs:
            return np.empty((0, 0), dtype="float64")
        return np.vstack(outputs).astype("float64", copy=False)

    def metadata(self) -> dict[str, object]:
        return {
            "model_name": "MOMENT research quote filter",
            "checkpoint": self.config.checkpoint,
            "backend": self.config.backend,
            "frozen_encoder": bool(self.config.frozen_encoder),
            "fine_tune": bool(self.config.fine_tune),
            "target_horizon": self.config.target_horizon,
            "lookback_length": int(self.config.lookback_length),
            "ridge_alpha": float(self.config.ridge_alpha),
            "max_fit_rows": self.config.max_fit_rows,
            "moment_fit_rows": self._moment_fit_rows,
            "moment_embedding_dim": self._moment_embedding_dim,
            "local_files_only": bool(self.config.local_files_only),
            "feature_columns": list(self.feature_columns_),
        }


def _feature_matrix(frame: pd.DataFrame, columns: Sequence[str]) -> np.ndarray:
    values = frame.reindex(columns=list(columns))
    values = values.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    values = values.ffill().fillna(0.0)
    return values.to_numpy(dtype="float32", copy=False)


def _target_values(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = frame[column] if column in frame else pd.Series(np.nan, index=frame.index)
    return pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)


def _window_batch(values: np.ndarray, *, start: int, stop: int, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    if lookback <= 0:
        raise ValueError("lookback_length must be > 0")
    batch_rows = max(0, stop - start)
    n_channels = int(values.shape[1]) if values.ndim == 2 else 0
    windows = np.zeros((batch_rows, n_channels, lookback), dtype="float32")
    masks = np.zeros((batch_rows, lookback), dtype="float32")
    for batch_idx, row_idx in enumerate(range(start, stop)):
        length = min(lookback, row_idx + 1)
        window = values[row_idx - length + 1 : row_idx + 1]
        windows[batch_idx, :, -length:] = window.T
        masks[batch_idx, -length:] = 1.0
    return windows, masks


def _fit_ridge(embeddings: np.ndarray, target: np.ndarray, *, alpha: float) -> np.ndarray | None:
    if embeddings.size == 0 or target.size == 0:
        return None
    finite = np.isfinite(target) & np.isfinite(embeddings).all(axis=1)
    if int(finite.sum()) < 2:
        return None
    x = embeddings[finite]
    y = target[finite]
    design = np.column_stack([x, np.ones(len(x), dtype=x.dtype)])
    penalty = float(alpha) * np.eye(design.shape[1], dtype=design.dtype)
    penalty[-1, -1] = 0.0
    lhs = design.T @ design + penalty
    rhs = design.T @ y
    try:
        return np.linalg.solve(lhs, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(lhs, rhs, rcond=None)[0]


def _predict_ridge(embeddings: np.ndarray, weights: np.ndarray) -> np.ndarray:
    design = np.column_stack([embeddings, np.ones(len(embeddings), dtype=embeddings.dtype)])
    return design @ weights


__all__ = ["MomentDependencyError", "MomentModelConfig", "MomentResearchModel"]
