# Site Review 1 — Implementation Plan

**Source document:** `docs/site_review_1_doc.md`

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
| No new dependencies | All changes use existing Jinja2, SQLAlchemy, CSS |

## Phase 1: Sidebar Spacing & Back Navigation

**Goal:** Sidebar is tighter, Intelligence pages have back buttons.
**Depends on:** Nothing (first phase).

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 1.1     | Completed | 2026-03-29 03:30 PM | 2026-03-29 03:31 PM | Reduce sidebar vertical spacing in `ai_benchmark/eval/ui/static/css/style.css`: `.sidebar-nav li a` padding 10px→7px, `.nav-section` top 16px→10px, `.sidebar-brand` 16px→12px |
| 1.2     | Completed | 2026-03-29 03:31 PM | 2026-03-29 03:32 PM | Add back button to `templates/analysis/model_detail.html` page-header → `/eval/analysis/models` |
| 1.3     | Completed | 2026-03-29 03:31 PM | 2026-03-29 03:32 PM | Add back button to `templates/analysis/models.html` page-header → `/eval/analysis` |
| 1.4     | Completed | 2026-03-29 03:31 PM | 2026-03-29 03:32 PM | Add back button to `templates/analysis/verification.html` page-header → `/eval/analysis` |
| 1.5     | Completed | 2026-03-29 03:32 PM | 2026-03-29 03:33 PM | Verify all 4 Intelligence pages render correctly (manual curl check) |
| 1.6     | Completed | 2026-03-29 03:33 PM | 2026-03-29 03:33 PM | Stage all Phase 1 changes |
| 1.7     | Completed | 2026-03-29 03:33 PM | 2026-03-29 03:33 PM | Commit all Phase 1 changes |

### Phase 1 Summary

- **Changes:** Reduced sidebar padding (brand 16→12px, links 10→7px, sections 16→10px, nav list 8→4px). Added "Back to" buttons on model_detail, models, and verification templates.
- **Changes hosted at:** `ai_benchmark/eval/ui/static/css/style.css`, `ai_benchmark/eval/ui/templates/analysis/{model_detail,models,verification}.html`
- **Commit:** `Site review 1: tighten sidebar spacing, add back navigation to Intelligence pages`

## Phase 2: Clickable Stat Cards

**Goal:** Summary stat cards on Intelligence pages link to relevant detail pages.
**Depends on:** Phase 1.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 2.1     | Completed | 2026-03-29 03:34 PM | 2026-03-29 03:35 PM | Add `a.stat-card-link` CSS rule in `style.css` (no underline, inherit color, display block) |
| 2.2     | Completed | 2026-03-29 03:35 PM | 2026-03-29 03:36 PM | Wrap overview.html stat cards: Models→`/eval/analysis/models`, Orgs→`/eval/analysis/models`, Claims→`/eval/analysis/verification`, Confirmed→`/eval/analysis/verification`, Conflicted→`/eval/analysis/verification` |
| 2.3     | Completed | 2026-03-29 03:36 PM | 2026-03-29 03:36 PM | Verify overview page renders with clickable cards and correct link targets |
| 2.4     | Completed | 2026-03-29 03:36 PM | 2026-03-29 03:36 PM | Stage all Phase 2 changes |
| 2.5     | Completed | 2026-03-29 03:36 PM | 2026-03-29 03:37 PM | Commit all Phase 2 changes |

### Phase 2 Summary

- **Changes:** Added `a.stat-card-link` CSS class with hover border/shadow effect. Wrapped 5 overview stat cards (Models, Orgs, Claims, Confirmed, Conflicted) in links to models and verification pages.
- **Changes hosted at:** `ai_benchmark/eval/ui/static/css/style.css`, `ai_benchmark/eval/ui/templates/analysis/overview.html`
- **Commit:** `Site review 1: make overview stat cards clickable links`

## Phase 3: Date Fallback

**Goal:** All models show First Seen and Latest Activity dates instead of "—".
**Depends on:** Phase 2.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 3.1     | Completed | 2026-03-29 03:38 PM | 2026-03-29 03:40 PM | Modify `list_tracked_models()` in `analysis/services/model_lifecycle.py` to COALESCE `published_date` with formatted `observed_at` for first_seen and latest_activity |
| 3.2     | Completed | 2026-03-29 03:40 PM | 2026-03-29 03:40 PM | Modify `build_model_profile()` in `analysis/services/model_lifecycle.py` to fall back to `observed_at.strftime("%Y-%m-%d")` when `published_date` is None |
| 3.3     | Completed | 2026-03-29 03:41 PM | 2026-03-29 03:42 PM | Run `pytest tests/test_analysis/` to verify no regressions — 213 passed |
| 3.4     | Completed | 2026-03-29 03:40 PM | 2026-03-29 03:41 PM | Run `ruff check` and `ruff format --check` on modified files |
| 3.5     | Completed | 2026-03-29 03:42 PM | 2026-03-29 03:42 PM | Stage all Phase 3 changes |
| 3.6     | Completed | 2026-03-29 03:42 PM | 2026-03-29 03:42 PM | Commit all Phase 3 changes |

### Phase 3 Summary

- **Changes:** `list_tracked_models()` uses SQLAlchemy `case()` to COALESCE `published_date` with `strftime("%Y-%m-%d", observed_at)`. `build_model_profile()` uses `e.published_date or e.observed_at.strftime("%Y-%m-%d")` for all events.
- **Changes hosted at:** `ai_benchmark/analysis/services/model_lifecycle.py`
- **Commit:** `Site review 1: fall back to observed_at for missing published_date`

## Phase 4: Slug Display Prettification

**Goal:** Model slugs display as human-readable text in table cells.
**Depends on:** Phase 3.

| PhaseNo | Status | Started (PST) | Completed (PST) | Description |
|---------|--------|---------------|------------------|-------------|
| 4.1     | Open   |               |                  | Register `prettify_slug` Jinja2 filter in `ai_benchmark/eval/ui/server.py` on the `templates` env: replace hyphens with spaces, title-case |
| 4.2     | Open   |               |                  | Apply `prettify_slug` filter in `templates/analysis/models.html` model name table cell (display only, not href) |
| 4.3     | Open   |               |                  | Apply `prettify_slug` filter in `templates/analysis/overview.html` spotlight and landscape model/org names where slugs appear |
| 4.4     | Open   |               |                  | Apply `prettify_slug` filter in `templates/analysis/verification.html` model name column |
| 4.5     | Open   |               |                  | Apply `prettify_slug` filter in `templates/analysis/model_detail.html` page title and related models section |
| 4.6     | Open   |               |                  | Run `ruff check` and `ruff format --check` on modified files |
| 4.7     | Open   |               |                  | Run full test suite `pytest` |
| 4.8     | Open   |               |                  | Stage all Phase 4 changes |
| 4.9     | Open   |               |                  | Commit all Phase 4 changes |

### Phase 4 Summary

- **Changes:** TBD
- **Changes hosted at:** TBD
- **Commit:** `Site review 1: prettify model slug display in Intelligence UI`
