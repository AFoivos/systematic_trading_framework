from __future__ import annotations

from fastapi import APIRouter

from app.api._errors import raise_http_error
from app.schemas.experiment import TradeRecord
from app.schemas.market import TimeValuePoint
from app.services.backtest_loader import BacktestLoader


router = APIRouter()


@router.get("/backtests/{run_id}/trades", response_model=list[TradeRecord])
def get_trades(run_id: str, asset: str | None = None) -> list[dict]:
    try:
        return BacktestLoader().load_trades(run_id, asset=asset)
    except Exception as exc:
        raise_http_error(exc)
        return []


@router.get("/backtests/{run_id}/equity", response_model=list[TimeValuePoint])
def get_equity(run_id: str) -> list[dict]:
    try:
        return BacktestLoader().load_equity(run_id)
    except Exception as exc:
        raise_http_error(exc)
        return []
