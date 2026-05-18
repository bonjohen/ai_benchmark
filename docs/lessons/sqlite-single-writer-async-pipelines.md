# SQLite Single-Writer for Async Pipelines

## The Lesson

SQLite supports exactly one concurrent writer. When an async pipeline shares a database with a long-running server process, the fix is architectural (serialize writers) — not a PRAGMA tweak. WAL mode reduces contention but does not eliminate it.

## Context

A data collection pipeline runs on a schedule, fetching pages and writing events to a SQLite database. A separate eval server process reads and writes the same database for its own purposes. Both are async Python (SQLAlchemy async sessions, httpx). The pipeline runs on Windows where SQLite locking behavior differs subtly from Linux. Collection runs produced intermittent "database is locked" errors that grew worse as more sources were added.

## What Happened

1. Collection logs showed 22 `collection_failed` errors caused by SQLite write locks — the eval server and collection process competed for the single write lock.
2. Initial instinct was to enable WAL mode (`PRAGMA journal_mode=WAL`), which allows concurrent reads during writes. A design doc was written exploring this option.
3. The design doc concluded WAL was insufficient: WAL still allows only one writer, and the real problem was two separate processes both writing. WAL would reduce read contention but not fix write collisions.
4. The architectural fix was a single-writer pattern: the collection batch script stops the eval server before collection starts and restarts it after collection completes.
5. The same investigation revealed 65 wasted retries on permanently 403-blocked pages (Cloudflare) and 58 fetch failures that would never succeed. The fix skipped retries for permanent failures.
6. Semantic Scholar rate limiting (22 errors) was fixed by increasing inter-query delay from 3s to 30s for unauthenticated access.

## Key Insights

- **WAL is not a concurrency solution for writers.** WAL mode is often recommended as the "fix" for SQLite concurrency, but it only helps readers coexist with a single writer. Two writers still block each other. Understanding this distinction saves a round of failed fixes.
- **Architectural constraints beat runtime configuration.** Stopping the server during batch collection is crude but correct — it makes the single-writer constraint impossible to violate, rather than hoping timeout and retry logic handles it.
- **Permanent failures should not be retried.** A 403 from Cloudflare will not succeed on retry. Categorizing failures as transient vs. permanent and skipping retries for permanent ones eliminated over 120 wasted requests per collection run.
- **Rate limits need per-source tuning.** A 3-second delay is fine for most APIs but far too aggressive for Semantic Scholar without an API key. Per-source delay configuration prevents one source's rate limits from cascading into pipeline-wide failures.
- **Design docs catch bad fixes before implementation.** The initial "just enable WAL" instinct would have shipped, been deployed, and failed in production. Writing the design doc forced a deeper analysis that found the real problem.

## Applicability

Applies to any system using SQLite with multiple writer processes — web apps with background workers, CLI tools sharing a database with a server, multi-process ETL pipelines. Does NOT apply to PostgreSQL/MySQL where true concurrent writes are supported, or to read-only workloads where WAL genuinely helps.

## Related Lessons

- [Pipeline Data Quality Remediation](pipeline-data-quality-design-doc-first.md) — The broader remediation effort that included this fix.
