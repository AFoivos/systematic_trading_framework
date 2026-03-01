## 13. Scaling Strategy

### 13.1 Τρέχον Scaling Model

Το τρέχον σύστημα είναι κατάλληλο για low-to-medium scale research workloads: λίγα έως δεκάδες assets, daily ή
moderate frequency data, single-host execution και artifact persistence σε local filesystem. Η architecture είναι
modular αλλά όχι ακόμη distributed.

### 13.2 Ποια Σημεία Κλιμακώνονται Ομαλά

- Η per-asset feature/model pipeline μπορεί να παραλληλοποιηθεί εύκολα, επειδή κάθε asset επεξεργάζεται ανεξάρτητα μέχρι το portfolio alignment stage.
- Το snapshot storage είναι deterministic και άρα επιδέχεται migration σε object store χωρίς αλλαγή contract.
- Τα evaluation metrics λειτουργούν πάνω σε generic Series/DataFrames, άρα scale horizontally με batch processing.

### 13.3 Πού Θα Εμφανιστεί Bottleneck

- Στο `runner.py`, επειδή ο orchestration layer κάνει πολλά responsibilities σε ένα process.
- Στο `build_rolling_covariance_by_date()` για μεγάλο αριθμό assets και μεγάλα windows.
- Στο `optimize_mean_variance()` όταν μεγαλώνει ο αριθμός assets και constraints.
- Στο pandas-based long-format snapshot persistence για μεγάλα intraday panels.

### 13.4 Προτεινόμενη Στρατηγική Κλιμάκωσης

1. Asset-level parallelism πριν από portfolio alignment.
2. Μεταφορά raw/processed snapshots σε parquet/object store με partitioning ανά dataset/run/asset.
3. Εισαγωγή feature store metadata layer αν το feature space μεγαλώσει σημαντικά.
4. Cache warm-up και covariance incremental updates αντί για πλήρη recomputation ανά ημερομηνία.
5. Αν το universe φτάσει υψηλές διαστάσεις, αντικατάσταση SLSQP με optimizer ειδικά σχεδιασμένο για sparse or factor-constrained portfolios.
