"""
API Integration Tests for FastAPI Application Routes (app/main.py).
"""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from app.exceptions import (
    MeterNotFoundError,
    PortalAuthenticationError,
    UpstreamTimeoutError,
)
from app.main import app, get_portal_client


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.login.return_value = True
    client.get_meters.return_value = {
        "data": [
            {
                "meterId": "MTR-1001",
                "serialNo": "SN-9988",
                "make": "Genus",
                "phaseType": "3-Phase",
                "installStatus": "Active",
                "dtCode": "DT-501"
            }
        ],
        "total": 1
    }
    client.get_meter_detail.return_value = {
        "data": {
            "meterId": "MTR-1001",
            "hierarchy": {"Zone": "North", "Circle": "Circle-A", "DT": "DT-501"},
            "detail": [{"parameterName": "Voltage Rating", "parameterValue": "230V"}]
        }
    }
    client.get_meter_geo.return_value = {
        "data": {"latitude": "28.6139", "longitude": "77.2090"}
    }
    client.get_meter_consumption.return_value = {
        "data": [
            {"timestamp": "2026-09-10T10:00:00Z", "kwh": "15.40", "kvah": "16.10", "voltR": "230.5"}
        ]
    }
    client.get_hierarchy_dts.return_value = {
        "data": [
            {"code": "DT-501", "name": "DT North Sector", "feederCode": "F-01", "capacityKva": "250"}
        ],
        "total": 1
    }
    return client


@pytest.fixture
def test_app(mock_client):
    app.dependency_overrides[get_portal_client] = lambda: mock_client
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_health_check_endpoint(test_app):
    response = test_app.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "https://" in data["upstream_portal"]


def test_root_redirect_endpoint(test_app):
    response = test_app.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/docs"


def test_login_endpoint(test_app):
    response = test_app.post("/api/v1/auth/login", json={"email": "admin@flockenergy.tech", "password": "pass"})
    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_list_meters_endpoint(test_app):
    response = test_app.get("/api/v1/meters?page=1&page_size=20")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == 1
    assert payload["data"][0]["meter_id"] == "MTR-1001"
    assert payload["pagination"]["total_records"] == 1
    assert payload["pagination"]["total_pages"] == 1


def test_get_meter_detail_endpoint(test_app):
    response = test_app.get("/api/v1/meters/MTR-1001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meter_id"] == "MTR-1001"
    assert payload["hierarchy"]["Zone"] == "North"
    assert payload["location"]["latitude"] == 28.6139
    assert payload["location"]["longitude"] == 77.2090


def test_get_meter_consumption_endpoint(test_app):
    response = test_app.get("/api/v1/meters/MTR-1001/consumption")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meter_id"] == "MTR-1001"
    assert len(payload["data"]) == 1
    assert payload["data"][0]["kwh"] == 15.4


def test_get_hierarchy_endpoint(test_app):
    response = test_app.get("/api/v1/hierarchy?page=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["code"] == "DT-501"
    assert payload["data"][0]["capacity_kva"] == 250.0


def test_meter_not_found_handler(test_app, mock_client):
    mock_client.get_meter_detail.side_effect = MeterNotFoundError("NON_EXISTENT")
    response = test_app.get("/api/v1/meters/NON_EXISTENT")
    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


def test_auth_error_handler(test_app, mock_client):
    mock_client.login.side_effect = PortalAuthenticationError("Invalid credentials")
    response = test_app.post("/api/v1/auth/login", json={"email": "bad", "password": "bad"})
    assert response.status_code == 401
    assert "authentication failed" in response.json()["detail"].lower()


def test_timeout_error_handler(test_app, mock_client):
    mock_client.get_meters.side_effect = UpstreamTimeoutError("Timeout")
    response = test_app.get("/api/v1/meters")
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_pagination_validation_error(test_app):
    response = test_app.get("/api/v1/meters?page=0")
    assert response.status_code == 422
