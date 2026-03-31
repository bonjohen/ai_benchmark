# Data Presentation Rework — Design Document

## 1. Purpose

The Intelligence UI currently presents "models" as raw (model_slug, organization) rows derived from `event_records`. The production database has 501 distinct model_slugs and 535 (slug, org) combinations, displayed as "Total Models: 500." These are not models — they are model-organization-event groups. The same real-world model appears multiple times under different slugs (e.g., `claude-sonnet-3.5` from Anthropic and `claude-3-5-sonnet-20241022` from LMArena) and under different reporting organizations (e.g., `gpt-5` from both OpenAI and Scale AI). The UI shows event counts, Elo scores, and active/deprecated status in a flat table that conflates identity with observation.

Separately, benchmarks have no dedicated page in the UI despite the system tracking 8 benchmark variants with leaderboard data. Benchmark data is accessible only through model detail pages and the overview's evolution table.

This design introduces a curated Model Registry and a first-class Benchmarks section to fix both problems.

## 2. Scope

**In scope:**
- New `model_entities` and `model_entity_slugs` database tables
- Automated seeding service that populates the registry from existing event data
- Reworked Models list page: curated models with publisher, status, release date
- Reworked Model detail page: uses registry identity, aggregates events across all slug variants
- New Benchmarks list page: select a benchmark, see entry count and leader
- New Benchmark detail page: full leaderboard with model scores
- Corrected overview stats using curated model count
- Sidebar navigation update (add Benchmarks link)

**Out of scope:**
- Changes to the collection pipeline, normalizer, or event schema
- Manual curation UI (automated seeding only; manual curation is a future enhancement)
- Model family grouping (grouping `claude-sonnet-3.5` / `3.7` / `4.5` into a "Claude Sonnet" family)
- Changes to CLI analysis commands or API endpoints

## 3. Core Design Principles

1. **Separate identity from observation.** A ModelEntity is "model Y exists, was published by org Z." An EventRecord is "source X said model Y did something." The registry is authoritative for display names, publisher, and status. Events remain authoritative for what happened and when.

2. **Publisher vs. aggregator distinction.** LMArena, Scale AI, Artificial Analysis, Stanford x Laude are aggregators that report on models they did not create. Anthropic, OpenAI, Google, Meta, xAI, Mistral AI, Cohere are publishers. The registry records the publisher, not the reporting source.

3. **Automated seeding, nullable enrichment.** Initial population is fully automated from event data. Description, parameter count, and model family are nullable fields that can be enriched over time without requiring re-seeding.

4. **Benchmarks are a peer entity.** Benchmarks get equal navigational weight with models — their own list page and detail page in the sidebar.

## 4. Primary User Stories

1. A user navigates to `/eval/analysis/models` and sees a clean list of ~100-150 distinct AI models (e.g., "Claude Sonnet 4.5", "GPT-5", "Gemini 3 Pro") with their publisher, status, and release date. Clicking a model opens its detail page.

2. A user clicks a model and sees: publisher, status, description (if available), release date, event timeline across all sources that mentioned this model, benchmark scores, and related models.

3. A user navigates to `/eval/analysis/benchmarks` and sees the 8 benchmark variants with entry counts and current leaders. Clicking a benchmark shows the full leaderboard.

4. A user on the overview page sees "Tracked Models: ~120" (curated count), not "500" (raw event groups).

## 5. Functional Requirements

### 5.1 Data Model

**`model_entities` table:**

| Column | Type | Purpose |
|---|---|---|
| id | Integer PK | Auto-increment |
| canonical_slug | String(200), unique | Authoritative slug (e.g., `claude-sonnet-4.5`) |
| display_name | String(300) | Human-readable name (e.g., "Claude Sonnet 4.5") |
| publisher | String(200) | Organization that created the model |
| model_family | String(200), nullable | Grouping (e.g., "Claude Sonnet") |
| status | String(20) | `active`, `deprecated`, `announced` |
| description | Text, nullable | Short description |
| parameter_count | String(50), nullable | Model size (e.g., "70B") |
| release_date | String(20), nullable | First known release date |
| created_at | DateTime | Row creation |
| updated_at | DateTime | Last modification |

**`model_entity_slugs` table (many-to-one mapping):**

| Column | Type | Purpose |
|---|---|---|
| id | Integer PK | Auto-increment |
| entity_id | Integer FK(model_entities.id) | Parent entity |
| event_slug | String(200) | A model_slug value from event_records |
| source_org | String(200) | The organization that used this slug |

Example: ModelEntity `claude-sonnet-3.5` (Anthropic) maps to slugs:
- `claude-sonnet-3.5` from Anthropic
- `claude-3-5-sonnet-20240620` from LMArena
- `claude-3-5-sonnet-20241022` from LMArena

### 5.2 Seeding Service

New file: `ai_benchmark/analysis/services/model_registry.py`

**`seed_model_entities(session)`** — populates registry from event data:

1. Query all distinct (model_slug, organization) pairs where model_slug is not NULL
2. Classify each organization as publisher or aggregator:
   - Publishers: Anthropic, OpenAI, Google, Meta, xAI, Mistral AI, Cohere
   - Aggregators: LMArena, Scale AI, Artificial Analysis, Stanford x Laude, SWE-bench team, GAIA benchmark
3. For each publisher-sourced slug → create a ModelEntity with that publisher
4. For each aggregator-sourced slug → match to existing publisher entity by slug, or create with publisher="Unknown"
5. Handle versioned slugs: strip `-YYYYMMDD` suffixes and map to base slug if it exists

**`list_model_entities(session, publisher=None, status=None, limit=200)`** — query for list page

**`get_model_entity(session, canonical_slug)`** — single entity lookup

**`get_entity_events(session, entity_id)`** — all events across all mapped slugs

### 5.3 Overview Page Changes

- "Tracked Models" stat → count of `model_entities` rows (not `list_tracked_models()`)
- "Organizations" stat → distinct publishers from `model_entities`
- "Benchmarks" stat card → links to `/eval/analysis/benchmarks`
- Keep Events Collected and Claims stats as-is

### 5.4 Models List Page

Route: `GET /eval/analysis/models`

Table columns:
- **Model** (display_name, links to detail page)
- **Publisher**
- **Status** (badge: active/deprecated/announced)
- **Release Date**

Remove: Event count, Organization (replaced by Publisher), Elo scores.

Filter: Publisher dropdown (replaces org filter).

### 5.5 Model Detail Page

Route: `GET /eval/analysis/models/{slug}`

Header: display_name, publisher, status badge, release date, description, parameter count.

Sections below header (using existing services, querying across all mapped slugs):
- **Event Timeline** — chronological list of events from all sources
- **Benchmark Scores** — scores from benchmark events
- **Claims Summary** — confirmation/conflict status
- **Related Models** — from cross-references

### 5.6 Benchmarks List Page

Route: `GET /eval/analysis/benchmarks`

Uses existing `list_benchmarks()` service.

Table columns:
- **Benchmark** (links to detail)
- **Entries** (model count)
- **Latest Date**
- **Current Leader** (model display name)
- **Top Score**

### 5.7 Benchmark Detail Page

Route: `GET /eval/analysis/benchmarks/{name}`

Uses existing `get_benchmark_leaderboard()` service.

Sections:
- Header with benchmark name and as-of date
- **Leaderboard table**: Rank, Model (links to model detail), Score, Date, Source

### 5.8 Sidebar Update

Add to Intelligence section in eval `base.html`:
```
Models (existing)
Benchmarks (NEW — links to /eval/analysis/benchmarks)
Verification (existing)
```

## 6. Key Implementation Files

| File | Change |
|---|---|
| `alembic/versions/010_model_entities.py` | New migration |
| `analysis/models.py` | Add ModelEntity, ModelEntitySlug ORM models |
| `analysis/services/model_registry.py` | New seeding and query service |
| `analysis/cli.py` | Add `seed-models` command |
| `eval/ui/server.py` | Update overview, models, model detail routes; add benchmarks routes |
| `eval/ui/templates/analysis/overview.html` | Update stats, add benchmarks link |
| `eval/ui/templates/analysis/models.html` | Rewrite for registry data |
| `eval/ui/templates/analysis/model_detail.html` | Use registry identity |
| `eval/ui/templates/analysis/benchmarks.html` | New template |
| `eval/ui/templates/analysis/benchmark_detail.html` | New template |
| `eval/ui/templates/base.html` | Add Benchmarks to sidebar |

## 7. Verification

1. Run `ai-benchmark analyze seed-models` → verify ~100-150 entities created
2. Load `/eval/analysis` → verify "Tracked Models" shows curated count
3. Load `/eval/analysis/models` → verify clean model list with publishers
4. Click a model → verify detail page shows events from all slug variants
5. Load `/eval/analysis/benchmarks` → verify 8 benchmarks listed
6. Click a benchmark → verify leaderboard with model scores
7. Run `pytest` → all existing + new tests pass
