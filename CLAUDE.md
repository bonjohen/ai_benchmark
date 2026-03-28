# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ai_benchmark** is an AI model and benchmark intelligence pipeline. It monitors official AI company sources, benchmark leaderboards, research feeds, and news outlets to track model releases, pricing changes, benchmark results, and research papers. The system produces a structured local knowledge base of verified AI industry events.

## Core Domain Concepts

- **Source catalog**: 22 monitored sources spanning official company pages (OpenAI, Anthropic, Google, xAI, Mistral, Cohere, Meta), benchmarks (Artificial Analysis, LMArena, LiveBench, SWE-bench, GAIA, HLE, Terminal-Bench), research feeds (arXiv, Semantic Scholar, HF Papers), and news (Reuters, TechCrunch, HF Forums, GitHub)
- **Source classifications**: primary (official vendor pages), secondary (independent benchmarks, reputable news), discovery-only (community forums, arXiv, trending feeds)
- **Trust tiers**: sources rated 1-5; official vendor pages are 5, community sources as low as 3
- **Event records**: normalized change records with source, title, path, observed timestamp, and extracted model/version names
- **Claim records**: separate records per source for conflicting claims, with source_type, confidence tier, and cross-references — never merge conflicting claims prematurely

## Verification Hierarchy

This ordering is load-bearing for the entire pipeline:

1. **Model releases**: vendor launch surface > developer docs/model catalog > pricing > changelog/release notes > system card. Confirmed when at least two official surfaces align on model name and availability.
2. **Benchmark claims**: always check the benchmark owner first, not the vendor. Record variant (e.g., SWE-bench Verified vs Lite vs Pro) and evaluation conditions.
3. **Pricing changes**: only confirmed when the official pricing page changes. Store HTML snapshot + observation timestamp.
4. **Company announcements**: company newsroom/press first, then docs/product page, then Reuters, then other outlets.
5. **Research claims**: primary paper (arXiv/publisher) first, then Semantic Scholar metadata, then company blog narrative. Blog alone never confirms a technical claim.

## Polling Cadences

| Source type | Frequency |
|---|---|
| Official changelogs/release notes | Every 6-12 hours |
| Official newsrooms | Daily |
| Pricing pages | Daily |
| Benchmark leaderboards | Daily (or 6-12h for frontier ranking) |
| Benchmark methodology | Weekly |
| Research feeds (arXiv, HF Papers) | Every 12-24 hours |
| Reuters | Every 3-6 hours |
| TechCrunch | Every 6-12 hours |
| Community sources (forums, GitHub chatter) | Daily |

## Deduplication Strategy

Composite key: `{normalized_title, organization, source_type, canonical_path_or_slug, published_date}`. For model events, also store `{model_slug, version_date}`. Maintain a cross-reference table linking related records across newsroom posts, changelogs, docs, GitHub releases, and benchmark notes — do not flatten into a single merged record.

## Key Design Constraints

- HTML diffing is the primary collection method for most sources; some sources support API access (Semantic Scholar, GitHub, Hugging Face)
- Research papers go through a triage pipeline (candidate queue > enrichment > authoritative store) — never auto-ingest arXiv preprints as authoritative
- Community sources ingest only minimal metadata by default (title, author, timestamp, tags, outbound links)
- Conflicts between sources are stored as separate claim records, not resolved automatically
- Low-value pages to skip: marketing landing pages without dates, localized doc duplicates, stale archived leaderboards, broken HF Spaces

## Requirements Document

All source details, page-level specifications, search strategies, and intake guidance live in `docs/core_requirements.md`.
