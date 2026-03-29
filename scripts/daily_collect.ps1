# AI Benchmark Daily Collection
# Launched by Windows Task Scheduler at 5:00 AM daily.
# Invokes Claude Code via OAuth (not API key) to run the source collection pipeline.

$ErrorActionPreference = "Stop"
$ProjectDir = "C:\Projects\ai_benchmark"
$LogDir = Join-Path $ProjectDir "logs"
$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$LogFile = Join-Path $LogDir "collect_$Timestamp.log"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

Set-Location $ProjectDir

# Clear ANTHROPIC_API_KEY so Claude Code uses OAuth instead of API credits
$env:ANTHROPIC_API_KEY = $null

$Prompt = @"
Run the full source collection pipeline and report the results. Execute these steps:

1. Run: python -m ai_benchmark.cli collect
2. Run: python -m ai_benchmark.cli status
3. Summarize what was collected, any errors, and new events found.

Write the summary to logs/collect_summary_$Timestamp.md
"@

# Run Claude Code in non-interactive mode using OAuth auth
& claude -p $Prompt --allowedTools "Bash(command)" "Write(file_path,content)" "Read(file_path)" 2>&1 | Tee-Object -FilePath $LogFile

exit $LASTEXITCODE
