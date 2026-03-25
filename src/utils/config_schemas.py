from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _extras(data: dict[str, Any], known: set[str]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k not in known}


@dataclass(frozen=True)
class FeatureStep:
    step: str
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureStep":
        known = {"step", "params", "enabled"}
        return cls(
            step=str(data["step"]),
            params=dict(data.get("params", {}) or {}),
            enabled=bool(data.get("enabled", True)),
            extra=_extras(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"step": self.step, "params": dict(self.params), "enabled": self.enabled} | dict(self.extra)


@dataclass(frozen=True)
class DataConfig:
    source: str
    interval: str
    start: str | None
    end: str | None
    alignment: str
    symbol: str | None = None
    symbols: list[str] | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    pit: dict[str, Any] = field(default_factory=dict)
    storage: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DataConfig":
        known = {
            "source",
            "interval",
            "start",
            "end",
            "alignment",
            "symbol",
            "symbols",
            "api_key",
            "api_key_env",
            "pit",
            "storage",
        }
        return cls(
            source=str(data.get("source", "yahoo")),
            interval=str(data.get("interval", "1d")),
            start=data.get("start"),
            end=data.get("end"),
            alignment=str(data.get("alignment", "inner")),
            symbol=data.get("symbol"),
            symbols=[str(v) for v in data["symbols"]] if data.get("symbols") is not None else None,
            api_key=data.get("api_key"),
            api_key_env=data.get("api_key_env"),
            pit=dict(data.get("pit", {}) or {}),
            storage=dict(data.get("storage", {}) or {}),
            extra=_extras(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "source": self.source,
            "interval": self.interval,
            "start": self.start,
            "end": self.end,
            "alignment": self.alignment,
            "symbol": self.symbol,
            "symbols": list(self.symbols) if self.symbols is not None else None,
            "api_key": self.api_key,
            "api_key_env": self.api_key_env,
            "pit": dict(self.pit),
            "storage": dict(self.storage),
        }
        return payload | dict(self.extra)


@dataclass(frozen=True)
class ModelConfig:
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    feature_cols: list[str] | None = None
    target: dict[str, Any] = field(default_factory=dict)
    split: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    env: dict[str, Any] = field(default_factory=dict)
    use_features: bool = True
    pred_prob_col: str | None = None
    pred_ret_col: str | None = None
    returns_input_col: str | None = None
    signal_col: str | None = None
    action_col: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelConfig":
        known = {
            "kind",
            "params",
            "feature_cols",
            "target",
            "split",
            "runtime",
            "env",
            "use_features",
            "pred_prob_col",
            "pred_ret_col",
            "returns_input_col",
            "signal_col",
            "action_col",
        }
        feature_cols_raw = data.get("feature_cols")
        if feature_cols_raw is not None and not isinstance(feature_cols_raw, list):
            raise TypeError("model.feature_cols must be a list[str].")
        return cls(
            kind=str(data.get("kind", "none")),
            params=dict(data.get("params", {}) or {}),
            feature_cols=[str(v) for v in feature_cols_raw] if feature_cols_raw is not None else None,
            target=dict(data.get("target", {}) or {}),
            split=dict(data.get("split", {}) or {}),
            runtime=dict(data.get("runtime", {}) or {}),
            env=dict(data.get("env", {}) or {}),
            use_features=bool(data.get("use_features", True)),
            pred_prob_col=data.get("pred_prob_col"),
            pred_ret_col=data.get("pred_ret_col"),
            returns_input_col=data.get("returns_input_col"),
            signal_col=data.get("signal_col"),
            action_col=data.get("action_col"),
            extra=_extras(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "kind": self.kind,
            "params": dict(self.params),
            "feature_cols": list(self.feature_cols) if self.feature_cols is not None else None,
            "target": dict(self.target),
            "split": dict(self.split),
            "runtime": dict(self.runtime),
            "env": dict(self.env),
            "use_features": self.use_features,
            "pred_prob_col": self.pred_prob_col,
            "pred_ret_col": self.pred_ret_col,
            "returns_input_col": self.returns_input_col,
            "signal_col": self.signal_col,
            "action_col": self.action_col,
        }
        return payload | dict(self.extra)


@dataclass(frozen=True)
class SignalsConfig:
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SignalsConfig":
        known = {"kind", "params"}
        return cls(
            kind=str(data.get("kind", "none")),
            params=dict(data.get("params", {}) or {}),
            extra=_extras(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "params": dict(self.params)} | dict(self.extra)


@dataclass(frozen=True)
class RiskConfig:
    cost_per_turnover: float
    slippage_per_turnover: float
    target_vol: float | None
    max_leverage: float
    dd_guard: dict[str, Any] = field(default_factory=dict)
    vol_col: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RiskConfig":
        known = {
            "cost_per_turnover",
            "slippage_per_turnover",
            "target_vol",
            "max_leverage",
            "dd_guard",
            "vol_col",
        }
        target_vol = data.get("target_vol")
        return cls(
            cost_per_turnover=float(data.get("cost_per_turnover", 0.0)),
            slippage_per_turnover=float(data.get("slippage_per_turnover", 0.0)),
            target_vol=float(target_vol) if target_vol is not None else None,
            max_leverage=float(data.get("max_leverage", 3.0)),
            dd_guard=dict(data.get("dd_guard", {}) or {}),
            vol_col=data.get("vol_col"),
            extra=_extras(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "cost_per_turnover": self.cost_per_turnover,
            "slippage_per_turnover": self.slippage_per_turnover,
            "target_vol": self.target_vol,
            "max_leverage": self.max_leverage,
            "dd_guard": dict(self.dd_guard),
            "vol_col": self.vol_col,
        }
        return payload | dict(self.extra)


@dataclass(frozen=True)
class BacktestConfig:
    returns_col: str
    signal_col: str
    periods_per_year: int
    returns_type: str
    missing_return_policy: str
    min_holding_bars: int = 0
    subset: str | None = None
    vol_col: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BacktestConfig":
        known = {
            "returns_col",
            "signal_col",
            "periods_per_year",
            "returns_type",
            "missing_return_policy",
            "min_holding_bars",
            "subset",
            "vol_col",
        }
        return cls(
            returns_col=str(data.get("returns_col", "")),
            signal_col=str(data.get("signal_col", "")),
            periods_per_year=int(data.get("periods_per_year", 252)),
            returns_type=str(data.get("returns_type", "simple")),
            missing_return_policy=str(data.get("missing_return_policy", "raise_if_exposed")),
            min_holding_bars=int(data.get("min_holding_bars", 0)),
            subset=data.get("subset"),
            vol_col=data.get("vol_col"),
            extra=_extras(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "returns_col": self.returns_col,
            "signal_col": self.signal_col,
            "periods_per_year": self.periods_per_year,
            "returns_type": self.returns_type,
            "missing_return_policy": self.missing_return_policy,
            "min_holding_bars": self.min_holding_bars,
            "subset": self.subset,
            "vol_col": self.vol_col,
        }
        return payload | dict(self.extra)


@dataclass(frozen=True)
class PortfolioConfig:
    enabled: bool
    construction: str
    gross_target: float
    long_short: bool
    expected_return_col: str | None = None
    covariance_window: int | None = 60
    covariance_rebalance_step: int | None = 1
    risk_aversion: float = 5.0
    trade_aversion: float = 0.0
    constraints: dict[str, Any] = field(default_factory=dict)
    asset_groups: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PortfolioConfig":
        known = {
            "enabled",
            "construction",
            "gross_target",
            "long_short",
            "expected_return_col",
            "covariance_window",
            "covariance_rebalance_step",
            "risk_aversion",
            "trade_aversion",
            "constraints",
            "asset_groups",
        }
        covariance_window_raw = data.get("covariance_window", 60)
        covariance_rebalance_step_raw = data.get("covariance_rebalance_step", 1)
        return cls(
            enabled=bool(data.get("enabled", False)),
            construction=str(data.get("construction", "signal_weights")),
            gross_target=float(data.get("gross_target", 1.0)),
            long_short=bool(data.get("long_short", True)),
            expected_return_col=data.get("expected_return_col"),
            covariance_window=(
                int(covariance_window_raw) if covariance_window_raw is not None else None
            ),
            covariance_rebalance_step=(
                int(covariance_rebalance_step_raw)
                if covariance_rebalance_step_raw is not None
                else None
            ),
            risk_aversion=float(data.get("risk_aversion", 5.0)),
            trade_aversion=float(data.get("trade_aversion", 0.0)),
            constraints=dict(data.get("constraints", {}) or {}),
            asset_groups=dict(data.get("asset_groups", {}) or {}),
            extra=_extras(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "enabled": self.enabled,
            "construction": self.construction,
            "gross_target": self.gross_target,
            "long_short": self.long_short,
            "expected_return_col": self.expected_return_col,
            "covariance_window": self.covariance_window,
            "covariance_rebalance_step": self.covariance_rebalance_step,
            "risk_aversion": self.risk_aversion,
            "trade_aversion": self.trade_aversion,
            "constraints": dict(self.constraints),
            "asset_groups": dict(self.asset_groups),
        }
        return payload | dict(self.extra)


@dataclass(frozen=True)
class MonitoringConfig:
    enabled: bool
    psi_threshold: float
    n_bins: int
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MonitoringConfig":
        known = {"enabled", "psi_threshold", "n_bins"}
        return cls(
            enabled=bool(data.get("enabled", True)),
            psi_threshold=float(data.get("psi_threshold", 0.2)),
            n_bins=int(data.get("n_bins", 10)),
            extra=_extras(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "psi_threshold": self.psi_threshold,
            "n_bins": self.n_bins,
        } | dict(self.extra)


@dataclass(frozen=True)
class ExecutionConfig:
    enabled: bool
    mode: str
    capital: float
    price_col: str
    min_trade_notional: float
    current_weights: dict[str, Any] = field(default_factory=dict)
    current_prices: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionConfig":
        known = {
            "enabled",
            "mode",
            "capital",
            "price_col",
            "min_trade_notional",
            "current_weights",
            "current_prices",
        }
        return cls(
            enabled=bool(data.get("enabled", False)),
            mode=str(data.get("mode", "paper")),
            capital=float(data.get("capital", 1_000_000.0)),
            price_col=str(data.get("price_col", "close")),
            min_trade_notional=float(data.get("min_trade_notional", 0.0)),
            current_weights=dict(data.get("current_weights", {}) or {}),
            current_prices=dict(data.get("current_prices", {}) or {}),
            extra=_extras(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "enabled": self.enabled,
            "mode": self.mode,
            "capital": self.capital,
            "price_col": self.price_col,
            "min_trade_notional": self.min_trade_notional,
            "current_weights": dict(self.current_weights),
            "current_prices": dict(self.current_prices),
        }
        return payload | dict(self.extra)


@dataclass(frozen=True)
class LoggingConfig:
    enabled: bool
    run_name: str
    output_dir: str
    stage_tails: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoggingConfig":
        known = {"enabled", "run_name", "output_dir", "stage_tails"}
        return cls(
            enabled=bool(data.get("enabled", True)),
            run_name=str(data.get("run_name", "experiment")),
            output_dir=str(data.get("output_dir", "logs/experiments")),
            stage_tails=dict(data.get("stage_tails", {}) or {}),
            extra=_extras(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "run_name": self.run_name,
            "output_dir": self.output_dir,
            "stage_tails": dict(self.stage_tails),
        } | dict(self.extra)


@dataclass(frozen=True)
class ResolvedExperimentConfig:
    config_path: str
    data: DataConfig
    features: list[FeatureStep]
    model: ModelConfig
    signals: SignalsConfig
    runtime: dict[str, Any]
    risk: RiskConfig
    backtest: BacktestConfig
    portfolio: PortfolioConfig
    monitoring: MonitoringConfig
    execution: ExecutionConfig
    logging: LoggingConfig
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResolvedExperimentConfig":
        known = {
            "config_path",
            "data",
            "features",
            "model",
            "signals",
            "runtime",
            "risk",
            "backtest",
            "portfolio",
            "monitoring",
            "execution",
            "logging",
        }
        return cls(
            config_path=str(data["config_path"]),
            data=DataConfig.from_dict(dict(data.get("data", {}) or {})),
            features=[FeatureStep.from_dict(dict(step)) for step in list(data.get("features", []) or [])],
            model=ModelConfig.from_dict(dict(data.get("model", {}) or {})),
            signals=SignalsConfig.from_dict(dict(data.get("signals", {}) or {})),
            runtime=dict(data.get("runtime", {}) or {}),
            risk=RiskConfig.from_dict(dict(data.get("risk", {}) or {})),
            backtest=BacktestConfig.from_dict(dict(data.get("backtest", {}) or {})),
            portfolio=PortfolioConfig.from_dict(dict(data.get("portfolio", {}) or {})),
            monitoring=MonitoringConfig.from_dict(dict(data.get("monitoring", {}) or {})),
            execution=ExecutionConfig.from_dict(dict(data.get("execution", {}) or {})),
            logging=LoggingConfig.from_dict(dict(data.get("logging", {}) or {})),
            extra=_extras(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "config_path": self.config_path,
            "data": self.data.to_dict(),
            "features": [step.to_dict() for step in self.features],
            "model": self.model.to_dict(),
            "signals": self.signals.to_dict(),
            "runtime": dict(self.runtime),
            "risk": self.risk.to_dict(),
            "backtest": self.backtest.to_dict(),
            "portfolio": self.portfolio.to_dict(),
            "monitoring": self.monitoring.to_dict(),
            "execution": self.execution.to_dict(),
            "logging": self.logging.to_dict(),
        }
        return payload | dict(self.extra)


__all__ = [
    "BacktestConfig",
    "DataConfig",
    "ExecutionConfig",
    "FeatureStep",
    "LoggingConfig",
    "ModelConfig",
    "MonitoringConfig",
    "PortfolioConfig",
    "ResolvedExperimentConfig",
    "RiskConfig",
    "SignalsConfig",
]
