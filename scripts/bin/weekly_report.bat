@echo off
:: AI Benchmark — Weekly Report (synthesize 7 daily markdown reports)
:: Reads config from INSTALL_DIR\config\.env
:: Requires Claude CLI (claude) on PATH
::
:: Usage:  weekly_report.bat [YYYY-MM-DD]
::   Argument is the week-ending Sunday date.
::   Without argument: uses the most recent Sunday.
::
:: Set CLAUDE_SESSION to a session ID to resume an authorized session.

setlocal enabledelayedexpansion

:: Clear API keys so Claude CLI uses OAuth, not API key billing
set ANTHROPIC_API_KEY=
set ANTHROPIC_AUTH_TOKEN=

set INSTALL_DIR={{INSTALL_DIR}}
set ENV_FILE=%INSTALL_DIR%\config\.env
set ARTIFACTS=%INSTALL_DIR%\artifacts

:: Determine Sunday date — from argument or most recent Sunday
set SUNDAY=%~1
if not defined SUNDAY (
    for /f "delims=" %%D in ('powershell -NoProfile -Command "(Get-Date).AddDays(-(([int](Get-Date).DayOfWeek))).ToString('yyyy-MM-dd')"') do set SUNDAY=%%D
)

:: Compute Monday (Sunday - 6 days) and all 7 dates via PowerShell
for /f "delims=" %%M in ('powershell -NoProfile -Command "([DateTime]'%SUNDAY%').AddDays(-6).ToString('yyyy-MM-dd')"') do set MONDAY=%%M

echo [%date% %time%] Generating weekly report for %MONDAY% through %SUNDAY%

:: Build list of 7 daily report file paths and check existence
set FILE_LIST=
set MISSING=0
set FOUND=0
for /f "delims=" %%L in ('powershell -NoProfile -Command "$sun=[DateTime]'%SUNDAY%'; for($i=6;$i -ge 0;$i--){($sun.AddDays(-$i)).ToString('yyyyMMdd')}"') do (
    set DSAFE=%%L
    set FPATH=%ARTIFACTS%\daily_report_%%L.md
    if exist "!FPATH!" (
        set FILE_LIST=!FILE_LIST! "!FPATH!"
        set /a FOUND+=1
    ) else (
        echo WARNING: Missing daily_report_%%L.md
        set /a MISSING+=1
    )
)

echo Found %FOUND% of 7 daily reports (%MISSING% missing)

if %FOUND% equ 0 (
    echo ERROR: No daily reports found — cannot generate weekly report.
    exit /b 1
)

:: Output filename
set SUNDAY_SAFE=%SUNDAY:-=%
set REPORT=%ARTIFACTS%\weekly_report_%SUNDAY_SAFE%.md

:: Load AI_BENCH_ variables and CLAUDE_SESSION from .env
if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        set "LINE=%%A"
        if not "!LINE:~0,1!"=="#" (
            if "!LINE:~0,9!"=="AI_BENCH_" set "%%A=%%B"
            if "!LINE!"=="CLAUDE_SESSION" set "%%A=%%B"
        )
    )
)

:: Ensure artifacts directory exists
if not exist "%ARTIFACTS%" mkdir "%ARTIFACTS%"

cd /d %INSTALL_DIR%

:: Claude CLI uses OAuth because ANTHROPIC_API_KEY was cleared above.
echo Synthesizing weekly report with Claude CLI...
claude -p "Read these daily AI intelligence reports: %FILE_LIST%. They cover the week of %MONDAY% through %SUNDAY%. Produce a weekly intelligence summary with these sections: # AI Intelligence Weekly Report, ## Week of %MONDAY% through %SUNDAY%, ## Key Developments (the 3-5 most significant events of the week), ## Story Arcs (announcements that evolved over multiple days), ## Emerging Trends (patterns visible across multiple days), ## Competitive Landscape (moves and responses between AI companies). Write the report as markdown to %REPORT%."
if %ERRORLEVEL% neq 0 (
    echo ERROR: Claude CLI returned error
    exit /b 2
)

echo.
echo Weekly report written to %REPORT%
echo [%date% %time%] Weekly report complete
