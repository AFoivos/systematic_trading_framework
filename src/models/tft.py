from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd


def _build_sequence_samples(
    *,
    full_df: pd.DataFrame,
    indices: np.ndarray,
    feature_cols: list[str],
    target_col: str,
    lookback: int,
    require_target: bool,
    allowed_window_indices: set[int] | None = None,
) -> tuple[np.ndarray, np.ndarray, pd.Index]:
    """
    Build rolling supervised windows for sequence models such as TFT.
    """
    if lookback <= 1:
        raise ValueError("lookback must be > 1 for sequence models.")
    if not feature_cols:
        raise ValueError("TFT requires at least one feature column.")

    x_raw = full_df[feature_cols].to_numpy(dtype=float)
    y_raw = full_df[target_col].to_numpy(dtype=float)
    index_values = full_df.index

    x_rows: list[np.ndarray] = []
    y_rows: list[float] = []
    out_index: list[pd.Timestamp] = []
    for idx in np.asarray(indices, dtype=int):
        start = int(idx - lookback + 1)
        if start < 0:
            continue
        window = np.arange(start, int(idx) + 1, dtype=int)
        if allowed_window_indices is not None and any(int(w) not in allowed_window_indices for w in window):
            continue
        x_win = x_raw[window]
        if not np.isfinite(x_win).all():
            continue
        if require_target:
            y_val = float(y_raw[int(idx)])
            if not np.isfinite(y_val):
                continue
            y_rows.append(y_val)
        x_rows.append(x_win.astype("float32"))
        out_index.append(index_values[int(idx)])

    if not x_rows:
        return (
            np.empty((0, lookback, len(feature_cols)), dtype="float32"),
            np.empty((0,), dtype="float32"),
            pd.Index([], dtype="datetime64[ns]"),
        )
    x_arr = np.stack(x_rows, axis=0).astype("float32")
    if require_target:
        y_arr = np.asarray(y_rows, dtype="float32")
    else:
        y_arr = np.empty((len(x_rows),), dtype="float32")
    return x_arr, y_arr, pd.Index(out_index)


def make_tft_fold_predictor() -> Callable[
    [pd.DataFrame, np.ndarray, np.ndarray, list[str], str, dict[str, Any], dict[str, Any]],
    tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]],
]:
    """
    Build the fold predictor closure used by the experiment layer for the TFT model family.
    """
    def _predictor(
        full_df: pd.DataFrame,
        train_idx: np.ndarray,
        test_idx: np.ndarray,
        feature_cols: list[str],
        target_col: str,
        model_params: dict[str, Any],
        runtime_meta: dict[str, Any],
    ) -> tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]]:
        try:
            import torch
            import torch.nn as nn
            from torch.utils.data import DataLoader, TensorDataset
        except Exception as exc:
            raise ImportError(
                "TFT model requires torch. Install torch to use model.kind='tft_forecaster'."
            ) from exc

        lookback = int(model_params.get("lookback", 32))
        hidden_dim = int(model_params.get("hidden_dim", 32))
        n_heads = int(model_params.get("num_heads", 4))
        n_layers = int(model_params.get("num_layers", 2))
        dropout = float(model_params.get("dropout", 0.1))
        epochs = int(model_params.get("epochs", 20))
        batch_size = int(model_params.get("batch_size", 64))
        learning_rate = float(model_params.get("learning_rate", 1e-3))
        weight_decay = float(model_params.get("weight_decay", 1e-4))
        quantiles_cfg = model_params.get("quantiles", [0.1, 0.5, 0.9])
        quantiles = tuple(float(q) for q in quantiles_cfg)

        if len(quantiles) < 2:
            raise ValueError("model.params.quantiles for TFT must contain at least two values.")
        if any(not (0.0 < q < 1.0) for q in quantiles):
            raise ValueError("TFT quantiles must be within (0, 1).")
        if hidden_dim <= 0 or n_heads <= 0 or n_layers <= 0:
            raise ValueError("TFT hidden_dim/num_heads/num_layers must be positive.")
        if hidden_dim % n_heads != 0:
            raise ValueError("TFT hidden_dim must be divisible by num_heads.")

        seed = int(runtime_meta.get("seed", 7))
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        threads = runtime_meta.get("threads")
        if isinstance(threads, int) and threads > 0:
            torch.set_num_threads(threads)

        allowed_train = set(int(i) for i in np.asarray(train_idx, dtype=int))
        x_train, y_train, _ = _build_sequence_samples(
            full_df=full_df,
            indices=np.asarray(train_idx, dtype=int),
            feature_cols=feature_cols,
            target_col=target_col,
            lookback=lookback,
            require_target=True,
            allowed_window_indices=allowed_train,
        )
        if x_train.shape[0] < 32:
            raise ValueError(
                f"TFT fold has only {x_train.shape[0]} train samples after sequence construction."
            )

        x_test, _, test_prediction_index = _build_sequence_samples(
            full_df=full_df,
            indices=np.asarray(test_idx, dtype=int),
            feature_cols=feature_cols,
            target_col=target_col,
            lookback=lookback,
            require_target=False,
            allowed_window_indices=None,
        )

        class _MiniTFT(nn.Module):
            """
            Compact transformer-based forecaster that follows TFT-like temporal encoding.
            """

            def __init__(self, *, input_dim: int, hidden: int, heads: int, layers: int, p: float, out_dim: int):
                super().__init__()
                self.input_proj = nn.Linear(input_dim, hidden)
                enc_layer = nn.TransformerEncoderLayer(
                    d_model=hidden,
                    nhead=heads,
                    dim_feedforward=max(hidden * 2, 32),
                    dropout=p,
                    batch_first=True,
                    activation="gelu",
                )
                self.encoder = nn.TransformerEncoder(enc_layer, num_layers=layers)
                self.gate = nn.Sequential(nn.Linear(hidden, hidden), nn.Sigmoid())
                self.head = nn.Linear(hidden, out_dim)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                h = self.input_proj(x)
                h = self.encoder(h)
                h_last = h[:, -1, :]
                h_last = h_last * self.gate(h_last)
                return self.head(h_last)

        def _quantile_loss(
            pred: torch.Tensor,
            target: torch.Tensor,
            quantile_tensor: torch.Tensor,
        ) -> torch.Tensor:
            err = target.unsqueeze(1) - pred
            loss = torch.maximum(quantile_tensor * err, (quantile_tensor - 1.0) * err)
            return loss.mean()

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = _MiniTFT(
            input_dim=x_train.shape[2],
            hidden=hidden_dim,
            heads=n_heads,
            layers=n_layers,
            p=dropout,
            out_dim=len(quantiles),
        ).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
        quantile_tensor = torch.tensor(quantiles, dtype=torch.float32, device=device)

        ds = TensorDataset(torch.tensor(x_train, dtype=torch.float32), torch.tensor(y_train, dtype=torch.float32))
        loader = DataLoader(ds, batch_size=max(8, min(batch_size, len(ds))), shuffle=True, drop_last=False)
        model.train()
        for _ in range(max(1, epochs)):
            for xb, yb in loader:
                xb = xb.to(device)
                yb = yb.to(device)
                optimizer.zero_grad(set_to_none=True)
                pred = model(xb)
                loss = _quantile_loss(pred, yb, quantile_tensor)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()

        if x_test.shape[0] == 0:
            empty = pd.Series(dtype="float32", index=test_prediction_index)
            return (
                empty,
                {},
                model,
                {
                    "lookback": lookback,
                    "quantiles": list(quantiles),
                    "prob_scale": float(np.std(y_train, ddof=1)) if len(y_train) >= 2 else None,
                    "tft_train_samples": int(x_train.shape[0]),
                    "tft_test_samples": 0,
                },
            )

        model.eval()
        with torch.no_grad():
            pred_tensor = model(torch.tensor(x_test, dtype=torch.float32, device=device))
            pred_np = pred_tensor.detach().cpu().numpy().astype(float)

        quantile_to_col: dict[float, str] = {}
        extra_cols: dict[str, pd.Series] = {}
        for i, q in enumerate(quantiles):
            col = f"pred_q{int(round(q * 100)):02d}"
            quantile_to_col[q] = col
            extra_cols[col] = pd.Series(pred_np[:, i], index=test_prediction_index, dtype="float32")

        median_q = min(quantiles, key=lambda q: abs(q - 0.5))
        pred_ret = pd.Series(extra_cols[quantile_to_col[median_q]], copy=False).astype("float32")
        low_q = min(quantiles)
        high_q = max(quantiles)
        if low_q != high_q:
            q_low = extra_cols[quantile_to_col[low_q]].astype(float)
            q_high = extra_cols[quantile_to_col[high_q]].astype(float)
            pred_vol = ((q_high - q_low).abs() / 2.0).astype("float32")
            extra_cols["pred_vol"] = pred_vol

        prob_scale = float(np.std(y_train, ddof=1)) if len(y_train) >= 2 else None
        fold_meta = {
            "lookback": lookback,
            "quantiles": list(quantiles),
            "median_quantile": float(median_q),
            "lower_quantile": float(low_q),
            "upper_quantile": float(high_q),
            "prob_scale": prob_scale,
            "tft_train_samples": int(x_train.shape[0]),
            "tft_test_samples": int(x_test.shape[0]),
            "tft_epochs": int(max(1, epochs)),
            "runtime_threads": runtime_meta.get("threads"),
        }
        return pred_ret, extra_cols, model, fold_meta

    return _predictor


__all__ = ["make_tft_fold_predictor"]
