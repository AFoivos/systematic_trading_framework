# VectorBT Research Backend — Phase 3A

Κατάσταση: **implemented — screening only**

Η Phase 3A ενσωματώνει το `vectorbt==0.28.5` ως optional, replaceable backend
για γρήγορο screening μεγάλων αλλά πεπερασμένων rule-based parameter grids.
Δεν αλλάζει τον canonical backtester και δεν προσθέτει νέο δρόμο προς
promotion ή execution.

Οι δύο κρίσιμες ισότητες είναι:

```text
VectorBT result ≠ canonical validation
VectorBT screening Sharpe ≠ validated alpha Sharpe
```

## Dependency και συμβατότητα

Το optional manifest είναι το `requirements.vectorbt.txt`. Η έκδοση 0.28.5
επιλέχθηκε επειδή υποστηρίζει Python 3.11, NumPy 1.26 και pandas 2.2. Η νεότερη
γραμμή 1.x απαιτεί νεότερο NumPy/pandas stack και επομένως δεν είναι συμβατή με
το frozen framework environment χωρίς broad dependency migration.

Για περιβάλλον εκτός του project image:

```bash
python -m pip install -r requirements.vectorbt.txt
```

Το `src.research` και οι neutral discovery contracts δεν εισάγουν το VectorBT.
Η πραγματική φόρτωση γίνεται μόνο όταν επιλεγεί `VectorBTSearchExecutor`. Αν η
εξάρτηση λείπει, ο adapter αποτυγχάνει με σαφές optional-dependency error και
δεν κάνει fallback σε grid, Optuna ή canonical backtesting.

## Architecture boundary

```text
framework features / signals
            │
            ▼
VectorBTSignalSet (portable pandas inputs)
            │
            ▼
src/research/backends/vectorbt/
  contracts.py
  adapter.py ──lazy──> VectorBT Portfolio.from_signals
  optional_dependency.py
            │
            ▼
DiscoveryTrial[] (JSON-compatible)
            │
            ▼
eligibility → ranking → selection
            │
            ▼
PENDING_CANONICAL_VALIDATION
```

VectorBT-native `Portfolio`, order records, trade records και arrays δεν
περνούν στα framework contracts. Ο adapter διαβάζει τα native order records
μόνο εσωτερικά για να ελέγξει ότι timestamps, sides και gross fill prices
συμφωνούν με το δηλωμένο timing contract.

## Πραγματικές capabilities

Ο adapter δηλώνει μόνο:

- `vectorized_screening`,
- `parameter_grid_search`,
- `rule_based_strategy_screening`.

Η αρχική υλοποίηση υποστηρίζει:

- ένα asset ανά discovery run,
- long-only direction,
- πλήρως επενδεδυμένο `target_fraction=1.0`,
- framework-produced entry/exit intent,
- signals διαθέσιμα στο close μιας μπάρας,
- entry και exit στο open επόμενης ή μεταγενέστερης μπάρας,
- finite categorical/fixed/integer/stepped-float grids,
- independent capital ανά parameter combination,
- explicit percentage commission, slippage και fixed per-order fees,
- optional scalar-spread approximation μόνο μετά από explicit opt-in,
- batched VectorBT execution με deterministic per-combination trial expansion.

## Unsupported semantics

Τα παρακάτω απορρίπτονται fail-closed:

- same-close fill ή delay μικρότερο από μία μπάρα,
- signal timing διαφορετικό από bar close,
- fill price διαφορετικό από bar open,
- short-only ή long-short,
- multi-asset/shared-capital portfolio,
- partial target weights, fixed units, target weights ή volatility-adjusted
  sizing,
- model-driven/ML walk-forward search,
- continuous ή log-scaled non-enumerable search space,
- dynamic bid/ask spread ή quote-path execution,
- nonzero holding/funding cost,
- ambiguous cost names όπως `spread_bps` ή `commission_bps`,
- intrabar stops, limits, event sequencing, queue ή latency semantics,
- canonical validation, robustness promotion, paper, demo ή live execution.

Η στενή sizing υποστήριξη είναι σκόπιμη: ένα partial cash fraction στο VectorBT
είναι fixed fraction at entry και το asset weight μεταβάλλεται όσο κινείται η
τιμή, ενώ ένα bar engine μπορεί να ερμηνεύει το ίδιο scalar ως διαρκώς
rebalanced exposure. Δεν γίνεται αυθαίρετη μετάφραση πριν υπάρξει ξεχωριστό
capital-semantics parity contract.

## Timing mapping

| STF έννοια | VectorBT mapping | Κατάσταση |
|---|---|---|
| signal known at `close[t]` | entry/exit boolean μετατοπίζεται κατά declared delay | exact |
| `entry_delay_bars >= 1` | buy signal στο αντίστοιχο future row | exact |
| `entry_price_source = open` | `Portfolio.from_signals(close=open_frame)` | exact για το δηλωμένο bar model |
| `exit_delay_bars >= 1` | sell signal στο αντίστοιχο future row | exact |
| `exit_price_source = open` | ίδια open-price σειρά | exact |
| same-close execution | δεν υπάρχει valid policy | unsupported |

Ο adapter ελέγχει έπειτα τα native order records. Timing mismatch δεν
καλύπτεται από numerical tolerance: μετατρέπει ολόκληρο το επηρεαζόμενο batch
σε auditable runtime failures.

## Cost mapping

| STF assumption | VectorBT parameter | Κατάσταση |
|---|---|---|
| `commission_bps_per_side` | `fees = bps / 10_000` | exact percentage of executed order value |
| `cost_per_turnover` | `fees` | screening-equivalent, parity-tested με tolerance |
| `slippage_bps_per_side` | `slippage = bps / 10_000` | exact adverse fill-price fraction |
| `slippage_per_turnover` | `slippage` | screening-equivalent, parity-tested με tolerance |
| `fixed_fee_per_order` | `fixed_fees` | exact currency amount per executed order |
| `spread_bps_per_side` | προστίθεται στο adverse slippage | approximate, explicit opt-in μόνο |
| dynamic bid/ask spread | καμία μετάφραση | unsupported |
| `holding_cost_per_exposed_bar != 0` | καμία μετάφραση | unsupported |

Το synthetic nonzero-cost fixture χρησιμοποιεί absolute net-return tolerance
`1e-5`. Η ανοχή αφορά τη μικρή διαφορά στον τρόπο με τον οποίο τα engines
ενσωματώνουν fee/slippage στο fill sizing. Gross return και timestamps έχουν
ξεχωριστούς αυστηρούς ελέγχους και δεν κρύβονται πίσω από αυτή την ανοχή.

## Data alignment και warmup

Πριν από οποιοδήποτε allocation απαιτούνται:

- non-empty DataFrame,
- timezone-aware, strictly monotonic και unique `DatetimeIndex`,
- `open` και `close` columns με positive finite values,
- exact signal/data index equality.

Warmup `NaN` επιτρέπεται μόνο ως ένα contiguous leading prefix. Το prefix
μετατρέπεται σε explicit no-signal rows, χωρίς forward fill. Internal NaN,
duplicate/non-monotonic timestamps, missing price columns και non-finite prices
απορρίπτονται. Signals που πέφτουν μετά το τέλος του διαθέσιμου sample λόγω
delay δεν εκτελούνται και ο αριθμός τους καταγράφεται στο trial provenance.

## Search-space handling και determinism

Ο executor καταναλώνει το Phase 2 `DiscoverySpecification` και το υπάρχον
backend-neutral `SearchSpace`.

1. Υπολογίζει ολόκληρο το finite cardinality.
2. Εφαρμόζει το frozen `trial_budget` χωρίς να υπερβαίνει το cardinality.
3. Κάνει resource preflight πριν δημιουργήσει parameter ή price matrices.
4. Χρησιμοποιεί το deterministic `SearchSpace.iter_grid` order.
5. Εκτελεί contiguous batches χωρίς να αλλάζει το logical order.
6. Μετατρέπει κάθε combination σε ξεχωριστό `DiscoveryTrial`.

Το trial ID και το seed εξαρτώνται από `research_run_id + parameters`, όχι από
batch ή DataFrame column number. Αλλαγή του batch size δεν αλλάζει parameter
order, IDs ή metrics.

## Resource protection

Η default `VectorBTResourcePolicy` είναι:

| Guard | Default |
|---|---:|
| maximum combinations | 10,000 |
| batch size | 256 |
| maximum estimated working set | 512 MiB |
| conservative bytes per bar/combination | 96 |

Η peak-working-set εκτίμηση είναι
`rows × min(planned combinations, batch size) × 96`, ενώ το full planned
cardinality ελέγχεται ανεξάρτητα από το `max_combinations`. Παραβίαση
combination ή memory cap σηκώνει `resource_limit` πριν γίνει lazy import του
VectorBT, πριν κληθεί signal builder και πριν δημιουργηθούν μεγάλα arrays. Δεν
αλλάζουν global Numba ή threading environment variables και δεν δημιουργείται
persistent VectorBT cache από τον adapter.

## Trial, metric και error mapping

Κάθε combination παράγει portable trial με `completed`, `failed` ή `invalid`
status. Οι βασικές error classes είναι:

| Error class | Phase 2 αποτέλεσμα |
|---|---|
| `unsupported_semantics` από συγκεκριμένο signal set | `invalid` trial |
| `invalid_input` | `invalid` trial |
| `vectorbt_runtime_error` | `failed` trial |
| `invalid_metric` | `invalid` trial |
| preflight `resource_limit` | run-level fail πριν από allocation |

Τα metrics είναι screening metadata μόνο:

- net/gross total return και terminal return drag,
- framework annualized return/volatility/conventional Sharpe,
- framework max drawdown,
- finite bar profit factor όπου ορίζεται,
- completed/open trade count,
- turnover, observation count και warmup missing rate,
- `oos_rows=0` και `oos_coverage=0`, επειδή το backend καταναλώνει μόνο
  `DISCOVERY` evidence και δεν ισχυρίζεται OOS validation.

Ένα zero-trade run ολοκληρώνεται deterministically με `trade_count=0` και
finite zero metrics. Η configured Phase 2 eligibility policy αποφασίζει αν
είναι eligible· ο adapter δεν εφευρίσκει threshold.

## Provenance και artifacts

Κάθε trial αποθηκεύει JSON-compatible metadata για:

- VectorBT/Python/platform/NumPy/pandas/Numba versions,
- capabilities και unsupported scope,
- timing, cost και sizing mapping,
- search cardinality, budget, batch index και resource estimate,
- exact entry/exit timestamps, warmup και dropped end-of-sample signals,
- framework signal metadata και metric definitions.

Όταν ο caller παρέχει νέο artifact root, ο adapter γράφει create-once:

```text
vectorbt_backend.json
vectorbt_timing_mapping.json
vectorbt_cost_mapping.json
vectorbt_search_summary.json
```

Δεν γίνεται overwrite και δεν αποθηκεύεται native portfolio object.

## Candidate lifecycle boundary

Το αποτέλεσμα περνά από το υπάρχον Phase 2 eligibility/ranking/selection.
Selected combination γίνεται `SCREENED` και αμέσως
`PENDING_CANONICAL_VALIDATION`, μαζί με `CanonicalValidationRequest`. Ο
VectorBT adapter δεν μπορεί να δημιουργήσει `CanonicalValidationRecord`,
`RobustnessRecord`, `EvidenceRecord`, promotion decision ή `VALIDATED`
candidate.

## Πότε χρησιμοποιείται κάθε executor

| Executor | Χρήση |
|---|---|
| `GridCandidateGenerator` | μικρό deterministic test/manual search με injected evaluator |
| `ExistingOptunaSearchExecutor` | adaptive search ή non-enumerable/continuous space |
| `VectorBTSearchExecutor` | μεγάλο finite, vectorizable, rule-based screening grid |

Η επιλογή γίνεται explicit μέσω του orchestration-side executor factory. Άγνωστο
όνομα ή unavailable/unsupported backend αποτυγχάνει· δεν υπάρχει silent
fallback.

## Deferred work

- partial/fixed-unit/target-weight/volatility sizing parity,
- short και long-short parity,
- independent-per-asset ή shared-capital multi-asset contract,
- dynamic bid/ask spread και holding/funding costs,
- richer stop/limit/intrabar semantics,
- benchmark report χωρίς hardware-dependent pass/fail threshold,
- Phase 3B PyBroker ML walk-forward adapter,
- Phase 3C Qlib decision/integration.
