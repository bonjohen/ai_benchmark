# Collection Coordinator Design Document

## 1. Purpose

The ai_benchmark collection pipeline produces `sqlite3.OperationalError: database is locked` errors when multiple collection pipelines execute concurrently. This occurs in three scenarios: the APScheduler daemon firing overlapping cron jobs (e.g., OpenAI, Artificial Analysis, and LMArena all fire at `0 */6 * * *`); a manual `ai-benchmark collect` command running while the daemon is active; and running the three pipeline classifications (primary, secondary, discovery-only) in parallel from separate shell invocations.

SQLite permits only a single writer at any given moment. When two `collect_source()` coroutines write to the same database, one receives `OperationalError: database is locked`. Because the current architecture wraps each source's pages in a single session transaction (`scheduler.py:125-178`) and the processing pipeline in a second transaction (`scheduler.py:185-194`), a lock failure rolls back the entire source collection, losing all fetched data for that run. In a concrete test on 2026-03-30, running all 22 sources across three parallel pipelines resulted in only 2 of 22 sources completing successfully — the remaining 20 all failed with cascading lock errors.

This document proposes replacing the current architecture with a centralized coordinator pattern. The coordinator is the single process that reads source configuration, dispatches fetch tasks, and performs all database operations. Workers perform HTTP fetching and HTML extraction only, with no database access. This eliminates write contention by construction: there is exactly one writer.

Beyond fixing the locking problem, the refactor addresses five additional architectural weaknesses: the monolithic `collect_source()` coroutine that mixes I/O, parsing, and persistence; the absence of backpressure between fetching and processing; the in-memory-only health tracker that loses state on restart; the lack of task-level retry granularity; and sequential page processing within a single source despite the pages being independent.

## 2. Current Architecture

The collection pipeline follows a scheduler-driven sequential model. The `PipelineScheduler` (`ai_benchmark/scheduling/scheduler.py:77-244`) is the central orchestrator. It holds an `AsyncIOScheduler` from APScheduler, a `SourceHealthTracker` (in-memory dict, lines 42-75), a shared `Fetcher` (httpx client with `asyncio.Semaphore(5)`, `ai_benchmark/collection/fetcher.py:33-163`), and an `async_sessionmaker` for SQLite (`ai_benchmark/models/base.py:31-33`).

When a cron trigger fires or the user runs `ai-benchmark collect --source X`, the scheduler calls `collect_source(organization)` (`scheduler.py:98-202`). This single coroutine performs every step of collection and processing for one source:

```
                          collect_source(org)
                                |
                    +-----------+-----------+
                    |   Session 1 (pages)   |
                    |                       |
                    |  for page in pages:   |
                    |    fetch HTML          |
                    |    snapshot/diff       |
                    |    extract items       |
                    |  commit                |
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    |  Session 2 (process)  |
                    |                       |
                    |  process_items():     |
                    |    normalize           |
                    |    dedup (3-layer)     |
                    |    create event        |
                    |    create claim        |
                    |    verify              |
                    |    cross-reference     |
                    |  commit                |
                    +-----------+-----------+
```

The flow within a single source is sequential: pages are fetched one at a time inside the `for page in collector.get_pages()` loop (line 139). The Fetcher's semaphore governs cross-source concurrency when multiple `collect_source()` calls overlap, but it does not parallelize pages within a single source.

When the daemon is running, APScheduler fires cron-triggered calls to `collect_source()` independently. With 22 schedule entries in `schedules.toml` and several sources sharing the same hour marks, multiple coroutines write to the database simultaneously:

```
  APScheduler                         SQLite
      |                                 |
      +-- collect_source("OpenAI")  --> Session: write pages, snapshots
      |                                 |
      +-- collect_source("LMArena") --> Session: write pages, snapshots
      |                                        ^-- LOCKED! OpenAI holds write lock
      +-- collect_source("Artificial    |
      |     Analysis")              --> Session: write pages, snapshots
      |                                        ^-- LOCKED! still waiting
```

**Strengths of the current design.** When running a single source at a time, the pipeline is correct and simple. The two-session pattern provides a natural checkpoint: if processing fails, page snapshots are already committed. The `SnapshotManager` and `DiffResult` comparison logic is well-tested. The three-layer dedup strategy (exact composite key, model slug, fuzzy) prevents duplicate events reliably. The collector registry pattern (`COLLECTOR_CLASSES` in `sources/registry.py`) is clean and extensible.

## 3. Problems with Current Approach

### 3.1 SQLite Write Contention

The root cause. SQLite uses a file-level lock for writes. The `async_sessionmaker` creates independent sessions for each `collect_source()` call. When APScheduler fires multiple sources at overlapping times, their sessions compete for the write lock. The default SQLite busy timeout is 5 seconds; if the first writer's transaction takes longer (common when fetching 5-10 pages with snapshot storage), the second writer receives `OperationalError: database is locked`. This rolls back the second writer's entire transaction, losing all fetched data for that source.

### 3.2 Monolithic `collect_source()` Coroutine

The 100-line coroutine at `scheduler.py:98-202` mixes four concerns: configuration lookup (lines 111-121), HTTP I/O (lines 159-165 via `collector.collect_page()`), database persistence (lines 125-178 session 1, lines 185-194 session 2), and health tracking (lines 196-201). This makes it difficult to test any concern independently, retry at a granular level, or restructure the pipeline's concurrency model.

### 3.3 No Backpressure

If the processing pipeline is slow (e.g., dedup queries are expensive for a source with many historical events), there is no mechanism to slow down fetching. In practice this is not yet a problem because fetching and processing happen sequentially within `collect_source()`, but it would become a problem under any design that parallelizes them. A sound architecture should include backpressure by default.

### 3.4 In-Memory Health Tracker

The `SourceHealthTracker` class (lines 42-75 of `scheduler.py`) stores consecutive failure counts and timestamps in a plain dict. This state is lost every time the process restarts. The circuit breaker (trip after 5 consecutive failures) resets on every daemon restart, which means a persistently broken source will be retried indefinitely across restarts, generating noise in logs and wasting rate-limit budget.

### 3.5 No Task-Level Retry

Within `collect_source()`, if one page raises an exception, the `except` block logs a warning and continues to the next page. There is no mechanism to retry just the failed page on the next cycle, no record of which pages failed, and no way to prioritize retrying recently-failed pages. The `Page.consecutive_failures` column exists in the schema (`models/sources.py:43`) but is never incremented.

### 3.6 Sequential Page Processing

The `for page in collector.get_pages()` loop at line 139 processes pages one at a time. For a source like OpenAI with 10 pages, this means 10 sequential HTTP requests (each potentially taking up to 30 seconds). Pages within a source are independent and could be fetched concurrently. The Fetcher has `fetch_many()` (line 102 of `fetcher.py`) which uses `asyncio.gather`, but `collect_source()` does not use it.

## 4. Proposed Architecture: Centralized Coordinator

The new architecture introduces a `CollectionCoordinator` that serves as the single owner of all database access. Workers perform HTTP fetching and HTML extraction as pure functions, reporting results back to the coordinator via an asyncio queue.

```
  +------------------------------------------------------------------+
  |                     CollectionCoordinator                         |
  |                     (single asyncio task)                         |
  |                                                                  |
  |  Reads: source catalog, schedules, page records                  |
  |  Writes: pages, snapshots, events, claims, cross-refs            |
  |  Owns: session factory, health tracker, discovery queue           |
  |                                                                  |
  |  +-------------------+          +----------------------------+   |
  |  | Schedule Reader    |          | Result Processor           |   |
  |  | - reads TOML       |          | - receives FetchResults    |   |
  |  | - creates tasks    |          | - snapshot/diff            |   |
  |  | - applies cadence  |          | - normalize/dedup          |   |
  |  +--------+----------+          | - create events/claims     |   |
  |           |                     | - verify/cross-ref         |   |
  |           v                     | - flush/commit             |   |
  |  +--------+----------+          +------------+---------------+   |
  |  |  Task Queue        |<--- results ------+  |                   |
  |  |  (asyncio.Queue,   |                   |  |                   |
  |  |   bounded)         +--- tasks ----+    |  |                   |
  |  +-------------------+              |    |  |                   |
  +------------------------------------------------------------------+
                                        |    |
                          +-------------+----+------------------+
                          |          Worker Pool                 |
                          |   (N asyncio tasks, same process)    |
                          |                                      |
                          |   Worker 1: fetch URL, extract items  |
                          |   Worker 2: fetch URL, extract items  |
                          |   Worker 3: fetch URL, extract items  |
                          |   ...                                |
                          |                                      |
                          |   NO database access                 |
                          |   Pure: (url, config) -> (items, meta)|
                          +--------------------------------------+
```

### 4.1 Coordinator Responsibilities

The coordinator is a single asyncio task that owns the database session factory and performs all reads and writes. It reads the source catalog and schedule configuration to determine which pages need collection. It creates `FetchTask` objects and places them on a bounded `asyncio.Queue`. It receives `FetchResult` objects from workers and processes them through the existing pipeline: snapshot comparison, normalization, deduplication, event creation, claim creation, verification, and cross-referencing. All of these operations use a single session at a time, so SQLite contention is impossible.

### 4.2 Worker Pool

Workers are asyncio tasks running in the same process (not separate OS processes). Each worker takes a `FetchTask` from the task queue, performs the HTTP fetch using the shared `Fetcher` instance, runs the appropriate collector's `extract_items()` method on the returned HTML, and puts a `FetchResult` (containing the extracted `RawItem` list and fetch metadata) onto the result queue. Workers have no access to the database session. They are pure functions: URL and configuration in, items and metadata out.

The choice to use asyncio tasks in the same process rather than multiprocessing is deliberate. Workers are I/O-bound (HTTP fetch is the bottleneck, not CPU). asyncio tasks avoid IPC serialization overhead, shared-memory complexity, and the need to pickle collector classes. The Fetcher's existing `asyncio.Semaphore(max_concurrency)` already provides HTTP concurrency control.

### 4.3 Task and Result Data Types

```
FetchTask:
    task_id: str                    # unique identifier for tracking
    organization: str               # source org name
    page_url: str                   # canonical URL to fetch
    page_type: str                  # page type from catalog
    page_id: int | None             # DB page ID (coordinator's use on result)
    source_id: int                  # DB source ID (coordinator's use on result)
    classification: str             # primary/secondary/discovery-only
    collector_class_name: str       # registry key for instantiating collector
    since_date: date | None         # backfill date filter

FetchResult:
    task_id: str                    # matches the originating FetchTask
    organization: str
    page_url: str
    page_type: str
    page_id: int | None
    source_id: int
    classification: str
    items: list[RawItem]            # extracted items (may be empty)
    html_content: str               # raw HTML for snapshot storage
    fetch_status: int               # HTTP status code
    fetch_error: str | None         # error message if fetch failed
    elapsed_ms: float               # fetch duration
    fetched_at: datetime            # timestamp
```

The coordinator creates `FetchTask` objects by reading the source catalog and looking up `page_id` and `source_id` from the database. Workers receive the task, perform the fetch and extraction, and return a `FetchResult`. The coordinator uses the result's DB identifiers to perform all persistence operations.

### 4.4 Task Lifecycle

```
  Pending ---------> Dispatched ---------> Completed
                         |                     |
                         +--------> Failed ----+
                                      |
                                      v
                                  (retry queue, up to N retries)
```

The coordinator tracks task state internally. A task is Pending when created, Dispatched when placed on the queue, Completed when the result is processed, and Failed when the fetch returns an error or the worker raises an exception. Failed tasks are re-queued up to a configurable retry limit (default: the existing `retry_attempts=3` from settings), with exponential backoff applied by the coordinator before re-dispatch.

### 4.5 Write Serialization

Because only the coordinator writes to the database, and the coordinator is a single asyncio task, all writes are naturally serialized. The coordinator processes results one at a time from the result queue. Within a single result's processing, it opens a session, performs all pipeline steps, and commits. There is never a second concurrent writer.

This is the key architectural invariant: **the coordinator is the only entity that holds a database session.**

### 4.6 Backpressure

The task queue is a bounded `asyncio.Queue(maxsize=N)` where N is configurable (default: 2x worker count). When the queue is full, the coordinator's `put()` call blocks until a worker takes a task. Similarly, the result queue is bounded: if the coordinator is slow to process results, workers block on `put()`, which transitively slows down fetching. This prevents unbounded memory growth and ensures the pipeline self-regulates.

### 4.7 Health Tracking Persistence

The coordinator persists health state to the database instead of an in-memory dict. The `Page.consecutive_failures` column (already present in the schema but unused) will be incremented on fetch failures and reset on success. The circuit breaker logic moves from the in-memory `SourceHealthTracker` to a query against the Page table: a source is circuit-broken when all of its pages have `consecutive_failures >= MAX_CONSECUTIVE_FAILURES`.

### 4.8 Scheduling Integration

The coordinator replaces APScheduler's direct invocation of `collect_source()`. It runs its own scheduling loop: reads `schedules.toml`, computes which sources are due for collection based on their cron expressions and `Page.last_polled_at` timestamps, and creates `FetchTask` objects for those sources' pages. This eliminates the need for APScheduler's `max_instances` parameter and gives the coordinator full visibility into what is running.

APScheduler may be retained as an optional timer that wakes the coordinator's scheduling loop, or replaced with a simpler `asyncio.sleep()` loop that checks schedules every minute.

## 5. Data Flow Comparison

**Current flow (per source, sequential):**

```
  Schedule trigger
       |
       v
  collect_source(org)
       |
       v
  Load source config from TOML
       |
       v
  Open Session 1
       |
       v
  for each page (sequential):
       |
       +---> Fetch HTML (via Fetcher)
       +---> Compare snapshot (SnapshotManager, DB read+write)
       +---> Extract items (Collector.extract_items)
       |
       v
  Commit Session 1  <-- DB WRITE (pages, snapshots)
       |
       v
  Open Session 2
       |
       v
  process_items()
       +---> Normalize (pure function)
       +---> Dedup (DB read)
       +---> Create EventRecord (DB write)
       +---> Create ClaimRecord (DB write)
       +---> Verify (DB read+write)
       +---> Cross-reference (DB read+write)
       |
       v
  Commit Session 2  <-- DB WRITE (events, claims, cross-refs)
       |
       v
  Update health tracker (in-memory, lost on restart)
```

**Proposed flow (coordinator + workers):**

```
  Coordinator (single task)              Workers (N asyncio tasks)
       |                                       |
       v                                       |
  Check schedules                              |
       |                                       |
       v                                       |
  Read source catalog + page records           |
  (DB READ -- coordinator only)                |
       |                                       |
       v                                       |
  Create FetchTasks                            |
       |                                       |
       +---- put(FetchTask) ---> Task Queue    |
       |                              |        |
       |                              +------->+
       |                                       |
       |                              Worker takes task
       |                              Fetch HTML (Fetcher)
       |                              Extract items (Collector)
       |                              No DB access
       |                                       |
       |                              +--------+
       |                              |
       +<--- get(FetchResult) <- Result Queue
       |
       v
  Process result (coordinator only):
       +---> Store snapshot (DB WRITE)
       +---> Compare with latest (DB READ)
       +---> Normalize (pure function)
       +---> Dedup (DB READ)
       +---> Create EventRecord (DB WRITE)
       +---> Create ClaimRecord (DB WRITE)
       +---> Verify (DB READ+WRITE)
       +---> Cross-reference (DB READ+WRITE)
       +---> Update page metadata (DB WRITE)
       +---> Update health state (DB WRITE)
       |
       v
  Commit session
       |
       v
  Next result (or next schedule check)
```

The critical difference: all boxes labeled "DB" appear only in the left column (coordinator). The right column (workers) never touches the database.

## 6. Component Responsibilities

| Component | Current Owner | Proposed Owner | Change |
|-----------|---------------|----------------|--------|
| Source catalog reads | `collect_source()` | Coordinator | Move to coordinator init |
| Page record lookup/create | Session 1 in `collect_source()` | Coordinator | Move to task creation phase |
| HTTP fetch | `Fetcher` via `collect_page()` | Worker pool via `Fetcher` | Workers call `Fetcher.fetch()` directly |
| HTML extraction | `Collector.extract_items()` | Worker pool | Workers instantiate collector, call `extract_items()` |
| Snapshot storage | `SnapshotManager` (Session 1) | Coordinator | Coordinator stores snapshot from worker's HTML |
| Snapshot diff | `SnapshotManager` (Session 1) | Coordinator | Coordinator compares after receiving HTML |
| Normalization | `pipeline.process_item()` | Coordinator | No change to logic |
| Deduplication | `pipeline.process_item()` | Coordinator | No change to logic |
| Event/claim creation | `pipeline.process_item()` | Coordinator | No change to logic |
| Verification | `pipeline.process_item()` | Coordinator | No change to logic |
| Cross-referencing | `pipeline.process_item()` | Coordinator | No change to logic |
| Discovery queue | `check_and_enqueue()` | Coordinator | No change, already uses session |
| Health tracking | `SourceHealthTracker` (in-memory) | Coordinator (persistent) | Replace dict with Page table updates |
| Schedule management | APScheduler `AsyncIOScheduler` | Coordinator (schedule loop) | Replace job dispatch with coordinator-driven scheduling |
| Quality filtering | `is_low_value_page()` | Coordinator | Move to result processing |

## 7. Key Files Affected

### Modified Files

| File | Change |
|------|--------|
| `ai_benchmark/scheduling/scheduler.py` | Refactor `PipelineScheduler` to delegate to `CollectionCoordinator`. `SourceHealthTracker` moves to persistent storage. |
| `ai_benchmark/cli.py` | `collect` and `run` commands instantiate coordinator instead of scheduler directly. |
| `ai_benchmark/sources/base.py` | `collect_page()` split: workers call a new `fetch_and_extract()` that does not require `SnapshotManager` or session. |
| `ai_benchmark/collection/snapshot.py` | `SnapshotManager` unchanged but called only from coordinator context. |
| `ai_benchmark/processing/pipeline.py` | `process_items()` unchanged but called only from coordinator context. |

### New Files

| File | Purpose |
|------|---------|
| `ai_benchmark/coordination/__init__.py` | Package init. |
| `ai_benchmark/coordination/coordinator.py` | `CollectionCoordinator`: schedule loop, task creation, result processing, session management. |
| `ai_benchmark/coordination/worker.py` | Worker loop coroutine: takes tasks from queue, fetches, extracts, returns results. |
| `ai_benchmark/coordination/types.py` | `FetchTask` and `FetchResult` dataclasses. |
| `tests/test_coordination/test_coordinator.py` | Unit tests for coordinator logic. |
| `tests/test_coordination/test_worker.py` | Unit tests for worker logic. |

## 8. Migration Path

Each phase is independently shippable and testable.

**Phase 1: Extract worker logic.** Create `coordination/types.py` with `FetchTask` and `FetchResult` dataclasses. Create `coordination/worker.py` with a `fetch_and_extract()` function that takes a `FetchTask` and a `Fetcher`, performs the HTTP fetch and HTML extraction, and returns a `FetchResult`. This is a pure extraction of the fetch-and-extract portion of `collect_page()` from `sources/base.py`. The existing `collect_source()` is not modified. Tests validate that `fetch_and_extract()` produces the same `RawItem` lists as the current `collect_page()` for each collector type.

**Phase 2: Build coordinator core.** Create `coordination/coordinator.py` with the `CollectionCoordinator` class. Implement the task queue, result queue, worker pool, and result processing loop. The coordinator's result processor calls the existing `SnapshotManager.compare_with_latest()` and `process_items()` functions unchanged. Add a `collect_all()` method that accepts a list of organizations and coordinates their collection. Test by running `collect_all(["OpenAI"])` against the dev database and verifying identical results to the current `collect_source("OpenAI")`.

**Phase 3: Wire into CLI.** Modify `cli.py` so that the `collect` command uses `CollectionCoordinator` instead of `PipelineScheduler.collect_source()`. The `run` (daemon) command still uses APScheduler, but each triggered job calls the coordinator's `collect_org()` method instead of `collect_source()`. This is a minimal integration that proves the coordinator works in production without changing the scheduling model.

**Phase 4: Replace APScheduler dispatch.** Move schedule management into the coordinator. The `run` command starts the coordinator's own scheduling loop instead of APScheduler. APScheduler is removed as a dependency (or retained only for its cron-expression parser). Health tracking moves to persistent storage via `Page.consecutive_failures`. The `SourceHealthTracker` class is deprecated.

**Phase 5: Cleanup.** Remove the `collect_source()` method from `PipelineScheduler`. Remove `SourceHealthTracker`. Update `CLAUDE.md` architecture section. Remove APScheduler if it is no longer used elsewhere.

## 9. Risks and Mitigations

**Single point of failure.** The coordinator is a single task. If it crashes or deadlocks, all collection stops. *Mitigation:* The coordinator's main loop wraps each result-processing cycle in try/except that logs the error and continues. A watchdog timer detects if the coordinator has not processed a result in N minutes and restarts it. The CLI `collect` command can still invoke single-source collection synchronously as a fallback.

**Coordinator becomes a bottleneck.** If result processing is slower than fetching, the result queue fills up and workers idle. *Mitigation:* Result processing is dominated by database I/O (SQLite writes), which is fast for single-row inserts. Batch flushes (every 100 items, as currently in `process_items()`) amortize commit overhead. If profiling shows the coordinator is the bottleneck, result processing can be parallelized across sources (each source's results in a separate asyncio task with its own session, serialized per-source but parallel across sources).

**Worker errors not surfaced.** If a worker raises an unhandled exception, the task is lost. *Mitigation:* Workers wrap all logic in try/except and return a `FetchResult` with `fetch_error` populated. The coordinator checks `fetch_error` and applies retry logic (re-queue with backoff) or marks the task as permanently failed. Task accounting ensures every dispatched task is eventually resolved.

**Migration regression.** The coordinator must produce identical results to the current pipeline for all 22 sources. *Mitigation:* Phase 1 includes a comparison test: for each collector type, run the current `collect_page()` and the new `fetch_and_extract()` on the same HTML fixture and assert identical `RawItem` lists. Phase 3 includes an integration test: run coordinator-based collection for all sources and diff event counts against a baseline.

**Snapshot comparison requires session.** The current `SnapshotManager.compare_with_latest()` reads the latest snapshot from the database and writes the new snapshot. Workers cannot perform this step. *Mitigation:* The coordinator performs snapshot comparison after receiving the worker's result. The worker returns raw HTML in `FetchResult.html_content`, and the coordinator passes it to `SnapshotManager.compare_with_latest()`. The minor cost is that raw HTML is held in memory on the result queue until the coordinator processes it; for current page sizes (typically 50-500 KB), this is negligible.

**Collectors with custom `collect_page()` overrides.** Three collectors override `collect_page()` to call APIs directly: `GitHubDiscoveryCollector`, `SemanticScholarCollector`, and `MetaCollector`. These overrides bypass the standard fetch-extract pattern. *Mitigation:* Workers detect when a collector has a custom `collect_page()` and call it directly (passing only the Fetcher, not a SnapshotManager or session). The worker wraps the returned items into a `FetchResult`. The coordinator handles these results identically to standard results, except it skips snapshot comparison (API responses are not HTML pages to diff).
