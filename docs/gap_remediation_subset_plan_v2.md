Number | Status | Started | Completed | Description
01 | Completed | 2026-03-28 19:48 | 2026-03-28 19:50 | Wire `execute_follow_up_tasks()` to real fetch execution: change the signature to accept `fetcher`, dispatch each follow-up task type to the correct page or constructed URL, run the result through the normal processing pipeline, and only mark the task completed after a real fetch and process succeeds.

02 | Completed | 2026-03-28 19:50 | 2026-03-28 19:52 | Standardize confidence-tier vocabulary by changing `processing/verification.py` so `"secondary"` maps to `"high_secondary"` instead of `"independent_report"`, then backfill or migrate any existing claim records that already use the wrong tier value. 

03 | Completed | 2026-03-28 19:52 | 2026-03-28 19:52 | Add `https://www.anthropic.com/pricing` to `config/sources.toml` as an Anthropic `pricing` page with `polling_frequency = "daily"` and `priority = true`. 

04 | Completed | 2026-03-28 19:52 | 2026-03-28 19:52 | Add `https://www.swebench.com/pro.html` to `config/sources.toml` as a SWE-bench `leaderboard` page with `polling_frequency = "daily"` and `priority = true`. 

05 | Completed | 2026-03-28 19:52 | 2026-03-28 19:52 | Add `https://docs.mistral.ai/deployment/ai-studio/pricing` to `config/sources.toml` as a Mistral AI `pricing` page with `polling_frequency = "daily"`. 

06 | Completed | 2026-03-28 19:52 | 2026-03-28 19:52 | Add `https://docs.x.ai/developers/rate-limits` to `config/sources.toml` as an xAI `rate limits` page with `polling_frequency = "daily"`. 

07 | Completed | 2026-03-28 19:52 | 2026-03-28 19:54 | Add `https://artificialanalysis.ai/embed/llm-performance-leaderboard` to `config/sources.toml` as an Artificial Analysis `leaderboard` page with `polling_frequency = "6h"` and `priority = true`. 

08 | Completed | 2026-03-28 19:54 | 2026-03-28 19:55 | Implement the `cites` relationship in `cross_reference.py` by detecting arXiv IDs in titles or content and returning `"cites"` when a referenced arXiv ID matches a known tracked event. 

09 | Completed | 2026-03-28 19:55 | 2026-03-28 19:56 | Implement the documented arXiv-ID cross-reference strategy in `build_cross_references()` by extracting arXiv IDs from `raw_content`, matching related events by those IDs, and creating cross-references with `relationship_type="cites"`. 

10 | Completed | 2026-03-28 19:56 | 2026-03-28 19:56 | Update `HLECollector.extract_leaderboard()` so it emits separate entries for distinct score slices such as `hle_public`, `hle_text_only`, and `hle_calibration` instead of hardcoding every row to `hle_public`. 

11 | Completed | 2026-03-28 19:56 | 2026-03-28 19:56 | Add LMArena image and vision leaderboard pages to `config/sources.toml` using the live tab URLs, with `polling_frequency = "6h"`. 

12 | Completed | 2026-03-28 19:56 | 2026-03-28 19:57 | Extend the GitHub source catalog to include benchmark-owner repositories and release pages for SWE-bench, LiveBench, GAIA, HLE or Scale, Terminal-Bench, Artificial Analysis, and LMArena, with at least `12h` polling on release pages. 

13 | Completed | 2026-03-28 19:57 | 2026-03-28 19:59 | Split Semantic Scholar handling into two roles by adding either dual classification support in the source catalog or source-tier overrides in `normalizer.py`, so metadata-confirmation output remains `high_secondary` while discovery output is recorded as `low_discovery`. 
