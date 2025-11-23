# Architecture Overview

## Components

1. **API Layer (`app/main.py`)**
   - FastAPI app exposing `/audit`, `/health`, `/metrics`.
   - Applies request validation, audit logging, and Prometheus instrumentation.

2. **Adapter Layer (`app/adapters/`)**
   - `AdapterResponse` contract enforces (`text`, `tokens`, `latency_ms`, `raw`).
   - Each adapter implements retries + exponential backoff with classified errors.
   - Mock adapter is provided for local testing.

3. **Pipelines (`app/services`)**
   - `AuditService` orchestrates adapter fan-out, safety enforcement, judge compute, consensus, and persistence.
   - `SafetyChecker` scrubs prompts/responses and emits violations.
   - `JudgeEngine` enforces the JSON rubric with validation and fallback.
   - `ConsensusEngine` aggregates multi-LLM outputs, requiring contributor provenance and citations.

4. **Persistence**
   - `storage.ObjectStoreClient` – S3-compatible interface; local fallback writes JSON blobs to `var/object_store`.
   - `storage.RelationalStore` – Postgres (psycopg) client; local fallback uses SQLite and SQLAlchemy.
   - Both paths persist raw adapter responses, safety events, judgments, and metadata.

5. **Telemetry**
   - Structured JSON logs emitted per pipeline step (audit ingest, adapter call, judge, consensus, persistence).
   - Prometheus metrics: `audit_requests_total`, `audit_latency_seconds`, `judge_failures_total`.

6. **Embedding Model**
   - Configured via `EmbeddingSettings.model_name`. All similarity and contradiction detection uses this model exclusively to keep vectors comparable.

## Data Flow

1. Client posts an `AuditRequest` → FastAPI validates payload.
2. Request logged, metrics timer started.
3. Adapters invoked in parallel (mocked locally) → responses normalized.
4. Safety checker processes each adapter response. Violations replaced with `[REDACTED_HARMFUL_CONTENT]`.
5. Judge engine scores sanitized responses according to the rubric.
6. Consensus engine merges judgments, includes list of contributors + citation handles.
7. Storage layer writes raw adapter outputs, sanitized artifacts, and judgments to object store + relational DB.
8. Response returned to caller only after persistence succeeds.

## Deployment Notes

- **Runtime**: Python 3.11, FastAPI, Uvicorn w/ gunicorn for production.
- **Databases**: Postgres (with pgvector) for relational + vector storage. Redis for rate limiting and job queues.
- **Object Store**: AWS S3 or compatible service (MinIO locally).
- **Kubernetes**: Provide manifests for API, worker, and scheduler deployments; metrics scraped by Prometheus Operator.

## Security & Compliance

- All datasets sanitized before persistence.
- PII prohibited unless request explicitly carries `pii_allowed=true`.
- Audit logs immutable; retention enforced by storage tier.
- Adapters use signed credentials loaded from Kubernetes secrets.

