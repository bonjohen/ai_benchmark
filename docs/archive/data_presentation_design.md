# Data Presentation & Intelligence Products Design Document

## 1. Purpose

The ai_benchmark system has a complete collection pipeline (22 sources, 87 pages) and a complete analysis pipeline (6 services: model lifecycle, benchmark trends, competitive intelligence, research pulse, anomaly detection, periodic digest). The analysis pipeline produces structured intelligence at the individual-service level — a model profile here, a leaderboard there, an anomaly list somewhere else. However, there is no mechanism to synthesize across these services to answer the questions that matter most: "Which new models are actually good?", "How fast are benchmarks improving?", "Who is winning the AI race right now?"

Industry platforms like Artificial Analysis (composite intelligence index, price-performance scatter plots), LMArena (ELO rankings with confidence intervals across categories), HELM (multi-dimensional radar charts across 42 scenarios), Papers With Code (state-of-the-art tracking per benchmark), and Epoch AI (historical compute and performance frontier trends) all answer these questions by combining multiple data dimensions into synthesized views. The ai_benchmark system already collects the underlying data — EventRecords with benchmark scores, model slugs, organizations, pricing changes, and timestamps; ClaimRecords with confidence tiers and confirmation statuses; CrossReferences linking corroborating sources; EnrichedPapers with citation counts and relevance tags — but does not yet produce the higher-order products that make the data actionable.

The Data Presentation & Intelligence Products layer sits on top of the existing six analysis services, composing their outputs into seven new intelligence products. Each product answers a specific class of question, and together they transform the system from a data repository into an intelligence platform. No new data collection is required.

## 2. Scope

This design covers seven intelligence products organized into three priority tiers. Tier 1 addresses the user's explicit requests (new model spotlight, benchmark evolution). Tier 2 adds industry-standard views (capability profiles, competitive landscape, research pipeline). Tier 3 adds advanced analytics (claim verification, benchmark correlation).

Each product includes a service function (async, accepting AsyncSession), result dataclasses, CLI subcommand, API endpoint, and formatter output. Products are independent — Tier 1 can ship without Tiers 2 or 3.

In scope: new service functions in the existing `ai_benchmark/analysis/services/` package, new dataclasses in `types.py`, new CLI subcommands in `cli.py`, new API endpoints in `api.py`, new formatters in `formatters/`, and integration into the existing digest. No new database tables are required — all results use the existing AnalysisSnapshot for optional persistence.

Out of scope: interactive visualization (Chart.js, D3), real-time streaming, external notifications (email, Slack, webhooks), natural language generation beyond templated Markdown, integration with the eval pipeline's run results, and new data collection sources or collection methods.

## 3. Core Design Principles

The first principle is composition over creation. The six existing analysis services — `list_tracked_models()`, `build_model_profile()`, `get_benchmark_leaderboard()`, `get_benchmark_timeline()`, `get_activity_timeline()`, `detect_competitive_clusters()`, `get_research_trends()`, `detect_anomalies()`, `generate_digest()` — already query the underlying tables and return structured results. The new products compose these service calls with additional join and aggregation logic rather than re-querying from scratch. Where a service already fetches the data, the presentation layer calls it and post-processes. Where no service covers the query, the new product adds a targeted query following the same async session pattern.

The second principle is no new collection. Every product computes entirely from data already in EventRecord, ClaimRecord, CrossReference, CandidatePaper, and EnrichedPaper. The data fields that are currently underutilized — `evaluation_conditions`, `version`, CrossReference graph relationships, `confidence_tier` distributions, and benchmark variant inter-relationships — are surfaced in the new products without requiring any changes to the collection or processing pipelines.

The third principle is graceful degradation. Score extraction from raw_content is regex-based and inherently lossy (`extract_benchmark_score()` in benchmark_trends.py uses a 4-priority chain: percentage, Elo-like, decimal fraction, bare integer). Products that depend on scores handle None values without breaking. Products that require a minimum data threshold (correlation matrix needs overlapping models, capability profile needs multiple benchmark variants) report when data is insufficient rather than producing misleading results.

The fourth principle is independent delivery. Products are not interdependent. The spotlight report does not require the correlation matrix. The evolution dashboard does not require the verification dashboard. This allows phased delivery: Tier 1 first (the user's explicit requests), then Tier 2 and Tier 3 as incremental additions.

## 4. Primary User Stories

A user who tracks the AI industry wants to see which models appeared in the last month and how they stack up. They run `ai-benchmark analyze spotlight --days 30` and see a ranked list of new models with their best benchmark scores, number of benchmarks evaluated, cross-reference confirmation depth, and any anomaly flags. The report answers "What's new and good?" in one view.

A user who monitors benchmark progress wants to understand how a specific benchmark is evolving. They run `ai-benchmark analyze evolution --benchmark "SWE-bench Verified" --days 180` and see the rate of improvement per month, the current frontier (record-holding model and score), saturation analysis (how close the top score is to the theoretical ceiling), and the historical sequence of record-breaking models. The report answers "Is this benchmark still differentiating?" and "How fast is the field improving?"

A user who evaluates models for deployment wants to see how a model performs across all benchmarks where it has been tested. They run `ai-benchmark analyze capability gpt-5` and see normalized scores (percentile rank) for each benchmark variant, a composite capability score, and a comparison-ready capability vector. The report answers "Is this model broadly capable or narrowly specialized?"

A user who tracks competitive dynamics wants a synthesized view of the AI landscape. They run `ai-benchmark analyze landscape --days 30` and see each organization's model count, new model releases, average benchmark ranking, best single result, pricing changes, and competitive cluster participation. The report answers "Who is winning, and who is gaining ground?"

A user who monitors research trends wants to understand the research-to-product pipeline. They run `ai-benchmark analyze research-pipeline --days 90` and see papers with the highest citation velocity, topics that are trending up or down, and papers that preceded product releases with their lag times. The report answers "What research is about to become a product?"

A user who wants to assess the reliability of the knowledge base runs `ai-benchmark analyze verification` and sees confirmation depth per model (how many independent sources corroborate each claim), confidence tier distribution, conflict rates, and the models with the strongest and weakest verification. The report answers "How much can I trust this data?"

A user who wants to understand benchmark relationships runs `ai-benchmark analyze correlations` and sees which benchmark pairs are highly correlated (models that score well on one tend to score well on the other) and which are independent (measuring distinct capabilities). The report answers "Which benchmarks are redundant and which are complementary?"

## 5. Functional Requirements

### 5.1 New Model Spotlight Report

The spotlight service identifies models whose `first_seen` date falls within a configurable window (default 30 days) and enriches them with benchmark performance data. For each model, the report includes: model slug, organization, first-seen date, status (active/announced/deprecated), the number of benchmark variants where the model has been evaluated, the best score per benchmark variant, a "debut strength" indicator computed as the number of benchmarks where the model ranks in the top 3 among all tracked models, the cross-reference count (how many independent sources confirm the model's existence via CrossReference relationships), and whether any AnalysisInsight records of type `new_model` or `benchmark_record` exist for the model.

The service composes existing calls: `list_tracked_models()` filtered by `first_seen >= cutoff` to get new models, `get_benchmark_leaderboard()` per benchmark variant to compute rankings, and `get_recent_insights()` filtered by `related_model_slug` for anomaly context. The new join logic scores each model by debut strength and sorts descending.

Parameters: `window_days` (default 30), `min_benchmarks` (default 1, filters out models with fewer benchmark entries), `organization` (optional filter). Returns a list of SpotlightEntry dataclasses sorted by debut strength.

CLI: `ai-benchmark analyze spotlight [--days 30] [--min-benchmarks 1] [--org ORG] [--format text|json|markdown|csv]`
API: `GET /api/analysis/spotlight?days=30&min_benchmarks=1&org=ORG`

### 5.2 Benchmark Evolution Dashboard

The evolution service computes temporal aggregate statistics for each benchmark or a specified benchmark. For each benchmark variant, it produces: total score improvement over the window (latest top score minus earliest top score), rate of improvement (score gain per month), current leader (model slug and score), gap to second place, number of distinct models evaluated in the window, a saturation indicator (whether the top score is within 5% of a theoretical ceiling — 100% for percentage-based benchmarks, or the maximum observed score if no ceiling is known), the date of the most recent record-breaking score, and a "frontier progression" — the chronological sequence of record-holding models and their scores.

The saturation indicator uses heuristics: if the benchmark's highest score is a percentage, the ceiling is 100%; if the benchmark name contains "Elo" or the scores are in the 1000-2000 range, there is no fixed ceiling and saturation is not computed; otherwise, the ceiling is estimated as the highest observed score plus 10%.

The frontier progression is the sequence of `(date, model_slug, score)` tuples where each entry represents a new all-time high for that benchmark variant, ordered chronologically.

Parameters: `benchmark_name` (optional, if omitted produces summaries for all benchmarks), `window_days` (default 180). Returns EvolutionSummary dataclass or list thereof.

CLI: `ai-benchmark analyze evolution [--benchmark NAME] [--days 180] [--format text|json|markdown|csv]`
API: `GET /api/analysis/evolution?benchmark=NAME&days=180`

### 5.3 Cross-Benchmark Model Capability Profile

The capability service takes a model slug and retrieves its scores across all benchmark variants where it has been evaluated. Raw scores are normalized to percentile rank within each benchmark: for each variant, the model's score is positioned relative to all known scores for that variant (0th percentile = worst, 100th = best). This solves the apples-to-oranges problem of comparing a percentage on SWE-bench to an ELO on LMArena.

The service also computes a composite capability score: a weighted average of percentile ranks across all benchmarks where the model has data. Default weights are equal; a custom weight map (benchmark_variant → weight) can be passed. This mirrors Artificial Analysis's Intelligence Index concept.

The capability vector (list of `(benchmark_variant, percentile_rank)` tuples) is structured to support downstream radar/spider chart visualization if a UI layer is added later.

Parameters: `model_slug`, `weights` (optional dict of benchmark → weight, default equal). Returns CapabilityProfile dataclass containing the model slug, organization, benchmark count, per-benchmark percentile ranks, composite score, and the raw underlying scores.

For comparison, the service also accepts a list of model slugs and returns profiles for all of them in a single call, enabling side-by-side comparison.

CLI: `ai-benchmark analyze capability <slug> [--compare slug2,slug3] [--format text|json|markdown]`
API: `GET /api/analysis/capability/{slug}` and `GET /api/analysis/capability?models=slug1,slug2,slug3`

### 5.4 Competitive Landscape Summary

The landscape service extends the existing competitive intelligence with benchmark context. For each organization active in the window, it produces: total model count, new model count (first_seen in window), the list of active model slugs, benchmark evaluation breadth (number of distinct benchmarks where any org model has been evaluated), average percentile ranking across all org models and benchmarks (using the normalization from the capability service), the organization's single best benchmark result (model slug, benchmark variant, score), pricing event count and whether any price_drop anomaly insights exist, competitive cluster participation count, and a trend indicator comparing event counts to the prior equivalent period.

This product answers "Who is winning, and who is gaining ground?" by combining activity volume, benchmark quality, and pricing strategy in a single view.

Parameters: `window_days` (default 30), `organization` (optional, for single-org detail view). Returns LandscapeSummary dataclass or list of OrgLandscapeEntry dataclasses.

CLI: `ai-benchmark analyze landscape [--days 30] [--org ORG] [--format text|json|markdown]`
API: `GET /api/analysis/landscape?days=30&org=ORG`

### 5.5 Research-to-Product Pipeline Intelligence

The pipeline service enhances the existing research_pulse data with velocity and trend analysis. For each enriched paper, it computes citation velocity (citations per week since the paper's `enriched_at` date). For each relevance tag, it computes a trend direction by comparing tag frequency in the recent half of the window to the earlier half (rising if recent > earlier by more than 20%, falling if less by more than 20%, stable otherwise).

The service also produces a "predictive signals" list: papers with above-median citation velocity in topics whose tags have historically appeared on papers that preceded model_release events (using the existing `detect_paper_to_product()` output as training data). This is a simple heuristic, not ML — it identifies papers in "hot" topics that have a track record of becoming products.

The paper-to-product links from the existing service are enriched with citation velocity at the time of product release, enabling analysis of whether highly-cited papers become products faster.

Parameters: `window_days` (default 90), `min_citations` (default 0, filters out papers with fewer citations). Returns ResearchPipelineReport dataclass.

CLI: `ai-benchmark analyze research-pipeline [--days 90] [--format text|json|markdown]`
API: `GET /api/analysis/research-pipeline?days=90`

### 5.6 Claim Verification Dashboard

The verification service surfaces the confirmation depth and reliability of the knowledge base. For each model slug, it computes: total claim count, percentage of claims with `confirmation_status = 'confirmed'`, percentage with `conflicted`, the number of distinct `source_name` values across claims (corroboration breadth), the highest `confidence_tier` achieved (ordered: `official_self_report` > `benchmark_owner_report` > `high_secondary` > `medium_discovery` > `low_discovery`), and the number of CrossReference relationships of type `confirms` involving events for this model.

For each benchmark variant, it computes: the number of distinct sources reporting scores, whether any claims are in conflict, and the score variance across sources (high variance suggests contested results).

A system-level summary includes: total events, total claims, overall confirmation rate, conflict rate, and the distribution of claims across the five confidence tiers.

This product is unique to the ai_benchmark system — industry platforms do not expose their verification methodology. It provides transparency into how much to trust each data point.

Parameters: `organization` (optional filter), `model_slug` (optional filter). Returns VerificationReport dataclass.

CLI: `ai-benchmark analyze verification [--org ORG] [--model SLUG] [--format text|json|markdown|csv]`
API: `GET /api/analysis/verification?org=ORG&model=SLUG`

### 5.7 Benchmark Correlation Matrix

The correlation service computes pairwise Spearman rank correlation coefficients between benchmark variants. For each pair of benchmarks with at least `min_overlap` models that have scores on both benchmarks, it computes the rank correlation of model scores. A high correlation (> 0.8) suggests the benchmarks measure similar capabilities; a low correlation (< 0.3) suggests they measure distinct capabilities.

The output is a symmetric matrix of benchmark variant pairs with their correlation coefficient, the number of overlapping models, and a qualitative label (redundant/similar/moderate/distinct/independent). The matrix also identifies benchmark clusters — groups of benchmarks that are all highly correlated with each other.

This product helps users understand which benchmarks to pay attention to and which are measuring the same thing.

Parameters: `min_overlap` (default 5, minimum models with scores on both benchmarks). Returns CorrelationMatrix dataclass containing entries (benchmark_a, benchmark_b, correlation, overlap_count, label) and clusters.

CLI: `ai-benchmark analyze correlations [--min-overlap 5] [--format text|json|csv]`
API: `GET /api/analysis/correlations?min_overlap=5`

### 5.8 Enhanced Digest Integration

The existing `generate_digest()` function in `services/digest.py` is extended to include spotlight models and benchmark evolution summaries. The digest's `headline_insights` list gains entries for top new models (from the spotlight) and benchmark saturation warnings (from evolution). The `DigestReport` dataclass is extended with optional `spotlight_models` and `evolution_highlights` fields.

This ensures the weekly digest — the system's primary output product — surfaces the new intelligence automatically without requiring users to run separate commands.

### 5.9 Output Formatting

Each new product type gets a markdown renderer in `formatters/markdown.py`, following the existing pattern of building a list of lines and joining with newlines. Tabular products (spotlight, landscape, correlations, verification) get CSV exporters in `formatters/csv_export.py`. All products use the existing `to_json()` from `formatters/json_export.py` via `dataclasses.asdict()`.

The text format for CLI output reuses the markdown renderer with simple terminal-friendly adjustments (no `#` headers, use underlines instead).
