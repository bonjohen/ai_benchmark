# Dev/Production Interaction Analysis — Design Document

## 1. Purpose

Document every interaction point between the production installation at `C:\ai-benchmark` and the development environment at `C:\Projects\ai_benchmark`. These interactions create risk of unintended side effects where development activity alters production behavior, or production workloads interfere with development.

## 2. Scope

This analysis covers: file-system references, Python packaging, database configuration, scheduled tasks, log paths, and runtime dependencies. It does not propose fixes — it catalogs the current state.

## 3. Architecture Overview

The production "installation" at `C:\ai-benchmark` is a thin runtime shell:

```
C:\ai-benchmark\
  bin\            4 batch scripts (collect, run, serve, backfill)
  config\         .env (database URL, log format, API keys)
  data\           ai_benchmark.db (42 MB production database)
  logs\           Collection run logs
  artifacts\      Eval pipeline artifacts
  backup\         Database backups
```

No Python source code lives here. All code execution originates from `C:\Projects\ai_benchmark` via pip's editable install mechanism.

## 4. Identified Interactions

### 4.1 Editable Install — Live Code Sharing

**Severity: Critical**

The `ai-benchmark` package is installed system-wide as an editable install (`pip install -e .`) pointing to the development repository.

| Artifact | Location |
|---|---|
| `.pth` file | `C:\Users\boen3\AppData\Roaming\Python\Python314\site-packages\_ai_benchmark.pth` |
| Content | `C:\Projects\ai_benchmark` |
| `direct_url.json` | `{"dir_info": {"editable": true}, "url": "file:///C:/Projects/ai_benchmark"}` |

**Effect:** Any code change to `C:\Projects\ai_benchmark\ai_benchmark\` is immediately live in production. There is no build step, no deployment gate, and no way to test changes without affecting the next production run. A syntax error introduced during development will cause the next scheduled collection to fail.

**Evidence:** Production log stack traces reference dev paths:
```
C:\Projects\ai_benchmark\ai_benchmark\collection\differ.py:40
```

### 4.2 Shared CLI Binary

**Severity: High**

A single CLI entry point exists system-wide:

| Component | Path |
|---|---|
| Executable | `C:\Python314\Scripts\ai-benchmark.exe` |
| Python interpreter | `C:\Python314\python.exe` (3.14.3) |
| Package resolution | Editable install at `C:\Projects\ai_benchmark` |

Both dev usage (`ai-benchmark collect --source OpenAI`) and production scripts (`python -m ai_benchmark.cli collect`) resolve to the same code. There is no virtual environment for either environment.

### 4.3 No Virtual Environment Isolation

**Severity: High**

Neither the production installation nor the development environment uses a virtual environment. Both use the system Python at `C:\Python314\python.exe`. Dependency changes in development (e.g., `pip install` or `pip uninstall`) immediately affect production.

| Aspect | Dev | Production |
|---|---|---|
| Python | `C:\Python314\python.exe` | `C:\Python314\python.exe` |
| Site-packages | User site-packages | Same |
| venv | None | None |

### 4.4 Concurrent Scheduled Tasks at 5:00 AM

**Severity: High**

Two independent scheduled tasks both trigger collection at 5:00 AM daily:

| Task Name | Trigger | Command | Target |
|---|---|---|---|
| `AIBenchmarkCollect` | Daily 05:00 | `cmd.exe /c C:\ai-benchmark\bin\collect.bat` | Production database via `.env` |
| `AI Benchmark Daily Collection` | Daily 05:00 | `powershell.exe -File C:\Projects\ai_benchmark\scripts\daily_collect.ps1` | Dev database via CWD default |

Both tasks run the same Python code (via the editable install). They hit different databases but make the same external HTTP requests simultaneously, which doubles rate-limit exposure to sources like Semantic Scholar (429 errors observed in logs).

### 4.5 `daily_collect.ps1` Targets Dev Directory

**Severity: Medium**

The `daily_collect.ps1` script explicitly sets its working directory to the dev project:

```powershell
$ProjectDir = "C:\Projects\ai_benchmark"
```

It invokes Claude Code (`claude -p`) from within the dev directory, writes logs to `C:\Projects\ai_benchmark\logs\`, and operates against the dev database at `C:\Projects\ai_benchmark\ai_benchmark.db`. This is the only scheduled task that references the dev directory.

### 4.6 Database Isolation by Convention Only

**Severity: Medium**

Database selection depends entirely on environment variables and current working directory:

| Environment | Database Path | Size | Selection Mechanism |
|---|---|---|---|
| Production | `C:\ai-benchmark\data\ai_benchmark.db` | 42 MB | Absolute path in `.env`: `AI_BENCH_DATABASE_URL` |
| Dev | `C:\Projects\ai_benchmark\ai_benchmark.db` | 26 MB | Relative default `ai_benchmark.db` resolves to CWD |

The default in `PipelineSettings` and `EvalSettings` is:
```python
database_url: str = "sqlite+aiosqlite:///ai_benchmark.db"
```

No `.env` file exists in the dev root. Isolation depends on:
1. The production `.env` setting an absolute path
2. The dev environment having no `.env` (uses relative default)
3. The CWD being `C:\Projects\ai_benchmark` when running in dev

If any script `cd`s to an unexpected directory, or if a `.env` is created in the dev root with the production path, the databases would collide.

### 4.7 Installer Scripts Formalize the Coupling

**Severity: Informational**

The deployment scripts in `scripts/` explicitly create the editable-install coupling:

| Script | Key Action |
|---|---|
| `scripts/install.bat` | `pip install -e .` from dev repo, creates `C:\ai-benchmark` dirs |
| `scripts/install.ps1` | Same, PowerShell version |
| `scripts/env.template` | Template for production `.env` with absolute paths |
| `scripts/bin/*.bat` | Production launchers that `cd /d C:\ai-benchmark` then run Python |

The installers treat `pip install -e .` as the deployment mechanism. There is no `pip install .` (non-editable) or wheel/sdist deployment option.

### 4.8 Log Path Separation

**Severity: Low**

Logs are written to separate directories but the split is fragile:

| Source | Log Path | Mechanism |
|---|---|---|
| Production batch scripts | `C:\ai-benchmark\logs\collect_YYYYMMDD_HHMMSS.log` | Script creates timestamped file, redirects stdout |
| `daily_collect.ps1` | `C:\Projects\ai_benchmark\logs\collect_YYYY-MM-DD_HH-MM-SS.log` | Script creates timestamped file |

Both `.gitignore` and the production directory exclude logs from version control. The risk is minor — logs are append-only and independently timestamped.

### 4.9 Backup Directory

**Severity: Informational**

Production has a backup at `C:\ai-benchmark\backup\ai_benchmark_20260329_210340.db` (29 MB). No backup mechanism exists for the dev database. The backup appears to be a manual copy, not automated.

## 5. Interaction Matrix

| # | Interaction | Dev -> Prod | Prod -> Dev | Shared Resource |
|---|---|---|---|---|
| 4.1 | Editable install | Code changes go live immediately | Stack traces reference dev paths | Source code |
| 4.2 | CLI binary | Same executable | Same executable | `ai-benchmark.exe` |
| 4.3 | No venv | `pip install` affects prod | `pip install` affects dev | System site-packages |
| 4.4 | Dual scheduled tasks | Both run same code | Both hit same external APIs | Rate limits, code |
| 4.5 | `daily_collect.ps1` | N/A | Runs in dev directory | Dev filesystem |
| 4.6 | Database convention | Could accidentally write prod DB | Could accidentally write dev DB | Convention only |
| 4.7 | Installer scripts | Formalizes coupling | N/A | Deployment mechanism |
| 4.8 | Log separation | Independent logs | Independent logs | None (separated) |

## 6. Observed Consequences

1. **XMLParsedAsHTMLWarning in production logs** — caused by dev code (fixed in Phase 5 of remediation plan, now live in production via editable install)
2. **Semantic Scholar 429 rate limiting** — two concurrent collection runs at 5:00 AM double the API request rate
3. **Production database 42 MB vs dev 26 MB** — different data sets accumulating independently, neither aware of the other
4. **No git remote configured** — `C:\Projects\ai_benchmark` has no push target, so there is no external backup of the source code that both environments depend on
