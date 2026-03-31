# Daily AI Benchmark Publication — Implementation Plan

**Source document:** `docs/publication_pdr.md`

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
| ORM tables | SQLAlchemy 2.0 async mapped columns, inheriting from `models/base.py:Base` |
| Migration | Alembic async (`alembic/versions/009_publication_pipeline.py`) |
| Configuration | Pydantic v2 `BaseSettings` with `AI_BENCH_PUB_` env prefix |
| Service layer | Async functions accepting `AsyncSession`, returning dataclasses |
| API | FastAPI router mounted at `/api/publications/` on eval app |
| UI | Jinja2 templates under `publication/ui/templates/`, mounted via `mount_publication_ui()` |
| CLI | Click subgroup `publish` registered on root CLI group |
| Formatters | Dataclass → string converters following `analysis/formatters/` pattern |
| Scheduler | APScheduler cron job in `scheduling/scheduler.py` |

---

## Phase 1: Data Model & Package Foundation

**Goal:** Publication schema exists in the database, configuration is loadable, type definitions are in place, and the package structure is established.
**Depends on:** Nothing (first phase).

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1 | Completed | 2026-03-30 12:00 PM | 2026-03-30 12:01 PM | Create `ai_benchmark/publication/__init__.py` with module docstring and version constant. |
| 1.2 | Completed | 2026-03-30 12:01 PM | 2026-03-30 12:05 PM | Create `ai_benchmark/publication/models.py` — four ORM tables: `PublicationEdition`, `PublicationSection`, `PublicationEntry`, `PublicationAuditLog`. All inherit from `Base` in `models/base.py`. |
| 1.3 | Completed | 2026-03-30 12:01 PM | 2026-03-30 12:03 PM | Create `ai_benchmark/publication/config.py` — `PublicationSettings(BaseSettings)` with `AI_BENCH_PUB_` env prefix. |
| 1.4 | Completed | 2026-03-30 12:01 PM | 2026-03-30 12:03 PM | Create `ai_benchmark/publication/types.py` — dataclasses: `CandidateItem`, `ScoredCandidate`, `EntryResult`, `SectionResult`, `EditionResult`. |
| 1.5 | Completed | 2026-03-30 12:01 PM | 2026-03-30 12:04 PM | Create `alembic/versions/009_publication_pipeline.py` — migration creating four publication tables with indexes. |
| 1.6 | Completed | 2026-03-30 12:05 PM | 2026-03-30 12:08 PM | Create `tests/test_publication_models.py` — 12 tests covering model CRUD, relationships, cascade delete, config defaults/overrides, and dataclass creation. Updated `tests/conftest.py` to register publication models. |
| 1.7 | Completed | 2026-03-30 12:08 PM | 2026-03-30 12:12 PM | All 12 tests pass. Ruff check and format clean. |
| 1.8 | Completed | 2026-03-30 12:12 PM | 2026-03-30 12:13 PM | Stage all Phase 1 changes. |
| 1.9 | Completed | 2026-03-30 12:13 PM | 2026-03-30 12:14 PM | Commit all Phase 1 changes. |

### Phase 1 Summary

- **Changes:** Created `ai_benchmark/publication/` package with `__init__.py`, `models.py` (4 ORM tables), `config.py` (PublicationSettings), `types.py` (5 dataclasses). Added `alembic/versions/009_publication_pipeline.py` migration. Created `tests/test_publication_models.py` (12 tests). Updated `tests/conftest.py` to register publication models in both engine fixtures.
- **Changes hosted at:** TBD
- **Commit:** `Add publication data model, config, types, and migration`

---

## Phase 2: Candidate Assembly & Scoring

**Goal:** The system can load eligible items from the database, apply eligibility rules, score them, and assign them to editorial sections.
**Depends on:** Phase 1.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 2.1 | Completed | 2026-03-30 12:15 PM | 2026-03-30 12:15 PM | Create `ai_benchmark/publication/services/__init__.py`. |
| 2.2 | Completed | 2026-03-30 12:15 PM | 2026-03-30 12:22 PM | Create `ai_benchmark/publication/services/assembly.py` — eligibility filtering, dedup, cross-ref counting, analysis signal loading. |
| 2.3 | Completed | 2026-03-30 12:15 PM | 2026-03-30 12:20 PM | Create `ai_benchmark/publication/services/scoring.py` — 8-factor weighted scoring with deterministic ordering. |
| 2.4 | Completed | 2026-03-30 12:15 PM | 2026-03-30 12:20 PM | Create `ai_benchmark/publication/services/sectioning.py` — type-to-section mapping, overflow to watchlist, top_summary population. |
| 2.5 | Completed | 2026-03-30 12:22 PM | 2026-03-30 12:28 PM | Create `tests/test_publication_assembly.py` — 16 tests covering eligibility, dedup, scoring determinism, sectioning, overflow, cross-refs. |
| 2.6 | Completed | 2026-03-30 12:28 PM | 2026-03-30 12:32 PM | All 16 tests pass. Ruff check and format clean. |
| 2.7 | Completed | 2026-03-30 12:32 PM | 2026-03-30 12:33 PM | Stage all Phase 2 changes. |
| 2.8 | Completed | 2026-03-30 12:33 PM | 2026-03-30 12:33 PM | Commit all Phase 2 changes. |

### Phase 2 Summary

- **Changes:** Created `ai_benchmark/publication/services/` with `assembly.py` (candidate loading, eligibility rules, dedup, cross-ref counting), `scoring.py` (8-factor weighted composite scoring), and `sectioning.py` (type-to-section mapping with overflow). Created `tests/test_publication_assembly.py` (16 tests).
- **Changes hosted at:** TBD
- **Commit:** `Add candidate assembly, scoring, and sectioning services`

---

## Phase 3: Edition Generation Pipeline

**Goal:** A single async function call generates a complete daily edition — assembles candidates, scores, sections, generates text, and persists to the database.
**Depends on:** Phase 2.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Completed | 2026-03-30 12:35 PM | 2026-03-30 12:40 PM | Create `ai_benchmark/publication/services/render.py` — deterministic template-based text generation for edition summary, section summaries, and entry text (title, summary, why_it_matters). |
| 3.2 | Completed | 2026-03-30 12:35 PM | 2026-03-30 12:42 PM | Create `ai_benchmark/publication/services/edition.py` — `generate_edition()` orchestrator with window computation, idempotent regeneration, frozen rejection, and full persistence. |
| 3.3 | Completed | 2026-03-30 12:42 PM | 2026-03-30 12:48 PM | Create `tests/test_publication_edition.py` — 10 tests covering end-to-end generation, persistence, idempotency, frozen rejection, empty day, entry text, and render unit tests. |
| 3.4 | Completed | 2026-03-30 12:48 PM | 2026-03-30 12:52 PM | All 10 tests pass. Ruff check and format clean. |
| 3.5 | Completed | 2026-03-30 12:52 PM | 2026-03-30 12:53 PM | Stage all Phase 3 changes. |
| 3.6 | Completed | 2026-03-30 12:53 PM | 2026-03-30 12:53 PM | Commit all Phase 3 changes. |

### Phase 3 Summary

- **Changes:** Created `render.py` (deterministic text generation for editions, sections, entries) and `edition.py` (orchestrator: window → assemble → score → section → render → persist). Created `tests/test_publication_edition.py` (10 tests).
- **Changes hosted at:** TBD
- **Commit:** `Add edition generation pipeline with text rendering and persistence`

---

## Phase 4: Output Formats & API

**Goal:** Editions are retrievable via REST API and exportable as Markdown and JSON. The publication router is mounted on the eval app.
**Depends on:** Phase 3.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Completed | 2026-03-30 12:55 PM | 2026-03-30 12:55 PM | Create `ai_benchmark/publication/formatters/__init__.py` with exports. |
| 4.2 | Completed | 2026-03-30 12:55 PM | 2026-03-30 12:58 PM | Create `ai_benchmark/publication/formatters/markdown.py` — full edition rendering with verification badges and metadata. |
| 4.3 | Completed | 2026-03-30 12:55 PM | 2026-03-30 12:57 PM | Create `ai_benchmark/publication/formatters/json_export.py` — dataclasses.asdict serialization. |
| 4.4 | Completed | 2026-03-30 12:58 PM | 2026-03-30 01:05 PM | Create `ai_benchmark/publication/api.py` — 6 endpoints: GET /latest, GET /{date}, GET /, POST /generate, GET /{date}/export. |
| 4.5 | Completed | 2026-03-30 01:05 PM | 2026-03-30 01:07 PM | Mount publication router at `/api/publications` and add model imports to lifespan in `eval/api/app.py`. |
| 4.6-7 | Completed | 2026-03-30 01:07 PM | 2026-03-30 01:15 PM | Create `tests/test_publication_api.py` — 13 tests covering all API endpoints, markdown/JSON formatters, and edge cases. |
| 4.8 | Completed | 2026-03-30 01:15 PM | 2026-03-30 01:18 PM | All 51 publication tests pass. Ruff check and format clean. |
| 4.9 | Completed | 2026-03-30 01:18 PM | 2026-03-30 01:19 PM | Stage all Phase 4 changes. |
| 4.10 | Completed | 2026-03-30 01:19 PM | 2026-03-30 01:19 PM | Commit all Phase 4 changes. |

### Phase 4 Summary

- **Changes:** Created `publication/formatters/` with `markdown.py` (edition_to_markdown with verification badges, metadata) and `json_export.py` (dataclass serialization). Created `publication/api.py` (6 REST endpoints). Mounted router and models in `eval/api/app.py`. Created `tests/test_publication_api.py` (13 tests).
- **Changes hosted at:** TBD
- **Commit:** `Add publication formatters, REST API, and mount on eval app`

---

## Phase 5: CLI & Web UI

**Goal:** Editions are viewable in the browser via server-rendered pages and generatable from the command line.
**Depends on:** Phase 4.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1 | Completed | 2026-03-30 01:20 PM | 2026-03-30 01:28 PM | Create `ai_benchmark/publication/cli.py` — 5 Click commands: generate, list, export, status, freeze. |
| 5.2 | Completed | 2026-03-30 01:28 PM | 2026-03-30 01:29 PM | Register `publish` CLI group in `ai_benchmark/cli.py`. |
| 5.3-5.4 | Completed | 2026-03-30 01:29 PM | 2026-03-30 01:35 PM | Create `publication/ui/__init__.py` and `server.py` with mount_publication_ui and 3 routes. |
| 5.5-5.8 | Completed | 2026-03-30 01:29 PM | 2026-03-30 01:35 PM | Create 4 Jinja2 templates: base.html, latest.html, archive.html, detail.html. |
| 5.9-5.10 | Completed | 2026-03-30 01:29 PM | 2026-03-30 01:35 PM | Create publication.css (nav, cards, badges, tables) and publication.js (entry detail toggle). |
| 5.11 | Completed | 2026-03-30 01:35 PM | 2026-03-30 01:36 PM | Mount publication UI in eval app via mount_publication_ui(app). |
| 5.12-5.13 | Completed | 2026-03-30 01:36 PM | 2026-03-30 01:45 PM | Create tests: 6 CLI tests + 6 UI tests = 12 total. |
| 5.14 | Completed | 2026-03-30 01:45 PM | 2026-03-30 01:50 PM | All 12 tests pass. Ruff check and format clean. |
| 5.15 | Completed | 2026-03-30 01:50 PM | 2026-03-30 01:51 PM | Stage all Phase 5 changes. |
| 5.16 | Completed | 2026-03-30 01:51 PM | 2026-03-30 01:51 PM | Commit all Phase 5 changes. |

### Phase 5 Summary

- **Changes:** Created `publication/cli.py` (5 Click commands), `publication/ui/` with `server.py` (3 routes), 4 Jinja2 templates, CSS, and JS. Registered CLI group and UI mount in main app. Created 12 tests.
- **Changes hosted at:** TBD
- **Commit:** `Add publication CLI commands and server-rendered web UI`

---

## Phase 6: Scheduler Integration

**Goal:** Daily editions are generated automatically after collection and analysis jobs complete. Publication health is tracked alongside source health.
**Depends on:** Phase 5.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 6.1 | Completed | 2026-03-30 01:55 PM | 2026-03-30 02:02 PM | Create `ai_benchmark/publication/scheduler.py` — `run_publication_job()` and `add_publication_job()` with APScheduler CronTrigger. Failures caught and logged, never block collection. |
| 6.2 | Completed | 2026-03-30 02:02 PM | 2026-03-30 02:03 PM | Add Publication schedule entry to `config/schedules.toml` with cron `"0 7 * * *"`. |
| 6.3 | Completed | 2026-03-30 01:55 PM | 2026-03-30 02:00 PM | Create `PublicationHealthTracker` in `publication/scheduler.py` — tracks success/failure, consecutive failures, total runs. |
| 6.4 | Completed | 2026-03-30 01:55 PM | 2026-03-30 01:58 PM | Create `publication/services/export.py` — `export_static()` writes date-stamped markdown/JSON files. |
| 6.5 | Completed | 2026-03-30 02:03 PM | 2026-03-30 02:08 PM | Add `check_regeneration_eligible()` to `edition.py` — checks for high-confidence events after generation within freeze window, sets status to "regeneration_available". |
| 6.6 | Completed | 2026-03-30 02:08 PM | 2026-03-30 02:15 PM | Create `tests/test_publication_scheduler.py` — 10 tests covering health tracker, static export, and regeneration eligibility. |
| 6.7 | Completed | 2026-03-30 02:15 PM | 2026-03-30 02:18 PM | All 10 tests pass. Ruff check and format clean. |
| 6.8 | Completed | 2026-03-30 02:18 PM | 2026-03-30 02:19 PM | Stage all Phase 6 changes. |
| 6.9 | Completed | 2026-03-30 02:19 PM | 2026-03-30 02:19 PM | Commit all Phase 6 changes. |

### Phase 6 Summary

- **Changes:** Created `publication/scheduler.py` (PublicationHealthTracker, run_publication_job, add_publication_job), `publication/services/export.py` (static file export), added `check_regeneration_eligible()` to edition.py. Added Publication entry to schedules.toml. Created 10 tests.
- **Changes hosted at:** TBD
- **Commit:** `Add scheduler integration, publication health tracking, and static export`

---

## Phase 7: Editorial Controls & Audit

**Goal:** Operators can pin, suppress, override, freeze, and regenerate editions. All editorial actions are audit-logged. An admin page provides the control surface.
**Depends on:** Phase 6.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 7.1 | Open | | | Create `ai_benchmark/publication/services/editorial.py` — async functions: `pin_entry(session, entry_id, actor)`, `suppress_entry(session, entry_id, actor)`, `override_entry(session, entry_id, *, title, summary, section_key, rank, actor)`, `mark_featured(session, entry_id, actor)`, `freeze_edition(session, edition_id, actor)`, `regenerate_edition(session, edition_id, actor, settings)`, `restore_entry(session, entry_id, actor)` (restores generated text over final text). Each function persists the change and writes a `PublicationAuditLog` record with before/after state. |
| 7.2 | Open | | | Add editorial API endpoints to `ai_benchmark/publication/api.py` — `POST /{date}/freeze`, `POST /{date}/regenerate`, `POST /{date}/entries/{id}/pin`, `POST /{date}/entries/{id}/suppress`, `POST /{date}/entries/{id}/override` (body: title, summary, section, rank). All require actor identification. Return updated entry/edition state. Frozen edition endpoints return 409 Conflict. |
| 7.3 | Open | | | Create `ai_benchmark/publication/ui/templates/admin.html` — editorial control page: edition selector, edition status with freeze/regenerate buttons, entry list with pin/suppress/override controls per entry, audit log timeline showing recent editorial actions. Accessible from publication nav as "Editor". |
| 7.4 | Open | | | Add `GET /publication/admin` route to `ai_benchmark/publication/ui/server.py` — render admin template with current edition data and recent audit log entries. |
| 7.5 | Open | | | Create `tests/test_publication_editorial.py` — test pin/suppress/override/freeze/regenerate/restore: verify DB state changes, audit log records created with correct before/after, frozen edition rejects edits, restore reverts to generated text. |
| 7.6 | Open | | | Run full `pytest` and ruff checks — fix until green. |
| 7.7 | Open | | | Stage all Phase 7 changes. |
| 7.8 | Open | | | Commit all Phase 7 changes. |

### Phase 7 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add editorial controls, audit logging, and admin UI`

---

## Phase 8: Refinement & Polish

**Goal:** Scoring is tuned, section balance is optimized, visual presentation is polished, and edition-to-edition comparison is supported.
**Depends on:** Phase 7.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 8.1 | Open | | | Tune scoring weights in `ai_benchmark/publication/services/scoring.py` — validate weight distribution against representative populated database, adjust thresholds for section-appropriate score ranges, add configurable weight overrides in `PublicationSettings`. |
| 8.2 | Open | | | Add section balance heuristics to `ai_benchmark/publication/services/sectioning.py` — minimum 1 item per non-empty section, diversity constraint (no single org dominates >50% of a section), watchlist promotion when primary sections are thin. |
| 8.3 | Open | | | Add verification state and confidence visual indicators to UI templates — color-coded badges (green=confirmed, yellow=unconfirmed, red=conflicted), confidence tier labels, source count pills. Update `publication/ui/static/css/publication.css`. |
| 8.4 | Open | | | Add entry detail expansion in `publication/ui/templates/detail.html` — expandable panel per entry showing: supporting event details, claim list with source names and confidence tiers, cross-reference links, score breakdown. Add toggle JS to `publication/ui/static/js/publication.js`. |
| 8.5 | Open | | | Add edition comparison support — `async def compare_editions(session, date_a, date_b) -> dict` in `ai_benchmark/publication/services/edition.py`. Identify new entries, removed entries, moved entries (section/rank changes), and score deltas between two editions. Add `GET /api/publications/compare?date_a=X&date_b=Y` endpoint. |
| 8.6 | Open | | | Add UI filters to `publication/ui/templates/detail.html` — filter entries by section, organization, benchmark, and verification state. Client-side filtering via JS in `publication.js`. |
| 8.7 | Open | | | Add HTML export renderer to `ai_benchmark/publication/formatters/html.py` — `edition_to_html(edition: EditionResult) -> str`. Render self-contained HTML document with inline CSS for email/static distribution. Wire into `GET /{date}/export?format=html` endpoint. |
| 8.8 | Open | | | Create `tests/test_publication_refinement.py` — test section balance constraints, comparison output structure, HTML export validity, filter behavior with mixed data. |
| 8.9 | Open | | | Run full `pytest` and ruff checks — fix until green. |
| 8.10 | Open | | | Stage all Phase 8 changes. |
| 8.11 | Open | | | Commit all Phase 8 changes. |

### Phase 8 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Tune scoring, add section balance, edition comparison, filters, and HTML export`
