@echo off
:: AI Benchmark — Historical backfill runner
:: Collects data from a given start date forward using --since.
:: Usage: backfill.bat [SINCE_DATE]
::   Default: 2026-01-01
:: Reads config from C:\ai-benchmark\config\.env

setlocal enabledelayedexpansion

set INSTALL_DIR=C:\ai-benchmark
set ENV_FILE=%INSTALL_DIR%\config\.env
set PYTHON=%INSTALL_DIR%\venv\Scripts\python.exe

set SINCE=%~1
if "%SINCE%"=="" set SINCE=2026-01-01

:: Load environment from .env
if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        set "LINE=%%A"
        if not "!LINE:~0,1!"=="#" (
            if not "%%A"=="" set "%%A=%%B"
        )
    )
)

:: Ensure logs directory exists
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"

:: Timestamped log file
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
set LOGFILE=%INSTALL_DIR%\logs\backfill_%dt:~0,8%_%dt:~8,6%.log

cd /d %INSTALL_DIR%

echo [%date% %time%] Starting backfill (since %SINCE%) >> "%LOGFILE%" 2>&1
%PYTHON% -m ai_benchmark.cli collect --since %SINCE% >> "%LOGFILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] Backfill finished (exit code %EXIT_CODE%) >> "%LOGFILE%" 2>&1

exit /b %EXIT_CODE%
