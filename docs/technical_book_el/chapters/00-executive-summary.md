## Εκτελεστική Σύνοψη

Το repository αποτελεί ένα ερευνητικό αλλά σαφώς production-oriented framework για systematic trading, με
δηλωτική παραμετροποίηση πειραμάτων, anti-leakage time-series evaluation, point-in-time hardening,
signal-to-portfolio mapping, portfolio constraints, drift diagnostics και paper execution artifacts.
Η παρούσα τεκμηρίωση βασίζεται στην πραγματική κατάσταση του κώδικα την 2 Μαρτίου 2026, σε ανάγνωση όλου
του repository, καθώς και σε εκτέλεση του test suite (`51 passed, 2 warnings`). Το framework σήμερα
υλοποιεί πλήρως data ingestion, feature engineering, classification-based signal generation, single-asset και
multi-asset portfolio backtesting, reproducibility metadata και artifact persistence. Αντίθετα, deep
learning, reinforcement learning και live broker execution αναφέρονται στο README ως roadmap και όχι ως
ενεργές υλοποιήσεις στον παρόντα κώδικα.

Βασικά μετρήσιμα μεγέθη του codebase:

- `63` Python modules (source + tests).
- `268` callable definitions (top-level functions, test callables και class methods).
- `13` classes/dataclasses/interfaces.
- `5` YAML configuration files.
- `7` primary test modules με συνολικά 51 passing tests.

Αρχιτεκτονικά, το σύστημα ακολουθεί layered modular design με σαφή ροή: `config -> data -> PIT ->
features -> model -> signal -> backtest/portfolio -> evaluation -> monitoring -> execution -> artifacts`.
Η πιο ισχυρή ιδιαιτερότητα του repository είναι ότι τα anti-leakage safeguards δεν είναι απλώς θεωρητικές
συστάσεις: κωδικοποιούνται ρητά σε contracts, purged/embargoed splits, horizon trimming, lagged PnL
accounting και regression tests.
