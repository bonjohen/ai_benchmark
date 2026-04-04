<#
.SYNOPSIS
    Batch daily report generation over a date range.

.DESCRIPTION
    Stage 1: Extracts raw JSON for every date via ai-benchmark report-range.
    Stage 2: Runs report.bat (Claude CLI summarization) for each date,
    skipping dates where daily_report_YYYYMMDD.md already exists.

.PARAMETER Since
    Start date (YYYY-MM-DD, inclusive). Required.

.PARAMETER Until
    End date (YYYY-MM-DD, inclusive). Defaults to today.

.EXAMPLE
    report_range.ps1 -Since 2026-02-15
    report_range.ps1 -Since 2026-02-15 -Until 2026-04-02
#>
param(
    [Parameter(Mandatory)][string]$Since,
    [string]$Until = (Get-Date).ToString("yyyy-MM-dd")
)

$installDir = "{{INSTALL_DIR}}"
$artifacts = "$installDir\artifacts"
$reportBat = "$installDir\bin\report.bat"
$python = "$installDir\venv\Scripts\python.exe"

$env:AI_BENCH_ENV_FILE = "$installDir\config\.env"

# Ensure logs directory exists
$logsDir = "$installDir\logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
$logFile = "$logsDir\report_range_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# Stage 1: Batch JSON extraction (fast, one DB connection)
Write-Host "=== Stage 1: Extracting raw JSON for $Since through $Until ==="
Write-Host "    Log file: $logFile"
# Redirect stdout+stderr to log file directly (no Tee-Object pipe, which can
# swallow $LASTEXITCODE and wrap stderr lines in ErrorRecord objects).
& $python -m ai_benchmark report-range --since $Since --until $Until --output-dir $artifacts > $logFile 2>&1
$exitCode = $LASTEXITCODE
Get-Content $logFile
if ($exitCode -ne 0) {
    Write-Host "ERROR: Stage 1 (report-range) failed with exit code $exitCode — see $logFile"
    exit 1
}

# Stage 2: Claude CLI summarization for each date
Write-Host ""
Write-Host "=== Stage 2: Claude CLI summarization ==="

$current = [DateTime]$Since
$end = [DateTime]$Until
$generated = 0
$skipped = 0

while ($current -le $end) {
    $dateStr = $current.ToString("yyyy-MM-dd")
    $dateSafe = $current.ToString("yyyyMMdd")
    $reportFile = "$artifacts\daily_report_$dateSafe.md"

    if (Test-Path $reportFile) {
        Write-Host "SKIP $dateStr - daily_report_$dateSafe.md already exists"
        $skipped++
    } else {
        Write-Host "Generating $dateStr..."
        & $reportBat $dateStr
        if ($LASTEXITCODE -ne 0) {
            Write-Host "WARNING: report.bat failed for $dateStr (exit $LASTEXITCODE), retrying once..."
            Start-Sleep -Seconds 5
            & $reportBat $dateStr
            if ($LASTEXITCODE -ne 0) {
                Write-Host "ERROR: report.bat failed for $dateStr on retry, skipping"
                $current = $current.AddDays(1)
                continue
            }
        }
        $generated++
    }

    $current = $current.AddDays(1)
}

Write-Host ""
Write-Host "=== Complete: $generated generated, $skipped skipped ==="
