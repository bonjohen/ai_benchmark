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
| 1.8 | Open | | | Stage all Phase 1 changes. |
| 1.9 | Open | | | Commit all Phase 1 changes. |

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
| 2.1 | Open | | | Create `ai_benchmark/publication/services/__init__.py`. |
| 2.2 | Open | | | Create `ai_benchmark/publication/services/assembly.py` — `async def assemble_candidates(session, *, window_start, window_end, settings) -> list[CandidateItem]`. Load eligible EventRecords, ClaimRecords, EnrichedPapers, and cached AnalysisInsights within the window. Apply eligibility rules per PDR §9.2: exclude conflicted events unless configured; require benchmark-owner claim for benchmark entries; require promoted status for research entries; require pricing verification path for pricing entries. Collapse duplicate candidate representations per event cluster using existing dedup keys. Attach cross-reference counts, benchmark deltas from `benchmark_trends`, and spotlight/anomaly signals from `AnalysisInsight`. |
| 2.3 | Open | | | Create `ai_benchmark/publication/services/scoring.py` — `async def score_candidates(candidates: list[CandidateItem], settings) -> list[ScoredCandidate]`. Compute composite score from weighted factors: verification_status (0.25), confidence_tier (0.20), source_diversity/source_count (0.15), recency (0.10), cross_ref_density (0.10), novelty (0.10), benchmark_magnitude (0.05), anomaly_signal (0.05). Return deterministic ordering. Persist score_breakdown dict on each ScoredCandidate. Penalize low-signal churn and repeated follow-up noise. |
| 2.4 | Open | | | Create `ai_benchmark/publication/services/sectioning.py` — `async def assign_sections(scored: list[ScoredCandidate], settings) -> dict[str, list[ScoredCandidate]]`. Map entry_type to section_key: benchmark results → "benchmark_movers", model/vendor announcements → "announcements", research → "research_pulse", news/secondary → "industry_news". Items below min_score_threshold or beyond max_items_per_section → "watchlist". Resolve ties by score descending then observed_at ascending. Return dict keyed by section_key. |
| 2.5 | Open | | | Create `tests/test_publication_assembly.py` — tests for: eligibility filtering (conflicted excluded, benchmark-owner required, promoted-only research), duplicate collapse, scoring determinism and weight correctness, section assignment and overflow to watchlist, empty-window graceful handling. |
| 2.6 | Open | | | Run `pytest tests/test_publication_assembly.py` and ruff checks — fix until green. |
| 2.7 | Open | | | Stage all Phase 2 changes. |
| 2.8 | Open | | | Commit all Phase 2 changes. |

### Phase 2 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add candidate assembly, scoring, and sectioning services`

---

## Phase 3: Edition Generation Pipeline

**Goal:** A single async function call generates a complete daily edition — assembles candidates, scores, sections, generates text, and persists to the database.
**Depends on:** Phase 2.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 3.1 | Open | | | Create `ai_benchmark/publication/services/render.py` — `async def render_edition_text(sections: dict[str, list[ScoredCandidate]], session) -> tuple[str, dict[str, str], dict[int, dict]]`. Generate edition summary text (top 3 headlines), per-section summary text, and per-entry text (headline, summary, why_it_matters) from candidate data and supporting claims. Return (edition_summary, section_summaries, entry_texts_by_candidate_index). Use event titles, claim text, benchmark scores, and org names — no LLM calls, deterministic template-based generation. |
| 3.2 | Open | | | Create `ai_benchmark/publication/services/edition.py` — `async def generate_edition(session, *, publication_date, settings) -> EditionResult`. Orchestrate: compute window from cutoff_hour + timezone → assemble_candidates → score_candidates → assign_sections → render_edition_text → persist PublicationEdition, PublicationSections, PublicationEntries to DB. Set edition status to "draft". Return EditionResult. Handle idempotency: if edition for date exists and is not frozen, delete and regenerate; if frozen, raise error. |
| 3.3 | Open | | | Create `tests/test_publication_edition.py` — end-to-end generation tests with seeded EventRecords, ClaimRecords, and EnrichedPapers: verify edition persisted with correct sections and entries, verify idempotent regeneration of draft editions, verify frozen edition rejection, verify empty-day produces edition with zero entries, verify entry text fields populated. |
| 3.4 | Open | | | Run `pytest tests/test_publication_edition.py` and ruff checks — fix until green. |
| 3.5 | Open | | | Stage all Phase 3 changes. |
| 3.6 | Open | | | Commit all Phase 3 changes. |

### Phase 3 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add edition generation pipeline with text rendering and persistence`

---

## Phase 4: Output Formats & API

**Goal:** Editions are retrievable via REST API and exportable as Markdown and JSON. The publication router is mounted on the eval app.
**Depends on:** Phase 3.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 4.1 | Open | | | Create `ai_benchmark/publication/formatters/__init__.py` with exports. |
| 4.2 | Open | | | Create `ai_benchmark/publication/formatters/markdown.py` — `edition_to_markdown(edition: EditionResult) -> str`. Render full edition: title with date, edition summary, then each section with header, section summary, and numbered entries (headline, summary, why_it_matters, verification badge, source count, org/model/benchmark tags). Follow pattern from `analysis/formatters/markdown.py`. |
| 4.3 | Open | | | Create `ai_benchmark/publication/formatters/json_export.py` — `edition_to_json(edition: EditionResult) -> str`. Serialize EditionResult via `dataclasses.asdict()` with JSON encoding of dates. Follow pattern from `analysis/formatters/json_export.py`. |
| 4.4 | Open | | | Create `ai_benchmark/publication/api.py` — FastAPI router with endpoints per PDR §9.8: `GET /latest`, `GET /{date}`, `GET /` (list with pagination), `POST /generate`, `GET /{date}/export?format=markdown|json|html`. Use `Depends(get_session)` from eval app. Load edition from DB, convert to EditionResult, format per request. Return 404 when no edition exists for date. |
| 4.5 | Open | | | Import and mount publication router in `ai_benchmark/eval/api/app.py` at prefix `/api/publications` with tag `"publications"`. Add publication model imports to lifespan handler for table creation. |
| 4.6 | Open | | | Create `tests/test_publication_formatters.py` — test markdown output structure (headers, sections, entries), JSON round-trip (parse output, verify keys), edge cases (empty sections, missing optional fields). |
| 4.7 | Open | | | Create `tests/test_publication_api.py` — test endpoints with `httpx.AsyncClient` + `TestClient`: generate, retrieve latest, retrieve by date, list, export as markdown, export as JSON, 404 for missing date. |
| 4.8 | Open | | | Run full `pytest` and ruff checks — fix until green. |
| 4.9 | Open | | | Stage all Phase 4 changes. |
| 4.10 | Open | | | Commit all Phase 4 changes. |

### Phase 4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add publication formatters, REST API, and mount on eval app`

---

## Phase 5: CLI & Web UI

**Goal:** Editions are viewable in the browser via server-rendered pages and generatable from the command line.
**Depends on:** Phase 4.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 5.1 | Open | | | Create `ai_benchmark/publication/cli.py` — Click subgroup `publish` with commands: `generate` (--date, --force), `list` (--limit, --status), `export` (--date, --format markdown\|json, --output), `status` (--date), `freeze` (--date). Each command creates engine + session, calls service, outputs result. Follow pattern from `analysis/cli.py`. |
| 5.2 | Open | | | Register `publish` CLI group in `ai_benchmark/cli.py` — import and `cli.add_command(publish_group)`. |
| 5.3 | Open | | | Create `ai_benchmark/publication/ui/__init__.py`. |
| 5.4 | Open | | | Create `ai_benchmark/publication/ui/server.py` — `mount_publication_ui(app)` function. Configure Jinja2Templates pointing at `publication/ui/templates/`. Register routes: `GET /publication/` (latest edition landing page), `GET /publication/archive` (edition list), `GET /publication/{date}` (edition detail), `GET /publication/{date}#{section}` (anchor navigation). Mount static files from `publication/ui/static/`. |
| 5.5 | Open | | | Create `ai_benchmark/publication/ui/templates/base.html` — publication layout template with header, nav (Latest, Archive), main content block, footer. Reuse CSS variables and conventions from `eval/ui/templates/`. |
| 5.6 | Open | | | Create `ai_benchmark/publication/ui/templates/latest.html` — daily landing page: edition date, summary, sections with anchor links, entries with headline/summary/verification badge/confidence indicator/source count. Expandable entry detail showing why_it_matters and supporting evidence links. |
| 5.7 | Open | | | Create `ai_benchmark/publication/ui/templates/archive.html` — paginated list of prior editions with date, status, item count, and link to detail page. |
| 5.8 | Open | | | Create `ai_benchmark/publication/ui/templates/detail.html` — full edition view with section navigation sidebar, entry cards, verification state badges, confidence tier indicators, and source link sets. |
| 5.9 | Open | | | Create `ai_benchmark/publication/ui/static/css/publication.css` — styles for edition layout, section cards, entry cards, verification badges (confirmed/unconfirmed/conflicted), confidence indicators, expandable detail panels. |
| 5.10 | Open | | | Create `ai_benchmark/publication/ui/static/js/publication.js` — entry detail expansion toggle, section anchor scroll, auto-refresh for latest page. |
| 5.11 | Open | | | Mount publication UI in `ai_benchmark/eval/api/app.py` — call `mount_publication_ui(app)` alongside existing `mount_ui(app)`. |
| 5.12 | Open | | | Create `tests/test_publication_cli.py` — test CLI commands with Click test runner: generate produces edition, list shows editions, export writes file, freeze updates status. |
| 5.13 | Open | | | Create `tests/test_publication_ui.py` — test UI routes return 200 with expected content: latest page, archive page, detail page, static file serving. |
| 5.14 | Open | | | Run full `pytest` and ruff checks — fix until green. |
| 5.15 | Open | | | Stage all Phase 5 changes. |
| 5.16 | Open | | | Commit all Phase 5 changes. |

### Phase 5 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Add publication CLI commands and server-rendered web UI`

---

## Phase 6: Scheduler Integration

**Goal:** Daily editions are generated automatically after collection and analysis jobs complete. Publication health is tracked alongside source health.
**Depends on:** Phase 5.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 6.1 | Open | | | Add publication job registration to `ai_benchmark/scheduling/scheduler.py` — new method `add_publication_job(cron, settings)` that adds an APScheduler CronTrigger job calling `generate_edition()`. Job runs after collection and analysis jobs by scheduling at cutoff_hour + offset. Record start/end time, success/failure, and edition metadata. Publication failures must not block the base collection pipeline (catch and log). |
| 6.2 | Open | | | Add `[publication]` section to `ai_benchmark/config/schedules.toml` with default cron `"0 7 * * *"` (daily at 7 AM, after typical 6 AM analysis window). |
| 6.3 | Open | | | Add publication health tracking to `SourceHealthTracker` or create `PublicationHealthTracker` in `ai_benchmark/scheduling/scheduler.py` — record publication job success/failure, last_generated_at, last_error, consecutive_failures. Expose via `get_publication_status() -> dict`. |
| 6.4 | Open | | | Create `ai_benchmark/publication/services/export.py` — `async def export_static(edition: EditionResult, export_path: str, formats: list[str])`. Write markdown and/or JSON files to configured export_path with date-stamped filenames. Called by scheduler job when `export_path` is configured. |
| 6.5 | Open | | | Add late-update regeneration logic to `ai_benchmark/publication/services/edition.py` — `async def check_regeneration_eligible(session, publication_date, settings) -> bool`. Check if high-confidence items arrived after edition generation but before auto_freeze_delay_hours. If eligible and edition is not frozen, flag edition status as "regeneration_available". |
| 6.6 | Open | | | Create `tests/test_publication_scheduler.py` — test job registration, publication health tracking, static export file creation, regeneration eligibility detection. |
| 6.7 | Open | | | Run full `pytest` and ruff checks — fix until green. |
| 6.8 | Open | | | Stage all Phase 6 changes. |
| 6.9 | Open | | | Commit all Phase 6 changes. |

### Phase 6 Summary

- **Changes:** TBD
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
