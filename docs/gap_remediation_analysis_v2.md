# Gap Remediation Analysis v2

**Scope**: Compare `docs/archive/core_requirements.md` against the current implementation as of 2026-03-28.

**Status**: All 13 identified gaps remediated on 2026-03-28. See `docs/gap_remediation_subset_plan_v2.md` for the task-by-task record.

The requirements document describes 22 sources, 20 priority pages, 5 verification chains, a discovery loop, and intake cadences. This document records every deviation found, ranked by severity.

---

## Critical Gaps

These gaps mean a requirement is stated but the code is a stub or the behavior is provably wrong.

### C-1: Discovery follow-up tasks are never executed

**Requirement (Section 4):** "Whenever a new model slug appears, immediately queue follow-up searches for pricing, release notes, system card/model card, and benchmark coverage."

**Implementation:** `processing/discovery_queue.py` correctly enqueues four `FollowUpTask` records per new slug (`pricing_search`, `release_notes_search`, `system_card_search`, `benchmark_coverage_search`). However, `execute_follow_up_tasks()` contains an explicit stub comment:

> "For now, marks tasks as completed. Full search integration requires the scheduling layer to dispatch actual page fetches."

The function increments `status = "completed"` for each pending task without dispatching any real fetch. Follow-up coverage is tracked in the DB but never fulfilled.

**Impact:** New model slugs do not trigger pricing/system-card/benchmark pages to be fetched. The discovery loop is broken end-to-end.

---

### C-2: Confidence tier vocabulary inconsistency

**Requirement (Section 3):** Five named tiers: `official_self_report`, `benchmark_owner_report`, `high_secondary`, `medium_discovery`, `low_discovery`. Specifically: "if a vendor announcement claims top benchmark performance but the benchmark-owner leaderboard shows different conditions, keep both records and mark the vendor claim as 'official self-report' and the leaderboard claim as 'benchmark-owner report'."

**Implementation mismatch:** `processing/verification.py` (`CLAIM_LABELS`) maps `"secondary"` → `"independent_report"`. This value does not appear in the required vocabulary. `processing/normalizer.py` (`CONFIDENCE_TIERS`) correctly maps `"secondary"` → `"high_secondary"`. The two modules disagree.

`CLAIM_LABELS` in `verification.py`:
```python
"secondary": "independent_report",  # should be "high_secondary"
```

`CONFIDENCE_TIERS` in `normalizer.py`:
```python
"secondary": "high_secondary",      # correct
```

**Impact:** Claims created through `verification.create_claim()` receive a non-standard tier string. Downstream filtering, reporting, and the CLAUDE.md documentation all use the five-tier vocabulary. Any query filtering on `confidence_tier = 'high_secondary'` will miss claims that were written as `'independent_report'`.

---

## Significant Gaps

These gaps are missing source pages or page variants that the requirements explicitly call out as important.

### S-1: Anthropic main pricing page not monitored

**Requirement (Section 3):** "Anthropic's docs explicitly tell users to check Anthropic's main pricing page for the most current prices, which is a useful reminder that older docs can lag. Store both the detected HTML snapshot and the timestamp of observation."

**Implementation:** `config/sources.toml` monitors `docs.anthropic.com/en/docs/about-claude/pricing` (the docs page), but not `www.anthropic.com/pricing` (the main page). The requirements explicitly flag the docs page as a lagging source.

**Remediation:** Add `https://www.anthropic.com/pricing` as a `pricing` page under the Anthropic source with `polling_frequency = "daily"` and `priority = true`.

---

### S-2: SWE-bench Pro variant page not configured

**Requirement (Section 3):** "For SWE-bench specifically, record whether the claim refers to Verified, Lite, Full, Pro, or another variant, because the public subsets differ and frontier contamination is now a documented concern." The requirements also note that "OpenAI's February 2026 analysis argues that SWE-bench Verified is now increasingly contaminated for frontier models and recommends SWE-bench Pro instead."

**Implementation:** `SWEBENCH_VARIANTS` in `sources/benchmarks/swebench.py` includes `"pro"` in the detection set, so the collector is ready to handle it. However, no page with a `/pro` URL is configured in `sources.toml`. The variant detection will never fire because the Pro URL is never fetched.

**Remediation:** Add `https://www.swebench.com/pro.html` as a leaderboard page under SWE-bench with `polling_frequency = "daily"` and `priority = true`.

---

### S-3: Mistral AI Studio pricing page missing

**Requirement (Section 1, source #5):** Relevant sections include `docs.mistral.ai/deployment/ai-studio/pricing`.

**Implementation:** `sources.toml` covers `docs.mistral.ai/getting-started/changelog`, `mistral.ai/news/`, and `mistral.ai/pricing`, but not the AI Studio pricing page. The AI Studio endpoint has different pricing from the API and warrants separate monitoring.

**Remediation:** Add `https://docs.mistral.ai/deployment/ai-studio/pricing` as a `pricing` page under Mistral AI with `polling_frequency = "daily"`.

---

### S-4: xAI rate limits page not configured

**Requirement (Section 1, source #4):** Relevant sections include `docs.x.ai/developers/rate-limits`.

**Implementation:** `sources.toml` covers `docs.x.ai/docs/release-notes` and `docs.x.ai/developers/models` but not the rate-limits page. Google's equivalent (`ai.google.dev/gemini-api/docs/rate-limits`) is correctly configured; xAI's is missing.

**Remediation:** Add `https://docs.x.ai/developers/rate-limits` as a `rate limits` page under xAI with `polling_frequency = "daily"`.

---

### S-5: Artificial Analysis embedded performance leaderboard not configured

**Requirement (Section 2, page #11):** Priority page `https://artificialanalysis.ai/embed/llm-performance-leaderboard` for operational model-selection comparisons (price + latency + speed).

**Implementation:** `sources.toml` has the main models leaderboard (`artificialanalysis.ai/leaderboards/models`) and an arena methodology page (`artificialanalysis.ai/text/arena?tab=Ranking`). The embedded performance leaderboard — which blends benchmark score with operational metadata — is absent. This is the page the requirements describe as "especially useful when deciding what to run, not just what is 'smartest.'"

**Remediation:** Add `https://artificialanalysis.ai/embed/llm-performance-leaderboard` as a `leaderboard` page under Artificial Analysis with `polling_frequency = "6h"` and `priority = true`.

---

## Minor / Design Gaps

These gaps are partially implemented features, missing sub-variants, or design oversights that do not completely break requirements but reduce completeness.

### M-1: "cites" cross-reference relationship never produced

**Requirement (implied by design):** `cross_reference.py` module docstring lists four relationship types: `confirms`, `supplements`, `conflicts_with`, `cites` — where `cites` is for "research papers cited across sources."

**Implementation:** `determine_relationship()` returns only `confirms`, `supplements`, or `conflicts_with`. The `cites` branch is declared but never returned. Research papers discovered via arXiv/Semantic Scholar that cite other tracked events will never have `cites` cross-references created.

**Remediation:** Add logic to detect arXiv ID presence in event titles/content (pattern `\barXiv:\d{4}\.\d{4,5}\b`) and return `"cites"` when the referenced arXiv ID matches a known event.

---

### M-2: arXiv ID cross-reference strategy not implemented

**Requirement (cross_reference.py docstring):** "arxiv_id (research papers cited across sources)" is listed as matching strategy #3.

**Implementation:** `build_cross_references()` applies two strategies — model slug time-window and org+event-type. The arXiv ID strategy is documented but has no implementation. No code extracts arXiv IDs from events or uses them for cross-reference matching.

**Remediation:** Implement strategy 3 in `build_cross_references()`: extract arXiv IDs from both events' `raw_content`, query for events with matching IDs, and call `create_cross_reference()` with `relationship_type="cites"`.

---

### M-3: HLE collector tracks only one accuracy slice

**Requirement (Section 3):** "For Humanity's Last Exam, record whether the claim is public-question accuracy, text-only accuracy, or another slice, and note that HLE uses automatic judging and confidence intervals."

**Implementation:** `sources/benchmarks/hle.py` hardcodes `variant="hle_public"` for every row. The text-only accuracy slice and any calibration slice are not distinguished. The HLE leaderboard page exposes different accuracy columns (overall, text-only, with-tools) that are all collapsed into a single variant label.

**Remediation:** In `HLECollector.extract_leaderboard()`, detect column headers or separate score columns and emit separate `LeaderboardEntry` records per slice with distinct variant values (`hle_public`, `hle_text_only`, `hle_calibration`).

---

### M-4: LMArena image and vision leaderboard pages not configured

**Requirement (Section 1, source #9):** "arena-style preference data captures user-facing quality in ways static benchmarks often miss, and the current overview exposes sub-rankings such as expert, hard prompts, coding, math, and longer query" plus image and vision categories.

**Implementation:** `sources.toml` covers `/leaderboard/`, `/leaderboard/expert`, `/leaderboard/hard-prompts`, `/leaderboard/coding`, `/leaderboard/math`, `/leaderboard/longer-query` — all text categories. Image and vision leaderboard tabs are not configured.

**Remediation:** Add `https://lmarena.ai/leaderboard/image` and `https://lmarena.ai/leaderboard/vision` (or equivalent tab URLs once confirmed live) with `polling_frequency = "6h"`.

---

### M-5: Benchmark repository GitHub coverage absent

**Requirement (Section 4):** "To discover new benchmark projects, watch three places continuously: benchmark hubs, arXiv, and community-amplified paper feeds. Scale's benchmark hub, Terminal-Bench's registry, GAIA's organization page, and Artificial Analysis methodology pages expose named benchmarks directly."

**Implementation:** `sources.toml` GitHub source covers vendor orgs (`openai`, `anthropics`, `google`, `mistralai`, `xai-org`, `cohere-ai`) but not benchmark-owner repos (`swebench`, `LiveBench-AI`, `huggingface/gaia-benchmark`, `terminal-bench`, `ScaleAI`). New benchmark releases from these repos are not discovered via GitHub.

**Remediation:** Add GitHub org/repo pages for the seven benchmark sources already in the catalog: SWE-bench, LiveBench, GAIA, HLE (Scale), Terminal-Bench, Artificial Analysis, LMArena. At minimum, poll their release pages at `12h` cadence.

---

### M-6: Semantic Scholar dual classification not modeled

**Requirement (Section 1, source #18):** "classification: secondary for metadata, discovery for new papers."

**Implementation:** `sources.toml` assigns `classification = "secondary"` to Semantic Scholar, which sets `confidence_tier = "high_secondary"` for all its output. But Semantic Scholar is also used as a discovery source (new papers enriched from arXiv candidates), and the confidence tier for its discovery output should be `low_discovery` rather than `high_secondary`.

**Remediation:** Either (a) add a dual-role `classification` field to the source catalog or (b) add a `SOURCE_TIER_OVERRIDE` in `normalizer.py` that maps `("Semantic Scholar", "api_endpoint")` to `"high_secondary"` and a second override for `("Semantic Scholar", "paper_discovery")` to `"low_discovery"`. Option (b) is consistent with the existing override pattern.

---

### M-7: execute_follow_up_tasks not connected to fetcher

**This is a sub-gap of C-1, listed separately as a design note.** The `FollowUpTask` model and enqueue logic are correct and complete. The gap is only in execution — the scheduler calls `execute_follow_up_tasks()` but the function does not accept a `Fetcher` instance. Wiring would require: (1) `execute_follow_up_tasks(session, fetcher)` signature, (2) per-task-type dispatch to the relevant page from the org's page list or constructed URL, and (3) routing the result through the standard `process_item()` pipeline.

---

## Non-Gaps (Verified Correct)

For completeness, these requirements items were checked and confirmed implemented:

| Requirement | Status |
|---|---|
| All 22 sources registered | ✅ All 22 in sources.toml and registry.py |
| 5 verification chains | ✅ VERIFICATION_CHAINS in verification.py |
| 3-layer deduplication | ✅ exact key → model slug → fuzzy in deduplicator.py |
| Composite key includes model_slug | ✅ UniqueConstraint in EventRecord |
| Separate ClaimRecords per source | ✅ create_claim() never merges |
| claim_text, source_type, source_name, page_title, observed_at, confidence_tier on ClaimRecord | ✅ All fields present in models/events.py |
| HTML snapshot + timestamp for pricing changes | ✅ ClaimRecord.snapshot_id FK to Snapshot |
| benchmark_variant and evaluation_conditions on EventRecord | ✅ Both columns present |
| SWE-bench variant detection (Verified/Lite/Full/Multilingual/Multimodal) | ✅ SWEBENCH_VARIANTS + URL detection |
| HLE: conditions note automatic judging + confidence intervals | ✅ conditions string in HLECollector |
| Research triage pipeline (candidate → enrichment → promote/reject) | ✅ processing/triage.py |
| Community sources ingest minimal metadata only | ✅ HFForumsCollector, body="" |
| Support thread filtering for HF Forums | ✅ SUPPORT_THREAD_PATTERNS |
| Path prober covers all 11 required path families | ✅ PATH_FAMILIES in path_prober.py |
| Cross-reference table (not merged records) | ✅ CrossReference model + build_cross_references() |
| Conflict detection → conflicted status | ✅ detect_claim_conflict() + update_confirmation_status() |
| Discovery queue enqueue on new slug | ✅ check_and_enqueue() in discovery_queue.py |
| 4 follow-up task types per new slug | ✅ FOLLOW_UP_TASK_TYPES |
| Reuters 3h cadence | ✅ schedules.toml: `0 */3 * * *` |
| arXiv 12h cadence | ✅ schedules.toml: `0 6,18 * * *` |
| Official changelogs 6h cadence | ✅ OpenAI/Anthropic/Google on `0 */6 * * *` |
| Benchmark leaderboards daily | ✅ LiveBench/SWE-bench/GAIA/HLE/Terminal-Bench |
| Gemini rate-limits page configured | ✅ ai.google.dev/gemini-api/docs/rate-limits |
| OpenAI system-card index configured | ✅ openai.com/index/system-cards/ |
| Anthropic system-card index configured | ✅ www.anthropic.com/system-cards |
| arXiv cs.AI, cs.CL, cs.LG all three categories | ✅ All three in sources.toml |
| SOURCE_TIER_OVERRIDES for Reuters/TechCrunch | ✅ In normalizer.py |

---

## Summary Table

| ID | Severity | Description |
|---|---|---|
| C-1 | Critical | Discovery follow-up tasks are stub — no real fetches dispatched |
| C-2 | Critical | `verification.py` uses `"independent_report"` not `"high_secondary"` |
| S-1 | Significant | `anthropic.com/pricing` (main page) not monitored — only docs page |
| S-2 | Significant | SWE-bench Pro page not in sources.toml |
| S-3 | Significant | Mistral AI Studio pricing page missing |
| S-4 | Significant | xAI rate-limits page missing |
| S-5 | Significant | Artificial Analysis embedded leaderboard page missing |
| M-1 | Minor | `"cites"` relationship type declared but never returned |
| M-2 | Minor | arXiv ID cross-reference strategy documented but not implemented |
| M-3 | Minor | HLE text-only and calibration accuracy slices not tracked |
| M-4 | Minor | LMArena image/vision leaderboard tabs not configured |
| M-5 | Minor | Benchmark owner GitHub repos not in GitHub source |
| M-6 | Minor | Semantic Scholar confidence tier not split by use (metadata vs. discovery) |
| M-7 | Minor | (Sub-gap of C-1) follow-up task executor not wired to Fetcher |
