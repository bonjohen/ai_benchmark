@echo off
:: AI Benchmark Pipeline — Windows Installer
:: Run from an elevated (Admin) Command Prompt.
:: Usage: install.bat [INSTALL_DIR] [PYTHON_PATH]
::   Defaults: C:\ai-benchmark, C:\Python314\python.exe

setlocal enabledelayedexpansion

:: ── Configuration ──
set INSTALL_DIR=%~1
if "%INSTALL_DIR%"=="" set INSTALL_DIR=C:\ai-benchmark

set PYTHON=%~2
if "%PYTHON%"=="" set PYTHON=C:\Python314\python.exe

set SOURCE_DIR=%~dp0..
set TASK_NAME=AIBenchmarkCollect
set TASK_SCHEDULE=daily
set TASK_TIME=05:00

echo.
echo ============================================
echo  AI Benchmark Pipeline Installer
echo ============================================
echo  Install dir : %INSTALL_DIR%
echo  Python      : %PYTHON%
echo  Source      : %SOURCE_DIR%
echo ============================================
echo.

:: ── Verify Python ──
if not exist "%PYTHON%" (
    echo ERROR: Python not found at %PYTHON%
    echo   Pass the path as the second argument: install.bat C:\ai-benchmark C:\path\to\python.exe
    exit /b 1
)

:: ── Create directory structure ──
echo [1/6] Creating directory structure...
for %%D in (bin config data artifacts logs backup) do (
    if not exist "%INSTALL_DIR%\%%D" (
        mkdir "%INSTALL_DIR%\%%D"
        echo   Created %INSTALL_DIR%\%%D
    ) else (
        echo   Exists  %INSTALL_DIR%\%%D
    )
)

:: ── Copy bin scripts ──
echo.
echo [2/6] Installing scripts...
for %%F in ("%SOURCE_DIR%\scripts\bin\*.bat") do (
    copy /y "%%F" "%INSTALL_DIR%\bin\" >nul
    echo   Installed bin\%%~nxF
)

:: ── Write .env (only if not already present) ──
echo.
echo [3/6] Writing configuration...
if not exist "%INSTALL_DIR%\config\.env" (
    copy /y "%SOURCE_DIR%\scripts\env.template" "%INSTALL_DIR%\config\.env" >nul
    echo   Created config\.env from template
    echo   ** Edit %INSTALL_DIR%\config\.env to add API keys **
) else (
    echo   config\.env already exists — skipping (will not overwrite)
)

:: ── Install Python package ──
echo.
echo [4/6] Installing Python package...
pushd "%SOURCE_DIR%"
%PYTHON% -m pip install -e . --quiet
if errorlevel 1 (
    echo ERROR: pip install failed
    popd
    exit /b 1
)
popd
echo   Package installed successfully

:: ── Initialize database ──
echo.
echo [5/6] Initializing database...
:: Set env vars for init-db
set AI_BENCH_DATABASE_URL=sqlite+aiosqlite:///C:/ai-benchmark/data/ai_benchmark.db
cd /d "%INSTALL_DIR%"
%PYTHON% -m ai_benchmark.cli init-db
if errorlevel 1 (
    echo ERROR: Database initialization failed
    exit /b 1
)
echo   Database ready at data\ai_benchmark.db

:: ── Register scheduled task ──
echo.
echo [6/6] Registering scheduled task...
schtasks /create /tn "%TASK_NAME%" /tr "cmd.exe /c %INSTALL_DIR%\bin\collect.bat" /sc %TASK_SCHEDULE% /st %TASK_TIME% /rl highest /f >nul 2>&1
if errorlevel 1 (
    echo   WARNING: Could not create scheduled task. Create it manually:
    echo   schtasks /create /tn "%TASK_NAME%" /tr "cmd.exe /c %INSTALL_DIR%\bin\collect.bat" /sc %TASK_SCHEDULE% /st %TASK_TIME% /rl highest /f
) else (
    echo   Task "%TASK_NAME%" registered: %TASK_SCHEDULE% at %TASK_TIME%
)

:: ── Done ──
echo.
echo ============================================
echo  Installation complete!
echo ============================================
echo.
echo  Install dir  : %INSTALL_DIR%
echo  Config       : %INSTALL_DIR%\config\.env
echo  Database     : %INSTALL_DIR%\data\ai_benchmark.db
echo  Logs         : %INSTALL_DIR%\logs\
echo  Artifacts    : %INSTALL_DIR%\artifacts\
echo.
echo  Next steps:
echo    1. Edit %INSTALL_DIR%\config\.env (add API keys)
echo    2. Test: %INSTALL_DIR%\bin\collect.bat
echo    3. Check: schtasks /query /tn "%TASK_NAME%"
echo    4. Run now: schtasks /run /tn "%TASK_NAME%"
echo.

endlocal
