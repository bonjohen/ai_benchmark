#Requires -Version 5.1
<#
.SYNOPSIS
    AI Benchmark Installer - status subcommand.
.DESCRIPTION
    Displays detailed status for a specific instance: version info,
    database size, last collection time, scheduled task state, and
    whether the eval server is running.
.PARAMETER Name
    Instance name (from registry).
.PARAMETER Path
    Instance installation path (alternative to -Name).
.EXAMPLE
    .\Get-InstanceStatus.ps1 -Name prod
    .\Get-InstanceStatus.ps1 -Path C:\ai-benchmark
#>

param(
    [string]$Name = "",
    [string]$Path = ""
)

Import-Module (Join-Path $PSScriptRoot "module.psm1") -Force

# ---- Resolve instance ----

if (-not $Name -and -not $Path) {
    Write-Host "ERROR: Specify -Name or -Path to identify the instance." -ForegroundColor Red
    Write-Host "  Example: ai-bench-installer.bat status -Name prod"
    exit 1
}

$entry = $null
$instanceName = $Name

if ($Name) {
    $entry = Find-InstanceByName -Name $Name
    if (-not $entry) {
        Write-Host "ERROR: Instance '$Name' not found in registry." -ForegroundColor Red
        Write-Host "  Run 'ai-bench-installer.bat list' to see registered instances."
        exit 1
    }
    $Path = $entry.path
} else {
    $Path = [System.IO.Path]::GetFullPath($Path)
    $instanceName = Test-InstanceExists -Path $Path
    if (-not $instanceName) {
        Write-Host "ERROR: No instance registered at '$Path'." -ForegroundColor Red
        Write-Host "  Run 'ai-bench-installer.bat list' to see registered instances."
        exit 1
    }
    $entry = Find-InstanceByName -Name $instanceName
}

# ---- Gather status info ----

# Version
$versionInfo = Read-VersionJson -InstallDir $Path
$packageVersion = if ($versionInfo) { $versionInfo.package_version } else { "unknown" }
$pythonVersion = if ($versionInfo) { $versionInfo.python_version } else { "unknown" }
$installerVersion = if ($versionInfo) { $versionInfo.installer_version } else { "unknown" }
$installTimestamp = if ($versionInfo) { $versionInfo.install_timestamp } else { "unknown" }

# Database
$dbPath = Join-Path $Path "data\ai_benchmark.db"
$dbSize = "(not found)"
if (Test-Path $dbPath) {
    $sizeBytes = (Get-Item $dbPath).Length
    if ($sizeBytes -gt 1MB) {
        $dbSize = "{0:N1} MB" -f ($sizeBytes / 1MB)
    } else {
        $dbSize = "{0:N0} KB" -f ($sizeBytes / 1KB)
    }
}

# Last collection log
$logsDir = Join-Path $Path "logs"
$lastCollection = "(no logs found)"
if (Test-Path $logsDir) {
    $latestLog = Get-ChildItem -Path $logsDir -Filter "collect_*.log" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($latestLog) {
        $lastCollection = $latestLog.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
    }
}

# Scheduled task
$taskState = "(no task)"
$taskName = $entry.task_name
if ($taskName) {
    try {
        $taskOutput = schtasks /query /tn $taskName /fo LIST 2>&1
        if ($LASTEXITCODE -eq 0) {
            $statusLine = $taskOutput | Where-Object { $_ -match '^\s*Status:\s*(.+)' }
            if ($statusLine -and $Matches[1]) {
                $taskState = $Matches[1].Trim()
            } else {
                $taskState = "Registered"
            }
        } else {
            $taskState = "(not registered)"
        }
    } catch {
        $taskState = "(query failed)"
    }
}

# Eval server
$port = $entry.api_port
$serverState = "(not checked)"
if ($port) {
    try {
        $result = Test-NetConnection -ComputerName 127.0.0.1 -Port $port -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        if ($result.TcpTestSucceeded) {
            $serverState = "Running on port $port"
        } else {
            $serverState = "Not running (port $port closed)"
        }
    } catch {
        $serverState = "Could not check port $port"
    }
}

# Venv
$venvPython = Join-Path $Path "venv\Scripts\python.exe"
$venvState = if (Test-Path $venvPython) { "OK" } else { "Missing" }

# ---- Display ----

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Instance Status: $instanceName" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Path              : $Path"
Write-Host "  Type              : $($entry.type)"
Write-Host ""
Write-Host "  Package version   : $packageVersion"
Write-Host "  Python version    : $pythonVersion"
Write-Host "  Installer version : $installerVersion"
Write-Host "  Install date      : $installTimestamp"
Write-Host ""
Write-Host "  Database          : $dbSize"
Write-Host "  Venv              : $venvState"
Write-Host "  Last collection   : $lastCollection"
Write-Host ""
Write-Host "  Scheduled task    : $(if ($taskName) { $taskName } else { '(none)' })"
Write-Host "  Task state        : $taskState"
Write-Host "  Eval server       : $serverState"
Write-Host ""
