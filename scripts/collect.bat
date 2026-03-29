@echo off
:: AI Benchmark collection runner
:: Delegates to the install folder's bin\collect.bat
:: For development use, runs from the install folder with proper .env config.

if exist "C:\ai-benchmark\bin\collect.bat" (
    call "C:\ai-benchmark\bin\collect.bat"
) else (
    echo ERROR: ai-benchmark is not installed.
    echo Run scripts\install.bat from an admin Command Prompt first.
    exit /b 1
)
