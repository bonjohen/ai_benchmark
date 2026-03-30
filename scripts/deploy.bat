@echo off
:: AI Benchmark Pipeline — Deploy/Upgrade Script
:: Builds a wheel from dev source, backs up the production database,
:: installs the wheel into the production venv, and copies bin scripts.
:: Usage: deploy.bat [INSTALL_DIR]
::   Default: C:\ai-benchmark

setlocal enabledelayedexpansion

set INSTALL_DIR=%~1
if "%INSTALL_DIR%"=="" set INSTALL_DIR=C:\ai-benchmark

set SOURCE_DIR=%~dp0..
set VENV_DIR=%INSTALL_DIR%\venv
set VENV_PYTHON=%VENV_DIR%\Scripts\python.exe
set VENV_PIP=%VENV_DIR%\Scripts\pip.exe
set TMP_DIR=%VENV_DIR%\tmp

echo.
echo ============================================
echo  AI Benchmark Pipeline — Deploy
echo ============================================
echo  Install dir : %INSTALL_DIR%
echo  Source      : %SOURCE_DIR%
echo ============================================
echo.

:: ── Validate venv exists ──
if not exist "%VENV_PYTHON%" (
    echo ERROR: Venv not found at %VENV_DIR%
    echo   Run install.bat first for initial setup.
    exit /b 1
)

:: ── Backup production database ──
echo [1/4] Backing up database...
if exist "%~dp0backup.bat" (
    call "%~dp0backup.bat" "%INSTALL_DIR%"
) else (
    if exist "%INSTALL_DIR%\data\ai_benchmark.db" (
        for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
        copy /y "%INSTALL_DIR%\data\ai_benchmark.db" "%INSTALL_DIR%\backup\ai_benchmark_!dt:~0,8!_!dt:~8,6!.db" >nul
        echo   Backed up database
    ) else (
        echo   No database to back up
    )
)

:: ── Build wheel ──
echo.
echo [2/4] Building wheel...
if exist "%TMP_DIR%" rmdir /s /q "%TMP_DIR%"
mkdir "%TMP_DIR%"
:: Use system Python for build (venv may not have build tools)
set BUILD_PYTHON=C:\Python314\python.exe
if not exist "%BUILD_PYTHON%" set BUILD_PYTHON=python
%BUILD_PYTHON% -m build --wheel --outdir "%TMP_DIR%" "%SOURCE_DIR%" >nul 2>&1
if errorlevel 1 (
    echo ERROR: wheel build failed
    exit /b 1
)

:: ── Install wheel into venv ──
echo.
echo [3/4] Installing into venv...
for %%W in ("%TMP_DIR%\*.whl") do (
    echo   Installing %%~nxW...
    "%VENV_PIP%" install "%%W" --force-reinstall --quiet
    if errorlevel 1 (
        echo ERROR: pip install failed
        exit /b 1
    )
)
rmdir /s /q "%TMP_DIR%" >nul 2>&1
echo   Package upgraded successfully

:: ── Copy updated bin scripts ──
echo.
echo [4/4] Updating bin scripts...
for %%F in ("%SOURCE_DIR%\scripts\bin\*.bat") do (
    copy /y "%%F" "%INSTALL_DIR%\bin\" >nul
    echo   Updated bin\%%~nxF
)

:: ── Verify ──
echo.
echo Verifying installation...
"%VENV_PYTHON%" -m ai_benchmark.cli check-config
if errorlevel 1 (
    echo WARNING: check-config returned non-zero exit code
) else (
    echo   Verification passed
)

echo.
echo ============================================
echo  Deploy complete!
echo ============================================
echo.

endlocal
