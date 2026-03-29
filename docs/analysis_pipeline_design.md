# Analysis Pipeline Design Document

## 1. Purpose

The ai_benchmark system has a complete extract pipeline that collects AI industry events from 22 sources across 87 monitored pages, processes them through normalization, deduplication, verification, and cross-referencing, and stores them as structured records (events, claims, cross-references, research papers). However, the output surface is limited to flat event/claim queries with basic filters and simple JSON/CSV export. There is no mechanism to synthesize this data into higher-level intelligence products.

The analysis pipeline transforms raw collected data into actionable intelligence: model lifecycle timelines, benchmark trend analysis, competitive activity tracking, research pulse monitoring, automated anomaly detection, and periodic digest reports. It sits on top of the extract pipeline as a consumer of its output, producing structured intelligence products that answer questions like "What happened with GPT-5 since release?", "Who is leading SWE-bench Verified this month?", "Which vendors released models in the same week?", and "What research topics are trending?"

## 2. Scope

The analysis pipeline covers six intelligence products, a persistence layer for caching and historical comparison, a CLI interface, an optional REST API, and multi-format output rendering. It does not modify the extract pipeline, the eval pipeline, or any existing data models. It operates read-only against the extract pipeline's tables and writes only to its own two new tables.

Out of scope: real-time streaming analysis, external notification/alerting (email, Slack), visualization/charting libraries, natural language generation beyond templated Markdown, and integration with the eval pipeline's run results.

## 3. Core Design Principles

The analysis pipeline follows three principles. First, it is a pure consumer of the extract pipeline's output. It queries EventRecord, ClaimRecord, CrossReference, CandidatePaper, and EnrichedPaper but never modifies them. This clean boundary means the analysis pipeline cannot break collection or processing behavior. Second, analysis results are computed on demand with optional persistence. Expensive or time-sensitive analyses (anomaly detection, digests) persist their results for incremental processing and historical comparison, while simple queries (model profile, leaderboard) compute fresh results each time. Third, the pipeline follows every existing project pattern: async services accepting AsyncSession, Click CLI groups, FastAPI routers, alembic migrations, dataclass result types, and ruff-compliant Python 3.12+ code.

## 4. Primary User Stories

A user who monitors AI model releases wants to see a complete lifecycle for a specific model (e.g., "claude-4-sonnet"): when it was first announced, when pricing appeared, what benchmark scores were reported, whether any claims conflict, and what the current status is. They should be able to run `ai-benchmark analyze model claude-4-sonnet` and see this timeline.

A user tracking benchmark competitions wants to see the current leaderboard for a specific benchmark and how it has changed over time. They should be able to run `ai-benchmark analyze benchmark "SWE-bench Verified"` and see ranked entries with scores and dates.

A user tracking competitive dynamics wants to see which organizations have been most active in the last 30 days and whether multiple vendors released models or pricing changes in the same week. They should be able to run `ai-benchmark analyze competitive --days 30`.

A user overseeing the full pipeline wants a weekly digest summarizing all notable activity: new models, benchmark record changes, pricing moves, competitive clusters, research trends, and flagged anomalies. They should be able to run `ai-benchmark analyze digest --days 7 --format markdown`.

A user who wants automated alerting wants the system to detect and persist notable events (new organizations, benchmark records, conflicting claims, rapid model iteration) without manual review. They should be able to run `ai-benchmark analyze anomalies` and see recently detected insights.

## 5. Functional Requirements

### 5.1 Model Lifecycle Analysis

The model lifecycle service queries all EventRecords for a given model_slug, joins with ClaimRecords for confidence and confirmation data, and assembles a structured profile. The profile includes the model slug, organization, first-seen and latest-activity dates, an inferred status (active, deprecated, announced), an ordered list of milestone events (each with date, event type, title, and confidence tier), a claim summary (counts of confirmed, unconfirmed, and conflicted claims), benchmark scores extracted from raw content, and related models derived from CrossReference "supplements" links.

The service also provides a model listing function that returns all distinct model slugs with event counts and date ranges, filterable by organization. A comparison function accepts a list of model slugs and produces a side-by-side matrix of release dates, event type counts, and claim counts.

### 5.2 Benchmark Trend Analysis

The benchmark trends service filters EventRecords where benchmark_variant is not null, extracts numerical scores from raw_content using regex patterns (percentages like "92.3%", Elo ratings like "1287", and decimal scores like "0.623"), and builds two views: a point-in-time leaderboard (models ranked by score for a given benchmark as of a given date) and a time-series view (how a model's score on a benchmark changes over time).

Score extraction from unstructured text is inherently best-effort. The service handles missing scores gracefully and clearly marks entries where scores could not be extracted.

### 5.3 Competitive Intelligence

The competitive intelligence service queries all EventRecords within a time window, groups them by organization and buckets them by day or week, and produces an activity timeline showing what each vendor did. It also detects "competitive clusters": time windows where two or more organizations had events of the same type (e.g., two vendors both released model updates within the same 7-day window).

Per-organization summaries include event counts by type, active model slugs, and a simple trend indicator (more or fewer events than the prior equivalent period).

### 5.4 Research Pulse

The research pulse service queries EnrichedPapers for citation leaders (top papers by citation_count), parses relevance_tags into topic frequency counts to identify trending research areas, and attempts to detect paper-to-product links by matching enriched paper authors/organizations to model_release EventRecords within a configurable time window. The paper-to-product lag metric captures how long it takes for research to appear as a shipped product.

### 5.5 Anomaly and Milestone Detection

The anomaly detector runs a set of rules against recent data and persists detected insights as AnalysisInsight records. Rules include: new organization appearing for the first time, rapid model iteration (3+ events for the same model_slug within 7 days), benchmark records (a score exceeding the previous maximum for that benchmark_variant), claim conflict detection (claims transitioning to conflicted status), pricing decreases, and new model family prefixes.

The detector is idempotent: it checks whether insights have already been generated for the same event IDs before creating new ones. It runs on recent data only (configurable window, default 7 days) and produces insights with three severity levels: info, notable, and critical.

### 5.6 Periodic Digest

The digest service orchestrates all five preceding services for a given time window and composes a structured report containing: headline insights (top 5 by severity), model updates (models with new activity), benchmark movements (notable rank changes), competitive overview (org activity counts and clusters), research highlights (top papers and trending topics), and summary statistics (total new events, claims, papers).

The digest is always persisted as an AnalysisSnapshot for historical comparison. It supports multiple output formats: plain text for terminal display, Markdown for documentation, JSON for programmatic consumption, and HTML for browser viewing.

### 5.7 Persistence and Incremental Processing

Analysis results are optionally cached in an AnalysisSnapshot table. Each snapshot records the analysis type, scope key, computation timestamp, time window, result JSON, and the number of source events used. On re-run, services can check whether new events exist since the last snapshot to decide whether recomputation is needed.

The anomaly detector and digest service always persist results. The anomaly detector uses a cursor pattern (tracking the latest processed event ID) to ensure incremental processing. Other services (model lifecycle, benchmark trends, competitive intel, research pulse) compute fresh results by default but can be persisted via a bulk `run-all` command.

### 5.8 Output Formatting

A formatter layer converts analysis dataclasses into output formats. Markdown formatters produce structured documents with headers, tables, and lists. JSON formatters use dataclasses.asdict for clean serialization. CSV formatters handle tabular products (model lists, leaderboards). The CLI uses the formatter layer to render results; the API returns JSON directly.

### 5.9 CLI Interface

The analysis pipeline is exposed as a Click group `analyze` registered on the main CLI, following the exact pattern used for the eval group at cli.py:274. Commands include: `models`, `model <slug>`, `benchmark <name>`, `benchmarks`, `competitive`, `research`, `anomalies`, `digest`, and `run-all`. All commands support `--format` and relevant filtering options.

### 5.10 REST API

An optional FastAPI router provides programmatic access to all analysis products, mounted at `/api/analysis/` on the existing eval API app. Endpoints mirror the CLI commands: `/api/analysis/models`, `/api/analysis/models/{slug}`, `/api/analysis/benchmarks`, `/api/analysis/benchmarks/{name}`, `/api/analysis/competitive`, `/api/analysis/research`, `/api/analysis/insights`, `/api/analysis/digest`.
