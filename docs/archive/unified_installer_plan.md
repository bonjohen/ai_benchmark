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
| 1.1 | Completed | 2026-03-30 10:10 PM | 2026-03-30 10:10 PM | Convert `scripts/env.template` — replace all `C:/ai-benchmark` with `{{INSTALL_DIR}}`, hardcoded port `8100` with `{{API_PORT}}`, add `{{INSTANCE_NAME}}` for log prefix comments. Add precedence documentation header per req E4. |
| 1.2 | Completed | 2026-03-30 10:10 PM | 2026-03-30 10:10 PM | Convert `scripts/env.dev.template` — replace `C:/Projects/ai_benchmark` with `{{INSTALL_DIR}}` for consistency with the substitution engine. |
| 1.3 | Completed | 2026-03-30 10:10 PM | 2026-03-30 10:15 PM | Create `scripts/bin/bin_template.bat` — single template with `{{INSTALL_DIR}}` and `{{CLI_COMMAND}}` placeholders, consolidating the 4 nearly-identical bin scripts (`collect.bat`, `run.bat`, `serve.bat`, `backfill.bat`). Log filename uses `{{LOG_PREFIX}}` for per-instance log names (req B5). Keep originals until Phase 6 cleanup. |
| 1.4 | Completed | 2026-03-30 10:15 PM | 2026-03-30 10:25 PM | Create `scripts/installer/module.psm1` — PowerShell module with shared functions: `Invoke-TemplateSubstitution` (reads template, replaces `{{KEY}}` tokens from a hashtable, writes output), `Write-InstallerLog` (appends timestamped entries to `logs\installer_<timestamp>.log` per req F6), `Test-Elevation` (checks admin privileges, suggests `runas` if needed per req F4). |
| 1.5 | Completed | 2026-03-30 10:15 PM | 2026-03-30 10:25 PM | Add pre-flight check functions to `module.psm1` — `Test-PythonVersion` (verifies >= 3.12), `Test-PipAvailable`, `Test-BuildModule`, `Test-DirectoryWritable`, `Test-PortAvailable` (checks registry for port collisions). Per req F1. |
| 1.6 | Completed | 2026-03-30 10:15 PM | 2026-03-30 10:25 PM | Add instance registry functions to `module.psm1` — `Get-InstanceRegistry` (reads/creates `%LOCALAPPDATA%\ai-benchmark\instances.json`), `Set-InstanceEntry` (adds/updates entry), `Remove-InstanceEntry`, `Test-InstanceExists` (prevents duplicate path installs), `Find-InstanceByName` (lookup by name). Registry schema per req B3: name, path, type, version, install_date, last_upgrade_date, api_port, task_name. |
| 1.7 | Completed | 2026-03-30 10:15 PM | 2026-03-30 10:25 PM | Add dry-run infrastructure to `module.psm1` — `$Script:DryRun` flag, `Invoke-InstallerAction` wrapper that logs the action description and either executes or prints "[DRY RUN] would: ..." per req F5. All subsequent subcommands use this wrapper for mutating operations. |
| 1.8 | Completed | 2026-03-30 10:15 PM | 2026-03-30 10:25 PM | Add version tracking functions to `module.psm1` — `Write-VersionJson` (writes `config\version.json` with package_version, install_timestamp, python_version, installer_version), `Read-VersionJson`. Per req C2. |
| 1.9 | Completed | 2026-03-30 10:25 PM | 2026-03-30 10:30 PM | Verify: run `Get-Module -ListAvailable` import test on `module.psm1`. Confirm `Invoke-TemplateSubstitution` correctly replaces tokens in env.template and bin_template.bat with sample values. |
| 1.10 | Completed | 2026-03-30 10:30 PM | 2026-03-30 10:30 PM | Stage all Phase 1 changes. |
| 1.11 | Completed | 2026-03-30 10:30 PM | 2026-03-30 10:30 PM | Commit all Phase 1 changes. |

### Phase 1 Summary

- **Changes:** Templatized `scripts/env.template` (6 `{{INSTALL_DIR}}`, 1 `{{API_PORT}}`, 1 `{{INSTANCE_NAME}}` with precedence documentation header), `scripts/env.dev.template` (2 `{{INSTALL_DIR}}`). Created `scripts/bin/bin_template.bat` (4 placeholders: INSTALL_DIR, CLI_COMMAND, LOG_PREFIX, SCRIPT_DESCRIPTION). Created `scripts/installer/module.psm1` with 18 exported functions across 5 groups (Core, Pre-flight, Registry, Dry-run, Version). All 3 templates verified via automated test script — no unreplaced placeholders. Ruff lint and format clean.
- **Changes hosted at:** `scripts/env.template`, `scripts/env.dev.template`, `scripts/bin/bin_template.bat`, `scripts/installer/module.psm1`
- **Commit:** `Add template placeholders and core installer PowerShell module`

## Phase 2: Install Subcommand

**Goal:** `ai-bench-installer.bat install --path C:\my-instance` creates a fully functional instance: venv, wheel, substituted .env and bin scripts, initialized database, validated config, registered in instance registry. No hardcoded `C:\ai-benchmark` in any installed output.
**Depends on:** Phase 1 (templates and module).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-03-30 10:35 PM | 2026-03-30 10:50 PM | Create `scripts/installer/Install-Instance.ps1` — implements the `install` subcommand. Parameters: `-Path` (required), `-Name` (optional, defaults to directory name per req A5), `-PythonPath` (optional, auto-detect 3.12+ in PATH), `-Port` (optional, default 8100 per req B2), `-TaskTime` (optional, default `05:00` per req B4), `-NoSchedule` (switch, skip task creation). |
| 2.2 | Completed | 2026-03-30 10:35 PM | 2026-03-30 10:50 PM | Implement install steps 1-2 in `Install-Instance.ps1` — run pre-flight checks (Python version, pip, build module, writable directory, no existing instance at path unless `--force` per req F2, port not in use). If not elevated and `-NoSchedule` not set, warn and provide `runas` command (req F4). Create directory structure: `bin/`, `config/`, `data/`, `artifacts/`, `logs/`, `backup/`. |
| 2.3 | Completed | 2026-03-30 10:35 PM | 2026-03-30 10:50 PM | Implement install step 3 — generate `.env` from `env.template` via `Invoke-TemplateSubstitution` with `{{INSTALL_DIR}}` → forward-slash install path, `{{API_PORT}}` → port, `{{INSTANCE_NAME}}` → name. Write to `$Path\config\.env`. Only create if not exists (preserves existing config on `--force` reinstall per req F2). Per reqs A3, E1. |
| 2.4 | Completed | 2026-03-30 10:35 PM | 2026-03-30 10:50 PM | Implement install step 4 — generate bin scripts from `bin_template.bat` via `Invoke-TemplateSubstitution`. Generate 4 variants: `collect.bat` (CLI_COMMAND=`collect`, LOG_PREFIX=`collect_$Name`), `run.bat` (`run`, `daemon_$Name`), `serve.bat` (`eval serve`, `serve_$Name`), `backfill.bat` (`collect --since %~1`, `backfill_$Name`). Write to `$Path\bin\`. Per reqs A2, E2, B5. |
| 2.5 | Completed | 2026-03-30 10:35 PM | 2026-03-30 10:50 PM | Implement install step 5 — create venv at `$Path\venv`, build wheel from source directory, install into venv with `pip install <wheel> --force-reinstall`. Per existing install.ps1 pattern. |
| 2.6 | Completed | 2026-03-30 10:35 PM | 2026-03-30 10:50 PM | Implement install step 6 — initialize database. Set `AI_BENCH_DATABASE_URL` env var from the install path (not hardcoded) and run `venv\Scripts\python.exe -m ai_benchmark.cli init-db`. Per req A4. |
| 2.7 | Completed | 2026-03-30 10:35 PM | 2026-03-30 10:50 PM | Implement install step 7 — run `check-config` validation (req E3). Write `config\version.json` via `Write-VersionJson`. Register instance in registry via `Set-InstanceEntry`. |
| 2.8 | Completed | 2026-03-30 10:35 PM | 2026-03-30 10:50 PM | Implement install step 8 — create scheduled task `AIBenchmark_$Name_Collect` at `-TaskTime` (skip if `-NoSchedule`). Task runs `$Path\bin\collect.bat`. Per req B1. Clean up legacy `AIBenchmarkCollect` task if present (one-time migration). |
| 2.9 | Completed | 2026-03-30 10:50 PM | 2026-03-30 10:55 PM | Create `scripts/ai-bench-installer.bat` — entry point that dispatches to PowerShell. Accepts `install` as first arg, passes remaining args to `Install-Instance.ps1`. Stubs for other subcommands (`upgrade`, `uninstall`, `list`, `status`, `backup`, `dev-setup`) print "not yet implemented". Per req D1 (partial). |
| 2.10 | Completed | 2026-03-30 10:55 PM | 2026-03-30 11:10 PM | Verify: dry-run prints all 8 steps as `[DRY RUN] would:` with no mutations. Real install to `C:\temp\test-ai-bench`: venv created, wheel installed (0.1.0), `.env` has forward-slash paths, bin scripts have backslash `INSTALL_DIR`, `check-config` passes (22 sources, 86 pages), `version.json` written (python 3.14.3), registry entry created. Fixed `$ErrorActionPreference=Stop` + stderr from native commands causing false failures. |
| 2.11 | Completed | 2026-03-30 11:10 PM | 2026-03-30 11:10 PM | Stage all Phase 2 changes. |
| 2.12 | Completed | 2026-03-30 11:10 PM | 2026-03-30 11:10 PM | Commit all Phase 2 changes. |

### Phase 2 Summary

- **Changes:** Created `scripts/installer/Install-Instance.ps1` with 8-step install process (pre-flight, dirs, .env generation, bin script generation, venv+wheel, DB init, bookkeeping, scheduled task). Features: Python auto-detection via `py` launcher, forward/backslash path handling, dry-run mode, `--force` reinstall support, instance-specific task names. Created `scripts/ai-bench-installer.bat` entry point dispatching to PowerShell with install wired and 6 stub subcommands. Fixed `$ErrorActionPreference=Stop` incompatibility with stderr from native commands (build, pip, CLI) by scoping `$ErrorActionPreference=Continue` around external process calls.
- **Changes hosted at:** `scripts/installer/Install-Instance.ps1`, `scripts/ai-bench-installer.bat`, `docs/unified_installer_plan.md`
- **Commit:** `Add install subcommand with instance-aware path substitution`

## Phase 3: Multi-Instance Support & Info Subcommands

**Goal:** Multiple instances can coexist on one machine with unique task names, ports, and log prefixes. `list` and `status` subcommands query the registry and instance state.
**Depends on:** Phase 2 (install subcommand).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-03-30 11:15 PM | 2026-03-30 11:20 PM | Create `scripts/installer/Get-Instances.ps1` — implements `list` subcommand. Reads instance registry, prints table: name, path, type, version, port, task schedule, last upgrade date. Per req D5. |
| 3.2 | Completed | 2026-03-30 11:15 PM | 2026-03-30 11:20 PM | Create `scripts/installer/Get-InstanceStatus.ps1` — implements `status` subcommand. Parameters: `-Path` or `-Name` (identify instance). Displays: version (from `version.json`), database file size, last collection time (newest log file timestamp in `logs/`), scheduled task state (via `schtasks /query`), whether eval server is running on configured port (via `Test-NetConnection`). Per req D6. |
| 3.3 | Completed | 2026-03-30 11:20 PM | 2026-03-30 11:20 PM | Update `ai-bench-installer.bat` — wire `list` and `status` subcommands to their scripts. |
| 3.4 | Completed | 2026-03-30 10:35 PM | 2026-03-30 10:50 PM | Add port collision detection to `Install-Instance.ps1` — already implemented in Phase 2 pre-flight step 1f via `Test-PortAvailable`. |
| 3.5 | Completed | 2026-03-30 11:20 PM | 2026-03-30 11:25 PM | Add schedule stagger suggestion — checks registry for `task_time` collision, suggests 30-min stagger. Added `task_time` field to registry entry. Per req B4. |
| 3.6 | Completed | 2026-03-30 11:25 PM | 2026-03-30 11:30 PM | Verify: installed test instance, `list` shows it with correct table (name, path, type, version, port, task, dates). `status -Name test` shows version info, DB size (64 KB), venv OK, collection logs, task state, eval server port check. Empty registry shows "No instances registered." message. |
| 3.7 | Completed | 2026-03-30 11:30 PM | 2026-03-30 11:30 PM | Stage all Phase 3 changes. |
| 3.8 | Completed | 2026-03-30 11:30 PM | 2026-03-30 11:30 PM | Commit all Phase 3 changes. |

### Phase 3 Summary

- **Changes:** Created `scripts/installer/Get-Instances.ps1` (list subcommand with formatted table output) and `scripts/installer/Get-InstanceStatus.ps1` (status subcommand showing version, DB size, last collection, task state, eval server). Wired both into `ai-bench-installer.bat`. Added schedule stagger suggestion to Install-Instance.ps1 (checks registry for `task_time` collision, suggests 30-min offset). Added `task_time` field to registry entries.
- **Changes hosted at:** `scripts/installer/Get-Instances.ps1`, `scripts/installer/Get-InstanceStatus.ps1`, `scripts/ai-bench-installer.bat`, `scripts/installer/Install-Instance.ps1`, `docs/unified_installer_plan.md`
- **Commit:** `Add list and status subcommands with multi-instance port and schedule management`

## Phase 4: Upgrade Subcommand

**Goal:** `ai-bench-installer.bat upgrade --name prod` performs a full backup → wheel install → migration → config merge → verify → rollback-on-failure upgrade cycle. Existing config and data are preserved.
**Depends on:** Phase 3 (registry lookup by name).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Completed | 2026-03-30 11:35 PM | 2026-03-30 11:50 PM | Create `scripts/installer/Update-Instance.ps1` — implements `upgrade` subcommand. Parameters: `-Path` or `-Name` (identify instance via registry), `-SourceDir` (optional, defaults to project directory containing the installer). Reads current `version.json` to determine installed state. Per req D3. |
| 4.2 | Completed | 2026-03-30 11:35 PM | 2026-03-30 11:50 PM | Implement pre-upgrade backup — create `backup\upgrade_<timestamp>\` directory. Copy: database file, `config\.env`, all files in `bin\`. Per req C1. |
| 4.3 | Completed | 2026-03-30 11:35 PM | 2026-03-30 11:50 PM | Implement wheel build and install — build wheel from `-SourceDir`, install into existing venv with `pip install <wheel> --force-reinstall` (no venv recreation per req C6). Auto-detects system Python via py launcher, falls back to venv Python. |
| 4.4 | Completed | 2026-03-30 11:35 PM | 2026-03-30 11:50 PM | Implement config merge — generates reference .env from template, parses both as key=value, appends missing keys as commented `# NEW in <version>` lines. Never overwrites or reorders existing values. Per req C4. |
| 4.5 | Completed | 2026-03-30 11:35 PM | 2026-03-30 11:50 PM | Implement bin script regeneration — generates to temp dir first, copies into `bin\` on success. Per req F3. |
| 4.6 | Completed | 2026-03-30 11:35 PM | 2026-03-30 12:00 AM | Implement schema migration — detects init-db databases (no alembic_version table) and uses `alembic stamp head` instead of `upgrade head` to avoid "table already exists" errors. For tracked databases, runs `alembic upgrade head`. Per req C3. |
| 4.7 | Completed | 2026-03-30 11:35 PM | 2026-03-30 12:00 AM | Implement post-upgrade verification with rollback — restores DB, .env, and bin scripts from backup on failure. Uses return values instead of `$Script:` scoping for failure tracking. Per req C5. |
| 4.8 | Completed | 2026-03-30 11:35 PM | 2026-03-30 11:50 PM | Implement post-upgrade bookkeeping — `Write-VersionJson` and `Set-InstanceEntry` with version, last_upgrade_date. |
| 4.9 | Completed | 2026-03-30 11:50 PM | 2026-03-30 11:50 PM | Update `ai-bench-installer.bat` — wire `upgrade` subcommand. |
| 4.10 | Completed | 2026-03-30 11:50 PM | 2026-03-30 12:05 AM | Verify: installed test instance, ran upgrade. Backup created (DB + .env + 4 bin scripts), wheel reinstalled, alembic stamped head (init-db database), check-config passed, version.json updated, registry shows last_upgrade_date. Dry-run mode tested. |
| 4.11 | Completed | 2026-03-31 12:05 AM | 2026-03-31 12:05 AM | Stage all Phase 4 changes. |
| 4.12 | Completed | 2026-03-31 12:05 AM | 2026-03-31 12:05 AM | Commit all Phase 4 changes. |

### Phase 4 Summary

- **Changes:** Created `scripts/installer/Update-Instance.ps1` with 7-step upgrade process: instance resolution, pre-upgrade backup (DB + .env + bin scripts to `backup\upgrade_<timestamp>\`), wheel build+install, config merge (appends new keys as commented lines), atomic bin script regeneration, schema migration (detects init-db databases and stamps instead of migrating), and post-upgrade verification with rollback on failure. Fixed two issues: (1) init-db databases lack alembic_version table, causing `upgrade head` to fail with "table already exists" — solved by checking for alembic_version and using `stamp head` for untracked databases; (2) `$Script:` variable scoping inside `Invoke-InstallerAction` scriptblocks — solved by using return values. Wired upgrade subcommand into `ai-bench-installer.bat`.
- **Changes hosted at:** `scripts/installer/Update-Instance.ps1`, `scripts/ai-bench-installer.bat`, `docs/unified_installer_plan.md`
- **Commit:** `Add upgrade subcommand with backup, migration, config merge, and rollback`

## Phase 5: Uninstall, Backup, Dev-Setup Subcommands

**Goal:** All remaining subcommands (`uninstall`, `backup`, `dev-setup`) are implemented. The unified entry point handles all 7 subcommands. Old scripts are superseded.
**Depends on:** Phase 4 (upgrade subcommand).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1 | Completed | 2026-03-30 11:45 PM | 2026-03-30 11:50 PM | Create `scripts/installer/Uninstall-Instance.ps1` — implements `uninstall` subcommand. Parameters: `-Path` or `-Name`, `-KeepData` (switch, preserves `data/` and `backup/`), `-Purge` (switch, deletes entire directory). Removes scheduled task (`schtasks /delete`), deregisters from registry. Without `-Purge`, removes venv, bin, config but keeps data. Per req D4. |
| 5.2 | Completed | 2026-03-30 11:50 PM | 2026-03-30 11:55 PM | Create `scripts/installer/Backup-Instance.ps1` — implements `backup` subcommand. Parameters: `-Path` or `-Name`, `-RetainCount` (default 10). Copies database to `backup\ai_benchmark_<timestamp>.db`, rotates old backups. Reuses logic from existing `backup.ps1` but resolves instance path from registry. Per req D7. |
| 5.3 | Completed | 2026-03-30 11:55 PM | 2026-03-31 12:00 AM | Create `scripts/installer/Setup-Dev.ps1` — implements `dev-setup` subcommand. Runs from project directory: `pip install -e ".[dev]"`, generates `.env` from `env.dev.template` via `Invoke-TemplateSubstitution` (with `{{INSTALL_DIR}}` → project path), runs `init-db`, registers as `dev` type instance in registry. Per reqs D8, G2. |
| 5.4 | Completed | 2026-03-31 12:00 AM | 2026-03-31 12:05 AM | Finalize `scripts/ai-bench-installer.bat` — wire all 7 subcommands: `install`, `upgrade`, `uninstall`, `list`, `status`, `backup`, `dev-setup`. Add `--help` output listing subcommands and brief descriptions. Add `--dry-run` global flag forwarded to all subcommands. Per req D1. |
| 5.5 | Completed | 2026-03-31 12:05 AM | 2026-03-31 12:05 AM | Verify: syntax check on all three new PowerShell scripts (Uninstall-Instance.ps1, Backup-Instance.ps1, Setup-Dev.ps1) — all pass. Dispatcher verified with all 7 subcommands wired. |
| 5.6 | Completed | 2026-03-31 12:05 AM | 2026-03-31 12:10 AM | Stage all Phase 5 changes. |
| 5.7 | Completed | 2026-03-31 12:10 AM | 2026-03-31 12:10 AM | Commit all Phase 5 changes. |

### Phase 5 Summary

- **Changes:** Created `scripts/installer/Uninstall-Instance.ps1` (selective removal with `-KeepData`/`-Purge`, scheduled task cleanup, registry deregistration), `scripts/installer/Backup-Instance.ps1` (timestamped DB backup with rotation), `scripts/installer/Setup-Dev.ps1` (editable install, .env from dev template, init-db, dev registry entry). Wired all 7 subcommands in `scripts/ai-bench-installer.bat` — no more stubs.
- **Changes hosted at:** TBD
- **Commit:** `Add uninstall, backup, and dev-setup subcommands; finalize unified entry point`

## Phase 6: Developer Workflow & Python Accommodations

**Goal:** `serve-compare` works from the registry. Dev instances are first-class in list/status. The two Python-side accommodations (eval serve port, explicit .env path) are implemented. Old scripts are documented as deprecated.
**Depends on:** Phase 5 (all subcommands).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 6.1 | Completed | 2026-03-31 12:20 AM | 2026-03-31 12:25 AM | Add `serve-compare` support to `ai-bench-installer.bat` — accepts `--instances prod,dev` (or two names). Reads paths and ports from registry. Launches two `cmd /c start` windows running each instance's `serve.bat`. Opens both URLs in browser. Replaces hardcoded `scripts/serve_both.bat`. Per req G1. |
| 6.2 | Completed | 2026-03-31 12:25 AM | 2026-03-31 12:30 AM | Add cross-instance database comparison to `module.psm1` — `Compare-InstanceDatabases` function. Accepts two instance names/paths, runs `SELECT name, COUNT(*) FROM sqlite_master ...` style queries via venv Python against both databases, prints table row-count diff. Per req G3. Wire as `ai-bench-installer.bat compare --instances prod,dev`. |
| 6.3 | Completed | 2026-03-31 12:15 AM | 2026-03-31 12:20 AM | Python accommodation 1 — modify `ai_benchmark/eval/cli/commands.py` eval `serve` command: change `--port` default from hardcoded `8100` to `EvalSettings().api_port` so `.env` port is respected without explicit `--port` flag. Per design §6 item 1. |
| 6.4 | Completed | 2026-03-31 12:10 AM | 2026-03-31 12:15 AM | Python accommodation 2 — add `AI_BENCH_ENV_FILE` support to `PipelineSettings` and `EvalSettings` in `ai_benchmark/config/settings.py` and `ai_benchmark/eval/config.py`. If env var is set, use it as `env_file` path instead of CWD-relative `.env`. Per design §6 item 2. |
| 6.5 | Completed | 2026-03-31 12:15 AM | 2026-03-31 12:15 AM | Update bin scripts template (`bin_template.bat`) — set `AI_BENCH_ENV_FILE={{INSTALL_DIR}}\config\.env` before invoking Python, so settings load explicitly from the instance config rather than relying on `cd /d` working directory. |
| 6.6 | Completed | 2026-03-31 12:35 AM | 2026-03-31 12:40 AM | Run `pytest -x -v` — full suite green after Python-side changes. Run `ruff check ai_benchmark/ tests/` and `ruff format --check ai_benchmark/ tests/` — clean. |
| 6.7 | Completed | 2026-03-31 12:30 AM | 2026-03-31 12:35 AM | Add deprecation notice to old scripts — prepend comment block to `scripts/install.ps1`, `scripts/install.bat`, `scripts/deploy.ps1`, `scripts/deploy.bat`, `scripts/backup.ps1`, `scripts/backup.bat`, `scripts/setup_dev.bat`, `scripts/serve_both.bat` noting they are superseded by `ai-bench-installer.bat` and will be removed in a future release. Do not delete yet. |
| 6.8 | Completed | 2026-03-31 12:35 AM | 2026-03-31 12:35 AM | Update `CLAUDE.md` Deployment section — document `ai-bench-installer.bat` subcommands, instance registry location, template mechanism, and the two Python-side changes. Keep old script references with "(deprecated)" annotation. |
| 6.9 | Completed | 2026-03-31 12:40 AM | 2026-03-31 12:40 AM | Stage all Phase 6 changes. |
| 6.10 | Completed | 2026-03-31 12:40 AM | 2026-03-31 12:40 AM | Commit all Phase 6 changes. |

### Phase 6 Summary

- **Changes:** Created `scripts/installer/Serve-Compare.ps1` (registry-driven dual eval server launcher) and `scripts/installer/Compare-Instances.ps1` (database row-count diff). Added `Compare-InstanceDatabases` to `module.psm1`. Python: `AI_BENCH_ENV_FILE` env var support in `PipelineSettings` and `EvalSettings` (`settings.py`, `eval/config.py`). Eval serve port/host defaults now read from `EvalSettings` (`commands.py`). `bin_template.bat` sets `AI_BENCH_ENV_FILE`. Deprecation notices on 8 old scripts. `CLAUDE.md` Deployment section updated. `ai-bench-installer.bat` now dispatches all 9 subcommands.
- **Changes hosted at:** TBD
- **Commit:** `Add serve-compare, Python accommodations, deprecate old scripts, update docs`
