@echo off
:: AI Benchmark — Daily Report (two-stage: extract JSON + Claude CLI summarize)
:: Reads config from INSTALL_DIR\config\.env
:: Requires Claude CLI (claude) on PATH

setlocal enabledelayedexpansion

set INSTALL_DIR=C:\ai-data-pipeline
set ENV_FILE=%INSTALL_DIR%\config\.env
set PYTHON=%INSTALL_DIR%\venv\Scripts\python.exe
set AI_BENCH_ENV_FILE=%ENV_FILE%
set ARTIFACTS=%INSTALL_DIR%\artifacts
set RAW=%ARTIFACTS%\raw_articles.json
set REPORT=%ARTIFACTS%\daily_report.md

:: Load environment from .env
if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        set "LINE=%%A"
        if not "!LINE:~0,1!"=="#" (
            if not "%%A"=="" set "%%A=%%B"
        )
    )
)

:: Ensure artifacts directory exists
if not exist "%ARTIFACTS%" mkdir "%ARTIFACTS%"

:: Ensure logs directory exists
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"

cd /d %INSTALL_DIR%

echo [%date% %time%] Starting daily report generation

:: Stage 1: Extract compact JSON from database
echo Stage 1: Extracting articles...
%PYTHON% -m ai_benchmark report --output "%RAW%"
if %ERRORLEVEL% neq 0 (
    echo ERROR: Stage 1 failed — JSON extraction returned error
    exit /b 1
)
echo Stage 1 complete: %RAW%

:: Stage 2: Summarize with Claude CLI
echo Stage 2: Summarizing with Claude CLI...
claude -p "Read the file %RAW%. It contains AI industry events from the last 24 hours. Group the articles by topic (thematic, not by publisher). For each topic, write a 2-3 sentence summary, then list the articles. Skip any non-AI articles (wars, politics, sports). Write the final report as markdown to %REPORT%. Format: # AI Intelligence Daily Report, ## date, then ## Topic Name sections with summary paragraphs and bullet-pointed articles with [Source](url) links."
if %ERRORLEVEL% neq 0 (
    echo ERROR: Stage 2 failed — Claude CLI returned error
    exit /b 2
)

echo.
echo Report written to %REPORT%
echo [%date% %time%] Daily report complete
