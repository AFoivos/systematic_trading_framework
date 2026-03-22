from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from src.models.sequence import build_sequence_samples, fit_sequence_scaler


def make_lstm_fold_predictor() -> Callable[
    [pd.DataFrame, np.ndarray, np.ndarray, list[str], str, dict[str, Any], dict[str, Any]],
    tuple[pd.Series, dict[str, pd.Series], object, dict[str, Any]],
]:
    """
    Build the fold predictor closure for a compact LSTM forecaster.
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
                "LSTM forecaster requires torch. Install torch to use model.kind='lstm_forecaster'."
            ) from exc

        lookback = int(model_params.get("lookback", 48))
        hidden_dim = int(model_params.get("hidden_dim", 32))
        num_layers = int(model_params.get("num_layers", 2))
        dropout = float(model_params.get("dropout", 0.1))
        epochs = int(model_params.get("epochs", 12))
        batch_size = int(model_params.get("batch_size", 64))
        learning_rate = float(model_params.get("learning_rate", 1e-3))
        weight_decay = float(model_params.get("weight_decay", 1e-4))
        quantiles_cfg = model_params.get("quantiles")
        quantiles = tuple(float(q) for q in quantiles_cfg) if quantiles_cfg is not None else ()
        scale_target = bool(model_params.get("scale_target", True))

        if hidden_dim <= 0 or num_layers <= 0:
            raise ValueError("LSTM hidden_dim and num_layers must be positive.")
        if dropout < 0.0 or dropout >= 1.0:
            raise ValueError("LSTM dropout must be in [0,1).")
        if quantiles and (len(quantiles) < 2 or any(not (0.0 < q < 1.0) for q in quantiles)):
            raise ValueError("LSTM quantiles must contain at least two values within (0,1).")

        seed = int(runtime_meta.get("seed", 7))
        deterministic = bool(runtime_meta.get("deterministic", True))
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        if deterministic:
            try:
                torch.use_deterministic_algorithms(True)
            except Exception:
                pass
            if hasattr(torch.backends, "cudnn"):
                torch.backends.cudnn.deterministic = True
                torch.backends.cudnn.benchmark = False
        threads = runtime_meta.get("threads")
        if isinstance(threads, int) and threads > 0:
            torch.set_num_threads(threads)

        scaler = fit_sequence_scaler(
            full_df=full_df,
            train_idx=np.asarray(train_idx, dtype=int),
            feature_cols=feature_cols,
            target_col=target_col,
            scale_target=scale_target,
        )
        allowed_train = set(int(i) for i in np.asarray(train_idx, dtype=int))
        train_samples = build_sequence_samples(
            full_df=full_df,
            indices=np.asarray(train_idx, dtype=int),
            feature_cols=feature_cols,
            target_col=target_col,
            lookback=lookback,
            require_target=True,
            scaler=scaler,
            allowed_window_indices=allowed_train,
        )
        if train_samples.x.shape[0] < 32:
            raise ValueError(
                f"LSTM fold has only {train_samples.x.shape[0]} train samples after sequence construction."
            )

        test_samples = build_sequence_samples(
            full_df=full_df,
            indices=np.asarray(test_idx, dtype=int),
            feature_cols=feature_cols,
            target_col=target_col,
            lookback=lookback,
            require_target=False,
            scaler=scaler,
            allowed_window_indices=None,
        )

        class _LSTMForecaster(nn.Module):
            def __init__(self, *, input_dim: int, hidden: int, layers: int, p: float, out_dim: int):
                super().__init__()
                lstm_dropout = p if layers > 1 else 0.0
                self.lstm = nn.LSTM(
                    input_size=input_dim,
                    hidden_size=hidden,
                    num_layers=layers,
                    dropout=lstm_dropout,
                    batch_first=True,
                )
                self.norm = nn.LayerNorm(hidden)
                self.head = nn.Linear(hidden, out_dim)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                out, _ = self.lstm(x)
                last = self.norm(out[:, -1, :])
                return self.head(last)

        def _quantile_loss(pred: torch.Tensor, target: torch.Tensor, q: torch.Tensor) -> torch.Tensor:
            err = target.unsqueeze(1) - pred
            return torch.maximum(q * err, (q - 1.0) * err).mean()

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        out_dim = len(quantiles) if quantiles else 1
        model = _LSTMForecaster(
            input_dim=train_samples.x.shape[2],
            hidden=hidden_dim,
            layers=num_layers,
            p=dropout,
            out_dim=out_dim,
        ).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
        quantile_tensor = torch.tensor(quantiles, dtype=torch.float32, device=device) if quantiles else None

        ds = TensorDataset(
            torch.tensor(train_samples.x, dtype=torch.float32),
            torch.tensor(train_samples.y, dtype=torch.float32),
        )
        loader = DataLoader(
            ds,
            batch_size=max(8, min(batch_size, len(ds))),
            shuffle=True,
            drop_last=False,
            num_workers=0,
            generator=torch.Generator().manual_seed(seed),
        )

        model.train()
        for _ in range(max(1, epochs)):
            for xb, yb in loader:
                xb = xb.to(device)
                yb = yb.to(device)
                optimizer.zero_grad(set_to_none=True)
                pred = model(xb)
                if quantile_tensor is not None:
                    loss = _quantile_loss(pred, yb, quantile_tensor)
                else:
                    loss = torch.nn.functional.mse_loss(pred.squeeze(-1), yb)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()

        if test_samples.x.shape[0] == 0:
            empty = pd.Series(dtype="float32", index=test_samples.index)
            return (
                empty,
                {},
                model,
                {
                    "lookback": lookback,
                    "lstm_train_samples": int(train_samples.x.shape[0]),
                    "lstm_test_samples": 0,
                    "prob_scale": float(np.std(train_samples.y, ddof=1)) if len(train_samples.y) >= 2 else None,
                    "quantiles": list(quantiles),
                },
            )

        model.eval()
        with torch.no_grad():
            pred_tensor = model(torch.tensor(test_samples.x, dtype=torch.float32, device=device))
            pred_np = pred_tensor.detach().cpu().numpy().astype(float)

        extra_cols: dict[str, pd.Series] = {}
        if quantiles:
            for i, q in enumerate(quantiles):
                col_name = f"pred_q{int(round(q * 100)):02d}"
                extra_cols[col_name] = pd.Series(
                    scaler.inverse_target(pred_np[:, i]),
                    index=test_samples.index,
                    dtype="float32",
                )
            median_q = min(quantiles, key=lambda q: abs(q - 0.5))
            pred_ret = pd.Series(extra_cols[f"pred_q{int(round(median_q * 100)):02d}"], copy=False).astype("float32")
            q_low = extra_cols[f"pred_q{int(round(min(quantiles) * 100)):02d}"].astype(float)
            q_high = extra_cols[f"pred_q{int(round(max(quantiles) * 100)):02d}"].astype(float)
            extra_cols["pred_vol"] = ((q_high - q_low).abs() / 2.0).astype("float32")
        else:
            pred_ret = pd.Series(
                scaler.inverse_target(pred_np[:, 0]),
                index=test_samples.index,
                dtype="float32",
            )

        prob_scale = float(np.std(scaler.inverse_target(train_samples.y), ddof=1)) if len(train_samples.y) >= 2 else None
        fold_meta = {
            "lookback": lookback,
            "hidden_dim": hidden_dim,
            "num_layers": num_layers,
            "dropout": dropout,
            "lstm_train_samples": int(train_samples.x.shape[0]),
            "lstm_test_samples": int(test_samples.x.shape[0]),
            "quantiles": list(quantiles),
            "prob_scale": prob_scale,
            "runtime_threads": runtime_meta.get("threads"),
            "deterministic": deterministic,
            "scaled_target": bool(scale_target),
        }
        return pred_ret, extra_cols, model, fold_meta

    return _predictor


__all__ = ["make_lstm_fold_predictor"]
