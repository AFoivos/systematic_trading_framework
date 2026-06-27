# Local Repository MCP Server

This repository includes a Dockerized Model Context Protocol (MCP) server that exposes only this repository to ChatGPT.

The server is tool-only. It does not provide a widget. It mounts the repository at `/workspace` inside the container and resolves every requested path against that root. Absolute paths and symlinks that escape `/workspace` are rejected.

## Security Model

- The Docker Compose service mounts the repository read-only.
- Tools can read files, search code, inspect git state, read experiment artifacts, read configs, read logs, and inspect Optuna SQLite databases in read-only mode.
- There is no arbitrary shell tool.
- Git tools use fixed `git` argument lists and never mutate the repository.
- Python script execution is allowlisted in `mcp_server/mcp-config.yaml` and additionally requires `confirmation="RUN_APPROVED_REPOSITORY_SCRIPT"`.
- The server exposes no directory outside the repository volume.

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

Git:

- `git_status`
- `git_diff`
- `git_log`
- `git_current_branch`

Project utilities:

- `list_experiment_runs`
- `read_experiment_result`
- `read_optuna_database`
- `read_config`
- `read_log`
- `execute_approved_python_script`

## Run With Docker Compose

Build and start the server:

```bash
docker compose up --build mcp
```

The MCP endpoint is:

```text
http://localhost:8765/mcp
```

For ChatGPT Developer Mode, expose the local endpoint through your preferred HTTPS tunnel and register the `/mcp` URL as a remote MCP server. Keep the tunnel pointed only at the MCP service port.

## Configuration

The server reads:

```text
mcp_server/mcp-config.yaml
```

Important fields:

- `limits.max_read_bytes`: maximum bytes returned by file-like reads.
- `limits.max_search_results`: maximum search results.
- `limits.max_tree_entries`: maximum tree/listing entries.
- `approved_python_scripts`: repository-relative Python scripts that can be run after explicit confirmation.

To add future tools, add a focused module under `mcp_server/repo_mcp/`, import the handler in `server.py`, and register it with `@mcp.tool()`.
