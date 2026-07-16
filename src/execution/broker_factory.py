from __future__ import annotations

from typing import Any, Mapping

from src.execution.broker_base import BrokerBase
from src.execution.dry_run_execution import DryRunExecution
from src.execution.mt5_execution import MT5Execution
from src.execution.oanda_execution import OandaExecution


def create_execution_engine(config: Mapping[str, Any]) -> BrokerBase:
    """Create a broker execution engine from a config mapping.

    Args:
        config: Full config or the nested ``execution`` config.

    Returns:
        A concrete BrokerBase implementation.
    """

    execution_cfg = dict(config.get("execution", config) or {})
    broker = str(execution_cfg.get("broker") or execution_cfg.get("mode") or "mt5").lower()
    if broker == "dry_run" or str(execution_cfg.get("mode", "")).lower() == "dry_run":
        return DryRunExecution(execution_cfg)
    if broker in {"oanda", "oanda_v20"}:
        return OandaExecution(dict(execution_cfg.get("oanda", {}) or {}))
    if broker in {"mt5", "demo_mt5", "metatrader5"}:
        return MT5Execution(execution_cfg)
    raise ValueError(f"Unsupported execution broker: {broker!r}.")


__all__ = ["create_execution_engine"]
