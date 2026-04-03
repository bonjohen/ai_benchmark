@echo off
setlocal enabledelayedexpansion
REM Phase 6: Deploy, Upgrade, and Backfill
REM Run from any cmd window. Each step uses absolute paths.
REM Halts on any error. Safe to re-run (idempotent where possible).

REM Step 1: Upgrade deployed instance (installs latest code + regenerates bin scripts)
echo === Step 1: Upgrading deployed instance ===
cd /d C:\Projects\ai_benchmark
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\installer\Update-Instance.ps1 -Name ai-data-pipeline
if %ERRORLEVEL% neq 0 (echo ERROR: Installer upgrade failed & exit /b 1)

REM Step 2: Ensure AI_BENCH_LOG_DIR is in .env (idempotent — skips if already present)
echo === Step 2: Ensuring file logging is enabled ===
cd /d C:\ai-data-pipeline
findstr /C:"AI_BENCH_LOG_DIR" config\.env >nul 2>&1
if %ERRORLEVEL% neq 0 (
    powershell.exe -NoProfile -Command "Add-Content config\.env \"`nAI_BENCH_LOG_DIR=C:/ai-data-pipeline/logs\""
    echo Added AI_BENCH_LOG_DIR to .env
) else (
    echo AI_BENCH_LOG_DIR already in .env — skipping
)

REM Step 3: Verify config
echo === Step 3: Verifying config ===
set AI_BENCH_ENV_FILE=C:\ai-data-pipeline\config\.env
C:\ai-data-pipeline\venv\Scripts\python.exe -m ai_benchmark check-config
if %ERRORLEVEL% neq 0 (echo ERROR: Config check failed & exit /b 1)

REM Step 4: Delete old database and reinitialize
echo === Step 4: Resetting database ===
set AI_BENCH_ENV_FILE=C:\ai-data-pipeline\config\.env
if exist C:\ai-data-pipeline\data\ai_benchmark.db del C:\ai-data-pipeline\data\ai_benchmark.db
C:\ai-data-pipeline\venv\Scripts\python.exe -m ai_benchmark init-db
if %ERRORLEVEL% neq 0 (echo ERROR: init-db failed & exit /b 1)

REM Step 5: Backfill collection data
echo === Step 5: Backfilling collection data ===
set AI_BENCH_ENV_FILE=C:\ai-data-pipeline\config\.env
C:\ai-data-pipeline\venv\Scripts\python.exe -m ai_benchmark collect --since 2026-03-29
if %ERRORLEVEL% neq 0 (echo ERROR: Backfill failed & exit /b 1)

REM Step 6: Generate daily reports (JSON extraction + Claude CLI summarization)
echo === Step 6: Generating daily reports ===
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\ai-data-pipeline\bin\report_range.ps1 -Since 2026-03-29
if %ERRORLEVEL% neq 0 (echo ERROR: Report generation failed & exit /b 1)

REM Step 7: Generate weekly report (Thu 3/29 through today)
echo === Step 7: Generating weekly report ===
C:\ai-data-pipeline\bin\weekly_report.bat 2026-04-06

echo.
echo === Phase 6 complete ===
