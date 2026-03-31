@echo off
:: AI Benchmark - Unified Installer
:: Usage: ai-bench-installer.bat <subcommand> [options]
::
:: Subcommands:
::   install     Create a new instance
::   upgrade     Upgrade an existing instance
::   uninstall   Remove an instance
::   list        List all registered instances
::   status      Show instance status
::   backup      Back up instance database
::   dev-setup   Set up development environment

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "INSTALLER_DIR=%SCRIPT_DIR%installer\"
set "SUBCMD=%~1"

if "%SUBCMD%"=="" (
    echo.
    echo  AI Benchmark - Unified Installer
    echo  =================================
    echo.
    echo  Usage: %~nx0 ^<subcommand^> [options]
    echo.
    echo  Subcommands:
    echo    install     Create a new instance
    echo    upgrade     Upgrade an existing instance
    echo    uninstall   Remove an instance
    echo    list        List all registered instances
    echo    status      Show instance status
    echo    backup      Back up instance database
    echo    dev-setup   Set up development environment
    echo.
    echo  Examples:
    echo    %~nx0 install -Path C:\ai-benchmark
    echo    %~nx0 install -Path D:\staging -Name staging -Port 9200 -NoSchedule
    echo    %~nx0 install -Path C:\ai-benchmark -DryRun
    echo    %~nx0 list
    echo.
    echo  Run '%~nx0 ^<subcommand^> -Help' for subcommand options.
    exit /b 1
)

:: Shift past the subcommand to collect remaining args
shift

set "ARGS="
:argloop
if "%~1"=="" goto :dispatch
set "ARGS=!ARGS! "%~1""
shift
goto :argloop

:dispatch

if /i "%SUBCMD%"=="install" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%INSTALLER_DIR%Install-Instance.ps1" !ARGS!
    exit /b !ERRORLEVEL!
)

if /i "%SUBCMD%"=="upgrade" (
    echo Subcommand 'upgrade' is not yet implemented. Coming in Phase 4.
    exit /b 1
)

if /i "%SUBCMD%"=="uninstall" (
    echo Subcommand 'uninstall' is not yet implemented. Coming in Phase 5.
    exit /b 1
)

if /i "%SUBCMD%"=="list" (
    echo Subcommand 'list' is not yet implemented. Coming in Phase 3.
    exit /b 1
)

if /i "%SUBCMD%"=="status" (
    echo Subcommand 'status' is not yet implemented. Coming in Phase 3.
    exit /b 1
)

if /i "%SUBCMD%"=="backup" (
    echo Subcommand 'backup' is not yet implemented. Coming in Phase 5.
    exit /b 1
)

if /i "%SUBCMD%"=="dev-setup" (
    echo Subcommand 'dev-setup' is not yet implemented. Coming in Phase 5.
    exit /b 1
)

echo ERROR: Unknown subcommand '%SUBCMD%'
echo Run '%~nx0' without arguments for usage.
exit /b 1
