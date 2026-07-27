# Delta-neutral funding carry σε BTC και ETH — οδηγός από το Α έως το Ω

## 1. Τι είναι αυτή η στρατηγική σε μία πρόταση

Η στρατηγική αγοράζει το πραγματικό crypto στο spot και ταυτόχρονα πουλάει το
αντίστοιχο perpetual future, με ίση ποσότητα νομισμάτων, όταν το αναμενόμενο
funding είναι αρκετά θετικό ώστε να καλύπτει προμήθειες, slippage και κόστος
κεφαλαίου.

Για παράδειγμα, αν αγοράσουμε `0.01 BTC` στο spot, πουλάμε ταυτόχρονα
`0.01 BTC` στο BTCUSDT perpetual. Δεν προσπαθούμε να προβλέψουμε αν το Bitcoin
θα ανέβει ή θα πέσει. Προσπαθούμε να εισπράξουμε τη χρηματοδότηση που πληρώνουν
οι long perpetual traders στους short perpetual traders.

Το YAML της πλήρους έκδοσης reporting είναι:

`config/research/funding_carry/binance_btc_eth_positive_funding_v2.yaml`

Η έκδοση `v2` δεν αλλάζει τους κανόνες της στρατηγικής `v1`. Είναι δηλωμένη ως
`reporting_only_no_signal_execution_or_split_parameter_changes`: προσθέτει
metrics και artifacts, όχι καινούργια fitted parameters μετά την παρατήρηση των
αποτελεσμάτων.

## 2. Ποια ανωμαλία της αγοράς προσπαθούμε να εκμεταλλευτούμε

Τα perpetual futures δεν έχουν ημερομηνία λήξης. Για να παραμένει η τιμή τους
κοντά στην τιμή spot, το ανταλλακτήριο πραγματοποιεί περιοδικές πληρωμές
funding ανάμεσα στους long και short κατόχους.

- Όταν το funding rate είναι θετικό, οι long πληρώνουν τους short.
- Όταν το funding rate είναι αρνητικό, οι short πληρώνουν τους long.
- Η Binance συνήθως πραγματοποιεί funding settlement ανά οκτώ ώρες, αλλά ο
  κώδικας χρησιμοποιεί τα πραγματικά timestamps και δεν υποθέτει ότι όλα τα
  διαστήματα είναι ακριβώς οκτώ ώρες.

Η οικονομική υπόθεση είναι ότι οι crypto traders έχουν συχνά επίμονη ζήτηση
για leveraged long exposure. Αυτή η ζήτηση μπορεί να δημιουργεί θετικό funding
για αρκετό χρόνο. Ο market-neutral επενδυτής αναλαμβάνει να βρίσκεται short
στο perpetual και πληρώνεται γι' αυτό, ενώ αντισταθμίζει την κατεύθυνση της
τιμής αγοράζοντας spot.

Αυτό δεν είναι δωρεάν χρήμα. Το πιθανό κέρδος υπάρχει επειδή αναλαμβάνουμε:

- κίνδυνο ανταλλακτηρίου και θεματοφυλακής,
- κίνδυνο να γίνει το funding αρνητικό,
- basis risk μεταξύ spot και perpetual,
- execution risk στα δύο legs,
- margin και liquidation risk,
- κόστος κεφαλαίου,
- τεχνικό και λειτουργικό κίνδυνο.

## 3. Τα μέσα που χρησιμοποιούνται

Το universe είναι σκόπιμα μικρό και ρευστό:

- `BTCUSDT` spot και BTCUSDT USD-M perpetual,
- `ETHUSDT` spot και ETHUSDT USD-M perpetual.

Η στρατηγική δεν κάνει short spot. Επιτρέπεται μόνο η κατεύθυνση:

1. long spot,
2. short perpetual,
3. ίσες μονάδες του underlying.

Η αποφυγή short spot είναι σημαντική. Το short spot απαιτεί borrow availability,
borrow rate και πραγματικές ιστορικές πληροφορίες δανεισμού. Αν τα αγνοούσαμε,
θα δημιουργούσαμε μη ρεαλιστικό backtest.

## 4. Γιατί χρησιμοποιούμε ίσες μονάδες και όχι ίσα δολάρια

Αν αγοράσουμε `q` BTC spot και πουλήσουμε `q` BTC στο linear perpetual, η πρώτη
τάξη έκθεσης στην κίνηση του BTC είναι περίπου μηδενική:

```text
spot delta       = +q BTC
perpetual delta  = -q BTC
συνολικό delta   =  0 BTC
```

Αν αντίθετα χρησιμοποιούσαμε ίσα dollar notionals σε κάθε funding interval,
θα άλλαζαν συνεχώς οι ποσότητες των legs. Αυτό θα ισοδυναμούσε με δωρεάν
rebalancing. Το backtest δεν το κάνει.

Η ποσότητα παγώνει από την είσοδο μέχρι την έξοδο του trade. Όταν ανοίξει νέο
trade, η ποσότητα επανυπολογίζεται με βάση το τότε διαθέσιμο equity.

## 5. Τι δεδομένα χρησιμοποιούνται

Η πηγή είναι τα δημόσια REST endpoints της Binance, χωρίς API key:

- spot 30-minute klines,
- USD-M perpetual 30-minute klines,
- πραγματικά funding rates και funding timestamps.

Ο downloader υποστηρίζει επιπλέον:

- mark-price klines,
- index-price klines,
- premium-index klines.

Τα τρία τελευταία δεν είναι απαραίτητα για το βασικό backtest και γι' αυτό το
τρέχον snapshot κατέβηκε με `--required-only`.

Το χρονικό διάστημα του YAML είναι:

```text
start inclusive: 2020-09-01 00:00:00 UTC
end exclusive:   2026-07-01 00:00:00 UTC
```

Το snapshot περιλαμβάνει ανά asset περίπου:

- 102 χιλιάδες spot candles,
- 102 χιλιάδες perpetual candles,
- 6.387 funding settlements.

## 6. Timestamp semantics και αποφυγή lookahead

Ένα 30-minute candle που ανοίγει στις 07:30 δεν είναι γνωστό στις 07:30. Τα
`high`, `low` και `close` γίνονται γνωστά μόνο όταν κλείσει, περίπου στις
07:59:59.999.

Γι' αυτό ο downloader αποθηκεύει τα klines με index το `close_time` και όχι το
`open_time`.

Για κάθε funding settlement στο χρόνο `t`, το price alignment χρησιμοποιεί:

```text
τελευταίο candle με close_time <= funding_time
```

Η ένωση γίνεται με backward `merge_asof`. Απαγορεύεται future candle. Αν δεν
υπάρχει προηγούμενο price bar μέσα στο επιτρεπτό όριο, το πρόγραμμα σταματά.

## 7. Τι γίνεται όταν υπάρχουν stale prices

Στο development dataset βρέθηκαν τρία κοινά spot data gaps για BTC και ETH.
Το μεγαλύτερο είχε ηλικία περίπου τέσσερις ώρες.

Η πολιτική είναι χωρισμένη σε δύο επίπεδα:

- Ένα causal, παλιότερο spot price έως 240 λεπτά μπορεί να χρησιμοποιηθεί μόνο
  για προσωρινό mark-to-market.
- Για υποθετική είσοδο ή έξοδο απαιτείται price ηλικίας έως 31 λεπτά.

Άρα ένα stale price δεν δημιουργεί ψεύτικο fill. Αν υπάρχει ήδη θέση, η θέση
κρατιέται μέχρι να επανέλθει εκτελέσιμη τιμή. Αν δεν υπάρχει θέση, η είσοδος
καθυστερεί. Η τελευταία παρατήρηση κάθε evaluation split πρέπει να είναι
εκτελέσιμη ώστε η θέση να κλείσει με πραγματικό κόστος.

## 8. Πώς κατασκευάζεται το funding forecast

Στο funding settlement `t` γνωρίζουμε το funding που μόλις πραγματοποιήθηκε.
Υπολογίζουμε:

```text
forecast(t) = median των τελευταίων 3 πραγματοποιημένων funding rates
```

Δεν χρησιμοποιείται το funding του επόμενου settlement. Η απόφαση που παίρνεται
στο `t` ισχύει για το διάστημα `(t, t+1]`.

Αυτό σημαίνει:

1. παρατηρούμε το funding στο `t`,
2. υπολογίζουμε το trailing median,
3. ανοίγουμε ή κλείνουμε μετά το settlement,
4. μόνο αν κρατήσουμε τη θέση έως το `t+1` λαμβάνουμε το funding του `t+1`.

Αυτή η χρονική σειρά είναι το βασικό anti-lookahead invariant.

## 9. Ο κανόνας εισόδου

Δεν αρκεί το forecast να είναι απλώς θετικό. Πρέπει να καλύπτει το εκτιμώμενο
round trip, το financing και ένα επιπλέον safety multiplier.

Οι παράμετροι είναι:

- αναμενόμενος ορίζοντας: 90 funding events,
- τυπικό funding interval για το threshold: 8 ώρες,
- safety multiplier: 1.25,
- spot fee: 10 bps ανά πλευρά,
- perpetual fee: 5 bps ανά πλευρά,
- spot slippage: 1 bp ανά πλευρά,
- perpetual slippage: 1 bp ανά πλευρά,
- ετήσιο financing rate: 3%,
- capital ανά 1 dollar spot notional: 1.25 dollars.

Το one-way transaction cost είναι:

```text
10 + 5 + 1 + 1 = 17 bps
```

Το round trip είναι περίπου:

```text
2 × 17 = 34 bps
```

Ο αναμενόμενος ορίζοντας 90 × 8 ώρες είναι περίπου 30 ημέρες. Το financing
αυτής της περιόδου προστίθεται στο απαιτούμενο edge. Το συνολικό ποσό
πολλαπλασιάζεται με 1.25 και μετατρέπεται σε απαιτούμενο funding ανά event.

Η είσοδος επιτρέπεται μόνο όταν:

```text
forecast > 0
και
forecast × 90 > 1.25 × (round-trip costs + expected financing)
```

Με τις δηλωμένες παραμέτρους, το threshold είναι περίπου 0.9 basis points ανά
funding event. Υπολογίζεται από τον κώδικα και καταγράφεται σε κάθε event ως
`entry_threshold_rate`.

## 10. Ο κανόνας εξόδου

Η θέση κλείνει όταν συμβεί ένα από τα παρακάτω:

- το trailing funding forecast γίνει μικρότερο ή ίσο με μηδέν,
- η θέση συμπληρώσει 180 funding intervals,
- φτάσουμε στο τέλος του evaluation split.

Αν το τρέχον price είναι stale και δεν επιτρέπεται execution, η έξοδος
καθυστερεί. Δεν χρησιμοποιείται η παλιά τιμή ως υποθετικό fill.

Σημαντικό: αν το funding γίνει αρνητικό στο settlement `t`, η θέση που ήταν
ανοιχτή στο προηγούμενο interval πληρώνει κανονικά αυτό το αρνητικό funding.
Μόνο μετά την παρατήρησή του μπορεί να κλείσει. Αυτό είναι δυσάρεστο αλλά
αιτιακά σωστό.

## 11. Position sizing και κεφάλαιο

Για κάθε 1.00 μονάδα portfolio equity, το YAML επιτρέπει περίπου:

```text
spot notional = equity / 1.25 = 0.80 × equity
```

Ανοίγεται ίση underlying ποσότητα στο perpetual. Επομένως το αρχικό gross
market exposure είναι περίπου `1.60 × equity`, παρότι το directional delta σε
μονάδες του asset είναι περίπου μηδέν.

Το επιπλέον 0.25 στο `capital_per_spot_notional` λειτουργεί ως margin/buffer.
Δεν αποτελεί πλήρες liquidation model. Πριν από live χρήση χρειάζεται
venue-specific margin simulation.

## 12. Πώς υπολογίζεται το PnL

Για ποσότητα `q`, από το προηγούμενο settlement στο τρέχον:

```text
spot PnL       = q × (spot_now - spot_previous)
perpetual PnL  = -q × (perp_now - perp_previous)
funding PnL    = q × perp_now × realized_funding_rate
gross PnL      = spot PnL + perpetual PnL + funding PnL
```

Στη συνέχεια αφαιρούνται:

```text
spot fees
perpetual fees
spot slippage
perpetual slippage
financing cost
```

Όλα τα components διαιρούνται με το equity πριν από το event. Το νέο equity
ενημερώνεται και το επόμενο trade γίνεται scale στο νέο equity.

Για κάθε event ελέγχεται αριθμητικά:

```text
spot return component
+ perpetual return component
+ funding return component
- fee cost
- slippage cost
- financing cost
= net return
```

Αν το reconciliation error ξεπεράσει `1e-12`, το run αποτυγχάνει.

## 13. Τι σημαίνει basis return

Basis είναι η διαφορά perpetual και spot:

```text
basis_bps = (perpetual_price / spot_price - 1) × 10.000
```

Επειδή τα legs έχουν ίση underlying ποσότητα, η κοινή κίνηση του BTC ή ETH
ακυρώνεται σε μεγάλο βαθμό. Αυτό που μένει από τις τιμές είναι κυρίως η αλλαγή
του basis.

Το reporting χωρίζει:

- `funding_return_component`,
- `basis_return_component`,
- spot και perpetual components ξεχωριστά.

Έτσι μπορούμε να δούμε αν το αποτέλεσμα προήλθε πραγματικά από funding ή από
τυχαία μεταβολή του basis.

## 14. Chronological research splits

Τα splits είναι σταθερά και μη επικαλυπτόμενα:

| Split | Από | Έως, exclusive | Κατάσταση |
|---|---|---|---|
| Development | 2020-09-01 | 2023-01-01 | ανοικτό |
| Validation | 2023-01-01 | 2025-01-01 | ανοικτό |
| Locked test | 2025-01-01 | 2026-07-01 | κλειδωμένο |

Κάθε split ξεκινά flat και κλείνει flat. Δεν μεταφέρεται θέση ή κόστος από το
προηγούμενο split. Τα trailing funding features μπορούν να χρησιμοποιούν μόνο
ιστορικές παρατηρήσεις πριν από την αρχή του split, αλλά το simulated κεφάλαιο
και η θέση επανεκκινούν.

Το locked test δεν εκτελείται χωρίς το ρητό flag:

```text
--unlock-locked-test
```

## 15. Τα βασικά performance metrics

Το `summary.json` περιλαμβάνει για portfolio και κάθε asset:

- cumulative return,
- annualized return,
- annualized volatility,
- Sharpe ratio,
- Sortino ratio,
- Calmar ratio,
- maximum drawdown,
- profit factor σε event returns,
- hit rate σε μη μηδενικά event returns,
- gross PnL,
- net PnL,
- gross και net return sums,
- total cost και cost drag,
- cost-to-gross-PnL,
- average και total turnover.

Η annualization γίνεται από πλήρες UTC calendar-daily grid. Η αγορά crypto
λειτουργεί επτά ημέρες την εβδομάδα, γι' αυτό δεν χρησιμοποιείται η υπόθεση
252 trading days.

## 16. Extended performance metrics

Η κατηγορία `extended_performance` προσθέτει:

- arithmetic annualized daily return,
- geometric mean daily return,
- return-to-volatility ratio,
- return-to-max-drawdown ratio,
- correlation της στρατηγικής με το spot,
- beta της στρατηγικής ως προς το spot.

Για market-neutral carry θέλουμε correlation και beta κοντά στο μηδέν. Μεγάλο
beta σημαίνει ότι η αντιστάθμιση δεν λειτουργεί όπως περιμένουμε.

## 17. Risk και tail metrics

Τα metrics υπολογίζονται τόσο στα event returns όσο και στα calendar-daily
returns:

- mean και median,
- standard deviation,
- skewness,
- excess kurtosis,
- minimum και maximum return,
- positive και zero-return fraction,
- downside deviation,
- gain-to-pain ratio,
- Omega ratio με threshold μηδέν,
- tail ratio 95% προς 5%,
- historical VaR 95% και 99%,
- historical CVaR / expected shortfall 95% και 99%.

Το VaR δεν είναι εγγύηση μέγιστης ζημίας. Λέει ποιο loss threshold ξεπεράστηκε
σε ένα μικρό ποσοστό του ιστορικού δείγματος. Το CVaR κοιτάζει το μέσο loss
ακριβώς μέσα σε αυτή την κακή ουρά.

## 18. Drawdown metrics

Η κατηγορία `drawdown_analysis` περιλαμβάνει:

- maximum drawdown,
- average negative drawdown,
- Ulcer Index,
- μέγιστο πλήθος underwater events,
- μέγιστες underwater calendar days,
- timestamp προηγούμενου peak,
- timestamp drawdown trough,
- timestamp recovery, αν υπάρχει,
- ημέρες peak-to-trough,
- ημέρες trough-to-recovery.

Το drawdown υπολογίζεται στην πλήρη event-level equity curve, ώστε να μην
κρύβεται intraday ή intra-funding drawdown από daily aggregation.

## 19. Trade-level metrics

Για BTC και ETH παράγεται ξεχωριστό trade ledger. Κάθε γραμμή περιέχει:

- entry και exit timestamps,
- holding events και holding hours,
- entry/exit spot και perpetual prices,
- entry/exit basis,
- entry/exit equity,
- καθαρό trade return,
- gross return sum,
- funding return,
- basis return,
- fees,
- slippage,
- financing,
- minimum και maximum event return,
- maximum gross leverage του trade.

Από το ledger υπολογίζονται:

- trade count,
- winners, losers και flat trades,
- win rate,
- average και median trade return,
- trade-return standard deviation,
- best και worst trade,
- average win και average loss,
- payoff ratio,
- trade-level profit factor,
- expectancy,
- maximum consecutive wins και losses,
- average, median και maximum holding period,
- average funding return ανά trade,
- average basis return ανά trade,
- average total cost ανά trade.

Δεν αναφέρεται portfolio trade count, επειδή BTC και ETH μπορούν να ανοίγουν
και να κλείνουν σε διαφορετικά timestamps. Το portfolio αξιολογείται ως κοινή
time series και τα trade metrics παραμένουν σωστά σε επίπεδο asset.

## 20. Funding και basis attribution

Η κατηγορία `funding_and_basis_attribution` περιλαμβάνει:

- active funding events,
- συνολικό funding return,
- συνολικό basis return,
- spot και perpetual component sums,
- funding share των θετικών gross components,
- average, median, minimum και maximum realized funding όταν η θέση είναι
  ενεργή,
- positive funding fraction,
- πλήθος αρνητικών funding events που πληρώθηκαν,
- average, median, minimum και maximum basis σε bps.

Αν το funding component δεν είναι η κύρια σταθερή πηγή κέρδους, η αρχική
οικονομική υπόθεση χρειάζεται επανεξέταση.

## 21. Αναλυτικά cost metrics

Η κατηγορία `detailed_cost_attribution` χωρίζει:

- fee cost,
- slippage cost,
- συνολικό transaction cost,
- financing cost,
- όλα τα costs μαζί,
- ποσοστό κάθε κατηγορίας στα συνολικά costs,
- cost προς absolute gross return sum.

Οι fees και το slippage χρεώνονται στην πραγματική τρέχουσα αξία κάθε leg και
όχι σε σταθερό υποθετικό notional.

## 22. Exposure και leverage metrics

Η κατηγορία `exposure_and_leverage` περιλαμβάνει:

- fraction του χρόνου με ενεργή θέση,
- average gross leverage σε όλα τα events,
- average και median gross leverage όταν υπάρχει θέση,
- maximum gross leverage,
- average net mark-notional ratio,
- maximum absolute net mark-notional ratio.

Το gross leverage μπορεί να είναι αρκετά πάνω από 1 παρότι το directional
delta είναι περίπου μηδέν. Market neutral δεν σημαίνει χωρίς leverage ή χωρίς
κίνδυνο.

## 23. Calendar metrics

Παράγονται daily, weekly, monthly και yearly return series. Για κάθε συχνότητα
υπολογίζονται:

- observations,
- compounded return,
- mean και median return,
- standard deviation,
- positive-period fraction,
- best και worst period,
- timestamps καλύτερου και χειρότερου period.

Παράγεται επίσης dictionary με year-by-year returns. Αυτό μας βοηθά να δούμε
αν το αποτέλεσμα βασίζεται αποκλειστικά σε μία crypto bull market.

## 24. Rolling metrics

Για windows 30, 90, 180 και 365 calendar days παράγονται πλήρεις time series:

- rolling compounded return,
- rolling annualized volatility,
- rolling Sharpe,
- rolling maximum drawdown.

Στο JSON αποθηκεύονται minimum, median, maximum, latest value και observation
count για κάθε rolling metric. Οι πλήρεις σειρές αποθηκεύονται σε CSV.

Rolling Sharpe που καταρρέει στα νεότερα windows είναι ένδειξη ότι το funding
edge μπορεί να έχει κορεστεί ή να έχει αλλάξει regime.

## 25. Bootstrap uncertainty

Το YAML ενεργοποιεί deterministic circular moving-block bootstrap:

```text
samples:            2000
block length:       21 calendar days
confidence level:   95%
random seed:        42
```

Δεν ανακατεύονται ανεξάρτητα όλες οι ημέρες. Δειγματοληπτούνται blocks 21
ημερών ώστε να διατηρείται μέρος της χρονικής εξάρτησης και των regimes.

Παράγονται για annualized return και Sharpe:

- bootstrap median,
- lower confidence bound,
- upper confidence bound,
- probability ότι η τιμή είναι θετική.

Το bootstrap μετρά αβεβαιότητα μέσα στο ιστορικό δείγμα. Δεν προστατεύει από
καινούργιο market regime, exchange failure ή structural disappearance του
funding premium.

## 26. Cost-stress grid

Το `v2` τρέχει αυτόματα ολόκληρη τη στρατηγική με:

- 1.00× transaction costs,
- 1.25× transaction costs,
- 1.50× transaction costs,
- 2.00× transaction costs.

Δεν αφαιρεί απλώς περισσότερο κόστος από τα ίδια trades. Επανυπολογίζει το
entry threshold, άρα μπορεί να πάρει λιγότερα trades όταν τα costs αυξάνονται.

Το validation result με τα τρέχοντα δεδομένα είναι:

| Cost multiplier | Portfolio return | Sharpe |
|---:|---:|---:|
| 1.00× | 8.96% | 5.07 |
| 1.25× | 8.17% | 6.11 |
| 1.50× | 7.68% | 5.46 |
| 2.00× | 6.43% | 4.22 |

Η Sharpe μπορεί να αυξηθεί σε ενδιάμεσο stress επειδή το υψηλότερο threshold
αφαιρεί χαμηλής ποιότητας entries. Αυτό δεν σημαίνει ότι το κόστος βοηθά το
PnL· η συνολική απόδοση πέφτει κανονικά.

## 27. Data-quality metrics

Για κάθε scope καταγράφονται:

- αρχικό και τελικό timestamp,
- πλήθος observations,
- elapsed calendar days,
- median και maximum event interval,
- intervals μεγαλύτερα από 12 ώρες,
- execution-price availability fraction,
- πλήθος μη εκτελέσιμων stale events,
- median και maximum spot-price age,
- median και maximum perpetual-price age.

Τα data-quality metrics πρέπει να ελέγχονται πριν από performance metrics.
Υψηλή απόδοση πάνω σε προβληματική ευθυγράμμιση δεν είναι alpha.

## 28. Acceptance gates

Το validation χαρακτηρίζεται qualified μόνο αν ισχύουν όλα:

- portfolio Sharpe τουλάχιστον 0.75,
- portfolio cumulative return μη αρνητικό,
- τουλάχιστον 8 entries ανά asset,
- θετικό baseline return και σε BTC και σε ETH,
- θετικό 1.5× cost-stress return και σε BTC και σε ETH,
- θετικό portfolio return στο 1.5× stress.

Τα gates δεν αποδεικνύουν ότι η στρατηγική θα κερδίσει live. Αποτρέπουν όμως
την προώθηση ενός αποτελέσματος που βασίζεται σε ένα asset, ελάχιστα trades ή
εύθραυστες παραδοχές κόστους.

## 29. Τι artifacts παράγονται

Στο root κάθε run γράφονται:

- `summary.json`: όλα τα nested metrics,
- `metrics_flat.csv`: ένα metric ανά γραμμή για εύκολο filtering,
- `cost_stress.json`: metrics για κάθε cost multiplier,
- `run_manifest.json`: config hash, data-manifest hash, git state και hashes όλων
  των artifacts.

Για κάθε split γράφονται:

- `portfolio.csv`,
- `portfolio_returns_daily.csv`,
- `portfolio_returns_weekly.csv`,
- `portfolio_returns_monthly.csv`,
- `portfolio_returns_yearly.csv`,
- `portfolio_rolling_metrics.csv`.

Για κάθε asset γράφονται:

- `{SYMBOL}_events.csv`,
- `{SYMBOL}_trades.csv`,
- `{SYMBOL}_returns_daily.csv`,
- `{SYMBOL}_returns_weekly.csv`,
- `{SYMBOL}_returns_monthly.csv`,
- `{SYMBOL}_returns_yearly.csv`,
- `{SYMBOL}_rolling_metrics.csv`.

## 30. Reproducibility και hashes

Ο downloader δημιουργεί `manifest.json` με:

- ακριβές request contract,
- provider και endpoints,
- UTC start/end,
- symbols και interval,
- row counts,
- timestamps πρώτης/τελευταίας γραμμής,
- SHA-256 κάθε CSV,
- SHA-256 ολόκληρου request contract.

Αν υπάρχει snapshot με διαφορετικό request ή αποτυχημένο hash, ο downloader
δεν το αντικαθιστά σιωπηρά. Χρειάζεται `--refresh` ή διαφορετικό output path.

Το backtest επαληθεύει τους hashes πριν φορτώσει τα δεδομένα.

## 31. Docker commands

### Download των απαραίτητων δεδομένων

```bash
docker compose run --rm app python scripts/download_binance_funding_carry.py \
  config/research/funding_carry/binance_btc_eth_positive_funding_v2.yaml \
  --required-only
```

Αν το snapshot υπάρχει και οι hashes ταιριάζουν, χρησιμοποιείται το cache.

### Development με όλα τα metrics

```bash
docker compose run --rm app python scripts/run_funding_carry.py \
  config/research/funding_carry/binance_btc_eth_positive_funding_v2.yaml \
  --phase development
```

### Validation με όλα τα metrics και cost grid

```bash
docker compose run --rm app python scripts/run_funding_carry.py \
  config/research/funding_carry/binance_btc_eth_positive_funding_v2.yaml \
  --phase validation
```

### Tests

```bash
docker compose run --rm app pytest -q \
  tests/market_data/test_binance_public_data.py \
  tests/backtesting/test_funding_carry.py
```

### Locked test

Το command υπάρχει, αλλά δεν πρέπει να εκτελεστεί μέχρι να παγώσουν οριστικά
κώδικας, YAML, acceptance gates και review checklist:

```bash
docker compose run --rm app python scripts/run_funding_carry.py \
  config/research/funding_carry/binance_btc_eth_positive_funding_v2.yaml \
  --phase locked_test \
  --unlock-locked-test
```

## 32. Πώς διαβάζουμε σωστά τα μέχρι τώρα αποτελέσματα

Τα μέχρι τώρα frozen-rule αποτελέσματα είναι:

| Split | Portfolio return | Annualized return | Sharpe | Max drawdown |
|---|---:|---:|---:|---:|
| Development 2020–2022 | 30.06% | 11.93% | 4.62 | -7.03% |
| Validation 2023–2024 | 8.96% | 4.38% | 5.07 | -1.47% |

Στο validation:

- BTCUSDT: `+8.07%`, 18 entries,
- ETHUSDT: `+9.86%`, 17 entries,
- 1.5× cost-stress portfolio: `+7.68%`,
- 2.0× cost-stress portfolio: `+6.43%`.

Η πτώση από development σε validation είναι σημαντική. Η στρατηγική παραμένει
θετική αλλά το διαθέσιμο funding premium είναι μικρότερο. Αυτό είναι πιο
ρεαλιστικό από το να θεωρήσουμε ότι η development απόδοση θα συνεχιστεί.

Η πολύ υψηλή Sharpe προέρχεται από μικρά, σχετικά σταθερά delta-neutral returns
και χαμηλή volatility. Δεν είναι άμεσα συγκρίσιμη με Sharpe directional
strategy. Πρέπει να ελεγχθούν ιδιαίτερα:

- tail losses,
- basis drawdowns,
- exchange outages,
- πραγματικά fills δύο legs,
- margin/liquidation mechanics.

## 33. Τι δεν μοντελοποιείται ακόμη

Το backtest δεν περιλαμβάνει ακόμη:

- order-book depth ανά ιστορικό timestamp,
- partial fills,
- latency μεταξύ spot και perpetual order,
- legging loss αν εκτελεστεί μόνο το ένα leg,
- maker-order queue position,
- venue-specific maintenance margin και liquidation engine,
- stablecoin depeg,
- exchange default ή withdrawal freeze,
- φορολογία,
- account-tier fee discounts,
- live funding estimate revisions πριν από settlement,
- capacity πέρα από τα εξαιρετικά ρευστά BTC και ETH.

Οι δηλωμένες taker-like fees και slippage είναι πιο συντηρητικές από δωρεάν
maker fills, αλλά δεν αντικαθιστούν πραγματικό order-book replay.

## 34. Οι σημαντικότεροι πραγματικοί κίνδυνοι

### Funding reversal

Το funding μπορεί να γίνει αρνητικό απότομα. Η θέση πληρώνει το πρώτο αρνητικό
settlement πριν μπορέσει να αντιδράσει.

### Basis widening

Spot και perpetual μπορούν προσωρινά να αποκλίνουν. Ακόμη και με μηδενικό
underlying delta, το basis μπορεί να προκαλέσει drawdown.

### Liquidation

Το short perpetual χρειάζεται margin. Με ανεπαρκές buffer, μια μεγάλη κίνηση ή
mark-price dislocation μπορεί να οδηγήσει σε liquidation παρότι το συνολικό
οικονομικό trade είναι hedged.

### Exchange and custody risk

Και τα δύο legs βρίσκονται στο ίδιο venue στο backtest. Αυτό μειώνει operational
latency αλλά συγκεντρώνει counterparty risk.

### Execution mismatch

Αν εκτελεστεί το spot αλλά όχι το perpetual, υπάρχει προσωρινό directional
exposure. Το αντίστροφο είναι επίσης επικίνδυνο.

### Capacity

BTC και ETH έχουν μεγάλη ρευστότητα, αλλά το slippage αυξάνεται με το μέγεθος.
Το fixed 1 bp δεν ισχύει για απεριόριστο capital.

## 35. Τι χρειάζεται πριν από paper trading

Πριν γίνει paper deployment πρέπει να ολοκληρωθούν:

1. ανεξάρτητη αναπαραγωγή σε Bybit,
2. σύγκριση Binance και Bybit funding timestamps/rates,
3. venue-specific fee schedule του πραγματικού account tier,
4. margin και liquidation simulation,
5. order-book slippage model ανά notional,
6. atomic ή hedged two-leg execution policy,
7. monitoring για stale market data,
8. monitoring για position mismatch,
9. kill switch σε exchange/API failure,
10. reconciliation πραγματικών funding cash flows.

## 36. Τι χρειάζεται πριν ανοίξει το locked test

Πριν χρησιμοποιηθεί το `--unlock-locked-test` πρέπει να αποθηκευτούν:

- git commit του τελικού κώδικα,
- SHA-256 του `v2` YAML,
- SHA-256 του data manifest,
- ακριβές acceptance checklist,
- απόφαση ότι δεν θα αλλάξουν thresholds μετά το αποτέλεσμα,
- signed-off λίστα γνωστών περιορισμών.

Αν το locked test αποτύχει, δεν πρέπει να βελτιστοποιηθεί επανειλημμένα πάνω
στο ίδιο διάστημα και να συνεχίσει να ονομάζεται locked. Θα έχει μετατραπεί σε
νέο development set και θα χρειάζεται νεότερο, πραγματικά αθέατο test.

## 37. Τελική ερμηνεία

Η στρατηγική έχει καθαρή οικονομική λογική και θετικό chronological validation
με συντηρητικά δηλωμένα costs. Αυτό την κάνει υπολογίσιμο alpha candidate.

Δεν είναι ακόμη αποδεδειγμένο live alpha. Το τελικό συμπέρασμα απαιτεί:

- επιτυχία στο πραγματικά κλειδωμένο test,
- cross-venue replication,
- paper execution με πραγματικά order books,
- επιβεβαίωση ότι τα realized fees, slippage και funding cash flows συμφωνούν
  με το backtest.

Η σωστή ερώτηση δεν είναι «έχει υψηλή Sharpe;». Η σωστή ερώτηση είναι:

> Παραμένει θετική η καθαρή χρηματοδότηση μετά από όλα τα πραγματικά κόστη,
> χωρίς directional leakage, σε διαφορετικές περιόδους και σε διαφορετικό
> venue;

Το `v2` reporting έχει σχεδιαστεί ώστε να μπορούμε να απαντήσουμε αυτή την
ερώτηση με αναγώγιμα δεδομένα και όχι με μία μόνο τελική Sharpe.
