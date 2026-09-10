"""
Unit Tests for UrjaPortalClient HTTP and Session Lifecycle (app/client.py).
"""

import httpx
import pytest
from app.client import UrjaPortalClient
from app.exceptions import (
    PortalAuthenticationError,
    PortalRequestError,
    PortalSessionExpired,
    UpstreamTimeoutError,
)


def test_client_login_success():
    def mock_handler(request: httpx.Request):
        if request.url.path == "/login":
            if request.method == "GET":
                return httpx.Response(200, text="<html>Login Form</html>")
            elif request.method == "POST":
                # Ensure Origin header was supplied
                assert request.headers.get("Origin") == "https://urja-ops.flockenergy.tech"
                return httpx.Response(302, headers={"Set-Cookie": "session_id=valid_session_123"})
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    client = UrjaPortalClient(
        base_url="https://urja-ops.flockenergy.tech",
        username="admin@flockenergy.tech",
        password="correct_password",
        transport=transport,
    )

    assert client.login() is True
    assert client.is_authenticated is True


def test_client_login_failure():
    def mock_handler(request: httpx.Request):
        if request.url.path == "/login" and request.method == "POST":
            return httpx.Response(
                200,
                json={"type": "failure", "status": 401, "data": '["Invalid email or password."]'}
            )
        return httpx.Response(200, text="Login Form")

    transport = httpx.MockTransport(mock_handler)
    client = UrjaPortalClient(
        base_url="https://urja-ops.flockenergy.tech",
        username="admin@flockenergy.tech",
        password="wrong_password",
        transport=transport,
    )

    with pytest.raises(PortalAuthenticationError):
        client.login()

    assert client.is_authenticated is False


def test_client_session_expired_single_retry():
    call_count = 0

    def mock_handler(request: httpx.Request):
        nonlocal call_count
        if request.url.path == "/login":
            return httpx.Response(200, text="OK")
        if request.url.path == "/portal/meters/search":
            call_count += 1
            if call_count == 1:
                # First attempt returns 401 unauth
                return httpx.Response(401, json={"error": "unauthorized", "message": "A valid session is required."})
            else:
                # Retry attempt returns successful JSON
                return httpx.Response(200, json={"data": [{"meterId": "MTR-001"}], "total": 1})
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    client = UrjaPortalClient(
        base_url="https://urja-ops.flockenergy.tech",
        username="admin@flockenergy.tech",
        password="password",
        transport=transport,
    )
    client.is_authenticated = True

    result = client.get_meters(page=1)
    assert result["total"] == 1
    assert call_count == 2  # Proves 1 initial request + 1 retry = 2 total requests


def test_client_infinite_loop_prevention():
    def mock_handler(request: httpx.Request):
        if request.url.path == "/login":
            return httpx.Response(200, text="OK")
        if request.url.path == "/portal/meters/search":
            # Always return 401
            return httpx.Response(401, json={"error": "unauthorized"})
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    client = UrjaPortalClient(
        base_url="https://urja-ops.flockenergy.tech",
        username="admin@flockenergy.tech",
        password="password",
        transport=transport,
    )
    client.is_authenticated = True

    with pytest.raises(PortalSessionExpired):
        client.get_meters(page=1)


def test_client_timeout_handling():
    def mock_handler(request: httpx.Request):
        raise httpx.ReadTimeout("Connection timed out")

    transport = httpx.MockTransport(mock_handler)
    client = UrjaPortalClient(
        base_url="https://urja-ops.flockenergy.tech",
        username="admin@flockenergy.tech",
        password="password",
        transport=transport,
    )
    client.is_authenticated = True

    with pytest.raises(UpstreamTimeoutError):
        client.get_meters(page=1)


def test_client_upstream_500_handling():
    def mock_handler(request: httpx.Request):
        return httpx.Response(502, text="Bad Gateway")

    transport = httpx.MockTransport(mock_handler)
    client = UrjaPortalClient(
        base_url="https://urja-ops.flockenergy.tech",
        username="admin@flockenergy.tech",
        password="password",
        transport=transport,
    )
    client.is_authenticated = True

    with pytest.raises(PortalRequestError):
        client.get_meters(page=1)
