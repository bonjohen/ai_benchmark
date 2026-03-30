# Dev/Production Isolation — Implementation Plan

**Source document:** `docs/dev_prod_interaction_design.md`

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
| Production venv | `C:\Python314\python.exe -m venv C:\ai-benchmark\venv` |
| Wheel build | `python -m build --wheel` (v1.4.0, hatchling backend) |
| Backup | `Copy-Item` / `copy` (native OS, SQLite single-file) |
| Scheduled tasks | `schtasks` (batch) / `Register-ScheduledTask` (PowerShell) |

---

## Phase 1: Production Virtual Environment and Non-Editable Install

**Goal:** Production runs inside its own venv at `C:\ai-benchmark\venv` with a non-editable wheel install. Dev code changes no longer go live in production. Bin scripts use the venv Python. A deploy script provides the ongoing dev-to-prod workflow. Resolves interactions 4.1 (editable install), 4.2 (shared CLI), 4.3 (no venv), 4.7 (installer coupling).
**Depends on:** Nothing (first phase).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-03-30 10:30 AM | 2026-03-30 10:32 AM | Update `scripts/install.ps1` step [4/6]: Replace `pip install -e .` with (a) create venv `& $PythonPath -m venv "$InstallDir\venv"`, (b) build wheel `& $PythonPath -m build --wheel --outdir "$InstallDir\venv\tmp" $SourceDir`, (c) install wheel into venv `& "$InstallDir\venv\Scripts\pip.exe" install (Get-ChildItem "$InstallDir\venv\tmp\*.whl") --force-reinstall`, (d) clean up tmp. Update step [5/6] to use `$InstallDir\venv\Scripts\python.exe` for init-db. |
| 1.2 | Completed | 2026-03-30 10:32 AM | 2026-03-30 10:34 AM | Update `scripts/install.bat` step [4/6]: Mirror 1.1 in batch syntax — `%PYTHON% -m venv "%INSTALL_DIR%\venv"`, build wheel, install into venv with `"%INSTALL_DIR%\venv\Scripts\pip.exe"`, cleanup. Update step [5/6] to use venv Python for init-db. |
| 1.3 | Completed | 2026-03-30 10:34 AM | 2026-03-30 10:35 AM | Update all four bin scripts (`scripts/bin/collect.bat`, `run.bat`, `serve.bat`, `backfill.bat`): Change `set PYTHON=C:\Python314\python.exe` to `set PYTHON=%INSTALL_DIR%\venv\Scripts\python.exe` |
| 1.4 | Completed | 2026-03-30 10:35 AM | 2026-03-30 10:38 AM | Create `scripts/deploy.ps1` — upgrade script for ongoing deployments. Steps: (a) validate `$InstallDir\venv` exists, (b) back up production database, (c) build wheel from `$SourceDir`, (d) install wheel into venv with `--force-reinstall`, (e) copy updated bin scripts, (f) run `& "$InstallDir\venv\Scripts\python.exe" -m ai_benchmark.cli check-config` to verify |
| 1.5 | Completed | 2026-03-30 10:38 AM | 2026-03-30 10:39 AM | Create `scripts/deploy.bat` — batch version of deploy script with same steps |
| 1.6 | Completed | 2026-03-30 10:39 AM | 2026-03-30 10:40 AM | Verify `python -m build --wheel` succeeds in `C:\Projects\ai_benchmark` and produces a valid `.whl` file (306 KB, ai_benchmark-0.1.0-py3-none-any.whl). |
| 1.7 | Completed | 2026-03-30 10:40 AM | 2026-03-30 10:40 AM | Stage all Phase 1 changes |
| 1.8 | Completed | 2026-03-30 10:40 AM | 2026-03-30 10:40 AM | Commit all Phase 1 changes |

### Phase 1 Summary

- **Changes:** Updated `install.ps1` and `install.bat` to create venv, build wheel, and install non-editable into `$InstallDir\venv`. Updated all 4 bin scripts to use `%INSTALL_DIR%\venv\Scripts\python.exe`. Created `deploy.ps1` and `deploy.bat` for ongoing dev-to-prod deployments with backup, wheel build, and verification.
- **Changes hosted at:** `scripts/install.ps1`, `scripts/install.bat`, `scripts/bin/collect.bat`, `scripts/bin/run.bat`, `scripts/bin/serve.bat`, `scripts/bin/backfill.bat`, `scripts/deploy.ps1`, `scripts/deploy.bat`
- **Commit:** `Phase 1: Add production venv isolation with wheel-based deployment`

---

## Phase 2: Scheduled Task Consolidation

**Goal:** Only one scheduled collection runs at 5:00 AM. The `daily_collect.ps1` targets production (not dev) and runs at 06:00 for analysis/summary only. Duplicate API rate-limit exposure is eliminated. Resolves interactions 4.4 (concurrent tasks) and 4.5 (daily_collect.ps1 targets dev).
**Depends on:** Phase 1 (bin scripts reference venv Python).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-03-30 10:42 AM | 2026-03-30 10:44 AM | Update `scripts/daily_collect.ps1`: Change `$ProjectDir = "C:\Projects\ai_benchmark"` to `$InstallDir = "C:\ai-benchmark"`. Update log paths. Update Claude Code prompt to skip `collect` and run `status` + `analyze digest`. Use venv Python. Load .env for database URL. |
| 2.2 | Completed | 2026-03-30 10:44 AM | 2026-03-30 10:46 AM | Update `scripts/install.ps1` step [6/6]: Add `Unregister-ScheduledTask -TaskName "AI Benchmark Daily Collection"` to remove stale task. Add commented-out optional analysis task registration at 06:00. |
| 2.3 | Completed | 2026-03-30 10:46 AM | 2026-03-30 10:47 AM | Update `scripts/install.bat` step [6/6]: Add `schtasks /delete /tn "AI Benchmark Daily Collection" /f` to remove stale task. |
| 2.4 | Completed | 2026-03-30 10:47 AM | 2026-03-30 10:47 AM | Added commented-out optional Claude Code analysis task registration at 06:00 in install.ps1 with instructions to enable. |
| 2.5 | Completed | 2026-03-30 10:47 AM | 2026-03-30 10:47 AM | Stage all Phase 2 changes |
| 2.6 | Completed | 2026-03-30 10:47 AM | 2026-03-30 10:47 AM | Commit all Phase 2 changes |

### Phase 2 Summary

- **Changes:** Rewrote `daily_collect.ps1` to target production (`C:\ai-benchmark`) and run analysis-only (status + digest, no collect). Updated `install.ps1` to remove stale `AI Benchmark Daily Collection` task and added commented-out optional analysis task at 06:00. Updated `install.bat` to delete stale task.
- **Changes hosted at:** `scripts/daily_collect.ps1`, `scripts/install.ps1`, `scripts/install.bat`
- **Commit:** `Phase 2: Consolidate scheduled tasks and retarget daily_collect.ps1`

---

## Phase 3: Database Safety Guards

**Goal:** Dev and production databases are protected by structural guards. Dev has an explicit `.env` with absolute database path. `PipelineSettings` and `EvalSettings` warn on relative default. Alembic reads from `PipelineSettings` instead of hardcoded `alembic.ini`. Resolves interaction 4.6 (database isolation by convention).
**Depends on:** Phase 1 (production `.env` already uses absolute paths; this phase addresses dev side).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-03-30 10:49 AM | 2026-03-30 10:49 AM | Create `scripts/env.dev.template` — template for dev `.env` with `AI_BENCH_DATABASE_URL=sqlite+aiosqlite:///C:/Projects/ai_benchmark/ai_benchmark.db`, `AI_BENCH_LOG_FORMAT=console`, `AI_BENCH_LOG_LEVEL=DEBUG` |
| 3.2 | Completed | 2026-03-30 10:49 AM | 2026-03-30 10:49 AM | Create `C:\Projects\ai_benchmark\.env` from the template (file is gitignored). This makes the dev database path explicit rather than CWD-dependent. |
| 3.3 | Completed | 2026-03-30 10:49 AM | 2026-03-30 10:50 AM | Update `ai_benchmark/config/settings.py`: Add a `model_validator(mode="after")` to `PipelineSettings` that logs a `structlog` warning if `database_url` equals the bare relative default `sqlite+aiosqlite:///ai_benchmark.db` — warns developers who forget to create `.env`. Added `extra="ignore"` so shared `.env` files work. |
| 3.4 | Completed | 2026-03-30 10:50 AM | 2026-03-30 10:51 AM | Update `ai_benchmark/eval/config.py`: Add `env_file=".env"`, `env_file_encoding="utf-8"`, and `extra="ignore"` to `EvalSettings.model_config` so eval settings load from `.env`. Add same relative-path warning validator as 3.3. |
| 3.5 | Completed | 2026-03-30 10:51 AM | 2026-03-30 10:51 AM | Update `alembic/env.py`: Import `PipelineSettings`, read `database_url` from `PipelineSettings()`, and override `config.set_main_option("sqlalchemy.url", ...)` so alembic uses the same database as the application (respecting `.env` and env vars). Add comment in `alembic.ini` noting the URL is overridden at runtime. |
| 3.6 | Completed | 2026-03-30 10:51 AM | 2026-03-30 10:53 AM | Add tests in `tests/test_config.py`: (a) `PipelineSettings` with explicit `AI_BENCH_DATABASE_URL` env var does not trigger warning, (b) default value triggers warning (capture structlog output), (c) `EvalSettings` loads `env_file` |
| 3.7 | Completed | 2026-03-30 10:53 AM | 2026-03-30 10:55 AM | Run `pytest` (938 passed) and `ruff check` and `ruff format --check` — all green |
| 3.8 | Completed | 2026-03-30 10:55 AM | 2026-03-30 10:55 AM | Stage all Phase 3 changes |
| 3.9 | Completed | 2026-03-30 10:55 AM | 2026-03-30 10:55 AM | Commit all Phase 3 changes |

### Phase 3 Summary

- **Changes:** Created `scripts/env.dev.template` for dev `.env` with explicit absolute database path. Added `model_validator` warnings to `PipelineSettings` and `EvalSettings` when database URL is the relative default. Added `env_file=".env"` and `extra="ignore"` to both settings classes so they can share a single `.env` file. Updated `alembic/env.py` to read database URL from `PipelineSettings` instead of `alembic.ini`. Added 3 tests. Updated `test_default_settings` to isolate from `.env`.
- **Changes hosted at:** `scripts/env.dev.template`, `ai_benchmark/config/settings.py`, `ai_benchmark/eval/config.py`, `alembic/env.py`, `alembic.ini`, `tests/test_config.py`
- **Commit:** `Phase 3: Add database safety guards and dev .env template`

---

## Phase 4: Automated Backup

**Goal:** Production database is automatically backed up before every deploy. Old backups are rotated (keep last 10). Resolves interaction 4.9 (no automated backup).
**Depends on:** Phase 1 (deploy scripts exist to integrate backup into).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Completed | 2026-03-30 10:56 AM | 2026-03-30 10:57 AM | Create `scripts/backup.ps1`: Accepts `$InstallDir` (default `C:\ai-benchmark`), `$RetainCount` (default 10). Copies `$InstallDir\data\ai_benchmark.db` to `$InstallDir\backup\ai_benchmark_YYYYMMDD_HHMMSS.db`. Rotates backups: sorts by name descending, deletes beyond `$RetainCount`. Reports size and count. |
| 4.2 | Completed | 2026-03-30 10:57 AM | 2026-03-30 10:57 AM | Create `scripts/backup.bat` — batch version with same copy + rotation logic |
| 4.3 | Completed | 2026-03-30 10:57 AM | 2026-03-30 10:58 AM | Update `scripts/deploy.ps1`: Replaced inline backup fallback with direct call to `& "$PSScriptRoot\backup.ps1" -InstallDir $InstallDir` |
| 4.4 | Completed | 2026-03-30 10:58 AM | 2026-03-30 10:58 AM | Update `scripts/deploy.bat`: Replaced inline backup fallback with `call "%~dp0backup.bat" "%INSTALL_DIR%"` |
| 4.5 | Completed | 2026-03-30 10:58 AM | 2026-03-30 10:58 AM | Verified scripts are syntactically correct and deploy scripts reference backup scripts correctly |
| 4.6 | Completed | 2026-03-30 10:58 AM | 2026-03-30 10:58 AM | Stage all Phase 4 changes |
| 4.7 | Completed | 2026-03-30 10:58 AM | 2026-03-30 10:58 AM | Commit all Phase 4 changes |

### Phase 4 Summary

- **Changes:** Created `scripts/backup.ps1` (PowerShell) and `scripts/backup.bat` (batch) with timestamped backup and rotation (keep last 10). Simplified deploy scripts to call dedicated backup scripts instead of inline backup logic.
- **Changes hosted at:** `scripts/backup.ps1`, `scripts/backup.bat`, `scripts/deploy.ps1`, `scripts/deploy.bat`
- **Commit:** `Phase 4: Add automated database backup with rotation`

---

## Phase 5: Documentation and Cleanup

**Goal:** All scripts have consistent documentation. `CLAUDE.md` documents the deploy workflow. Templates reflect the new venv architecture. Resolves interaction 4.8 (log separation via documentation).
**Depends on:** Phases 1-4 (all scripts finalized).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1 | Completed | 2026-03-30 10:59 AM | 2026-03-30 10:59 AM | Update `scripts/env.template`: Add header comments explaining production architecture (venv at `C:\ai-benchmark\venv`, wheel-based install, separate from dev editable install) |
| 5.2 | Completed | 2026-03-30 10:59 AM | 2026-03-30 11:01 AM | Update `CLAUDE.md`: Added "Deployment" section with install/deploy/backup commands and production layout. Document that `pip install -e ".[dev]"` is dev-only. |
| 5.3 | Completed | 2026-03-30 11:01 AM | 2026-03-30 11:02 AM | Update `CLAUDE.md` "Configuration" section: Documented dev `.env` file, `env.dev.template`, and database safety guard. Consolidated duplicate Configuration section. |
| 5.4 | Completed | 2026-03-30 11:02 AM | 2026-03-30 11:02 AM | Verified `scripts/deploy.ps1` and `scripts/deploy.bat` already have proper header comments (created with headers in Phase 1) |
| 5.5 | Completed | 2026-03-30 11:02 AM | 2026-03-30 11:03 AM | Audited all scripts: All bin scripts use venv Python. Only install/deploy scripts reference `C:\Python314\python.exe` for venv creation/wheel building. No inconsistencies. |
| 5.6 | Completed | 2026-03-30 11:03 AM | 2026-03-30 11:04 AM | Run `pytest` (938 passed) and `ruff check` and `ruff format --check` — all green |
| 5.7 | Completed | 2026-03-30 11:04 AM | 2026-03-30 11:04 AM | Stage all Phase 5 changes |
| 5.8 | Completed | 2026-03-30 11:04 AM | 2026-03-30 11:04 AM | Commit all Phase 5 changes |

### Phase 5 Summary

- **Changes:** Updated `scripts/env.template` with production architecture header comments. Added "Deployment" and "Configuration" sections to `CLAUDE.md` documenting install/deploy/backup workflow, production layout, dev `.env` usage, and database safety guard. Removed duplicate Configuration section from later in the file.
- **Changes hosted at:** `scripts/env.template`, `CLAUDE.md`
- **Commit:** `Phase 5: Update documentation and templates for venv-based deployment`

---

## Phase 6: First Production Deploy

**Goal:** Production environment migrated from editable install to venv-based wheel install. The old coupling is severed and verified. This is an operational phase — run the installer, verify isolation.
**Depends on:** Phases 1-5 (all scripts tested and committed).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 6.1 | Completed | 2026-03-30 11:06 AM | 2026-03-30 11:06 AM | Pre-deploy: AIBenchmarkCollect next run 3/31 5:00 AM. Backup from yesterday exists. Production DB is 40 MB. |
| 6.2 | Completed | 2026-03-30 11:06 AM | 2026-03-30 11:07 AM | Ran `backup.ps1` — created backup (41076 KB), 2 retained. Fixed em dash encoding issue in backup.ps1. |
| 6.3 | Completed | 2026-03-30 11:07 AM | 2026-03-30 11:10 AM | Created venv, built wheel, installed into venv (ai_benchmark-0.1.0 + 42 deps), copied bin scripts, removed stale "AI Benchmark Daily Collection" task. |
| 6.4 | Completed | 2026-03-30 11:10 AM | 2026-03-30 11:11 AM | check-config: 22 sources, 86 pages OK. status: 2742+ events, 118 papers visible from venv with production DB. |
| 6.5 | Completed | 2026-03-30 11:11 AM | 2026-03-30 11:13 AM | Isolation test PASSED: added marker to dev cli.py, confirmed NOT visible from venv when CWD=C:\ai-benchmark. Reverted marker. Note: CWD must be production dir for isolation (bin scripts handle this via `cd /d %INSTALL_DIR%`). |
| 6.6 | Completed | 2026-03-30 11:13 AM | 2026-03-30 11:13 AM | Stage all Phase 6 changes |
| 6.7 | Completed | 2026-03-30 11:13 AM | 2026-03-30 11:13 AM | Commit all Phase 6 changes |

### Phase 6 Summary

- **Changes:** Production venv created at `C:\ai-benchmark\venv` with wheel-based install. Stale "AI Benchmark Daily Collection" task removed. Fixed em dash encoding issue in `backup.ps1`. Isolation verified — dev code changes not visible from production venv. All 9 interactions from design document are now resolved.
- **Changes hosted at:** `scripts/backup.ps1`, `docs/dev_prod_isolation_plan.md`
- **Commit:** `Phase 6: Complete first production deploy with venv isolation`

---

## Interaction Resolution Matrix

| # | Interaction | Severity | Resolution Phase | Mechanism |
|---|---|---|---|---|
| 4.1 | Editable install — live code sharing | Critical | 1, verified 6 | Wheel install into production venv |
| 4.2 | Shared CLI binary | High | 1 | Separate binaries: system (dev) vs venv (prod) |
| 4.3 | No virtual environment | High | 1 | Production venv at `C:\ai-benchmark\venv` |
| 4.4 | Concurrent scheduled tasks | High | 2 | Single batch task at 05:00; Claude Code at 06:00 analysis-only |
| 4.5 | daily_collect.ps1 targets dev | Medium | 2 | Retarget `$ProjectDir` to `C:\ai-benchmark` |
| 4.6 | Database isolation by convention | Medium | 3 | Dev `.env` + relative-path warning validator + alembic fix |
| 4.7 | Installer formalizes coupling | Informational | 1 | Installers now create venv + install wheel |
| 4.8 | Log path separation | Low | 2, 5 | Retargeted daily_collect.ps1 + documentation |
| 4.9 | No automated backup | Informational | 4 | `backup.ps1` with rotation; integrated into deploy |
