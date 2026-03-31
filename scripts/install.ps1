#Requires -RunAsAdministrator
# DEPRECATED: Use ai-bench-installer.bat install instead.
# This script will be removed in a future release.
# See: scripts\ai-bench-installer.bat install -Help
Write-Warning "This script is deprecated. Use ai-bench-installer.bat install instead."
<#
.SYNOPSIS
    AI Benchmark Pipeline — Windows Installer (PowerShell)
.DESCRIPTION
    Creates the application install folder, copies scripts, writes config,
    installs the Python package, initializes the database, and registers
    the scheduled task.
.PARAMETER InstallDir
    Installation directory. Default: C:\ai-benchmark
.PARAMETER PythonPath
    Path to python.exe. Default: C:\Python314\python.exe
.PARAMETER TaskTime
    Daily collection time (HH:MM). Default: 05:00
.EXAMPLE
    .\install.ps1
    .\install.ps1 -InstallDir D:\ai-benchmark -PythonPath C:\Python312\python.exe
#>

param(
    [string]$InstallDir = "C:\ai-benchmark",
    [string]$PythonPath = "C:\Python314\python.exe",
    [string]$TaskTime = "05:00"
)

$ErrorActionPreference = "Stop"
$SourceDir = Split-Path -Parent $PSScriptRoot
# If run from scripts/ directly, SourceDir is the project root
if (-not (Test-Path "$SourceDir\pyproject.toml")) {
    $SourceDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

$TaskName = "AIBenchmarkCollect"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " AI Benchmark Pipeline Installer" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Install dir : $InstallDir"
Write-Host " Python      : $PythonPath"
Write-Host " Source      : $SourceDir"
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── Verify Python ──
if (-not (Test-Path $PythonPath)) {
    Write-Host "ERROR: Python not found at $PythonPath" -ForegroundColor Red
    Write-Host "  Use -PythonPath to specify the correct path."
    exit 1
}

# ── Create directory structure ──
Write-Host "[1/6] Creating directory structure..." -ForegroundColor Yellow
$dirs = @("bin", "config", "data", "artifacts", "logs", "backup")
foreach ($dir in $dirs) {
    $path = Join-Path $InstallDir $dir
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "  Created $path"
    } else {
        Write-Host "  Exists  $path"
    }
}

# ── Copy bin scripts ──
Write-Host ""
Write-Host "[2/6] Installing scripts..." -ForegroundColor Yellow
$binSource = Join-Path $SourceDir "scripts\bin"
if (Test-Path $binSource) {
    Get-ChildItem -Path $binSource -Filter "*.bat" | ForEach-Object {
        Copy-Item $_.FullName -Destination (Join-Path $InstallDir "bin") -Force
        Write-Host "  Installed bin\$($_.Name)"
    }
} else {
    Write-Host "  WARNING: $binSource not found — skipping script copy" -ForegroundColor Yellow
}

# ── Write .env ──
Write-Host ""
Write-Host "[3/6] Writing configuration..." -ForegroundColor Yellow
$envFile = Join-Path $InstallDir "config\.env"
if (-not (Test-Path $envFile)) {
    $template = Join-Path $SourceDir "scripts\env.template"
    if (Test-Path $template) {
        Copy-Item $template -Destination $envFile -Force
        Write-Host "  Created config\.env from template"
        Write-Host "  ** Edit $envFile to add API keys **" -ForegroundColor Magenta
    } else {
        Write-Host "  WARNING: env.template not found" -ForegroundColor Yellow
    }
} else {
    Write-Host "  config\.env already exists - skipping (will not overwrite)"
}

# ── Create venv and install Python package (wheel, non-editable) ──
Write-Host ""
Write-Host "[4/6] Installing Python package into venv..." -ForegroundColor Yellow
$VenvDir = Join-Path $InstallDir "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$TmpDir = Join-Path $VenvDir "tmp"

# Create venv if it doesn't exist
if (-not (Test-Path $VenvPython)) {
    Write-Host "  Creating virtual environment at $VenvDir..."
    & $PythonPath -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: venv creation failed" -ForegroundColor Red
        exit 1
    }
}

# Build wheel from source
Write-Host "  Building wheel..."
if (Test-Path $TmpDir) { Remove-Item $TmpDir -Recurse -Force }
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
& $PythonPath -m build --wheel --outdir $TmpDir $SourceDir 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: wheel build failed" -ForegroundColor Red
    exit 1
}

# Install wheel into venv
$WheelFile = (Get-ChildItem -Path $TmpDir -Filter "*.whl" | Select-Object -First 1).FullName
if (-not $WheelFile) {
    Write-Host "ERROR: No .whl file found in $TmpDir" -ForegroundColor Red
    exit 1
}
Write-Host "  Installing $([System.IO.Path]::GetFileName($WheelFile))..."
& $VenvPip install $WheelFile --force-reinstall --quiet 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install failed" -ForegroundColor Red
    exit 1
}

# Cleanup
Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  Package installed into venv successfully"

# ── Initialize database ──
Write-Host ""
Write-Host "[5/6] Initializing database..." -ForegroundColor Yellow
$env:AI_BENCH_DATABASE_URL = "sqlite+aiosqlite:///C:/ai-benchmark/data/ai_benchmark.db"
Push-Location $InstallDir
try {
    & $VenvPython -m ai_benchmark.cli init-db 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Database initialization failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Database ready at data\ai_benchmark.db"
} finally {
    Pop-Location
}

# ── Register scheduled task ──
Write-Host ""
Write-Host "[6/6] Registering scheduled task..." -ForegroundColor Yellow

# Remove stale duplicate task if present (was 'AI Benchmark Daily Collection' at 05:00)
Unregister-ScheduledTask -TaskName "AI Benchmark Daily Collection" -Confirm:$false -ErrorAction SilentlyContinue

# Register the sole daily collection task
try {
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$InstallDir\bin\collect.bat`""
    $trigger = New-ScheduledTaskTrigger -Daily -At $TaskTime
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -RunLevel Highest -Force | Out-Null
    Write-Host "  Task '$TaskName' registered: daily at $TaskTime"
} catch {
    Write-Host "  WARNING: Could not create scheduled task: $_" -ForegroundColor Yellow
    Write-Host "  Create it manually from an admin Command Prompt:"
    Write-Host "  schtasks /create /tn `"$TaskName`" /tr `"cmd.exe /c $InstallDir\bin\collect.bat`" /sc daily /st $TaskTime /rl highest /f"
}

# Optional: register Claude Code analysis task at 06:00 (uncomment to enable)
# $analysisAction = New-ScheduledTaskAction -Execute "powershell.exe" `
#     -Argument "-ExecutionPolicy Bypass -File `"$InstallDir\..\Projects\ai_benchmark\scripts\daily_collect.ps1`""
# $analysisTrigger = New-ScheduledTaskTrigger -Daily -At "06:00"
# Register-ScheduledTask -TaskName "AIBenchmarkAnalysis" -Action $analysisAction `
#     -Trigger $analysisTrigger -Settings $settings -RunLevel Highest -Force | Out-Null

# ── Done ──
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Installation complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host " Install dir  : $InstallDir"
Write-Host " Venv         : $InstallDir\venv\"
Write-Host " Config       : $InstallDir\config\.env"
Write-Host " Database     : $InstallDir\data\ai_benchmark.db"
Write-Host " Logs         : $InstallDir\logs\"
Write-Host " Artifacts    : $InstallDir\artifacts\"
Write-Host ""
Write-Host " Next steps:" -ForegroundColor Cyan
Write-Host "   1. Edit $InstallDir\config\.env (add API keys)"
Write-Host "   2. Test: $InstallDir\bin\collect.bat"
Write-Host "   3. Check: schtasks /query /tn `"$TaskName`""
Write-Host "   4. Run now: schtasks /run /tn `"$TaskName`""
Write-Host ""
