# Physical Design Requirements: Pipeline Reset, Backfill, and Weekly Reporting

**Source document:** `docs/pipeline_reset_design.md`
**Project root:** `C:\Projects\ai_benchmark`
**Date:** 2026-04-03 01:00 AM (PST)

## 1. System Context

### 1.1 Existing Infrastructure to Reuse

| Asset | Location | Reuse |
|---|---|---|
| Report query layer | `ai_benchmark/reporting/report_queries.py` | Modify `gather_daily_report()` — add `reference_date` parameter. Reuse `_fetch_events_in_date_range()` unchanged. |
| Report formatter | `ai_benchmark/reporting/report_formatter.py` | No changes — `format_json()` already reads `generated_at` from `DailyReport`. |
| CLI report command | `ai_benchmark/cli.py` lines 241-274 | Modify — add `--date` option. Add new `report-range` command. |
| report.bat | `scripts/bin/report.bat` | Rewrite — accept optional date argument, deterministic filename. |
| Installer scripts | `scripts/installer/Install-Instance.ps1`, `Update-Instance.ps1` | Modify — add generation for `weekly_report.bat` and `report_range.ps1`. |
| Backfill infrastructure | `ai_benchmark/cli.py` `collect --since`, `coordination/worker.py`, `sources/base.py` `_make_rss_date_windows()` | No changes — backfill works as-is. |
| Export command | `ai_benchmark/cli.py` lines 208-238 | Use as-is for pre-wipe safety export. |
| Test suite | `tests/test_daily_report.py` | Modify — add `reference_date` tests. |

### 1.2 New Dependencies to Add

| Package | Purpose | Version Constraint |
|---|---|---|
| (none) | All new code uses existing stdlib + SQLAlchemy + Click | — |

## 2. Package Layout

No new Python packages. Changes to existing files plus three new scripts.

```
ai_benchmark/
  reporting/
    report_queries.py       # Modified: add reference_date param to gather_daily_report()
  cli.py                    # Modified: add --date to report, add report-range command

scripts/
  bin/
    report.bat              # Modified: accept date argument, deterministic filename
    report_range.ps1        # New: batch Claude CLI summarization over date range
    weekly_report.bat       # New: weekly synthesis from 7 daily markdown files

scripts/
  installer/
    Install-Instance.ps1    # Modified: generate weekly_report.bat and report_range.ps1
    Update-Instance.ps1     # Modified: generate weekly_report.bat and report_range.ps1

tests/
  test_daily_report.py      # Modified: add reference_date tests

docs/
  pipeline_reset_design.md  # Existing design doc
  pipeline_reset_pdr.md     # This document
```

## 3. Data Model

No database schema changes. No new tables. No migrations.

### 3.1 Modified Function Signature

**File:** `ai_benchmark/reporting/report_queries.py`

Current:
```python
async def gather_daily_report(
    session: AsyncSession,
    hours: int = 24,
) -> DailyReport:
```

New:
```python
async def gather_daily_report(
    session: AsyncSession,
    hours: int = 24,
    reference_date: date | None = None,
) -> DailyReport:
```

When `reference_date` is provided:
- `date_from` = `reference_date.isoformat()` (same day)
- `date_to` = `reference_date.isoformat()` (same day)
- `generated_at` = `datetime.combine(reference_date, datetime.min.time(), tzinfo=UTC)`
- `hours` parameter is ignored

When `reference_date` is `None` (default, backward compatible):
- Current behavior preserved: `cutoff = now - timedelta(hours=hours)`, `today = now`

### 3.2 Modified CLI Command

**File:** `ai_benchmark/cli.py`

Add to `report` command:
```python
@click.option(
    "--date",
    "report_date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Generate report for a specific date (YYYY-MM-DD). Overrides --hours.",
)
```

Pass through:
```python
ref_date = report_date.date() if report_date else None
data = await gather_daily_report(session, hours=hours, reference_date=ref_date)
```

### 3.3 New `report-range` CLI Command

**File:** `ai_benchmark/cli.py`

```python
@cli.command("report-range")
@click.option("--since", required=True, type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--until", type=click.DateTime(formats=["%Y-%m-%d"]), default=None)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
```

Behavior:
1. Open one DB engine + session factory
2. Loop from `since` to `until` (default: today), one day at a time
3. For each date, call `gather_daily_report(session, reference_date=d)`
4. Write `raw_articles_YYYYMMDD.json` to `output-dir`
5. Print summary: `Generated N reports (M with articles, K empty)`

This command handles Stage 1 (JSON extraction) only. Stage 2 (Claude CLI) is handled by `report_range.ps1`.

### 3.4 File Naming Convention

| File | Pattern | Example |
|---|---|---|
| Daily JSON extract | `raw_articles_YYYYMMDD.json` | `raw_articles_20260315.json` |
| Daily markdown report | `daily_report_YYYYMMDD.md` | `daily_report_20260315.md` |
| Weekly markdown report | `weekly_report_YYYYMMDD.md` (Sunday date) | `weekly_report_20260330.md` |

## 4. Scripts

### 4.1 Modified `report.bat`

**File:** `scripts/bin/report.bat`

Accept optional first argument as date (YYYY-MM-DD):
- `report.bat` — uses today's date
- `report.bat 2026-03-15` — generates report for March 15

Logic:
```
set DATE_ARG=%~1
if not defined DATE_ARG → compute today as YYYY-MM-DD from wmic
set DATE_SAFE=%DATE_ARG:-=%    (strip hyphens: 20260315)
set RAW=%ARTIFACTS%\raw_articles_%DATE_SAFE%.json
set REPORT=%ARTIFACTS%\daily_report_%DATE_SAFE%.md

Stage 1: %PYTHON% -m ai_benchmark report --date %DATE_ARG% --output "%RAW%"
Stage 2: %CLAUDE_CMD% -p "Read %RAW%... write to %REPORT%..."
```

When no date is provided and `--date` is omitted, `gather_daily_report()` falls back to `hours=24` from now (backward compatible).

### 4.2 New `report_range.ps1`

**File:** `scripts/bin/report_range.ps1`

PowerShell script for batch Claude CLI summarization.

**Usage:** `report_range.ps1 -Since 2026-02-15 [-Until 2026-04-02]`

Logic:
```powershell
param(
    [Parameter(Mandatory)][string]$Since,
    [string]$Until = (Get-Date).ToString("yyyy-MM-dd")
)

$installDir = "{{INSTALL_DIR}}"
$artifacts = "$installDir\artifacts"
$reportBat = "$installDir\bin\report.bat"

$current = [DateTime]$Since
$end = [DateTime]$Until

while ($current -le $end) {
    $dateStr = $current.ToString("yyyy-MM-dd")
    $dateSafe = $current.ToString("yyyyMMdd")
    $reportFile = "$artifacts\daily_report_$dateSafe.md"

    if (Test-Path $reportFile) {
        Write-Host "SKIP $dateStr — already exists"
    } else {
        Write-Host "Generating $dateStr..."
        & $reportBat $dateStr
    }

    $current = $current.AddDays(1)
}
```

Key features:
- Idempotent: skips dates where `daily_report_YYYYMMDD.md` already exists
- Uses `report.bat` for each date (inherits API key clearing, session resume, etc.)
- PowerShell for clean date arithmetic

### 4.3 New `weekly_report.bat`

**File:** `scripts/bin/weekly_report.bat`

**Usage:** `weekly_report.bat [YYYY-MM-DD]` (week-ending Sunday, defaults to most recent Sunday)

Logic:
1. Parse the Sunday date from `%~1` or compute most recent Sunday
2. Compute Monday = Sunday - 6 days
3. Build list of 7 daily report file paths: `daily_report_YYYYMMDD.md` for Monday through Sunday
4. Check which files exist, warn about missing ones
5. Concatenate existing file paths into a space-separated list
6. Call Claude CLI:

```
%CLAUDE_CMD% -p "Read these daily AI intelligence reports: [file list].
They cover the week of [Monday] through [Sunday].
Produce a weekly intelligence summary with these sections:
# AI Intelligence Weekly Report
## Week of [Monday] through [Sunday]
## Key Developments — the 3-5 most significant events
## Story Arcs — announcements that evolved over multiple days
## Emerging Trends — patterns visible across multiple days
## Competitive Landscape — moves and responses between AI companies
Write the report to [output path]."
```

Output: `weekly_report_YYYYMMDD.md` (Sunday date in filename).

### 4.4 Installer Integration

**Files:** `scripts/installer/Install-Instance.ps1`, `scripts/installer/Update-Instance.ps1`

Add to the bin script generation section (after report.bat generation):

```powershell
# weekly_report.bat
$weeklyPath = Join-Path $SourceDir "scripts\bin\weekly_report.bat"
if (Test-Path $weeklyPath) {
    Invoke-TemplateSubstitution -TemplatePath $weeklyPath `
        -OutputPath (Join-Path $binDir "weekly_report.bat") `
        -Tokens @{ INSTALL_DIR = $Path }
}

# report_range.ps1
$rangePath = Join-Path $SourceDir "scripts\bin\report_range.ps1"
if (Test-Path $rangePath) {
    Invoke-TemplateSubstitution -TemplatePath $rangePath `
        -OutputPath (Join-Path $binDir "report_range.ps1") `
        -Tokens @{ INSTALL_DIR = $Path }
}
```

## 5. Clean Install Procedure

This is an operational procedure, not code. Steps to execute after all code changes are deployed:

1. **Safety export:** `ai-benchmark export --format json --limit 99999 --output C:\ai-data-pipeline\artifacts\pre_wipe_events.json`
2. **Delete DB:** Remove `C:\ai-data-pipeline\data\ai_benchmark.db`
3. **Init schema:** `ai-benchmark init-db`
4. **Backfill:** `ai-benchmark collect --since 2026-02-15` (sources/pages auto-created from TOML, RSS enrichment active)
5. **Batch daily reports Stage 1:** `ai-benchmark report-range --since 2026-02-15 --output-dir C:\ai-data-pipeline\artifacts`
6. **Batch daily reports Stage 2:** `C:\ai-data-pipeline\bin\report_range.ps1 -Since 2026-02-15`
7. **Weekly reports:** Run `weekly_report.bat` for each complete week

## 6. Verification

| Step | Command | Expected |
|---|---|---|
| Unit tests pass | `pytest tests/test_daily_report.py` | All pass including new reference_date tests |
| Lint clean | `ruff check ai_benchmark/reporting/ ai_benchmark/cli.py` | No errors |
| Historical report works | `ai-benchmark report --date 2026-04-01 --output test.json` | JSON with articles from April 1 |
| Batch extraction works | `ai-benchmark report-range --since 2026-04-01 --until 2026-04-02 --output-dir /tmp` | Two JSON files |
| report.bat with date | `report.bat 2026-04-01` | `daily_report_20260401.md` produced |
| weekly_report.bat | `weekly_report.bat 2026-03-30` | `weekly_report_20260330.md` from 7 dailies |
| Installer generates scripts | `ai-bench-installer.bat upgrade` | `bin/weekly_report.bat` and `bin/report_range.ps1` present |
