# Revert-Restore-Reapply: Safe Source Catalog Changes

## The Lesson

Never bundle additive changes (new sources) with destructive changes (dropping existing pages) in one commit. If a rollback is needed, you lose the additions along with the removals — and untangling them under pressure wastes time.

## Context

An ETL pipeline monitors ~80 pages across 21 sources for AI industry intelligence. The source catalog is a TOML file that defines every monitored URL. Adding new sources (DeepSeek, Epoch AI) seemed like a natural time to prune 10 pages that had produced zero events — a net improvement on paper.

## What Happened

1. A single commit added 2 new sources (DeepSeek with 4 pages, Epoch AI with 2 pages) and simultaneously dropped 10 zero-yield pages from existing sources. Net change: 21→23 sources, 80→76 pages.
2. The page drops were immediately questioned — zero-yield pages may yield data in the future (new product launches, API changes), and removing them loses monitoring coverage silently.
3. The entire commit was reverted, which also removed the new sources that were fine.
4. The revert was itself reverted (re-applying the original), just to get the new sources back.
5. A final commit restored all 10 dropped pages alongside the new sources. Final state: 23 sources, 86 pages.
6. Four commits and two reverts to accomplish what should have been one clean additive commit.

## Key Insights

- **Separate additive from destructive changes.** Adding new sources is low-risk and independently valuable. Dropping pages is a coverage decision that needs separate justification. Bundling them creates a false dependency.
- **Zero-yield is not zero-value.** A monitoring page that produces no events today may produce critical events tomorrow. The cost of keeping an idle page (one HTTP request per cycle) is negligible compared to the cost of missing a signal.
- **Reverts are blunt instruments.** `git revert` undoes the entire commit. If the commit mixes concerns, the revert forces you to re-apply the parts you wanted to keep, creating noise in the history.
- **Catalog changes deserve their own commits.** Source catalog files are shared configuration. Small, single-purpose commits make it easy to bisect issues and cherry-pick changes across branches.

## Applicability

Applies to any shared configuration file where entries are independently meaningful: monitoring configs, feature flags, dependency lists, DNS records. Does NOT apply when changes are genuinely coupled (e.g., renaming a source requires updating both the catalog entry and the collector code in one commit).

## Related Lessons

- [Revert as a Design Signal](revert-as-design-signal.md) — The broader pattern of using reverts as feedback that the original approach had a gap.
