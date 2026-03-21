from __future__ import annotations

from typing import Sequence

import gymnasium as gym
import torch
from torch import nn

from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


_ALLOWED_EXTRACTORS = {"flatten", "cnn1d", "lstm", "transformer"}


class SequenceFeatureExtractor(BaseFeaturesExtractor):
    """
    Sequence-aware feature extractor for SB3 policies operating on rolling windows.
    """

    def __init__(
        self,
        observation_space: gym.Space,
        *,
        kind: str = "flatten",
        features_dim: int = 64,
        hidden_dim: int = 64,
        num_layers: int = 1,
        num_heads: int = 4,
        dropout: float = 0.1,
        conv_channels: Sequence[int] = (32, 64),
        kernel_sizes: Sequence[int] = (3, 3),
    ) -> None:
        if not isinstance(observation_space, gym.spaces.Box):
            raise TypeError("SequenceFeatureExtractor expects a Box observation space.")
        if len(observation_space.shape) != 2:
            raise ValueError("SequenceFeatureExtractor expects observations with shape=(window, features).")
        if features_dim <= 0:
            raise ValueError("features_dim must be > 0.")
        if kind not in _ALLOWED_EXTRACTORS:
            raise ValueError(f"Unsupported extractor kind: {kind}")

        super().__init__(observation_space, features_dim=features_dim)
        self.kind = kind
        self.window_size = int(observation_space.shape[0])
        self.input_dim = int(observation_space.shape[1])

        if kind == "flatten":
            self.extractor = nn.Sequential(
                nn.Flatten(),
                nn.Linear(self.window_size * self.input_dim, features_dim),
                nn.ReLU(),
            )
            return

        if kind == "cnn1d":
            channels = list(int(v) for v in conv_channels)
            kernels = list(int(v) for v in kernel_sizes)
            if not channels:
                raise ValueError("conv_channels must be non-empty for kind='cnn1d'.")
            if len(kernels) not in {1, len(channels)}:
                raise ValueError("kernel_sizes must have length 1 or match conv_channels length.")
            if len(kernels) == 1:
                kernels = kernels * len(channels)

            layers: list[nn.Module] = []
            in_channels = self.input_dim
            for out_channels, kernel_size in zip(channels, kernels):
                padding = max(int(kernel_size) // 2, 0)
                layers.append(
                    nn.Conv1d(
                        in_channels=in_channels,
                        out_channels=int(out_channels),
                        kernel_size=int(kernel_size),
                        padding=padding,
                    )
                )
                layers.append(nn.ReLU())
                in_channels = int(out_channels)
            self.extractor = nn.Sequential(*layers)
            with torch.no_grad():
                sample = torch.zeros(1, self.input_dim, self.window_size)
                flattened_dim = int(self.extractor(sample).reshape(1, -1).shape[1])
            self.project = nn.Sequential(
                nn.Flatten(),
                nn.Linear(flattened_dim, features_dim),
                nn.ReLU(),
            )
            return

        if hidden_dim <= 0:
            raise ValueError("hidden_dim must be > 0.")
        if num_layers <= 0:
            raise ValueError("num_layers must be > 0.")

        if kind == "lstm":
            lstm_dropout = float(dropout) if int(num_layers) > 1 else 0.0
            self.extractor = nn.LSTM(
                input_size=self.input_dim,
                hidden_size=int(hidden_dim),
                num_layers=int(num_layers),
                dropout=lstm_dropout,
                batch_first=True,
            )
            self.project = (
                nn.Identity()
                if int(hidden_dim) == features_dim
                else nn.Sequential(nn.Linear(int(hidden_dim), features_dim), nn.ReLU())
            )
            return

        if int(hidden_dim) % int(num_heads) != 0:
            raise ValueError("hidden_dim must be divisible by num_heads for transformer extractor.")

        self.input_projection = nn.Linear(self.input_dim, int(hidden_dim))
        self.position_embedding = nn.Parameter(torch.zeros(1, self.window_size, int(hidden_dim)))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=int(hidden_dim),
            nhead=int(num_heads),
            dim_feedforward=max(int(hidden_dim) * 2, 32),
            dropout=float(dropout),
            batch_first=True,
            activation="gelu",
        )
        self.extractor = nn.TransformerEncoder(encoder_layer, num_layers=int(num_layers))
        self.project = (
            nn.Identity()
            if int(hidden_dim) == features_dim
            else nn.Sequential(nn.Linear(int(hidden_dim), features_dim), nn.ReLU())
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        x = observations.float()
        if self.kind == "flatten":
            return self.extractor(x)
        if self.kind == "cnn1d":
            features = self.extractor(x.transpose(1, 2))
            return self.project(features)
        if self.kind == "lstm":
            _, (hidden, _) = self.extractor(x)
            return self.project(hidden[-1])

        hidden = self.input_projection(x) + self.position_embedding[:, : x.shape[1], :]
        encoded = self.extractor(hidden)
        pooled = encoded.mean(dim=1)
        return self.project(pooled)


__all__ = ["SequenceFeatureExtractor"]
