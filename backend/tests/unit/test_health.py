from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "env" in body


def test_health_response_includes_correlation_id_header() -> None:
    response = client.get("/health")
    assert response.headers.get("X-Correlation-ID")