from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


def test_root_redirects_to_dashboard():
    resp = client.get("/")
    assert resp.status_code in (302, 307)
    assert "/dashboard" in resp.headers["location"]


def test_dashboard_home_loads():
    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    assert "AI Systems Overview" in resp.text
