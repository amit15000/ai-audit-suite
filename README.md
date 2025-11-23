# Project W – Multi-LLM Audit Platform

Project W is an enterprise-grade audit and evaluation control plane for orchestrating multi-LLM assessments with deterministic safety, provenance, and compliance guarantees. This repository hosts the FastAPI control surface, adapter abstractions, local safety tooling, and reference pipelines for consensus-based judging.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e .
uvicorn app.main:app --reload
```

Invoke the contract test:

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

Environment variables are defined in `app/config.py`. Copy `.env.example` (to be generated) and override secrets. Defaults point to local Postgres/Redis/S3 emulators; integration with production backends occurs via standard connection strings.

## Safety Workflow

Every outbound payload is sanitized via `SafetyChecker`. When violations occur, offending spans are replaced with `[REDACTED_HARMFUL_CONTENT]`, and an audit event is persisted for review. Dataset generation helpers enforce non-actionability through allow/deny patterns.

## Next Steps

1. Flesh out real adapter implementations against approved LLM providers.
2. Connect storage clients to managed Postgres + object store.
3. Extend consensus workers with real contradiction detection leveraging the configured embedding model.

