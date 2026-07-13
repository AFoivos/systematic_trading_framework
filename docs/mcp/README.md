# Τοπικός MCP server του repository

Τελευταία ενημέρωση: 2026-07-11

Το repository περιλαμβάνει Dockerized Model Context Protocol server για
ελεγχόμενη ανάγνωση, επιθεώρηση και, μετά από ρητή επιβεβαίωση, μεταβολή του
workspace. Το repository προσαρτάται ως `/workspace` και το streamable HTTP
endpoint είναι `/mcp`.

## Εκκίνηση

```bash
docker compose up -d --build mcp
docker compose logs -f mcp
```

Endpoint:

```text
http://127.0.0.1:8765/mcp
```

Για απομακρυσμένο client απαιτείται ελεγχόμενο HTTPS tunnel προς τη θύρα 8765.
Το tunnel δεν πρέπει να εκθέτει άλλες τοπικές υπηρεσίες.

## Όρια paths

- Όλα τα repository paths επιλύονται ως σχετικά προς `/workspace`.
- Absolute paths, path traversal και symlinks που διαφεύγουν από το root
  απορρίπτονται.
- Οι path mutation tools δεν μπορούν να μεταβάλουν `.git`.
- Secret-like paths όπως `.env`, `*.pem`, `*.key`, `id_rsa` και
  `id_ed25519` απορρίπτονται από write/delete/move operations.
- Το `git push` δεν εκτίθεται ως MCP tool.

## Επιβεβαιώσεις

Οι write, delete, shell, experiment και git-write tools απαιτούν:

```text
confirmation="RUN_FULL_ACCESS_REPOSITORY_ACTION"
```

Το allowlisted Python runner απαιτεί:

```text
confirmation="RUN_APPROVED_REPOSITORY_SCRIPT"
```

Το pytest helper απαιτεί:

```text
confirmation="RUN_APPROVED_REPOSITORY_TESTS"
```

Η ύπαρξη token δεν αποτελεί από μόνη της εξουσιοδότηση. Ο caller πρέπει να έχει
λάβει ρητή έγκριση για τη συγκεκριμένη μεταβολή ή εκτέλεση.

## Read-only εργαλεία

- Repository: `search`, `fetch`, `list_directory`, `read_file`,
  `search_files`, `search_code`, `search_symbols`, `find_references`,
  `read_project_tree`.
- Git: `git_status`, `git_diff`, `git_log`, `git_current_branch`.
- Artifacts/configs: `list_experiment_runs`, `read_experiment_result`,
  `read_optuna_database`, `read_config`, `read_log`.
- Introspection: `repo_overview_summary`, `registry_inventory`,
  `inspect_component`, `docs_registry_sync_check`, `inspect_config`,
  `feature_lineage`, `leakage_audit_config`,
  `target_signal_compatibility_check`, `list_recent_runs_with_metrics`,
  `compare_experiment_runs`, `review_current_changes` και
  `suggest_tests_for_change`.

## Εργαλεία μεταβολής και εκτέλεσης

- Αρχεία: `write_file`, `append_file`, `apply_patch`, `delete_path`,
  `move_path`.
- Commands: `run_shell_command`, `run_experiment`,
  `execute_approved_python_script`, `run_pytest`.
- Git: `git_add`, `git_commit`, `git_checkout_new_branch`, `git_restore`.

Το `run_experiment` δέχεται μόνο config κάτω από `config/experiments/` και
εκτελεί:

```bash
python -m src.experiments.runner <config_path>
```

Επιστρέφει stdout, stderr, return code, timeout status και, όταν εντοπιστεί,
το νέο run directory.

## Configuration

Το `mcp_server/mcp-config.yaml` ορίζει:

- `limits.max_read_bytes`,
- `limits.max_search_results`,
- `limits.max_tree_entries`,
- `limits.script_timeout_seconds`,
- τα `full_access.*` gates και timeouts,
- τη λίστα `approved_python_scripts`.

Environment overrides: `MCP_REPO_ROOT`, `MCP_CONFIG_PATH`, `MCP_HOST` και
`MCP_PORT`.

## Tests

```bash
python -m pytest -q mcp_server/tests
```

Οι tool definitions βρίσκονται στο `mcp_server/repo_mcp/server.py`.
