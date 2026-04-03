# Pipeline Reset, Backfill, and Weekly Reporting — Design Document

## 1. Purpose

Reset the AI intelligence pipeline to a clean state, backfill historical data from February 15, 2026, and establish a complete daily+weekly reporting pipeline. The current report command only generates reports for "today." This design adds historical date support, batch report generation across a date range, and weekly report synthesis from daily report files.

## 2. Scope

**In scope:**
- Data preservation audit and safety export before DB wipe
- Clean install procedure (delete DB, init-db, first collection recreates config from TOML)
- Adding `--date YYYY-MM-DD` parameter to the report command for historical daily reports
- New `report-range` CLI command for batch JSON extraction across a date range
- New `report_range.ps1` script for batch Claude CLI summarization
- New `weekly_report.bat` script that synthesizes 7 daily markdown reports into a weekly summary
- Installer updates to generate new bin scripts on install/upgrade

**Out of scope:**
- Changes to the collection pipeline (backfill via `--since` already works)
- Changes to the analysis or eval pipelines
- Database schema changes

## 3. Core Design Principles

1. **TOML is authoritative.** The database holds no unique configuration. Source and page records are recreated from `sources.toml` by `CollectionCoordinator._create_tasks()` on every collection run. A pre-wipe export is a safety net, not a requirement.

2. **Minimal surface area.** The `--date` parameter is a single addition to the existing `gather_daily_report()` function and `report` CLI command. No new query infrastructure is needed — `_fetch_events_in_date_range(session, date_from, date_to)` already exists and works with ISO date strings.

3. **Batch via script, not framework.** The batch daily report loop and weekly report composer are scripts calling existing CLI commands and Claude CLI, matching the established pattern in `report.bat` and `backfill.bat`.

4. **Deterministic filenames.** Daily reports: `daily_report_YYYYMMDD.md` (one per calendar day). Weekly reports: `weekly_report_YYYYMMDD.md` (dated to the Sunday that ends the week). Enables the weekly script to glob for the correct 7 files.

5. **Two-stage report pattern.** Stage 1 extracts JSON via Python (fast, one DB connection). Stage 2 summarizes via Claude CLI (slow, one call per report). Batch generation separates these stages so Stage 1 runs entirely first.

## 4. Primary User Stories

**US-1: Clean install from TOML config.** As a pipeline operator, I want to delete the existing database and reinitialize from scratch, confident that all configuration will be recreated from TOML files on first collection.

**US-2: Backfill historical data.** As a pipeline operator, I want to run `ai-benchmark collect --since 2026-02-15` to populate the database with historical events, understanding that Google News RSS provides approximately 30 days of history and that earlier dates may have gaps.

**US-3: Generate a daily report for a specific historical date.** As an analyst, I want to run `ai-benchmark report --date 2026-03-15` to produce the daily intelligence JSON for March 15 (events with `published_date` on that calendar day).

**US-4: Batch-generate all daily reports.** As a pipeline operator, I want to run a single command that generates daily report JSON for every date from Feb 15 to today, then a script that runs Claude CLI summarization for each.

**US-5: Generate a weekly summary from daily reports.** As an analyst, I want to run `weekly_report.bat 2026-03-30` specifying a week-ending Sunday, which reads the 7 corresponding daily report markdown files and produces a weekly synthesis via Claude CLI.

## 5. Functional Requirements

### 5.1 Data Preservation and Clean Install

The database contains no unique configuration. All source/page definitions originate in `sources.toml` and are recreated by `CollectionCoordinator._create_tasks()` (coordinator.py lines 131-208) on first collection.

| Data | Source of Truth | In DB? | Unique to DB? |
|------|----------------|--------|---------------|
| Source records | `sources.toml` | Yes | No — recreated from TOML |
| Page records | `sources.toml` | Yes | No — recreated from TOML |
| Polling metadata | DB `pages` table | Yes | Yes, but ephemeral |
| Schedules | `schedules.toml` | No | N/A |
| Event records | Collected data | Yes | Yes — will be re-collected |
| API keys | `.env` file | No | N/A |

**Safety net before wipe:** Export existing events via `ai-benchmark export --format json --output artifacts/pre_wipe_events.json` for reference. This is not needed for restoration — all data will be re-collected.

**Clean install procedure:**
1. Back up `.env` (already at `C:\ai-data-pipeline\config\.env`, gitignored)
2. Delete `ai_benchmark.db`
3. Run `ai-benchmark init-db` to create empty schema
4. Run `ai-benchmark collect --since 2026-02-15` (sources/pages auto-created from TOML)

No code changes needed for this section.

### 5.2 Backdated Collection

No code changes required. Existing infrastructure handles this:

- `cli.py`: `--since` parameter with `click.DateTime`
- `coordinator.py`: `collect_all(since_date=...)` passes date through to tasks
- `base.py`: `_make_rss_date_windows()` splits date range into monthly chunks with `after:/before:` Google News RSS filters
- `base.py`: `_enrich_rss_items()` follows links to get real meta descriptions

**Known limitation:** Google News RSS supports approximately 30 days of history. Feb 15 is ~47 days ago — the Feb 15–Mar 3 window may return sparse or empty results. March and April data should be complete.

### 5.3 Historical Daily Report Generation

#### 5.3.1 Add `reference_date` to `gather_daily_report()`

**File:** `ai_benchmark/reporting/report_queries.py`

When `reference_date` is provided, use it instead of `datetime.now(UTC)`. The query window becomes exactly that calendar day (same date for both `date_from` and `date_to` in `_fetch_events_in_date_range`). The `hours` parameter is ignored when `reference_date` is set.

#### 5.3.2 Add `--date` to CLI `report` command

**File:** `ai_benchmark/cli.py`

New option: `--date YYYY-MM-DD` passed as `reference_date` to `gather_daily_report()`. Overrides `--hours`.

#### 5.3.3 Update `report.bat` to accept a date argument

**File:** `scripts/bin/report.bat`

Accept optional `%~1` argument as a date. When provided, pass `--date` to the Python CLI and use `daily_report_YYYYMMDD.md` as the filename. When omitted, use today's date.

#### 5.3.4 New `report-range` CLI command

**File:** `ai_benchmark/cli.py`

Loops from `--since` to `--until` (default: today), calls `gather_daily_report()` for each date with one DB connection, writes `raw_articles_YYYYMMDD.json` for each date. Fast (~5 seconds for 47 dates).

#### 5.3.5 New `report_range.ps1` script

**File:** `scripts/bin/report_range.ps1`

PowerShell script that loops over `raw_articles_*.json` files and calls Claude CLI for each, producing `daily_report_YYYYMMDD.md`. Skips dates where the markdown already exists (idempotent). Uses PowerShell for clean date arithmetic.

### 5.4 Weekly Report Generation

**Design decision:** The weekly report reads 7 daily **markdown** files (not raw JSON). Daily reports are already curated by Claude CLI — the weekly report is a synthesis of syntheses, identifying multi-day trends and the most significant developments.

#### 5.4.1 New `weekly_report.bat` script

**File:** `scripts/bin/weekly_report.bat`

**Usage:** `weekly_report.bat [WEEK_ENDING_SUNDAY]`

1. Compute the 7 dates (Monday–Sunday) for the given week
2. Verify that `daily_report_YYYYMMDD.md` files exist for those dates
3. Pass the file paths to Claude CLI with a prompt to produce:
   - Key Developments (3-5 most significant)
   - Story Arcs (announcements that evolved over the week)
   - Emerging Trends (patterns visible across multiple days)
   - Competitive Landscape (moves and responses between AI companies)
4. Write `weekly_report_YYYYMMDD.md` (Sunday date)

#### 5.4.2 Installer integration

Both `Install-Instance.ps1` and `Update-Instance.ps1` need to generate `weekly_report.bat` and `report_range.ps1` into the `bin/` directory using the existing `Invoke-TemplateSubstitution` pattern with `{{INSTALL_DIR}}`.

## 6. Risks

1. **Google News 30-day limit.** Feb 15–Mar 3 data may be sparse. The `report-range` command should report dates with zero articles. Empty daily reports should still be generated.

2. **Claude CLI rate limits.** 47 sequential calls may hit timeouts. `report_range.ps1` should check exit codes and retry once with a delay.

3. **ANTHROPIC_API_KEY in environment.** The report scripts must clear this variable and use the `-r` session resume flag to ensure OAuth authentication.
