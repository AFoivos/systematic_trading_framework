from .broker_base import BrokerBase
from .broker_factory import create_execution_engine
from .exceptions import (
    AuthenticationError,
    BrokerError,
    ConnectionLost,
    OrderRejected,
    RateLimitExceeded,
    SymbolNotFound,
)
from .models import (
    AccountSnapshot,
    Order,
    OrderResult as BrokerOrderResult,
    Position,
    PriceTick,
    SymbolInfo,
)
from .mt5_connector import (
    MT5Connector,
    MT5ConnectorError,
    MT5CredentialsError,
    MT5DemoAccountError,
    MT5ImportError,
    MT5LoginError,
)
from .mt5_execution import MT5Execution
from .mt5_order_manager import MT5OrderManager, OrderResult, TradeParameters
from .mt5_position_manager import MT5PositionManager, PositionSnapshot
from .mt5_risk_manager import MT5RiskManager, RiskConfig, RiskDecision, calculate_position_size
from .mt5_symbol_mapper import MT5SymbolMapper, SymbolMapping
from .oanda_execution import OandaConfig, OandaExecution
from .paper import build_rebalance_orders

BrokerOrderRejected = OrderRejected

__all__ = [
    "AccountSnapshot",
    "AuthenticationError",
    "BrokerBase",
    "BrokerError",
    "BrokerOrderRejected",
    "BrokerOrderResult",
    "ConnectionLost",
    "MT5Connector",
    "MT5ConnectorError",
    "MT5CredentialsError",
    "MT5DemoAccountError",
    "MT5ImportError",
    "MT5Execution",
    "MT5LoginError",
    "MT5OrderManager",
    "MT5PositionManager",
    "MT5RiskManager",
    "MT5SymbolMapper",
    "OandaConfig",
    "OandaExecution",
    "Order",
    "OrderRejected",
    "OrderResult",
    "PositionSnapshot",
    "Position",
    "PriceTick",
    "RateLimitExceeded",
    "RiskConfig",
    "RiskDecision",
    "SymbolInfo",
    "SymbolMapping",
    "SymbolNotFound",
    "TradeParameters",
    "build_rebalance_orders",
    "calculate_position_size",
    "create_execution_engine",
]
