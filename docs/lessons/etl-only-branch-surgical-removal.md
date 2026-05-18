# ETL-Only Branch: Surgical Code Removal

## The Lesson

When stripping a codebase down to a subset of its functionality, remove in dependency order — packages first, then CLI registrations, then migrations, then dependencies, then tests, then deployment artifacts. Each commit should leave the system runnable, not just compilable.

## Context

A monorepo contained four major subsystems: data collection (ETL), model evaluation, intelligence analysis, and report publication. A new branch needed only the ETL pipeline — everything else was dead weight that complicated deployment, confused dependency management, and bloated the install. The codebase had ~175 files across the non-ETL packages, with deep cross-references in CLI entry points, database migrations, installer scripts, and test suites.

## What Happened

1. **Packages first** (`5c589cb`): Removed the `eval/`, `analysis/`, and `publication/` directories entirely. This is the most aggressive cut — it breaks imports immediately, which surfaces all coupling points.
2. **CLI registrations** (`f9cfe9e`): Stripped `eval`, `analysis`, and `publication` subcommand registrations from the CLI entry point. Without this, the CLI would crash on import.
3. **Migrations** (`7d0ce2c`): Removed database migration files for eval (revision 002), analysis (008), and publication (009). Pruned the migration chain so `alembic upgrade head` works with only ETL tables.
4. **Dependencies** (`4c96b18`): Trimmed `pyproject.toml` to remove packages only needed by eval/analysis/publication (Chart.js templates, scorer dependencies, etc.). Tightened linting config to match the reduced codebase.
5. **Tests** (`51d0349`): Removed 66 test files (16K+ lines) for the stripped packages. Fixed shared test fixtures that assumed eval tables existed.
6. **Deployment artifacts** (`e64a698`): Removed eval server from installer scripts, bin script templates, and environment variable templates. This is the outermost layer — the one users and ops scripts interact with.

## Key Insights

- **Remove inside-out, not outside-in.** Start with the core packages, not the deployment scripts. Breaking imports immediately tells you exactly what else depends on the removed code. Working outside-in (removing the CLI command first) leaves dead code that passes lint but fails at runtime.
- **Each commit must be independently runnable.** After removing packages, the CLI must still start (even if some commands are gone). After removing migrations, `alembic` must still work. This constraint forces you to fix coupling at each step rather than accumulating breakage.
- **Shared test fixtures are hidden coupling.** Test fixtures that create database tables for eval or spin up eval services will break even though no eval tests remain. Audit fixtures independently of test files.
- **Migration chains are fragile.** Removing a migration revision without updating the chain (down_revision pointers) breaks `alembic`. Each removed migration requires checking that the chain's `down_revision` links still form a connected path.
- **Deployment artifacts are the forgotten layer.** Installer scripts, environment templates, and generated batch files reference removed components. These are easy to miss because they're not Python — they don't show up in import analysis or test runs.

## Applicability

Applies to any project that needs to fork or strip a monorepo: extracting a microservice, creating a lite version, spinning off a standalone tool. Also applies to major deprecation efforts where entire feature areas are being removed. Does NOT apply to incremental feature removal where the deleted code is small and localized — overkill for removing a single endpoint.
