# Daily Report — Design Document

## 1. Purpose

Produce a daily AI intelligence report from the ETL pipeline's collected data. The report should be organized by topic (not by publisher or event_type), with AI-generated summaries and noise filtering. The pipeline collects ~3,000 events from 23 sources, but a daily report should surface only the 20-50 most relevant items, grouped thematically.

## 2. Problem Statement

The current report implementation has three problems:
1. **No topic grouping** — articles are grouped mechanically (by publisher or event_type), not by what they're actually about
2. **No noise filtering** — non-AI Reuters articles, irrelevant GitHub repos, and HF Forum complaints appear alongside real AI news
3. **No summarization** — articles echo raw titles and page fragments instead of explaining what happened

All three require LLM intelligence. The pipeline itself cannot call an LLM directly, and Claude Code cannot invoke itself recursively.

## 3. Architecture

### 3.1 Two-Stage Pipeline

**Stage 1: Data extraction (local, no LLM)**
- `ai-benchmark report --format json` queries the database for events with `published_date` in the last 24 hours
- Outputs structured JSON with: title, publisher, date, event_type, model_slug, abstract (from raw_content), url, confidence metadata
- Writes to a known local path (e.g., `C:\ai-data-pipeline\artifacts\raw_articles.json`)

**Stage 2: AI summarization (local, LLM-powered)**
- A Windows scheduled task is created to run immediately
- A) The scheduled task launches 'CMD claude' with an agent that reads the Stage 1 data file, writes summary paragraphs, produces the final markdown report.
- B) Files are written to the artifacts folder.
- C) Send notification (could be handled by claude)

### 3.2 Data Flow


```

### 3.3 Constraints

- Prompt size is limited — 183 articles at full detail is ~77K chars, needs compaction

---
```

## 5. What Exists Today

| Component | Location | Status |
|---|---|---|
| Query layer | `ai_benchmark/reporting/report_queries.py` | Working — extracts articles by published_date, deduplicates claims, attaches cross-refs |
| JSON export | `ai-benchmark report --format json` | Working — outputs full article data |
| Markdown formatter | `ai_benchmark/reporting/report_formatter.py` | Basic — groups by event_type, no AI summarization |
| CLI command | `ai_benchmark/cli.py` (`report`) | Working — `--format`, `--output`, `--hours`, `--days` options |
| Deployed instance | `C:\ai-data-pipeline` | Working — has database with fresh data |
