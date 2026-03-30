@echo off
:: Start both production and dev eval servers side by side.
::   Production: http://127.0.0.1:8100  (venv wheel install)
::   Dev:        http://127.0.0.1:8200  (editable install)
:: Press Ctrl+C in either window to stop that server.

setlocal enabledelayedexpansion

:: ── Production ──
set PROD_DIR=C:\ai-benchmark
set PROD_PYTHON=%PROD_DIR%\venv\Scripts\python.exe
set PROD_ENV=%PROD_DIR%\config\.env
set PROD_PORT=8100

:: ── Dev ──
set DEV_DIR=C:\Projects\ai_benchmark
set DEV_PYTHON=C:\Python314\python.exe
set DEV_PORT=8200

:: ── Verify both Pythons exist ──
if not exist "%PROD_PYTHON%" (
    echo ERROR: Production venv not found at %PROD_PYTHON%
    echo   Run scripts\install.ps1 first.
    exit /b 1
)
if not exist "%DEV_PYTHON%" (
    echo ERROR: Dev Python not found at %DEV_PYTHON%
    exit /b 1
)

echo.
echo ============================================
echo  Starting both eval servers
echo ============================================
echo  Production : http://127.0.0.1:%PROD_PORT%
echo  Dev        : http://127.0.0.1:%DEV_PORT%
echo ============================================
echo.

:: Start production server in a new window
start "AI Benchmark - PRODUCTION (%PROD_PORT%)" cmd /k "cd /d %PROD_DIR% && set AI_BENCH_DATABASE_URL=sqlite+aiosqlite:///C:/ai-benchmark/data/ai_benchmark.db && set AI_BENCH_EVAL_DATABASE_URL=sqlite+aiosqlite:///C:/ai-benchmark/data/ai_benchmark.db && "%PROD_PYTHON%" -m ai_benchmark.cli eval serve --port %PROD_PORT%"

:: Start dev server in a new window
start "AI Benchmark - DEV (%DEV_PORT%)" cmd /k "cd /d %DEV_DIR% && "%DEV_PYTHON%" -m ai_benchmark.cli eval serve --port %DEV_PORT%"

:: Give servers a moment to start
timeout /t 3 /nobreak >nul

:: Open both in the browser
start http://127.0.0.1:%PROD_PORT%
start http://127.0.0.1:%DEV_PORT%

echo Both servers launched. Close the server windows to stop them.
