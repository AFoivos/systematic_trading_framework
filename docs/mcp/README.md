# Systematic Trading Framework MCP server

This server provides bounded source inspection and Git review tools. Normal source
inspection avoids market data, logs, reports, artifacts, generated models,
virtual environments, caches, binary files, and sensitive files.

## Fast review workflow

1. Call mcp_health and confirm server_version, implementation_build_id,
   git_available, and git_worktree_valid.
2. Call get_repo_snapshot(include_untracked=false).
3. Call get_code_review_bundle() for safe uncommitted source changes.
4. Call read_files for selected files.
5. Call search_source or legacy search_code(root=".") for symbols.

For the fastest Git status in a large worktree, call
list_changed_paths(include_untracked=false). File-level review uses Git
untracked-files=all with source-policy exclusions.

## Scan policy

Top-level heavy/generated roots are excluded only when they are the first
repository-relative component:

- data, logs, reports, artifacts, tmp, models

Thus models/checkpoint.bin is excluded, while src/models/registry.py and
tests/models/test_model.py are searched.

The following directories are excluded wherever they occur:

- .git, node_modules, __pycache__, .pytest_cache, .mypy_cache,
  .ruff_cache, htmlcov, dist, build, site-packages, .ipynb_checkpoints
- virtual environments matching .venv, .venv*, venv, venv*, or env;
  this includes .venv312 and .venv_map

Normal source search also excludes CSV, columnar, database, model, archive,
and log extensions. To explicitly inspect permitted data-like text, specify
both the root and an include glob:

~~~text
search_source(query="field", roots=["data"], include_globs=["*.csv"])
~~~

Direct tools retain their intended uses: read_log, read_experiment_result, and
read_optuna_database do not use the normal source scan policy. Bulk/review
tools skip .env, .env.*, certificate/key files, credentials.json,
secrets.json, id_rsa, and id_ed25519.

## Fast tools

~~~text
search_source(
  query, roots=None, include_globs=None, exclude_globs=None,
  max_results=100, context_lines=1, time_budget_ms=3000, cursor=None,
)

stat_files(paths, include_git_status=false)

read_files(
  paths, start_line=None, max_lines_per_file=500,
  max_bytes_per_file=100000, total_max_bytes=1000000,
)

list_changed_paths(
  include_untracked=true, include_ignored=false,
  pathspecs=None, max_paths=1000, cursor=None,
)

git_diff(
  path=None, max_bytes=None, paths=None, mode="unified",
  include_untracked=false, context_lines=3, cursor=None,
)

read_changed_files(
  include_modified=true, include_untracked=true, include_deleted=false,
  include_docs=false, include_tests=true, include_configs=true,
  extensions=None, max_files=200, max_bytes_per_file=150000,
  total_max_bytes=3000000, cursor=None,
)
~~~

The default source roots are src, tests, config, scripts, and docs. The initial
metadata-only index builds lazily and incrementally within the search budget; it
has a 30-second TTL. Repeated default searches reuse it. Legacy
search_code(root=".") uses that same index. A source-search cursor preserves
the exact file and next-line position, so a page ending mid-file neither
duplicates nor loses matches.

stat_files uses one bounded Git status query for the whole batch when Git status
is requested. read_files enforces per-file and total limits; sha256 and
returned_content_sha256 describe only returned bytes, so it never reads the
rest of a large file merely to hash it. Binary files, including NUL-containing
CSV or JSON files, are not dumped.

list_changed_paths preserves real porcelain v1 status codes and returns
modified, added, untracked, deleted, renamed, copied, conflicted, and (when
requested) ignored groups. Rename entries include old from_path and new path.

read_changed_files and get_code_review_bundle enumerate reviewable untracked
source directories file by file. They exclude generated roots, binary files,
and sensitive paths before reading content. git_diff preserves legacy path
arguments and unified/stat/name-only modes. Unified pagination is by file and
then complete UTF-8 lines, never arbitrary byte slices; Git-state fingerprints
reject stale continuations.

~~~text
get_repo_snapshot(
  include_changed_paths=true, include_diff_stat=true,
  include_untracked=false, include_recent_commits=false,
  recent_commit_count=5,
)

get_code_review_bundle(
  scope="uncommitted", include_new_files=true,
  include_modified_diffs=true, include_related_tests=true,
  include_related_configs=true, include_docs=false,
  max_total_bytes=3000000, cursor=None,
)
~~~

Git responses expose git_available, git_worktree_valid, bounded error/stderr,
branch, detached-head state, and clean state. A non-Git root or Git failure
returns unknown branch/clean/detached values rather than claiming a clean
detached repository.

The review bundle captures one Git-state fingerprint, uses it for snapshot and
changed-file collection, then verifies it before returning. A working-tree
change during collection is reported as status="stale".

mcp_health does not traverse the repository or build/refresh the source index.
It reports process start time, server version, implementation path,
implementation build ID, index state, and a cheap structural Git
executable/worktree check. Git-backed tools perform the authoritative Git probe
before returning repository state.
mcp_diagnostics reports bounded tool metrics, source-index refresh count, and
cache hits/misses.

## Partial results and cursors

Large operations return completed items with status="partial", truncated=true,
and an opaque next_cursor. Cursors are process-local, time-limited,
size-bounded, parameter-fingerprinted, and contain no unrestricted absolute
paths or result bodies. Malformed, expired, or stale cursors raise a clear
validation error.

Repository paths accept Windows or POSIX separators. Absolute paths, drive
paths, root escapes, and symlinks escaping the repository are rejected. Git
uses argument arrays, explicit hard timeouts, and never uses shell=True.

## Compatibility

No existing public tool was removed or renamed. Existing clients can still use
git_status, git_diff, list_directory, read_file, search, search_code,
search_files, search_symbols, find_references, read_project_tree, read_config,
read_log, read_experiment_result, and read_optuna_database.

## Validation and synthetic benchmark

~~~powershell
python -m pytest -q mcp_server/tests
python mcp_server/scripts/benchmark_fast_tools.py
~~~

The synthetic benchmark measures health, cold/warm hit-heavy source search,
backward-compatible search_code, a full no-match search, bulk reads, changed
paths, snapshot, and review bundle. It verifies that src/models is included
while root models, .venv312, and .venv_map are excluded.

## Deployment and client refresh

The MCP Docker image copies mcp_server into /app at image build time. Editing
host MCP source files does not update an already running MCP process or its tool
schema. After MCP implementation changes, manually rebuild/recreate the service
and reconnect or refresh the MCP client:

~~~powershell
docker compose up -d --build --force-recreate mcp
~~~

This command is documented for the operator to run manually; it is not run by
the MCP implementation workflow.

After deployment:

1. Call mcp_health and confirm the new version/build ID.
2. Confirm new tool schemas are visible in the client.
3. Call get_repo_snapshot.
4. Call get_code_review_bundle.
5. Call read_files.
6. Call search_source.
