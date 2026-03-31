#Requires -Version 5.1
<#
.SYNOPSIS
    AI Benchmark Installer - list subcommand.
.DESCRIPTION
    Reads the instance registry and displays all registered instances
    in a formatted table.
#>

param()

Import-Module (Join-Path $PSScriptRoot "module.psm1") -Force

$registry = Get-InstanceRegistry

if ($registry.Count -eq 0) {
    Write-Host ""
    Write-Host "No instances registered." -ForegroundColor Yellow
    Write-Host "  Run 'ai-bench-installer.bat install -Path <dir>' to create one."
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Host "Registered AI Benchmark Instances ($($registry.Count)):" -ForegroundColor Cyan
Write-Host ""

# Build table data
$rows = @()
foreach ($name in ($registry.Keys | Sort-Object)) {
    $entry = $registry[$name]
    $rows += [PSCustomObject]@{
        Name       = $name
        Path       = $entry.path
        Type       = $entry.type
        Version    = $entry.version
        Port       = $entry.api_port
        Task       = if ($entry.task_name) { $entry.task_name } else { "(none)" }
        Installed  = if ($entry.install_date) {
            try { (Get-Date $entry.install_date -Format "yyyy-MM-dd") } catch { $entry.install_date }
        } else { "" }
        Upgraded   = if ($entry.last_upgrade_date) {
            try { (Get-Date $entry.last_upgrade_date -Format "yyyy-MM-dd") } catch { $entry.last_upgrade_date }
        } else { "(never)" }
    }
}

$rows | Format-Table -AutoSize -Property Name, Path, Type, Version, Port, Task, Installed, Upgraded

Write-Host ""
