# Revert as a Design Signal

## The Lesson

A git revert is a signal that the original change had a design gap — not just a bug. When you revert, don't just re-implement the same approach with a fix; use the revert as a forcing function to write down what the original approach missed before trying again.

## Context

A data pipeline and its associated web UI underwent several feature additions and fixes over a period of weeks. The git history contains multiple revert-then-redo sequences: a source catalog change that bundled additions with removals, a UI fix that introduced a performance regression, and a data file addition that turned out to be unnecessary. Each revert was followed by a different approach — but the time between revert and redo varied from minutes (reactive) to days (deliberate).

## What Happened

1. **Source catalog revert** (minutes between revert and redo): Added new sources and dropped zero-yield pages in one commit. Reverted within minutes when the page drops were questioned. Re-applied the additions, then separately restored the dropped pages. The fast turnaround meant no design reflection — the same bundling mistake could recur.
2. **Score parsing revert** (same day): A commit fixing score parsing, date display, and model detail density was reverted when it introduced a UI regression. The fix bundled three unrelated changes, making it impossible to keep the parts that worked and revert only the regression.
3. **Raw article data revert** (same day): A 2,893-line JSON file of raw article data was committed for AI summarization, then reverted when the approach was reconsidered — the data should be generated on demand, not cached in the repo.
4. In each case, the revert itself was correct. But only the third case led to a genuinely different approach (on-demand generation instead of cached files). The first two cases re-applied variations of the original approach without addressing the design gap (bundled changes).

## Key Insights

- **Reverts are design feedback, not just undo operations.** A revert means something was wrong with the approach, not just the implementation. Treating it as "oops, let me try again" misses the learning opportunity.
- **Fast reverts often skip the reflection step.** When the revert-and-redo cycle takes minutes, there's no pause to ask "why did this need reverting?" Deliberately slowing down after a revert — even for 10 minutes of written reflection — produces better second attempts.
- **Bundled changes amplify revert damage.** When a commit mixes independent changes, reverting it forces you to undo everything, including parts that were correct. This is the strongest argument for single-purpose commits: they make reverts surgical instead of destructive.
- **The best revert outcome is a design doc.** If the revert reveals that the approach was fundamentally wrong (not just buggy), the right next step is a short design note explaining what was missed, not another implementation attempt. The third case (raw data → on-demand generation) exemplifies this.
- **Track your revert rate.** Multiple reverts in a short period suggest a pattern problem — perhaps insufficient testing, unclear requirements, or a codebase area that needs better documentation. Individual reverts are normal; clusters are a signal.

## Applicability

Applies to any development workflow where reverts happen: feature development, hotfixes, configuration changes, infrastructure modifications. Does NOT apply to planned reverts (e.g., reverting a feature flag to disable a feature) — those are operational decisions, not design signals.

## Related Lessons

- [Revert-Restore-Reapply: Safe Source Catalog Changes](revert-restore-reapply-safe-catalog-changes.md) — A specific instance of this pattern in source catalog management.
- [Pipeline Data Quality Remediation](pipeline-data-quality-design-doc-first.md) — Shows the design-doc-first approach that prevents the need for reverts.
