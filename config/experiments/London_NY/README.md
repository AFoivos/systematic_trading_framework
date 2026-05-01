# London_NY v3 Research Structure

Αυτός ο φάκελος είναι το clean v3 research surface για 30m XAU/indices session strategies με strict PIT assumptions και FTMO-style portfolio guards.

## Τι είναι runnable τώρα

Η τρέχουσα runnable candidate family είναι η `opening_range_breakout`.

Υπάρχουν τρία layers πειραμάτων:

- `raw/`: diagnostic baseline χωρίς meta model. Το signal είναι καθαρό `orb_candidate_side`.
- `tree_only/`: per asset/session meta classifiers με switchable `xgboost_clf` / `lightgbm_clf`.
- `stack/`: basket-level staged stack `tree_meta_base -> tft_regime_overlay -> ensemble_decision`.

## Τι ΔΕΝ προσποιούμαστε ότι υπάρχει

Τα παρακάτω modules είναι planned next phase και δεν έχουν μπει ακόμη ως feature steps / signal modules:

- opening range continuation
- session momentum
- volatility expansion
- failed breakout / reversal diagnostic module

Το README τα κρατάει ως explicit roadmap. Δεν υπάρχουν fake configs που να δείχνουν runnable ενώ δεν είναι.

## Universe configs

### raw

- `raw/xauusd_london_orb_breakout_raw_v3.yaml`
- `raw/ger40_london_orb_breakout_raw_v3.yaml`
- `raw/spx500_ny_cash_orb_breakout_raw_v3.yaml`
- `raw/us100_ny_cash_orb_breakout_raw_v3.yaml`
- `raw/london_basket_orb_breakout_raw_v3.yaml`
- `raw/ny_cash_basket_no_us30_orb_breakout_raw_v3.yaml`

### tree_only

- `tree_only/xauusd_london_tree_meta_v3.yaml`
- `tree_only/ger40_london_tree_meta_v3.yaml`
- `tree_only/spx500_ny_cash_tree_meta_v3.yaml`
- `tree_only/us100_ny_cash_tree_meta_v3.yaml`
- `tree_only/london_basket_tree_meta_v3.yaml`
- `tree_only/ny_cash_basket_no_us30_tree_meta_v3.yaml`

### stack

- `stack/london_basket_tree_tft_overlay_v3.yaml`
- `stack/ny_cash_basket_no_us30_tree_tft_overlay_v3.yaml`

## Current design choices

- Base timeframe: `30m`
- Timestamp convention: `bar_start`
- Higher timeframe features: `1h`, `4h`
- ORB setup for higher candidate flow:
  - `opening_range_bars: 1`
  - `min_range_atr: 0.3`
  - `max_range_atr: 3.0`
  - `breakout_buffer_atr: 0.05`
  - `post_breakout_active_bars: 2`
  - `max_breakouts_per_session: 2`
- Default meta target in v3 configs:
  - `upper_mult: 1.5`
  - `lower_mult: 1.0`
  - `max_holding: 6`
- Risk baseline:
  - `risk_per_trade: 0.25%`
  - confidence scaling enabled on model-based configs
  - `max_gross_leverage: 1.0`
  - `max_weight: 0.35`
  - FTMO daily / weekly / total guards intact

## Tree-only model catalog

Τα `tree_only/` configs χρησιμοποιούν `models:` catalog ώστε να αλλάζει καθαρά το active meta classifier.

Τρέχον catalog:

- `xgboost_clf` -> enabled by default
- `lightgbm_clf` -> disabled by default

`catboost` δεν προστέθηκε εδώ γιατί δεν υπάρχει ακόμη registered model kind στο framework. Αυτό είναι intentional και όχι παράλειψη.

## Stack model

Τα `stack/` configs χρησιμοποιούν staged model pipeline:

1. `tree_meta_base`
2. `tft_regime_overlay`
3. `ensemble_decision`

Σημαντικό:

- Το TFT εδώ είναι regime / quality overlay.
- Δεν είναι direct execution model.
- Το τελικό trade approval εξακολουθεί να είναι same-side meta decision.
- Δεν γίνεται side flipping σε breakout candidates.

## Suggested run order before Optuna

1. Τρέξε `raw/` baselines.
2. Τρέξε `tree_only/` per asset/session configs.
3. Τρέξε `stack/` basket overlays.
4. Σύγκρινε:
   - raw vs tree_only
   - tree_only vs stack
   - cost drag
   - turnover
   - FTMO breaches
   - weekly target hit ratio

## Example commands

```bash
docker compose exec app python -m src.experiments.runner experiments/London_NY/raw/xauusd_london_orb_breakout_raw_v3.yaml
docker compose exec app python -m src.experiments.runner experiments/London_NY/tree_only/xauusd_london_tree_meta_v3.yaml
docker compose exec app python -m src.experiments.runner experiments/London_NY/stack/london_basket_tree_tft_overlay_v3.yaml
```

## Next implementation phase

Αν το v3 ORB family δείξει καθαρό edge, η επόμενη phase πρέπει να είναι νέα feature modules και όχι άμεσο Optuna πάνω σε μισο-υλοποιημένες ιδέες:

1. `opening_range_continuation`
2. `session_momentum`
3. `volatility_expansion`
4. `failed_breakout_reversal`
5. explicit ensemble scoring report diagnostics

