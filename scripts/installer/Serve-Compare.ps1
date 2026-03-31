#Requires -Version 5.1
<#
.SYNOPSIS
    AI Benchmark Installer - serve-compare subcommand.
.DESCRIPTION
    Launches two eval servers side by side in separate windows and opens
    both in the default browser. Replaces the hardcoded serve_both.bat.
.PARAMETER Instances
    Comma-separated pair of instance names, e.g. "prod,dev".
.EXAMPLE
    .\Serve-Compare.ps1 -Instances prod,dev
#>

param(
    [string]$Instances = ""
)

$ErrorActionPreference = "Stop"

Import-Module (Join-Path $PSScriptRoot "module.psm1") -Force

if (-not $Instances) {
    Write-Host "ERROR: Specify two instance names: -Instances prod,dev" -ForegroundColor Red
    exit 1
}

$names = $Instances -split ','
if ($names.Count -ne 2) {
    Write-Host "ERROR: Exactly two instance names required (comma-separated)." -ForegroundColor Red
    exit 1
}

$name1 = $names[0].Trim()
$name2 = $names[1].Trim()

$entry1 = Find-InstanceByName -Name $name1
$entry2 = Find-InstanceByName -Name $name2

if (-not $entry1) {
    Write-Host "ERROR: Instance '$name1' not found in registry." -ForegroundColor Red
    exit 1
}
if (-not $entry2) {
    Write-Host "ERROR: Instance '$name2' not found in registry." -ForegroundColor Red
    exit 1
}

$path1 = $entry1.path
$path2 = $entry2.path
$port1 = $entry1.api_port
$port2 = $entry2.api_port

if (-not $port1) { $port1 = 8100 }
if (-not $port2) { $port2 = 8100 }

# ---- Resolve Python for each instance ----

function Get-InstancePython {
    param([string]$InstancePath, [string]$InstanceType)

    $venvPython = Join-Path $InstancePath "venv\Scripts\python.exe"
    if (Test-Path $venvPython) { return $venvPython }

    # Dev instances use system Python
    if ($InstanceType -eq "development") {
        $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
        if ($pyLauncher) {
            foreach ($ver in @("-3.14", "-3.13", "-3.12")) {
                try {
                    $candidate = & py $ver -c "import sys; print(sys.executable)" 2>$null
                    if ($LASTEXITCODE -eq 0 -and $candidate) {
                        return $candidate.Trim()
                    }
                } catch { }
            }
        }
        $found = Get-Command "python" -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }

    return $null
}

$python1 = Get-InstancePython -InstancePath $path1 -InstanceType $entry1.type
$python2 = Get-InstancePython -InstancePath $path2 -InstanceType $entry2.type

if (-not $python1) {
    Write-Host "ERROR: Cannot find Python for instance '$name1' at $path1" -ForegroundColor Red
    exit 1
}
if (-not $python2) {
    Write-Host "ERROR: Cannot find Python for instance '$name2' at $path2" -ForegroundColor Red
    exit 1
}

# ---- Determine .env paths ----

$envFile1 = Join-Path $path1 "config\.env"
if (-not (Test-Path $envFile1)) {
    $envFile1 = Join-Path $path1 ".env"
}

$envFile2 = Join-Path $path2 "config\.env"
if (-not (Test-Path $envFile2)) {
    $envFile2 = Join-Path $path2 ".env"
}

# ---- Launch servers ----

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " AI Benchmark - Serve Compare" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " $name1 : http://127.0.0.1:$port1  ($path1)"
Write-Host " $name2 : http://127.0.0.1:$port2  ($path2)"
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$cmd1 = "cd /d `"$path1`" && set AI_BENCH_ENV_FILE=$envFile1 && `"$python1`" -m ai_benchmark.cli eval serve --port $port1"
$cmd2 = "cd /d `"$path2`" && set AI_BENCH_ENV_FILE=$envFile2 && `"$python2`" -m ai_benchmark.cli eval serve --port $port2"

Start-Process cmd -ArgumentList "/k", "title AI Benchmark - $($name1.ToUpper()) ($port1) && $cmd1"
Start-Process cmd -ArgumentList "/k", "title AI Benchmark - $($name2.ToUpper()) ($port2) && $cmd2"

# Give servers time to start
Start-Sleep -Seconds 3

# Open browser
Start-Process "http://127.0.0.1:$port1"
Start-Process "http://127.0.0.1:$port2"

Write-Host "Both servers launched. Close the server windows to stop them." -ForegroundColor Green
Write-Host ""
