#Requires -Version 5.1
<#
.SYNOPSIS
    AI Benchmark Installer - backup subcommand.
.DESCRIPTION
    Creates a timestamped backup of the instance database and rotates
    old backups to keep only the most recent copies.
.PARAMETER Name
    Instance name (from registry).
.PARAMETER Path
    Instance installation path (alternative to -Name).
.PARAMETER RetainCount
    Number of backup files to keep. Default: 10.
.PARAMETER DryRun
    Print what would happen without making changes.
.EXAMPLE
    .\Backup-Instance.ps1 -Name prod
    .\Backup-Instance.ps1 -Path C:\ai-benchmark -RetainCount 5
#>

param(
    [string]$Name = "",
    [string]$Path = "",
    [int]$RetainCount = 10,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Import-Module (Join-Path $PSScriptRoot "module.psm1") -Force

if ($DryRun) {
    Set-DryRunMode -Enabled $true
}

# ---- Resolve instance ----

if (-not $Name -and -not $Path) {
    Write-Host "ERROR: Specify -Name or -Path to identify the instance." -ForegroundColor Red
    exit 1
}

$entry = $null
$instanceName = $Name

if ($Name) {
    $entry = Find-InstanceByName -Name $Name
    if (-not $entry) {
        Write-Host "ERROR: Instance '$Name' not found in registry." -ForegroundColor Red
        exit 1
    }
    $Path = $entry.path
} else {
    $Path = [System.IO.Path]::GetFullPath($Path)
    $instanceName = Test-InstanceExists -Path $Path
    if (-not $instanceName) {
        Write-Host "ERROR: No instance registered at '$Path'." -ForegroundColor Red
        exit 1
    }
}

# ---- Backup database ----

$DbFile = Join-Path $Path "data\ai_benchmark.db"
$BackupDir = Join-Path $Path "backup"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = Join-Path $BackupDir "ai_benchmark_$Timestamp.db"

Write-Host ""
Write-Host "Backing up instance '$instanceName'..." -ForegroundColor Cyan

# Ensure backup directory exists
Invoke-InstallerAction -Description "Ensure backup directory exists" -Action {
    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    }
}

# Copy database
if (Test-Path $DbFile) {
    Invoke-InstallerAction -Description "Backup database to $BackupFile" -Action {
        Copy-Item $DbFile -Destination $BackupFile -Force
        $size = (Get-Item $BackupFile).Length
        $sizeKB = [math]::Round($size / 1024, 1)
        Write-Host "  Database backed up ($sizeKB KB)"
    }
} else {
    Write-Host "  No database found at $DbFile - nothing to back up" -ForegroundColor Yellow
    exit 0
}

# Rotate: keep only the most recent $RetainCount backups
Invoke-InstallerAction -Description "Rotate backups (keep $RetainCount)" -Action {
    $backups = Get-ChildItem -Path $BackupDir -Filter "ai_benchmark_*.db" |
        Sort-Object Name -Descending
    $total = $backups.Count

    if ($total -gt $RetainCount) {
        $toDelete = $backups | Select-Object -Skip $RetainCount
        foreach ($old in $toDelete) {
            Remove-Item $old.FullName -Force
            Write-Host "  Rotated out: $($old.Name)"
        }
    }

    $kept = [math]::Min($total, $RetainCount)
    Write-Host "  Backups: $kept retained (max $RetainCount)"
}

Write-InstallerLog -InstallDir $Path -Message "Database backed up to $BackupFile"
Write-Host ""
