# Product Design Requirements: Daily AI Benchmark and News Publication

## 1. Purpose

This document defines the requirements for adding a daily publication feature to `ai_benchmark`. The feature will generate one structured daily edition that summarizes benchmark movement, model/vendor news, research developments, and notable AI industry events using the project’s existing collection, verification, analysis, API, and UI foundations. The design is intentionally additive: it extends the current intelligence pipeline into a publication product rather than introducing a second crawler or a parallel reporting system. The current repository already collects from 22 sources, stores normalized event and claim records, applies a five-chain verification hierarchy, runs scheduled collection jobs, and exposes analysis outputs through CLI and API surfaces. ([GitHub][1])

## 2. Product Summary

The new capability shall produce one daily “edition” object per publication date. Each edition shall be assembled from verified or high-confidence items already present in the database, ranked into editorial sections, rendered into human-readable and machine-readable outputs, and published through both API and UI surfaces. The existing system already supports analysis snapshots, digest generation, Markdown/JSON/CSV formatting, FastAPI analysis endpoints, and a Jinja-based UI stack in the eval subsystem, so the publication feature should reuse those patterns wherever practical. ([GitHub][1])

## 3. Background and Current-State Fit

`ai_benchmark` already has the core backend needed for a publication product. It stores `EventRecord`, `ClaimRecord`, and `CrossReference` entities, preserves separate claims from different sources, and verifies events differently by event type, including benchmark-owner requirements for benchmark claims, pricing-page requirements for pricing changes, and primary-paper requirements for research claims. It also maintains scheduled collection with APScheduler, source health tracking, and a circuit breaker, which makes it suitable for a fixed daily publication window. ([GitHub][1])

The repository also already includes an analysis layer that produces model lifecycle views, benchmark leaderboards, research trends, anomaly detection, and digests, with persistence support via `AnalysisSnapshot` and `AnalysisInsight`, plus REST endpoints such as `/benchmarks`, `/research`, `/insights`, and `/digest`. This means the publication feature should be built as an edition-assembly layer over existing stored intelligence, not as a new extraction system. ([GitHub][1])

## 4. Problem Statement

The current project can collect, verify, query, analyze, and export AI intelligence, but it does not yet produce a stable daily publication artifact that a human can read as a finished briefing. The gap is not data collection. The gap is editorial assembly, persistence of a daily edition, publication rendering, and light operator control over what appears in the finished daily issue.

## 5. Goals

1. Create one daily publication edition from existing verified or high-confidence intelligence.
2. Present benchmark movement, vendor/model announcements, research developments, and notable industry news in a concise editorial structure.
3. Preserve full traceability from every published entry back to supporting events, claims, and sources.
4. Support both public-facing reading and machine consumption through HTML, Markdown, and JSON outputs.
5. Fit naturally into the existing scheduler, analysis, API, and UI architecture.
6. Keep the daily edition mostly stable once published, with controlled regeneration only for important late-arriving items.

## 6. Non-Goals

1. Do not create a second crawler, separate source catalog, or independent ingestion pipeline.
2. Do not replace the existing analysis pipeline.
3. Do not require full manual editorial authorship of each edition.
4. Do not attempt real-time newsroom publishing in the first version.
5. Do not merge or rewrite canonical event/claim truth; the publication layer is a view over stored intelligence.

## 7. Primary Users

### 7.1 Reader

A user who wants one daily page showing the most important AI benchmark and news developments.

### 7.2 Research Operator

A user who wants to inspect why an item was included, see supporting evidence, and trace benchmark or news claims back to source records.

### 7.3 Maintainer

A user who wants to review, tune, freeze, or lightly override the generated edition before or after publication.

## 8. Core Use Cases

1. Generate today’s edition after daily collection and analysis complete.
2. Read a daily front page with top items grouped by section.
3. Open any entry and see the supporting event, claims, verification state, and source links.
4. Retrieve the edition through an API or export it as Markdown or JSON.
5. Suppress a noisy item, pin an important item, or freeze an edition after review.
6. Compare today’s benchmark movement and stories with recent prior editions.

## 9. Product Requirements

### 9.1 Daily Edition Creation

1. The system shall create exactly one primary edition per publication date.
2. The edition shall be generated from records already present in the database.
3. The edition shall include only items within a configurable publication window.
4. The default window shall be the previous 24 hours ending at a configurable daily cutoff time.
5. The edition shall support controlled regeneration before freeze.
6. Once frozen, the edition shall remain immutable except through an explicit administrative override.

### 9.2 Eligibility Rules

1. Published entries shall originate from canonical stored entities, not raw fetch output.
2. Items with `conflicted` verification status shall not appear in the default edition unless explicitly allowed by configuration or operator override.
3. Benchmark-result entries shall require the presence of a benchmark-owner-supported claim.
4. Pricing entries shall require the pricing verification path already used by the platform.
5. Research entries shall originate from promoted research entities or other verified research records, not from untriaged candidates.
6. Duplicate supporting claims shall strengthen ranking but shall not create duplicate entries in the edition.

These requirements align with the current verification model, which already differentiates model releases, benchmark claims, pricing changes, announcements, and research claims through separate confirmation rules. ([GitHub][1])

### 9.3 Editorial Ranking

1. The system shall rank candidate entries before section placement.
2. Ranking shall consider at minimum:

   1. verification status,
   2. confidence tier,
   3. source diversity,
   4. recency,
   5. event type,
   6. benchmark magnitude or significance,
   7. novelty,
   8. cross-reference density,
   9. anomaly or spotlight signals where available.
3. The ranking service shall favor verified items over unverified items.
4. The ranking service shall favor benchmark-owner and official-source evidence over secondary coverage.
5. The ranking service shall penalize low-signal page churn, trivial diffs, and repeated follow-up noise.
6. The ranking service shall expose its scoring breakdown for audit and UI inspection.

### 9.4 Required Edition Sections

Each edition shall support the following sections:

1. Top Summary
   A short overview of the most important developments of the day.

2. Benchmark Movers
   Significant benchmark leaderboard movement, new benchmark results, changed rankings, or notable capability deltas.

3. Model and Vendor Announcements
   New models, launches, major updates, deprecations, pricing changes, system cards, and material product announcements.

4. Research Pulse
   Notable newly promoted papers, benchmark-related research, or research clusters relevant to current AI capability discussion.

5. Industry News
   High-value secondary reporting that affects model access, partnerships, policy, infrastructure, major funding, or distribution.

6. Watchlist
   High-interest items that are promising but not yet strong enough for top placement.

The repo already has analysis services for benchmark trends, research pulse, anomaly detection, spotlight, evolution, capability, landscape, and digest generation. Those signals should be reused during assembly where they fit. ([GitHub][1])

### 9.5 Entry Structure

Every publication entry shall include:

1. a stable entry identifier,
2. headline,
3. short summary,
4. section assignment,
5. rank within section,
6. entry type,
7. organization or benchmark name,
8. model slug where applicable,
9. publication timestamp,
10. verification status,
11. confidence tier summary,
12. “why this matters” text,
13. supporting event references,
14. supporting claim count,
15. source link set,
16. related entry links,
17. editorial state flags such as pinned, suppressed, or overridden.

### 9.6 Output Formats

The system shall generate the same edition in all of the following formats:

1. HTML for human reading,
2. Markdown for archival and downstream content reuse,
3. JSON for API consumers and automation.

Markdown and JSON fit the project’s current formatter patterns, while HTML should follow the existing server/UI conventions already present in the repository. ([GitHub][1])

### 9.7 Web Experience

The publication UI shall include:

1. a daily landing page showing the latest edition,
2. an archive page listing prior editions,
3. per-edition detail pages,
4. anchor navigation by section,
5. expandable entry detail,
6. supporting-evidence links,
7. visual indicators for verification state and confidence,
8. filters for section, organization, benchmark, and verification state,
9. a lightweight admin/editor page for overrides and freeze actions.

The UI should reuse the current server stack patterns rather than introducing a separate front end. The repo already includes a Jinja2 UI framework in the eval subsystem with dashboard, entity, report, comparison, and search pages, which makes this a practical reuse path. ([GitHub][1])

### 9.8 API Requirements

New publication endpoints shall be added. Minimum required endpoints:

1. `GET /api/publications/latest`
2. `GET /api/publications/{date}`
3. `GET /api/publications`
4. `POST /api/publications/generate`
5. `POST /api/publications/{date}/freeze`
6. `POST /api/publications/{date}/regenerate`
7. `POST /api/publications/{date}/entries/{id}/pin`
8. `POST /api/publications/{date}/entries/{id}/suppress`
9. `POST /api/publications/{date}/entries/{id}/override`
10. `GET /api/publications/{date}/export?format=markdown|json|html`

These endpoints should follow the same API style used by the existing analysis and eval services, which already expose REST resources and persistence-oriented digest operations. ([GitHub][1])

### 9.9 Scheduler Integration

1. A new daily publication job shall be added to the scheduler.
2. The publication job shall execute only after collection and relevant analysis jobs are complete for the target window.
3. The publication job shall record start time, end time, success/failure, and generated edition metadata.
4. Publication failures shall not block the base collection pipeline.
5. Late high-confidence updates may trigger a regeneration-eligible state before freeze.
6. Publication health shall be visible alongside other scheduled work.

This requirement fits the current scheduler model, which already supports cron-based jobs, health tracking, and failure handling. ([GitHub][1])

### 9.10 Editorial Controls

The first version shall include lightweight operator controls:

1. pin entry,
2. suppress entry,
3. change headline,
4. change summary,
5. change section,
6. change rank,
7. mark as featured,
8. freeze edition,
9. regenerate before freeze,
10. restore generated version,
11. record operator and timestamp for every override.

### 9.11 Traceability and Audit

1. Every publication entry shall maintain links back to canonical event and claim records.
2. The UI shall expose supporting evidence on demand.
3. The system shall preserve generated text and overridden text separately.
4. Every editorial action shall be audit logged.
5. The API shall return enough metadata for consumers to distinguish generated content from operator-edited content.

### 9.12 Configuration

The system shall support configuration for:

1. publication cutoff time,
2. time zone,
3. maximum items per section,
4. minimum score threshold,
5. inclusion/exclusion of low-confidence items,
6. regeneration rules,
7. auto-freeze delay,
8. export paths,
9. archive retention policy,
10. whether HTML output is generated dynamically, statically, or both.

## 10. Data Model Requirements

A dedicated publication data model shall be added. Minimum entities:

### 10.1 PublicationEdition

Fields should include:

1. id,
2. publication_date,
3. window_start,
4. window_end,
5. generated_at,
6. published_at,
7. frozen_at,
8. status,
9. generation_version,
10. summary_text,
11. top_headlines_blob or equivalent structured summary,
12. metadata JSON.

### 10.2 PublicationSection

Fields should include:

1. id,
2. edition_id,
3. section_key,
4. title,
5. rank,
6. item_count,
7. generated_summary.

### 10.3 PublicationEntry

Fields should include:

1. id,
2. edition_id,
3. section_id,
4. rank,
5. entry_type,
6. title_generated,
7. title_final,
8. summary_generated,
9. summary_final,
10. why_it_matters_generated,
11. why_it_matters_final,
12. status,
13. score,
14. score_explanation JSON,
15. event_id nullable,
16. paper_id nullable,
17. benchmark_name nullable,
18. org_slug nullable,
19. model_slug nullable,
20. verification_status,
21. confidence_summary,
22. source_count,
23. is_pinned,
24. is_suppressed,
25. is_overridden,
26. related_entry_ids JSON,
27. created_at,
28. updated_at.

### 10.4 PublicationAuditLog

Fields should include:

1. id,
2. edition_id,
3. entry_id nullable,
4. action_type,
5. actor,
6. before_state JSON,
7. after_state JSON,
8. created_at.

The current repository already uses normalized ORM models and persistent analysis tables, so adding a small publication schema is consistent with the existing design style. ([GitHub][1])

## 11. Processing Workflow Requirements

### 11.1 Candidate Assembly

1. Load eligible events, claims, promoted research items, and cached analysis signals for the target window.
2. Compute candidate publication items.
3. Collapse duplicate candidate representations into one publication candidate per story/result.
4. Attach benchmark deltas, research metadata, and cross-reference context where available.

### 11.2 Scoring

1. Score all candidates.
2. Persist score and score explanation.
3. Allow deterministic rerun from the same input window and configuration.

### 11.3 Sectioning

1. Assign each candidate to one primary section.
2. Resolve ties deterministically.
3. Cap section sizes by configuration.
4. Move overflow items to Watchlist or omit them.

### 11.4 Rendering

1. Generate edition summary text.
2. Generate section summaries.
3. Render final entry text.
4. Render HTML, Markdown, and JSON outputs from the same persisted edition data.

### 11.5 Publication

1. Save the edition.
2. Expose it through API.
3. Make it visible in the UI.
4. Export static artifacts where configured.
5. Mark the edition as published.

## 12. Quality Requirements

1. The same input window and configuration shall produce the same ranked edition unless operator overrides are applied.
2. The edition shall not include duplicate visible entries for the same event cluster.
3. Published entries shall always expose supporting evidence.
4. Edition generation shall degrade gracefully if one optional analysis service is unavailable.
5. The publication feature shall not degrade base collection reliability.

## 13. Acceptance Criteria

### 13.1 Functional Acceptance

1. A maintainer can run the system and generate a daily edition for a chosen date.
2. The edition appears in the UI as a readable daily briefing with required sections.
3. The same edition is retrievable through API and exportable as Markdown and JSON.
4. Each visible entry links to supporting evidence.
5. An operator can pin, suppress, override, regenerate, and freeze entries or editions.
6. A frozen edition remains stable across subsequent scheduler runs.

### 13.2 Visible Behavior Acceptance

1. Running the publication generation path produces a user-viewable daily publication page.
2. The page clearly displays benchmark movers, model/vendor announcements, research pulse, and industry news when qualifying items exist.
3. Clicking a publication entry reveals or navigates to supporting evidence and verification details.
4. The latest edition page updates automatically after a successful scheduled publication run.
5. The archive page shows prior editions in date order and opens each edition correctly.

### 13.3 Technical Acceptance

1. Publication generation completes against a representative populated database without breaking existing collection or analysis commands.
2. New API endpoints return valid payloads and appropriate status codes.
3. Markdown, HTML, and JSON renderers all produce output from the same persisted edition.
4. Audit records are created for all editorial overrides and freeze actions.
5. Automated tests cover generation, ranking, rendering, API access, override behavior, freeze behavior, and archive retrieval.

## 14. Delivery Plan

### Phase 1: Edition Core

Add schema, candidate assembly, ranking, and persistence.

### Phase 2: Render and Read

Add HTML, Markdown, and JSON renderers, latest-edition page, edition detail page, and archive page.

### Phase 3: Automate

Add scheduler integration, publication job health, and static export support.

### Phase 4: Editorial Controls

Add pin/suppress/override/freeze functions, admin UI, and audit logging.

### Phase 5: Refinement

Tune scoring, section balance, visual presentation, and comparative/archive features.

## 15. Design Guidance for Implementation

1. Reuse current event, claim, cross-reference, research, and analysis tables as input sources.
2. Reuse existing formatter and API conventions where possible.
3. Reuse existing server/UI conventions rather than creating a disconnected publication front end.
4. Keep publication logic isolated in a new module such as `ai_benchmark/publication/` to avoid polluting collection or analysis layers.
5. Treat the publication system as a consumer of canonical intelligence, not as a producer of new truth.

## 16. Recommended Module Layout

A reasonable implementation layout would be:

1. `ai_benchmark/publication/models.py`
2. `ai_benchmark/publication/types.py`
3. `ai_benchmark/publication/services/assembly.py`
4. `ai_benchmark/publication/services/scoring.py`
5. `ai_benchmark/publication/services/sectioning.py`
6. `ai_benchmark/publication/services/render.py`
7. `ai_benchmark/publication/services/editorial.py`
8. `ai_benchmark/publication/api.py`
9. `ai_benchmark/publication/cli.py`
10. `ai_benchmark/publication/formatters/`
11. `ai_benchmark/publication/ui/templates/`

## 17. Final Product Decision

This feature shall be implemented as a publication layer built on the repository’s existing intelligence pipeline. The repository already has normalized storage, event/claim verification, scheduled collection, analysis services, persisted analysis artifacts, REST endpoints, and a Jinja-capable UI foundation. The required addition is a durable daily edition concept plus ranking, rendering, editorial control, and publication workflow. ([GitHub][1])

[1]: https://github.com/bonjohen/ai_benchmark "GitHub - bonjohen/ai_benchmark · GitHub"
