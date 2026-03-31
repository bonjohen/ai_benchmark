# Physical Design Requirements: Pipeline Data Quality Remediation

**Source document:** `docs/pipeline_failures_design.md`
**Project root:** `C:\Projects\ai_benchmark`
**Date:** 2026-03-31 00:30 (PST)

## 1. System Context

### 1.1 Existing Infrastructure to Reuse

| Asset | Location | Reuse |
|---|---|---|
| Model slug extractor | `processing/normalizer.py:extract_model_slug()` (line 155) | Enhance regex patterns, add dictionary lookup pre-pass |
| Model slug validator | `processing/normalizer.py:validate_model_slug()` (line 323) | Keep poison word filters, relax overly aggressive blocks |
| Event type classifier | `processing/normalizer.py:classify_event_type()` (line 582) | Add benchmark_variant metadata override |
| Processing pipeline | `processing/pipeline.py:process_item()` (line 43) | Add post-normalization override for benchmark_variant presence |
| LMArena collector | `sources/benchmarks/lmarena.py:extract_leaderboard()` (line 60) | Already extracts Elo via `_extract_elo()`; fix `raw_content` to include score |
| BenchmarkCollector base | `sources/benchmarks/__init__.py:extract_items()` (line 39) | Modify `body` template to include score alongside rank |
| Cross-reference builder | `processing/cross_reference.py:build_cross_references()` (line 228) | Tighten strategy 2 (org+type) to require model_slug |
| Collection coordinator | `coordination/coordinator.py:_create_tasks()` (line 126) | Add source upsert before page creation |
| API client retry | `collection/api_client.py:get()` (line 39) | Already fixed (30s backoff). No change. |
| Candidate paper triage | `processing/triage.py:ingest_candidate()` | Add pending-retry logic on subsequent runs |
| Source catalog | `config/sources.toml` | Read by coordinator; use as seed for DB upsert |
| Model registry seeder | `analysis/services/model_registry.py:seed_model_entities()` | Re-run after slug backfill to update entity count |
| Backfill CLI | `analysis/cli.py` | Add `backfill-slugs` and `backfill-types` commands |

### 1.2 New Dependencies to Add

| Package | Purpose | Version Constraint |
|---|---|---|
| (none) | All fixes use existing dependencies | — |

## 2. Package Layout

All changes are within existing packages. No new packages required.

```
ai_benchmark/
  processing/
    normalizer.py          ← Enhanced extract_model_slug, classify_event_type
    pipeline.py            ← Benchmark type override in process_item
    cross_reference.py     ← Tightened supplement strategy
  sources/
    benchmarks/
      __init__.py          ← BenchmarkCollector body template includes score
      lmarena.py           ← raw_content includes Elo score
  coordination/
    coordinator.py         ← Source record upsert
  analysis/
    cli.py                 ← backfill-slugs, backfill-types commands
    services/
      model_registry.py    ← Re-seed after backfill
```

## 3. Data Model

No schema changes. All fixes operate on existing columns:
- `event_records.model_slug` (String 200, nullable) — populated by improved extractor
- `event_records.event_type` (String 50) — corrected by type override
- `event_records.raw_content` (Text, nullable) — enriched with Elo scores
- `sources.id` / `pages.id` — populated by coordinator upsert

## 4. Model Slug Extraction Enhancement

### 4.1 Known Model Dictionary

Add a dictionary-based pre-pass to `extract_model_slug()` that matches known model names before falling back to regex patterns. The dictionary maps display names to canonical slugs.

**Location:** `processing/normalizer.py`, new constant `_KNOWN_MODEL_NAMES` above `extract_model_slug()`.

**Dictionary contents** (derived from model_entities table + common names):

```python
_KNOWN_MODEL_NAMES: dict[str, str] = {
    "claude opus 4.6": "claude-opus-4.6",
    "claude sonnet 4.6": "claude-sonnet-4.6",
    "claude haiku 4.5": "claude-haiku-4.5",
    "claude opus 4.5": "claude-opus-4.5",
    "claude sonnet 4.5": "claude-sonnet-4.5",
    "claude opus 4": "claude-opus-4",
    "claude sonnet 3.7": "claude-sonnet-3.7",
    "claude sonnet 3.5": "claude-sonnet-3.5",
    "claude haiku 3.5": "claude-haiku-3.5",
    "claude 3 opus": "claude-3-opus",
    "claude 3 sonnet": "claude-3-sonnet",
    "claude 3 haiku": "claude-3-haiku",
    "gpt-5": "gpt-5",
    "gpt-5.2": "gpt-5.2",
    "gpt-5.3": "gpt-5.3",
    "gpt-5.4": "gpt-5.4",
    "gpt-4o": "gpt-4o",
    "gpt-4o mini": "gpt-4o-mini",
    "gemini 3 pro": "gemini-3-pro",
    "gemini 3 flash": "gemini-3-flash",
    "gemini 3": "gemini-3",
    "gemini 3.1 pro": "gemini-3.1-pro",
    "grok-4": "grok-4",
    "grok-3": "grok-3",
    "mistral small 3": "mistral-small-3",
    "mistral medium 3": "mistral-medium-3",
    "mistral large 3": "mistral-large-3",
    "command r": "command-r",
    "command r+": "command-r-plus",
    "command a": "command-a",
    "llama 3": "llama-3",
    "llama 3.1": "llama-3.1",
    "llama 3.3": "llama-3.3",
    "llama 4": "llama-4",
    # ... extend as needed
}
```

**Matching algorithm:**
1. Normalize input: lowercase, collapse whitespace, strip punctuation boundaries.
2. Apply whitespace repair: insert space before uppercase letter preceded by lowercase (fixes "launchedClaude" → "launched Claude").
3. Search for each dictionary key as a substring in the normalized text. Longest match wins.
4. If found, return the canonical slug.
5. If not found, fall back to existing regex patterns.

### 4.2 Whitespace Repair

Add a pre-processing step before slug extraction that fixes HTML-concatenated text:

```python
_CAMEL_BOUNDARY = re.compile(r"([a-z])([A-Z])")

def _repair_whitespace(text: str) -> str:
    """Insert spaces at CamelCase boundaries from HTML concatenation."""
    return _CAMEL_BOUNDARY.sub(r"\1 \2", text)
```

Called at the top of `extract_model_slug()` before dictionary and regex matching.

### 4.3 Backfill CLI Command

New command `ai-benchmark analyze backfill-slugs`:
1. Query all events where `model_slug IS NULL`.
2. For each event, run the improved `extract_model_slug()` against `title + " " + raw_content`.
3. If a slug is found, update the event record.
4. Report: `N events updated out of M NULL-slug events`.

**Location:** `analysis/cli.py`, new `@analyze_group.command("backfill-slugs")`.

## 5. LMArena Event Type and Score Fixes

### 5.1 Event Type Override

In `processing/pipeline.py:process_item()`, after `event_type = classify_event_type(...)` (line 75), add:

```python
# Override: items with benchmark_variant metadata are benchmark results
if item.metadata.get("benchmark_variant") and event_type == "announcement":
    event_type = "benchmark_result"
```

This ensures all future LMArena items are correctly typed.

### 5.2 Elo Score in raw_content

The `BenchmarkCollector.extract_items()` method in `sources/benchmarks/__init__.py` builds `body` as:
```python
body=f"Rank: {entry.rank}, Variant: {variant}, Conditions: {conditions}"
```

Change to include the score:
```python
score_str = f", Score: {entry.score}" if entry.score is not None else ""
body=f"Rank: {entry.rank}{score_str}, Variant: {variant}, Conditions: {conditions}"
```

The LMArena collector's `_extract_elo()` already parses the Elo score from the HTML. This just ensures it flows into `raw_content` via `body`.

### 5.3 Backfill Event Types

New command `ai-benchmark analyze backfill-types`:
```sql
UPDATE event_records SET event_type = 'benchmark_result'
WHERE benchmark_variant IS NOT NULL AND event_type = 'announcement';
```

Also backfill Elo scores from claim_text into raw_content:
1. Query events where `organization = 'LMArena'` and `raw_content LIKE 'Rank:%'` and `raw_content NOT LIKE '%Score:%'`.
2. For each, find the associated claim where `claim_text LIKE 'LMArena:%=%'`.
3. Extract the numeric Elo value from claim_text.
4. Update raw_content to include `Score: {elo}`.

## 6. Cross-Reference Tightening

### 6.1 Strategy 2 Modification

In `processing/cross_reference.py`, the org + event_type strategy (strategy 2) currently matches any two events from the same org with the same event_type within 3 days. This creates 333K supplements.

**Change:** Require `model_slug IS NOT NULL` on both events for strategy 2 to fire. Events without model_slug cannot meaningfully "supplement" each other.

```python
# In find_related_by_org_event_type():
stmt = stmt.where(EventRecord.model_slug.is_not(None))
```

Also add to the caller:
```python
# Skip strategy 2 if the event itself has no model_slug
if event.model_slug:
    related = await find_related_by_org_event_type(event, time_window_days=3)
```

### 6.2 Supplement Cap

Add a maximum of 10 supplements per event per strategy:
```python
related = related[:10]  # Cap supplements to avoid explosion
```

## 7. Source/Page Table Population

### 7.1 Coordinator Source Upsert

In `coordination/coordinator.py:_create_tasks()`, before the page lookup, add a source upsert:

```python
if source_record is None:
    source_record = SourceModel(
        source_name=source_config.source_name,
        category=source_config.category,
        organization=source_config.organization,
        homepage_url=source_config.homepage_url,
        base_domain=source_config.base_domain,
        trust_rating=source_config.trust_rating,
        source_role=source_config.source_role,
        classification=source_config.classification,
        collection_method=source_config.collection_method,
    )
    session.add(source_record)
    await session.flush()
```

This ensures the `sources` table is populated on first collection. The existing page creation code already handles pages (line 168-174) but depends on `source_id > 0`.

## 8. Research Enrichment Retry

### 8.1 Pending Candidate Retry

In the Semantic Scholar collector's `collect_via_api()`, after processing fresh queries, add a retry pass for pending candidates:

```python
# Retry pending candidates from previous runs
pending = await session.execute(
    select(CandidatePaper)
    .where(CandidatePaper.status == "pending")
    .where(CandidatePaper.retry_count < 3)
    .order_by(CandidatePaper.discovered_at)
    .limit(10)
)
for paper in pending.scalars():
    # Attempt enrichment...
    paper.retry_count += 1
    paper.last_retry_at = datetime.now(UTC)
```

### 8.2 Configuration

Add `AI_BENCH_SEMANTIC_SCHOLAR_API_KEY` to `C:\ai-benchmark\config\.env`. Document in the `.env` template that this key is recommended for research enrichment.

## 9. Verification Criteria

| Fix | Verification |
|---|---|
| §4 Slug extraction | Run `backfill-slugs` → report >60% of 2,402 NULL-slug events updated. Re-run `seed-models` → entity count decreases (dedup via dictionary). |
| §5.1 Event type override | Run `backfill-types` → 0 events with `event_type='announcement' AND benchmark_variant IS NOT NULL`. |
| §5.2 Elo in raw_content | Re-collect LMArena → `raw_content` contains `Score: NNNN`. Benchmark detail page shows numeric scores. |
| §5.3 Elo backfill | After backfill, query `SELECT count(*) FROM event_records WHERE raw_content LIKE '%Score:%' AND organization='LMArena'` → >600. |
| §6 Cross-ref tightening | Delete existing supplements: `DELETE FROM cross_references WHERE relationship_type='supplements'`. Re-collect one source. Cross-ref count stays <100 per source. |
| §7 Source upsert | After collection, `SELECT count(*) FROM sources` → 22. `ai-benchmark status` shows non-zero counts. |
| §8 Research retry | After 3 collection runs with API key, `SELECT count(*) FROM candidate_papers WHERE status='enriched'` → >0. |

## 10. Implementation Sequence

| Phase | Scope | Files Modified | Depends On |
|---|---|---|---|
| 1 | Slug extraction (§4) + backfill CLI | `normalizer.py`, `analysis/cli.py` | Nothing |
| 2 | LMArena type + score fix (§5) + backfill CLI | `pipeline.py`, `benchmarks/__init__.py`, `analysis/cli.py` | Nothing |
| 3 | Cross-reference tightening (§6) | `cross_reference.py` | Nothing |
| 4 | Source/page population (§7) | `coordinator.py` | Nothing |
| 5 | Research retry (§8) | `semantic_scholar.py`, config | Nothing |
| 6 | Deploy + backfill + re-seed | CLI commands, production deploy | Phases 1-5 |

All phases are independent and can be implemented in any order. Phase 6 is the integration step that runs backfill commands and re-seeds the model registry.
