from fastapi.testclient import TestClient
from src.api.main import app
client = TestClient(app)

def test_list_companies():
    r = client.get("/api/v1/companies")
    assert r.status_code == 200
    assert "companies" in r.json()

def test_get_company_not_found():
    r = client.get("/api/v1/companies/UNKNOWN123")
    assert r.status_code == 404

def test_invalid_limit():
    r = client.get("/api/v1/companies?limit=999")
    assert r.status_code == 400
