# Site Review 1 — Design Document

## 1. Purpose

Address the first round of UI/UX issues identified during manual walkthrough of the Intelligence section (`/eval/analysis/*`). These are polish and usability fixes — no new features, no new pages.

## 2. Scope

Five issues, all confined to the eval UI layer (templates, CSS, server routes) and the `model_lifecycle` service query layer.

### Issue 1: Sidebar Vertical Spacing Is Too Generous

The sidebar navigation sections (`.nav-section` headings, link padding) consume excessive vertical space. With the new Intelligence section adding 4 more nav items, the sidebar is becoming long. Current values:

- `.sidebar-nav li a` padding: `10px 20px` (10px vertical per link)
- `.sidebar-nav .nav-section` padding: `16px 20px 4px` (16px top gap before each section heading)
- `.sidebar-brand` padding: `16px 20px`

Reduce all three to tighten the sidebar without losing readability.

### Issue 2: No Back Navigation on Intelligence Pages

Every existing eval detail page (`datasets/detail.html`, `evaluations/detail.html`, `runs/detail.html`, etc.) includes a "Back to List" button in the page header using:

```html
<a href="/eval/..." class="btn btn-outline btn-sm">Back to List</a>
```

The four Intelligence templates (`overview.html`, `models.html`, `model_detail.html`, `verification.html`) have no back navigation. Users who arrive at a model detail page have no in-content way to return to the models list without using the sidebar.

Pages that need back links:
- `model_detail.html` → Back to Models (`/eval/analysis/models`)
- `verification.html` → Back to Overview (`/eval/analysis`)
- `models.html` → Back to Overview (`/eval/analysis`)

The overview page is the landing page and does not need a back link.

### Issue 3: Stat Cards Are Not Clickable

All stat cards on Intelligence pages are plain `<div>` elements. Users expect summary numbers to be clickable links to the underlying data. Applicable linkable cards:

**overview.html:**
- "Tracked Models" → `/eval/analysis/models`
- "Organizations" → `/eval/analysis/models` (the org filter is there)
- "Claims" → `/eval/analysis/verification`
- "Confirmed %" → `/eval/analysis/verification`
- "Conflicted %" → `/eval/analysis/verification`

**models.html:**
- "Active" count is informational (already on the models page)
- "Organizations" count is informational

**verification.html:**
- Tier distribution cards are informational (already on the verification page)

### Issue 4: Missing First Seen / Latest Activity Dates

Many models show "—" for First Seen and Latest Activity on the models list and model detail pages. Root cause: `list_tracked_models()` and `build_model_profile()` in `model_lifecycle.py` use `EventRecord.published_date` exclusively. Many EventRecords have NULL `published_date` (the field is optional String(20)).

Every EventRecord has a non-null `observed_at` (DateTime, server_default=now()). The fix is to fall back to `observed_at` when `published_date` is NULL:

- In `list_tracked_models`: use `COALESCE(published_date, CAST(observed_at AS text))` or equivalent SQLAlchemy expression for the min/max aggregations.
- In `build_model_profile`: use `e.published_date or e.observed_at.strftime("%Y-%m-%d")` when building the published_dates list (this pattern already exists in `get_model_timeline` at line ~120).

### Issue 5: Raw Slugs Displayed as Model Names

Model slugs are extracted from event titles via regex in `normalizer.py:extract_model_slug()`. For well-known models this produces clean identifiers (`gpt-5.2`, `claude-3.5-sonnet`). But for events without a matched model family, the slug can be a headline fragment (`gemini-3-becomes-top-model`, `gemini-3-pro-on-artificial`).

These slugs are fine as URL identifiers and programmatic keys. They look wrong as display text in table cells. The model_slug is the only identifier available — there is no separate display_name column.

Fix approach: add a Jinja2 template filter or inline transformation that prettifies slugs for display — replace hyphens with spaces and title-case. This won't produce perfect names but is a visual improvement. Where we have the full event title available (model_detail.html milestones table), we already display it correctly.

## 3. Core Design Principles

1. **Minimal changes** — CSS tweaks, template edits, one query fix. No new tables, no new services, no new endpoints.
2. **Consistent with existing patterns** — Back buttons use the same `btn btn-outline btn-sm` pattern. Stat cards wrap in `<a>` tags. Sidebar spacing changes apply globally.
3. **Graceful fallback** — Date fallback uses observed_at, which is always populated. Slug prettification is display-only and does not affect routing or data.

## 4. Primary User Stories

1. As a user browsing the Intelligence section, I can navigate back to parent pages without relying on the sidebar or browser back button.
2. As a user viewing summary statistics, I can click a stat card to drill into the relevant detail page.
3. As a user scanning the models list, I see dates for all models rather than "—" placeholders.
4. As a user reading the sidebar, all navigation items are visible without excessive scrolling.
5. As a user reading model names in tables, I see human-readable text rather than raw URL slugs.

## 5. Functional Requirements

### 5.1 Sidebar Spacing (CSS only)

Reduce vertical padding on `.sidebar-nav li a` from 10px to 7px. Reduce `.nav-section` top padding from 16px to 10px. Reduce `.sidebar-brand` vertical padding from 16px to 12px.

### 5.2 Back Navigation (Templates only)

Add a back button to the page-header div on `model_detail.html`, `models.html`, and `verification.html`. Use the existing `btn btn-outline btn-sm` pattern.

### 5.3 Clickable Stat Cards (Templates + CSS)

Wrap stat-card divs in `<a>` tags with appropriate href. Add CSS rule for `a.stat-card-link` to remove text-decoration and inherit color.

### 5.4 Date Fallback (Service query)

Modify `list_tracked_models()` to COALESCE published_date with a formatted observed_at. Modify `build_model_profile()` to fall back to observed_at when building the dates list.

### 5.5 Slug Display (Templates)

Register a Jinja2 filter `prettify_slug` on the templates engine that converts `some-model-name` to `Some Model Name`. Apply it in table cells that display model_slug as a label (not in href URLs).
