#Requires -Version 5.1
<#
.SYNOPSIS
    AI Benchmark Installer - install subcommand.
.DESCRIPTION
    Creates a new AI Benchmark instance: venv, wheel, substituted .env and
    bin scripts, initialized database, version tracking, and optional
    scheduled task. Supports arbitrary install paths and multiple
    concurrent instances.
.PARAMETER Path
    Target installation directory (required).
.PARAMETER Name
    Instance name for the registry. Defaults to the leaf directory name.
.PARAMETER PythonPath
    Path to python.exe. If omitted, auto-detects Python >= 3.12 via the
    py launcher or PATH.
.PARAMETER Port
    API port for the eval server. Default: 8100.
.PARAMETER TaskTime
    Daily collection time (HH:MM). Default: 05:00.
.PARAMETER NoSchedule
    Skip scheduled task creation.
.PARAMETER Force
    Allow reinstalling to an existing instance path. Preserves config.
.PARAMETER DryRun
    Print what would happen without making changes.
.EXAMPLE
    .\Install-Instance.ps1 -Path C:\ai-benchmark
    .\Install-Instance.ps1 -Path D:\staging -Name staging -Port 9200 -NoSchedule
    .\Install-Instance.ps1 -Path C:\ai-benchmark -DryRun
#>

param(
    [Parameter(Mandatory)][string]$Path,
    [string]$Name = "",
    [string]$PythonPath = "",
    [int]$Port = 8100,
    [string]$TaskTime = "05:00",
    [switch]$NoSchedule,
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# ---- Preamble ----

Import-Module (Join-Path $PSScriptRoot "module.psm1") -Force

# Derive source directory (project root) from script location
$SourceDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not (Test-Path (Join-Path $SourceDir "pyproject.toml"))) {
    Write-Host "ERROR: Cannot find pyproject.toml at $SourceDir" -ForegroundColor Red
    Write-Host "  Install-Instance.ps1 must be located at <project>/scripts/installer/"
    exit 1
}

# Default instance name to leaf directory
if (-not $Name) {
    $Name = Split-Path -Leaf $Path
}

# Normalize path to absolute
$Path = [System.IO.Path]::GetFullPath($Path)

# Forward-slash variant for SQLite URLs in .env
$ForwardSlashPath = $Path -replace '\\', '/'

# Enable dry-run mode
if ($DryRun) {
    Set-DryRunMode -Enabled $true
}

# ---- Python Auto-Detection ----

function Find-Python {
    <#
    .SYNOPSIS
        Find a suitable Python >= 3.12. Tries py launcher, then PATH.
    .OUTPUTS
        Full path to python.exe, or $null.
    #>
    # Try py launcher with specific versions (most reliable on Windows)
    $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        foreach ($ver in @("-3.14", "-3.13", "-3.12")) {
            try {
                $candidate = & py $ver -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Path $candidate)) {
                    $candidate = $candidate.Trim()
                    if (Test-PythonVersion -PythonPath $candidate) {
                        return $candidate
                    }
                }
            } catch { }
        }
    }

    # Try python3 / python on PATH
    foreach ($cmd in @("python3", "python")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) {
            if (Test-PythonVersion -PythonPath $found.Source) {
                return $found.Source
            }
        }
    }

    return $null
}

# ---- Banner ----

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " AI Benchmark Installer - Install" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Instance    : $Name"
Write-Host " Install dir : $Path"
Write-Host " Port        : $Port"
Write-Host " Source      : $SourceDir"
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ================================================================
# Step 1: Pre-flight Checks
# ================================================================

Write-Host "[1/8] Running pre-flight checks..." -ForegroundColor Yellow

# 1a. Resolve Python
$resolvedPython = $PythonPath
if (-not $resolvedPython) {
    Write-Host "  Auto-detecting Python >= 3.12..."
    $resolvedPython = Find-Python
    if (-not $resolvedPython) {
        Write-Host "FAIL: Could not find Python >= 3.12" -ForegroundColor Red
        Write-Host "  Searched: py -3.14, py -3.13, py -3.12, python3, python"
        Write-Host "  Use -PythonPath to specify the correct path."
        exit 1
    }
    Write-Host "  Found: $resolvedPython" -ForegroundColor Green
} else {
    if (-not (Test-PythonVersion -PythonPath $resolvedPython)) {
        exit 1
    }
    Write-Host "  Python OK: $resolvedPython"
}

# 1b. pip
if (-not (Test-PipAvailable -PythonPath $resolvedPython)) {
    Write-Host "FAIL: pip not available via $resolvedPython" -ForegroundColor Red
    exit 1
}
Write-Host "  pip OK"

# 1c. build module
if (-not (Test-BuildModule -PythonPath $resolvedPython)) {
    Write-Host "FAIL: build module not available" -ForegroundColor Red
    Write-Host "  Run: $resolvedPython -m pip install build"
    exit 1
}
Write-Host "  build module OK"

# 1d. Directory writable
if (-not (Test-DirectoryWritable -Path $Path)) {
    exit 1
}
Write-Host "  Directory writable OK"

# 1e. Instance collision
$existingName = Test-InstanceExists -Path $Path
if ($existingName) {
    if (-not $Force) {
        Write-Host "FAIL: Instance '$existingName' already registered at $Path" -ForegroundColor Red
        Write-Host "  Use -Force to reinstall, or use the upgrade subcommand."
        exit 1
    }
    Write-Host "  WARNING: Reinstalling over existing instance '$existingName' (-Force)" -ForegroundColor Yellow
}

# 1f. Port collision
if (-not (Test-PortAvailable -Port $Port -ExcludeName $Name)) {
    if (-not $Force) {
        exit 1
    }
    Write-Host "  WARNING: Port collision ignored (-Force)" -ForegroundColor Yellow
}
Write-Host "  Port $Port OK"

# 1g. Elevation
if (-not $NoSchedule) {
    $isAdmin = Test-Elevation
    if (-not $isAdmin) {
        Write-Host "  Continuing without elevation - task creation may fail." -ForegroundColor Yellow
    }
}

Write-Host "  All pre-flight checks passed." -ForegroundColor Green
Write-Host ""

# ================================================================
# Step 2: Create Directory Structure
# ================================================================

Write-Host "[2/8] Creating directory structure..." -ForegroundColor Yellow

$dirs = @("bin", "config", "data", "artifacts", "logs", "backup")
foreach ($dir in $dirs) {
    $dirPath = Join-Path $Path $dir
    Invoke-InstallerAction -Description "Create directory $dirPath" -Action {
        if (-not (Test-Path $dirPath)) {
            New-Item -ItemType Directory -Path $dirPath -Force | Out-Null
        }
    }
}

Write-InstallerLog -InstallDir $Path -Message "Install started: Name=$Name, Path=$Path, Port=$Port, Python=$resolvedPython"
Write-Host ""

# ================================================================
# Step 3: Generate .env from Template
# ================================================================

Write-Host "[3/8] Generating configuration..." -ForegroundColor Yellow

$envFile = Join-Path $Path "config\.env"
if (-not (Test-Path $envFile)) {
    Invoke-InstallerAction -Description "Generate config\.env from template" -Action {
        Invoke-TemplateSubstitution `
            -TemplatePath (Join-Path $SourceDir "scripts\env.template") `
            -OutputPath $envFile `
            -Tokens @{
                INSTALL_DIR   = $ForwardSlashPath
                API_PORT      = [string]$Port
                INSTANCE_NAME = $Name
            }
    }
    Write-Host "  ** Edit $envFile to add API keys **" -ForegroundColor Magenta
} else {
    Write-Host "  config\.env already exists - preserving existing configuration"
}
Write-Host ""

# ================================================================
# Step 4: Generate Bin Scripts from Template
# ================================================================

Write-Host "[4/8] Generating bin scripts..." -ForegroundColor Yellow

$binSpecs = @(
    @{
        FileName           = "collect.bat"
        CLI_COMMAND        = "collect"
        LOG_PREFIX         = "collect_$Name"
        SCRIPT_DESCRIPTION = "Collection runner"
    },
    @{
        FileName           = "run.bat"
        CLI_COMMAND        = "run"
        LOG_PREFIX         = "daemon_$Name"
        SCRIPT_DESCRIPTION = "Daemon mode (APScheduler)"
    },
    @{
        FileName           = "serve.bat"
        CLI_COMMAND        = "eval serve"
        LOG_PREFIX         = "serve_$Name"
        SCRIPT_DESCRIPTION = "Eval API server"
    },
    @{
        FileName           = "backfill.bat"
        CLI_COMMAND        = "collect --since %~1"
        LOG_PREFIX         = "backfill_$Name"
        SCRIPT_DESCRIPTION = "Historical backfill runner"
    }
)

$templatePath = Join-Path $SourceDir "scripts\bin\bin_template.bat"
foreach ($spec in $binSpecs) {
    $outputPath = Join-Path $Path "bin\$($spec.FileName)"
    Invoke-InstallerAction -Description "Generate bin\$($spec.FileName)" -Action {
        Invoke-TemplateSubstitution `
            -TemplatePath $templatePath `
            -OutputPath $outputPath `
            -Tokens @{
                INSTALL_DIR        = $Path
                CLI_COMMAND        = $spec.CLI_COMMAND
                LOG_PREFIX         = $spec.LOG_PREFIX
                SCRIPT_DESCRIPTION = $spec.SCRIPT_DESCRIPTION
            }
    }
}
Write-Host ""

# ================================================================
# Step 5: Create Venv, Build Wheel, Install
# ================================================================

Write-Host "[5/8] Installing Python package into venv..." -ForegroundColor Yellow

$VenvDir    = Join-Path $Path "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip    = Join-Path $VenvDir "Scripts\pip.exe"
$TmpDir     = Join-Path $VenvDir "tmp"

# Create venv
Invoke-InstallerAction -Description "Create virtual environment at $VenvDir" -Action {
    if (-not (Test-Path $VenvPython)) {
        Write-Host "    Creating venv..."
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $resolvedPython -m venv $VenvDir 2>&1 | Out-Null
        $ErrorActionPreference = $prevEAP
        if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
    } else {
        Write-Host "    Venv already exists - reusing"
    }
}

# Build wheel (using system Python, not venv)
Invoke-InstallerAction -Description "Build wheel from $SourceDir" -Action {
    if (Test-Path $TmpDir) { Remove-Item $TmpDir -Recurse -Force }
    New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
    Write-Host "    Building wheel..."
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $resolvedPython -m build --wheel --outdir $TmpDir $SourceDir 2>&1 | Out-Null
    $ErrorActionPreference = $prevEAP
    if ($LASTEXITCODE -ne 0) { throw "wheel build failed" }
}

# Install wheel into venv
Invoke-InstallerAction -Description "Install wheel into venv" -Action {
    $whl = (Get-ChildItem -Path $TmpDir -Filter "*.whl" | Select-Object -First 1).FullName
    if (-not $whl) { throw "No .whl file found in $TmpDir" }
    Write-Host "    Installing $([System.IO.Path]::GetFileName($whl))..."
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $VenvPip install $whl --force-reinstall --quiet 2>&1 | Out-Null
    $ErrorActionPreference = $prevEAP
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    # Cleanup
    Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "  Package installed into venv" -ForegroundColor Green
Write-Host ""

# ================================================================
# Step 6: Initialize Database
# ================================================================

Write-Host "[6/8] Initializing database..." -ForegroundColor Yellow

Invoke-InstallerAction -Description "Initialize database at data\ai_benchmark.db" -Action {
    $env:AI_BENCH_DATABASE_URL = "sqlite+aiosqlite:///$ForwardSlashPath/data/ai_benchmark.db"
    Push-Location $Path
    try {
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $VenvPython -m ai_benchmark.cli init-db 2>&1
        $ErrorActionPreference = $prevEAP
        if ($LASTEXITCODE -ne 0) { throw "Database initialization failed" }
        Write-Host "    Database ready"
    } finally {
        Pop-Location
    }
}
Write-Host ""

# ================================================================
# Step 7: Post-Install Bookkeeping
# ================================================================

Write-Host "[7/8] Validating and recording installation..." -ForegroundColor Yellow

# Validate config
Invoke-InstallerAction -Description "Validate configuration (check-config)" -Action {
    $env:AI_BENCH_DATABASE_URL = "sqlite+aiosqlite:///$ForwardSlashPath/data/ai_benchmark.db"
    Push-Location $Path
    try {
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $VenvPython -m ai_benchmark.cli check-config 2>&1
        $ErrorActionPreference = $prevEAP
        if ($LASTEXITCODE -ne 0) {
            Write-Host "    WARNING: check-config returned non-zero" -ForegroundColor Yellow
        }
    } finally {
        Pop-Location
    }
}

# Get version info
$pythonVersionOutput = & $resolvedPython --version 2>&1
$pythonVersion = if ($pythonVersionOutput -match 'Python (.+)') { $Matches[1] } else { "unknown" }

$packageVersion = "unknown"
$pyprojectContent = Get-Content (Join-Path $SourceDir "pyproject.toml") -Raw
if ($pyprojectContent -match '(?m)^version\s*=\s*"([^"]+)"') {
    $packageVersion = $Matches[1]
}

# Write version.json
Invoke-InstallerAction -Description "Write config\version.json" -Action {
    Write-VersionJson -InstallDir $Path `
        -PackageVersion $packageVersion `
        -PythonVersion $pythonVersion
}

# Register in instance registry
$taskName = if ($NoSchedule) { "" } else { "AIBenchmark_${Name}_Collect" }

Invoke-InstallerAction -Description "Register instance '$Name' in registry" -Action {
    Set-InstanceEntry -Name $Name -Data @{
        path              = $Path
        type              = "production"
        version           = $packageVersion
        install_date      = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
        last_upgrade_date = ""
        api_port          = $Port
        task_name         = $taskName
    }
}

Write-InstallerLog -InstallDir $Path -Message "Version: package=$packageVersion, python=$pythonVersion, installer=$((Get-Module -Name module).Version)"
Write-Host ""

# ================================================================
# Step 8: Create Scheduled Task
# ================================================================

if (-not $NoSchedule) {
    Write-Host "[8/8] Registering scheduled task..." -ForegroundColor Yellow
    $taskName = "AIBenchmark_${Name}_Collect"

    Invoke-InstallerAction -Description "Register scheduled task '$taskName' at $TaskTime" -Action {
        try {
            $action = New-ScheduledTaskAction -Execute "cmd.exe" `
                -Argument "/c `"$(Join-Path $Path 'bin\collect.bat')`""
            $trigger = New-ScheduledTaskTrigger -Daily -At $TaskTime
            $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
            Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
                -Settings $settings -RunLevel Highest -Force | Out-Null
            Write-Host "  Task '$taskName' registered: daily at $TaskTime"
        } catch {
            Write-Host "  WARNING: Could not create scheduled task: $_" -ForegroundColor Yellow
            Write-Host "  Create it manually from an admin Command Prompt:"
            Write-Host "  schtasks /create /tn `"$taskName`" /tr `"cmd.exe /c $(Join-Path $Path 'bin\collect.bat')`" /sc daily /st $TaskTime /rl highest /f"
        }
    }

    # One-time migration: clean up legacy fixed-name task
    Invoke-InstallerAction -Description "Remove legacy AIBenchmarkCollect task (if present)" -Action {
        Unregister-ScheduledTask -TaskName "AIBenchmarkCollect" -Confirm:$false -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "[8/8] Skipping scheduled task (-NoSchedule)" -ForegroundColor Yellow
}

# ================================================================
# Done
# ================================================================

Write-InstallerLog -InstallDir $Path -Message "Install completed successfully"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Installation complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host " Instance     : $Name"
Write-Host " Install dir  : $Path"
Write-Host " Venv         : $Path\venv\"
Write-Host " Config       : $Path\config\.env"
Write-Host " Database     : $Path\data\ai_benchmark.db"
Write-Host " API Port     : $Port"
Write-Host " Logs         : $Path\logs\"
Write-Host " Artifacts    : $Path\artifacts\"
Write-Host ""
Write-Host " Next steps:" -ForegroundColor Cyan
Write-Host "   1. Edit $Path\config\.env (add API keys)"
Write-Host "   2. Test: $Path\bin\collect.bat"
if (-not $NoSchedule) {
    Write-Host "   3. Check: schtasks /query /tn `"$taskName`""
}
Write-Host ""
