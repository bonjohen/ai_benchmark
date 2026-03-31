#Requires -Version 5.1
<#
.SYNOPSIS
    AI Benchmark Installer - compare subcommand.
.DESCRIPTION
    Compares row counts across all database tables between two instances.
.PARAMETER Instances
    Comma-separated pair of instance names, e.g. "prod,dev".
.EXAMPLE
    .\Compare-Instances.ps1 -Instances prod,dev
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

Write-Host ""
Write-Host "Comparing databases..." -ForegroundColor Cyan
Write-Host ""

Compare-InstanceDatabases -Name1 $names[0].Trim() -Name2 $names[1].Trim()

Write-Host ""
