# Unified Installer — Implementation Plan

**Source document:** `docs/unified_installer_design.md`

## Work Queue Instructions

### State Transitions

Open  ──>  Started  ──>  Completed
              │
              └──>  Blocked  ──>  Started  ──>  Completed

- **Open**: Not yet begun.
- **Started**: Actively in progress. Record the start datetime (PST).
- **Completed**: Done and verified. Record the completion datetime (PST).
- **Blocked**: Cannot proceed; note the blocker in the description.

### Commit Protocol

1. Work through all tasks in a phase.
2. When every task reaches Completed, write the Phase Summary.
3. Stage and commit all changes for the phase. Do not push.
4. Proceed immediately to the next phase.

## Technology Stack (Additive)

| Concern | Choice |
|---|---|
| Installer language | PowerShell 5.1+ (Windows built-in) |
| Entry point | `ai-bench-installer.bat` dispatching to PowerShell |
| Template substitution | PowerShell `-replace` with `{{TOKEN}}` placeholders |
| Instance registry | JSON at `%LOCALAPPDATA%\ai-benchmark\instances.json` |
| Version tracking | `config\version.json` per instance |
| Wheel build | `python -m build --wheel` (existing hatchling backend) |
| Schema migration | `alembic upgrade head` (existing infrastructure) |

## Phase 1: Template Infrastructure & Core Module

**Goal:** Bin scripts and env templates use `{{PLACEHOLDER}}` tokens instead of hardcoded paths. A PowerShell module provides shared utility functions (substitution, logging, pre-flight checks, registry I/O) used by all subsequent subcommands.
**Depends on:** Nothing (first phase).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1 | Open | | | Convert `scripts/env.template` — replace all `C:/ai-benchmark` with `{{INSTALL_DIR}}`, hardcoded port `8100` with `{{API_PORT}}`, add `{{INSTANCE_NAME}}` for log prefix comments. Add precedence documentation header per req E4. |
| 1.2 | Open | | | Convert `scripts/env.dev.template` — replace `C:/Projects/ai_benchmark` with `{{INSTALL_DIR}}` for consistency with the substitution engine. |
| 1.3 | Open | | | Create `scripts/bin/bin_template.bat` — single template with `{{INSTALL_DIR}}` and `{{CLI_COMMAND}}` placeholders, consolidating the 4 nearly-identical bin scripts (`collect.bat`, `run.bat`, `serve.bat`, `backfill.bat`). Log filename uses `{{LOG_PREFIX}}` for per-instance log names (req B5). Keep originals until Phase 6 cleanup. |
| 1.4 | Open | | | Create `scripts/installer/module.psm1` — PowerShell module with shared functions: `Invoke-TemplateSubstitution` (reads template, replaces `{{KEY}}` tokens from a hashtable, writes output), `Write-InstallerLog` (appends timestamped entries to `logs\installer_<timestamp>.log` per req F6), `Test-Elevation` (checks admin privileges, suggests `runas` if needed per req F4). |
| 1.5 | Open | | | Add pre-flight check functions to `module.psm1` — `Test-PythonVersion` (verifies >= 3.12), `Test-PipAvailable`, `Test-BuildModule`, `Test-DirectoryWritable`, `Test-PortAvailable` (checks registry for port collisions). Per req F1. |
| 1.6 | Open | | | Add instance registry functions to `module.psm1` — `Get-InstanceRegistry` (reads/creates `%LOCALAPPDATA%\ai-benchmark\instances.json`), `Set-InstanceEntry` (adds/updates entry), `Remove-InstanceEntry`, `Test-InstanceExists` (prevents duplicate path installs), `Find-InstanceByName` (lookup by name). Registry schema per req B3: name, path, type, version, install_date, last_upgrade_date, api_port, task_name. |
| 1.7 | Open | | | Add dry-run infrastructure to `module.psm1` — `$Script:DryRun` flag, `Invoke-InstallerAction` wrapper that logs the action description and either executes or prints "[DRY RUN] would: ..." per req F5. All subsequent subcommands use this wrapper for mutating operations. |
| 1.8 | Open | | | Add version tracking functions to `module.psm1` — `Write-VersionJson` (writes `config\version.json` with package_version, install_timestamp, python_version, installer_version), `Read-VersionJson`. Per req C2. |
| 1.9 | Open | | | Verify: run `Get-Module -ListAvailable` import test on `module.psm1`. Confirm `Invoke-TemplateSubstitution` correctly replaces tokens in env.template and bin_template.bat with sample values. |
| 1.10 | Open | | | Stage all Phase 1 changes. |
| 1.11 | Open | | | Commit all Phase 1 changes. |

### Phase 1 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add template placeholders and core installer PowerShell module`

## Phase 2: Install Subcommand

**Goal:** `ai-bench-installer.bat install --path C:\my-instance` creates a fully functional instance: venv, wheel, substituted .env and bin scripts, initialized database, validated config, registered in instance registry. No hardcoded `C:\ai-benchmark` in any installed output.
**Depends on:** Phase 1 (templates and module).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Open | | | Create `scripts/installer/Install-Instance.ps1` — implements the `install` subcommand. Parameters: `-Path` (required), `-Name` (optional, defaults to directory name per req A5), `-PythonPath` (optional, auto-detect 3.12+ in PATH), `-Port` (optional, default 8100 per req B2), `-TaskTime` (optional, default `05:00` per req B4), `-NoSchedule` (switch, skip task creation). |
| 2.2 | Open | | | Implement install steps 1-2 in `Install-Instance.ps1` — run pre-flight checks (Python version, pip, build module, writable directory, no existing instance at path unless `--force` per req F2, port not in use). If not elevated and `-NoSchedule` not set, warn and provide `runas` command (req F4). Create directory structure: `bin/`, `config/`, `data/`, `artifacts/`, `logs/`, `backup/`. |
| 2.3 | Open | | | Implement install step 3 — generate `.env` from `env.template` via `Invoke-TemplateSubstitution` with `{{INSTALL_DIR}}` → forward-slash install path, `{{API_PORT}}` → port, `{{INSTANCE_NAME}}` → name. Write to `$Path\config\.env`. Only create if not exists (preserves existing config on `--force` reinstall per req F2). Per reqs A3, E1. |
| 2.4 | Open | | | Implement install step 4 — generate bin scripts from `bin_template.bat` via `Invoke-TemplateSubstitution`. Generate 4 variants: `collect.bat` (CLI_COMMAND=`collect`, LOG_PREFIX=`collect_$Name`), `run.bat` (`run`, `daemon_$Name`), `serve.bat` (`eval serve`, `serve_$Name`), `backfill.bat` (`collect --since %1`, `backfill_$Name`). Write to `$Path\bin\`. Per reqs A2, E2, B5. |
| 2.5 | Open | | | Implement install step 5 — create venv at `$Path\venv`, build wheel from source directory, install into venv with `pip install <wheel> --force-reinstall`. Per existing install.ps1 pattern. |
| 2.6 | Open | | | Implement install step 6 — initialize database. Set `AI_BENCH_DATABASE_URL` env var from the install path (not hardcoded) and run `venv\Scripts\python.exe -m ai_benchmark.cli init-db`. Per req A4. |
| 2.7 | Open | | | Implement install step 7 — run `check-config` validation (req E3). Write `config\version.json` via `Write-VersionJson`. Register instance in registry via `Set-InstanceEntry`. |
| 2.8 | Open | | | Implement install step 8 — create scheduled task `AIBenchmark_$Name_Collect` at `-TaskTime` (skip if `-NoSchedule`). Task runs `$Path\bin\collect.bat`. Per req B1. Clean up legacy `AIBenchmarkCollect` task if present (one-time migration). |
| 2.9 | Open | | | Create `scripts/ai-bench-installer.bat` — entry point that dispatches to PowerShell. Accepts `install` as first arg, passes remaining args to `Install-Instance.ps1`. Stubs for other subcommands (`upgrade`, `uninstall`, `list`, `status`, `backup`, `dev-setup`) print "not yet implemented". Per req D1 (partial). |
| 2.10 | Open | | | Verify: run `ai-bench-installer.bat install --path C:\temp\test-instance --no-schedule` from project root. Confirm: venv created, wheel installed, `.env` has correct paths (no `C:\ai-benchmark`), bin scripts have correct `INSTALL_DIR`, `check-config` passes, `version.json` written, registry entry created. Run with `--dry-run` and confirm no mutations. |
| 2.11 | Open | | | Stage all Phase 2 changes. |
| 2.12 | Open | | | Commit all Phase 2 changes. |

### Phase 2 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add install subcommand with instance-aware path substitution`

## Phase 3: Multi-Instance Support & Info Subcommands

**Goal:** Multiple instances can coexist on one machine with unique task names, ports, and log prefixes. `list` and `status` subcommands query the registry and instance state.
**Depends on:** Phase 2 (install subcommand).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Open | | | Create `scripts/installer/Get-Instances.ps1` — implements `list` subcommand. Reads instance registry, prints table: name, path, type, version, port, task schedule, last upgrade date. Per req D5. |
| 3.2 | Open | | | Create `scripts/installer/Get-InstanceStatus.ps1` — implements `status` subcommand. Parameters: `-Path` or `-Name` (identify instance). Displays: version (from `version.json`), database file size, last collection time (newest log file timestamp in `logs/`), scheduled task state (via `schtasks /query`), whether eval server is running on configured port (via `Test-NetConnection`). Per req D6. |
| 3.3 | Open | | | Update `ai-bench-installer.bat` — wire `list` and `status` subcommands to their scripts. |
| 3.4 | Open | | | Add port collision detection to `Install-Instance.ps1` — before install, check registry for existing instance using the same port. Warn and refuse unless `--force`. Per req B3 collision prevention. |
| 3.5 | Open | | | Add schedule stagger suggestion — when `-TaskTime` is default `05:00` and another instance already uses `05:00`, suggest a staggered time (e.g., `05:30`) to avoid concurrent API rate-limit issues. Per req B4. |
| 3.6 | Open | | | Verify: install two instances to different paths with different names and ports. Run `list` — both appear. Run `status` on each — correct version, DB size, task state. Confirm task names are unique (`AIBenchmark_<name>_Collect`). Confirm `.env` files have different ports. |
| 3.7 | Open | | | Stage all Phase 3 changes. |
| 3.8 | Open | | | Commit all Phase 3 changes. |

### Phase 3 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add list and status subcommands with multi-instance port and schedule management`

## Phase 4: Upgrade Subcommand

**Goal:** `ai-bench-installer.bat upgrade --name prod` performs a full backup → wheel install → migration → config merge → verify → rollback-on-failure upgrade cycle. Existing config and data are preserved.
**Depends on:** Phase 3 (registry lookup by name).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Open | | | Create `scripts/installer/Update-Instance.ps1` — implements `upgrade` subcommand. Parameters: `-Path` or `-Name` (identify instance via registry), `-SourceDir` (optional, defaults to project directory containing the installer). Reads current `version.json` to determine installed state. Per req D3. |
| 4.2 | Open | | | Implement pre-upgrade backup — create `backup\upgrade_<timestamp>\` directory. Copy: database file, `config\.env`, all files in `bin\`. Per req C1 (current deploy scripts only back up DB, not config or bin scripts). |
| 4.3 | Open | | | Implement wheel build and install — build wheel from `-SourceDir`, install into existing venv with `pip install <wheel> --force-reinstall` (no venv recreation per req C6). Use venv Python for build if available, fall back to system Python. |
| 4.4 | Open | | | Implement config merge — compare new `env.template` (after substitution) with existing `config\.env`. For each key in template but absent from existing config: append as commented-out line with default value and `# NEW in <version>` annotation. Never overwrite or reorder existing values. Per req C4. |
| 4.5 | Open | | | Implement bin script regeneration — generate new bin scripts from `bin_template.bat` to a temp directory. If all succeed, rename into `bin\` replacing old scripts. If any step fails, old scripts remain untouched. Per req F3 (atomic bin script updates). |
| 4.6 | Open | | | Implement schema migration — run `venv\Scripts\python.exe -m alembic upgrade head` with `AI_BENCH_DATABASE_URL` set from instance `.env`. Per req C3. The alembic infrastructure already exists in `alembic/env.py`. |
| 4.7 | Open | | | Implement post-upgrade verification — run `check-config`. If non-zero exit or alembic migration failed: restore database, `.env`, and bin scripts from `backup\upgrade_<timestamp>\`. Report what was rolled back. Per req C5. |
| 4.8 | Open | | | Implement post-upgrade bookkeeping — update `config\version.json` via `Write-VersionJson`. Update registry entry via `Set-InstanceEntry` (version, last_upgrade_date). |
| 4.9 | Open | | | Update `ai-bench-installer.bat` — wire `upgrade` subcommand. |
| 4.10 | Open | | | Verify: install an instance, manually remove a setting from `.env`, run upgrade. Confirm: backup created (DB + .env + bin scripts), wheel reinstalled, missing setting appended as comment, `version.json` updated, registry updated. Simulate failure (rename DB mid-upgrade) and confirm rollback restores all three backup targets. |
| 4.11 | Open | | | Stage all Phase 4 changes. |
| 4.12 | Open | | | Commit all Phase 4 changes. |

### Phase 4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add upgrade subcommand with backup, migration, config merge, and rollback`

## Phase 5: Uninstall, Backup, Dev-Setup Subcommands

**Goal:** All remaining subcommands (`uninstall`, `backup`, `dev-setup`) are implemented. The unified entry point handles all 7 subcommands. Old scripts are superseded.
**Depends on:** Phase 4 (upgrade subcommand).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1 | Open | | | Create `scripts/installer/Uninstall-Instance.ps1` — implements `uninstall` subcommand. Parameters: `-Path` or `-Name`, `-KeepData` (switch, preserves `data/` and `backup/`), `-Purge` (switch, deletes entire directory). Removes scheduled task (`schtasks /delete`), deregisters from registry. Without `-Purge`, removes venv, bin, config but keeps data. Per req D4. |
| 5.2 | Open | | | Create `scripts/installer/Backup-Instance.ps1` — implements `backup` subcommand. Parameters: `-Path` or `-Name`, `-RetainCount` (default 10). Copies database to `backup\ai_benchmark_<timestamp>.db`, rotates old backups. Reuses logic from existing `backup.ps1` but resolves instance path from registry. Per req D7. |
| 5.3 | Open | | | Create `scripts/installer/Setup-Dev.ps1` — implements `dev-setup` subcommand. Runs from project directory: `pip install -e ".[dev]"`, generates `.env` from `env.dev.template` via `Invoke-TemplateSubstitution` (with `{{INSTALL_DIR}}` → project path), runs `init-db`, registers as `dev` type instance in registry. Per reqs D8, G2. |
| 5.4 | Open | | | Finalize `scripts/ai-bench-installer.bat` — wire all 7 subcommands: `install`, `upgrade`, `uninstall`, `list`, `status`, `backup`, `dev-setup`. Add `--help` output listing subcommands and brief descriptions. Add `--dry-run` global flag forwarded to all subcommands. Per req D1. |
| 5.5 | Open | | | Verify: run `dev-setup` from project root — editable install, `.env` created, DB initialized, registry shows dev instance. Run `backup --name dev` — backup created, rotation works. Run `uninstall --name dev --keep-data` — venv gone, data preserved, registry entry removed. Run `uninstall` on a production test instance with `--purge` — directory deleted. |
| 5.6 | Open | | | Stage all Phase 5 changes. |
| 5.7 | Open | | | Commit all Phase 5 changes. |

### Phase 5 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add uninstall, backup, and dev-setup subcommands; finalize unified entry point`

## Phase 6: Developer Workflow & Python Accommodations

**Goal:** `serve-compare` works from the registry. Dev instances are first-class in list/status. The two Python-side accommodations (eval serve port, explicit .env path) are implemented. Old scripts are documented as deprecated.
**Depends on:** Phase 5 (all subcommands).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 6.1 | Open | | | Add `serve-compare` support to `ai-bench-installer.bat` — accepts `--instances prod,dev` (or two names). Reads paths and ports from registry. Launches two `cmd /c start` windows running each instance's `serve.bat`. Opens both URLs in browser. Replaces hardcoded `scripts/serve_both.bat`. Per req G1. |
| 6.2 | Open | | | Add cross-instance database comparison to `module.psm1` — `Compare-InstanceDatabases` function. Accepts two instance names/paths, runs `SELECT name, COUNT(*) FROM sqlite_master ...` style queries via venv Python against both databases, prints table row-count diff. Per req G3. Wire as `ai-bench-installer.bat compare --instances prod,dev`. |
| 6.3 | Open | | | Python accommodation 1 — modify `ai_benchmark/eval/cli/commands.py` eval `serve` command: change `--port` default from hardcoded `8100` to `EvalSettings().api_port` so `.env` port is respected without explicit `--port` flag. Per design §6 item 1. |
| 6.4 | Open | | | Python accommodation 2 — add `AI_BENCH_ENV_FILE` support to `PipelineSettings` and `EvalSettings` in `ai_benchmark/config/settings.py` and `ai_benchmark/eval/config.py`. If env var is set, use it as `env_file` path instead of CWD-relative `.env`. Per design §6 item 2. |
| 6.5 | Open | | | Update bin scripts template (`bin_template.bat`) — set `AI_BENCH_ENV_FILE={{INSTALL_DIR}}\config\.env` before invoking Python, so settings load explicitly from the instance config rather than relying on `cd /d` working directory. |
| 6.6 | Open | | | Run `pytest -x -v` — full suite green after Python-side changes. Run `ruff check ai_benchmark/ tests/` and `ruff format --check ai_benchmark/ tests/` — clean. |
| 6.7 | Open | | | Add deprecation notice to old scripts — prepend comment block to `scripts/install.ps1`, `scripts/install.bat`, `scripts/deploy.ps1`, `scripts/deploy.bat`, `scripts/backup.ps1`, `scripts/backup.bat`, `scripts/setup_dev.bat`, `scripts/serve_both.bat` noting they are superseded by `ai-bench-installer.bat` and will be removed in a future release. Do not delete yet. |
| 6.8 | Open | | | Update `CLAUDE.md` Deployment section — document `ai-bench-installer.bat` subcommands, instance registry location, template mechanism, and the two Python-side changes. Keep old script references with "(deprecated)" annotation. |
| 6.9 | Open | | | Stage all Phase 6 changes. |
| 6.10 | Open | | | Commit all Phase 6 changes. |

### Phase 6 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add serve-compare, Python accommodations, deprecate old scripts, update docs`
