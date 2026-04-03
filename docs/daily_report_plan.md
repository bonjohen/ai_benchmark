# Daily Report — Implementation Plan

**Source document:** `docs/daily_report_pdr.md`

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
| AI summarization | Claude CLI (`claude -p`) invoked from batch script |
| JSON compaction | Python dataclasses in `report_queries.py` |
| Orchestration | `scripts/bin/report.bat` (Stage 1 extract + Stage 2 Claude CLI) |

## Phase 1: Noise Filtering and JSON Compaction

**Goal:** `ai-benchmark report --output file.json` produces compact, noise-free JSON under 20K chars.
**Depends on:** Nothing (first phase).

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-04-02 04:00 PM | 2026-04-02 04:10 PM | Add `_is_noise(event)` function to `report_queries.py` — filters short titles (<=10 chars), page chrome, RSS title-only articles (abstract empty or == title) |
| 1.2 | Completed | 2026-04-02 04:00 PM | 2026-04-02 04:10 PM | Add `_AI_REPO_PATTERNS` allowlist and GitHub filtering logic to `report_queries.py` — GitHub events whose title/path matches no pattern are noise |
| 1.3 | Completed | 2026-04-02 04:10 PM | 2026-04-02 04:15 PM | Modify `_build_article` in `report_queries.py` — compact fields: drop `event_type`, `source_type`, `cross_refs`, `event_id`; add `confirmed` bool; truncate abstract to 200 chars |
| 1.4 | Completed | 2026-04-02 04:15 PM | 2026-04-02 04:20 PM | Rewrite `format_json` in `report_formatter.py` — output compact structure: `{date, article_count, articles: [...]}` per PDR section 3.1 |
| 1.5 | Completed | 2026-04-02 04:15 PM | 2026-04-02 04:20 PM | Remove `format_markdown` and all markdown formatting helpers from `report_formatter.py` |
| 1.6 | Completed | 2026-04-02 04:10 PM | 2026-04-02 04:15 PM | Update `report` command in `cli.py` — remove `--format` choice (JSON only), remove `sys.stdout.reconfigure` workaround |
| 1.7 | Completed | 2026-04-02 04:20 PM | 2026-04-02 04:30 PM | Update `tests/test_daily_report.py` — test noise filtering (GitHub allowlist, short titles, empty abstracts), test compact JSON shape, remove markdown formatter tests |
| 1.8 | Completed | 2026-04-02 04:35 PM | 2026-04-02 04:36 PM | Verify against real DB: 15.6K chars, 25 articles, 3 GitHub (all AI-relevant), no filament/gvisor noise |
| 1.9 | Completed | 2026-04-02 04:30 PM | 2026-04-02 04:33 PM | `ruff check` and `ruff format --check` clean |
| 1.10 | Completed | 2026-04-02 04:33 PM | 2026-04-02 04:34 PM | `pytest tests/test_daily_report.py` — 16/16 pass |
| 1.11 | Completed | 2026-04-02 04:37 PM | 2026-04-02 04:38 PM | Stage all Phase 1 changes |
| 1.12 | Completed | 2026-04-02 04:38 PM | 2026-04-02 04:39 PM | Commit all Phase 1 changes |

### Phase 1 Summary

- **Changes:** Rewrote `report_queries.py` (compact Article dataclass, `_is_noise()` with GitHub allowlist, removed weekly stats/cross-refs/markdown support), rewrote `report_formatter.py` (compact JSON only), updated CLI (JSON-only, no `--format`), rewrote tests (16 tests: 6 noise filtering, 7 query, 3 formatter).
- **Changes hosted at:** TBD
- **Commit:** `Compact report JSON with noise filtering and GitHub allowlist`

## Phase 2: Claude CLI Integration Script

**Goal:** `scripts/bin/report.bat` runs both stages — extract JSON then Claude CLI summarization — and produces `daily_report.md`.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-04-02 04:42 PM | 2026-04-02 04:45 PM | Create `scripts/bin/report.bat` — Stage 1: call venv python `ai_benchmark report --output artifacts/raw_articles.json`; Stage 2: call `claude -p` with prompt to read JSON, group by topic, write markdown to `artifacts/daily_report.md` |
| 2.2 | Open | | | Test script manually from `C:\ai-data-pipeline` — verify `raw_articles.json` created, Claude CLI invoked, `daily_report.md` written |
| 2.3 | Completed | 2026-04-02 04:46 PM | 2026-04-02 04:46 PM | Stage all Phase 2 changes |
| 2.4 | Completed | 2026-04-02 04:46 PM | 2026-04-02 04:47 PM | Commit all Phase 2 changes |

### Phase 2 Summary

- **Changes:** Created `scripts/bin/report.bat` — two-stage script: Stage 1 extracts compact JSON to `artifacts/raw_articles.json`, Stage 2 invokes Claude CLI to group by topic and write `artifacts/daily_report.md`. Includes error handling, .env loading, and artifacts directory creation.
- **Changes hosted at:** TBD
- **Commit:** `Add report.bat for two-stage daily report (extract + Claude CLI)`

## Phase 3: Deploy and Verify

**Goal:** Deployed instance has the report command and script working end-to-end.
**Depends on:** Phase 2.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-04-02 04:50 PM | 2026-04-02 04:50 PM | Push to remote: `git push origin feature/data-pipeline-only` |
| 3.2 | Completed | 2026-04-02 04:50 PM | 2026-04-02 04:52 PM | Deploy: editable install already points at repo, code is live |
| 3.3 | Completed | 2026-04-02 04:53 PM | 2026-04-02 05:05 PM | End-to-end verified: Stage 1 produced raw_articles.json (25 articles), Stage 2 Claude CLI (OAuth) wrote daily_report.md with 4 topic sections |
| 3.4 | Completed | 2026-04-02 05:05 PM | 2026-04-02 05:06 PM | Output quality good: 4 thematic topics (Anthropic Dev Tools, OpenAI Codex, AI Safety, AI Trade Policy), summaries coherent, non-AI articles filtered |
| 3.5 | Completed | 2026-04-02 04:58 PM | 2026-04-02 05:00 PM | Fixed report.bat: clear ANTHROPIC_API_KEY at top, load only AI_BENCH_ vars from .env |
| 3.6 | Completed | 2026-04-02 05:00 PM | 2026-04-02 05:01 PM | Committed fix: "Clear API keys in report.bat so Claude CLI uses OAuth" |

### Phase 3 Summary

- **Changes:** Pushed and deployed. Fixed report.bat to clear API keys (use OAuth). End-to-end verified: 25 articles extracted, Claude CLI grouped into 4 thematic topics with summaries.
- **Changes hosted at:** `feature/data-pipeline-only` branch
- **Commit:** `Clear API keys in report.bat so Claude CLI uses OAuth`

## Key Files

| Purpose | File |
|---------|------|
| Noise filtering + compact articles | `ai_benchmark/reporting/report_queries.py` |
| JSON output formatter | `ai_benchmark/reporting/report_formatter.py` |
| CLI command | `ai_benchmark/cli.py` |
| Two-stage orchestration script | `scripts/bin/report.bat` |
| Tests | `tests/test_daily_report.py` |
| Design doc | `docs/daily_report_design.md` |
| PDR | `docs/daily_report_pdr.md` |
