<#
.SYNOPSIS
    AI Benchmark Pipeline — Deploy/Upgrade Script (PowerShell)
.DESCRIPTION
    Builds a wheel from the dev source, backs up the production database,
    installs the wheel into the production venv, and copies updated bin
    scripts. Use this for ongoing deployments after the initial install.
.PARAMETER InstallDir
    Production installation directory. Default: C:\ai-benchmark
.PARAMETER SourceDir
    Source project directory. Default: parent of scripts/
.EXAMPLE
    .\deploy.ps1
    .\deploy.ps1 -InstallDir D:\ai-benchmark
#>

param(
    [string]$InstallDir = "C:\ai-benchmark",
    [string]$SourceDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $SourceDir) {
    $SourceDir = Split-Path -Parent $PSScriptRoot
    if (-not (Test-Path "$SourceDir\pyproject.toml")) {
        $SourceDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
    }
}

$VenvDir = Join-Path $InstallDir "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$TmpDir = Join-Path $VenvDir "tmp"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " AI Benchmark Pipeline — Deploy" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Install dir : $InstallDir"
Write-Host " Source      : $SourceDir"
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── Validate venv exists ──
if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: Venv not found at $VenvDir" -ForegroundColor Red
    Write-Host "  Run install.ps1 first for initial setup."
    exit 1
}

# ── Backup production database ──
Write-Host "[1/4] Backing up database..." -ForegroundColor Yellow
& "$PSScriptRoot\backup.ps1" -InstallDir $InstallDir

# ── Build wheel ──
Write-Host ""
Write-Host "[2/4] Building wheel..." -ForegroundColor Yellow
if (Test-Path $TmpDir) { Remove-Item $TmpDir -Recurse -Force }
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
& "$VenvPython" -c "import sys; sys.exit(0)" 2>&1 | Out-Null
# Use system Python for build (venv may not have build tools)
$BuildPython = "C:\Python314\python.exe"
if (-not (Test-Path $BuildPython)) {
    $BuildPython = (Get-Command python -ErrorAction SilentlyContinue).Source
}
& $BuildPython -m build --wheel --outdir $TmpDir $SourceDir 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: wheel build failed" -ForegroundColor Red
    exit 1
}

$WheelFile = (Get-ChildItem -Path $TmpDir -Filter "*.whl" | Select-Object -First 1).FullName
Write-Host "  Built $([System.IO.Path]::GetFileName($WheelFile))"

# ── Install wheel into venv ──
Write-Host ""
Write-Host "[3/4] Installing into venv..." -ForegroundColor Yellow
& $VenvPip install $WheelFile --force-reinstall --quiet 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install failed" -ForegroundColor Red
    exit 1
}
Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  Package upgraded successfully"

# ── Copy updated bin scripts ──
Write-Host ""
Write-Host "[4/4] Updating bin scripts..." -ForegroundColor Yellow
$binSource = Join-Path $SourceDir "scripts\bin"
if (Test-Path $binSource) {
    Get-ChildItem -Path $binSource -Filter "*.bat" | ForEach-Object {
        Copy-Item $_.FullName -Destination (Join-Path $InstallDir "bin") -Force
        Write-Host "  Updated bin\$($_.Name)"
    }
}

# ── Verify ──
Write-Host ""
Write-Host "Verifying installation..." -ForegroundColor Yellow
& $VenvPython -m ai_benchmark.cli check-config 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: check-config returned non-zero exit code" -ForegroundColor Yellow
} else {
    Write-Host "  Verification passed"
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Deploy complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
