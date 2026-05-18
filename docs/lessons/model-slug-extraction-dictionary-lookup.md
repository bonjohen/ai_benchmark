# Model Slug Extraction: Dictionary Lookup Over Pure Regex

## The Lesson

When extracting structured identifiers (model names, product versions, package names) from unstructured text, a dictionary of known values with normalization beats regex-only extraction. Regex handles the general case; the dictionary handles the important cases correctly.

## Context

A data pipeline extracts model slugs (e.g., "claude-3-opus", "gpt-4o") from event titles and page content to link events to specific AI models. The initial implementation used regex patterns to match model name patterns — sequences of letters, digits, and hyphens that look like model identifiers. This worked for well-formatted titles but failed on real-world text where model names appear in unexpected formats.

## What Happened

1. Regex-only extraction worked for clean titles like "Announcing GPT-4o" but failed on CamelCase concatenations like "launchedClaude3.5Sonnet" (common in JavaScript-rendered pages where whitespace is stripped).
2. A `_repair_whitespace()` function was added to insert spaces at CamelCase boundaries before regex matching. This fixed concatenated names but introduced false positives on non-model CamelCase words.
3. A dictionary of ~50 known model names was built (`_KNOWN_MODEL_NAMES`), mapping display names to canonical slugs. The extraction pipeline tries the dictionary first, with normalization (lowercasing, collapsing hyphens/underscores/spaces), then falls back to regex on whitespace-repaired text.
4. A `backfill-slugs` CLI command was added to scan existing events with NULL slugs and apply the improved extraction retroactively.
5. The dictionary approach correctly handled 22 test cases covering whitespace repair, dictionary matching, regex fallback, HTML concatenation, and multi-model titles.

## Key Insights

- **Known-value dictionaries eliminate ambiguity for important cases.** The dictionary doesn't need to handle every possible model name — it needs to handle the ones that matter (high-profile models that appear frequently in events). New models can be added as they're discovered.
- **Normalization should happen before matching, not in the regex.** Lowercasing, collapsing separators, and repairing whitespace as preprocessing steps keep the matching logic simple. Trying to handle all variations in regex patterns makes them unreadable and fragile.
- **Backfill is a first-class operation.** When extraction logic improves, existing data with NULL or incorrect slugs needs to be updated. Planning for backfill from the start (a CLI command, not a one-off script) means the improvement actually reaches historical data.
- **CamelCase boundaries are a reliable whitespace signal.** The transition from lowercase to uppercase (`modelClaude` → `model Claude`) is a strong signal for missing whitespace in concatenated text. This heuristic generalizes beyond model names to any entity extraction from poorly formatted web content.

## Examples

**Regex-only (before):**
- Input: `"launchedClaude3.5Sonnet"` → No match (no separator between "launched" and "Claude")
- Input: `"GPT_4o"` → Partial match, wrong slug

**Dictionary + normalization (after):**
- Input: `"launchedClaude3.5Sonnet"` → whitespace repair → `"launched Claude 3.5 Sonnet"` → dictionary match → `"claude-3.5-sonnet"`
- Input: `"GPT_4o"` → normalize → `"gpt4o"` → dictionary match → `"gpt-4o"`

## Applicability

Applies to any entity extraction task where there's a known universe of high-value entities: product names, package identifiers, API versions, stock tickers. Does NOT apply when the entity space is open-ended (e.g., extracting arbitrary person names) — there the dictionary can't cover enough ground to be useful.
