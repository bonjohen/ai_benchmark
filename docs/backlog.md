# Backlog

| # | Priority | Description |
|---|----------|-------------|
| 1 | Normal | Log both `published_date` and `observed_at` for each item processed during collection. Currently only structlog context is emitted — add explicit per-item log lines showing the article's original publication date alongside the extraction timestamp so backfill runs are auditable from log files alone. |
| 2 | Normal | All direct `python -m ai_benchmark` commands in operational runbooks should include log file redirection. Currently steps 6–8 in Phase 6 write to console only. Either add `> logs/<name>.log 2>&1` to instructions or add built-in file logging to CLI commands. |
