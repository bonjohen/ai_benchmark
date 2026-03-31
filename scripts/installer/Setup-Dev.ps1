#Requires -Version 5.1
<#
.SYNOPSIS
    AI Benchmark Installer - dev-setup subcommand.
.DESCRIPTION
    Sets up the development environment: editable pip install with dev
    extras, .env from dev template, database init, and registry entry.
    Must be run from the project directory.
.PARAMETER PythonPath
    Path to python.exe. If omitted, auto-detects Python >= 3.12.
.PARAMETER DryRun
    Print what would happen without making changes.
.EXAMPLE
    .\Setup-Dev.ps1
    .\Setup-Dev.ps1 -PythonPath C:\Python314\python.exe
#>

param(
    [string]$PythonPath = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Import-Module (Join-Path $PSScriptRoot "module.psm1") -Force

# Derive project directory from script location
$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not (Test-Path (Join-Path $ProjectDir "pyproject.toml"))) {
    Write-Host "ERROR: Cannot find pyproject.toml at $ProjectDir" -ForegroundColor Red
    exit 1
}

$ForwardSlashPath = $ProjectDir -replace '\\', '/'

if ($DryRun) {
    Set-DryRunMode -Enabled $true
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " AI Benchmark - Dev Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Project : $ProjectDir"
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ---- Find Python ----

Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow

$resolvedPython = $PythonPath
if (-not $resolvedPython) {
    # Auto-detect
    $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        foreach ($ver in @("-3.14", "-3.13", "-3.12")) {
            try {
                $candidate = & py $ver -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Path $candidate.Trim())) {
                    $candidate = $candidate.Trim()
                    if (Test-PythonVersion -PythonPath $candidate) {
                        $resolvedPython = $candidate
                        break
                    }
                }
            } catch { }
        }
    }
    if (-not $resolvedPython) {
        foreach ($cmd in @("python3", "python")) {
            $found = Get-Command $cmd -ErrorAction SilentlyContinue
            if ($found -and (Test-PythonVersion -PythonPath $found.Source)) {
                $resolvedPython = $found.Source
                break
            }
        }
    }
    if (-not $resolvedPython) {
        Write-Host "FAIL: Could not find Python >= 3.12" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Found: $resolvedPython"
} else {
    if (-not (Test-PythonVersion -PythonPath $resolvedPython)) { exit 1 }
    Write-Host "  Python OK: $resolvedPython"
}
Write-Host ""

# ---- Editable install ----

Write-Host "[2/4] Installing package (editable + dev extras)..." -ForegroundColor Yellow

Invoke-InstallerAction -Description "pip install -e '.[dev]'" -Action {
    Push-Location $ProjectDir
    try {
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $resolvedPython -m pip install -e ".[dev]" --quiet 2>&1 | Out-Null
        $ErrorActionPreference = $prevEAP
        if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
        Write-Host "  Installed ai_benchmark in editable mode"
    } finally {
        Pop-Location
    }
}
Write-Host ""

# ---- Create .env from template ----

Write-Host "[3/4] Setting up .env..." -ForegroundColor Yellow

$envFile = Join-Path $ProjectDir ".env"
if (-not (Test-Path $envFile)) {
    Invoke-InstallerAction -Description "Generate .env from env.dev.template" -Action {
        Invoke-TemplateSubstitution `
            -TemplatePath (Join-Path $ProjectDir "scripts\env.dev.template") `
            -OutputPath $envFile `
            -Tokens @{
                INSTALL_DIR = $ForwardSlashPath
            }
    }
    Write-Host "  ** Edit .env to add API keys **" -ForegroundColor Magenta
} else {
    Write-Host "  .env already exists - skipping"
}
Write-Host ""

# ---- Initialize database ----

Write-Host "[4/4] Initializing database..." -ForegroundColor Yellow

Invoke-InstallerAction -Description "Initialize database" -Action {
    Push-Location $ProjectDir
    try {
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $resolvedPython -m ai_benchmark.cli init-db 2>&1
        $ErrorActionPreference = $prevEAP
        if ($LASTEXITCODE -ne 0) { throw "Database initialization failed" }
        Write-Host "  Database ready"
    } finally {
        Pop-Location
    }
}

# ---- Register as dev instance ----

$packageVersion = "unknown"
$pyprojectContent = Get-Content (Join-Path $ProjectDir "pyproject.toml") -Raw
if ($pyprojectContent -match '(?m)^version\s*=\s*"([^"]+)"') {
    $packageVersion = $Matches[1]
}

$devName = "dev"
Invoke-InstallerAction -Description "Register dev instance in registry" -Action {
    Set-InstanceEntry -Name $devName -Data @{
        path              = $ProjectDir
        type              = "development"
        version           = $packageVersion
        install_date      = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
        last_upgrade_date = ""
        api_port          = 8100
        task_name         = ""
        task_time         = ""
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Dev setup complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host " Project : $ProjectDir"
Write-Host " .env    : $envFile"
Write-Host ""
Write-Host " Next steps:" -ForegroundColor Cyan
Write-Host "   1. Edit .env to add API keys"
Write-Host "   2. ai-benchmark check-config"
Write-Host "   3. ai-benchmark eval serve"
Write-Host ""
