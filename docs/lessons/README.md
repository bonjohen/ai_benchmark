# Lessons Learned

Reusable patterns and mistakes extracted from real work on the ai_benchmark project.

## Data & Content Quality

- [Model Slug Extraction: Dictionary Lookup Over Pure Regex](model-slug-extraction-dictionary-lookup.md) — Known-value dictionaries with normalization beat regex-only entity extraction
- [RSS as Fallback Collection Method](rss-fallback-collection-method.md) — Google News RSS bypasses anti-bot defenses but needs enrichment for usable descriptions

## Architecture & Design

- [SQLite Single-Writer for Async Pipelines](sqlite-single-writer-async-pipelines.md) — WAL mode doesn't fix multi-process writer contention; serialize writers architecturally
- [Playwright Browser Lifecycle in Async Pipelines](playwright-browser-lifecycle-async.md) — Shared browser singletons need async locks at creation and explicit cleanup at shutdown
- [Two-Stage Report Generation: Extract Then Synthesize](two-stage-report-generation.md) — Separate deterministic data extraction from LLM synthesis for testability and cost control
- [ETL-Only Branch: Surgical Code Removal](etl-only-branch-surgical-removal.md) — Remove in dependency order (packages → CLI → migrations → deps → tests → deployment)

## Process & Methodology

- [Pipeline Data Quality Remediation: Design Doc First](pipeline-data-quality-design-doc-first.md) — Catalog all errors before fixing any; the design doc reveals shared root causes
- [Revert as a Design Signal](revert-as-design-signal.md) — Reverts mean the approach had a gap, not just a bug; pause to reflect before re-implementing
- [Revert-Restore-Reapply: Safe Source Catalog Changes](revert-restore-reapply-safe-catalog-changes.md) — Never bundle additive and destructive config changes in one commit

## Operations & Billing

- [OAuth Credit Routing for CLI Tools](oauth-credit-routing-cli-tools.md) — Scripts must explicitly select the billing path; environment variable precedence silently misroutes charges
