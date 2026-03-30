<#
.SYNOPSIS
    AI Benchmark — Database Backup with Rotation
.DESCRIPTION
    Copies the production SQLite database to a timestamped backup file.
    Rotates old backups, keeping only the most recent $RetainCount copies.
.PARAMETER InstallDir
    Production installation directory. Default: C:\ai-benchmark
.PARAMETER RetainCount
    Number of backup files to keep. Default: 10
.EXAMPLE
    .\backup.ps1
    .\backup.ps1 -InstallDir D:\ai-benchmark -RetainCount 5
#>

param(
    [string]$InstallDir = "C:\ai-benchmark",
    [int]$RetainCount = 10
)

$ErrorActionPreference = "Stop"

$DbFile = Join-Path $InstallDir "data\ai_benchmark.db"
$BackupDir = Join-Path $InstallDir "backup"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = Join-Path $BackupDir "ai_benchmark_$Timestamp.db"

# Ensure backup directory exists
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

# Back up database
if (Test-Path $DbFile) {
    Copy-Item $DbFile -Destination $BackupFile -Force
    $size = (Get-Item $BackupFile).Length
    $sizeKB = [math]::Round($size / 1024, 1)
    Write-Host "  Backed up database ($sizeKB KB) -> $BackupFile"
} else {
    Write-Host "  No database found at $DbFile - skipping backup" -ForegroundColor Yellow
    exit 0
}

# Rotate: keep only the most recent $RetainCount backups
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
