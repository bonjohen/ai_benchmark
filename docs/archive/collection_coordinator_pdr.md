# Physical Design Requirements: Collection Coordinator

**Source document:** `docs/collection_coordinator_design.md`
**Project root:** `C:\Projects\ai_benchmark`
**Date:** 2026-03-30 08:15 PM (PST)

## 1. System Context

### 1.1 Existing Infrastructure to Reuse

| Asset | Location | Reuse |
|---|---|---|
| `Fetcher` class | `ai_benchmark/collection/fetcher.py:33-163` | Workers call `fetch()` directly. Shared instance, concurrency governed by existing `asyncio.Semaphore(max_concurrency)`. No changes. |
| `FetchResult` (fetcher) | `ai_benchmark/collection/fetcher.py:17-30` | Workers receive from `Fetcher.fetch()`. Distinct from coordinator's `CoordFetchResult`. No changes. |
| `SnapshotManager` | `ai_benchmark/collection/snapshot.py:23-104` | Coordinator calls `compare_with_latest(page_id, html, selectors)`. Requires `AsyncSession` at init. No changes. |
| `DiffResult` | `ai_benchmark/collection/differ.py:69-77` | Returned by `SnapshotManager`. Coordinator passes to quality filter. No changes. |
| `process_items()` | `ai_benchmark/processing/pipeline.py:167-207` | Coordinator calls after snapshot comparison. No changes. |
| `is_low_value_page()` | `ai_benchmark/processing/quality_filter.py:32-88` | Coordinator calls after snapshot diff. No changes. |
| `get_collector()` | `ai_benchmark/sources/registry.py:73-82` | Workers call to instantiate collectors. Passes `github_token` and `semantic_scholar_api_key`. No changes. |
| `SourceCollector` ABC | `ai_benchmark/sources/base.py:91-287` | Workers call `extract_items(html, page)`. No changes to base class. |
| `RawItem` dataclass | `ai_benchmark/sources/base.py:78-88` | Carried in `CoordFetchResult.items`, passed to `process_items()`. No changes. |
| `PipelineSettings` | `ai_benchmark/config/settings.py:43-75` | Coordinator reads `max_concurrency`, `retry_attempts`, `database_url`, tokens. No changes. |
| `SourceConfig` / `PageConfig` | `ai_benchmark/config/settings.py:18-40` | Coordinator reads via `load_source_catalog()`. Workers receive fields via `FetchTask`. No changes. |
| `load_source_catalog()` | `ai_benchmark/config/settings.py:78-89` | Coordinator calls at task creation. No changes. |
| `Page` model | `ai_benchmark/models/sources.py:31-49` | Coordinator reads/writes `consecutive_failures` (line 43, exists but currently unused), `last_polled_at`, `last_changed_at`, `times_polled`. No schema changes. |
| `Source` model | `ai_benchmark/models/sources.py:13-28` | Coordinator reads `id`, `organization`. No changes. |
| `create_engine()` / `create_session_factory()` | `ai_benchmark/models/base.py:13-33` | Coordinator calls at `setup()`. No changes. |
| `_item_in_date_range()` | `ai_benchmark/scheduling/scheduler.py:34-39` | Coordinator reuses for backfill date filtering. Import from scheduler module. |

### 1.2 New Dependencies to Add

| Package | Purpose | Version Constraint |
|---|---|---|
| (none) | All functionality uses stdlib (`asyncio.Queue`, `dataclasses`, `uuid`) and existing project dependencies | N/A |

## 2. Package Layout

New package `ai_benchmark/coordination/` and test package `tests/test_coordination/`:

```
ai_benchmark/
  coordination/
    __init__.py             # Exports CollectionCoordinator
    types.py                # FetchTask and CoordFetchResult dataclasses
    coordinator.py          # CollectionCoordinator class
    worker.py               # worker_loop() and fetch_and_extract()

tests/
  test_coordination/
    __init__.py
    test_types.py           # FetchTask/CoordFetchResult construction
    test_worker.py          # fetch_and_extract() with mocked Fetcher/collectors
    test_coordinator.py     # Queue mechanics, result processing, retry, health
```

Modified files:

| File | Change |
|------|--------|
| `ai_benchmark/cli.py` | `collect` command uses coordinator; `run` delegates via PipelineScheduler |
| `ai_benchmark/scheduling/scheduler.py` | `PipelineScheduler` holds long-lived coordinator, delegates `collect_source()` |

File count: 4 new source files, 4 new test files (including `__init__.py`), 2 modified source files.

## 3. Data Model

No new database tables. No schema migrations. The existing `Page.consecutive_failures` column (`models/sources.py:43`) is activated for persistent health tracking.

### 3.1 FetchTask

Location: `ai_benchmark/coordination/types.py`

```python
@dataclass(frozen=True, slots=True)
class FetchTask:
    task_id: str                    # uuid4 hex string
    organization: str               # source org name (key into COLLECTOR_CLASSES)
    page_url: str                   # canonical URL to fetch
    page_type: str                  # from PageConfig.page_type
    page_id: int | None             # DB page ID (None if page not yet in DB)
    source_id: int                  # DB source ID
    classification: str             # primary / secondary / discovery-only
    collector_class_name: str       # organization name (key for get_collector)
    css_selectors: dict[str, str]   # from PageConfig.css_selectors
    since_date: date | None         # backfill date (None for normal polling)
    priority: bool                  # from PageConfig.priority
    attempt: int = 0                # retry counter (coordinator increments)
```

`frozen=True` because tasks are immutable. Retry creates a new task with `attempt + 1`.

### 3.2 CoordFetchResult

Location: `ai_benchmark/coordination/types.py`

Named `CoordFetchResult` to avoid collision with `ai_benchmark.collection.fetcher.FetchResult`.

```python
@dataclass(slots=True)
class CoordFetchResult:
    task_id: str                    # matches originating FetchTask.task_id
    organization: str
    page_url: str
    page_type: str
    page_id: int | None
    source_id: int
    classification: str
    items: list[RawItem]            # extracted items (may be empty)
    html_content: str               # raw HTML for snapshot (empty for API collectors)
    fetch_status: int               # HTTP status code (0 if no HTTP fetch)
    fetch_error: str | None         # error message if failed
    elapsed_ms: float               # fetch duration
    fetched_at: datetime            # UTC timestamp
    css_selectors: dict[str, str]   # carried from task for coordinator's snapshot call
    has_custom_collect: bool        # True if collector used API override path
    since_date: date | None         # carried from task for backfill logic
    priority: bool                  # carried from task
    attempt: int                    # carried from task
```

When `fetch_error is not None`, the result represents a failed fetch. When `has_custom_collect is True`, the coordinator skips snapshot comparison (API collectors don't produce diffable HTML).

## 4. Coordinator Component

Location: `ai_benchmark/coordination/coordinator.py`

### 4.1 Class Interface

```python
class CollectionCoordinator:
    def __init__(self, settings: PipelineSettings) -> None: ...
    async def setup(self) -> None: ...
    async def collect_all(
        self,
        organizations: list[str] | None = None,
        since_date: date | None = None,
    ) -> dict[str, int]: ...
    async def shutdown(self) -> None: ...
```

### 4.2 Internal State

| Attribute | Type | Source |
|---|---|---|
| `_settings` | `PipelineSettings` | Constructor |
| `_engine` | `AsyncEngine` | `setup()` via `create_engine()` |
| `_session_factory` | `async_sessionmaker[AsyncSession]` | `setup()` via `create_session_factory()` |
| `_fetcher` | `Fetcher` | `setup()` with settings params |
| `_task_queue` | `asyncio.Queue[FetchTask \| None]` | `collect_all()`, maxsize = `2 * worker_count` |
| `_result_queue` | `asyncio.Queue[CoordFetchResult]` | `collect_all()`, maxsize = `2 * worker_count` |
| `_worker_count` | `int` | `_settings.max_concurrency` (default 5) |

### 4.3 `setup()` Method

1. Create async engine from `_settings.database_url`.
2. Create session factory from engine.
3. Create `Fetcher` with settings params (user_agent, timeout, max_concurrency, retry_attempts, proxy_url).

### 4.4 `collect_all()` Method

Main entry point. Returns stats dict with `tasks_created`, `tasks_completed`, `tasks_failed`, `items_processed`, `events_created`.

**Step 1 — Create tasks.** Call `_create_tasks(organizations, since_date)`:
- Load catalog via `load_source_catalog()`.
- Filter to requested organizations (or all if `None`).
- Open session; for each source config, query `Source` by organization for `source_id`.
- For each page in config, query `Page` by canonical_url for `page_id`. Create `Page` row if missing.
- Build `FetchTask` per page with `uuid.uuid4().hex` for task_id.
- Commit session (persist any new Page rows).
- Return `list[FetchTask]`.

**Step 2 — Initialize queues.** Create bounded `asyncio.Queue` instances.

**Step 3 — Start workers.** Launch `_worker_count` asyncio tasks running `worker_loop()` from `worker.py`.

**Step 4 — Feed tasks and process results concurrently.** Two concurrent asyncio tasks:
- **Producer**: iterates tasks, `put()` each to task queue. After all tasks enqueued, puts `None` sentinel per worker. Blocks on `put()` when full (backpressure).
- **Consumer**: loops on `_result_queue.get()`. Calls `_process_result()` per result. Tracks pending count (incremented on enqueue, decremented on result). Exits when pending reaches 0.

**Step 5 — Await workers.** `asyncio.gather(*worker_tasks)`.

**Step 6 — Return stats.**

### 4.5 `_process_result()` Method

Opens one session per result. Steps:

1. **Fetch error → retry or log.** If `result.fetch_error` is set:
   - Increment `Page.consecutive_failures` for `result.page_id`.
   - If `result.attempt < _settings.retry_attempts - 1`: create new `FetchTask` with `attempt + 1`, re-enqueue, increment pending count.
   - Log warning. Commit. Return.

2. **Snapshot comparison (standard collectors).** If `not result.has_custom_collect` and `result.page_id` and `result.html_content`:
   - Create `SnapshotManager(session)`.
   - Call `compare_with_latest(page_id, html, content_selectors)` → `(diff, snapshot)`.
   - If `not diff.changed` and no `since_date`: log "no change", commit, return.

3. **Quality filter.** If standard collector and no `since_date`:
   - Call `is_low_value_page(diff, items, page_config)`. If True: log, commit, return.

4. **Date filter (backfill).** If `result.since_date`:
   - Filter items through `_item_in_date_range()`.

5. **Process items.** If items non-empty:
   - Call `process_items(session, items, source_id, page_id, organization, source_type=classification, classification=classification)`.
   - Record event count in stats.

6. **Update health.** Reset `Page.consecutive_failures = 0`. For custom collectors, update `Page.times_polled` and `Page.last_polled_at` (standard collectors get this from SnapshotManager). If items found, set `Page.last_changed_at`.

7. **Commit session.**

### 4.6 Queue Mechanics

| Queue | Maxsize | Producer | Consumer | Sentinel |
|---|---|---|---|---|
| `_task_queue` | `2 * worker_count` | Coordinator (task creator + retry) | Workers | `None` (one per worker) |
| `_result_queue` | `2 * worker_count` | Workers | Coordinator | N/A (pending count tracks completion) |

### 4.7 Retry Mechanism

On `CoordFetchResult` with `fetch_error` and `attempt < retry_attempts - 1`:
1. Create new `FetchTask` with all fields copied, `attempt = attempt + 1`, new `task_id`.
2. Put on `_task_queue`. Increment pending count.
3. Coordinator-level retry handles cases where the Fetcher's own retries are exhausted.

## 5. Worker Component

Location: `ai_benchmark/coordination/worker.py`

### 5.1 Worker Loop

```python
async def worker_loop(
    worker_id: int,
    task_queue: asyncio.Queue[FetchTask | None],
    result_queue: asyncio.Queue[CoordFetchResult],
    fetcher: Fetcher,
    settings: PipelineSettings,
) -> None:
```

Loop: get task → if `None` return → call `fetch_and_extract()` wrapped in try/except → put result → repeat. Unhandled exceptions produce a `CoordFetchResult` with `fetch_error` rather than killing the worker.

### 5.2 `fetch_and_extract()`

```python
async def fetch_and_extract(
    task: FetchTask,
    fetcher: Fetcher,
    settings: PipelineSettings,
) -> CoordFetchResult:
```

**Step 1 — Instantiate collector.** Build minimal `SourceConfig` from task fields, call `get_collector(source_config, github_token=settings.github_token, semantic_scholar_api_key=settings.semantic_scholar_api_key)`.

**Step 2 — Detect API collector.** Check for `_API_PAGE_TYPES` class attribute on collector:

```python
api_types = getattr(collector, "_API_PAGE_TYPES", set())
is_api_page = any(t in task.page_type for t in api_types)
```

This requires adding a one-line class attribute to 4 collectors:

| Collector | File | Attribute |
|---|---|---|
| `GitHubDiscoveryCollector` | `sources/community/github_discovery.py` | `_API_PAGE_TYPES: ClassVar[set[str]] = {"github"}` |
| `MetaCollector` | `sources/meta.py` | `_API_PAGE_TYPES: ClassVar[set[str]] = {"github"}` |
| `SemanticScholarCollector` | `sources/research/semantic_scholar.py` | `_API_PAGE_TYPES: ClassVar[set[str]] = {"api"}` |
| `HFForumsCollector` | `sources/community/hf_forums.py` | `_API_PAGE_TYPES: ClassVar[set[str]] = {"discourse json"}` |

**Step 3a — API path** (if `is_api_page`): Call `collector.collect_page(page, fetcher, snapshot_mgr=None, page_id=task.page_id or 0, since_date=task.since_date)`. These code paths never touch `snapshot_mgr`. Return result with `has_custom_collect=True`, `html_content=""`.

**Step 3b — Standard HTML path** (if not API):
1. `fetch_result = await fetcher.fetch(task.page_url)`
2. If `not fetch_result.ok`: return result with `fetch_error`.
3. `items = collector.extract_items(fetch_result.body_text, page)`
4. Return result with `items`, `html_content=fetch_result.body_text`, `has_custom_collect=False`.

**Step 3c — RSS backfill.** If `since_date` is set and `"rss" in task.page_type` and `"news.google.com/rss" in task.page_url`: call `collector.collect_rss_backfill(page, fetcher, since_date)` for backfill items, also fetch normal URL. Combine item lists.

### 5.3 Worker Constraints

Workers do NOT: hold database sessions, call SnapshotManager, call process_items(), write persistent state, or perform quality filtering.

## 6. CLI Integration

### 6.1 `collect` Command (`cli.py:71-105`)

Replace `PipelineScheduler.collect_source()` with coordinator:

```python
async def _collect() -> None:
    coordinator = CollectionCoordinator(settings)
    await coordinator.setup()
    stats = await coordinator.collect_all(
        organizations=[source] if source else None,
        since_date=since_date,
    )
    await coordinator.shutdown()
    click.echo(f"Collection complete. {stats['tasks_completed']} tasks, "
               f"{stats['events_created']} events.")
```

### 6.2 `run` Command (`cli.py:237-270`)

Interim integration: `PipelineScheduler` holds a long-lived coordinator initialized in `setup()`:

```python
# In PipelineScheduler:
async def setup(self) -> None:
    self._coordinator = CollectionCoordinator(self._settings)
    await self._coordinator.setup()

async def collect_source(self, organization, since_date=None) -> None:
    await self._coordinator.collect_all(
        organizations=[organization], since_date=since_date
    )
```

APScheduler and signal handling unchanged. Full scheduler replacement is a later phase.

### 6.3 No New CLI Commands

The coordinator is an internal detail. Users interact through existing `collect` and `run` commands.

## 7. Verification Criteria

### 7.1 Unit Tests

| Test | File | Verifies |
|---|---|---|
| `FetchTask` construction and frozen immutability | `test_types.py` | Dataclass fields, `frozen=True` prevents mutation |
| `CoordFetchResult` construction | `test_types.py` | All fields populate correctly, error variants |
| `fetch_and_extract` standard HTML path | `test_worker.py` | Mocked fetch returns HTML → worker calls `extract_items()` → items in result |
| `fetch_and_extract` API collector path | `test_worker.py` | Mock collector with `_API_PAGE_TYPES` → calls `collect_page()` → `has_custom_collect=True` |
| `fetch_and_extract` fetch failure | `test_worker.py` | `Fetcher.fetch()` returns `ok=False` → result has `fetch_error`, `items=[]` |
| `fetch_and_extract` RSS backfill | `test_worker.py` | `since_date` + RSS page → calls `collect_rss_backfill()` + normal fetch |
| `_process_result` success path | `test_coordinator.py` | Calls `compare_with_latest()` then `process_items()`, resets `Page.consecutive_failures` |
| `_process_result` failure + retry | `test_coordinator.py` | `fetch_error` + `attempt < limit` → re-enqueues with `attempt+1`, increments failures |
| `_process_result` skip unchanged | `test_coordinator.py` | `DiffResult(changed=False)` + no since_date → skips `process_items()` |
| `_process_result` custom collector | `test_coordinator.py` | `has_custom_collect=True` → skips `compare_with_latest()` |
| Queue backpressure | `test_coordinator.py` | `maxsize=2` queue → `put()` blocks when full |

### 7.2 Integration Tests

| Test | Verifies |
|---|---|
| `collect_all(["OpenAI"])` against test DB | End-to-end: tasks created, workers fetch (mocked HTTP), events in DB |
| `collect_all(None)` with 3+ sources | Multiple sources without `OperationalError: database is locked` |
| Concurrent `collect_all()` calls | Two calls via `asyncio.gather()` → no DB lock errors |

### 7.3 Regression Criteria

| Criterion | Method |
|---|---|
| Same items extracted | `fetch_and_extract()` vs `collect_page()` on same HTML fixtures → identical RawItem lists |
| Same events produced | Coordinator collection vs baseline → same event counts, titles, model slugs |
| No SQLite lock errors | All 22 sources via `collect_all(None)` 5x → zero OperationalError |
| Health state persists | Mock 500 → `Page.consecutive_failures` incremented. Success → reset to 0 |
| Backfill works | `collect_all(["OpenAI"], since_date=...)` → items date-filtered, RSS backfill generated |

### 7.4 Performance Criteria

| Metric | Expectation |
|---|---|
| Wall-clock time (all sources) | Equal or faster than current (pages fetch concurrently within source) |
| Peak memory | No more than 2x baseline (bounded by queue maxsize) |
| Worker idle time | Less than 20% of total run time |
