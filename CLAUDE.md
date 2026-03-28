# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ai_benchmark** is an AI model and benchmark intelligence pipeline. It monitors official AI company sources, benchmark leaderboards, research feeds, and news outlets to track model releases, pricing changes, benchmark results, and research papers. The system produces a structured local knowledge base of verified AI industry events.

## Build and Test

```bash
pip install -e ".[dev]"          # Install with dev dependencies
pip install -e ".[dev,research]" # Include research extras (S2, PDF)
pytest                           # Run all 163 tests
pytest tests/test_config.py      # Single file
pytest -x -v                     # Verbose, stop on first failure
ai-benchmark init-db             # Create database
ai-benchmark check-config        # Validate config
ai-benchmark collect --source OpenAI  # Test single source collection
ai-benchmark run                 # Start daemon mode
```

## Core Domain Concepts

- **Source catalog**: 22 monitored sources across 5 categories — 21 polled collectors + Semantic Scholar enrichment client
- **Source classifications**: primary (official vendor pages), secondary (independent benchmarks, reputable news), discovery-only (community forums, arXiv, trending feeds)
- **Trust tiers**: sources rated 1-5; official vendor pages are 5, community sources as low as 3
- **Event records**: normalized change records with source, title, path, observed timestamp, and extracted model/version names
- **Claim records**: separate records per source for conflicting claims, with source_type, confidence tier, and cross-references — never merge conflicting claims prematurely
- **Confidence tiers**: official_self_report (primary), high_secondary (Reuters), medium_discovery (TechCrunch), low_discovery (forums, GitHub)

## Verification Hierarchy

This ordering is load-bearing for the entire pipeline:

1. **Model releases**: vendor launch surface > developer docs/model catalog > pricing > changelog/release notes > system card. Confirmed when at least two official surfaces align on model name and availability.
2. **Benchmark claims**: always check the benchmark owner first, not the vendor. Record variant (e.g., SWE-bench Verified vs Lite vs Pro) and evaluation conditions.
3. **Pricing changes**: only confirmed when the official pricing page changes. Store HTML snapshot + observation timestamp.
4. **Company announcements**: company newsroom/press first, then docs/product page, then Reuters, then other outlets.
5. **Research claims**: primary paper (arXiv/publisher) first, then Semantic Scholar metadata, then company blog narrative. Blog alone never confirms a technical claim.

## Processing Pipeline

Each collected item goes through: normalize → deduplicate → create event → create claim → update confirmation status → build cross-references. Duplicates from different sources still create claims on the existing event, enabling multi-source confirmation.

## Key Patterns

- **SourceCollector**: Abstract base in `sources/base.py`. Subclass and implement `extract_items(html, page)`. Register in `sources/registry.py`.
- **BenchmarkCollector**: Extended base in `sources/benchmarks/__init__.py` with `extract_leaderboard()` returning `LeaderboardEntry` objects. Auto-converts to `RawItem`.
- **Registry**: `COLLECTOR_CLASSES` dict in `sources/registry.py` maps org names to classes. `get_collector(source_config)` is the factory.
- **Processing pipeline**: `processing/pipeline.py` — `process_item()` / `process_items()` run the full normalize→dedup→verify→xref chain.
- **Async throughout**: SQLAlchemy async sessions, httpx async client, APScheduler AsyncIOScheduler.

## Polling Cadences

Defined in `config/schedules.toml`. Vendors every 6-12h, Reuters every 3h, benchmarks daily, research every 12h, community daily.

## Deduplication Strategy

Three-layer: (1) exact composite key `{normalized_title, org, source_type, path, date}`, (2) model slug + org + date, (3) fuzzy title match (0.85 threshold via SequenceMatcher). Cross-reference table links related records — do not flatten into a merged record.

## Key Design Constraints

- HTML diffing is the primary collection method; some sources use API access (Semantic Scholar, GitHub, Hugging Face)
- Research papers go through a triage pipeline (candidate → enrichment → authoritative store) — never auto-ingest
- Community sources ingest only minimal metadata (title, author, timestamp, tags, outbound links)
- Conflicts between sources are stored as separate claim records, not resolved automatically

## Requirements Documents

- Source details and intake guidance: `docs/core_requirements.md`
- Implementation plan (all phases complete): `docs/core_requirements_plan.md`
- Model eval pipeline design: `docs/model_eval_pipeline_design.md`
- Model eval pipeline PDR: `docs/model_eval_pipeline_pdr.md`
- Model eval pipeline plan: `docs/model_eval_pipeline_plan.md`
