#Requires -Version 5.1
<#
.SYNOPSIS
    AI Benchmark Installer - shared utility module.
.DESCRIPTION
    Provides template substitution, logging, pre-flight checks, instance
    registry I/O, dry-run infrastructure, and version tracking used by
    all installer subcommands.
#>

# ─────────────────────────────────────────────────────────────────────
# Module-scope state
# ─────────────────────────────────────────────────────────────────────

$Script:DryRun = $false
$Script:InstallerVersion = "1.0.0"

# ─────────────────────────────────────────────────────────────────────
# Core: Template substitution, logging, elevation
# ─────────────────────────────────────────────────────────────────────

function Invoke-TemplateSubstitution {
    <#
    .SYNOPSIS
        Read a template file, replace {{KEY}} tokens, write output.
    .PARAMETER TemplatePath
        Path to the template file containing {{PLACEHOLDER}} tokens.
    .PARAMETER OutputPath
        Destination file path.
    .PARAMETER Tokens
        Hashtable of KEY=VALUE pairs. Each {{KEY}} in the template is
        replaced with VALUE.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$TemplatePath,
        [Parameter(Mandatory)][string]$OutputPath,
        [Parameter(Mandatory)][hashtable]$Tokens
    )

    if (-not (Test-Path $TemplatePath)) {
        throw "Template not found: $TemplatePath"
    }

    $content = Get-Content -Path $TemplatePath -Raw -Encoding UTF8

    foreach ($key in $Tokens.Keys) {
        $placeholder = "{{$key}}"
        $content = $content -replace [regex]::Escape($placeholder), $Tokens[$key]
    }

    # Verify no unreplaced placeholders remain
    $remaining = [regex]::Matches($content, '\{\{[A-Z_]+\}\}')
    if ($remaining.Count -gt 0) {
        $names = ($remaining | ForEach-Object { $_.Value }) -join ", "
        Write-Warning "Unreplaced placeholders in output: $names"
    }

    $outputDir = Split-Path -Parent $OutputPath
    if ($outputDir -and -not (Test-Path $outputDir)) {
        New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    }

    # Use .NET WriteAllText with explicit no-BOM UTF-8 encoding.
    # PowerShell 5.1's `Set-Content -Encoding UTF8` writes a BOM, which breaks
    # .bat files (cmd.exe parses the BOM as part of the first command, so
    # `@echo off` no longer takes effect).
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($OutputPath, $content, $utf8NoBom)
}

function Write-InstallerLog {
    <#
    .SYNOPSIS
        Append a timestamped entry to the installer log.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$Message
    )

    $logsDir = Join-Path $InstallDir "logs"
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    }

    $dateStamp = Get-Date -Format "yyyyMMdd"
    $logFile = Join-Path $logsDir "installer_$dateStamp.log"
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"

    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

function Test-Elevation {
    <#
    .SYNOPSIS
        Check if the current process is running with admin privileges.
    .OUTPUTS
        $true if elevated, $false otherwise. Prints a suggestion if not elevated.
    #>
    [CmdletBinding()]
    param()

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    $isAdmin = $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)

    if (-not $isAdmin) {
        Write-Host "WARNING: Not running as administrator." -ForegroundColor Yellow
        Write-Host "  Scheduled task creation requires elevation." -ForegroundColor Yellow
        Write-Host "  Run as admin:  runas /user:Administrator `"powershell -File $($MyInvocation.ScriptName)`"" -ForegroundColor Yellow
    }

    return $isAdmin
}

# ─────────────────────────────────────────────────────────────────────
# Pre-flight checks
# ─────────────────────────────────────────────────────────────────────

function Test-PythonVersion {
    <#
    .SYNOPSIS
        Verify Python >= 3.12 is available at the given path.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$PythonPath
    )

    if (-not (Test-Path $PythonPath)) {
        Write-Host "FAIL: Python not found at $PythonPath" -ForegroundColor Red
        return $false
    }

    try {
        $versionOutput = & $PythonPath --version 2>&1
        if ($versionOutput -match 'Python (\d+)\.(\d+)') {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 12) {
                return $true
            }
            Write-Host "FAIL: Python $major.$minor found, need >= 3.12" -ForegroundColor Red
            return $false
        }
        Write-Host "FAIL: Could not parse Python version from: $versionOutput" -ForegroundColor Red
        return $false
    } catch {
        Write-Host "FAIL: Error running Python: $_" -ForegroundColor Red
        return $false
    }
}

function Test-PipAvailable {
    <#
    .SYNOPSIS
        Check that pip is available via the given Python.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$PythonPath
    )

    try {
        $null = & $PythonPath -m pip --version 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Test-BuildModule {
    <#
    .SYNOPSIS
        Check that the build module is available via the given Python.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$PythonPath
    )

    try {
        $null = & $PythonPath -m build --version 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Test-DirectoryWritable {
    <#
    .SYNOPSIS
        Verify that the target directory (or its parent) is writable.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Path
    )

    $testDir = $Path
    if (-not (Test-Path $testDir)) {
        $testDir = Split-Path -Parent $testDir
        if (-not $testDir -or -not (Test-Path $testDir)) {
            Write-Host "FAIL: Parent directory does not exist: $testDir" -ForegroundColor Red
            return $false
        }
    }

    try {
        $tempFile = Join-Path $testDir ".ai_bench_write_test_$(Get-Random)"
        Set-Content -Path $tempFile -Value "test" -ErrorAction Stop
        Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
        return $true
    } catch {
        Write-Host "FAIL: Directory not writable: $testDir" -ForegroundColor Red
        return $false
    }
}

function Test-PortAvailable {
    <#
    .SYNOPSIS
        Check the instance registry for port collisions.
    .PARAMETER Port
        The API port to check.
    .PARAMETER ExcludeName
        Instance name to exclude from collision check (for self-update).
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][int]$Port,
        [string]$ExcludeName = ""
    )

    $registry = Get-InstanceRegistry
    foreach ($name in $registry.Keys) {
        if ($name -eq $ExcludeName) { continue }
        $entry = $registry[$name]
        if ($entry.api_port -eq $Port) {
            Write-Host "FAIL: Port $Port already in use by instance '$name' at $($entry.path)" -ForegroundColor Red
            return $false
        }
    }
    return $true
}

# ─────────────────────────────────────────────────────────────────────
# Instance registry
# ─────────────────────────────────────────────────────────────────────

function Get-RegistryPath {
    <#
    .SYNOPSIS
        Return the path to the machine-global instance registry JSON.
    #>
    [CmdletBinding()]
    param()

    $dir = Join-Path $env:LOCALAPPDATA "ai-benchmark"
    return Join-Path $dir "instances.json"
}

function Get-InstanceRegistry {
    <#
    .SYNOPSIS
        Read the instance registry. Creates it if missing.
    .OUTPUTS
        Hashtable of instance entries keyed by name.
    #>
    [CmdletBinding()]
    param()

    $path = Get-RegistryPath

    if (-not (Test-Path $path)) {
        $dir = Split-Path -Parent $path
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        Set-Content -Path $path -Value "{}" -Encoding UTF8
        return @{}
    }

    try {
        $json = Get-Content -Path $path -Raw -Encoding UTF8
        $obj = $json | ConvertFrom-Json
        # Convert PSCustomObject to hashtable
        $registry = @{}
        foreach ($prop in $obj.PSObject.Properties) {
            $entry = @{}
            foreach ($p in $prop.Value.PSObject.Properties) {
                $entry[$p.Name] = $p.Value
            }
            $registry[$prop.Name] = $entry
        }
        return $registry
    } catch {
        Write-Warning "Could not parse instance registry at $path - starting fresh."
        return @{}
    }
}

function Set-InstanceEntry {
    <#
    .SYNOPSIS
        Add or update an instance in the registry.
    .PARAMETER Name
        Instance name (registry key).
    .PARAMETER Data
        Hashtable with: path, type, version, install_date, last_upgrade_date,
        api_port, task_name.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][hashtable]$Data
    )

    $registry = Get-InstanceRegistry
    $registry[$Name] = $Data

    $path = Get-RegistryPath
    $json = $registry | ConvertTo-Json -Depth 4
    Set-Content -Path $path -Value $json -Encoding UTF8
}

function Remove-InstanceEntry {
    <#
    .SYNOPSIS
        Remove an instance from the registry.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Name
    )

    $registry = Get-InstanceRegistry
    if ($registry.ContainsKey($Name)) {
        $registry.Remove($Name)
        $path = Get-RegistryPath
        $json = $registry | ConvertTo-Json -Depth 4
        Set-Content -Path $path -Value $json -Encoding UTF8
        return $true
    }
    return $false
}

function Test-InstanceExists {
    <#
    .SYNOPSIS
        Check if an instance is already registered at the given path.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Path
    )

    $normalizedPath = (Resolve-Path $Path -ErrorAction SilentlyContinue).Path
    if (-not $normalizedPath) { $normalizedPath = $Path }

    $registry = Get-InstanceRegistry
    foreach ($name in $registry.Keys) {
        $entry = $registry[$name]
        $entryPath = $entry.path
        if ($entryPath -eq $normalizedPath -or $entryPath -eq $Path) {
            return $name
        }
    }
    return $null
}

function Find-InstanceByName {
    <#
    .SYNOPSIS
        Look up an instance by name and return its registry entry.
    .OUTPUTS
        Hashtable with instance data, or $null if not found.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Name
    )

    $registry = Get-InstanceRegistry
    if ($registry.ContainsKey($Name)) {
        return $registry[$Name]
    }
    return $null
}

# ─────────────────────────────────────────────────────────────────────
# Dry-run infrastructure
# ─────────────────────────────────────────────────────────────────────

function Set-DryRunMode {
    <#
    .SYNOPSIS
        Enable or disable dry-run mode for the current session.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][bool]$Enabled
    )

    $Script:DryRun = $Enabled
    if ($Enabled) {
        Write-Host "[DRY RUN] Dry-run mode enabled - no changes will be made." -ForegroundColor Cyan
    }
}

function Invoke-InstallerAction {
    <#
    .SYNOPSIS
        Execute or simulate an action depending on dry-run mode.
    .PARAMETER Description
        Human-readable description of the action.
    .PARAMETER Action
        ScriptBlock to execute if not in dry-run mode.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Description,
        [Parameter(Mandatory)][scriptblock]$Action
    )

    if ($Script:DryRun) {
        Write-Host "[DRY RUN] would: $Description" -ForegroundColor Cyan
        return $null
    }

    Write-Host "  $Description"
    return & $Action
}

# ─────────────────────────────────────────────────────────────────────
# Version tracking
# ─────────────────────────────────────────────────────────────────────

function Write-VersionJson {
    <#
    .SYNOPSIS
        Write config\version.json with install/upgrade metadata.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [string]$PackageVersion = "unknown",
        [string]$PythonVersion = "unknown",
        [string]$InstallerVersion = $Script:InstallerVersion
    )

    $data = @{
        package_version   = $PackageVersion
        installer_version = $InstallerVersion
        python_version    = $PythonVersion
        install_timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
    }

    $configDir = Join-Path $InstallDir "config"
    if (-not (Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    }

    $path = Join-Path $configDir "version.json"
    $json = $data | ConvertTo-Json -Depth 2
    Set-Content -Path $path -Value $json -Encoding UTF8
}

function Read-VersionJson {
    <#
    .SYNOPSIS
        Read config\version.json and return as hashtable.
    .OUTPUTS
        Hashtable with version metadata, or $null if not found.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$InstallDir
    )

    $path = Join-Path $InstallDir "config\version.json"
    if (-not (Test-Path $path)) {
        return $null
    }

    try {
        $json = Get-Content -Path $path -Raw -Encoding UTF8
        $obj = $json | ConvertFrom-Json
        $result = @{}
        foreach ($prop in $obj.PSObject.Properties) {
            $result[$prop.Name] = $prop.Value
        }
        return $result
    } catch {
        Write-Warning "Could not read version.json: $_"
        return $null
    }
}

# ─────────────────────────────────────────────────────────────────────
# Comparison
# ─────────────────────────────────────────────────────────────────────

function Compare-InstanceDatabases {
    <#
    .SYNOPSIS
        Compares row counts across all tables in two instance databases.
    .PARAMETER Name1
        First instance name.
    .PARAMETER Name2
        Second instance name.
    #>
    param(
        [Parameter(Mandatory)][string]$Name1,
        [Parameter(Mandatory)][string]$Name2
    )

    $entry1 = Find-InstanceByName -Name $Name1
    $entry2 = Find-InstanceByName -Name $Name2
    if (-not $entry1) { throw "Instance '$Name1' not found in registry." }
    if (-not $entry2) { throw "Instance '$Name2' not found in registry." }

    # Resolve database paths
    $db1 = Join-Path $entry1.path "data\ai_benchmark.db"
    if (-not (Test-Path $db1)) {
        $db1 = Join-Path $entry1.path "ai_benchmark.db"
    }
    $db2 = Join-Path $entry2.path "data\ai_benchmark.db"
    if (-not (Test-Path $db2)) {
        $db2 = Join-Path $entry2.path "ai_benchmark.db"
    }

    if (-not (Test-Path $db1)) {
        throw "Database not found for instance '$Name1'"
    }
    if (-not (Test-Path $db2)) {
        throw "Database not found for instance '$Name2'"
    }

    # Find a usable Python
    $python = Join-Path $entry1.path "venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        $python = Join-Path $entry2.path "venv\Scripts\python.exe"
    }
    if (-not (Test-Path $python)) {
        $found = Get-Command "python" -ErrorAction SilentlyContinue
        if ($found) { $python = $found.Source }
        else { throw "Cannot find Python to run comparison." }
    }

    # Write comparison script to temp file
    $tmpScript = Join-Path ([System.IO.Path]::GetTempPath()) "aibench_compare_$([guid]::NewGuid().ToString('N')).py"
    try {
        @"
import sqlite3, sys
db1, db2, n1, n2 = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
def get_counts(path):
    conn = sqlite3.connect(path)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )]
    counts = {}
    for t in tables:
        counts[t] = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    conn.close()
    return counts
c1, c2 = get_counts(db1), get_counts(db2)
all_tables = sorted(set(list(c1.keys()) + list(c2.keys())))
print(f"{'Table':<40} {n1:>10} {n2:>10} {'Diff':>10}")
print("-" * 74)
for t in all_tables:
    v1, v2 = c1.get(t, 0), c2.get(t, 0)
    diff = v2 - v1
    marker = "" if diff == 0 else f"{diff:+d}"
    print(f"{t:<40} {v1:>10} {v2:>10} {marker:>10}")
"@ | Set-Content -Path $tmpScript -Encoding UTF8

        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $python $tmpScript $db1 $db2 $Name1 $Name2 2>&1
        $ErrorActionPreference = $prevEAP
        if ($LASTEXITCODE -ne 0) {
            throw "Database comparison script failed."
        }
    } finally {
        Remove-Item $tmpScript -Force -ErrorAction SilentlyContinue
    }
}

# ─────────────────────────────────────────────────────────────────────
# Module exports
# ─────────────────────────────────────────────────────────────────────

Export-ModuleMember -Function @(
    # Core
    'Invoke-TemplateSubstitution'
    'Write-InstallerLog'
    'Test-Elevation'
    # Pre-flight
    'Test-PythonVersion'
    'Test-PipAvailable'
    'Test-BuildModule'
    'Test-DirectoryWritable'
    'Test-PortAvailable'
    # Registry
    'Get-RegistryPath'
    'Get-InstanceRegistry'
    'Set-InstanceEntry'
    'Remove-InstanceEntry'
    'Test-InstanceExists'
    'Find-InstanceByName'
    # Dry-run
    'Set-DryRunMode'
    'Invoke-InstallerAction'
    # Version
    'Write-VersionJson'
    'Read-VersionJson'
    # Comparison
    'Compare-InstanceDatabases'
)
