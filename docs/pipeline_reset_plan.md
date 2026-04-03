# Pipeline Reset, Backfill, and Weekly Reporting — Implementation Plan

**Source document:** `docs/pipeline_reset_pdr.md`

## Work Queue Instructions

### State Transitions

Open  ──>  Started  ──>  Completed
              │
              └──>  Blocked  ──>  Started  ──>  Completed

- **Open**: Not yet begun.
- **Started**: Actively in progress. Record the start datetime (PST).
- **Completed**: Done and verified. Record the completion datetime (PST).
- **Blocked**: Cannot proceed; note the blocker in the description.

### Commit Protocol

1. Work through all tasks in a phase.
2. When every task reaches Completed, write the Phase Summary.
3. Stage and commit all changes for the phase. Do not push.
4. Proceed immediately to the next phase.

## Technology Stack (Additive)

| Concern | Choice |
|---|---|
| Historical date support | `reference_date` param on `gather_daily_report()` |
| Batch JSON extraction | `report-range` CLI command (Python, one DB connection) |
| Batch Claude CLI loop | `report_range.ps1` (PowerShell, date arithmetic) |
| Weekly synthesis | `weekly_report.bat` (Claude CLI reads 7 daily markdown files) |

## Phase 1: Historical Date Support in Python

**Goal:** `ai-benchmark report --date 2026-03-15 --output test.json` produces JSON for a specific historical date.
**Depends on:** Nothing (first phase).

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-04-03 12:00 AM | 2026-04-03 12:05 AM | Add `reference_date: date \| None = None` param to `gather_daily_report()` in `ai_benchmark/reporting/report_queries.py` — when set, query window is that single calendar day; `hours` ignored; `generated_at` set to that date |
| 1.2 | Completed | 2026-04-03 12:00 AM | 2026-04-03 12:05 AM | Add `from datetime import date` import to `report_queries.py` (needed for type annotation) |
| 1.3 | Completed | 2026-04-03 12:00 AM | 2026-04-03 12:06 AM | Add `--date` option to `report` CLI command in `ai_benchmark/cli.py` — `click.DateTime(formats=["%Y-%m-%d"])`, passed as `reference_date` to `gather_daily_report()` |
| 1.4 | Completed | 2026-04-03 12:00 AM | 2026-04-03 12:07 AM | Add tests in `tests/test_daily_report.py`: (a) `test_gather_report_with_reference_date` — events on that date included, events on other dates excluded; (b) `test_gather_report_reference_date_sets_generated_at` — `generated_at` reflects the reference date, not now |
| 1.5 | Completed | 2026-04-03 12:08 AM | 2026-04-03 12:08 AM | `ruff check` and `ruff format --check` clean |
| 1.6 | Completed | 2026-04-03 12:08 AM | 2026-04-03 12:08 AM | `pytest tests/test_daily_report.py` all pass (18/18) |
| 1.7 | Completed | 2026-04-03 12:09 AM | 2026-04-03 12:09 AM | Stage all Phase 1 changes |
| 1.8 | Completed | 2026-04-03 12:10 AM | 2026-04-03 12:10 AM | Commit all Phase 1 changes |

### Phase 1 Summary

- **Changes:** Modified `ai_benchmark/reporting/report_queries.py` (added `reference_date` param), `ai_benchmark/cli.py` (added `--date` option), `tests/test_daily_report.py` (added 2 tests), `docs/pipeline_reset_plan.md` (status updates).
- **Changes hosted at:** TBD
- **Commit:** `Add --date parameter for historical daily report generation`

## Phase 2: Update report.bat

**Goal:** `report.bat 2026-03-15` produces `daily_report_20260315.md`; `report.bat` (no arg) uses today's date.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-04-03 12:10 AM | 2026-04-03 12:12 AM | Rewrite `scripts/bin/report.bat` — accept optional `%~1` as date (YYYY-MM-DD); compute today if omitted; derive `DATE_SAFE` (strip hyphens); filenames `raw_articles_YYYYMMDD.json` and `daily_report_YYYYMMDD.md`; pass `--date` to Python CLI |
| 2.2 | Completed | 2026-04-03 12:12 AM | 2026-04-03 12:13 AM | Update deployed copy at `C:\ai-data-pipeline\bin\report.bat` with `INSTALL_DIR=C:\ai-data-pipeline` |
| 2.3 | Completed | 2026-04-03 12:13 AM | 2026-04-03 12:13 AM | Stage all Phase 2 changes |
| 2.4 | Completed | 2026-04-03 12:13 AM | 2026-04-03 12:13 AM | Commit all Phase 2 changes |

### Phase 2 Summary

- **Changes:** Rewrote `scripts/bin/report.bat` (date arg, deterministic filenames, `--date` pass-through). Updated deployed copy at `C:\ai-data-pipeline\bin\report.bat` (fixed path, added `-p` flag, added `--date`).
- **Changes hosted at:** `scripts/bin/report.bat`, `C:\ai-data-pipeline\bin\report.bat`
- **Commit:** `Update report.bat with date argument and deterministic filenames`

## Phase 3: Batch Report Generation

**Goal:** `ai-benchmark report-range --since 2026-02-15 --output-dir artifacts/` extracts all daily JSONs; `report_range.ps1 -Since 2026-02-15` runs Claude CLI for each.
**Depends on:** Phase 2.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-04-03 12:14 AM | 2026-04-03 12:16 AM | Add `report-range` CLI command in `ai_benchmark/cli.py` — `--since` (required), `--until` (default today), `--output-dir` (required); loop dates, call `gather_daily_report(session, reference_date=d)`, write `raw_articles_YYYYMMDD.json`; print summary |
| 3.2 | Completed | 2026-04-03 12:16 AM | 2026-04-03 12:17 AM | Create `scripts/bin/report_range.ps1` — PowerShell script; `param($Since, $Until)`; loop dates; skip if `daily_report_YYYYMMDD.md` exists; call `report.bat $dateStr`; use `{{INSTALL_DIR}}` template token |
| 3.3 | Completed | 2026-04-03 12:17 AM | 2026-04-03 12:17 AM | `ruff check` and `ruff format --check` clean |
| 3.4 | Completed | 2026-04-03 12:17 AM | 2026-04-03 12:17 AM | `pytest tests/test_daily_report.py` all pass (18/18) |
| 3.5 | Completed | 2026-04-03 12:18 AM | 2026-04-03 12:18 AM | Stage all Phase 3 changes |
| 3.6 | Completed | 2026-04-03 12:18 AM | 2026-04-03 12:18 AM | Commit all Phase 3 changes |

### Phase 3 Summary

- **Changes:** Added `report-range` CLI command to `ai_benchmark/cli.py`. Created `scripts/bin/report_range.ps1` (two-stage batch: JSON extraction then Claude CLI summarization with skip/retry logic).
- **Changes hosted at:** `ai_benchmark/cli.py`, `scripts/bin/report_range.ps1`
- **Commit:** `Add report-range command and batch summarization script`

## Phase 4: Weekly Report

**Goal:** `weekly_report.bat 2026-03-30` reads 7 daily markdown files and produces `weekly_report_20260330.md`.
**Depends on:** Phase 2 (needs deterministic daily report filenames).

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 4.1 | Open | | | Create `scripts/bin/weekly_report.bat` — accept optional `%~1` as week-ending Sunday (YYYY-MM-DD); compute Monday through Sunday dates; build file paths for 7 `daily_report_YYYYMMDD.md` files; warn on missing; call Claude CLI to synthesize; write `weekly_report_YYYYMMDD.md`; use `{{INSTALL_DIR}}` template token; clear API keys; support `CLAUDE_SESSION` |
| 4.2 | Open | | | Stage all Phase 4 changes |
| 4.3 | Open | | | Commit all Phase 4 changes |

### Phase 4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add weekly report script synthesizing 7 daily reports`

## Phase 5: Installer Integration

**Goal:** `ai-bench-installer.bat upgrade` generates `weekly_report.bat` and `report_range.ps1` into the deployed `bin/` directory.
**Depends on:** Phases 3 and 4.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 5.1 | Open | | | Add `weekly_report.bat` generation to `scripts/installer/Install-Instance.ps1` — same pattern as report.bat (Invoke-TemplateSubstitution with INSTALL_DIR token) |
| 5.2 | Open | | | Add `report_range.ps1` generation to `scripts/installer/Install-Instance.ps1` |
| 5.3 | Open | | | Add `weekly_report.bat` generation to `scripts/installer/Update-Instance.ps1` (in the temp dir + atomic copy block) |
| 5.4 | Open | | | Add `report_range.ps1` generation to `scripts/installer/Update-Instance.ps1` (in the temp dir + atomic copy block) |
| 5.5 | Open | | | Stage all Phase 5 changes |
| 5.6 | Open | | | Commit all Phase 5 changes |

### Phase 5 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add weekly_report.bat and report_range.ps1 to installer`

## Phase 6: Deploy, Reset, Backfill

**Goal:** Deployed instance has clean DB with backfilled data from Feb 15 and all reporting scripts.
**Depends on:** Phase 5.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 6.1 | Open | | | Push to remote: `git push origin feature/data-pipeline-only` |
| 6.2 | Open | | | Deploy: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/installer/Update-Instance.ps1 -Name ai-data-pipeline` |
| 6.3 | Open | | | Verify new bin scripts exist: `ls C:\ai-data-pipeline\bin\weekly_report.bat C:\ai-data-pipeline\bin\report_range.ps1` |
| 6.4 | Open | | | Safety export: `ai-benchmark export --format json --limit 99999 --output C:\ai-data-pipeline\artifacts\pre_wipe_events.json` |
| 6.5 | Open | | | Delete DB: remove `C:\ai-data-pipeline\data\ai_benchmark.db` |
| 6.6 | Open | | | Init schema: `ai-benchmark init-db` |
| 6.7 | Open | | | Backfill: `ai-benchmark collect --since 2026-02-15` (user kicks off) |
| 6.8 | Open | | | Batch daily reports Stage 1: `ai-benchmark report-range --since 2026-02-15 --output-dir C:\ai-data-pipeline\artifacts` |
| 6.9 | Open | | | Batch daily reports Stage 2: `C:\ai-data-pipeline\bin\report_range.ps1 -Since 2026-02-15` (user kicks off) |
| 6.10 | Open | | | Generate weekly reports: `weekly_report.bat` for each complete week (user kicks off) |
| 6.11 | Open | | | Review output quality |

### Phase 6 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** N/A (operational phase, no code changes)

## Key Files

| Purpose | File |
|---------|------|
| Historical date query | `ai_benchmark/reporting/report_queries.py` |
| CLI commands | `ai_benchmark/cli.py` |
| Daily report script | `scripts/bin/report.bat` |
| Batch summarization | `scripts/bin/report_range.ps1` |
| Weekly report script | `scripts/bin/weekly_report.bat` |
| Installer (install) | `scripts/installer/Install-Instance.ps1` |
| Installer (upgrade) | `scripts/installer/Update-Instance.ps1` |
| Tests | `tests/test_daily_report.py` |
| Design doc | `docs/pipeline_reset_design.md` |
| PDR | `docs/pipeline_reset_pdr.md` |
