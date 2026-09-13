import asyncio
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

if __name__ == "__main__":
    print("Testing health endpoint...")
    test_health()
    print("Health check passed. Backend is ready for voice endpoint testing.")
