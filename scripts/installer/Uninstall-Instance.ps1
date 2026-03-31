#Requires -Version 5.1
<#
.SYNOPSIS
    AI Benchmark Installer - uninstall subcommand.
.DESCRIPTION
    Removes an instance: deregisters from the instance registry,
    removes the scheduled task, and optionally deletes files.
    By default keeps data/ and backup/ directories.
.PARAMETER Name
    Instance name (from registry).
.PARAMETER Path
    Instance installation path (alternative to -Name).
.PARAMETER KeepData
    Preserve data/ and backup/ directories (default behavior without -Purge).
.PARAMETER Purge
    Delete the entire installation directory including data.
.PARAMETER DryRun
    Print what would happen without making changes.
.EXAMPLE
    .\Uninstall-Instance.ps1 -Name prod
    .\Uninstall-Instance.ps1 -Name staging -Purge
    .\Uninstall-Instance.ps1 -Path C:\ai-benchmark -KeepData
#>

param(
    [string]$Name = "",
    [string]$Path = "",
    [switch]$KeepData,
    [switch]$Purge,
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
    $entry = Find-InstanceByName -Name $instanceName
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Yellow
Write-Host " AI Benchmark Installer - Uninstall" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Yellow
Write-Host " Instance : $instanceName"
Write-Host " Path     : $Path"
Write-Host " Mode     : $(if ($Purge) { 'PURGE (delete everything)' } else { 'Selective (keep data)' })"
Write-Host "============================================" -ForegroundColor Yellow
Write-Host ""

# ---- Remove scheduled task ----

$taskName = $entry.task_name
if ($taskName) {
    Invoke-InstallerAction -Description "Remove scheduled task '$taskName'" -Action {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    }
}

# ---- Remove files ----

if ($Purge) {
    # Delete entire directory
    Invoke-InstallerAction -Description "Delete entire directory $Path" -Action {
        if (Test-Path $Path) {
            Remove-Item $Path -Recurse -Force
        }
    }
} else {
    # Selective removal: keep data/ and backup/, remove venv/, bin/, config/, artifacts/, logs/
    $removeDirs = @("venv", "bin", "config", "artifacts", "logs")
    if (-not $KeepData) {
        # Default: also keep data/ and backup/
        # KeepData is the default behavior — -Purge is the override
    }

    foreach ($dir in $removeDirs) {
        $dirPath = Join-Path $Path $dir
        if (Test-Path $dirPath) {
            Invoke-InstallerAction -Description "Remove $dir\" -Action {
                Remove-Item $dirPath -Recurse -Force
            }
        }
    }

    Write-Host "  Preserved: data\, backup\"
}

# ---- Deregister from registry ----

Invoke-InstallerAction -Description "Remove '$instanceName' from instance registry" -Action {
    Remove-InstanceEntry -Name $instanceName | Out-Null
}

Write-Host ""
Write-Host "Instance '$instanceName' uninstalled." -ForegroundColor Green
if (-not $Purge) {
    Write-Host "  Data preserved at: $Path\data\"
    Write-Host "  Backups preserved at: $Path\backup\"
    Write-Host "  To fully remove: Remove-Item '$Path' -Recurse -Force"
}
Write-Host ""
