# Local Repository MCP Server

This repository includes a Dockerized Model Context Protocol (MCP) server for ChatGPT repository work.

The server mounts the repository at `/workspace` inside the container. All repository path arguments are resolved against that root. Absolute paths, path traversal, and symlinks that escape `/workspace` are rejected.

## Rebuild And Restart

```bash
docker compose up -d --build mcp
```

The MCP endpoint is:

```text
http://localhost:8765/mcp
```

For ChatGPT Developer Mode, expose the local endpoint through your preferred HTTPS tunnel and register the `/mcp` URL as a remote MCP server. Keep the tunnel pointed only at the MCP service port.

## Full-Access Confirmation

Write, delete, shell, experiment, and git-write tools require:

```text
confirmation="RUN_FULL_ACCESS_REPOSITORY_ACTION"
```

The legacy allowlisted Python script runner still requires:

```text
confirmation="RUN_APPROVED_REPOSITORY_SCRIPT"
```

The pytest helper still requires:

```text
confirmation="RUN_APPROVED_REPOSITORY_TESTS"
```

## Tools

Repository exploration:

- `search`
- `fetch`
- `list_directory`
- `read_file`
- `search_files`
- `search_code`
- `search_symbols`
- `find_references`
- `read_project_tree`

File mutation:

- `write_file`
- `append_file`
- `apply_patch`
- `delete_path`
- `move_path`

Commands and experiments:

- `run_shell_command`
- `run_experiment`
- `run_pytest`
- `execute_approved_python_script`

Git:

- `git_status`
- `git_diff`
- `git_log`
- `git_current_branch`
- `git_add`
- `git_commit`
- `git_checkout_new_branch`
- `git_restore`

Project utilities:

- `list_experiment_runs`
- `read_experiment_result`
- `read_optuna_database`
- `read_config`
- `read_log`
- repository introspection and leakage-audit helpers exposed by `server.py`

## Running Experiments Through MCP

Use `run_experiment` for experiment configs under:

```text
config/experiments/
```

The tool runs:

```bash
python -m src.experiments.runner <config_path>
```

It returns stdout, stderr, return code, timeout status, and a detected created run directory when an artifact manifest appears under `logs/`.

## Safety Boundaries

- All file and cwd paths are scoped to `/workspace`.
- Absolute paths are rejected.
- Path traversal outside the repository is rejected.
- Deleting the repository root is rejected.
- Deleting or mutating `.git` through path tools is rejected.
- Writes, deletes, moves, patches, and git path operations reject obvious secret-like paths:
  - `.env`
  - `.env.*`
  - `*.pem`
  - `*.key`
  - `id_rsa`
  - `id_ed25519`
- `git push` is intentionally not exposed.

## Configuration

The server reads:

```text
mcp_server/mcp-config.yaml
```

Important fields:

- `limits.max_read_bytes`: maximum bytes returned by file-like reads.
- `limits.max_search_results`: maximum search results.
- `limits.max_tree_entries`: maximum tree/listing entries.
- `full_access`: full-access capability gates, confirmation token, timeouts, and output limits.
- `approved_python_scripts`: repository-relative Python scripts that can be run by `execute_approved_python_script`.
