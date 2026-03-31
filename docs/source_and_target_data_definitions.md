# Source and Target Data Definitions

## 1. Source Data: What Each Source Provides

### 1.1 Primary Sources — Model Publishers (7)

#### OpenAI
| Page | URL | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|---|
| Product news | `openai.com/news/product-releases/` | title, url, body text | Author, publish date, category tags |
| API changelog | `platform.openai.com/docs/changelog` | title (via `extract_title`), body | Entry date, version number, affected APIs |
| Model catalog | `platform.openai.com/docs/models` | title, body | Context window, training cutoff, capabilities, deprecation date |
| Pricing | `openai.com/api/pricing/` | table cells (model name, price columns) | Effective date, regional pricing, volume discounts |
| System cards | `openai.com/index/system-cards/` | title, url, body | Document version, update date |
| Google News RSS | `news.google.com/rss/...site:openai.com` | title, url, pubDate, description | Full article text |

**Collection method:** HTML (browser=true for Cloudflare pages) + RSS fallback

#### Anthropic
| Page | URL | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|---|
| Newsroom | `anthropic.com/news` | article title, url, body | Publish date, author, category |
| System cards | `anthropic.com/system-cards` | card title, url, body | Version history, last modified date |
| API release notes | `docs.anthropic.com/en/release-notes/api` | section text via `extract_title`, body | Release date, version number, breaking changes |
| Models | `docs.anthropic.com/en/docs/about-claude/models` | table rows / section text, body | Parameter count, context window, training cutoff |
| Pricing | `docs.anthropic.com/en/docs/about-claude/pricing` | table rows (model, price columns) | Effective date, batch pricing, regional rates |
| Pricing page | `anthropic.com/pricing` | table rows | Tier descriptions |

**Collection method:** HTML

#### Google (Gemini API / DeepMind)
| Page | URL | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|---|
| API changelog | `ai.google.dev/gemini-api/docs/changelog` | section headings, body | Date, release channel (alpha/beta/stable) |
| Pricing | `ai.google.dev/pricing` | table rows | Regional variants, commitment discounts |
| Model docs | `ai.google.dev/gemini-api/docs/models/gemini` | table rows / sections | Release date, EOL date, context window |
| Blog | `blog.google/technology/google-deepmind/` | article title, url, body | Author, publish date, tags |
| Rate limits | `ai.google.dev/gemini-api/docs/rate-limits` | table rows | Quota reset cycles, burst limits |

**Collection method:** HTML

#### xAI
| Page | URL | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|---|
| Release notes | `docs.x.ai/docs/release-notes` | section headings, body | Version number, date |
| Models | `docs.x.ai/developers/models` | table rows / sections | Model size, context window |
| Rate limits | `docs.x.ai/developers/rate-limits` | table rows | Burst limits |
| News | `x.ai/news` | article title, url, body | Author, date, categories |
| Google News RSS | `news.google.com/rss/...site:x.ai` | title, url, pubDate, description | Full article text |

**Collection method:** HTML (browser=true for `x.ai/news`) + RSS fallback

#### Mistral AI
| Page | URL | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|---|
| Changelog | `docs.mistral.ai/getting-started/changelog` | **Next.js RSC payloads**: date, badge_type (model_release/api_update), model code slug, body | Release channel, breaking changes |
| News | `mistral.ai/news/` | **RSC JSON array**: slug, title, date, description, category | Full article text, featured image |
| Pricing | `mistral.ai/pricing` | Table cells (DOM fallback) | Effective date, volume discounts |
| Model pricing | `docs.mistral.ai/deployment/ai-studio/pricing` | Table cells | Commitment tiers |
| Model docs | `docs.mistral.ai/models` | **RSC h3 headings**: model name, description | Context window, deprecation status |
| Google News RSS | `news.google.com/rss/...site:mistral.ai` | title, url, pubDate, description | Full article text |

**Collection method:** HTML with Next.js RSC streaming parser + RSS

#### Cohere
| Page | URL | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|---|
| Changelog | `docs.cohere.com/changelog` | section headings, body | Date, version |
| Blog | `cohere.com/blog` | **Empty** (JS-rendered shell) | All content (requires browser) |
| Pricing | `cohere.com/pricing` | **Empty** (JS-rendered shell) | All pricing data |
| Model docs | `docs.cohere.com/docs/models` | table rows / sections | Model size, capabilities |
| Google News RSS | `news.google.com/rss/...site:cohere.com` | title, url, pubDate, description | Full article text |

**Collection method:** HTML (mostly empty due to JS rendering) + RSS as primary path

#### Meta (Open Source AI)
| Page | URL | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|---|
| GitHub orgs | GitHub API `/orgs/{org}/repos` | repo name, url, updated_at, description, stars, language | Fork count, contributors, README, topics |
| GitHub releases | GitHub API `/repos/{repo}/releases` | tag, name, url, published_at, body[:500] | Assets, pre-release status, commit SHA |
| Landing page | `ai.meta.com/opensourceAI/` | section text, body | Embedded media |
| Llama page | `llama.meta.com/` | section text, body | Model architecture details |
| Google News RSS | `news.google.com/rss/...site:ai.meta.com` | title, url, pubDate, description | Full article text |

**Collection method:** GitHub API + HTML + RSS

### 1.2 Secondary Sources — Benchmarks (7)

#### LMArena (Chatbot Arena)
| Page | URL Pattern | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|---|
| Main leaderboard | `arena.ai/leaderboard/` | **Table rows**: model name (col 1-2), Elo score (col 2-3), rank (col 0), org (span with · separator) | Confidence interval (±N), battle count, win/loss ratios, historical rankings |
| Variant pages | `arena.ai/leaderboard/{text,code,vision,...}` | Same structure, variant from URL path | Category-specific breakdowns |

**Variants detected:** `arena_elo`, `arena_elo_text`, `arena_elo_code`, `arena_elo_vision`, `arena_elo_text-to-image`, `arena_elo_text-to-video`, `arena_elo_search`, `arena_elo_document`

**Collection method:** HTML. Score extraction strips `±confidence` suffix.

#### Artificial Analysis
| Page | URL | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|---|
| Leaderboard | `artificialanalysis.ai/leaderboards/models` | Table rows: model (col 0), score (col 1), auto-rank | Score breakdown by category, confidence, test count |
| Embed leaderboard | `artificialanalysis.ai/embed/llm-performance-leaderboard` | Same | Same |
| Google News RSS | `news.google.com/rss/...` | title, url, pubDate, description | Full article |

**Collection method:** HTML + RSS. Variant = `performance`.

#### SWE-bench
| Page | Variant URL | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|---|
| Verified | `swebench.com/verified.html` | model (col 0), score (col 1), rank | Per-test scores, contamination flags |
| Lite | `swebench.com/lite.html` | Same | Same |
| Multilingual | `swebench.com/multilingual.html` | **language/repo** (col 0), score (col 1) — model_slug = NULL | Model-per-language breakdown |
| Multimodal | `swebench.com/multimodal.html` | model, score, rank | Same |

**Collection method:** HTML. Multilingual variant stores repo names, not model names.

#### GAIA, LiveBench, HLE (Scale AI), Terminal-Bench
| Source | Structure Extracted | Key Losses |
|---|---|---|
| GAIA | Table: model, score, rank. Org page: links to artifacts | Difficulty-level breakdown |
| LiveBench | Table: model, score, rank. PDF methodology | Task-level scores, time-locked results |
| HLE | **Multi-column**: each score column → separate variant (hle_text_only, hle_calibration, hle_public) | Confidence intervals, judge agreement |
| Terminal-Bench | Table: model, score, rank | Task-level command accuracy |

### 1.3 Secondary Sources — News (2)

#### Reuters
| Source | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|
| Google News RSS (site:reuters.com) | title (strip ` - Reuters` suffix), url, pubDate, description[:500] | Author, full article body, section/category, multimedia |

#### TechCrunch
| Source | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|
| WordPress RSS feed | title, url, pubDate, author (dc:creator), description[:500] | Full article body, tags/categories, multimedia, related articles |
| HTML fallback | article title, date, author, body[:500] | Same as above |

**RSS parsing has 3 fallback layers:** lxml-xml → lxml HTML → regex extraction

### 1.4 Research Sources (3)

#### arXiv
| Source | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|
| Recent lists (cs.AI, cs.CL, cs.LG) | title, arxiv_id, authors, url | Abstract, submission date, revision history, citation count, venue |

**Relevance filter:** keyword match on title+authors (benchmark, leaderboard, evaluation, language model, etc.)

#### Hugging Face Papers
| Source | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|
| Papers + trending | title, url, arxiv_id, upvotes | Abstract, publication date, author list, venue, citations |

#### Semantic Scholar (API)
| API Field | Extracted | Available but Not Extracted |
|---|---|---|
| title, url, abstract, authors, externalIds.ArXiv, paperId, citationCount | Yes | year, venue, references, citations graph, paper type |

**Rate limit:** 30s between queries without API key, 3s with key.

### 1.5 Discovery Sources (3)

#### HF Forums (Discourse API)
| Source | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|
| Topic list JSON | title, url, created_at, tags, reply_count, views, author | Full post content (intentionally not stored), user reputation |

**Support thread filter:** Regex excludes "help with install/setup" type posts.

#### GitHub Discovery
| Source | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|
| Org repos (7 orgs) | repo name, url, updated_at, description, stars, language | Fork count, contributors, README, topics, license |
| Repo releases | tag, name, url, published_at, body[:500] | Assets, pre-release flag, commit SHA |

**Watched orgs:** openai, anthropics, google-deepmind, meta-llama, mistralai, xai-org, cohere-ai

#### HF Leaderboard Docs
| Source | Structure Extracted | Fields Available but Not Extracted |
|---|---|---|
| Documentation index | Link title, url (matching /spaces, /leaderboard, /benchmark patterns) | Link context, destination page content, benchmark methodology |

**Meta-source:** Discovers links to community benchmarks, does not extract benchmark data itself.

## 2. Target Data: Database Tables

### 2.1 Core Intelligence Tables

**`sources`** (22 rows) — Source catalog

| Column | Type | Description |
|---|---|---|
| source_name | String(200) | Display name (e.g., "OpenAI") |
| category | String(100) | Category description |
| organization | String(200) | Organization key used throughout the system |
| homepage_url | String(500) | Base URL |
| base_domain | String(200) | Domain for URL matching |
| trust_rating | Float | 1.0–5.0 trust score |
| source_role | Text | Description of what this source provides |
| classification | String(50) | `primary`, `secondary`, `discovery-only` |
| collection_method | String(50) | `html`, `api`, `github_api` |

**`pages`** (86 rows) — Individual pages within sources

| Column | Type | Description |
|---|---|---|
| source_id | FK → sources | Parent source |
| canonical_url | String(500) | Page URL |
| page_type | String(100) | e.g., "leaderboard", "pricing", "api changelog" |
| polling_frequency | String(20) | e.g., "daily", "6h" |
| priority | Boolean | High-priority pages fetched first |
| times_polled | Integer | Fetch attempt count |
| consecutive_failures | Integer | Sequential failure count (circuit breaker) |

**`snapshots`** (649 rows) — Raw HTML captures

| Column | Type | Description |
|---|---|---|
| page_id | FK → pages | Which page |
| content_hash | String(64) | SHA-256 of content (change detection) |
| content | Text | Full HTML body |
| fetched_at | DateTime | When captured |

**`event_records`** (3,763 rows) — Normalized intelligence events

| Column | Type | Populated From | Notes |
|---|---|---|---|
| source_id | FK → sources | Source catalog lookup | |
| page_id | FK → pages | Page catalog lookup | |
| title | Text | `RawItem.title` | May be truncated by `extract_title()` |
| normalized_title | String(500) | Lowercased, whitespace-collapsed title | Used for deduplication |
| organization | String(200) | Source organization | The *reporting* org, not the model publisher |
| source_type | String(100) | Page type from catalog | e.g., "leaderboard", "pricing" |
| canonical_path | String(500) | `RawItem.url` | Item-specific URL |
| published_date | String(20), nullable | `extract_date()` on `RawItem.date_text` or body | **NULL on all LMArena (731) and Artificial Analysis (195) events** |
| event_type | String(50) | `classify_event_type()` on title+body | `model_release`, `pricing_change`, `api_update`, `deprecation`, `system_card`, `benchmark_result`, `announcement` |
| model_slug | String(200), nullable | `extract_model_slug()` or `RawItem.model_hint` | **NULL on 82% of events** |
| version | String(100), nullable | Not populated | Always NULL |
| benchmark_variant | String(100), nullable | `RawItem.metadata["benchmark_variant"]` | Set by benchmark collectors only |
| evaluation_conditions | Text, nullable | `RawItem.metadata["evaluation_conditions"]` | Benchmark conditions |
| observed_at | DateTime | `datetime.now(UTC)` at processing | When *we* processed it, not source date |
| raw_content | Text, nullable | `RawItem.body[:2000]` | For benchmarks: `"Rank: N, Score: NNNN, Variant: ..., Conditions: ..."` |

**`claim_records`** (28,749 rows) — Per-source assertions about events

| Column | Type | Populated From | Notes |
|---|---|---|---|
| event_id | FK → event_records | Parent event | |
| claim_text | Text | `RawItem.title` | For benchmarks: `"LMArena: model = score"` |
| source_type | String(100) | Page type | |
| source_name | String(200) | Organization name | |
| observed_at | DateTime | `datetime.now(UTC)` | |
| confidence_tier | String(50) | Source classification mapping | `official_self_report`, `benchmark_owner_report`, `high_secondary`, `medium_discovery`, `low_discovery` |
| confirmation_status | String(50) | Cross-check logic | `unconfirmed`, `confirmed`, `conflicted` |
| snapshot_id | FK → snapshots, nullable | Pricing claims only | Links to HTML evidence |

**`cross_references`** (333,706 rows) — Links between related events

| Column | Type | Description |
|---|---|---|
| record_a_id | FK → event_records | First event |
| record_b_id | FK → event_records | Second event |
| relationship_type | String(50) | `confirms`, `supplements`, `conflicts_with`, `cites` |

### 2.2 Research Pipeline Tables

**`candidate_papers`** (472 rows) — Discovered papers pending enrichment

| Column | Type | Description |
|---|---|---|
| title | Text | Paper title |
| arxiv_id | String(50), nullable | arXiv identifier |
| authors | Text, nullable | Author list |
| categories | String(200), nullable | Subject categories |
| status | String(20) | `pending`, `enriched`, `promoted`, `rejected` |
| retry_count | Integer | Enrichment attempt count |

**`enriched_papers`** (0 rows) — Papers that passed enrichment

| Column | Type | Description |
|---|---|---|
| candidate_id | Integer, nullable | Link to candidate |
| title, arxiv_id, authors, abstract, venue | Text fields | Full paper metadata |
| citation_count | Integer | Citation metric |
| relevance_tags | Text, nullable | AI-relevance tags |

### 2.3 Model Registry Tables (Derived)

**`model_entities`** (545 rows) — Curated model identities

| Column | Type | Description |
|---|---|---|
| canonical_slug | String(200), unique | Authoritative model identifier |
| display_name | String(300) | Human-readable name |
| publisher | String(200) | Organization that created the model |
| model_family | String(200), nullable | Grouping (not populated) |
| status | String(20) | `active`, `deprecated`, `announced` |
| description | Text, nullable | Not populated |
| parameter_count | String(50), nullable | Not populated |
| release_date | String(20), nullable | Earliest published_date from events |

**`model_entity_slugs`** (601 rows) — Maps raw event slugs to registry entities

| Column | Type | Description |
|---|---|---|
| entity_id | FK → model_entities | Parent entity |
| event_slug | String(200) | A model_slug value from event_records |
| source_org | String(200) | Which organization used this slug |

### 2.4 Publication Tables (Empty — not yet generated)

`publication_editions`, `publication_sections`, `publication_entries`, `publication_audit_log` — daily edition pipeline. See `docs/publication_pdr.md`.

### 2.5 Eval Pipeline Tables (Separate subsystem)

`datasets`, `dataset_versions`, `test_cases`, `scorers`, `scorer_versions`, `evaluation_definitions`, `evaluation_versions`, `machine_profiles`, `runner_profiles`, `target_configurations`, `runs`, `run_item_results`, `run_aggregate_metrics`, `artifacts` — model evaluation framework. Not part of the intelligence collection pipeline.
