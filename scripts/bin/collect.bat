@echo off
:: AI Benchmark — Collection runner
:: Invoked by Windows Task Scheduler or manually.
:: Reads config from C:\ai-benchmark\config\.env

setlocal enabledelayedexpansion

set INSTALL_DIR=C:\ai-benchmark
set ENV_FILE=%INSTALL_DIR%\config\.env
set PYTHON=C:\Python314\python.exe

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
set LOGFILE=%INSTALL_DIR%\logs\collect_%dt:~0,8%_%dt:~8,6%.log

cd /d %INSTALL_DIR%

echo [%date% %time%] Starting collection >> "%LOGFILE%" 2>&1
%PYTHON% -m ai_benchmark.cli collect >> "%LOGFILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] Collection finished (exit code %EXIT_CODE%) >> "%LOGFILE%" 2>&1

exit /b %EXIT_CODE%
