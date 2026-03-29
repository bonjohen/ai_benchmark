# General Code Review Findings

## 1. Executive Summary

The ai_benchmark codebase is a well-structured Python 3.12 project implementing two major subsystems: (1) an AI model and benchmark intelligence pipeline that monitors 22 sources for model releases, pricing changes, and benchmark results, and (2) a model evaluation pipeline with an API, CLI, and web UI for running evaluations against multiple LLM targets.

The codebase is largely well-designed, with clean layering, consistent patterns, and comprehensive test coverage (340 tests passing). Ruff linting is fully clean. However, the review identified several issues that would prevent reliable production operation:

**Trust-critical issues:**
- The scheduler's `collect_source()` method passes a session factory where a session is expected, and hardcodes `page_id=0` -- this means the collection daemon cannot actually run.
- The UI server has multiple runtime-crashing bugs: accessing `i.input_text` instead of `i.input_sent`, calling `await report_service.list_presets(session)` on a sync function that takes no arguments.
- Parallel execution in the orchestrator has a race condition on `run.completed_items` / `run.failed_items` counters (unsynchronized `+=` from concurrent tasks sharing the same ORM object).

**Security issues:**
- No authentication or authorization on any API endpoint or UI route.
- No CORS configuration, no CSP headers, no CSRF protection.
- The `export_html()` function injects user-controlled data into HTML without escaping (stored XSS).
- API keys are stored in `runtime_options` JSON in the database as plaintext and returned in API responses.

**Operational gaps:**
- No CI/CD pipeline, no Dockerfile, no deployment configuration.
- No initial Alembic migration for core tables (sources, events, research, discovery).
- 2 known failing CLI tests (`test_query_command_no_results`, `test_export_json_no_results`).
- 10 adapter stubs raise `NotImplementedError` (ollama, vllm, llamacpp, lmstudio, mlx, sglang, tensorrt, openvino).

**Overall assessment:** The codebase demonstrates strong domain modeling and thoughtful architecture, but has correctness bugs in critical paths (scheduler, UI, parallel execution) that would cause runtime failures. It is not production-ready without addressing at least Phase 1 and Phase 2 items below.

## 2. Review Scope and Method

- **Review mode:** Mode A -- Whole Codebase Review
- **What was inspected:** All 188 source files across ai_benchmark/ and tests/, including config, models (core + eval), collection pipeline, 22 source collectors, processing pipeline (normalizer, deduplicator, verification, cross-reference, triage, quality filter, discovery queue), scheduling, reporting, eval subsystem (API routes, schemas, services, execution orchestrator/executor, 14 model adapters, 7 scorers, scorer runner), UI templates (16 HTML), static assets, CLI commands, Alembic migrations (5), test files (41), pyproject.toml, alembic.ini.
- **What was executed:** `pytest` (340 passed, 2 failed, 1843 warnings), `ruff check` (all clean), `ruff format --check` (177 files clean).
- **What could not be verified:** Runtime behavior of the scheduler (requires real HTTP sources), actual model adapter execution (requires API keys/running services), Alembic migration application against a real database, deployment behavior.
- **Limits on confidence:** No integration tests run collection end-to-end with real URLs. The eval execution path is tested via API but not with real LLM calls. The UI templates were inspected for XSS but not rendered and tested in a browser.

## 3. Project Shape as Observed

### System Description
Two interconnected subsystems sharing a SQLAlchemy Base and database:

1. **Intelligence Pipeline** (`ai_benchmark/`): Monitors 22 AI company/benchmark/research/news sources via HTTP polling, compares HTML snapshots, extracts structured event records, deduplicates across a 3-layer strategy, creates claims with confidence tiers, builds cross-references, and routes research papers through a triage pipeline. Scheduled via APScheduler with circuit breaker health tracking.

2. **Evaluation Pipeline** (`ai_benchmark/eval/`): Manages datasets, scorers, evaluation definitions, target configurations, machine profiles, and runs. Orchestrates LLM inference via model adapters (OpenAI, Anthropic, local, generic HTTP, plus 10 stubs), scores outputs against 7 built-in scorers, computes aggregates, and provides comparison/report capabilities. Exposed via FastAPI REST API (44 endpoints), Jinja2 UI (16 templates), and Click CLI (8 subcommands).

### Major Parts
- **Config layer** (`config/`): Pydantic settings with `AI_BENCH_` env prefix, TOML source catalog (22 sources, ~70 pages), TOML schedule definitions.
- **Model layer** (`models/`): 9 core models across 4 modules (sources, events, research, discovery) + 15 eval models across 10 modules.
- **Collection layer** (`collection/`): Fetcher (httpx, retry/backoff), HTML differ, snapshot manager, API client base.
- **Source layer** (`sources/`): 22 registered collectors with HTML extraction, organized by category.
- **Processing layer** (`processing/`): Full pipeline orchestration with 7 processing stages.
- **Scheduling layer** (`scheduling/`): APScheduler async integration with health tracking.
- **Reporting layer** (`reporting/`): Query functions, JSON/CSV export.
- **Eval layer** (`eval/`): Full evaluation pipeline stack.

### Runtime Workflow
1. **Collection**: Scheduler triggers `collect_source()` -> Fetcher gets HTML -> SnapshotManager compares/stores -> Collector extracts items -> Pipeline processes items.
2. **Eval**: API/CLI creates run -> Orchestrator validates + creates -> Executor sends prompts to adapter -> ScorerRunner scores results -> Aggregates computed -> Run finalized.

### Weak/Unclear Design Areas
- The boundary between `PipelineSettings` and `EvalSettings` is inconsistent: the eval API app uses `getattr(settings, "database_url", ...)` as a workaround for `EvalSettings` not having `database_url`.
- The scheduler passes incorrect types to `SnapshotManager`, indicating the collection daemon path has never been integration-tested.
- Global mutable state: `_session_factory` in `app.py`, `_presets` dict in `report_service.py`, adapter/scorer registries.
- JSON fields stored as Text columns (inference_params, scorer_config, tags, runtime_options) without DB-level validation.

## 4. Phased Remediation Plan

### Phase 1: Foundation and Trust

**Timeline: Immediate (blocks production use)**

1. **Fix scheduler `collect_source()` method** (Critical, Blocking)
   - Pass an actual `AsyncSession` to `SnapshotManager`, not the session factory.
   - Resolve hardcoded `page_id=0` to actual page IDs from the database.
   - Add integration test for `collect_source` with mocked HTTP.

2. **Fix UI server runtime crashes** (Critical, Blocking)
   - Change `i.input_text` to `i.input_sent` on line 312 of `server.py`.
   - Fix `await report_service.list_presets(session)` -- make `list_presets` async or remove `await` and `session` arg.
   - Add basic smoke test for each UI route with test data.

3. **Fix parallel execution race condition** (High, Blocking)
   - Replace unsynchronized `run.completed_items += 1` / `run.failed_items += 1` with atomic database updates or an `asyncio.Lock`.

4. **Add authentication to API and UI** (High, Blocking for any deployment)
   - At minimum, add API key or Bearer token authentication middleware.
   - Protect UI routes behind the same auth.

5. **Fix `export_html()` XSS vulnerability** (High, Blocking)
   - HTML-escape all user-controlled data (`group_name`, `model_name`, `title`) using `html.escape()`.

6. **Remove API keys from API responses** (High, Blocking)
   - Strip `runtime_options.api_key` from target configuration API responses and comparison diffs.

### Phase 2: Correctness and Maintainability

**Timeline: Before first release**

1. **Fix 2 failing CLI tests** (Medium)
   - `test_query_command_no_results` and `test_export_json_no_results` are documented as known failures. Investigate and fix the assertion mismatches.

2. **Unify settings model** (Medium)
   - Either add `database_url` to `EvalSettings` or have the eval app always receive `PipelineSettings`. The `getattr(..., "database_url", default)` pattern is fragile.

3. **Fix `ScorerRunner._scorer_accum` pattern** (Medium)
   - Use a local variable instead of instance-level mutable state. The `hasattr`/`del` pattern is fragile and not thread-safe.

4. **Add CORS middleware** (Medium)
   - Configure `CORSMiddleware` with appropriate origins. Currently no CORS headers are set, blocking any cross-origin frontend.

5. **Add error handling to UI comparison page** (Medium)
   - The `int(r.strip())` parsing of the `runs` query parameter at line 386 of `server.py` will 500 on invalid input. Wrap in try/except.

6. **Eliminate httpx client-per-request in Fetcher** (Medium)
   - Share a single `httpx.AsyncClient` across requests (create on init or first use, close on shutdown) instead of creating one per retry attempt.

7. **Create initial Alembic migration for core tables** (Medium)
   - The migration chain starts at 002 (eval tables) with `down_revision = None`. Core tables (sources, events, research, discovery) have no migration -- they rely on `Base.metadata.create_all`. Add migration 001.

8. **Add missing `dataset_version_id` parameter to batch creation** (Low)
   - The `create_batch` in the runs route looks up `dataset_version_id` from the evaluation version, but `run_service.create_batch` receives `total_items=0` (not computed), so batch runs all start with `total_items=0`.

### Phase 3: Test and Release Confidence

**Timeline: Before production deployment**

1. **Add integration test for the collection daemon path** -- the scheduler -> collector -> snapshot -> pipeline chain has never been tested together. Mock HTTP responses and verify end-to-end event creation.

2. **Add UI route smoke tests** -- every UI endpoint should be hit at least once with valid test data. The `input_text` / `input_sent` bug demonstrates that UI code paths are untested.

3. **Add security-focused tests** -- test that auth rejects unauthenticated requests (once auth is added), test that HTML export escapes special characters, test that API keys are not leaked in responses.

4. **Add adapter integration tests** -- at minimum, test the OpenAI and Anthropic adapters against mock HTTP servers that return realistic responses.

5. **Add migration verification test** -- run `alembic upgrade head` against a clean database in CI and verify the schema matches the ORM models.

6. **Set up CI/CD pipeline** -- create GitHub Actions (or equivalent) config to run `pytest`, `ruff check`, `ruff format --check`, and `mypy` on every push/PR.

7. **Add end-to-end eval execution test** -- test the full create -> execute -> score -> finalize path using a mock adapter, not just the API create + verify.

### Phase 4: Operations and Reviewer Polish

**Timeline: Post-launch improvements**

1. **Add health check endpoint** -- `/healthz` or `/api/health` returning service status, database connectivity, and scheduler state.

2. **Add CSP headers** -- `Content-Security-Policy` header on the FastAPI app to prevent XSS attacks from inline scripts.

3. **Add request rate limiting** -- protect API endpoints against abuse.

4. **Add structured access logging** -- log all API requests with method, path, status code, latency, and user identity.

5. **Improve percentile calculation** -- current p50/p95/p99 use simple index-based selection (`latencies[int(len * 0.95)]`). For small sample sizes, use proper interpolation or note the limitation.

6. **Add UI accessibility improvements** -- `<table>` elements lack `<caption>`, forms lack `<label>` associations, no skip-to-content link, color-only status indicators (PASS=green, FAIL=red) need text alternatives.

7. **Add N+1 query mitigation** -- the reports dashboard fetches metrics per-run in a loop (`for r in runs: metrics = await run_service.get_metrics(session, r.id)`). Use eager loading or a single query with JOIN.

8. **Clean up 1843 pytest warnings** -- mostly `pytest-asyncio` deprecation warnings that should be resolved by pinning/updating the library.

## 5. Detailed Findings

### F-01: Scheduler passes session factory to SnapshotManager (expects session)
- **Area:** Scheduling / Collection
- **Severity:** Critical
- **Blocking:** Yes
- **Evidence:** `scheduler.py:102` -- `snapshot_mgr = SnapshotManager(self._session_factory)`. `SnapshotManager.__init__` expects `session: AsyncSession`.
- **Why it matters:** The collection daemon (`ai-benchmark run`) cannot execute any collection cycle. All calls to `snapshot_mgr.session.execute(...)` would raise `AttributeError` because a session factory is not a session.
- **Recommended change:** Open a session from the factory for each collection cycle and pass it to SnapshotManager.
- **Recommended validation:** Add integration test that calls `collect_source()` with mocked HTTP.

### F-02: Scheduler hardcodes `page_id=0`
- **Area:** Scheduling / Collection
- **Severity:** Critical
- **Blocking:** Yes
- **Evidence:** `scheduler.py:108` -- `page, self._fetcher, snapshot_mgr, page_id=0`.
- **Why it matters:** `page_id=0` does not correspond to a real page in the database. SnapshotManager's `store_snapshot` and `compare_with_latest` use this ID to query/create snapshots. With FK constraints, this would fail. Without FK constraints, snapshots are orphaned and page metadata (times_polled, last_changed_at) is never updated.
- **Recommended change:** Look up or create Page records from the database before collection, pass actual page IDs.
- **Recommended validation:** Verify end-to-end that page metadata is updated after collection.

### F-03: UI server accesses `i.input_text` but model has `input_sent`
- **Area:** Eval UI
- **Severity:** Critical
- **Blocking:** Yes
- **Evidence:** `server.py:312` -- `"input_text": (i.input_text or "")[:200]`. `RunItemResult` model has `input_sent`, not `input_text`.
- **Why it matters:** The run detail page would raise `AttributeError` whenever a run has item results, making it unusable.
- **Recommended change:** Change `i.input_text` to `i.input_sent`.
- **Recommended validation:** Add UI smoke test that renders run detail with item results.

### F-04: UI calls sync `list_presets()` with `await` and wrong args
- **Area:** Eval UI
- **Severity:** Critical
- **Blocking:** Yes
- **Evidence:** `server.py:438` -- `presets = await report_service.list_presets(session)`. But `list_presets()` is defined as `def list_presets() -> list[dict]` (sync, no parameters).
- **Why it matters:** This raises `TypeError: list_presets() takes 0 positional arguments but 1 was given` when visiting the reports page. Even if the arg were removed, `await` on a non-coroutine returns a `TypeError`.
- **Recommended change:** Either make `list_presets` async and accept session, or call it without await and without session.
- **Recommended validation:** Add smoke test for `/eval/reports`.

### F-05: Race condition in parallel execution counter updates
- **Area:** Eval Execution
- **Severity:** High
- **Blocking:** Yes
- **Evidence:** `orchestrator.py:148-167` -- `_execute_parallel` uses `asyncio.gather` with tasks that mutate `run.failed_items += 1` and `run.completed_items += 1` concurrently on the same ORM object.
- **Why it matters:** With `asyncio.Semaphore` allowing multiple concurrent tasks, the `+=` operations are not atomic. While Python's GIL prevents actual data corruption in CPython, the ORM object's state could become stale relative to the database, and the final flush may overwrite intermediate values. This leads to incorrect completion counts.
- **Recommended change:** Use an `asyncio.Lock` around counter updates, or accumulate results and update once after `gather`, or use atomic SQL updates.
- **Recommended validation:** Test parallel execution with 10+ items and verify final counts match expectations.

### F-06: No authentication on API or UI
- **Area:** Security
- **Severity:** High
- **Blocking:** Yes (for any non-localhost deployment)
- **Evidence:** No auth middleware, no login routes, no API key validation in any route. All 44 API endpoints and 16 UI routes are publicly accessible.
- **Why it matters:** Anyone with network access can create/delete datasets, trigger evaluation runs, view API keys stored in target configs, and manipulate results.
- **Recommended change:** Add API key or Bearer token middleware for API routes. For the UI, add session-based authentication or proxy behind an authenticating reverse proxy.
- **Recommended validation:** Verify unauthenticated requests return 401.

### F-07: XSS in `export_html()` function
- **Area:** Security
- **Severity:** High
- **Blocking:** Yes
- **Evidence:** `report_service.py:146` -- `f"<h3>{group_name}</h3>"` injects `group_name` (user-controlled from target/eval names) directly into HTML without escaping.
- **Why it matters:** An attacker could store a malicious evaluation name like `<script>alert(1)</script>` and trigger XSS when anyone exports the HTML report.
- **Recommended change:** Use `html.escape()` on all interpolated values, or use Jinja2 templates for HTML export.
- **Recommended validation:** Create an evaluation with `<script>` in the name, export HTML, verify the tag is escaped.

### F-08: API keys stored and returned as plaintext in runtime_options
- **Area:** Security
- **Severity:** High
- **Blocking:** Non-blocking (depends on threat model)
- **Evidence:** `orchestrator.py:101` -- `api_key=runtime_options.pop("api_key", None)`. Target configs store `runtime_options` as JSON Text, and the API/UI returns it unredacted via `_target_to_dict()`.
- **Why it matters:** API keys for OpenAI, Anthropic, etc. are stored in the database and exposed in every GET response for target configurations. If the database is compromised or the API is accessed by unauthorized users, all provider API keys are leaked.
- **Recommended change:** Either (a) store API keys in environment variables referenced by name, not in the database, or (b) encrypt them at rest, or at minimum (c) redact `api_key` from all API responses.
- **Recommended validation:** GET a target config and verify no `api_key` appears in the response.

### F-09: No CORS configuration
- **Area:** Security
- **Severity:** Medium
- **Blocking:** Non-blocking
- **Evidence:** No import or usage of `CORSMiddleware` anywhere in the codebase. No CORS-related headers configured.
- **Why it matters:** Cross-origin requests from any frontend application would be blocked by browsers. While this accidentally provides some protection, it means the API cannot be used from any external frontend without a proxy.
- **Recommended change:** Add `CORSMiddleware` with explicit allowed origins.
- **Recommended validation:** Verify OPTIONS preflight requests return correct headers.

### F-10: No CI/CD pipeline
- **Area:** Build / Release
- **Severity:** Medium
- **Blocking:** Non-blocking (but should block before first release)
- **Evidence:** No `.github/workflows/`, no `Dockerfile`, no `docker-compose.yml`, no CI configuration files of any kind.
- **Why it matters:** Code quality checks (pytest, ruff, mypy) depend on manual execution. There is no automated gate preventing regressions from being merged.
- **Recommended change:** Add GitHub Actions workflow running `pytest`, `ruff check`, `ruff format --check`, and optionally `mypy`.
- **Recommended validation:** Push a branch with a failing test and verify CI blocks merge.

### F-11: Missing initial Alembic migration for core tables
- **Area:** Data / Schema
- **Severity:** Medium
- **Blocking:** Non-blocking
- **Evidence:** Migration chain starts at `002` (eval tables) with `down_revision = None`. Core tables (sources, pages, snapshots, event_records, claim_records, cross_references, candidate_papers, enriched_papers, follow_up_tasks) have no migration. The CLI `init-db` command uses `Base.metadata.create_all`.
- **Why it matters:** There is no way to incrementally migrate the core table schema. Adding columns or indexes to core tables requires manual SQL or a new migration that doesn't chain properly from the eval migration 002.
- **Recommended change:** Add migration 001 for core tables, update 002's `down_revision` to `"001"`.
- **Recommended validation:** Run `alembic upgrade head` on a clean database, verify all tables exist.

### F-12: httpx client created per request in Fetcher
- **Area:** Performance
- **Severity:** Medium
- **Blocking:** Non-blocking
- **Evidence:** `fetcher.py:72` -- `async with httpx.AsyncClient(**self._client_kwargs) as client:` inside the retry loop, creating a new connection per attempt.
- **Why it matters:** Each request creates a new TCP/TLS connection. For a pipeline monitoring 22 sources with multiple pages each, this adds substantial overhead and prevents HTTP/2 connection reuse.
- **Recommended change:** Create the client once (in `__init__` or `__aenter__`) and reuse across requests. Add explicit `aclose()` lifecycle management.
- **Recommended validation:** Monitor connection count during a batch collection cycle.

### F-13: Two known failing CLI tests
- **Area:** Tests
- **Severity:** Medium
- **Blocking:** Non-blocking
- **Evidence:** `test_cli.py::test_query_command_no_results` and `test_cli.py::test_export_json_no_results` -- both fail with assertion errors. CLAUDE.md documents these as "2 known failures".
- **Why it matters:** Known test failures erode confidence in the test suite and can mask new regressions. If "2 known failures" becomes normal, developers stop investigating when the count increases.
- **Recommended change:** Fix or properly skip these tests with `@pytest.mark.skip(reason="...")`.
- **Recommended validation:** `pytest` exits with 0 failures.

### F-14: Ten adapter stubs raise NotImplementedError
- **Area:** Eval Execution
- **Severity:** Medium
- **Blocking:** Non-blocking (adapters are registered but not yet usable)
- **Evidence:** `ollama_adapter.py`, `vllm_adapter.py`, `llamacpp_adapter.py`, `lmstudio_adapter.py`, `mlx_adapter.py`, `sglang_adapter.py`, `tensorrt_adapter.py`, `openvino_adapter.py` all register with the adapter registry but raise `NotImplementedError`.
- **Why it matters:** Creating a target config with `provider="ollama"` and running it would crash with an unhelpful error. The adapter registry accepts these providers, creating a false promise.
- **Recommended change:** Either (a) don't register stubs until they're implemented, or (b) return a clear error at registration time or config validation, not at execution time.
- **Recommended validation:** Test that creating a run with an unimplemented provider gives a clear error at run creation time, not mid-execution.

### F-15: Unvalidated query parameter parsing in UI comparison page
- **Area:** Eval UI
- **Severity:** Low
- **Blocking:** Non-blocking
- **Evidence:** `server.py:386` -- `run_ids = [int(r.strip()) for r in runs.split(",") if r.strip()]`. If `runs=abc`, this raises `ValueError` -> 500 Internal Server Error.
- **Why it matters:** User-facing 500 errors are unprofessional and leak implementation details.
- **Recommended change:** Wrap in try/except, return a user-friendly error or redirect.
- **Recommended validation:** Visit `/eval/comparisons?runs=abc` and verify a clean error page.

### F-16: `_scorer_accum` uses fragile instance-level mutable state
- **Area:** Eval Scoring
- **Severity:** Low
- **Blocking:** Non-blocking
- **Evidence:** `scorer_runner.py:182-190` -- uses `hasattr(self, "_scorer_accum")` to conditionally create and later `del` an instance attribute.
- **Why it matters:** If `compute_aggregates` throws an exception between accumulation and deletion, the attribute leaks to the next call on the same `ScorerRunner` instance. This is a maintenance hazard.
- **Recommended change:** Use a local variable `scorer_accum: dict[str, list[bool]] = {}` instead of instance state.
- **Recommended validation:** Existing tests should continue to pass.

### F-17: Duplicated `_run_to_dict` / `_metric_to_dict` helper functions
- **Area:** Implementation Quality
- **Severity:** Low
- **Blocking:** Non-blocking
- **Evidence:** `_run_to_dict` is defined separately in `routes/runs.py` and `ui/server.py` with different field sets. `_target_to_dict` similarly duplicated.
- **Why it matters:** Changes to the Run model must be reflected in multiple places. The two versions can silently diverge (and already have -- the UI version omits `scoring_started_at`, `updated_at`, etc.).
- **Recommended change:** Create shared serialization helpers or use Pydantic response models consistently.
- **Recommended validation:** N/A -- this is a refactoring improvement.

### F-18: No database connection pooling configuration
- **Area:** Operations / Performance
- **Severity:** Low
- **Blocking:** Non-blocking
- **Evidence:** `create_engine(database_url, echo=False)` uses default pool settings. For SQLite this is appropriate, but if the database URL is changed to PostgreSQL, the default pool may be insufficient.
- **Why it matters:** Switching to a production database without adjusting pool settings could lead to connection exhaustion.
- **Recommended change:** Expose pool_size and max_overflow as config settings.
- **Recommended validation:** Not critical while using SQLite.

### F-19: JSON fields lack schema validation
- **Area:** Data Integrity
- **Severity:** Low
- **Blocking:** Non-blocking
- **Evidence:** Multiple Text columns store JSON (inference_params, scorer_config, runtime_options, tags, etc.) but neither the database nor the ORM validates the JSON structure. Pydantic schemas validate on API input but not on direct service calls.
- **Why it matters:** Malformed JSON stored in these columns would cause `json.JSONDecodeError` at read time, propagating as 500 errors.
- **Recommended change:** Validate JSON at the service layer before storing. Consider using SQLAlchemy's `JSON` column type if migrating to PostgreSQL.
- **Recommended validation:** Test that storing invalid JSON in service functions raises a clear error.

### F-20: No CSP or X-Frame-Options headers on the UI
- **Area:** Security
- **Severity:** Nit
- **Blocking:** Non-blocking
- **Evidence:** No security headers are set on the FastAPI application. The base HTML template does not include any meta CSP tags.
- **Why it matters:** The UI could be embedded in an iframe (clickjacking) and inline scripts could be injected.
- **Recommended change:** Add `X-Frame-Options: DENY` and `Content-Security-Policy` headers via middleware.
- **Recommended validation:** Check response headers include security headers.

## 6. Missing Things That Should Exist

1. **Migration 001 for core tables** -- sources, pages, snapshots, event_records, claim_records, cross_references, candidate_papers, enriched_papers, follow_up_tasks.
2. **CI/CD configuration** -- automated testing, linting, and format checking on every commit.
3. **Authentication middleware** -- API key or Bearer token for API, session auth for UI.
4. **Integration test for the collection daemon** -- the primary runtime path has zero test coverage.
5. **UI route smoke tests** -- none of the 16 UI endpoints have test coverage.
6. **Health check endpoint** -- for load balancers and monitoring.
7. **Deployment configuration** -- Dockerfile, docker-compose, or equivalent.
8. **API key management strategy** -- environment variable references instead of plaintext in database.
9. **Database backup/restore documentation** -- no guidance on data management.
10. **Error handling middleware** -- global exception handler that returns structured error responses instead of raw stack traces.

## 7. Highest-Risk Areas

1. **`scheduling/scheduler.py:collect_source()`** -- The primary runtime loop for the intelligence pipeline is broken. It passes wrong types and hardcodes IDs. This has never been integration-tested.

2. **`eval/execution/orchestrator.py:_execute_parallel()`** -- Race condition on counter updates. Any parallel eval run will produce incorrect completion statistics.

3. **`eval/ui/server.py`** -- Multiple runtime crashes (`input_text` vs `input_sent`, `list_presets` call). The UI has no test coverage and clearly has never been tested with real data.

4. **`eval/api/routes/`** -- No authentication. Any network-accessible deployment exposes full CRUD on all evaluation data, including stored API keys.

5. **`eval/services/report_service.py:export_html()`** -- Stored XSS via unescaped user data injection into HTML output.

## 8. Approval Recommendation

**Request changes.**

The codebase has strong foundations -- clean architecture, good domain modeling, comprehensive test suite for the parts that are tested, and full linting compliance. However, the identified issues include:

- 4 critical runtime bugs that would crash core functionality (scheduler, UI pages)
- 1 high-severity race condition in parallel execution
- No authentication on any endpoint
- A stored XSS vulnerability
- Zero CI/CD

These issues collectively mean the system cannot reliably operate its primary functions (collection scheduling, UI run inspection, parallel eval execution) and has security gaps that block any non-localhost deployment. The fixes are straightforward and well-scoped, but they must be completed before this codebase can be approved for production use.

## 9. Recommended Next Actions

1. **Immediate (this week):**
   - Fix F-01 and F-02 (scheduler bugs) -- restore the collection daemon to working state.
   - Fix F-03 and F-04 (UI crashes) -- these are one-line fixes.
   - Fix F-05 (race condition) -- replace `+=` with locked or batched updates.
   - Fix F-07 (XSS) -- add `html.escape()` calls.

2. **Before any deployment:**
   - Add authentication (F-06).
   - Redact API keys from responses (F-08).
   - Set up CI/CD (F-10).
   - Fix or skip the 2 failing tests (F-13).

3. **Before first production release:**
   - Add integration test for collection daemon path.
   - Add UI smoke tests.
   - Create migration 001 for core tables (F-11).
   - Add CORS middleware (F-09).
   - Implement at least one of the local adapter stubs (ollama) to validate the adapter pattern end-to-end.

4. **Ongoing:**
   - Implement remaining adapter stubs as needed.
   - Address the performance items (F-12 httpx client reuse, F-17 N+1 queries).
   - Add security headers (F-20).
   - Clean up pytest warnings.
