from __future__ import annotations

from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from src.models.sequence import build_sequence_samples, fit_sequence_scaler


def _parse_quantiles(raw_quantiles: Sequence[float]) -> tuple[float, ...]:
    quantiles = tuple(sorted(float(q) for q in raw_quantiles))
    if len(quantiles) < 2:
        raise ValueError("model.params.quantiles for TFT must contain at least two values.")
    if len(set(quantiles)) != len(quantiles):
        raise ValueError("TFT quantiles must be unique.")
    if any(not (0.0 < q < 1.0) for q in quantiles):
        raise ValueError("TFT quantiles must be within (0, 1).")
    return quantiles


def _quantile_col(quantile: float) -> str:
    return f"pred_q{int(round(quantile * 100)):02d}"


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
            import torch.nn.functional as F
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
        scale_target = bool(model_params.get("scale_target", True))
        min_train_samples = int(model_params.get("min_train_samples", 32))
        quantiles = _parse_quantiles(model_params.get("quantiles", [0.1, 0.5, 0.9]))

        if hidden_dim <= 0 or n_heads <= 0 or n_layers <= 0:
            raise ValueError("TFT hidden_dim/num_heads/num_layers must be positive.")
        if hidden_dim % n_heads != 0:
            raise ValueError("TFT hidden_dim must be divisible by num_heads.")
        if min_train_samples <= 0:
            raise ValueError("TFT min_train_samples must be positive.")

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
        x_train = train_samples.x
        y_train = train_samples.y
        if x_train.shape[0] < min_train_samples:
            raise ValueError(
                f"TFT fold has only {x_train.shape[0]} train samples after sequence construction."
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
        x_test = test_samples.x
        test_prediction_index = test_samples.index

        class _GatedLinearUnit(nn.Module):
            def __init__(self, input_dim: int, output_dim: int):
                super().__init__()
                self.proj = nn.Linear(input_dim, output_dim * 2)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                value, gate = self.proj(x).chunk(2, dim=-1)
                return value * torch.sigmoid(gate)

        class _GateAddNorm(nn.Module):
            def __init__(self, input_dim: int, hidden: int, p: float):
                super().__init__()
                self.glu = _GatedLinearUnit(input_dim, hidden)
                self.dropout = nn.Dropout(p)
                self.norm = nn.LayerNorm(hidden)

            def forward(self, x: torch.Tensor, residual: torch.Tensor) -> torch.Tensor:
                return self.norm(self.dropout(self.glu(x)) + residual)

        class _GatedResidualNetwork(nn.Module):
            def __init__(self, input_dim: int, hidden: int, output_dim: int, p: float):
                super().__init__()
                self.fc1 = nn.Linear(input_dim, hidden)
                self.fc2 = nn.Linear(hidden, output_dim)
                self.dropout = nn.Dropout(p)
                self.skip = nn.Linear(input_dim, output_dim) if input_dim != output_dim else nn.Identity()
                self.gate_add_norm = _GateAddNorm(output_dim, output_dim, p)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                residual = self.skip(x)
                h = self.fc2(self.dropout(F.elu(self.fc1(x))))
                return self.gate_add_norm(h, residual)

        class _VariableSelectionNetwork(nn.Module):
            def __init__(self, input_dim: int, hidden: int, p: float):
                super().__init__()
                self.input_dim = input_dim
                self.feature_grns = nn.ModuleList(
                    [_GatedResidualNetwork(1, hidden, hidden, p) for _ in range(input_dim)]
                )
                self.context_grn = _GatedResidualNetwork(input_dim, hidden, hidden, p)
                self.weight_proj = nn.Linear(hidden, input_dim)

            def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
                if x.shape[-1] != self.input_dim:
                    raise ValueError("TFT variable selection input shape mismatch.")
                context = self.context_grn(x)
                weights = torch.softmax(self.weight_proj(context), dim=-1)
                transformed = torch.stack(
                    [
                        feature_grn(x[..., feature_idx : feature_idx + 1])
                        for feature_idx, feature_grn in enumerate(self.feature_grns)
                    ],
                    dim=-2,
                )
                selected = torch.sum(weights.unsqueeze(-1) * transformed, dim=-2)
                return selected, weights

        class _TemporalAttentionBlock(nn.Module):
            def __init__(self, hidden: int, heads: int, p: float):
                super().__init__()
                self.attention = nn.MultiheadAttention(
                    embed_dim=hidden,
                    num_heads=heads,
                    dropout=p,
                    batch_first=True,
                )
                self.attention_gate = _GateAddNorm(hidden, hidden, p)
                self.positionwise_grn = _GatedResidualNetwork(hidden, hidden, hidden, p)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                attended, _ = self.attention(x, x, x, need_weights=False)
                gated = self.attention_gate(attended, x)
                return self.positionwise_grn(gated)

        class _TemporalFusionTransformer(nn.Module):
            def __init__(
                self,
                *,
                input_dim: int,
                seq_len: int,
                hidden: int,
                heads: int,
                layers: int,
                p: float,
                out_dim: int,
            ):
                super().__init__()
                self.input_dim = input_dim
                self.seq_len = seq_len
                self.variable_selection = _VariableSelectionNetwork(input_dim, hidden, p)
                self.position = nn.Parameter(torch.zeros(1, seq_len, hidden))
                self.local_lstm = nn.LSTM(
                    input_size=hidden,
                    hidden_size=hidden,
                    num_layers=layers,
                    dropout=p if layers > 1 else 0.0,
                    batch_first=True,
                )
                self.local_gate = _GateAddNorm(hidden, hidden, p)
                self.static_enrichment = _GatedResidualNetwork(hidden, hidden, hidden, p)
                self.attention_blocks = nn.ModuleList(
                    [_TemporalAttentionBlock(hidden, heads, p) for _ in range(layers)]
                )
                self.decoder_grn = _GatedResidualNetwork(hidden, hidden, hidden, p)
                self.quantile_head = nn.Linear(hidden, out_dim)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                if x.shape[1] != self.seq_len or x.shape[2] != self.input_dim:
                    raise ValueError("TFT input shape mismatch.")
                selected, _ = self.variable_selection(x)
                selected = selected + self.position[:, : selected.shape[1], :]
                local, _ = self.local_lstm(selected)
                temporal = self.local_gate(local, selected)
                temporal = self.static_enrichment(temporal)
                for block in self.attention_blocks:
                    temporal = block(temporal)
                context = self.decoder_grn(temporal[:, -1, :])
                return self.quantile_head(context)

            def variable_importance(self, x: torch.Tensor) -> torch.Tensor:
                _, weights = self.variable_selection(x)
                return weights.mean(dim=(0, 1))

        def _quantile_loss(
            pred: torch.Tensor,
            target: torch.Tensor,
            quantile_tensor: torch.Tensor,
        ) -> torch.Tensor:
            err = target.unsqueeze(1) - pred
            loss = torch.maximum(quantile_tensor * err, (quantile_tensor - 1.0) * err)
            return loss.mean()

        def _attach_feature_importances(
            fitted_model: _TemporalFusionTransformer,
            values: np.ndarray,
        ) -> None:
            device_for_model = next(fitted_model.parameters()).device
            totals = torch.zeros(values.shape[2], dtype=torch.float32, device=device_for_model)
            rows = 0
            fitted_model.eval()
            importance_batch_size = max(8, min(batch_size, values.shape[0]))
            with torch.no_grad():
                for start in range(0, values.shape[0], importance_batch_size):
                    batch = torch.tensor(
                        values[start : start + importance_batch_size],
                        dtype=torch.float32,
                        device=device_for_model,
                    )
                    weights = fitted_model.variable_importance(batch)
                    totals += weights * int(batch.shape[0])
                    rows += int(batch.shape[0])
            raw = (totals / max(rows, 1)).detach().cpu().numpy().astype(float)
            raw = np.where(np.isfinite(raw), np.abs(raw), 0.0)
            total = float(raw.sum())
            if total > 0.0:
                raw = raw / total
            fitted_model.feature_importances_ = raw
            fitted_model.feature_names_ = list(feature_cols)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = _TemporalFusionTransformer(
            input_dim=x_train.shape[2],
            seq_len=x_train.shape[1],
            hidden=hidden_dim,
            heads=n_heads,
            layers=n_layers,
            p=dropout,
            out_dim=len(quantiles),
        ).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
        quantile_tensor = torch.tensor(quantiles, dtype=torch.float32, device=device)
        data_loader_generator = torch.Generator()
        data_loader_generator.manual_seed(seed)

        ds = TensorDataset(torch.tensor(x_train, dtype=torch.float32), torch.tensor(y_train, dtype=torch.float32))
        loader = DataLoader(
            ds,
            batch_size=max(8, min(batch_size, len(ds))),
            shuffle=True,
            drop_last=False,
            num_workers=0,
            generator=data_loader_generator,
        )
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

        _attach_feature_importances(model, x_train)

        train_target_unscaled = scaler.inverse_target(y_train)
        prob_scale = (
            float(np.std(train_target_unscaled, ddof=1))
            if len(train_target_unscaled) >= 2
            else None
        )

        if x_test.shape[0] == 0:
            empty = pd.Series(dtype="float32", index=test_prediction_index)
            return (
                empty,
                {},
                model,
                {
                    "lookback": lookback,
                    "quantiles": list(quantiles),
                    "prob_scale": prob_scale,
                    "tft_train_samples": int(x_train.shape[0]),
                    "tft_test_samples": 0,
                    "tft_architecture": "temporal_fusion_transformer",
                    "variable_selection": True,
                    "lstm_layers": int(n_layers),
                    "attention_layers": int(n_layers),
                },
            )

        model.eval()
        with torch.no_grad():
            pred_tensor = model(torch.tensor(x_test, dtype=torch.float32, device=device))
            pred_np = pred_tensor.detach().cpu().numpy().astype(float)
        pred_np = np.maximum.accumulate(pred_np, axis=1)

        quantile_to_col: dict[float, str] = {}
        extra_cols: dict[str, pd.Series] = {}
        for i, q in enumerate(quantiles):
            col = _quantile_col(q)
            quantile_to_col[q] = col
            extra_cols[col] = pd.Series(
                scaler.inverse_target(pred_np[:, i]),
                index=test_prediction_index,
                dtype="float32",
            )

        median_q = min(quantiles, key=lambda q: abs(q - 0.5))
        pred_ret = pd.Series(extra_cols[quantile_to_col[median_q]], copy=False).astype("float32")
        low_q = min(quantiles)
        high_q = max(quantiles)
        if low_q != high_q:
            q_low = extra_cols[quantile_to_col[low_q]].astype(float)
            q_high = extra_cols[quantile_to_col[high_q]].astype(float)
            pred_vol = ((q_high - q_low).abs() / 2.0).astype("float32")
            extra_cols["pred_vol"] = pred_vol

        fold_meta = {
            "lookback": lookback,
            "hidden_dim": hidden_dim,
            "num_heads": n_heads,
            "num_layers": n_layers,
            "quantiles": list(quantiles),
            "median_quantile": float(median_q),
            "lower_quantile": float(low_q),
            "upper_quantile": float(high_q),
            "prob_scale": prob_scale,
            "tft_train_samples": int(x_train.shape[0]),
            "tft_test_samples": int(x_test.shape[0]),
            "tft_epochs": int(max(1, epochs)),
            "tft_architecture": "temporal_fusion_transformer",
            "variable_selection": True,
            "lstm_layers": int(n_layers),
            "attention_layers": int(n_layers),
            "runtime_threads": runtime_meta.get("threads"),
            "deterministic": deterministic,
            "scaled_target": bool(scale_target),
        }
        return pred_ret, extra_cols, model, fold_meta

    return _predictor


__all__ = ["make_tft_fold_predictor"]
