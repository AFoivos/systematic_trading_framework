from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StorageContext:
    symbols: list[str]
    source: str | None
    interval: str | None
    start: str | None
    end: str | None
    pit: dict[str, Any] = field(default_factory=dict)
    pit_hash_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbols": list(self.symbols),
            "source": self.source,
            "interval": self.interval,
            "start": self.start,
            "end": self.end,
            "pit": dict(self.pit),
            "pit_hash_sha256": self.pit_hash_sha256,
        }


@dataclass(frozen=True)
class EvaluationPayload:
    scope: str
    primary_summary: dict[str, Any]
    timeline_summary: dict[str, Any]
    oos_only_summary: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "scope": self.scope,
            "primary_summary": dict(self.primary_summary),
            "timeline_summary": dict(self.timeline_summary),
        }
        if self.oos_only_summary is not None:
            payload["oos_only_summary"] = dict(self.oos_only_summary)
        return payload | dict(self.extra)


@dataclass(frozen=True)
class MonitoringPayload:
    asset_count: int
    drifted_feature_count: int
    feature_count: int
    per_asset: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_count": self.asset_count,
            "drifted_feature_count": self.drifted_feature_count,
            "feature_count": self.feature_count,
            "per_asset": dict(self.per_asset),
        }


@dataclass(frozen=True)
class ExecutionPayload:
    mode: str
    capital: float
    as_of: str | None
    order_count: int
    gross_target: float
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "capital": self.capital,
            "as_of": self.as_of,
            "order_count": self.order_count,
            "gross_target": self.gross_target,
        } | dict(self.extra)


@dataclass(frozen=True)
class PortfolioMetaPayload:
    construction: str
    asset_count: int
    alignment: str
    expected_return_col: str | None
    avg_gross_exposure: float
    avg_net_exposure: float
    avg_turnover: float
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "construction": self.construction,
            "asset_count": self.asset_count,
            "alignment": self.alignment,
            "expected_return_col": self.expected_return_col,
            "avg_gross_exposure": self.avg_gross_exposure,
            "avg_net_exposure": self.avg_net_exposure,
            "avg_turnover": self.avg_turnover,
        } | dict(self.extra)


__all__ = [
    "EvaluationPayload",
    "ExecutionPayload",
    "MonitoringPayload",
    "PortfolioMetaPayload",
    "StorageContext",
]
