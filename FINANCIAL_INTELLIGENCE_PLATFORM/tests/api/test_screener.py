from fastapi.testclient import TestClient
from src.api.main import app
client = TestClient(app)

def test_screener_get():
    r = client.get("/api/v1/screener")
    assert r.status_code == 200
    assert "results" in r.json()

def test_screener_preset_valid():
    r = client.get("/api/v1/screener?preset=Quality Compounder")
    assert r.status_code == 200

def test_screener_preset_invalid():
    r = client.get("/api/v1/screener?preset=InvalidPreset")
    assert r.status_code == 400

def test_screener_post():
    r = client.post("/api/v1/screener/screen", json={"preset":"Value Pick"})
    assert r.status_code == 200
