# Data Quality: Model Slug Validation Design Document

## 1. Purpose

Non-AI-model entries are being stored as `model_slug` values in the EventRecord table, polluting the model namespace. Programming languages ("Rust", "Go", "Java"), repository paths ("redis/redis", "tokio-rs/tokio"), aggregate labels ("Total", "2022"), and feature names ("Code execution", "File search") appear as tracked models. This document defines how to prevent garbage model slugs at ingestion and clean up existing data.

## 2. Scope

The problem has two root causes:

1. **SWE-bench multilingual variant** — The leaderboard ranks programming languages and repositories, not AI models. The collector passes `cells[0]` as `model_hint`, which the pipeline uses directly without validation.

2. **Pipeline bypass** — `process_item()` at line 71 of `pipeline.py` uses `model_hint` directly when present, skipping `extract_model_slug()` which would correctly reject non-model text. This means any benchmark collector can inject arbitrary strings as model slugs.

Impact: 51 SWE-bench entries (100% garbage), plus additional garbage from other sources. These pollute the Models page, inflate model counts, and create spurious cross-references (all 51 SWE-bench entries link to each other via org+event_type matching).

## 3. Core Design Principles

1. **Validate at the gate** — `model_hint` must pass the same validation as `extract_model_slug()` before being accepted. The pipeline should never blindly trust collector-provided hints.

2. **Source-aware handling** — SWE-bench multilingual entries should store the language/repo as benchmark metadata, not as model slugs. The variant detection already exists in the collector.

3. **Clean existing data** — Null out invalid model_slugs on existing records. Remove orphaned cross-references. This is a one-time migration.

4. **Minimal blast radius** — Don't change the EventRecord schema. Don't delete events. Only null out the `model_slug` field on records where it's wrong.

## 4. Primary User Stories

1. As a user viewing the Models page, I see only actual AI models — not programming languages, repositories, or feature names.

2. As a developer running collection, I know that new benchmark entries will be validated before their model_slug is stored.

3. As an analyst, cross-references between models are meaningful because garbage slugs no longer create spurious links.

## 5. Functional Requirements

### 5.1 Pipeline Validation

Add `validate_model_slug(slug: str) -> str | None` to `normalizer.py`. This function:
- Rejects known non-model patterns: programming language names, repository paths (contains `/`), aggregate labels, feature names
- Rejects slugs shorter than 2 characters or longer than 100
- Returns the slug if valid, None if rejected

Modify `process_item()` in `pipeline.py` line 71:
```python
# Before (trusts model_hint blindly):
model_slug = item.model_hint or extract_model_slug(combined_text)

# After (validates model_hint):
raw_hint = item.model_hint or extract_model_slug(combined_text)
model_slug = validate_model_slug(raw_hint) if raw_hint else None
```

### 5.2 Blocklist

A module-level set in `normalizer.py` of known non-model strings:

**Programming languages**: python, rust, go, java, javascript, typescript, c, c++, c/c++, ruby, php, swift, kotlin, scala, r, perl, lua, haskell, erlang, elixir, zig, nim, dart, objective-c

**Aggregate labels**: total, average, median, mean, overall, aggregate, combined, all, baseline, human, random

**Year/date labels**: patterns matching bare years (2019-2030) or date-like strings

**Feature/product terms**: free, pro, enterprise, preview, beta, alpha, standard, premium, basic

### 5.3 SWE-bench Multilingual Handling

In `swebench.py`, when the detected variant is `multilingual`:
- Set `model_hint=None` on generated RawItems (the language/repo is not a model)
- Store the language or repository name in the item's `metadata` dict as `benchmark_subject` for documentation purposes
- The entry still gets created as an EventRecord but with `model_slug=None`, keeping the benchmark data without polluting the model namespace

### 5.4 Data Cleanup Migration

A one-time cleanup script (run via `ai-benchmark cleanup-slugs` or a standalone script):
1. Query all EventRecords where `model_slug` matches the blocklist or fails validation
2. Set `model_slug = None` on those records
3. Delete CrossReferences where both endpoints now have `model_slug = None` (orphaned links between non-model entries)
4. Report counts of cleaned records

### 5.5 Verification

1. After cleanup: `list_tracked_models()` returns no programming languages, repos, or aggregate labels
2. After collection: new SWE-bench multilingual entries have `model_slug = None`
3. Existing valid models and their cross-references are untouched
4. Full test suite passes
