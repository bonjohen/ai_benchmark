@echo off
:: AI Benchmark — Daily Report (two-stage: extract JSON + Claude CLI summarize)
:: Reads config from INSTALL_DIR\config\.env
:: Requires Claude CLI (claude) on PATH
::
:: Usage:  report.bat [YYYY-MM-DD]
::   With date argument: generates report for that specific date.
::   Without argument:   generates report for today's date.
::
:: Set CLAUDE_SESSION to a session ID to resume an authorized session.
:: Without it, claude -p starts a fresh session.

setlocal enabledelayedexpansion

:: Clear API keys so Claude CLI uses OAuth, not API key billing
set ANTHROPIC_API_KEY=
set ANTHROPIC_AUTH_TOKEN=

set INSTALL_DIR={{INSTALL_DIR}}
set ENV_FILE=%INSTALL_DIR%\config\.env
set PYTHON=%INSTALL_DIR%\venv\Scripts\python.exe
set AI_BENCH_ENV_FILE=%ENV_FILE%
set ARTIFACTS=%INSTALL_DIR%\artifacts

:: Determine date — from argument or today
set DATE_ARG=%~1
if not defined DATE_ARG (
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
    set DATE_ARG=!dt:~0,4!-!dt:~4,2!-!dt:~6,2!
)

:: Derive DATE_SAFE (strip hyphens): 2026-03-15 -> 20260315
set DATE_SAFE=%DATE_ARG:-=%

set RAW=%ARTIFACTS%\raw_articles_%DATE_SAFE%.json
set REPORT=%ARTIFACTS%\daily_report_%DATE_SAFE%.md

:: Load only AI_BENCH_ variables from .env — do NOT load ANTHROPIC_API_KEY
:: or other API keys, which would cause Claude CLI to use the API key
:: instead of OAuth authentication.
if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        set "LINE=%%A"
        if not "!LINE:~0,1!"=="#" (
            if "!LINE:~0,9!"=="AI_BENCH_" set "%%A=%%B"
        )
    )
)

:: Ensure artifacts directory exists
if not exist "%ARTIFACTS%" mkdir "%ARTIFACTS%"

:: Ensure logs directory exists
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"

cd /d %INSTALL_DIR%

echo [%date% %time%] Starting daily report generation for %DATE_ARG%

:: Stage 1: Extract compact JSON from database
echo Stage 1: Extracting articles for %DATE_ARG%...
%PYTHON% -m ai_benchmark report --date %DATE_ARG% --output "%RAW%"
if %ERRORLEVEL% neq 0 (
    echo ERROR: Stage 1 failed — JSON extraction returned error
    exit /b 1
)
echo Stage 1 complete: %RAW%

:: Stage 2: Summarize with Claude CLI
echo Stage 2: Summarizing with Claude CLI...

:: Build claude command — resume session if CLAUDE_SESSION is set
set CLAUDE_CMD=claude
if defined CLAUDE_SESSION set CLAUDE_CMD=claude -r "%CLAUDE_SESSION%"

%CLAUDE_CMD% -p "Read the file %RAW%. It contains AI industry events from %DATE_ARG%. Group the articles by topic (thematic, not by publisher). For each topic, write a 2-3 sentence summary, then list the articles. Skip any non-AI articles (wars, politics, sports). Write the final report as markdown to %REPORT%. Format: # AI Intelligence Daily Report, ## %DATE_ARG%, then ## Topic Name sections with summary paragraphs and bullet-pointed articles with [Source](url) links."
if %ERRORLEVEL% neq 0 (
    echo ERROR: Stage 2 failed — Claude CLI returned error
    exit /b 2
)

echo.
echo Report written to %REPORT%
echo [%date% %time%] Daily report complete for %DATE_ARG%
