from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_rates():
    response = client.get("/rates")
    assert response.status_code == 200
    assert "rates" in response.json()

