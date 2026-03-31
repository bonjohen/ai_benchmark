# Collection Coordinator — Implementation Plan

**Source document:** `docs/collection_coordinator_pdr.md`

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
| Task/result passing | `asyncio.Queue` (stdlib) |
| Task identity | `uuid.uuid4().hex` (stdlib) |
| Data carriers | `dataclasses` with `frozen=True` / `slots=True` |
| Concurrency | `asyncio.create_task` worker pool (same process) |
| HTTP concurrency | Existing `Fetcher` with `asyncio.Semaphore(max_concurrency)` |
| Testing | `pytest` + `pytest-asyncio` (existing dev deps) |

## Phase 1: Coordination Package Foundation

**Goal:** The `ai_benchmark/coordination/` package exists with `FetchTask` and `CoordFetchResult` dataclasses fully defined and tested. No behavioral changes.
**Depends on:** Nothing (first phase).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-03-30 08:37 PM | 2026-03-30 08:37 PM | Create `ai_benchmark/coordination/__init__.py` — empty package init. |
| 1.2 | Completed | 2026-03-30 08:37 PM | 2026-03-30 08:39 PM | Create `ai_benchmark/coordination/types.py` — `FetchTask` (`frozen=True`, `slots=True`, 12 fields per PDR §3.1) and `CoordFetchResult` (`slots=True`, 18 fields per PDR §3.2). |
| 1.3 | Completed | 2026-03-30 08:37 PM | 2026-03-30 08:37 PM | Create `tests/test_coordination/__init__.py` — empty test package init. |
| 1.4 | Completed | 2026-03-30 08:39 PM | 2026-03-30 08:41 PM | Create `tests/test_coordination/test_types.py` — tests: `FetchTask` construction with all fields, frozen immutability raises `FrozenInstanceError`, `CoordFetchResult` construction, error variant (`fetch_error` set, `items=[]`), `has_custom_collect` flag variants. |
| 1.5 | Completed | 2026-03-30 08:41 PM | 2026-03-30 08:42 PM | Run `pytest tests/test_coordination/test_types.py -x -v` — 9 passed. Run `ruff check ai_benchmark/coordination/ tests/test_coordination/` and `ruff format --check` — clean. |
| 1.6 | Completed | 2026-03-30 08:43 PM | 2026-03-30 08:43 PM | Stage all Phase 1 changes. |
| 1.7 | Completed | 2026-03-30 08:43 PM | 2026-03-30 08:44 PM | Commit all Phase 1 changes. |

### Phase 1 Summary

- **Changes:** Created `ai_benchmark/coordination/` package with `__init__.py` and `types.py` (FetchTask frozen dataclass, CoordFetchResult dataclass). Created `tests/test_coordination/` with `test_types.py` (9 tests). All pass, lint clean.
- **Changes hosted at:** `ai_benchmark/coordination/types.py`, `tests/test_coordination/test_types.py`
- **Commit:** `Add coordination package with FetchTask and CoordFetchResult dataclasses` (8605f0d)

## Phase 2: Worker Logic

**Goal:** `fetch_and_extract()` and `worker_loop()` exist and are tested with mocked Fetcher/collectors. Four collectors annotated with `_API_PAGE_TYPES`. No coordinator yet — workers are standalone and testable.
**Depends on:** Phase 1 (types).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-03-30 08:48 PM | 2026-03-30 08:48 PM | Add `_API_PAGE_TYPES: ClassVar[set[str]]` to `GitHubDiscoveryCollector` (`sources/community/github_discovery.py`) — `{"github"}`. |
| 2.2 | Completed | 2026-03-30 08:48 PM | 2026-03-30 08:48 PM | Add `_API_PAGE_TYPES: ClassVar[set[str]]` to `MetaCollector` (`sources/meta.py`) — `{"github"}`. |
| 2.3 | Completed | 2026-03-30 08:48 PM | 2026-03-30 08:49 PM | Add `_API_PAGE_TYPES: ClassVar[set[str]]` to `SemanticScholarCollector` (`sources/research/semantic_scholar.py`) — `{"api"}`. |
| 2.4 | Completed | 2026-03-30 08:49 PM | 2026-03-30 08:49 PM | Add `_API_PAGE_TYPES: ClassVar[set[str]]` to `HFForumsCollector` (`sources/community/hf_forums.py`) — `{"discourse json"}`. |
| 2.5 | Completed | 2026-03-30 08:50 PM | 2026-03-30 08:55 PM | Create `ai_benchmark/coordination/worker.py` — implement `fetch_and_extract(task, fetcher, settings) -> CoordFetchResult` with three paths: standard HTML (fetch → `extract_items()`), API collector (`_API_PAGE_TYPES` detection → `collect_page()`), and RSS backfill (`since_date` + RSS page → `collect_rss_backfill()` + normal fetch). Per PDR §5.2. |
| 2.6 | Completed | 2026-03-30 08:50 PM | 2026-03-30 08:55 PM | Implement `worker_loop(worker_id, task_queue, result_queue, fetcher, settings)` in `worker.py` — loop on queue get, `None` sentinel exits, try/except wraps `fetch_and_extract()`, error produces `CoordFetchResult` with `fetch_error`. Per PDR §5.1. |
| 2.7 | Completed | 2026-03-30 08:55 PM | 2026-03-30 08:58 PM | Create `tests/test_coordination/test_worker.py` — 7 tests: standard HTML success, fetch failure, API collector path, RSS backfill, worker_loop exits on sentinel, processes task then exits, exception produces error result. Per PDR §7.1. |
| 2.8 | Completed | 2026-03-30 08:58 PM | 2026-03-30 09:00 PM | Run `pytest tests/test_coordination/ -x -v` — 16 passed. Run `ruff check` and `ruff format --check` on changed files — clean. |
| 2.9 | Open | | | Stage all Phase 2 changes. |
| 2.10 | Open | | | Commit all Phase 2 changes. |

### Phase 2 Summary

- **Changes:** Added `_API_PAGE_TYPES` ClassVar to 4 API collectors (GitHubDiscovery, Meta, SemanticScholar, HFForums). Created `coordination/worker.py` with `fetch_and_extract()` (3 paths: HTML, API, RSS backfill) and `worker_loop()` (queue consumer with error handling). 7 new worker tests. Total coordination tests: 16 passed.
- **Changes hosted at:** `ai_benchmark/coordination/worker.py`, `tests/test_coordination/test_worker.py`, 4 collector files
- **Commit:** `Add fetch_and_extract worker logic and _API_PAGE_TYPES annotations`

## Phase 3: Coordinator Core

**Goal:** `CollectionCoordinator` exists with `setup()`, `collect_all()`, `shutdown()`, queue mechanics, result processing, retry, and persistent health tracking — all tested in isolation with mocked workers and DB.
**Depends on:** Phase 2 (worker logic).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-03-30 09:05 PM | 2026-03-30 09:10 PM | Create `ai_benchmark/coordination/coordinator.py` — `CollectionCoordinator.__init__(settings)` storing `_settings`, `_engine`, `_session_factory`, `_fetcher`, `_worker_count` as `None`/unset. Per PDR §4.1–4.2. |
| 3.2 | Completed | 2026-03-30 09:05 PM | 2026-03-30 09:10 PM | Implement `setup()` — create async engine, session factory, and Fetcher from settings. Per PDR §4.3. |
| 3.3 | Completed | 2026-03-30 09:05 PM | 2026-03-30 09:10 PM | Implement `shutdown()` — close Fetcher, dispose engine. |
| 3.4 | Completed | 2026-03-30 09:05 PM | 2026-03-30 09:10 PM | Implement `_create_tasks(organizations, since_date)` — load catalog, filter orgs, open session, query/create `Source` and `Page` rows, build `FetchTask` per page, commit, return task list. Import `_item_in_date_range` from scheduler module. Per PDR §4.4 Step 1. |
| 3.5 | Completed | 2026-03-30 09:05 PM | 2026-03-30 09:10 PM | Implement `_process_result(result, stats)` — fetch error → retry or log with `Page.consecutive_failures` increment; snapshot comparison via `SnapshotManager` for standard collectors; quality filter; date filter for backfill; `process_items()` call; health state reset; commit. Per PDR §4.5. |
| 3.6 | Completed | 2026-03-30 09:05 PM | 2026-03-30 09:20 PM | Implement `collect_all(organizations, since_date)` — create tasks, init bounded queues (`maxsize=2*worker_count`), launch worker tasks, producer enqueues initial tasks, consumer loop with `_process_result` per result and pending count tracking, sentinels sent after all work (including retries) completes, await workers, return stats dict. Fixed sentinel timing bug: sentinels must be sent after consumer loop, not by producer, to avoid worker exit before retries. Per PDR §4.4 Steps 2–6, §4.6. |
| 3.7 | Completed | 2026-03-30 09:05 PM | 2026-03-30 09:10 PM | Implement retry in `_process_result` — on `fetch_error` with `attempt < retry_attempts - 1`, create new `FetchTask` with `attempt + 1` and new `task_id`, re-enqueue, increment pending count. Per PDR §4.7. |
| 3.8 | Completed | 2026-03-30 09:20 PM | 2026-03-30 09:20 PM | Update `ai_benchmark/coordination/__init__.py` — export `CollectionCoordinator`. |
| 3.9 | Completed | 2026-03-30 09:20 PM | 2026-03-30 09:25 PM | Create `tests/test_coordination/test_coordinator.py` — 10 tests: success path (snapshot + process_items + health reset), custom collector (skips snapshot), failure + retry (increments failures, re-enqueues), no retry on last attempt, unchanged skips processing, date filter on backfill, collect_all end-to-end, empty tasks, retry integration, queue backpressure. Per PDR §7.1. |
| 3.10 | Completed | 2026-03-30 09:25 PM | 2026-03-30 09:30 PM | Run `pytest tests/test_coordination/ -x -v` — 26 passed in 0.34s. Run `ruff check` and `ruff format --check` on changed files — clean. |
| 3.11 | Completed | 2026-03-30 09:30 PM | 2026-03-30 09:30 PM | Stage all Phase 3 changes. |
| 3.12 | Completed | 2026-03-30 09:30 PM | 2026-03-30 09:30 PM | Commit all Phase 3 changes. |

### Phase 3 Summary

- **Changes:** Created `ai_benchmark/coordination/coordinator.py` with full `CollectionCoordinator` class: `setup()`, `shutdown()`, `collect_all()`, `_create_tasks()`, `_process_result()`, `_handle_failure()`, `_update_health()`. Fixed sentinel timing bug in `collect_all()` — sentinels sent after consumer loop completes (including retries), not by producer. Updated `__init__.py` to export `CollectionCoordinator`. Created `test_coordinator.py` with 10 tests covering success, failure+retry, unchanged skip, custom collector, date filter, end-to-end queue mechanics, and backpressure. Total coordination tests: 26 passed.
- **Changes hosted at:** `ai_benchmark/coordination/coordinator.py`, `ai_benchmark/coordination/__init__.py`, `tests/test_coordination/test_coordinator.py`
- **Commit:** `Add CollectionCoordinator with queue mechanics, result processing, and retry`

## Phase 4: CLI Integration

**Goal:** The `collect` command uses `CollectionCoordinator`. `PipelineScheduler.collect_source()` delegates to a long-lived coordinator. All 22 sources can run concurrently without `OperationalError: database is locked`. Full test suite green.
**Depends on:** Phase 3 (coordinator core).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Completed | 2026-03-30 09:35 PM | 2026-03-30 09:40 PM | Modify `ai_benchmark/cli.py` `collect` command — replace `PipelineScheduler.collect_source()` with `CollectionCoordinator.collect_all()`. Instantiate coordinator, `setup()`, call `collect_all(organizations=[source] if source else None, since_date=since_date)`, `shutdown()`, echo stats. Per PDR §6.1. |
| 4.2 | Completed | 2026-03-30 09:40 PM | 2026-03-30 09:45 PM | Modify `ai_benchmark/scheduling/scheduler.py` `PipelineScheduler` — replaced `_fetcher`/`_session_factory` with `_coordinator: CollectionCoordinator`. `setup()` creates and sets up coordinator. `collect_source()` delegates to `_coordinator.collect_all()`. Added `shutdown_coordinator()` async method. `run` command calls `shutdown_coordinator()` on exit. Fixed circular import by making `_item_in_date_range` import lazy in coordinator. Moved `PipelineSettings` to TYPE_CHECKING. Per PDR §6.2. |
| 4.3 | Completed | 2026-03-30 09:45 PM | 2026-03-30 09:55 PM | Rewrote `tests/test_collection_integration.py` — 5 integration tests using coordinator with mocked HTTP: full path (items extracted → events created → page metadata updated), no items, empty catalog, fetch failure (consecutive_failures incremented), snapshot creation. Rewrote `tests/test_code_review_phase1.py` scheduler tests — 4 tests: delegation to coordinator, since_date passthrough, failure recording, circuit breaker. Per PDR §7.2. |
| 4.4 | Completed | 2026-03-30 09:55 PM | 2026-03-30 10:00 PM | Run `pytest -x -q` — 977 passed in 41.50s. Run `ruff check ai_benchmark/ tests/` and `ruff format --check ai_benchmark/ tests/` — clean. |
| 4.5 | Completed | 2026-03-30 10:00 PM | 2026-03-30 10:00 PM | Stage all Phase 4 changes. |
| 4.6 | Completed | 2026-03-30 10:00 PM | 2026-03-30 10:00 PM | Commit all Phase 4 changes. |

### Phase 4 Summary

- **Changes:** Wired `CollectionCoordinator` into CLI `collect` command and `PipelineScheduler`. CLI now instantiates coordinator, calls `collect_all()`, and reports stats. Scheduler delegates `collect_source()` to coordinator. Fixed circular import between coordinator and scheduler (lazy import of `_item_in_date_range`). Fixed sentinel timing bug from Phase 3 caught during integration testing. Rewrote `test_collection_integration.py` (5 tests) and scheduler tests in `test_code_review_phase1.py` (4 tests) for the new architecture. Full suite: 977 passed.
- **Changes hosted at:** `ai_benchmark/cli.py`, `ai_benchmark/scheduling/scheduler.py`, `ai_benchmark/coordination/coordinator.py`, `tests/test_collection_integration.py`, `tests/test_code_review_phase1.py`
- **Commit:** `Wire CollectionCoordinator into collect command and PipelineScheduler`
