@echo off
:: AI Benchmark — Database Backup with Rotation
:: Copies the production SQLite database to a timestamped backup file.
:: Rotates old backups, keeping only the most recent 10 copies.
:: Usage: backup.bat [INSTALL_DIR]
::   Default: C:\ai-benchmark

setlocal enabledelayedexpansion

set INSTALL_DIR=%~1
if "%INSTALL_DIR%"=="" set INSTALL_DIR=C:\ai-benchmark

set DB_FILE=%INSTALL_DIR%\data\ai_benchmark.db
set BACKUP_DIR=%INSTALL_DIR%\backup
set RETAIN_COUNT=10

:: Ensure backup directory exists
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

:: Get timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
set TIMESTAMP=%dt:~0,8%_%dt:~8,6%
set BACKUP_FILE=%BACKUP_DIR%\ai_benchmark_%TIMESTAMP%.db

:: Back up database
if not exist "%DB_FILE%" (
    echo   No database found at %DB_FILE% — skipping backup
    exit /b 0
)

copy /y "%DB_FILE%" "%BACKUP_FILE%" >nul
echo   Backed up database -^> %BACKUP_FILE%

:: Rotate: keep only the most recent RETAIN_COUNT backups
:: Count and delete oldest if over limit
set count=0
for /f %%F in ('dir /b /o-n "%BACKUP_DIR%\ai_benchmark_*.db" 2^>nul') do (
    set /a count+=1
    if !count! gtr %RETAIN_COUNT% (
        del "%BACKUP_DIR%\%%F" >nul 2>&1
        echo   Rotated out: %%F
    )
)

echo   Backups: %RETAIN_COUNT% retained (max %RETAIN_COUNT%)

endlocal
