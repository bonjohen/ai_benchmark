# General Code Review Remediation Plan

Status lifecycle for every task: Open → Started → Completed. Use Blocked when work cannot continue. Started and Completed must be recorded as PST datetimes.

Based on findings in `docs/general_code_review_findings.md` (F-01 through F-20).

## Phase 1 — Foundation and Trust (Blocks Production Use)

| No. | Status | Started (PST) | Completed (PST) | Finding | Description |
| --: | ------ | ------------- | --------------- | ------- | ----------- |
| 1 | Completed | 2026-03-28 11:00 PM | 2026-03-28 11:30 PM | F-01 | Fix scheduler `collect_source()`: pass an actual AsyncSession to SnapshotManager, not the session factory. Open a session from the factory for each collection cycle. |
| 2 | Completed | 2026-03-28 11:00 PM | 2026-03-28 11:30 PM | F-02 | Fix scheduler hardcoded `page_id=0`: look up or create Page records from the database before collection, pass actual page IDs. |
| 3 | Completed | 2026-03-28 11:30 PM | 2026-03-29 12:15 AM | F-01/02 | Add integration test for `collect_source` with mocked HTTP. Verify end-to-end that page metadata is updated after collection. (4 tests in `test_code_review_phase1.py`.) |
| 4 | Completed | 2026-03-29 12:00 AM | 2026-03-29 12:00 AM | F-03 | Fix UI server `i.input_text` → `i.input_sent` in run detail route. (Fixed in Phase 13 of runner plan.) |
| 5 | Completed | 2026-03-29 12:00 AM | 2026-03-29 12:00 AM | F-04 | Fix `await report_service.list_presets(session)` → `report_service.list_presets()` (sync, no args). Fix preset_data dict access. (Fixed in Phase 13 of runner plan.) |
| 6 | Completed | 2026-03-28 11:30 PM | 2026-03-28 11:45 PM | F-05 | Fix parallel execution race condition: added `asyncio.Lock` around counter updates in `_execute_parallel`. |
| 7 | Completed | 2026-03-28 11:45 PM | 2026-03-29 12:15 AM | F-05 | Add test: run parallel execution with 10+ items and verify final completed/failed counts match expectations. (3 tests in `test_code_review_phase1.py`.) |
| 8 | Completed | 2026-03-28 11:45 PM | 2026-03-28 11:50 PM | F-07 | Verified `export_html()` already uses `html.escape()` on all user-controlled data (group_name, model_name, title, status, errors). No changes needed. |
| 9 | Completed | 2026-03-29 12:00 AM | 2026-03-29 12:15 AM | F-07 | Add test: XSS payloads in title, group_name, model_name, status, and error fields all verified escaped. (5 tests in `test_code_review_phase1.py`.) |
| 10 | Completed | 2026-03-28 11:50 PM | 2026-03-29 12:00 AM | F-08 | Redact API keys from API responses: added `_redact_keys()` helper to strip `api_key`, `secret_key`, `token`, `password` from `runtime_options` in `_target_to_dict`. |
| 11 | Completed | 2026-03-29 12:00 AM | 2026-03-29 12:15 AM | F-08 | Add test: GET/list target configs with api_key in runtime_options, verify redacted in response. (5 tests in `test_code_review_phase1.py`.) |
| 12 | Completed | 2026-03-29 12:15 AM | 2026-03-29 12:15 AM | | Stage all Phase 1 changes. |
| 13 | Completed | 2026-03-29 12:15 AM | 2026-03-29 12:15 AM | | Commit all Phase 1 changes. |
| 14 | Completed | 2026-03-29 12:15 AM | 2026-03-29 12:15 AM | | Immediately begin Phase 2. |

## Phase 2 — Correctness and Maintainability (Before First Release)

| No. | Status | Started (PST) | Completed (PST) | Finding | Description |
| --: | ------ | ------------- | --------------- | ------- | ----------- |
| 15 | Completed | 2026-03-29 12:15 AM | 2026-03-29 12:30 AM | F-13 | Fixed 2 failing CLI tests: root cause was stale DB file without `benchmark_variant` column. Added `_use_temp_db` fixture with `monkeypatch.setenv` to use fresh temp DB per test. All 8 CLI tests now pass. |
| 16 | Completed | 2026-03-29 12:30 AM | 2026-03-29 12:45 AM | F-09 | Added CORS middleware: `CORSMiddleware` with `allow_origins=["*"]` configured on FastAPI app in `create_app()`. |
| 17 | Completed | 2026-03-28 11:45 PM | 2026-03-28 11:50 PM | F-15 | Fixed comparison page query param parsing: wrapped `int(r.strip())` in try/except ValueError. (Done in prior runner plan Phase 13.) |
| 18 | Completed | 2026-03-29 12:30 AM | 2026-03-29 12:45 AM | F-12 | Fixed httpx client-per-request: Fetcher now lazily creates and reuses a single `httpx.AsyncClient`. Added `aclose()` and context manager support. |
| 19 | Completed | 2026-03-29 12:30 AM | 2026-03-29 12:45 AM | F-11 | Created Alembic migration 001 for 8 core tables (sources, pages, snapshots, event_records, claim_records, cross_references, candidate_papers, enriched_papers). Updated 002's down_revision to "001". |
| 20 | Completed | 2026-03-29 12:30 AM | 2026-03-29 12:45 AM | F-16 | Fixed `ScorerRunner._scorer_accum`: replaced instance-level mutable state with local `scorer_accum` variable in `compute_aggregates`. |
| 21 | Completed | 2026-03-29 12:30 AM | 2026-03-29 12:45 AM | F-14 | Improved adapter stubs: all 8 stub adapters now raise `NotImplementedError` with descriptive message naming available alternatives. |
| 22 | Completed | 2026-03-29 12:30 AM | 2026-03-29 12:45 AM | — | Fixed batch creation: `create_batch` endpoint now looks up DatasetVersion item count instead of defaulting to 0. |
| 23 | Completed | 2026-03-29 12:30 AM | 2026-03-29 12:45 AM | — | Unified settings: added `database_url` to `EvalSettings`, removed `getattr(settings, "database_url", ...)` workaround in app.py. |
| 24 | Completed | 2026-03-29 12:45 AM | 2026-03-29 12:45 AM | | Stage all Phase 2 changes. |
| 25 | Completed | 2026-03-29 12:45 AM | 2026-03-29 12:45 AM | | Commit all Phase 2 changes. |
| 26 | Completed | 2026-03-29 12:45 AM | 2026-03-29 12:45 AM | | Immediately begin Phase 3. |

## Phase 3 — Test and Release Confidence (Before Production Deployment)

| No. | Status | Started (PST) | Completed (PST) | Finding | Description |
| --: | ------ | ------------- | --------------- | ------- | ----------- |
| 27 | Completed | 2026-03-29 12:45 AM | 2026-03-29 1:00 AM | — | Added integration test for collection daemon path. 5 tests in `test_collection_integration.py`: full path with items, no-changes, source-not-found, page-error-continues, snapshot-creation. |
| 28 | Completed | 2026-03-28 11:59 PM | 2026-03-29 12:00 AM | — | Add UI route smoke tests for all endpoints. (16 regression tests added in Phase 14 of runner plan covering all UI routes.) |
| 29 | Completed | 2026-03-29 12:45 AM | 2026-03-29 1:00 AM | — | Added security tests: 7 auth tests in `test_auth.py` (no-auth, missing-creds, bearer, x-api-key, wrong-token, healthz, UI protection). XSS tests in Phase 1. API key redaction tests in Phase 1. |
| 30 | Completed | 2026-03-29 12:45 AM | 2026-03-29 1:00 AM | — | Added adapter integration tests: 23 tests in `test_adapter_integration.py` using respx. OpenAI (8), Anthropic (8), GenericHTTP (7) — success, errors, timeouts, auth headers, inference params. |
| 31 | Completed | 2026-03-29 12:45 AM | 2026-03-29 1:00 AM | — | Added migration verification test: 4 tests in `test_migrations.py` — upgrade head, idempotent, version check, column verification. |
| 32 | Completed | 2026-03-29 12:45 AM | 2026-03-29 1:00 AM | F-10 | Created `.github/workflows/ci.yml`: pytest, ruff check, ruff format --check on push/PR to main. |
| 33 | Completed | 2026-03-29 12:45 AM | 2026-03-29 1:00 AM | — | Added end-to-end eval execution test: 5 tests in `test_e2e_eval.py` — lifecycle with/without scorer, status transitions, partial failure, item count verification. |
| 34 | Completed | 2026-03-29 12:45 AM | 2026-03-29 1:00 AM | F-06 | Auth middleware already existed in `api/middleware.py`. Added 7 tests in `test_auth.py`. Bearer token and X-API-Key supported. Disabled when `api_key` is None. |
| 35 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:00 AM | | Stage all Phase 3 changes. |
| 36 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:00 AM | | Commit all Phase 3 changes. |
| 37 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:00 AM | | Immediately begin Phase 4. |

## Phase 4 — Operations and Polish (Post-Launch Improvements)

| No. | Status | Started (PST) | Completed (PST) | Finding | Description |
| --: | ------ | ------------- | --------------- | ------- | ----------- |
| 38 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:15 AM | F-20 | Added `SecurityHeadersMiddleware`: X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Content-Security-Policy, Referrer-Policy. |
| 39 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:15 AM | — | Added `/healthz` endpoint with DB connectivity check (`SELECT 1`). Returns `{"status": "ok", "database": "connected"}`. |
| 40 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:15 AM | — | Added `AccessLoggingMiddleware`: structlog with method, path, status_code, latency_ms. Skips /healthz. |
| 41 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:15 AM | — | Added `RateLimitMiddleware`: 100 req/min per IP (configurable via `rate_limit_per_minute`), 429 on exceed. |
| 42 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:15 AM | F-17 | Created `api/serializers.py` with shared `run_to_dict` and `target_to_dict`. Updated API routes to use shared module. |
| 43 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:15 AM | — | Fixed N+1 in report_service: batch-load all RunAggregateMetric and TargetConfiguration in single queries instead of per-run loops. |
| 44 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:15 AM | F-18 | Added `db_pool_size` and `db_max_overflow` to EvalSettings. Passed to `create_engine()` for non-SQLite databases. |
| 45 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:15 AM | F-19 | Added `_validate_json_field()` in target_service and eval_service. Validates inference_params, runtime_options, tags, scorer_config, preprocessing, pass_criteria. |
| 46 | Completed | 2026-03-29 1:15 AM | 2026-03-29 1:20 AM | — | Added pytest filterwarnings for pytest_asyncio and starlette deprecation warnings. Warnings dropped from 4172 to 13. |
| 47 | Completed | 2026-03-29 1:00 AM | 2026-03-29 1:15 AM | — | Added skip-to-content link, nav aria-label, sr-only labels in base.html. Table captions in list/detail/dashboard templates. Status badges with role="status". |
| 48 | Completed | 2026-03-29 1:20 AM | 2026-03-29 1:20 AM | | Stage all Phase 4 changes. |
| 49 | Completed | 2026-03-29 1:20 AM | 2026-03-29 1:20 AM | | Commit all Phase 4 changes. |

## Operating Rules for Execution

| No. | Status | Started (PST) | Completed (PST) | Description |
| --: | ------ | ------------- | --------------- | ----------- |
| 50 | Completed | 2026-03-29 1:20 AM | 2026-03-29 1:25 AM | At the end of every phase, update readme.md to reflect what was delivered and what remains. |
| 51 | Completed | 2026-03-29 1:20 AM | 2026-03-29 1:25 AM | At the end of every phase, stage all changes created during that phase. |
| 52 | Completed | 2026-03-29 1:20 AM | 2026-03-29 1:25 AM | At the end of every phase, create a commit with a clear phase-complete commit message. |
| 53 | Completed | 2026-03-29 1:20 AM | 2026-03-29 1:25 AM | After committing a phase, immediately begin the next phase unless a task is explicitly marked Blocked. |
