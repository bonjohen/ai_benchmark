# Phased Release Document

Status lifecycle for every task: Open → Started → Completed. Use Blocked when work cannot continue. Started and Completed must be recorded as PST datetimes.

**Tooling**: Ruff (configured in `pyproject.toml` — line-length 100, target py312, rules E/F/I/N/W/UP/B/SIM/TCH).
**Baseline**: 384 lint violations + 98 files needing format normalization across `ai_benchmark/` and `tests/`.

## Phase 1 — Safe Auto-Fixes (ruff check --fix)

Applies all safe auto-fixable violations. Run `ruff check ai_benchmark/ tests/ --fix` then verify tests pass.

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                          |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
|   1 | Open   |               |                 | Fix 64 I001 (unsorted imports) violations across all source and test files via `ruff check --fix --select I001`.                                     |
|   2 | Open   |               |                 | Fix 44 F401 (unused imports) violations: remove `sys` from `cli.py`, `AsyncSession` from `eval/api/app.py`, `Query` from evaluations route, `json`/`time` from executor, `field` from adapter base, `asyncio` from scheduler, `datetime`/`timezone` from `sources/base.py` and `reporting/export.py`, and 25 unused imports across test files. |
|   3 | Open   |               |                 | Fix 38 UP017 (datetime-timezone-utc) violations: replace `datetime.timezone.utc` with `datetime.UTC` in `collection/fetcher.py`, `collection/snapshot.py` (4 sites), `sources/persistence.py`, `processing/` modules, and 19 test files.                          |
|   4 | Open   |               |                 | Fix 12 UP037 (quoted-annotation) violations: remove unnecessary string quoting from type annotations in `eval/api/schemas/`, `eval/models/`, and `eval/services/`. |
|   5 | Open   |               |                 | Fix 2 SIM117 (multiple-with-statements) violations: merge nested `with` blocks in `collection/api_client.py:47` and `eval/scoring/scorer_runner.py:40`. |
|   6 | Open   |               |                 | Fix 1 F541 (f-string-missing-placeholders) violation in `tests/test_sources/test_community.py:49` — convert to plain string or add interpolation.    |
|   7 | Open   |               |                 | Run full test suite (`pytest`) to confirm no regressions from auto-fixes.                                                                            |
|   8 | Open   |               |                 | Stage all Phase 1 changes.                                                                                                                           |
|   9 | Open   |               |                 | Commit all Phase 1 changes with a phase-complete commit message.                                                                                     |
|  10 | Open   |               |                 | Immediately begin Phase 2.                                                                                                                           |

## Phase 2 — Code Formatting (ruff format)

Applies canonical ruff formatting to all 98 files that deviate from the configured style.

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                          |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
|  11 | Open   |               |                 | Run `ruff format ai_benchmark/ tests/` to normalize formatting across all 98 non-compliant files.                                                    |
|  12 | Open   |               |                 | Verify no semantic changes were introduced — confirm `git diff` is whitespace/formatting only.                                                       |
|  13 | Open   |               |                 | Run full test suite (`pytest`) to confirm no regressions from formatting.                                                                            |
|  14 | Open   |               |                 | Stage all Phase 2 changes.                                                                                                                           |
|  15 | Open   |               |                 | Commit all Phase 2 changes with a phase-complete commit message.                                                                                     |
|  16 | Open   |               |                 | Immediately begin Phase 3.                                                                                                                           |

## Phase 3 — Line Length Violations (E501)

Manually rewrap 60 lines exceeding 100-character limit across 30 files. All require human judgment on break points.

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                          |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
|  17 | Open   |               |                 | Fix 2 E501 violations in `ai_benchmark/cli.py` (lines 66, 160).                                                                                     |
|  18 | Open   |               |                 | Fix 2 E501 violations in `ai_benchmark/collection/differ.py` (lines 142–143).                                                                       |
|  19 | Open   |               |                 | Fix 4 E501 violations in `ai_benchmark/eval/cli/commands.py` (lines 63, 174, 444, 450).                                                             |
|  20 | Open   |               |                 | Fix 2 E501 violations in `ai_benchmark/eval/execution/adapters/local_adapter.py` (line 46) and `openai_adapter.py` (lines 47, 53).                   |
|  21 | Open   |               |                 | Fix 6 E501 violations in `ai_benchmark/eval/models/` — `dataset.py:7`, `evaluation.py:26`, `machine.py:29,46`, `run.py:71`, `scorer.py:38`, `target.py:32`. |
|  22 | Open   |               |                 | Fix 3 E501 violations in `ai_benchmark/eval/scoring/builtin/model_judge.py` (lines 14, 18, 95) and 1 in `rubric.py:78`.                              |
|  23 | Open   |               |                 | Fix 4 E501 violations in `ai_benchmark/eval/scoring/scorer_runner.py` (lines 135, 136, 138, 139).                                                   |
|  24 | Open   |               |                 | Fix 2 E501 violations in `ai_benchmark/eval/services/` — `machine_service.py:110`, `report_service.py:25,146`.                                      |
|  25 | Open   |               |                 | Fix 1 E501 violation in `ai_benchmark/models/events.py:63`.                                                                                         |
|  26 | Open   |               |                 | Fix 2 E501 violations in `ai_benchmark/processing/normalizer.py` (lines 36, 102) and 1 each in `pipeline.py:112`, `quality_filter.py:50`.            |
|  27 | Open   |               |                 | Fix 4 E501 violations in `ai_benchmark/sources/` — `benchmarks/__init__.py:43`, `benchmarks/gaia.py:28`, `community/github_discovery.py:101`, `research/arxiv.py:36`, `research/semantic_scholar.py:83`. |
|  28 | Open   |               |                 | Fix 13 E501 violations across test files: `test_config.py:36`, `test_cross_reference.py:119-120`, `test_comparison_service.py:109-111`, `test_eval_models.py:148`, `test_integration.py:68-72,422`, `test_pipeline.py:158-160`, `test_benchmarks.py:91`, `test_news.py:28,33`, `test_triage.py:92,157`. |
|  29 | Open   |               |                 | Run full test suite to confirm no regressions.                                                                                                       |
|  30 | Open   |               |                 | Stage all Phase 3 changes.                                                                                                                           |
|  31 | Open   |               |                 | Commit all Phase 3 changes with a phase-complete commit message.                                                                                     |
|  32 | Open   |               |                 | Immediately begin Phase 4.                                                                                                                           |

## Phase 4 — Typing-Only Imports (TC001/TC002/TC003)

Move 95 imports used only in type annotations into `TYPE_CHECKING` blocks. These are unsafe auto-fixes (`--unsafe-fixes`) and require test verification after each batch.

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                          |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
|  33 | Open   |               |                 | Fix 41 TC001 violations: move first-party imports (`PageConfig`, `SourceConfig`, `RawItem`, `SourceCollector`, `DiffResult`, `FetchResult`, `Fetcher`, `SnapshotManager`, `TestCase`) into `TYPE_CHECKING` blocks across `sources/`, `eval/execution/`, `sources/persistence.py`, `sources/registry.py`, `sources/base.py`. |
|  34 | Open   |               |                 | Fix 37 TC002 violations: move `sqlalchemy.ext.asyncio.AsyncSession` into `TYPE_CHECKING` blocks across `collection/snapshot.py`, all 9 `eval/api/routes/` modules, `eval/execution/executor.py`, `eval/execution/orchestrator.py`, `eval/scoring/scorer_runner.py`, all 8 `eval/services/` modules, `eval/ui/server.py`, `sources/persistence.py`, and 7 test files. |
|  35 | Open   |               |                 | Fix 17 TC003 violations: move `datetime.datetime` into `TYPE_CHECKING` blocks across `eval/api/schemas/` (6 files), `eval/models/` (7 files), `models/discovery.py`, `models/events.py`, `models/research.py`, `models/sources.py`.                                   |
|  36 | Open   |               |                 | Run full test suite to confirm no regressions — `TYPE_CHECKING` blocks affect runtime imports when classes are used in non-annotation contexts (e.g., `isinstance` checks, SQLAlchemy column types). Revert individual fixes that cause failures.                       |
|  37 | Open   |               |                 | Stage all Phase 4 changes.                                                                                                                           |
|  38 | Open   |               |                 | Commit all Phase 4 changes with a phase-complete commit message.                                                                                     |
|  39 | Open   |               |                 | Immediately begin Phase 5.                                                                                                                           |

## Phase 5 — FastAPI Depends Pattern (B008)

Suppress 58 B008 violations. FastAPI's `Depends()` in function parameter defaults is the canonical pattern per FastAPI documentation. These are not real bugs.

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                          |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
|  40 | Open   |               |                 | Add `"B008"` to the `[tool.ruff.lint.per-file-ignores]` section in `pyproject.toml` for `ai_benchmark/eval/api/routes/*.py` — this is the idiomatic FastAPI pattern and should not trigger warnings. |
|  41 | Open   |               |                 | Verify `ruff check --select B008` reports zero violations after the per-file-ignore is applied.                                                      |
|  42 | Open   |               |                 | Stage all Phase 5 changes.                                                                                                                           |
|  43 | Open   |               |                 | Commit all Phase 5 changes with a phase-complete commit message.                                                                                     |
|  44 | Open   |               |                 | Immediately begin Phase 6.                                                                                                                           |

## Phase 6 — Manual Code Quality Fixes (SIM/F/B)

Fix 11 remaining violations that require manual code changes and judgment.

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                          |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
|  45 | Open   |               |                 | Fix 1 F821 (undefined name) in `ai_benchmark/models/events.py:74` — reference to `Snapshot` that does not exist in scope. Add the correct import or fix the forward reference. |
|  46 | Open   |               |                 | Fix 2 F841 (unused variable) violations: `ai_benchmark/eval/cli/commands.py:99` (variable `ev`) and `tests/test_path_prober.py:72` (variable `domains`). Remove or use the assigned variables. |
|  47 | Open   |               |                 | Fix 1 B904 (raise-without-from) violation in `ai_benchmark/eval/cli/commands.py:115` — add `from` clause to re-raised exception to preserve traceback chain. |
|  48 | Open   |               |                 | Fix 4 SIM108 (if-else-block-instead-of-ternary) violations in `cli.py:187`, `sources/hf_leaderboard_docs.py:27`, `sources/openai.py:86`, `eval/cli/commands.py:159`. Evaluate each case: convert to ternary only when readability is preserved; add `# noqa: SIM108` if the multi-line form is clearer. |
|  49 | Open   |               |                 | Fix 2 SIM105 (suppressible-exception) violations in `cli.py:227` and `eval/cli/commands.py:225` — replace `try/except/pass` with `contextlib.suppress()`. |
|  50 | Open   |               |                 | Run full test suite to confirm no regressions.                                                                                                       |
|  51 | Open   |               |                 | Stage all Phase 6 changes.                                                                                                                           |
|  52 | Open   |               |                 | Commit all Phase 6 changes with a phase-complete commit message.                                                                                     |
|  53 | Open   |               |                 | Immediately begin Phase 7.                                                                                                                           |

## Phase 7 — CI Enforcement and Configuration

Lock in compliance so violations cannot regress.

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                          |
| --: | ------ | ------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
|  54 | Open   |               |                 | Verify `ruff check ai_benchmark/ tests/` exits with zero violations after all phases.                                                                |
|  55 | Open   |               |                 | Verify `ruff format --check ai_benchmark/ tests/` exits with zero files needing reformatting.                                                        |
|  56 | Open   |               |                 | Add a `[tool.ruff.lint.per-file-ignores]` entry for `tests/**/*.py` to allow `F401` for test fixtures that import symbols for side effects, if any remain after Phase 1. |
|  57 | Open   |               |                 | Confirm `pyproject.toml` ruff configuration is complete: `line-length = 100`, `target-version = "py312"`, all desired rule selectors active.         |
|  58 | Open   |               |                 | Run full test suite one final time to confirm clean state.                                                                                           |
|  59 | Open   |               |                 | Stage all Phase 7 changes.                                                                                                                           |
|  60 | Open   |               |                 | Commit all Phase 7 changes with a phase-complete commit message.                                                                                     |

## Violation Summary

| Rule  | Category                           | Count | Fix Method        | Phase |
| ----- | ---------------------------------- | ----: | ----------------- | ----: |
| I001  | Unsorted imports                   |    64 | `--fix`           |     1 |
| E501  | Line too long (>100)               |    60 | Manual rewrap     |     3 |
| B008  | `Depends()` in default arg         |    58 | Per-file ignore   |     5 |
| F401  | Unused import                      |    44 | `--fix`           |     1 |
| TC001 | Typing-only first-party import     |    41 | `--unsafe-fixes`  |     4 |
| UP017 | `datetime.timezone.utc` → `.UTC`   |    38 | `--fix`           |     1 |
| TC002 | Typing-only third-party import     |    37 | `--unsafe-fixes`  |     4 |
| TC003 | Typing-only stdlib import          |    17 | `--unsafe-fixes`  |     4 |
| UP037 | Quoted annotation                  |    12 | `--fix`           |     1 |
| SIM108| If-else instead of ternary         |     4 | Manual / noqa     |     6 |
| F841  | Unused variable                    |     2 | Manual            |     6 |
| SIM105| Suppressible exception             |     2 | Manual            |     6 |
| SIM117| Nested with statements             |     2 | `--fix`           |     1 |
| B904  | Raise without from                 |     1 | Manual            |     6 |
| F541  | f-string no placeholders           |     1 | `--fix`           |     1 |
| F821  | Undefined name                     |     1 | Manual (bug fix)  |     6 |
| —     | ruff format deviations             |    98 | `ruff format`     |     2 |
| **Total** |                              | **384 + 98 format** |               |       |

## Operating Rules for Execution

| No. | Status | Started (PST) | Completed (PST) | Description                                                                                                                                       |
| --: | ------ | ------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
|  61 | Open   |               |                 | At the end of every phase, run `ruff check` and `ruff format --check` to confirm the targeted violations are resolved.                            |
|  62 | Open   |               |                 | At the end of every phase, run the full test suite to confirm no regressions.                                                                     |
|  63 | Open   |               |                 | At the end of every phase, stage all changes created during that phase.                                                                           |
|  64 | Open   |               |                 | At the end of every phase, create a commit with a clear phase-complete commit message.                                                            |
|  65 | Open   |               |                 | After committing a phase, immediately begin the next phase unless a task is explicitly marked Blocked.                                            |
|  66 | Open   |               |                 | If a task becomes Blocked, record the blocking reason in the task description before continuing with unblocked work.                              |
