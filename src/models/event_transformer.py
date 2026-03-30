from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.time_splits import (
    assert_no_forward_label_leakage,
    build_time_splits,
    trim_train_indices_for_horizon,
)
from src.experiments.contracts import TargetContract, validate_feature_target_contract
from src.experiments.support.diagnostics import (
    aggregate_label_distributions,
    summarize_feature_availability,
    summarize_label_distribution,
)
from src.experiments.support.metrics import (
    binary_classification_metrics,
    empty_classification_metrics,
    empty_regression_metrics,
    empty_volatility_metrics,
)
from src.models.runtime import infer_feature_columns, resolve_runtime_for_model
from src.models.sequence import build_sequence_samples, fit_sequence_scaler
from src.targets import build_classifier_target


def resolve_event_embedding_columns(
    *,
    embedding_dim: int,
    embedding_prefix: str = "event_emb",
) -> list[str]:
    if embedding_dim <= 0:
        raise ValueError("embedding_dim must be a positive integer.")
    width = max(2, len(str(int(embedding_dim) - 1)))
    return [f"{embedding_prefix}_{idx:0{width}d}" for idx in range(int(embedding_dim))]


def _prediction_alignment_summary(
    *,
    index: pd.Index,
    oos_mask: pd.Series,
    embedding_series: pd.Series,
) -> dict[str, Any]:
    predicted_mask = embedding_series.notna()
    oos_rows = int(oos_mask.sum())
    predicted_rows = int((predicted_mask & oos_mask).sum())
    non_oos_prediction_rows = int((predicted_mask & ~oos_mask).sum())
    missing_oos_prediction_rows = int((oos_mask & ~predicted_mask).sum())
    return {
        "oos_rows": oos_rows,
        "predicted_rows": predicted_rows,
        "non_oos_prediction_rows": non_oos_prediction_rows,
        "missing_oos_prediction_rows": missing_oos_prediction_rows,
        "oos_prediction_coverage": float(predicted_rows / max(oos_rows, 1)),
        "alignment_ok": bool(non_oos_prediction_rows == 0 and embedding_series.index.equals(index)),
    }


def train_event_transformer_encoder(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except Exception as exc:
        raise ImportError(
            "Event transformer encoder requires torch. Install torch to use "
            "model.kind='event_transformer_encoder'."
        ) from exc

    cfg = dict(model_cfg or {})
    model_params = dict(cfg.get("params", {}) or {})
    runtime_meta = resolve_runtime_for_model(
        model_cfg=cfg,
        model_params=model_params,
        estimator_family="torch",
    )
    pred_prob_col = cfg.get("pred_prob_col")
    out, label_col, _, target_meta = build_classifier_target(df=df, target_cfg=cfg.get("target", {}) or {})
    candidate_col = str(target_meta.get("candidate_col") or "")
    if not candidate_col:
        raise ValueError(
            "event_transformer_encoder requires a candidate-based target. "
            "Set target.kind='triple_barrier' with target.candidate_col."
        )

    feature_cols = infer_feature_columns(
        out,
        explicit_cols=cfg.get("feature_cols"),
        exclude={label_col, pred_prob_col} if pred_prob_col else {label_col},
    )
    if not feature_cols:
        raise ValueError("No feature columns resolved for event transformer encoder.")
    contract_meta = validate_feature_target_contract(
        out,
        feature_cols=feature_cols,
        target=TargetContract(target_col=label_col, horizon=int(target_meta["horizon"])),
    )

    lookback = int(model_params.get("lookback", 48))
    hidden_dim = int(model_params.get("hidden_dim", 32))
    num_heads = int(model_params.get("num_heads", 4))
    num_layers = int(model_params.get("num_layers", 2))
    dropout = float(model_params.get("dropout", 0.1))
    epochs = int(model_params.get("epochs", 8))
    batch_size = int(model_params.get("batch_size", 64))
    learning_rate = float(model_params.get("learning_rate", 1e-3))
    weight_decay = float(model_params.get("weight_decay", 1e-4))
    embedding_dim = int(model_params.get("embedding_dim", hidden_dim))
    embedding_prefix = str(model_params.get("embedding_prefix", "event_emb"))
    min_train_samples = int(model_params.get("min_train_samples", 32))
    event_embedding_cols = resolve_event_embedding_columns(
        embedding_dim=embedding_dim,
        embedding_prefix=embedding_prefix,
    )

    if lookback <= 1:
        raise ValueError("event_transformer_encoder params.lookback must be > 1.")
    if hidden_dim <= 0 or embedding_dim <= 0 or num_heads <= 0 or num_layers <= 0:
        raise ValueError("event_transformer_encoder dimensions must be positive.")
    if hidden_dim % num_heads != 0:
        raise ValueError("event_transformer_encoder hidden_dim must be divisible by num_heads.")
    if not 0.0 <= dropout < 1.0:
        raise ValueError("event_transformer_encoder dropout must be in [0,1).")
    if min_train_samples <= 1:
        raise ValueError("event_transformer_encoder min_train_samples must be > 1.")

    split_cfg = dict(cfg.get("split", {}) or {})
    split_method = str(split_cfg.get("method", "time"))
    splits = build_time_splits(
        method=split_method,
        n_samples=len(out),
        split_cfg=split_cfg,
        target_horizon=int(target_meta["horizon"]),
    )

    seed = int(runtime_meta.get("seed", 7))
    deterministic = bool(runtime_meta.get("deterministic", True))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        try:
            torch.use_deterministic_algorithms(True)
        except Exception as exc:
            if str(runtime_meta.get("repro_mode", "strict")) == "strict":
                raise RuntimeError(
                    "deterministic=True was requested but PyTorch deterministic mode could not be enabled."
                ) from exc
        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    threads = runtime_meta.get("threads")
    if isinstance(threads, int) and threads > 0:
        torch.set_num_threads(threads)

    candidate_mask = out[candidate_col].fillna(0.0).astype(bool)
    label_mask = out[label_col].notna()
    target_horizon = int(target_meta["horizon"])
    oos_mask = pd.Series(False, index=out.index, name="pred_is_oos")
    oos_assignment_count = pd.Series(0, index=out.index, dtype="int32")
    embedding_outputs = {
        col: pd.Series(np.nan, index=out.index, name=col, dtype="float32")
        for col in event_embedding_cols
    }
    head_prob = (
        pd.Series(np.nan, index=out.index, name=str(pred_prob_col), dtype="float32")
        if pred_prob_col
        else None
    )

    class _EventTransformer(nn.Module):
        def __init__(
            self,
            *,
            input_dim: int,
            seq_len: int,
            hidden: int,
            heads: int,
            layers: int,
            p: float,
            emb_dim: int,
        ):
            super().__init__()
            self.input_proj = nn.Linear(input_dim, hidden)
            self.position = nn.Parameter(torch.zeros(1, seq_len, hidden))
            enc_layer = nn.TransformerEncoderLayer(
                d_model=hidden,
                nhead=heads,
                dim_feedforward=max(hidden * 2, 32),
                dropout=p,
                batch_first=True,
                activation="gelu",
            )
            self.encoder = nn.TransformerEncoder(enc_layer, num_layers=layers)
            self.norm = nn.LayerNorm(hidden)
            self.embedding_head = nn.Linear(hidden, emb_dim)
            self.classifier_head = nn.Linear(emb_dim, 1)

        def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            tokens = self.input_proj(x) + self.position[:, : x.shape[1], :]
            encoded = self.encoder(tokens)
            pooled = self.norm(encoded[:, -1, :])
            embedding = self.embedding_head(pooled)
            logits = self.classifier_head(torch.tanh(embedding)).squeeze(-1)
            return embedding, logits

    fold_meta: list[dict[str, Any]] = []
    train_label_distributions: list[dict[str, Any]] = []
    eval_label_distributions: list[dict[str, Any]] = []
    eval_labels_all: list[np.ndarray] = []
    eval_probs_all: list[np.ndarray] = []
    total_train_rows = 0
    total_test_pred_rows = 0
    total_trimmed_rows = 0
    total_train_rows_dropped_missing = 0
    total_test_rows_not_candidates = 0
    total_test_rows_without_prediction = 0
    folds_with_zero_predictions = 0
    model: object | None = None

    for split in splits:
        raw_train_idx = np.asarray(split.train_idx, dtype=int)
        safe_train_idx = trim_train_indices_for_horizon(
            raw_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )
        assert_no_forward_label_leakage(
            safe_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )
        trimmed_rows = int(len(raw_train_idx) - len(safe_train_idx))
        total_trimmed_rows += trimmed_rows

        scaler = fit_sequence_scaler(
            full_df=out,
            train_idx=safe_train_idx,
            feature_cols=feature_cols,
            target_col=label_col,
            scale_target=False,
        )
        allowed_train = set(int(i) for i in np.asarray(safe_train_idx, dtype=int))
        train_event_idx = np.asarray(
            [
                int(i)
                for i in safe_train_idx
                if bool(candidate_mask.iloc[int(i)]) and bool(label_mask.iloc[int(i)])
            ],
            dtype=int,
        )
        test_event_idx = np.asarray(
            [int(i) for i in np.asarray(split.test_idx, dtype=int) if bool(candidate_mask.iloc[int(i)])],
            dtype=int,
        )

        train_samples = build_sequence_samples(
            full_df=out,
            indices=train_event_idx,
            feature_cols=feature_cols,
            target_col=label_col,
            lookback=lookback,
            require_target=True,
            scaler=scaler,
            allowed_window_indices=allowed_train,
        )
        if train_samples.x.shape[0] < min_train_samples:
            raise ValueError(
                "event_transformer_encoder fold has too few train samples after sequence construction: "
                f"{train_samples.x.shape[0]} < {min_train_samples}."
            )
        y_train = train_samples.y.astype("float32")
        if int(pd.Series(y_train).nunique()) < 2:
            raise ValueError(
                f"event_transformer_encoder fold {split.fold} has a single target class after preprocessing."
            )
        train_label_distribution = summarize_label_distribution(pd.Series(y_train.astype(int)))
        train_label_distributions.append(train_label_distribution)

        test_samples = build_sequence_samples(
            full_df=out,
            indices=test_event_idx,
            feature_cols=feature_cols,
            target_col=label_col,
            lookback=lookback,
            require_target=False,
            scaler=scaler,
            allowed_window_indices=None,
        )

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = _EventTransformer(
            input_dim=train_samples.x.shape[2],
            seq_len=train_samples.x.shape[1],
            hidden=hidden_dim,
            heads=num_heads,
            layers=num_layers,
            p=dropout,
            emb_dim=embedding_dim,
        ).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
        loss_fn = nn.BCEWithLogitsLoss()
        train_ds = TensorDataset(
            torch.tensor(train_samples.x, dtype=torch.float32),
            torch.tensor(y_train, dtype=torch.float32),
        )
        train_loader = DataLoader(
            train_ds,
            batch_size=max(8, min(batch_size, len(train_ds))),
            shuffle=True,
            drop_last=False,
            num_workers=0,
            generator=torch.Generator().manual_seed(seed),
        )

        model.train()
        for _ in range(max(1, epochs)):
            for xb, yb in train_loader:
                xb = xb.to(device)
                yb = yb.to(device)
                optimizer.zero_grad(set_to_none=True)
                _, logits = model(xb)
                loss = loss_fn(logits, yb)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()

        pred_rows = int(test_samples.x.shape[0])
        if pred_rows == 0:
            folds_with_zero_predictions += 1
        total_test_rows_not_candidates += int(len(split.test_idx) - len(test_event_idx))
        total_test_rows_without_prediction += int(len(test_event_idx) - pred_rows)
        train_rows_dropped_missing = int(len(train_event_idx) - train_samples.x.shape[0])
        total_train_rows_dropped_missing += train_rows_dropped_missing

        fold_eval_metrics = empty_classification_metrics()
        eval_label_distribution = summarize_label_distribution(pd.Series(dtype=int))
        if pred_rows > 0:
            model.eval()
            with torch.no_grad():
                emb_tensor, logits_tensor = model(
                    torch.tensor(test_samples.x, dtype=torch.float32, device=device)
                )
            emb_np = emb_tensor.detach().cpu().numpy().astype("float32")
            prob_np = torch.sigmoid(logits_tensor).detach().cpu().numpy().astype("float32")
            for col_idx, col_name in enumerate(event_embedding_cols):
                embedding_outputs[col_name].loc[test_samples.index] = emb_np[:, col_idx]
            if head_prob is not None:
                head_prob.loc[test_samples.index] = prob_np

            eval_labels = out.loc[test_samples.index, label_col].dropna().astype(int)
            if not eval_labels.empty:
                eval_probs = pd.Series(prob_np, index=test_samples.index, dtype="float32").reindex(eval_labels.index)
                fold_eval_metrics = binary_classification_metrics(eval_labels, eval_probs)
                eval_label_distribution = summarize_label_distribution(eval_labels)
                eval_labels_all.append(eval_labels.to_numpy(dtype=int, copy=False))
                eval_probs_all.append(eval_probs.to_numpy(dtype=float, copy=False))
        eval_label_distributions.append(eval_label_distribution)

        fold_test_idx = out.index[np.asarray(split.test_idx, dtype=int)]
        oos_mask.loc[fold_test_idx] = True
        oos_assignment_count.loc[fold_test_idx] += 1
        total_train_rows += int(train_samples.x.shape[0])
        total_test_pred_rows += pred_rows
        fold_meta.append(
            {
                "fold": int(split.fold),
                "train_start": int(split.train_start),
                "train_end": int(split.train_end),
                "effective_train_start": int(safe_train_idx.min()) if len(safe_train_idx) else None,
                "effective_train_end": int(safe_train_idx.max() + 1) if len(safe_train_idx) else None,
                "trimmed_for_horizon_rows": trimmed_rows,
                "test_start": int(split.test_start),
                "test_end": int(split.test_end),
                "train_rows_raw": int(len(train_event_idx)),
                "train_rows": int(train_samples.x.shape[0]),
                "train_rows_dropped_missing": train_rows_dropped_missing,
                "test_rows": int(len(split.test_idx)),
                "test_candidate_rows": int(len(test_event_idx)),
                "test_pred_rows": pred_rows,
                "test_rows_not_candidates": int(len(split.test_idx) - len(test_event_idx)),
                "test_rows_without_prediction": int(len(test_event_idx) - pred_rows),
                "train_feature_availability": summarize_feature_availability(out.iloc[safe_train_idx], feature_cols),
                "test_feature_availability": summarize_feature_availability(out.iloc[np.asarray(split.test_idx, dtype=int)], feature_cols),
                "train_label_distribution": train_label_distribution,
                "eval_label_distribution": eval_label_distribution,
                "classification_metrics": fold_eval_metrics,
                "regression_metrics": empty_regression_metrics(),
                "volatility_metrics": empty_volatility_metrics(),
                "sequence_train_samples": int(train_samples.x.shape[0]),
                "sequence_test_samples": pred_rows,
            }
        )

    if model is None:
        raise ValueError("Event transformer encoder training failed: no valid folds were trained.")
    if (oos_assignment_count > 1).any():
        raise ValueError("Overlapping test windows detected. Use non-overlapping split configuration.")

    if head_prob is not None:
        out[str(pred_prob_col)] = head_prob
    for col_name, series in embedding_outputs.items():
        out[col_name] = series
    out["pred_is_oos"] = oos_mask

    oos_classification_summary = empty_classification_metrics()
    if eval_labels_all and eval_probs_all:
        y_all = pd.Series(np.concatenate(eval_labels_all), dtype=int)
        p_all = pd.Series(np.concatenate(eval_probs_all), dtype=float)
        oos_classification_summary = binary_classification_metrics(y_all, p_all)

    label_distribution = {
        "train": aggregate_label_distributions(train_label_distributions),
        "oos_evaluation": aggregate_label_distributions(eval_label_distributions),
    }
    alignment_probe_col = embedding_outputs[event_embedding_cols[0]]
    prediction_diagnostics = _prediction_alignment_summary(
        index=out.index,
        oos_mask=oos_mask,
        embedding_series=alignment_probe_col,
    )
    meta = {
        "model_kind": "event_transformer_encoder",
        "runtime": runtime_meta,
        "feature_cols": feature_cols,
        "embedding_cols": event_embedding_cols,
        "pred_prob_col": str(pred_prob_col) if pred_prob_col else None,
        "label_col": label_col,
        "split_method": split_method,
        "split_index": int(splits[0].test_start),
        "n_folds": int(len(splits)),
        "folds": fold_meta,
        "train_rows": int(total_train_rows),
        "test_pred_rows": int(total_test_pred_rows),
        "oos_rows": int(oos_mask.sum()),
        "oos_prediction_coverage": float(total_test_pred_rows / max(int(oos_mask.sum()), 1)),
        "oos_classification_summary": oos_classification_summary,
        "oos_regression_summary": empty_regression_metrics(),
        "oos_volatility_summary": empty_volatility_metrics(),
        "feature_importance": {},
        "label_distribution": label_distribution,
        "prediction_diagnostics": prediction_diagnostics,
        "missing_value_diagnostics": {
            "train_rows_dropped_missing": int(total_train_rows_dropped_missing),
            "test_rows_not_candidates": int(total_test_rows_not_candidates),
            "test_rows_without_prediction": int(total_test_rows_without_prediction),
            "folds_with_zero_predictions": int(folds_with_zero_predictions),
        },
        "target": target_meta,
        "returns_col": returns_col,
        "contracts": contract_meta,
        "anti_leakage": {
            "target_horizon": target_horizon,
            "total_trimmed_train_rows": int(total_trimmed_rows),
            "sequence_lookback": lookback,
            "window_ends_at_event_time": True,
            "train_windows_restricted_to_fold": True,
            "candidate_based_training": True,
        },
    }
    return out, model, meta


__all__ = ["resolve_event_embedding_columns", "train_event_transformer_encoder"]
