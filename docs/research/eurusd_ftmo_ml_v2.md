# EURUSD FTMO 2-Step ML Meta-Ensemble v2

This package is a documented reconstruction of the fixed candidate-trade strategy. It implements research/training, annual strict-OOS evaluation, a versioned final model bundle, and paper/forward inference. It intentionally contains no broker or cTrader execution.

Run the registered pipeline with:

```powershell
python -m src.experiments.runner config/experiments/eurusd_ftmo_ml_v2/eurusd_ftmo_ml_v2_reconstruction.yaml
```

The run first verifies and copies authoritative files from `/mnt/data` into `artifacts/reference/eurusd_ftmo_ml_v2`. Missing files and hash mismatches fail closed and are written to `reference_manifest.json` and `parity_report.md`; they are never replaced with synthetic artifacts.

The implementation composes the existing feature/helper registries for returns, ATR, trend, RSI, ADX, volatility, range position, rolling z-scores, ATR-scaled distances, generic transforms, path efficiency, autocorrelation, and completed-trade history. The model matrix is checked against the exact 151-column contract before every fit or inference.

Paper/forward code should build the same candidate feature matrix and call `forward_inference` from `src.models.classification.eurusd_ftmo_meta_ensemble` with the versioned final bundle. That function validates the feature order and never refits.
