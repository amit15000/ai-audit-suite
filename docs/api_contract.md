# API Contract – POST /audit

```
POST /audit
Content-Type: application/json
```

## Request Schema (`AuditRequest`)

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `job_id` | string | yes | Deterministic identifier for the audit job. |
| `prompt` | string | yes | High-level task description. |
| `adapters` | AdapterInvocation[] | yes | List of adapter executions to perform. |
| `pii_allowed` | bool | no | Default `false`. If true, safety checker skips PII redaction. |
| `metadata` | object | no | Arbitrary key/value metadata propagated to storage. |

### AdapterInvocation

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `adapter_id` | string | yes | Identifier of the adapter to invoke (e.g., `mock`). |
| `instructions` | string | yes | Prompt/instructions to send to the adapter. |
| `context` | string | no | Optional additional context. |
| `metadata` | object | no | Caller metadata for this invocation. |

## Response Schema (`AuditResponse`)

| Field | Type | Description |
| --- | --- | --- |
| `job_id` | string | Mirrors request `job_id`. |
| `status` | enum(`completed`,`failed`) | Pipeline status. |
| `artifacts` | AdapterAuditArtifact[] | Per-adapter, sanitized outputs. |
| `consensus` | ConsensusOutput | Consensus summary with contributors/citations. |
| `created_at` | ISO-8601 datetime | Response timestamp. |
| `metadata` | object | Echo of request metadata. |

### AdapterAuditArtifact

- `adapter_id` – adapter identifier.
- `sanitized_text` – post-safety output.
- `findings` – list of safety findings (`category`, `details`, `replaced_text`).
- `scores` – `JudgmentScores` structure.
- `citations` – references to persisted evidence (e.g., `artifact:mock`).

### ConsensusOutput

- `summary` – machine-readable summary containing score snippets.
- `contributors` – array of `{adapter_id, evidence}` entries.
- `citations` – deduplicated references supporting the summary.

## Error Handling

- 400 – Validation failure (FastAPI / Pydantic error payload).
- 500 – Unexpected pipeline failure (message capped, sensitive data stripped).

All responses are passed through the safety checker prior to return.

