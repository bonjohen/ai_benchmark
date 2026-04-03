# ETL-Only Branch — Implementation Plan

**Source document:** Codebase exploration of `C:\Projects\ai_benchmark`
**Branch:** `feature/data-pipeline-only`
**Date:** 2026-04-01

## Context

The `ai_benchmark` codebase has 4 subsystems: core ETL pipeline, eval, analysis, and publication. This plan creates a branch containing **only** the ETL pipeline (collection, processing, storage, scheduling, reporting). The ETL pipeline already has **zero imports** from eval/analysis/publication — coupling is limited to CLI registration, shared test fixtures, migration chain, and pyproject.toml dependencies.

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

## Phase 1: Delete Non-ETL Source Directories

**Goal:** Remove eval, analysis, and publication packages from the source tree.
**Depends on:** Nothing (first phase).

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 1.1 | Open | | | Delete `ai_benchmark/eval/` directory |
| 1.2 | Open | | | Delete `ai_benchmark/analysis/` directory |
| 1.3 | Open | | | Delete `ai_benchmark/publication/` directory |
| 1.4 | Open | | | Stage all Phase 1 changes |
| 1.5 | Open | | | Commit all Phase 1 changes |

### Phase 1 Summary

- **Changes:** TBD
- **Commit:** `Remove eval, analysis, and publication packages`

## Phase 2: Strip CLI and Fix Imports

**Goal:** CLI loads without import errors, exposes only ETL commands.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 2.1 | Open | | | Remove eval/analysis/publication group imports and `cli.add_command()` calls from `ai_benchmark/cli.py` (lines 327-340) |
| 2.2 | Open | | | Fix `alembic/env.py` line 16: remove eval model imports, add discovery import |
| 2.3 | Open | | | Stage all Phase 2 changes |
| 2.4 | Open | | | Commit all Phase 2 changes |

### Phase 2 Summary

- **Changes:** TBD
- **Commit:** `Strip non-ETL CLI registrations and alembic imports`

## Phase 3: Fix Migration Chain

**Goal:** Alembic migration chain is valid with only ETL-relevant migrations.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 3.1 | Open | | | Delete `alembic/versions/002_evaluation_pipeline.py` |
| 3.2 | Open | | | Delete `alembic/versions/009_publication_pipeline.py` |
| 3.3 | Open | | | Delete `alembic/versions/010_model_entities.py` |
| 3.4 | Open | | | Fix chain: change `down_revision = "002"` → `"001"` in `alembic/versions/003_gap_schema_extensions.py` |
| 3.5 | Open | | | Rewrite `alembic/versions/008_analysis_pipeline.py`: keep 7 index-creation statements on core ETL tables, remove `analysis_snapshots` and `analysis_insights` table creation, update docstring |
| 3.6 | Open | | | Stage all Phase 3 changes |
| 3.7 | Open | | | Commit all Phase 3 changes |

**Final chain:** `001 → 003 → 004 → 005 → 006 → 007 → 008`

### Phase 3 Summary

- **Changes:** TBD
- **Commit:** `Remove non-ETL migrations, fix revision chain`

## Phase 4: Trim pyproject.toml

**Goal:** Dependencies reflect ETL-only requirements. Lint/test config cleaned.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 4.1 | Open | | | Remove `fastapi`, `uvicorn`, `python-multipart`, `jinja2` from `[project.dependencies]` |
| 4.2 | Open | | | Remove `[tool.ruff.lint.per-file-ignores]` section (all 3 paths are eval-only) |
| 4.3 | Open | | | Remove `"ignore::DeprecationWarning:starlette.templating"` from `[tool.pytest.ini_options].filterwarnings` |
| 4.4 | Open | | | Stage all Phase 4 changes |
| 4.5 | Open | | | Commit all Phase 4 changes |

### Phase 4 Summary

- **Changes:** TBD
- **Commit:** `Trim dependencies and lint config to ETL-only`

## Phase 5: Delete Non-ETL Tests and Fix Fixtures

**Goal:** All remaining tests pass without eval/analysis/publication imports.
**Depends on:** Phases 1-4.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 5.1 | Open | | | Delete `tests/test_eval/` and `tests/test_analysis/` directories |
| 5.2 | Open | | | Delete `tests/test_publication_*.py` (9 files), `tests/test_model_registry.py`, `tests/test_code_review_phase1.py` |
| 5.3 | Open | | | Edit `tests/conftest.py`: remove `db_engine_fk` fixture entirely; in `db_engine`, keep only `from ai_benchmark.models import discovery, events, research, sources` |
| 5.4 | Open | | | Edit `tests/test_config.py`: remove `EvalSettings` import and `test_eval_settings_loads_env_file` test |
| 5.5 | Open | | | Edit `tests/test_migrations.py`: remove eval model imports from inline env.py template, remove `EVAL_TABLES` constant and assertions |
| 5.6 | Open | | | Stage all Phase 5 changes |
| 5.7 | Open | | | Commit all Phase 5 changes |

### Phase 5 Summary

- **Changes:** TBD
- **Commit:** `Remove non-ETL tests, fix shared fixtures`

## Phase 6: Update Installer, Bin Scripts, and Env Templates

**Goal:** Installer deploys ETL-only instance without eval server references.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 6.1 | Open | | | Delete `scripts/bin/serve.bat` and `scripts/serve_both.bat` |
| 6.2 | Open | | | Edit `scripts/installer/Install-Instance.ps1`: remove `serve.bat` from `$binSpecs` array |
| 6.3 | Open | | | Edit `scripts/installer/Update-Instance.ps1`: remove `serve.bat` from `$binSpecs` array |
| 6.4 | Open | | | Edit `scripts/env.template`: remove entire `# ── Eval Pipeline ──` section (12 `AI_BENCH_EVAL_*` vars), remove `EvalSettings` references from header comments |
| 6.5 | Open | | | Edit `scripts/env.dev.template`: remove `# ── Eval Pipeline ──` section |
| 6.6 | Open | | | Stage all Phase 6 changes |
| 6.7 | Open | | | Commit all Phase 6 changes |

### Phase 6 Summary

- **Changes:** TBD
- **Commit:** `Strip eval server from installer and env templates`

## Phase 7: Update CLAUDE.md

**Goal:** Documentation reflects ETL-only scope.
**Depends on:** All prior phases.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 7.1 | Open | | | Remove eval CLI commands, analysis CLI commands, publication CLI commands from Build and Test section |
| 7.2 | Open | | | Remove eval Architecture, Analysis Architecture, Eval Key Patterns, Analysis Key Patterns sections |
| 7.3 | Open | | | Update Deployment section: remove `serve.bat`, `-Port`, `eval serve`, `serve-compare`, `EvalSettings` refs |
| 7.4 | Open | | | Update Source catalog counts, Database Models section, Architecture tree |
| 7.5 | Open | | | Update Configuration section: remove `EvalSettings` references |
| 7.6 | Open | | | Stage all Phase 7 changes |
| 7.7 | Open | | | Commit all Phase 7 changes |

### Phase 7 Summary

- **Changes:** TBD
- **Commit:** `Update CLAUDE.md for ETL-only scope`

## Phase 8: Verification

**Goal:** Branch is green — installs, lints, and tests cleanly.
**Depends on:** All prior phases.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 8.1 | Open | | | `pip install -e ".[dev]"` — confirm clean install |
| 8.2 | Open | | | `ai-benchmark check-config` — confirm CLI works |
| 8.3 | Open | | | `ruff check ai_benchmark/ tests/` — lint clean |
| 8.4 | Open | | | `ruff format --check ai_benchmark/ tests/` — format clean |
| 8.5 | Open | | | `pytest` — all remaining tests pass |
| 8.6 | Open | | | Stage all Phase 8 changes (if any fixes needed) |
| 8.7 | Open | | | Commit all Phase 8 changes (if any fixes needed) |

### Phase 8 Summary

- **Changes:** TBD
- **Commit:** `Fix verification issues` (if needed)

## Key Files

| Purpose | File |
|---------|------|
| CLI entry point | `ai_benchmark/cli.py` |
| Package deps | `pyproject.toml` |
| Migration env | `alembic/env.py` |
| Migration chain break | `alembic/versions/003_gap_schema_extensions.py` |
| Migration rewrite | `alembic/versions/008_analysis_pipeline.py` |
| Test fixtures | `tests/conftest.py` |
| Config tests | `tests/test_config.py` |
| Migration tests | `tests/test_migrations.py` |
| Install script | `scripts/installer/Install-Instance.ps1` |
| Upgrade script | `scripts/installer/Update-Instance.ps1` |
| Prod env template | `scripts/env.template` |
| Dev env template | `scripts/env.dev.template` |
