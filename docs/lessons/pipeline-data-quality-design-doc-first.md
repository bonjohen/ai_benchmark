# Pipeline Data Quality Remediation: Design Doc First

## The Lesson

When a data pipeline has multiple interacting failure modes, writing a design document that catalogs all errors before fixing any of them produces better fixes than addressing errors one at a time. The design doc reveals which failures share root causes and which fixes would conflict.

## Context

A data collection pipeline fetching from 21 sources across 80+ pages accumulated several categories of failures over its first weeks of production operation: database locks, permanent HTTP errors being retried, rate limiting, empty page fetches, incorrect model slug extraction, and missing publisher attribution. Each failure was individually small, but together they degraded data quality significantly — and some fixes interacted (e.g., the database lock fix required changing the deployment architecture, which affected the retry logic).

## What Happened

1. Pipeline logs showed errors across 6 categories: 22 database lock failures, 65 permanent 403 errors retried wastefully, 22 rate limit errors from Semantic Scholar, zero-yield pages from Cloudflare-blocked sites, incorrect model slugs from regex-only extraction, and 160 models with unknown publishers.
2. Rather than fixing errors as they appeared, a design document (`collection_errors_design.md`) was written cataloging all 6 categories with root causes, affected sources, and proposed solutions.
3. The design doc revealed interactions: the database lock fix (single-writer) required stopping the eval server during collection, which changed the deployment script, which was also where retry logic lived. Fixing them independently would have created merge conflicts and possibly regressions.
4. A PDR translated the design into physical implementation requirements, and a phased plan ordered the fixes by dependency: architectural changes (single-writer) first, then fetch-level fixes (retry skip, Playwright), then data-level fixes (slug extraction, publisher mapping).
5. The Playwright fetcher for Cloudflare-blocked pages was added in its own phase because it introduced a new dependency (browser automation) that needed its own testing.
6. Publisher mappings for 160 unknown-publisher models were bulk-applied as a data remediation step after the pipeline fixes were stable.

## Key Insights

- **Error catalogs reveal shared root causes.** The database locks and the retry waste looked like separate bugs, but both stemmed from the same deployment architecture (two processes sharing one SQLite file). The design doc made this connection visible; ticket-by-ticket triage would have missed it.
- **Fix ordering matters when fixes interact.** The single-writer change altered the deployment script. The Playwright addition altered the dependency tree. Doing them in the wrong order would have required rework. The phased plan encoded the correct dependency graph.
- **Data remediation is separate from pipeline remediation.** Fixing the pipeline (so future data is correct) is a different concern from fixing existing data (backfilling slugs, adding publishers). Mixing them in one phase risks breaking production while running backfills.
- **Design docs are cheap insurance for multi-bug fixes.** A design doc for a single bug is overhead. A design doc for 6 interacting bugs saves days of rework. The threshold is roughly "more than 2 interacting failure modes."
- **Log analysis is the design doc's primary input.** The entire design doc was derived from structured analysis of collection logs. If the pipeline hadn't had structured logging, the error catalog couldn't have been built.

## Applicability

Applies to any system experiencing multiple correlated failures: database pipelines, distributed systems, CI/CD infrastructure, monitoring platforms. Does NOT apply to isolated bugs with clear fixes — the overhead of a design doc is not justified for a single, well-understood error.

## Related Lessons

- [SQLite Single-Writer for Async Pipelines](sqlite-single-writer-async-pipelines.md) — One of the specific fixes that emerged from this design process.
- [Playwright Browser Lifecycle in Async Pipelines](playwright-browser-lifecycle-async.md) — Another fix from the same remediation effort.
