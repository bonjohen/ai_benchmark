@echo off
:: DEPRECATED: Use ai-bench-installer.bat dev-setup instead.
:: This script will be removed in a future release.
:: See: scripts\ai-bench-installer.bat dev-setup -Help
echo WARNING: This script is deprecated. Use ai-bench-installer.bat dev-setup instead.
echo.
:: AI Benchmark — Dev Environment Setup
:: Run from the project root: scripts\setup_dev.bat
:: Sets up the dev editable install, creates .env, and initializes the database.

setlocal enabledelayedexpansion

set SOURCE_DIR=%~dp0..
set PYTHON=C:\Python314\python.exe

if not exist "%PYTHON%" (
    echo ERROR: Python not found at %PYTHON%
    echo   Edit this script to set the correct PYTHON path.
    exit /b 1
)

echo.
echo ============================================
echo  AI Benchmark — Dev Setup
echo ============================================
echo.

:: ── Install package in editable mode with dev dependencies ──
echo [1/3] Installing package (editable + dev extras)...
cd /d "%SOURCE_DIR%"
"%PYTHON%" -m pip install -e ".[dev]" --quiet
if errorlevel 1 (
    echo ERROR: pip install failed
    exit /b 1
)
echo   Installed ai_benchmark in editable mode

:: ── Create .env from template if missing ──
echo.
echo [2/3] Setting up .env...
if not exist "%SOURCE_DIR%\.env" (
    copy /y "%SOURCE_DIR%\scripts\env.dev.template" "%SOURCE_DIR%\.env" >nul
    echo   Created .env from env.dev.template
    echo   ** Edit .env to add API keys **
) else (
    echo   .env already exists — skipping
)

:: ── Initialize database ──
echo.
echo [3/3] Initializing database...
"%PYTHON%" -m ai_benchmark.cli init-db
if errorlevel 1 (
    echo ERROR: Database initialization failed
    exit /b 1
)
echo   Database ready

echo.
echo ============================================
echo  Dev setup complete!
echo ============================================
echo.
echo  Next steps:
echo    1. Edit .env to add API keys
echo    2. ai-benchmark check-config
echo    3. ai-benchmark eval serve
echo.

endlocal
