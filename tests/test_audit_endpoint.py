from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_audit_endpoint_returns_artifacts(tmp_path, monkeypatch):
    payload = {
        "job_id": "job-123",
        "prompt": "Evaluate response",
        "adapters": [
            {
                "adapter_id": "mock",
                "instructions": "Explain the purpose of audits.",
                "context": "testing",
            }
        ],
        "metadata": {"source": "pytest"},
    }

    response = client.post("/audit", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "job-123"
    assert body["status"] == "completed"
    assert len(body["artifacts"]) == 1
    artifact = body["artifacts"][0]
    assert artifact["adapter_id"] == "mock"
    assert "sanitized_text" in artifact
    assert "scores" in artifact
    assert "consensus" in body
    assert body["consensus"]["contributors"]

