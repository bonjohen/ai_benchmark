#Requires -Version 5.1
<#
.SYNOPSIS
    AI Benchmark Installer - upgrade subcommand.
.DESCRIPTION
    Upgrades an existing instance: backs up database/config/bin scripts,
    builds and installs a new wheel, merges config (appends new keys),
    regenerates bin scripts, runs schema migration, verifies, and
    rolls back on failure.
.PARAMETER Name
    Instance name (from registry).
.PARAMETER Path
    Instance installation path (alternative to -Name).
.PARAMETER SourceDir
    Project directory containing pyproject.toml. Defaults to the
    repository root derived from script location.
.PARAMETER DryRun
    Print what would happen without making changes.
.EXAMPLE
    .\Update-Instance.ps1 -Name prod
    .\Update-Instance.ps1 -Path C:\ai-benchmark -DryRun
#>

param(
    [string]$Name = "",
    [string]$Path = "",
    [string]$SourceDir = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# ---- Preamble ----

Import-Module (Join-Path $PSScriptRoot "module.psm1") -Force

# Derive source directory
if (-not $SourceDir) {
    $SourceDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
if (-not (Test-Path (Join-Path $SourceDir "pyproject.toml"))) {
    Write-Host "ERROR: Cannot find pyproject.toml at $SourceDir" -ForegroundColor Red
    exit 1
}

if ($DryRun) {
    Set-DryRunMode -Enabled $true
}

# ================================================================
# Step 1: Resolve Instance
# ================================================================

Write-Host ""
Write-Host "[1/7] Resolving instance..." -ForegroundColor Yellow

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

$ForwardSlashPath = $Path -replace '\\', '/'

# Read current version
$currentVersion = Read-VersionJson -InstallDir $Path
$currentPkgVersion = if ($currentVersion) { $currentVersion.package_version } else { "unknown" }

# Read new package version from pyproject.toml
$newPackageVersion = "unknown"
$pyprojectContent = Get-Content (Join-Path $SourceDir "pyproject.toml") -Raw
if ($pyprojectContent -match '(?m)^version\s*=\s*"([^"]+)"') {
    $newPackageVersion = $Matches[1]
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " AI Benchmark Installer - Upgrade" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Instance    : $instanceName"
Write-Host " Install dir : $Path"
Write-Host " Current     : $currentPkgVersion"
Write-Host " New         : $newPackageVersion"
Write-Host " Source      : $SourceDir"
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Write-InstallerLog -InstallDir $Path -Message "Upgrade started: $currentPkgVersion -> $newPackageVersion from $SourceDir"

# ================================================================
# Step 2: Pre-upgrade Backup
# ================================================================

Write-Host "[2/7] Creating pre-upgrade backup..." -ForegroundColor Yellow

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $Path "backup\upgrade_$timestamp"

Invoke-InstallerAction -Description "Create backup directory $backupDir" -Action {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

# Backup database
$dbPath = Join-Path $Path "data\ai_benchmark.db"
if (Test-Path $dbPath) {
    Invoke-InstallerAction -Description "Backup database" -Action {
        Copy-Item $dbPath -Destination (Join-Path $backupDir "ai_benchmark.db") -Force
    }
} else {
    Write-Host "  No database found - skipping DB backup"
}

# Backup config
$envFile = Join-Path $Path "config\.env"
if (Test-Path $envFile) {
    Invoke-InstallerAction -Description "Backup config\.env" -Action {
        Copy-Item $envFile -Destination (Join-Path $backupDir ".env") -Force
    }
}

# Backup bin scripts
$binDir = Join-Path $Path "bin"
if (Test-Path $binDir) {
    Invoke-InstallerAction -Description "Backup bin scripts" -Action {
        Get-ChildItem -Path $binDir -Filter "*.bat" | ForEach-Object {
            Copy-Item $_.FullName -Destination $backupDir -Force
        }
    }
}

Write-Host "  Backup saved to: $backupDir"
Write-Host ""

# ================================================================
# Step 3: Build and Install Wheel
# ================================================================

Write-Host "[3/7] Building and installing package..." -ForegroundColor Yellow

$VenvDir    = Join-Path $Path "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip    = Join-Path $VenvDir "Scripts\pip.exe"
$TmpDir     = Join-Path $VenvDir "tmp"

if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: Venv not found at $VenvDir - cannot upgrade." -ForegroundColor Red
    Write-Host "  Use 'install' to create a new instance instead."
    exit 1
}

# Find Python for building (prefer system Python, fall back to venv)
$buildPython = $null
$pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
if ($pyLauncher) {
    foreach ($ver in @("-3.14", "-3.13", "-3.12")) {
        try {
            $candidate = & py $ver -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Path $candidate.Trim())) {
                $buildPython = $candidate.Trim()
                break
            }
        } catch { }
    }
}
if (-not $buildPython) {
    $buildPython = $VenvPython
}

# Build wheel
Invoke-InstallerAction -Description "Build wheel from $SourceDir" -Action {
    if (Test-Path $TmpDir) { Remove-Item $TmpDir -Recurse -Force }
    New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
    Write-Host "    Building wheel (using $buildPython)..."
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $buildPython -m build --wheel --outdir $TmpDir $SourceDir 2>&1 | Out-Null
    $ErrorActionPreference = $prevEAP
    if ($LASTEXITCODE -ne 0) { throw "wheel build failed" }
}

# Install wheel
Invoke-InstallerAction -Description "Install wheel into venv" -Action {
    $whl = (Get-ChildItem -Path $TmpDir -Filter "*.whl" | Select-Object -First 1).FullName
    if (-not $whl) { throw "No .whl file found in $TmpDir" }
    Write-Host "    Installing $([System.IO.Path]::GetFileName($whl))..."
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $VenvPip install $whl --force-reinstall --quiet 2>&1 | Out-Null
    $ErrorActionPreference = $prevEAP
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "  Package upgraded" -ForegroundColor Green
Write-Host ""

# ================================================================
# Step 4: Config Merge
# ================================================================

Write-Host "[4/7] Merging configuration..." -ForegroundColor Yellow

$envFile = Join-Path $Path "config\.env"
$templatePath = Join-Path $SourceDir "scripts\env.template"

if ((Test-Path $envFile) -and (Test-Path $templatePath)) {
    Invoke-InstallerAction -Description "Merge new config keys into .env" -Action {
        # Generate reference config from template
        $refTempFile = Join-Path $env:TEMP "ai_bench_ref_env_$timestamp.tmp"
        Invoke-TemplateSubstitution `
            -TemplatePath $templatePath `
            -OutputPath $refTempFile `
            -Tokens @{
                INSTALL_DIR   = $ForwardSlashPath
                API_PORT      = [string]$entry.api_port
                INSTANCE_NAME = $instanceName
            }

        # Parse reference keys
        $refKeys = @{}
        Get-Content $refTempFile -Encoding UTF8 | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith('#') -and $line -match '^([A-Z_]+)=(.*)$') {
                $refKeys[$Matches[1]] = $Matches[2]
            }
        }

        # Parse existing keys
        $existingKeys = @{}
        Get-Content $envFile -Encoding UTF8 | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith('#') -and $line -match '^([A-Z_]+)=') {
                $existingKeys[$Matches[1]] = $true
            }
        }

        # Find new keys
        $newKeys = @()
        foreach ($key in $refKeys.Keys) {
            if (-not $existingKeys.ContainsKey($key)) {
                $newKeys += $key
            }
        }

        if ($newKeys.Count -gt 0) {
            $appendLines = @("")
            $appendLines += "# --- NEW in $newPackageVersion ---"
            foreach ($key in ($newKeys | Sort-Object)) {
                $appendLines += "# $key=$($refKeys[$key])"
            }
            Add-Content -Path $envFile -Value ($appendLines -join "`n") -Encoding UTF8
            Write-Host "  Added $($newKeys.Count) new key(s) (commented out):"
            foreach ($key in ($newKeys | Sort-Object)) {
                Write-Host "    # $key=$($refKeys[$key])"
            }
        } else {
            Write-Host "  No new configuration keys"
        }

        Remove-Item $refTempFile -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "  No .env or template found - skipping config merge"
}
Write-Host ""

# ================================================================
# Step 5: Bin Script Regeneration (atomic)
# ================================================================

Write-Host "[5/7] Regenerating bin scripts..." -ForegroundColor Yellow

$binTmpDir = Join-Path $env:TEMP "ai_bench_bin_$timestamp"
$binTemplatePath = Join-Path $SourceDir "scripts\bin\bin_template.bat"

$binSpecs = @(
    @{
        FileName           = "collect.bat"
        CLI_COMMAND        = "collect"
        LOG_PREFIX         = "collect_$instanceName"
        SCRIPT_DESCRIPTION = "Collection runner"
    },
    @{
        FileName           = "run.bat"
        CLI_COMMAND        = "run"
        LOG_PREFIX         = "daemon_$instanceName"
        SCRIPT_DESCRIPTION = "Daemon mode (APScheduler)"
    },
    @{
        FileName           = "serve.bat"
        CLI_COMMAND        = "eval serve"
        LOG_PREFIX         = "serve_$instanceName"
        SCRIPT_DESCRIPTION = "Eval API server"
    },
    @{
        FileName           = "backfill.bat"
        CLI_COMMAND        = "collect --since %~1"
        LOG_PREFIX         = "backfill_$instanceName"
        SCRIPT_DESCRIPTION = "Historical backfill runner"
    }
)

Invoke-InstallerAction -Description "Generate bin scripts to temp directory" -Action {
    New-Item -ItemType Directory -Path $binTmpDir -Force | Out-Null
    foreach ($spec in $binSpecs) {
        $outputPath = Join-Path $binTmpDir $spec.FileName
        Invoke-TemplateSubstitution `
            -TemplatePath $binTemplatePath `
            -OutputPath $outputPath `
            -Tokens @{
                INSTALL_DIR        = $Path
                CLI_COMMAND        = $spec.CLI_COMMAND
                LOG_PREFIX         = $spec.LOG_PREFIX
                SCRIPT_DESCRIPTION = $spec.SCRIPT_DESCRIPTION
            }
    }

    # Atomic copy: all or nothing
    $binDir = Join-Path $Path "bin"
    Get-ChildItem -Path $binTmpDir -Filter "*.bat" | ForEach-Object {
        Copy-Item $_.FullName -Destination $binDir -Force
    }
    Remove-Item $binTmpDir -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host ""

# ================================================================
# Step 6: Schema Migration
# ================================================================

Write-Host "[6/7] Running schema migration..." -ForegroundColor Yellow

$migrationFailed = $false

# Check if alembic_version table exists before running migration
# (init-db creates tables via create_all without alembic tracking)
$alembicCheckScript = Join-Path $env:TEMP "ai_bench_alembic_check.py"
Set-Content -Path $alembicCheckScript -Value @"
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
r = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'").fetchone()
print('yes' if r else 'no')
c.close()
"@ -Encoding UTF8

$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$hasAlembicRaw = & $VenvPython $alembicCheckScript $dbPath 2>$null
$ErrorActionPreference = $prevEAP
Remove-Item $alembicCheckScript -Force -ErrorAction SilentlyContinue

$needsStamp = (($hasAlembicRaw | Out-String).Trim() -eq 'no')

$migrationResult = Invoke-InstallerAction -Description "Run schema migration" -Action {
    $env:AI_BENCH_DATABASE_URL = "sqlite+aiosqlite:///$ForwardSlashPath/data/ai_benchmark.db"
    Push-Location $SourceDir
    try {
        if ($needsStamp) {
            Write-Host "    Database created by init-db (no alembic tracking) - stamping head"
            $prevEAP = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            & $VenvPython -m alembic stamp head 2>&1 | Out-Null
            $ErrorActionPreference = $prevEAP
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  WARNING: alembic stamp head failed" -ForegroundColor Yellow
                return "failed"
            }
        } else {
            $prevEAP = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            & $VenvPython -m alembic upgrade head 2>&1 | Out-Null
            $ErrorActionPreference = $prevEAP
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  WARNING: Migration returned non-zero exit code" -ForegroundColor Yellow
                return "failed"
            }
        }
        Write-Host "  Migration complete"
        return "ok"
    } finally {
        Pop-Location
    }
}

if ($migrationResult -eq "failed") {
    $migrationFailed = $true
}
Write-Host ""

# ================================================================
# Step 7: Verify + Bookkeeping (or Rollback)
# ================================================================

Write-Host "[7/7] Verifying upgrade..." -ForegroundColor Yellow

$verifyFailed = $false

$verifyResult = Invoke-InstallerAction -Description "Validate configuration (check-config)" -Action {
    $env:AI_BENCH_DATABASE_URL = "sqlite+aiosqlite:///$ForwardSlashPath/data/ai_benchmark.db"
    Push-Location $Path
    try {
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $VenvPython -m ai_benchmark.cli check-config 2>&1
        $ErrorActionPreference = $prevEAP
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  WARNING: check-config returned non-zero" -ForegroundColor Yellow
            return "failed"
        }
        return "ok"
    } finally {
        Pop-Location
    }
}

if ($verifyResult -eq "failed") {
    $verifyFailed = $true
}

# Rollback if migration or verification failed
if ($migrationFailed -or $verifyFailed) {
    Write-Host ""
    Write-Host "UPGRADE FAILED - Rolling back..." -ForegroundColor Red

    # Restore database
    $backupDb = Join-Path $backupDir "ai_benchmark.db"
    if (Test-Path $backupDb) {
        Copy-Item $backupDb -Destination $dbPath -Force
        Write-Host "  Restored database from backup" -ForegroundColor Yellow
    }

    # Restore config
    $backupEnv = Join-Path $backupDir ".env"
    if (Test-Path $backupEnv) {
        Copy-Item $backupEnv -Destination $envFile -Force
        Write-Host "  Restored config\.env from backup" -ForegroundColor Yellow
    }

    # Restore bin scripts
    Get-ChildItem -Path $backupDir -Filter "*.bat" -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item $_.FullName -Destination (Join-Path $Path "bin") -Force
    }
    Write-Host "  Restored bin scripts from backup" -ForegroundColor Yellow

    Write-InstallerLog -InstallDir $Path -Message "Upgrade FAILED and rolled back. Backup: $backupDir"
    Write-Host ""
    Write-Host "Upgrade rolled back. Backup preserved at: $backupDir" -ForegroundColor Red
    exit 1
}

# Success - update bookkeeping
$pythonVersionOutput = & $VenvPython --version 2>&1
$pythonVersion = if ($pythonVersionOutput -match 'Python (.+)') { $Matches[1] } else { "unknown" }

Invoke-InstallerAction -Description "Write config\version.json" -Action {
    Write-VersionJson -InstallDir $Path `
        -PackageVersion $newPackageVersion `
        -PythonVersion $pythonVersion
}

Invoke-InstallerAction -Description "Update registry entry for '$instanceName'" -Action {
    $updatedEntry = @{
        path              = $Path
        type              = $entry.type
        version           = $newPackageVersion
        install_date      = $entry.install_date
        last_upgrade_date = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
        api_port          = $entry.api_port
        task_name         = $entry.task_name
        task_time         = $entry.task_time
    }
    Set-InstanceEntry -Name $instanceName -Data $updatedEntry
}

Write-InstallerLog -InstallDir $Path -Message "Upgrade completed: $currentPkgVersion -> $newPackageVersion"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Upgrade complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host " Instance : $instanceName"
Write-Host " Previous : $currentPkgVersion"
Write-Host " Current  : $newPackageVersion"
Write-Host " Backup   : $backupDir"
Write-Host ""
