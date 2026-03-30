# AI Benchmark Daily Analysis
# Launched by Windows Task Scheduler at 6:00 AM daily (one hour after collection).
# Invokes Claude Code via OAuth (not API key) to run status and analysis.
#
# Collection is handled by AIBenchmarkCollect task (collect.bat) at 5:00 AM.
# This task runs analysis/summary only — it does NOT run collect.

$ErrorActionPreference = "Stop"
$InstallDir = "C:\ai-benchmark"
$LogDir = Join-Path $InstallDir "logs"
$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$LogFile = Join-Path $LogDir "analysis_$Timestamp.log"
$VenvPython = Join-Path $InstallDir "venv\Scripts\python.exe"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

Set-Location $InstallDir

# Load .env for database URL and other config
$EnvFile = Join-Path $InstallDir "config\.env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
        }
    }
}

# Clear ANTHROPIC_API_KEY so Claude Code uses OAuth instead of API credits
$env:ANTHROPIC_API_KEY = $null

$Prompt = @"
Report on the most recent collection run and generate a daily digest. Execute these steps:

1. Run: & "$VenvPython" -m ai_benchmark.cli status
2. Run: & "$VenvPython" -m ai_benchmark.cli analyze digest --output logs/digest_$Timestamp.md
3. Summarize the collection status, any anomalies, and key findings from the digest.

Write the summary to logs/analysis_summary_$Timestamp.md
"@

# Run Claude Code in non-interactive mode using OAuth auth
& claude -p $Prompt --allowedTools "Bash(command)" "Write(file_path,content)" "Read(file_path)" 2>&1 | Tee-Object -FilePath $LogFile

exit $LASTEXITCODE
