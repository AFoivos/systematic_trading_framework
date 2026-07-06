# Market Making Moment Research

> Ελληνική τεκμηρίωση strategy family. Το αρχείο είναι source-backed από τα YAML configs και τα διαθέσιμα logged artifacts στο repo. Δεν αποτελεί επενδυτική σύσταση και δεν υποκαθιστά ανεξάρτητο leakage/reproducibility review πριν από production χρήση.

## Σύνοψη

Research-only market-making pipeline με order-book replay, MOMENT features και toxicity/markout diagnostics.

- Πλήθος checked-in configs που χαρτογραφήθηκαν: **4**.
- Πλήθος logged runs που χαρτογραφήθηκαν: **6**.
- Κύρια model kinds: `none/unspecified` (4).
- Κύρια signal kinds: `none/unspecified` (4).

## Φιλοσοφία

Η market-making οικογένεια είναι ξεχωριστή από directional experiments. Δεν προσπαθεί να προβλέψει directional alpha σε OHLCV bars· αξιολογεί αν quote placement και fill quality μπορούν να βελτιωθούν με order-book context και pretrained time-series representations.

Το βασικό ερώτημα είναι fee-adjusted markout: οι fills είναι πραγματικά κερδοφόρες μετά από fees/adverse selection ή απλώς φαίνονται καλές επειδή αγνοούμε toxic flow; Το MOMENT layer είναι feature extractor/quality model, όχι live execution engine.

Τα configs είναι research-only και δεν πρέπει να συνδέονται με demo/live order placement. Τα outputs παραμένουν JSON/CSV/Markdown/Parquet για auditability.

## Αρχιτεκτονική

- Input layer: order-book events ή collected top-of-book/orderbook CSV.
- Replay layer: paper market-making engine που παράγει quotes/fills/cancels και markout summaries.
- Dataset layer: μετατροπή replay/orderbook σε MOMENT-ready supervised dataset.
- Model layer: lightweight head πάνω σε MOMENT/pretrained representation για toxic-fill ή markout quality.
- Evaluation: realized/unrealized PnL, fees, fill ratio, markout, baseline-vs-moment και risk summaries.

## Causality, leakage και reproducibility guardrails

- Τα features πρέπει να υπολογίζονται μόνο από διαθέσιμες τιμές στο timestamp απόφασης. Rolling windows, lags και session aggregates δεν πρέπει να κοιτούν future bars.
- Τα model splits πρέπει να παραμένουν walk-forward/purged όπου ορίζεται, με OOS predictions να παράγονται μόνο για test rows.
- Τα labels, barrier outcomes και forward returns είναι training/evaluation targets. Δεν πρέπει να χρησιμοποιούνται στο signal layer εκτός OOS prediction output.
- Τα logged metrics πρέπει να διαβάζονται μαζί με costs, turnover, drawdown και fold dispersion. Υψηλό cumulative return με ασταθή folds ή τεράστιο cost drag δεν είναι robust edge.
- Τα links σε `logs/` είναι artifacts του τρέχοντος workspace. Αν λείπουν σε άλλο clone, το config παραμένει η canonical προδιαγραφή και το run πρέπει να αναπαραχθεί.

## Inventory configs

| Config | Strategy | TF | Assets | Model | Target | Signal | Backtest | Features |
|---|---|---:|---|---|---|---|---|---:|
| [market_making_large_moment_collect_2m_pipeline.yaml](../../config/experiments/market_making/market_making_large_moment_collect_2m_pipeline.yaml) | `market_making_large_moment_collect_2m_pipeline` |  |  | `none` | `` | `` | `` | 0 |
| [market_making_large_moment_pipeline.yaml](../../config/experiments/market_making/market_making_large_moment_pipeline.yaml) | `market_making_large_moment_pipeline` |  |  | `none` | `` | `` | `` | 0 |
| [market_making_moment.yaml](../../config/experiments/market_making/market_making_moment.yaml) | `market_making_moment` |  |  | `none` | `` | `` | `` | 0 |
| [market_making_moment_collect_100k_pipeline.yaml](../../config/experiments/market_making/market_making_moment_collect_100k_pipeline.yaml) | `market_making_moment_collect_100k_pipeline` |  |  | `none` | `` | `` | `` | 0 |

## Best διαθέσιμο run

Το καλύτερο διαθέσιμο run επιλέχθηκε μηχανικά με προτεραιότητα στο Sharpe όπου υπάρχει, και μετά στο cumulative return/PnL. Αυτό δεν σημαίνει ότι είναι το πιο production-ready run· σημαίνει ότι είναι το ισχυρότερο logged αποτέλεσμα με το διαθέσιμο scoring rule.

- Run: [market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1)
- Config path από metadata: `config/experiments/market_making/market_making_moment_collect_100k_pipeline.yaml`
- Canonicality: **checked-in strategy config** στο `config/experiments/`.
- Strategy name: `market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1`
- Model / Signal: `none` / `none`
- Assets: n/a

| Metric | Τιμή |
|---|---:|
| Cumulative return / total PnL | -0.0215 |
| Annualized return | n/a |
| Sharpe | -0.0368 |
| Sortino | -0.0161 |
| Max drawdown | -214.6739 |
| Profit factor | 0.0000 |
| Hit rate | 0.0000 |
| Total cost / fees | 200,000.00 |
| Total turnover | 136.0000 |

Κύριο report: [report.md](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/report.md)

### Πλήρες artifact inventory του best run

| Artifact | Ρόλος |
|---|---|
| [report.md](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/report.md) | Κύριο Markdown report του runner. |
| [summary.json](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/summary.json) | Μηχανικά αναγνώσιμη σύνοψη metrics. |
| [run_metadata.json](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/run_metadata.json) | Metadata αναπαραγωγής, path config και runtime info. |
| [config_used.yaml](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/config_used.yaml) | Το ακριβές resolved config που χρησιμοποιήθηκε στο run. |
| [returns.csv](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [gross_returns.csv](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/gross_returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [equity_curve.csv](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/equity_curve.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [positions.csv](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/positions.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [costs.csv](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/costs.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [turnover.csv](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/turnover.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifact_manifest.json](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/artifact_manifest.json) | JSON diagnostic/metadata artifact. |

## Όλα τα logged runs αυτής της οικογένειας

| Run | Strategy | Sharpe | CumRet/PnL | MaxDD | PF | Cost | Report |
|---|---|---:|---:|---:|---:|---:|---|
| [market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1) | `market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1` | -0.0368 | -0.0215 | -214.6739 | 0.0000 | 200,000.00 | [report.md](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215905_b92261e1/report.md) |
| [market_making_moment_collect_100k_timestamp_regression_20260703_215944_b92261e1](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215944_b92261e1) | `market_making_moment_collect_100k_timestamp_regression_20260703_215944_b92261e1` | -0.0368 | -0.0215 | -214.6739 | 0.0000 | 200,000.00 | [report.md](../../logs/experiments/market_making/market_making_moment_collect_100k_timestamp_regression_20260703_215944_b92261e1/report.md) |
| [moment_collect_100k_replay](../../logs/experiments/market_making/runs/moment_collect_100k_replay) | `moment_collect_100k_replay` | n/a | -0.2557 | 0.4179 | n/a | 0.1736 |  |
| [20260703_224328_kraken_orderbook_csv_top_of_book_crossing](../../logs/experiments/market_making/runs/20260703_224328_kraken_orderbook_csv_top_of_book_crossing) | `20260703_224328_kraken_orderbook_csv_top_of_book_crossing` | n/a | -0.3398 | 0.3858 | n/a | 0.0876 |  |
| [diagnostics](../../logs/experiments/market_making/runs/20260703_224328_kraken_orderbook_csv_top_of_book_crossing/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a | [report.md](../../logs/experiments/market_making/runs/20260703_224328_kraken_orderbook_csv_top_of_book_crossing/diagnostics/report.md) |
| [diagnostics](../../logs/experiments/market_making/runs/moment_collect_100k_replay/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a | [report.md](../../logs/experiments/market_making/runs/moment_collect_100k_replay/diagnostics/report.md) |

## Πώς να αναπαραχθεί

Ενδεικτικά, κάθε config μπορεί να τρέξει με τον official runner:

```bash
docker compose run --rm app python -m src.experiments.runner experiments/market_making/market_making_large_moment_collect_2m_pipeline.yaml
```

Για serious comparison, κράτα σταθερά data snapshot, costs, split semantics, random seeds και config diff. Μην συγκρίνεις run που αλλάζει ταυτόχρονα target, features, model, signal threshold και backtest constraints χωρίς ablation table.
