# Unified Installer Design Document

## 1. Purpose

The ai_benchmark project needs a unified installer that supports arbitrary install paths, multiple concurrent instances on one machine, and in-place upgrades that preserve configuration and data. The current scripts hardcode `C:\ai-benchmark` throughout bin scripts, environment templates, and utility scripts, making all three requirements impossible without manual editing.

## 2. Scope

This document specifies the feature set for a unified installer. The scope is limited to the scripts layer (`scripts/`) and the `.env` template mechanism. It does not require changes to the Python package itself (`ai_benchmark/`), though it identifies two minor Python-side accommodations that would be beneficial. The installer is Windows-only (matching the project's deployment target). It replaces the current seven separate scripts (`install.ps1/bat`, `deploy.ps1/bat`, `backup.ps1/bat`, `setup_dev.bat`) with a single entry point.

## 3. Root Cause Analysis

Three structural problems in the current scripts prevent the user's requirements:

**Custom install paths break at runtime.** The four bin scripts (`collect.bat`, `run.bat`, `serve.bat`, `backfill.bat`) all contain `set INSTALL_DIR=C:\ai-benchmark` on line 8. The install scripts copy these files verbatim into the target directory. After installation, the bin scripts ignore the actual directory they are in and always reference `C:\ai-benchmark`. The `env.template` hardcodes six path references to `C:/ai-benchmark/`. The `install.ps1` line 143 hardcodes the database URL for `init-db`.

**Multiple instances collide.** The scheduled task name is always `AIBenchmarkCollect`. The eval server port is always 8100. There is no namespace or differentiator per instance, so installing a second instance overwrites the first's scheduled task and two instances cannot serve simultaneously.

**Upgrades are incomplete.** The deploy scripts back up the database but not the `.env` config file. They do not run alembic migrations. They do not track what version is installed. There is no rollback mechanism if an upgrade fails. New `.env` keys introduced in a version update are silently absent from the existing config.

## 4. What Already Works

The existing infrastructure provides a solid foundation:

- `install.ps1/bat` accept `InstallDir` and `PythonPath` as parameters
- `deploy.ps1/bat` accept `InstallDir` parameter
- `backup.ps1/bat` accept `InstallDir` and `RetainCount` parameters
- Wheel build (`python -m build --wheel`) with hatchling backend is clean
- Venv creation and non-editable wheel install into venv works
- `PipelineSettings` and `EvalSettings` load from `.env` and environment variables with `extra="ignore"`
- `alembic/env.py` reads the database URL from `PipelineSettings` (respects `.env`)
- `check-config` CLI command validates the installation

## 5. Functional Requirements

### 5.1 Instance-Aware Installation

**A1. User-specified install path.** The installer accepts a target directory as its primary argument. All generated files, scripts, and configs must use this path. No hardcoded `C:\ai-benchmark` may appear anywhere in the installed output.

**A2. Bin script path resolution at install time.** During installation, the installer rewrites the `INSTALL_DIR=` line in each bin script to the actual install path before copying. The four bin scripts in the repository become templates with a `{{INSTALL_DIR}}` placeholder. The installer substitutes the chosen path when copying to the target. This is more reliable than runtime path discovery because Windows Task Scheduler does not set a reliable working directory.

**A3. Template path substitution for .env.** During installation, the installer performs path substitution on `env.template` before writing `config\.env`. Every occurrence of `C:/ai-benchmark` is replaced with the forward-slash form of the install path. This covers `AI_BENCH_DATABASE_URL`, `AI_BENCH_EVAL_DATABASE_URL`, and `AI_BENCH_EVAL_ARTIFACT_STORAGE_PATH`.

**A4. Install-time database URL.** The `init-db` step uses the correct database URL derived from the install path, not a hardcoded string.

**A5. Instance name.** Each installation accepts an optional short name (e.g., `prod`, `staging`, `experiment-3`). Defaults to the directory name. Used for scheduled task naming, log prefixes, and the instance registry.

### 5.2 Multi-Instance Support

**B1. Unique scheduled task names.** The scheduled task name incorporates the instance name: `AIBenchmark_<name>_Collect` instead of the fixed `AIBenchmarkCollect`. Install and uninstall operations manage only their own task.

**B2. Configurable API port.** The installer accepts an API port parameter (default 8100). Written into `.env` as `AI_BENCH_EVAL_API_PORT`. The `serve.bat` bin script reads from `.env` rather than relying on the hardcoded default.

**B3. Instance registry.** A machine-global JSON file at `%LOCALAPPDATA%\ai-benchmark\instances.json` records: instance name, install path, instance type (`production` or `dev`), version installed, install date, last upgrade date, API port, and task name. The installer writes an entry on install, updates on upgrade, and removes on uninstall. The registry is advisory, not authoritative: if the file is deleted, instances still function; they just cannot be enumerated centrally. The registry also prevents accidentally installing two instances to the same path and detects port collisions.

**B4. Configurable collection schedule.** The installer accepts a collection time parameter (default `05:00`). Two instances should not default to the same collection time to avoid API rate-limit doubling (a problem documented in the dev/prod interaction design, section 4.4, where concurrent Semantic Scholar queries caused 429 errors).

**B5. Per-instance log prefixes.** The instance name appears in the log filename (e.g., `collect_staging_20260330_050000.log`) so that centralized log collection can distinguish sources.

### 5.3 In-Place Upgrades

**C1. Pre-upgrade backup.** Before any upgrade, automatically back up: (a) the SQLite database, (b) the `.env` config file, (c) the current bin scripts. Backups go to `backup\upgrade_<timestamp>\`. The current deploy scripts back up the database but not the config.

**C2. Version tracking.** Write a `config\version.json` file during install and upgrade containing: package version (from wheel metadata), install timestamp, Python version, and installer script version. The upgrade process reads this to determine the current state.

**C3. Schema migration.** After installing the new wheel, run `alembic upgrade head` from within the venv against the instance's database. The database URL is read from the instance's `.env`. The alembic infrastructure already exists and works. The current deploy scripts do not run migrations, so adding a new column in an upgrade silently breaks the application.

**C4. Config merge.** When a new version ships with new `.env` keys, the upgrade process: (a) identifies keys present in the new template but absent from the existing `.env`, (b) appends them as commented-out lines with their defaults, (c) never overwrites or reorders existing user values. Users should not lose API keys or custom settings, and should not need to manually diff templates.

**C5. Rollback on failure.** After a failed upgrade (detected by `check-config` returning non-zero or alembic migration failure), automatically restore from the pre-upgrade backup. Report what was rolled back.

**C6. Upgrade without recreating venv.** Use `pip install <wheel> --force-reinstall` (which the current deploy scripts already do correctly). The venv itself is not recreated unless the Python version changes.

### 5.4 Unified Command Interface

**D1. Single entry point.** One script (`ai-bench-installer.bat` dispatching to a PowerShell implementation) with subcommands: `install`, `upgrade`, `uninstall`, `list`, `status`, `backup`, `dev-setup`. Replaces the current seven separate scripts.

**D2. `install` subcommand.** Creates a new instance. Parameters: `--path` (required), `--name` (optional), `--python` (optional, default: find Python 3.12+ in PATH), `--port` (optional, default: 8100), `--task-time` (optional, default: 05:00), `--no-schedule` (skip task creation).

**D3. `upgrade` subcommand.** Upgrades an existing instance. Parameters: `--path` or `--name` (identify instance), `--source` (optional, defaults to the project directory containing the installer). Runs the full backup-install-migrate-merge-verify-rollback sequence.

**D4. `uninstall` subcommand.** Removes an instance. Parameters: `--path` or `--name`, `--keep-data` (preserves `data/` and `backup/`). Removes scheduled task, deregisters from instance registry. Does not delete the directory unless `--purge` is specified.

**D5. `list` subcommand.** Prints a table of all registered instances: name, path, type, version, port, task schedule, last upgrade date.

**D6. `status` subcommand.** For a specific instance: version, database size, last collection time (from logs), scheduled task state, whether the eval server is running on the configured port.

**D7. `backup` subcommand.** Backs up a specific instance's database with rotation. Parameters: `--path` or `--name`, `--retain` (default: 10).

**D8. `dev-setup` subcommand.** Sets up a development environment at the current project directory. Installs editable mode with dev extras, creates `.env` from `env.dev.template`, runs `init-db`. Registers as a `dev` instance in the registry.

### 5.5 Configuration Management

**E1. Template variable substitution.** The `.env` template uses placeholder tokens (`{{INSTALL_DIR}}`, `{{API_PORT}}`, `{{INSTANCE_NAME}}`) instead of hardcoded paths. The installer substitutes these at install time. The resulting `.env` is a plain file with no template syntax remaining.

**E2. Bin script template generation.** The four bin scripts in the repository are collapsed into a single template (`scripts/bin/bin_template.bat`) with `{{INSTALL_DIR}}` and `{{CLI_COMMAND}}` placeholders. The installer generates all four variants. This eliminates duplication across four nearly-identical files and removes the hardcoded path problem at its source.

**E3. Config validation on install.** After writing `.env` and initializing the database, run `check-config` to verify the installation. Report the result clearly. The deploy scripts already do this; the install scripts should as well.

**E4. Precedence documentation in .env.** The installed `.env` includes comments explaining the precedence order (environment variable > `.env` file > default) and that all settings can be overridden via env vars with the `AI_BENCH_` prefix.

### 5.6 Operational Safety

**F1. Pre-flight checks.** Before installing: verify Python version >= 3.12, verify `pip` and `build` module availability, verify target directory is writable, verify no existing instance at that path (unless `--force`), verify chosen port is not in use by another registered instance.

**F2. Idempotent install.** Running `install` against an existing instance path (without `--force`) refuses and suggests `upgrade` instead. Running `install --force` behaves like a fresh install but preserves `config\.env` and `data\`.

**F3. Atomic bin script updates.** During upgrade, write new bin scripts to a temp location, then rename into place. If any step fails, the old scripts remain functional.

**F4. Elevation check.** The installer checks for admin privileges (needed for `schtasks`). If not elevated, provides the `runas` command to use. If `--no-schedule` is passed, elevation is not required.

**F5. Dry-run mode.** A `--dry-run` flag prints every action without executing. Useful for sysadmins previewing changes on production machines.

**F6. Installer operation log.** The installer writes a log to `%INSTALL_DIR%\logs\installer_<timestamp>.log` capturing every step, parameter, and outcome for post-mortem debugging.

### 5.7 Developer Workflow Integration

**G1. Serve-compare from registry.** Replace the hardcoded `serve_both.bat` with an installer subcommand (e.g., `ai-bench-installer serve-compare --instances prod,dev`) that reads paths and ports from the registry.

**G2. Dev as first-class instance type.** The registry distinguishes `production` instances (wheel install, venv) from `dev` instances (editable install, no venv). The `list` and `status` commands show both. Dev instances use `env.dev.template` with DEBUG logging and console format.

**G3. Cross-instance database comparison.** A convenience command that reports row counts per table for two instances, highlighting differences. Useful during development to verify a dev instance produces the same data as production.

## 6. Python-Side Accommodations

Two minor changes to the Python package would improve the installer experience but are not strictly required:

1. **`eval serve` port default.** The `--port` Click option in `eval/cli/commands.py:487` hardcodes `default=8100`. It should read from `EvalSettings().api_port` so that the port configured in `.env` is respected without passing `--port` explicitly. This lets the bin script `serve.bat` invoke `eval serve` without arguments and get the correct port.

2. **Explicit .env path.** Bin scripts currently `cd /d %INSTALL_DIR%` so that Pydantic finds `.env` in CWD. An `AI_BENCH_ENV_FILE` environment variable that `PipelineSettings` and `EvalSettings` read would make the config path explicit rather than CWD-dependent.

## 7. Out of Scope

- Changes to the Python package's CLI, models, or core logic
- Linux/macOS support (project is Windows-only)
- GUI installer
- Remote deployment or orchestration
- Docker/container packaging
