from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def sharpe(x: pd.Series, periods_per_year: int = 17_520) -> float:
    x = pd.to_numeric(x, errors="coerce").dropna()
    if x.empty or float(x.std(ddof=1)) <= 0:
        return 0.0
    return float(x.mean() / x.std(ddof=1) * np.sqrt(periods_per_year))


def max_drawdown(x: pd.Series) -> float:
    equity = (1.0 + x.fillna(0.0)).cumprod()
    return float((equity / equity.cummax() - 1.0).min())


def cumulative_return(x: pd.Series) -> float:
    return float((1.0 + x.fillna(0.0)).prod() - 1.0)


def extract_trade_blocks(position: np.ndarray) -> list[tuple[int, float]]:
    blocks: list[tuple[int, float]] = []
    i = 0
    n = len(position)
    while i < n:
        if position[i] == 0 or not np.isfinite(position[i]):
            i += 1
            continue
        sign = float(np.sign(position[i]))
        j = i + 1
        while j < n and np.sign(position[j]) == sign and position[j] != 0:
            j += 1
        blocks.append((j - i, sign))
        i = j
    return blocks


def random_block_signal(
    n: int,
    blocks: list[tuple[int, float]],
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Randomize trade-block placement while preserving each block's
    duration and direction.

    Blocks are separated by randomly allocated flat gaps. This avoids
    repeatedly convolving across the complete timeline.
    """
    signal = np.zeros(n, dtype=float)

    if not blocks:
        return signal

    shuffled_indices = rng.permutation(len(blocks))
    shuffled_blocks = [
        (int(blocks[i][0]), float(blocks[i][1]))
        for i in shuffled_indices
    ]

    total_exposure = sum(length for length, _ in shuffled_blocks)
    if total_exposure >= n:
        shuffled_blocks = [
            (length, sign)
            for length, sign in shuffled_blocks
            if length < n
        ]
        total_exposure = sum(length for length, _ in shuffled_blocks)

    if not shuffled_blocks or total_exposure >= n:
        return signal

    flat_bars = n - total_exposure
    gap_count = len(shuffled_blocks) + 1

    # Random composition of all flat bars into before/between/after gaps.
    gap_weights = rng.dirichlet(np.ones(gap_count))
    gaps = np.floor(gap_weights * flat_bars).astype(int)

    # Assign rounding remainder randomly.
    remainder = flat_bars - int(gaps.sum())
    if remainder > 0:
        selected = rng.choice(gap_count, size=remainder, replace=True)
        np.add.at(gaps, selected, 1)

    cursor = int(gaps[0])

    for block_index, (length, sign) in enumerate(shuffled_blocks):
        end = min(cursor + length, n)
        signal[cursor:end] = sign
        cursor = end + int(gaps[block_index + 1])

        if cursor >= n:
            break

    return signal

def random_sign_distribution(
    close_ret: pd.Series,
    position: pd.Series,
    *,
    cost_per_turnover: float,
    draws: int,
    seed: int,
) -> pd.DataFrame:
    r = close_ret.fillna(0.0).to_numpy(dtype=float)
    p = position.fillna(0.0).to_numpy(dtype=float)
    blocks = extract_trade_blocks(p)
    rng = np.random.default_rng(seed)
    rows = []

    for draw in range(draws):
        sig = random_block_signal(len(p), blocks, rng)
        turnover = np.abs(np.diff(np.r_[0.0, sig]))
        net = np.roll(sig, 1) * r - turnover * cost_per_turnover
        net[0] = -turnover[0] * cost_per_turnover
        s = pd.Series(net)
        rows.append(
            {
                "draw": draw,
                "cumulative_return": cumulative_return(s),
                "sharpe": sharpe(s),
                "max_drawdown": max_drawdown(s),
            }
        )
    return pd.DataFrame(rows)


def moving_block_bootstrap(
    strategy_returns: pd.Series,
    *,
    block_bars: int,
    draws: int,
    seed: int,
) -> pd.DataFrame:
    values = strategy_returns.fillna(0.0).to_numpy(dtype=float)
    n = len(values)
    if n == 0:
        return pd.DataFrame()
    rng = np.random.default_rng(seed)
    starts = np.arange(max(1, n - block_bars + 1))
    rows = []

    for draw in range(draws):
        sample: list[float] = []
        while len(sample) < n:
            start = int(rng.choice(starts))
            sample.extend(values[start : start + block_bars].tolist())
        s = pd.Series(sample[:n])
        rows.append(
            {
                "draw": draw,
                "cumulative_return": cumulative_return(s),
                "sharpe": sharpe(s),
                "max_drawdown": max_drawdown(s),
            }
        )
    return pd.DataFrame(rows)


def read_series(path: Path, preferred: str | None = None) -> pd.Series:
    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")
    if preferred and preferred in df.columns:
        return pd.to_numeric(df[preferred], errors="coerce")
    numeric = [c for c in df.columns if c != "timestamp"]
    if not numeric:
        raise ValueError(f"No value column in {path}")
    return pd.to_numeric(df[numeric[0]], errors="coerce")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs-dir", default="logs/experiments")
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--raw-data", default="data/raw/dukascopy_30m_clean/ethusd_30m.csv")
    ap.add_argument("--random-draws", type=int, default=1000)
    ap.add_argument("--bootstrap-draws", type=int, default=5000)
    ap.add_argument("--block-bars", type=int, default=96)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    logs = Path(args.logs_dir)
    runs = sorted(
        [p for p in logs.iterdir() if p.is_dir() and p.name.startswith(args.prefix)]
    )
    if not runs:
        raise SystemExit(f"No runs found for prefix {args.prefix}")

    raw = pd.read_csv(args.raw_data, usecols=["timestamp", "close"])
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True)
    raw = raw.set_index("timestamp").sort_index()
    close_ret = raw["close"].pct_change()

    summary_rows = []
    for run in runs:
        pos = read_series(run / "positions.csv", "signal_structured_tail")
        strat = read_series(run / "returns.csv")
        aligned_ret = close_ret.reindex(pos.index).fillna(0.0)

        random_df = random_sign_distribution(
            aligned_ret,
            pos,
            cost_per_turnover=0.0001,
            draws=args.random_draws,
            seed=args.seed,
        )
        boot_df = moving_block_bootstrap(
            strat,
            block_bars=args.block_bars,
            draws=args.bootstrap_draws,
            seed=args.seed,
        )

        observed_return = cumulative_return(strat)
        observed_sharpe = sharpe(strat)
        observed_dd = max_drawdown(strat)

        result_dir = run / "artifacts" / "random_bootstrap"
        result_dir.mkdir(parents=True, exist_ok=True)
        random_df.to_csv(result_dir / "random_block_sign_baselines.csv", index=False)
        boot_df.to_csv(result_dir / "moving_block_bootstrap.csv", index=False)

        row = {
            "run": run.name,
            "observed_cumulative_return": observed_return,
            "observed_sharpe": observed_sharpe,
            "observed_max_drawdown": observed_dd,
            "random_return_percentile": float(
                (random_df["cumulative_return"] < observed_return).mean()
            ),
            "random_sharpe_percentile": float(
                (random_df["sharpe"] < observed_sharpe).mean()
            ),
            "bootstrap_prob_return_positive": float(
                (boot_df["cumulative_return"] > 0).mean()
            ),
            "bootstrap_prob_sharpe_positive": float(
                (boot_df["sharpe"] > 0).mean()
            ),
            "bootstrap_return_ci_025": float(
                boot_df["cumulative_return"].quantile(0.025)
            ),
            "bootstrap_return_ci_975": float(
                boot_df["cumulative_return"].quantile(0.975)
            ),
        }
        (result_dir / "summary.json").write_text(
            json.dumps(row, indent=2),
            encoding="utf-8",
        )
        summary_rows.append(row)

    leaderboard = pd.DataFrame(summary_rows).sort_values(
        ["bootstrap_prob_return_positive", "random_sharpe_percentile"],
        ascending=False,
    )
    output = logs / f"{args.prefix}_random_bootstrap_leaderboard.csv"
    leaderboard.to_csv(output, index=False)
    print(leaderboard.to_string(index=False))
    print({"leaderboard": str(output)})


if __name__ == "__main__":
    main()
