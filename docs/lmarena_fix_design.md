# LMArena Collector Fix — Design Document

## 1. Purpose

The LMArena collector (`ai_benchmark/sources/benchmarks/lmarena.py`) produces garbage data because it reads the wrong HTML table columns and mangles model names. All 441 existing LMArena event records contain incorrect model slugs, missing Elo scores, and broken titles. This document specifies the root causes and the correct parsing approach.

## 2. Scope

- Fix the `LMArenaCollector.extract_leaderboard()` method to correctly parse the arena.ai HTML table structure
- Clean up all existing bad LMArena data (events, claims, cross-references)
- Update the source catalog domain from `lmarena.ai` to `arena.ai`
- Add unit tests with HTML fixtures for both table layouts

## 3. Root Cause Analysis

### 3.1 Column Index Mismatch

The collector assumes `cells[0]` is model name and `cells[1]` is score. The actual table structure is:

**Sub-pages** (7 columns): Rank | Rank Spread | Model | Score | Votes | Price | Context
**Main page** (4 columns per mini-table): Rank | Model | Score | Votes

So `cells[0]` is always Rank (an integer), which ends up as the "model name."

### 3.2 Model Name Mangling

The Model cell contains complex nested DOM with an SVG org icon, a link with the model name, and a secondary span with "Org - License." Calling `get_text(strip=True)` on the whole `<td>` concatenates all text nodes: `"Anthropicclaude-opus-4-6-thinkingAnthropic - Proprietary"`.

The clean model name lives in `<a><span class="max-w-full truncate">claude-opus-4-6-thinking</span></a>`.

### 3.3 No Elo Score Captured

Since `cells[1]` is Rank Spread (not Score), and Rank Spread is a small integer (e.g., 14), the "Elo scores" in the database are actually rank spread values. The real Elo score is in column 3 (sub-pages) or column 2 (main page).

### 3.4 Single Hardcoded Variant

All entries use `variant="arena_elo"` regardless of which page they came from. The 8 configured pages cover different categories (text, code, vision, etc.) that should be distinguished.

## 4. Correct Parsing Approach

### 4.1 Column Detection

Count `<td>` elements per row:
- 7+ cells: sub-page layout → model at index 2, score at index 3
- 4-6 cells: main page layout → model at index 1, score at index 2

### 4.2 Model Name Extraction

Target the `<a>` tag inside the model cell, which contains only the clean model name:
```python
model_td = tds[model_idx]
link = model_td.select_one("a")
model_name = link.get_text(strip=True) if link else model_td.get_text(strip=True)
```

### 4.3 Organization Extraction

The model cell has a secondary `<span>` with text like `"Anthropic - Proprietary"`. Parse the org from before the separator.

### 4.4 Elo Score Extraction

The score cell contains `<span>1504</span><span>+-6</span>`. Extract the numeric portion by targeting the first `<span>` child or by splitting on "+-".

### 4.5 Variant Derivation

Map the page URL path to a variant:
- `/leaderboard/` → `arena_elo`
- `/leaderboard/text` → `arena_elo_text`
- `/leaderboard/code` → `arena_elo_code`
- `/leaderboard/vision` → `arena_elo_vision`
- etc.

## 5. Data Cleanup

All 441 existing LMArena events are unsalvageable (Elo scores were never captured). Delete all LMArena EventRecords and cascade to ClaimRecords and CrossReferences.
