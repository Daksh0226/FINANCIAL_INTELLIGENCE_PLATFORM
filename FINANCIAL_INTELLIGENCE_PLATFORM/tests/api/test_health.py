from fastapi.testclient import TestClient
from src.api.main import app
client = TestClient(app)

def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_root():
    r = client.get("/")
    assert r.status_code == 200

def test_healthz():
    r = client.get("/api/v1/healthz")
    assert r.status_code == 200
