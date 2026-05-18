# Two-Stage Report Generation: Extract Then Synthesize

## The Lesson

When building reports that combine deterministic data extraction with LLM synthesis, split them into two explicit stages: a repeatable extraction step that produces a structured intermediate file, and a separate synthesis step that feeds that file to the LLM. This makes each stage independently testable, debuggable, and retriable.

## Context

A daily intelligence report summarizes AI industry events collected over the previous 24 hours — new model releases, benchmark results, pricing changes, and research papers. The report needed to be both machine-structured (for archival) and human-readable (for consumption). The LLM synthesis step uses Claude CLI, which bills against OAuth credits — making unnecessary re-runs expensive.

## What Happened

1. The first implementation was a single CLI command that queried the database and formatted a markdown report in Python. No LLM involvement — pure template rendering. The output was factual but dense and unreadable.
2. A rewrite added claim-based reporting with deduplication, source URLs, confidence metadata, and abstract extraction from raw content. Better data, still not a narrative.
3. A `report.bat` script was introduced with two stages: Stage 1 runs `ai-benchmark report extract` to produce a deterministic JSON file; Stage 2 pipes that JSON to `claude -p` for narrative synthesis.
4. The JSON intermediate was too noisy. A compaction pass was added: noise filtering, GitHub-only allowlists for certain source types, deduplication of claims that differ only in timestamp.
5. Historical report generation was added (`--date` flag) so past days could be backfilled without re-collecting data.
6. Weekly reports were built as aggregations of 7 daily extracts — the same two-stage pattern at a larger time window.
7. OAuth routing was added: the script explicitly clears `ANTHROPIC_API_KEY` so Claude CLI uses session-based OAuth billing.
8. Idempotency was added: if the extract JSON already exists for a given date, Stage 1 is skipped, saving database queries and preventing accidental overwrites.

## Key Insights

- **Deterministic stages should be separable from stochastic stages.** The extract step produces the same output for the same database state. The LLM step is non-deterministic. Separating them means you can re-run synthesis without re-extracting, and debug extraction without paying for LLM calls.
- **Intermediate files are debuggable artifacts.** When the final report has an error, the first question is "bad data or bad synthesis?" The JSON intermediate answers this instantly. Without it, you're debugging the entire pipeline end-to-end.
- **Compaction is its own step, not part of extraction.** Raw extraction should be lossless. Filtering, deduplication, and noise removal happen in a compaction pass between extraction and synthesis. This keeps the raw extract available for debugging while giving the LLM a clean input.
- **Idempotency saves money.** LLM calls cost real money (or credits). Skipping extraction when the file already exists, and making synthesis retriable without side effects, prevents accidental double-billing during development and testing.
- **Weekly aggregation falls out naturally.** Once daily extracts exist as files, building weekly reports is just "read 7 JSON files and concatenate." The two-stage pattern made a new reporting cadence trivial to add.

## Applicability

Applies to any pipeline where data retrieval/transformation feeds into LLM generation: automated summaries, changelog generators, research digests, customer report builders. Does NOT apply when the LLM is doing the data retrieval itself (e.g., RAG with tool use) — there the stages are interleaved by design.

## Related Lessons

- [OAuth Credit Routing for CLI Tools](oauth-credit-routing-cli-tools.md) — The billing guardrail that protects the synthesis stage from draining the wrong budget.
