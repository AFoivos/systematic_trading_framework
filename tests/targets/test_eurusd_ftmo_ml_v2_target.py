from __future__ import annotations

import numpy as np

from src.targets.eurusd_ftmo_candidate_meta import executable_trade_return


def test_long_target_uses_ask_entry_bid_exit_and_one_round_turn_extra_cost() -> None:
    result = executable_trade_return(
        direction=1,
        entry_bid=1.1000,
        entry_ask=1.1002,
        exit_bid=1.1010,
        exit_ask=1.1012,
    )
    expected_gross = (1.1010 - 1.1002) / 1.1002
    expected_extra = 0.00006 / 1.1002
    assert np.isclose(result["gross_return"], expected_gross)
    assert np.isclose(result["net_return"], expected_gross - expected_extra)
    assert result["target_positive_net"] == 1


def test_short_target_uses_bid_entry_ask_exit() -> None:
    result = executable_trade_return(
        direction=-1,
        entry_bid=1.1000,
        entry_ask=1.1002,
        exit_bid=1.0990,
        exit_ask=1.0992,
    )
    expected_gross = (1.1000 - 1.0992) / 1.1000
    assert np.isclose(result["gross_return"], expected_gross)
    assert result["target_positive_net"] == 1


def test_spread_is_not_deducted_twice() -> None:
    result = executable_trade_return(
        direction=1,
        entry_bid=1.1000,
        entry_ask=1.1002,
        exit_bid=1.1000,
        exit_ask=1.1002,
    )
    assert np.isclose(result["gross_return"], -0.0002 / 1.1002)
    assert result["target_positive_net"] == 0
