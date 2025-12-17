# Project W – Multi-LLM Audit Platform

Project W is an enterprise-grade audit and evaluation control plane for orchestrating multi-LLM assessments with deterministic safety, provenance, and compliance guarantees. This repository hosts the FastAPI control surface, adapter abstractions, local safety tooling, and reference pipelines for consensus-based judging.

## Quick Start

### 1. Start Local Docker Services (PostgreSQL + MinIO)

```bash
docker-compose up -d
```

This starts:
- **PostgreSQL** (with pgvector) on port `5432`
  - User: `audit_user`
  - Password: `audit_password`
  - Database: `audit_db`
- **MinIO** (S3-compatible storage) on ports `9000` (API) and `9001` (Console)

### 2. Configure Environment Variables

Create a `.env` file in the project root with:

```env
# Local Docker PostgreSQL (recommended for development)
DB_URL=postgresql://audit_user:audit_password@localhost:5432/audit_db

# Optional: Supabase (only if DB_URL is not set)
# SUPABASE_DB_URL=postgresql://postgres:password@host:5432/postgres
```

### 3. Install Dependencies and Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e .
uvicorn app.main:app --reload
```

### 4. Initialize Database

```bash
python scripts/init_db.py
```

### 5. Test Database Connection (Optional)

```bash
python scripts/test_db_connection.py
```

### Run Tests

```bash
pytest
```

## Key Surfaces

- `POST /audit` – primary ingestion endpoint for audit jobs. Accepts the `AuditRequest` payload and returns canonical `AuditResponse`.
- `GET /health` – readiness probe.
- `GET /metrics` – Prometheus-compatible metrics.

## Architecture Overview

1. **Ingress** – FastAPI endpoint validates payloads and writes structured audit logs.
2. **Adapter Layer** – Implements retries, exponential backoff, and the AdapterResponse contract (`text`, `tokens`, `latency_ms`, `raw`).
3. **Safety Pipeline** – Rule-based safety checker sanitizes prompts/responses before exposure, replacing violations with `[REDACTED_HARMFUL_CONTENT]`.
4. **Judge + Consensus** – Deterministic rubric-based scorer produces JSON with `accuracy`, `completeness`, `clarity`, `reasoning`, `safety`, `hallucination_risk`. Consensus output lists contributors and citation references.
5. **Persistence** – Raw adapter responses and metadata are durably persisted via the storage interface (object store + relational DB). Local dev defaults to filesystem/SQLite.
6. **Telemetry** – Structured audit logs plus Prometheus metrics for pipeline steps.

See `docs/architecture.md` and `docs/judge_rubric.md` for deeper detail.

## Project Standards

- Python 3.11+, FastAPI, Postgres + pgvector, Redis, S3-compatible storage, Kubernetes-ready manifests.
- Single embedding model per deployment (configured via `EmbeddingSettings`).
- Non-actionable dataset generation; no PII unless explicitly whitelisted.
- All new features require unit + integration tests. Use `pytest` for test harnesses.

## Repository Layout

- `app/` – FastAPI app, adapters, services, pipelines.
- `system/` – system-level prompts and policies.
- `docs/` – architecture, API, rubric documentation.
- `tests/` – pytest suites (unit + integration).

## Local Configuration

### Database Configuration

The application supports multiple database backends:

1. **Local Docker PostgreSQL** (Recommended for development)
   - Set `DB_URL` in your `.env` file
   - Example: `DB_URL=postgresql://audit_user:audit_password@localhost:5432/audit_db`
   - Start with: `docker-compose up -d`

2. **Supabase** (Cloud PostgreSQL)
   - Set `SUPABASE_DB_URL` in your `.env` file (only used if `DB_URL` is not set)
   - SSL is automatically enabled for Supabase connections

3. **SQLite** (Default fallback)
   - Used if no database URL is configured
   - Database file: `var/audit.db`

### Environment Variables

Create a `.env` file in the project root. Key variables:

```env
# Database (choose one)
DB_URL=postgresql://audit_user:audit_password@localhost:5432/audit_db
# SUPABASE_DB_URL=postgresql://postgres:password@host:5432/postgres

# Storage (MinIO defaults)
STORAGE_S3_ENDPOINT=http://localhost:9000
STORAGE_S3_BUCKET=w-audit

# API Keys (as needed)
OPENAI_API_KEY=your-key-here
```

See `app/core/config.py` for all available configuration options.

## Safety Workflow

Every outbound payload is sanitized via `SafetyChecker`. When violations occur, offending spans are replaced with `[REDACTED_HARMFUL_CONTENT]`, and an audit event is persisted for review. Dataset generation helpers enforce non-actionability through allow/deny patterns.

## Next Steps

1. Flesh out real adapter implementations against approved LLM providers.
2. Connect storage clients to managed Postgres + object store.
3. Extend consensus workers with real contradiction detection leveraging the configured embedding model.

