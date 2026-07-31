<!-- Το αρχείο παράγεται από scripts/generate_component_catalog_appendices.py. Μην αλλάζετε χειροκίνητα τις registry-backed ενότητες. -->

# Κατάλογος Targets

Τελευταία ενημέρωση: 2026-07-31

Τα targets είναι μελλοντικά outcomes για εκπαίδευση και αξιολόγηση. Επιτρέπεται να κοιτούν μπροστά μόνο στο label-building στάδιο και δεν πρέπει ποτέ να επιστρέφουν στο feature matrix.

Ο κατάλογος συνδέεται απευθείας με τα registries: κάθε ενεργό όνομα του κώδικα έχει ξεχωριστή αναλυτική ενότητα, ερμηνεία τιμών, χρονικό συμβόλαιο και πλήρες YAML. Τα ονόματα κώδικα, οι στήλες και οι YAML τιμές παραμένουν στα αγγλικά για να αντιγράφονται αυτούσια· όλο το επεξηγηματικό κείμενο είναι ελληνικό.

Στα YAML, `<required>` σημαίνει υποχρεωτική τιμή που πρέπει να αντικατασταθεί και `<configured>` επιλογή χωρίς ασφαλή καθολική προεπιλογή. Το `null` σημαίνει ότι η λειτουργία είναι προαιρετική ή ότι ο υπολογιστής θα επιλέξει το προεπιλεγμένο όνομα/συμπεριφορά.

## Ενεργά targets

### `forward_return`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά την απόδοση από το timestamp t έως ακριβώς `horizon` bars στο μέλλον και προαιρετικά τη μετατρέπει σε δυαδικό label. Θετική αριθμητική τιμή σημαίνει υψηλότερη μελλοντική τιμή και αρνητική χαμηλότερη· το label 1 σημαίνει υπέρβαση του threshold, ενώ οι τελευταίες σειρές χωρίς πλήρη ορίζοντα μένουν NaN.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `fwd_col`, `label_col`, `price_col`, `returns_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `quantiles`, `returns_col`; χωρίς ασφαλές καθολικό default `fwd_col`; με προεπιλογή `horizon`, `label_col`, `price_col`, `returns_type`, `threshold`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: forward_return
  params:
    fwd_col: <configured>
    horizon: 1
    label_col: label
    price_col: close
    quantiles: <required>
    returns_col: <required>
    returns_type: simple
    threshold: 0.0
```

### `future_return_regression`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά συνεχή μελλοντική απόδοση σταθερού ορίζοντα για regression. Το μέγεθος εκφράζει την αναμενόμενη κατεύθυνση και ένταση που καλείται να προβλέψει το μοντέλο· clipping ή transformation αλλάζει την εκπαίδευση, όχι το οικονομικό πρόσημο.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `fwd_col`, `label_col`, `normalizer_col`, `price_col`, `raw_fwd_col`, `returns_col`, `target_col`, `volatility_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`, `returns_col`; χωρίς ασφαλές καθολικό default `fwd_col`, `horizon_bars`, `label_col`, `normalizer_col`, `raw_fwd_col`, `target_col`; με προεπιλογή `horizon`, `normalize_by_volatility`, `price_col`, `returns_type`, `volatility_col`, `volatility_floor`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: future_return_regression
  params:
    clip: <required>
    fwd_col: <configured>
    horizon: 1
    horizon_bars: <configured>
    label_col: <configured>
    normalize_by_volatility: false
    normalizer_col: <configured>
    price_col: close
    raw_fwd_col: <configured>
    returns_col: <required>
    returns_type: simple
    target_col: <configured>
    volatility_col: atr_14
    volatility_floor: 1.0e-12
```

### `volatility_normalized_future_return`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά τη μελλοντική απόδοση διαιρεμένη με point-in-time volatility ή ATR scale. Θετικό 1 σημαίνει περίπου μία μονάδα τρέχοντος κινδύνου υπέρ της αγοράς και αρνητικό -1 μία μονάδα κατά· επιτρέπει κοινό target μεταξύ assets διαφορετικής κλίμακας.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `volatility_col`, `raw_fwd_col`, `normalizer_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `raw_fwd_col`, `normalizer_col`, `fwd_col`, `label_col`; με προεπιλογή `price_col`, `volatility_col`, `horizon_bars`, `returns_type`, `volatility_floor`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: volatility_normalized_future_return
  params:
    price_col: close
    volatility_col: atr_14
    horizon_bars: 1
    returns_type: simple
    volatility_floor: 1.0e-12
    raw_fwd_col: <configured>
    normalizer_col: <configured>
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `risk_adjusted_future_return`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά μελλοντική απόδοση σε σχέση με τη μελλοντική realized volatility του ίδιου horizon. Μεγαλύτερη θετική τιμή σημαίνει καλύτερη απόδοση ανά μονάδα πραγματοποιημένου κινδύνου και αρνητική δυσμενή σχέση· επειδή ο παρονομαστής κοιτά το μέλλον είναι αυστηρά label-only.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `raw_fwd_col`, `realized_vol_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `raw_fwd_col`, `realized_vol_col`, `fwd_col`, `label_col`; με προεπιλογή `price_col`, `horizon_bars`, `returns_type`, `volatility_floor`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: risk_adjusted_future_return
  params:
    price_col: close
    horizon_bars: 2
    returns_type: simple
    volatility_floor: 1.0e-12
    raw_fwd_col: <configured>
    realized_vol_col: <configured>
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `r_multiple_regression`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά fixed-horizon απόδοση σε μονάδες αρχικού risk distance γνωστού στο t. Τιμή +2 σημαίνει κέρδος δύο R και -1 απώλεια ενός R, επιτρέποντας οικονομικά συνεπή regression και σύγκριση διαφορετικών assets ή volatility regimes.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `volatility_col`, `raw_fwd_col`, `risk_distance_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `raw_fwd_col`, `risk_distance_col`, `fwd_col`, `label_col`; με προεπιλογή `price_col`, `volatility_col`, `atr_multiple`, `returns_type`, `volatility_floor`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: r_multiple_regression
  params:
    price_col: close
    volatility_col: atr_14
    atr_multiple: 2.0
    returns_type: simple
    volatility_floor: 1.0e-12
    raw_fwd_col: <configured>
    risk_distance_col: <configured>
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `mfe_regression`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά τη μέγιστη ευνοϊκή κίνηση της μελλοντικής OHLC διαδρομής στον επιλεγμένο ορίζοντα. Μεγαλύτερο MFE σημαίνει μεγαλύτερη διαθέσιμη ανοδική κίνηση για long ή καθοδική για short· μπορεί να κανονικοποιηθεί με volatility αλλά δεν δηλώνει ότι το κέρδος ήταν εκτελέσιμο χωρίς stop policy.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `high_col`, `low_col`, `volatility_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `fwd_col`, `label_col`; με προεπιλογή `price_col`, `high_col`, `low_col`, `normalize_by_volatility`, `volatility_col`, `volatility_floor`, `direction`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: mfe_regression
  params:
    price_col: close
    high_col: high
    low_col: low
    normalize_by_volatility: false
    volatility_col: atr_14
    volatility_floor: 1.0e-12
    fwd_col: <configured>
    label_col: <configured>
    direction: long
    clip: <required>
```

### `mae_regression`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά τη μέγιστη δυσμενή κίνηση της μελλοντικής διαδρομής. Πιο αρνητικό MAE σημαίνει βαθύτερη adverse excursion και μεγαλύτερο stop risk· χρησιμοποιείται για επιλογή stop, sizing και απόρριψη setups με κακή αναμενόμενη διαδρομή.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `high_col`, `low_col`, `volatility_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `fwd_col`, `label_col`; με προεπιλογή `price_col`, `high_col`, `low_col`, `normalize_by_volatility`, `volatility_col`, `volatility_floor`, `direction`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: mae_regression
  params:
    price_col: close
    high_col: high
    low_col: low
    normalize_by_volatility: false
    volatility_col: atr_14
    volatility_floor: 1.0e-12
    fwd_col: <configured>
    label_col: <configured>
    direction: long
    clip: <required>
```

### `mfe_mae_ratio_regression`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά τον λόγο ευνοϊκής προς δυσμενή excursion μέσα στον μελλοντικό ορίζοντα. Υψηλότερος λόγος σημαίνει καλύτερη δυνητική ανταμοιβή σε σχέση με το adverse path, ενώ μικρός λόγος δηλώνει ότι το setup προσφέρει λίγο upside για τον κίνδυνο που αναλαμβάνει.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `high_col`, `low_col`, `mfe_col`, `mae_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `mfe_col`, `mae_col`, `fwd_col`, `label_col`; με προεπιλογή `direction`, `mode`, `price_col`, `high_col`, `low_col`, `denominator_floor`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: mfe_mae_ratio_regression
  params:
    direction: long
    mode: ratio
    price_col: close
    high_col: high
    low_col: low
    denominator_floor: 1.0e-12
    mfe_col: <configured>
    mae_col: <configured>
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `downside_adjusted_future_return`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά μελλοντική απόδοση αφού αφαιρέσει ποινή για δυσμενή ενδιάμεση διαδρομή. Δύο trades με ίδιο τελικό return παίρνουν διαφορετικό target αν το ένα υπέστη βαθύτερο drawdown· μεγαλύτερη τιμή σημαίνει πιο καθαρή και διαχειρίσιμη πορεία.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `high_col`, `low_col`, `volatility_col`, `raw_fwd_col`, `mae_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `raw_fwd_col`, `mae_col`, `fwd_col`, `label_col`; με προεπιλογή `direction`, `penalty_lambda`, `price_col`, `high_col`, `low_col`, `normalize_by_volatility`, `volatility_col`, `volatility_floor`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: downside_adjusted_future_return
  params:
    direction: long
    penalty_lambda: 1.0
    price_col: close
    high_col: high
    low_col: low
    normalize_by_volatility: false
    volatility_col: atr_14
    volatility_floor: 1.0e-12
    raw_fwd_col: <configured>
    mae_col: <configured>
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `future_trend_slope`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά την κλίση γραμμικής τάσης πάνω στις μελλοντικές τιμές του horizon. Θετική κλίση δηλώνει ανοδική μελλοντική τροχιά, αρνητική καθοδική και μεγάλο απόλυτο μέγεθος ισχυρότερη τάση· προαιρετική volatility normalization βελτιώνει τη συγκρισιμότητα.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `volatility_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `fwd_col`, `label_col`; με προεπιλογή `price_col`, `horizon_bars`, `normalize_by_price`, `normalize_by_volatility`, `volatility_col`, `volatility_floor`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: future_trend_slope
  params:
    price_col: close
    horizon_bars: 5
    normalize_by_price: true
    normalize_by_volatility: false
    volatility_col: atr_14
    volatility_floor: 1.0e-12
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `future_path_efficiency`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά πόσο ευθύγραμμη είναι η μελλοντική διαδρομή από την αρχή έως το τέλος του horizon. Τιμή κοντά στο 1 δείχνει καθαρή κατευθυντική κίνηση και κοντά στο 0 θορυβώδες μονοπάτι· στη signed μορφή το πρόσημο προσθέτει την τελική κατεύθυνση.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `fwd_col`, `label_col`; με προεπιλογή `price_col`, `horizon_bars`, `signed`, `path_floor`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: future_path_efficiency
  params:
    price_col: close
    horizon_bars: 2
    signed: true
    path_floor: 1.0e-12
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `excess_return_regression`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά τη μελλοντική απόδοση του asset μείον τη μελλοντική απόδοση benchmark. Θετική τιμή σημαίνει αναμενόμενη υπεραπόδοση και αρνητική υστέρηση, απομονώνοντας relative-strength alpha από τη γενική κίνηση της αγοράς.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `benchmark_price_col`, `price_col`, `benchmark_fwd_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `benchmark_fwd_col`, `fwd_col`, `label_col`; με προεπιλογή `benchmark_price_col`, `price_col`, `returns_type`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: excess_return_regression
  params:
    benchmark_price_col: benchmark_close
    price_col: close
    returns_type: simple
    benchmark_fwd_col: <configured>
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `residual_return_regression`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά το μελλοντικό return που απομένει αφού αφαιρεθεί beta-scaled benchmark return. Θετική residual τιμή δηλώνει alpha πέρα από τη συστηματική έκθεση, ενώ το beta πρέπει να έχει εκτιμηθεί μόνο με πληροφορία διαθέσιμη στο t.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `benchmark_price_col`, `price_col`, `raw_fwd_col`, `benchmark_fwd_col`, `beta_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `min_periods`, `raw_fwd_col`, `benchmark_fwd_col`, `beta_col`, `fwd_col`, `label_col`; με προεπιλογή `benchmark_price_col`, `beta_window`, `price_col`, `returns_type`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: residual_return_regression
  params:
    benchmark_price_col: benchmark_close
    beta_window: 100
    price_col: close
    returns_type: simple
    min_periods: <configured>
    raw_fwd_col: <configured>
    benchmark_fwd_col: <configured>
    beta_col: <configured>
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `future_range_regression`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά το συνολικό μελλοντικό high–low εύρος του horizon. Μεγαλύτερη τιμή σημαίνει μεγαλύτερη διαθέσιμη διακύμανση ανεξάρτητα από τελική κατεύθυνση· normalization ως ποσοστό τιμής ή volatility επιτρέπει συγκρίσεις.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `high_col`, `low_col`, `volatility_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `fwd_col`, `label_col`; με προεπιλογή `normalize`, `price_col`, `high_col`, `low_col`, `volatility_col`, `volatility_floor`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: future_range_regression
  params:
    normalize: price
    price_col: close
    high_col: high
    low_col: low
    volatility_col: atr_14
    volatility_floor: 1.0e-12
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `future_realized_volatility`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά την realized volatility των αποδόσεων που ακολουθούν το timestamp t. Υψηλή τιμή σημαίνει ότι το επόμενο horizon ήταν πιο ασταθές και είναι κατάλληλο target για risk forecasting, position sizing ή volatility gating, όχι για άμεση κατεύθυνση.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `periods_per_year`, `clip`; χωρίς ασφαλές καθολικό default `fwd_col`, `label_col`; με προεπιλογή `price_col`, `horizon_bars`, `returns_type`, `annualize`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: future_realized_volatility
  params:
    price_col: close
    horizon_bars: 5
    periods_per_year: <required>
    returns_type: simple
    annualize: false
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `future_drawdown_regression`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά τη χειρότερη μελλοντική adverse κίνηση έναντι της τιμής αναφοράς για long ή short πλευρά. Πιο αρνητική τιμή σημαίνει βαθύτερο αναμενόμενο drawdown· αποτελεί downside-risk label και όχι feature, ακόμη και όταν χρησιμοποιεί ATR γνωστό στο t για normalization.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `high_col`, `low_col`, `volatility_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `clip`; χωρίς ασφαλές καθολικό default `fwd_col`, `label_col`; με προεπιλογή `direction`, `price_col`, `high_col`, `low_col`, `normalize_by_volatility`, `volatility_col`, `volatility_floor`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: future_drawdown_regression
  params:
    direction: long
    price_col: close
    high_col: high
    low_col: low
    normalize_by_volatility: false
    volatility_col: atr_14
    volatility_floor: 1.0e-12
    fwd_col: <configured>
    label_col: <configured>
    clip: <required>
```

### `triple_barrier`

**Τι μετρά και τι πληροφορία δίνει.** Ταξινομεί ποιο από profit, stop ή time barrier επιτυγχάνεται πρώτο στη μελλοντική διαδρομή. Θετικό label σημαίνει profit hit, αρνητικό stop hit και ουδέτερο ή configured label λήξη χρόνου· η same-bar σύγκρουση πρέπει να επιλύεται με ρητή συντηρητική πολιτική.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `candidate_col`, `candidate_out_col`, `event_ret_col`, `fwd_col`, `high_col`, `hit_step_col`, `hit_type_col`, `label_col`, `low_col`, `lower_barrier_col`, `meta_side_col`, `open_col`, `oriented_r_col`, `oriented_ret_col`, `price_col`, `r_col`, `returns_col`, `side_col`, `upper_barrier_col`, `vol_source_col`, `volatility_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `candidate_col`, `label_mode`, `r_clip`, `returns_col`, `side_col`, `volatility_col`; χωρίς ασφαλές καθολικό default `candidate_out_col`, `fwd_col`, `hit_step_col`, `hit_type_col`, `lower_barrier_col`, `lower_mult`, `max_holding`, `meta_side_col`, `oriented_ret_col`, `upper_barrier_col`, `vol_source_col`; με προεπιλογή `add_r_multiple`, `candidate_mode`, `entry_price_mode`, `event_ret_col`, `high_col`, `horizon`, `label_col`, `low_col`, `min_vol`, `neutral_label`, `open_col`, `oriented_r_col`, `price_col`, `r_col`, `tie_break`, `upper_mult`, `vol_window`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: triple_barrier
  params:
    add_r_multiple: false
    candidate_col: <required>
    candidate_mode: all_nonzero
    candidate_out_col: <configured>
    entry_price_mode: current_close
    event_ret_col: tb_event_ret
    fwd_col: <configured>
    high_col: high
    hit_step_col: <configured>
    hit_type_col: <configured>
    horizon: 24
    label_col: label
    label_mode: <required>
    low_col: low
    lower_barrier_col: <configured>
    lower_mult: <configured>
    max_holding: <configured>
    meta_side_col: <configured>
    min_vol: 0.0001
    neutral_label: drop
    open_col: open
    oriented_r_col: tb_oriented_r
    oriented_ret_col: <configured>
    price_col: close
    r_clip: <required>
    r_col: tb_event_r
    returns_col: <required>
    side_col: <required>
    tie_break: closest_to_open
    upper_barrier_col: <configured>
    upper_mult: 2.0
    vol_source_col: <configured>
    vol_window: 24
    volatility_col: <required>
```

### `directional_triple_barrier`

**Τι μετρά και τι πληροφορία δίνει.** Εφαρμόζει triple-barrier labeling προσανατολισμένο στην ήδη γνωστή candidate πλευρά. Επιτυχία σημαίνει κίνηση υπέρ του long ή short candidate και αποτυχία κίνηση προς το stop· non-candidate rows παραμένουν NaN αντί να γίνονται τεχνητά αρνητικά samples.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `candidate_col`, `candidate_out_col`, `direction_col`, `event_ret_col`, `fwd_col`, `high_col`, `hit_step_col`, `hit_type_col`, `label_col`, `low_col`, `lower_barrier_col`, `meta_side_col`, `open_col`, `oriented_r_col`, `oriented_ret_col`, `price_col`, `r_col`, `side_col`, `upper_barrier_col`, `volatility_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `candidate_col`, `candidate_out_col`, `event_ret_col`, `fwd_col`, `high_col`, `hit_step_col`, `hit_type_col`, `label_col`, `low_col`, `lower_barrier_col`, `meta_side_col`, `open_col`, `oriented_r_col`, `oriented_ret_col`, `price_col`, `r_clip`, `r_col`, `side_col`, `upper_barrier_col`, `volatility_col`; χωρίς ασφαλές καθολικό default `direction_col`, `max_holding`, `profit_barrier_r`, `stop_barrier_r`, `vertical_barrier_bars`; με προεπιλογή `add_r_multiple`, `entry_price_mode`, `horizon`, `lower_mult`, `min_vol`, `neutral_label`, `tie_break`, `upper_mult`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: directional_triple_barrier
  params:
    add_r_multiple: false
    candidate_col: <required>
    candidate_out_col: <required>
    direction_col: <configured>
    entry_price_mode: current_close
    event_ret_col: <required>
    fwd_col: <required>
    high_col: <required>
    hit_step_col: <required>
    hit_type_col: <required>
    horizon: 4
    label_col: <required>
    low_col: <required>
    lower_barrier_col: <required>
    lower_mult: 1.0
    max_holding: <configured>
    meta_side_col: <required>
    min_vol: 1.0e-12
    neutral_label: drop
    open_col: <required>
    oriented_r_col: <required>
    oriented_ret_col: <required>
    price_col: <required>
    profit_barrier_r: <configured>
    r_clip: <required>
    r_col: <required>
    side_col: <required>
    stop_barrier_r: <configured>
    tie_break: closest_to_open
    upper_barrier_col: <required>
    upper_mult: 1.4
    vertical_barrier_bars: <configured>
    volatility_col: <required>
```

### `first_passage_barrier_multiclass`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά αν upper, lower ή κανένα ATR barrier αγγίζεται πρώτο μετά το επόμενο εκτελέσιμο bar. Οι τρεις κλάσεις διαχωρίζουν ανοδικό first passage, καθοδικό first passage και no-hit· αμφίσημο διπλό touch στο ίδιο bar αποκλείεται ή επιλύεται από την configured policy.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `atr_col`, `open_col`, `high_col`, `low_col`, `close_col`, `label_col`, `fwd_col`, `intrabar_open_col`, `intrabar_high_col`, `intrabar_low_col`, `time_to_first_hit_col`, `mfe_col`, `mae_col`, `mfe_atr_col`, `mae_atr_col`, `terminal_return_col`, `terminal_return_atr_col`, `upper_distance_col`, `lower_distance_col`, `ambiguous_col`, `intrabar_resolved_col`, `entry_price_col`, `exit_price_col`, `exit_reason_col`, `upper_barrier_col`, `lower_barrier_col`, `eligible_col`, `barrier_cost_ratio_col`, `stop_first_label_col`, `target_first_label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `intrabar_data`; χωρίς ασφαλές καθολικό default `horizon_bars`, `lower_atr_multiplier`, `atr_col`, `intrabar_open_col`, `intrabar_high_col`, `intrabar_low_col`; με προεπιλογή `upper_atr_multiplier`, `atr_period`, `entry_delay_bars`, `entry_price_type`, `ambiguous_policy`, `use_intrabar_resolution`, `minimum_barrier_to_cost_ratio`, `round_trip_cost`, `open_col`, `high_col`, `low_col`, `close_col`, `label_col`, `fwd_col`, `horizon`, `time_to_first_hit_col`, `mfe_col`, `mae_col`, `mfe_atr_col`, `mae_atr_col`, `terminal_return_col`, `terminal_return_atr_col`, `upper_distance_col`, `lower_distance_col`, `ambiguous_col`, `intrabar_resolved_col`, `entry_price_col`, `exit_price_col`, `exit_reason_col`, `upper_barrier_col`, `lower_barrier_col`, `eligible_col`, `barrier_cost_ratio_col`, `stop_first_label_col`, `target_first_label_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: first_passage_barrier_multiclass
  params:
    horizon_bars: <configured>
    upper_atr_multiplier: 1.0
    lower_atr_multiplier: <configured>
    atr_period: 14
    atr_col: <configured>
    entry_delay_bars: 1
    entry_price_type: open
    ambiguous_policy: exclude
    use_intrabar_resolution: false
    minimum_barrier_to_cost_ratio: 0.0
    round_trip_cost: 0.0
    open_col: open
    high_col: high
    low_col: low
    close_col: close
    label_col: first_passage_label
    fwd_col: first_passage_exit_return
    intrabar_open_col: <configured>
    intrabar_high_col: <configured>
    intrabar_low_col: <configured>
    horizon: 12
    time_to_first_hit_col: time_to_first_hit
    mfe_col: mfe
    mae_col: mae
    mfe_atr_col: mfe_atr
    mae_atr_col: mae_atr
    terminal_return_col: terminal_return
    terminal_return_atr_col: terminal_return_atr
    upper_distance_col: upper_distance
    lower_distance_col: lower_distance
    ambiguous_col: ambiguous
    intrabar_resolved_col: intrabar_resolved
    entry_price_col: entry_price
    exit_price_col: exit_price
    exit_reason_col: exit_reason
    upper_barrier_col: upper_barrier
    lower_barrier_col: lower_barrier
    eligible_col: barrier_cost_eligible
    barrier_cost_ratio_col: barrier_cost_ratio
    stop_first_label_col: first_passage_label_stop_first
    target_first_label_col: first_passage_label_target_first
    intrabar_data: <required>
```

### `r_multiple`

**Τι μετρά και τι πληροφορία δίνει.** Προσομοιώνει trade path με profit, stop και time exit και εκφράζει το αποτέλεσμα σε R. Θετικό R σημαίνει κέρδος σε σχέση με το αρχικό risk, -1R πλήρες stop και ενδιάμεση τιμή time exit· οι τιμές εξαρτώνται από entry, tie-break και κόστος.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `bars_held_col`, `candidate_col`, `candidate_out_col`, `entry_price_col`, `exit_price_col`, `exit_reason_col`, `fwd_col`, `high_col`, `hit_step_col`, `hit_type_col`, `label_col`, `low_col`, `open_col`, `oriented_r_col`, `price_col`, `r_col`, `stop_price_col`, `take_profit_price_col`, `trade_r_col`, `volatility_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: χωρίς ασφαλές καθολικό default `max_holding_bars`, `trade_r_col`; με προεπιλογή `allow_partial_horizon`, `bars_held_col`, `candidate_col`, `candidate_out_col`, `entry_price_col`, `entry_price_mode`, `exit_price_col`, `exit_reason_col`, `fwd_col`, `high_col`, `hit_step_col`, `hit_type_col`, `invalid_entry`, `label_col`, `low_col`, `max_holding`, `max_holding_close`, `open_col`, `oriented_r_col`, `price_col`, `r_col`, `side`, `stop_loss`, `stop_loss_r`, `stop_loss_return`, `stop_mode`, `stop_price_col`, `take_profit`, `take_profit_price_col`, `take_profit_r`, `take_profit_return`, `target_r_min`, `tie_break`, `unavailable_tail`, `volatility_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: r_multiple
  params:
    allow_partial_horizon: false
    bars_held_col: r_target_bars_held
    candidate_col: manual_long_signal
    candidate_out_col: r_target_candidate
    entry_price_col: r_target_entry_price
    entry_price_mode: next_open
    exit_price_col: r_target_exit_price
    exit_reason_col: r_target_exit_reason
    fwd_col: r_target_event_ret
    high_col: high
    hit_step_col: r_target_hit_step
    hit_type_col: r_target_hit_type
    invalid_entry: 0
    label_col: label
    low_col: low
    max_holding: 16
    max_holding_bars: <configured>
    max_holding_close: 0
    open_col: open
    oriented_r_col: r_target_oriented_r
    price_col: close
    r_col: r_target_trade_r
    side: long_only
    stop_loss: 0
    stop_loss_r: 1.0
    stop_loss_return: 0.005
    stop_mode: volatility_stop
    stop_price_col: r_target_stop_price
    take_profit: 0
    take_profit_price_col: r_target_take_profit_price
    take_profit_r: 2.0
    take_profit_return: 0.01
    target_r_min: 1.0
    tie_break: conservative
    trade_r_col: <configured>
    unavailable_tail: 0
    volatility_col: vol_rolling_24
```

### `path_dependent_r`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά realized R μόνο για ήδη κατασκευασμένα OOS primary candidates χρησιμοποιώντας την πλήρη μελλοντική trade path. Παράγει gross/net R, MFE, MAE, holding και exit reason· non-candidates και rows χωρίς πλήρη horizon μένουν NaN και η χρήση είναι post-model evaluation ή meta-target.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `candidate_col`, `side_col`, `pred_is_oos_col`, `open_col`, `high_col`, `low_col`, `close_col`, `volatility_col`, `meta_candidate_col`, `meta_side_col`, `entry_price_col`, `exit_price_col`, `exit_reason_col`, `hit_type_col`, `hit_step_col`, `holding_bars_col`, `gross_return_col`, `net_return_col`, `gross_r_col`, `net_r_col`, `mfe_r_col`, `mae_r_col`, `positive_label_col`, `min_025_label_col`, `min_050_label_col`, `min_100_label_col`, `price_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `candidate_col`, `side_col`, `pred_is_oos_col`, `open_col`, `high_col`, `low_col`, `volatility_col`, `meta_candidate_col`, `meta_side_col`, `entry_price_col`, `exit_price_col`, `exit_reason_col`, `hit_type_col`, `hit_step_col`, `holding_bars_col`, `gross_return_col`, `net_return_col`, `gross_r_col`, `net_r_col`, `mfe_r_col`, `mae_r_col`, `positive_label_col`, `min_025_label_col`, `min_050_label_col`, `min_100_label_col`, `price_col`; χωρίς ασφαλές καθολικό default `close_col`, `max_holding_bars`, `cost_per_unit_turnover`, `slippage_per_unit_turnover`; με προεπιλογή `require_oos`, `stop_mode`, `take_profit_r`, `stop_loss_r`, `risk_per_trade`, `entry_price_mode`, `tie_break`, `max_leverage`, `max_holding`, `allow_partial_horizon`, `apply_risk_sizing`, `legacy_same_bar_stop_reason`, `cost_per_turnover`, `slippage_per_turnover`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: path_dependent_r
  params:
    candidate_col: <required>
    side_col: <required>
    pred_is_oos_col: <required>
    require_oos: true
    open_col: <required>
    high_col: <required>
    low_col: <required>
    close_col: <configured>
    volatility_col: <required>
    stop_mode: volatility_stop
    take_profit_r: 5.0
    stop_loss_r: 2.0
    max_holding_bars: <configured>
    risk_per_trade: 0.006
    cost_per_unit_turnover: <configured>
    slippage_per_unit_turnover: <configured>
    entry_price_mode: next_open
    tie_break: conservative
    meta_candidate_col: <required>
    meta_side_col: <required>
    entry_price_col: <required>
    exit_price_col: <required>
    exit_reason_col: <required>
    hit_type_col: <required>
    hit_step_col: <required>
    holding_bars_col: <required>
    gross_return_col: <required>
    net_return_col: <required>
    gross_r_col: <required>
    net_r_col: <required>
    mfe_r_col: <required>
    mae_r_col: <required>
    positive_label_col: <required>
    min_025_label_col: <required>
    min_050_label_col: <required>
    min_100_label_col: <required>
    max_leverage: 1.0
    max_holding: 24
    allow_partial_horizon: false
    apply_risk_sizing: false
    legacy_same_bar_stop_reason: true
    price_col: <required>
    cost_per_turnover: 0.0
    slippage_per_turnover: 0.0
```

### `strategy_path_r`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά MATB outcome με ακριβώς την ίδια entry, stop, trailing, trend-flip, cap και cost πολιτική του production backtest. Το net trade R είναι το κύριο οικονομικό outcome, ενώ gross R, MFE/MAE και exit metadata επιτρέπουν parity audit μεταξύ target construction και στρατηγικής εκτέλεσης.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `candidate_col`, `side_col`, `volatility_col`, `trend_score_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: χωρίς ασφαλές καθολικό default `stop_loss_r`, `cost_per_unit_turnover`, `slippage_per_unit_turnover`; με προεπιλογή `candidate_col`, `side_col`, `volatility_col`, `trend_score_col`, `entry_price_mode`, `emergency_profit_r`, `trailing_activation_r`, `trailing_distance_atr`, `max_holding_bars`, `tie_break`, `strict_bid_ask`, `allow_partial_horizon`, `enforce_single_position`, `entry_delay_bars`, `stop_loss_atr`, `cost_per_turnover`, `slippage_per_turnover`, `overlapping_open_trade`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: strategy_path_r
  params:
    candidate_col: matb_candidate
    side_col: matb_side
    volatility_col: matb_atr
    trend_score_col: matb_trend_score
    entry_price_mode: next_open
    stop_loss_r: <configured>
    emergency_profit_r: 8.0
    trailing_activation_r: 1.5
    trailing_distance_atr: 2.5
    max_holding_bars: 1440
    tie_break: closest_to_open
    strict_bid_ask: true
    allow_partial_horizon: false
    enforce_single_position: true
    entry_delay_bars: 0
    cost_per_unit_turnover: <configured>
    slippage_per_unit_turnover: <configured>
    stop_loss_atr: 2.0
    cost_per_turnover: 0.0
    slippage_per_turnover: 0.0
    overlapping_open_trade: 0
```

### `candidate_expected_r`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά path-dependent R και επιτυχία μόνο στα deterministic candidate rows. Η είσοδος, τα barriers και το timeout προσομοιώνονται από μελλοντικό OHLC· clipped και raw R, excursions και exit reason παρέχουν labels για meta-model και diagnostics.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `candidate_col`, `volatility_col`, `side_col`, `open_col`, `high_col`, `low_col`, `close_col`, `price_col`, `label_col`, `trade_r_col`, `trade_r_clipped_col`, `event_ret_col`, `candidate_out_col`, `entry_price_col`, `exit_price_col`, `stop_price_col`, `take_profit_price_col`, `exit_reason_col`, `bars_held_col`, `hit_type_col`, `hit_step_col`, `mfe_r_col`, `mae_r_col`, `time_to_mfe_col`, `time_to_mae_col`, `fwd_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: χωρίς ασφαλές καθολικό default `event_ret_col`; με προεπιλογή `candidate_col`, `side`, `entry_price_mode`, `volatility_col`, `side_col`, `open_col`, `high_col`, `low_col`, `close_col`, `price_col`, `stop_mode`, `stop_loss_r`, `take_profit_r`, `max_holding_bars`, `target_r_min`, `clip_r`, `tie_break`, `allow_partial_horizon`, `stop_loss_return`, `label_col`, `trade_r_col`, `trade_r_clipped_col`, `candidate_out_col`, `entry_price_col`, `exit_price_col`, `stop_price_col`, `take_profit_price_col`, `exit_reason_col`, `bars_held_col`, `hit_type_col`, `hit_step_col`, `mfe_r_col`, `mae_r_col`, `time_to_mfe_col`, `time_to_mae_col`, `fwd_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: candidate_expected_r
  params:
    candidate_col: signal_candidate
    side: long_only
    entry_price_mode: next_open
    volatility_col: atr_over_price_14
    side_col: signal_side
    open_col: open
    high_col: high
    low_col: low
    close_col: close
    price_col: close
    stop_mode: volatility_stop
    stop_loss_r: 1.5
    take_profit_r: 2.5
    max_holding_bars: 16
    target_r_min: 0.75
    clip_r:
    - -2.0
    - 3.0
    tie_break: conservative
    allow_partial_horizon: false
    stop_loss_return: 0.005
    label_col: label
    trade_r_col: target_trade_r
    trade_r_clipped_col: target_trade_r_clipped
    event_ret_col: <configured>
    candidate_out_col: target_candidate
    entry_price_col: target_entry_price
    exit_price_col: target_exit_price
    stop_price_col: target_stop_price
    take_profit_price_col: target_take_profit_price
    exit_reason_col: target_exit_reason
    bars_held_col: target_bars_held
    hit_type_col: target_hit_type
    hit_step_col: target_hit_step
    mfe_r_col: target_mfe_r
    mae_r_col: target_mae_r
    time_to_mfe_col: target_time_to_mfe
    time_to_mae_col: target_time_to_mae
    fwd_col: target_event_ret
```

### `expected_realized_r`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά το καθαρό realized R candidate trades μετά από κόστη και ολίσθηση. Μεγαλύτερη θετική τιμή σημαίνει καλύτερο οικονομικό αποτέλεσμα μετά friction, αρνητική απώλεια· είναι regression label που διατηρεί περισσότερη πληροφορία από ένα απλό success flag.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `candidate_col`, `side_col`, `volatility_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `fwd_col`, `label_col`; με προεπιλογή `candidate_col`, `side_col`, `volatility_col`, `take_profit_r`, `stop_loss_r`, `max_holding_bars`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: expected_realized_r
  params:
    candidate_col: signal_candidate
    side_col: signal_side
    volatility_col: atr_over_price_14
    take_profit_r: 3.0
    stop_loss_r: 1.5
    max_holding_bars: 16
    fwd_col: <required>
    label_col: <required>
```

### `target_before_stop_probability`

**Τι μετρά και τι πληροφορία δίνει.** Παράγει δυαδικό label για το αν ο στόχος κέρδους επιτυγχάνεται πριν από το stop. Label 1 σημαίνει target-first και 0 stop-first ή μη επιτυχία σύμφωνα με την policy· χρησιμοποιείται για εκπαίδευση probability model πάνω σε πραγματικά candidate events.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `candidate_col`, `side_col`, `volatility_col`, `label_col`, `fwd_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `label_col`, `fwd_col`; με προεπιλογή `candidate_col`, `side_col`, `volatility_col`, `take_profit_r`, `stop_loss_r`, `max_holding_bars`, `tie_break`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: target_before_stop_probability
  params:
    candidate_col: signal_candidate
    side_col: signal_side
    volatility_col: atr_over_price_14
    take_profit_r: 3.0
    stop_loss_r: 1.5
    max_holding_bars: 16
    tie_break: conservative
    label_col: <required>
    fwd_col: <required>
```

### `trade_mfe_mae_regression`

**Τι μετρά και τι πληροφορία δίνει.** Μετρά MFE και MAE σε μονάδες R πάνω στην πλήρη candidate trade path και επιλέγει ένα ως regression output. Το MFE εκφράζει διαθέσιμη ευνοϊκή κίνηση, το MAE δυσμενή excursion και ο συνδυασμός τους βοηθά στην πρόβλεψη payoff quality, stop adequacy και exit design.

**Είσοδοι και έξοδοι.** Το target δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `target_col`, `candidate_col`, `side_col`, `volatility_col`, `fwd_col`, `label_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το target επιτρέπεται να κοιτά τη μελλοντική διαδρομή μόνο κατά την κατασκευή ετικετών. Όλες οι στήλες εξόδου του πρέπει να αποκλείονται από τον πίνακα χαρακτηριστικών, τα signals και την προσαρμογή της προεπεξεργασίας· σειρές χωρίς πλήρες μέλλον πρέπει να διατηρούν `NaN` αντί να μετατρέπονται σε αρνητικά δείγματα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `fwd_col`, `label_col`; με προεπιλογή `target_col`, `candidate_col`, `side_col`, `volatility_col`, `max_holding_bars`.

**Πλήρες YAML παράδειγμα:**

```yaml
target:
  kind: trade_mfe_mae_regression
  params:
    target_col: mfe_r
    candidate_col: signal_candidate
    side_col: signal_side
    volatility_col: atr_over_price_14
    max_holding_bars: 16
    fwd_col: <required>
    label_col: <required>
```
