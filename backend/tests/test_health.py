from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"
    # o banco pode estar fora em ambiente de teste; só garantimos que é reportado
    assert body["database"] in {"up", "down"}
