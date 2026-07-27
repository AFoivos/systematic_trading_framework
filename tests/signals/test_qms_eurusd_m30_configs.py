from __future__ import annotations

from pathlib import Path

from src.signals.qms_alpha_strategy import QMS_ALPHA_STRATEGIES
from src.utils.config import load_experiment_config


CONFIG_DIR = Path("config/experiments/qms_eurusd_m30")


def test_five_eurusd_m30_alpha_configs_are_self_contained_and_consistent() -> None:
    paths = sorted(CONFIG_DIR.glob("*.yaml"))
    assert len(paths) == 5

    configs = [load_experiment_config(path) for path in paths]
    assert {cfg["signals"]["params"]["strategy"] for cfg in configs} == set(
        QMS_ALPHA_STRATEGIES
    )

    for cfg in configs:
        feature = next(
            step for step in cfg["features"] if step["step"] == "quant_market_state"
        )
        storage_path = Path(cfg["data"]["storage"]["load_path"])

        assert cfg["strategy"]["symbol"] == "EURUSD"
        assert cfg["strategy"]["timeframe"] == "M30"
        assert cfg["data"]["interval"] == "30m"
        assert storage_path == Path(
            "data/raw/dukascopy_30m_clean/eurusd_30m.csv"
        ).resolve()
        assert storage_path.is_file()
        assert feature["params"]["bar_minutes"] == 30.0
        assert cfg["signals"]["kind"] == "qms_alpha_strategy"
        assert cfg["signals"]["params"]["lookback_bars"] == 4032
        assert cfg["signals"]["params"]["min_periods"] == 1008
        assert cfg["target"]["entry_price_mode"] == "next_open"
        assert cfg["target"]["max_holding"] == cfg["backtest"]["max_holding_bars"]
        assert cfg["target"]["upper_mult"] == cfg["backtest"]["take_profit_r"]
        assert cfg["target"]["lower_mult"] == cfg["backtest"]["stop_loss_r"]
        assert cfg["backtest"]["periods_per_year"] == 12_096
        assert cfg["validation"]["purge_bars"] >= cfg["target"]["max_holding"]
