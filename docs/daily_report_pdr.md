# Physical Design Requirements: Daily Report

**Source document:** `docs/daily_report_design.md`
**Project root:** `C:\Projects\ai_benchmark`
**Date:** 2026-04-01 11:00 PM (PST)

## 1. System Context

### 1.1 Existing Infrastructure to Reuse

| Asset | Location | Reuse |
|---|---|---|
| Report query layer | `ai_benchmark/reporting/report_queries.py` | Reuse `_fetch_events_in_date_range`, `_build_article`, `_attach_cross_refs`. Modify to filter noise and compact output. |
| Report formatter | `ai_benchmark/reporting/report_formatter.py` | Rewrite `format_json` to produce LLM-ready compact JSON. Remove `format_markdown` (Claude CLI will produce the final markdown). |
| CLI command | `ai_benchmark/cli.py` (`report`) | Keep `--format json --output` path. Remove markdown format option. |
| Deployed instance | `C:\ai-data-pipeline` | Database at `data/ai_benchmark.db`, output to `artifacts/` |
| Claude CLI | `C:\Users\boen3\AppData\Roaming\npm\claude` (v2.1.86) | Invoke via `claude -p` to summarize and produce final markdown |

### 1.2 New Dependencies to Add

| Package | Purpose | Version Constraint |
|---|---|---|
| (none) | Claude CLI is already installed system-wide | — |

## 2. Package Layout

No new Python packages. Changes to existing files plus one new script.

```
ai_benchmark/
  reporting/
    report_queries.py       # Modified: add noise filtering, compact article output
    report_formatter.py     # Modified: slim JSON output, drop markdown formatter
  cli.py                    # Modified: remove markdown format option

scripts/
  bin/
    report.bat              # New: two-stage script (extract JSON → Claude CLI → markdown)

docs/
  daily_report_design.md    # Existing design doc
  daily_report_pdr.md       # This document
```

## 3. Data Model

No database changes. The data model is the JSON output shape — what the query layer produces for Claude CLI to consume.

### 3.1 Compact Article JSON (output of Stage 1)

```json
{
  "date": "2026-04-02",
  "article_count": 45,
  "articles": [
    {
      "title": "anthropics/claude-code: v2.1.90",
      "publisher": "GitHub",
      "date": "2026-04-01",
      "model": "claude-code",
      "abstract": "Added /powerup interactive lessons and plugin marketplace resilience.",
      "url": "https://github.com/anthropics/claude-code/releases/tag/v2.1.90",
      "confirmed": false,
      "sources": 1
    }
  ]
}
```

Fields removed vs. current output: `event_type`, `source_type`, `confidence_tier`, `confirmation_status` (replaced by `confirmed` boolean), `cross_refs` (dropped — low value at current data quality), `last_7_days` (dropped), `weekly_stats` (dropped — future weekly report), `event_id`.

### 3.2 Noise Filtering Rules (applied in query layer)

Remove before JSON output:

| Rule | Examples |
|---|---|
| Non-AI GitHub repos | `google/filament`, `google/gvisor`, `google/osv.dev`, `google/triage-party`, `google/timesketch`, `google/pprof`, `google/j2cl`, `google/nerfies`, `google/device-infra`, `openai/mujoco-py` |
| Title is page chrome | Titles that are navigation fragments, single words, or HTML artifacts |
| Title too short | `len(title.strip()) <= 10` |
| RSS title-only articles with no abstract | Abstract is empty or identical to title (nothing to summarize) |

Implementation: add a `_is_noise(event)` function in `report_queries.py` that checks these rules. Applied during `_fetch_events_in_date_range` before building articles.

### 3.3 GitHub Repo Allowlist

Rather than blacklisting individual repos, maintain an allowlist of AI-relevant repo name patterns. A GitHub event passes if any pattern matches its title or canonical_path:

```python
_AI_REPO_PATTERNS = [
    "claude", "anthropic", "openai", "codex", "gpt",
    "gemini", "adk", "llama", "mistral", "cohere",
    "deepseek", "grok", "xai-sdk", "swe-bench",
    "agent", "langchain", "vllm", "transformers",
]
```

A GitHub event whose title/path contains none of these patterns is filtered as noise.

## 4. Stage 1: JSON Extraction

### 4.1 Modified `report_queries.py`

- Add `_is_noise(event: EventRecord) -> bool` — returns True for events that should be excluded
- Add `_AI_REPO_PATTERNS` list for GitHub filtering
- Modify `_build_article` to produce compact fields: drop `event_type`, `source_type`, `cross_refs`, `event_id`; add `confirmed` boolean (True if any claim has `confirmation_status == "confirmed"`)
- Truncate abstract to 200 chars max

### 4.2 Modified `report_formatter.py`

- `format_json(data)` outputs the compact structure from 3.1 — flat article list with metadata header
- Remove `format_markdown` — the markdown formatter is no longer used; Claude CLI produces the final report
- Remove `_format_article`, `_format_article_list`, `_format_articles_by_topic`, `_format_weekly_stats`, and related helpers

### 4.3 Modified `cli.py`

- Remove `--format` choice — JSON is the only output
- Keep `--output` and `--hours`/`--days` options
- Remove the `sys.stdout.reconfigure(encoding="utf-8")` workaround (no longer printing markdown to console)

## 5. Stage 2: Claude CLI Summarization

### 5.1 `scripts/bin/report.bat`

```bat
@echo off
setlocal

set ARTIFACTS=C:\ai-data-pipeline\artifacts
set RAW=%ARTIFACTS%\raw_articles.json
set REPORT=%ARTIFACTS%\daily_report.md

REM Stage 1: Extract
call C:\ai-data-pipeline\venv\Scripts\python.exe -m ai_benchmark report --output "%RAW%"

REM Stage 2: Summarize with Claude CLI
claude -p "Read the file %RAW%. It contains AI industry events from the last 24 hours. Group the articles by topic (thematic, not by publisher). For each topic, write a 2-3 sentence summary, then list the articles. Write the final report as markdown to %REPORT%. Format: # AI Intelligence Daily Report, ## date, then ## Topic Name sections with summary paragraphs and bullet-pointed articles."

echo Report written to %REPORT%
```

### 5.2 Claude CLI Invocation

The `claude` CLI supports:
- `-p "prompt"` — single-turn prompt, non-interactive
- `--allowedTools` — restrict which tools the CLI can use
- The CLI has access to the local filesystem (Read, Write tools) so it can read the JSON and write the markdown directly

The prompt instructs Claude to:
1. Read the raw JSON file
2. Group articles by topic (thematic)
3. Write summary paragraphs per topic
4. Skip any remaining noise
5. Write final markdown to the output path

### 5.3 Expected Output Format

```markdown
# AI Intelligence Daily Report
## 2026-04-02

45 articles analyzed, 28 relevant.

---

## Anthropic Claude Updates

Claude Code received two updates (v2.1.89 and v2.1.90) adding deferred
tool permissions and interactive feature tutorials. The Claude Agent SDK
also shipped v0.1.54.

- **anthropic/claude-code: v2.1.90** (GitHub, 2026-04-01)
  Added /powerup interactive lessons and plugin marketplace resilience.
  [Source](https://github.com/anthropics/claude-code)

---

## OpenAI Codex Releases

OpenAI shipped Codex 0.119.0-alpha.3 with Windows sandbox improvements.

- **openai/codex: 0.119.0-alpha.3** (GitHub, 2026-04-02)
  Windows sandbox egress rules, device code sign-in flow.
  [Source](https://github.com/openai/codex/releases/tag/rust-v0.119.0-alpha.3)

---
```

## 6. Verification

| Step | Command | Expected |
|---|---|---|
| JSON output is compact | `ai-benchmark report --output test.json` then check file size | Under 20K chars for a typical day |
| Noise filtered | Inspect JSON — no `google/filament`, no Iran war articles | Zero non-AI entries |
| Claude CLI produces report | `scripts\bin\report.bat` | `daily_report.md` exists, has topic sections |
| Lint clean | `ruff check ai_benchmark/reporting/` | No errors |
| Tests pass | `pytest tests/test_daily_report.py` | All pass |
| Deploy works | `ai-bench-installer.bat upgrade -Name ai-data-pipeline` | Upgrade complete |
