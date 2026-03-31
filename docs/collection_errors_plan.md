# Collection Error Remediation — Implementation Plan

**Source document:** `docs/collection_errors_design.md`

## Work Queue Instructions

### State Transitions

Open  ──>  Started  ──>  Completed

### Commit Protocol

1. Work through all tasks in a phase.
2. When every task reaches Completed, write the Phase Summary.
3. Stage and commit all changes for the phase.

## Phase 1: All Fixes (Single Phase — All Small Changes)

**Goal:** Collection logs produce near-zero warnings for known issues. Single-writer enforced. No retries on permanent failures.
**Depends on:** Nothing.

| Task | Status | Started (PST) | Completed (PST) | Description |
|------|--------|---------------|------------------|-------------|
| 1.1 | Open | | | **collect.bat template**: Add server stop/restart around collection. |
| 1.2 | Open | | | **Coordinator**: Don't retry 403/404 — check `result.status_code` before scheduling retry. |
| 1.3 | Open | | | **Coordinator**: Change `low_value_page_filtered` from warning to debug. |
| 1.4 | Open | | | **Semantic Scholar**: Increase inter-query delay from 3s to 10s when no API key. |
| 1.5 | Open | | | Regenerate `C:\ai-benchmark\bin\collect.bat` from updated template. |
| 1.6 | Open | | | Deploy to `C:\ai-benchmark`. |
| 1.7 | Open | | | Stage and commit. |

### Phase 1 Summary

- **Changes:** TBD
- **Commit:** `Fix collection errors: single-writer, no 403 retry, reduce log noise`
