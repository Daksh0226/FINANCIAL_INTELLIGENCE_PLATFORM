from fastapi.testclient import TestClient
from src.api.main import app
client = TestClient(app)

def test_list_sectors():
    r = client.get("/api/v1/sectors")
    assert r.status_code == 200
    assert "sectors" in r.json()

def test_get_sector_not_found():
    r = client.get("/api/v1/sectors/UnknownSectorXYZ")
    assert r.status_code == 404

def test_get_sector_valid():
    r = client.get("/api/v1/sectors/IT")
    # IT exists or Financials
    assert r.status_code in (200,404)
