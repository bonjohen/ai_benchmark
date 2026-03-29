# Analysis Pipeline Design Document

## 1. Purpose

Define the analysis pipeline (pipeline 2) as a directed acyclic graph (DAG) in the same TOML format used by the three collection pipeline graphs (pipeline 1). This provides a machine-readable, self-documenting representation of how collected data flows through analysis services into intelligence products consumed by the UI, API, and CLI.

## 2. Scope

Pipeline 1 (collection) is already documented in three TOML graph files:
- `graph_primary.toml` — 8 sources, 44 pages (official vendor monitoring, trust 4.5-5.0)
- `graph_secondary.toml` — 11 sources, 26 pages (benchmarks, news, trust 3.5-5.0)
- `graph_discovery.toml` — 3 sources, 7 pages (research, community, trust 3.0-4.5)

Pipeline 2 (analysis) transforms the output of pipeline 1 through 13 async services into 13 intelligence products. This document defines `graph_analysis.toml` covering:
- 5 input tables (produced by pipeline 1)
- 13 analysis services (in 3 tiers)
- 13 output products (typed dataclass results)
- 6 consumers (4 UI pages, REST API, CLI)

## 3. Core Design Principles

1. **Same structure** — The analysis graph uses the identical `[graph]`, `[[nodes]]`, `[[edges]]` TOML layout as collection graphs. Node types are adapted from `source/page` to `table/service/product/consumer` but the format is unchanged.

2. **Tiered services** — Services are organized into three tiers reflecting their dependency depth. Tier 1 reads directly from DB tables. Tier 2 composes Tier 1 services. Tier 3 (digest) orchestrates everything. This maps naturally to graph layers.

3. **Explicit data lineage** — Every edge traces exactly one dependency. If a UI page shows verification data, there is an explicit `renders` edge from `out.verification_data` to `ui.verification`. No implicit dependencies.

4. **Documentation artifact** — Like the collection graphs, this is a documentation and visualization artifact. The actual runtime orchestration happens through Python imports. The graph captures the architecture, not the execution.

## 4. Primary User Stories

1. As a developer, I can read `graph_analysis.toml` to understand which DB tables feed which services, and which services compose into which products.

2. As a user reviewing the UI, I can trace any dashboard widget back to its source service and underlying database table through the graph.

3. As someone comparing the two pipelines, I can see that pipeline 1 (collection) produces the 5 tables that pipeline 2 (analysis) consumes — the graphs connect at the table boundary.

## 5. Functional Requirements

### 5.1 Graph Header

The `[graph]` section uses fields analogous to collection graphs but adapted for analysis:

| Field | Value |
|-------|-------|
| name | "Analysis Pipeline" |
| classification | "analysis" |
| description | How collected data becomes intelligence products |
| table_count | 5 |
| service_count | 13 |
| product_count | 13 |
| consumer_count | 6 |

### 5.2 Node Types

**Control** (`START`, `END`) — identical to collection graphs.

**Table** — DB tables produced by pipeline 1. Fields: `id`, `type="table"`, `label`, `db_table` (SQLAlchemy tablename), `pipeline` (origin).

**Service** — Analysis service modules. Fields: `id`, `type="service"`, `label`, `tier` (1/2/3), `module` (Python path), `service_role` (what it does).

**Product** — Output dataclasses. Fields: `id`, `type="product"`, `label`, `dataclass` (type name from `types.py`).

**Consumer** — UI pages, API, CLI. Fields: `id`, `type="consumer"`, `label`, `consumer_type` (ui_page/api/cli), `route`.

### 5.3 Edge Types

| Relationship | Meaning | Analogous to collection graph |
|-------------|---------|-------------------------------|
| `initiates` | START triggers table reads | START → sources |
| `feeds` | Table provides data to service | sources → pages ("monitors") |
| `calls` | Service composes another service | (new) |
| `produces` | Service emits a product | pages → END ("produces") |
| `renders` | Product feeds a consumer | (new) |
| `delivers` | Consumer completes the pipeline | consumers → END |
| `validates` | Cross-service verification | cross-source ("confirms") |

### 5.4 Service Dependencies

Tier 1 (base, read from tables):
- `model_lifecycle` ← EventRecord, ClaimRecord, CrossReference
- `benchmark_trends` ← EventRecord
- `competitive_intel` ← EventRecord
- `research_pulse` ← CandidatePaper, EnrichedPaper, EventRecord
- `anomaly_detector` ← EventRecord, ClaimRecord
- `verification` ← EventRecord, ClaimRecord, CrossReference

Tier 2 (composed, call Tier 1):
- `capability` ← benchmark_trends
- `evolution` ← benchmark_trends
- `spotlight` ← model_lifecycle, benchmark_trends
- `landscape` ← competitive_intel, model_lifecycle, benchmark_trends
- `correlation` ← benchmark_trends
- `research_pipeline` ← research_pulse

Tier 3 (orchestrator):
- `digest` ← model_lifecycle, benchmark_trends, competitive_intel, research_pulse, anomaly_detector, spotlight, evolution

### 5.5 Consumer Dependencies

UI Overview page ← model_data, verification_data, spotlight_data, landscape_data, evolution_data
UI Models page ← model_data
UI Model Detail page ← model_data, capability_data
UI Verification page ← verification_data
REST API ← all 13 products (18 endpoints)
CLI ← all 13 products (16 subcommands)
