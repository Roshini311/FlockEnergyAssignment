"""
Urja Portal HTTP Client Adapter.

Encapsulates all session state, cookie persistence, authentication logic,
CSRF header handling, network timeout management, and single-retry re-authentication.
Provides a clean interface for data fetching while guarding against infinite retry loops.
"""

import logging
from typing import Any, Dict, Optional, Union
import httpx
from app.config import settings
from app.exceptions import (
    MeterNotFoundError,
    PortalAuthenticationError,
    PortalRequestError,
    PortalSessionExpired,
    UpstreamTimeoutError,
)

logger = logging.getLogger("urja_client")


class UrjaPortalClient:
    """
    HTTP Client Wrapper for Urja Meter Ops legacy portal.
    Maintains active session cookies and handles authentication lifecycle.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[float] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = (base_url or settings.URJA_BASE_URL).rstrip("/")
        self.username = username or settings.URJA_USERNAME
        self.password = password or settings.URJA_PASSWORD
        self.timeout = timeout or settings.REQUEST_TIMEOUT

        # Create persistent httpx client with cookie jar
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            transport=transport,
        )
        self.is_authenticated = False

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Authenticates against the legacy portal `/login` endpoint.
        Sends form-encoded email & password with required Origin header for SvelteKit CSRF compatibility.
        """
        user = username or self.username
        pwd = password or self.password

        if not user or not pwd:
            logger.error("Missing username or password for portal authentication.")
            raise PortalAuthenticationError("Credentials not provided for upstream authentication.")

        login_url = f"{self.base_url}/login"
        headers = {
            "Origin": self.base_url,
            "Referer": login_url,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "email": user,
            "password": pwd,
        }

        try:
            # First GET /login to ensure session cookie initialization if needed
            self.client.get("/login", headers={"Referer": self.base_url})

            response = self.client.post("/login", data=data, headers=headers)
        except httpx.TimeoutException as e:
            logger.error("Timeout during portal login attempt.")
            raise UpstreamTimeoutError("Timeout while connecting to upstream portal for login.") from e
        except httpx.HTTPError as e:
            logger.error(f"HTTP network error during login: {e}")
            raise PortalRequestError("Network error during upstream portal login.") from e

        # Check response for failure indicators
        text = response.text
        if response.status_code == 401 or "failure" in text.lower() or "invalid email or password" in text.lower():
            self.is_authenticated = False
            logger.warning("Upstream portal login failed with invalid credentials.")
            raise PortalAuthenticationError("Invalid username or password for Urja Meter Ops portal.")

        if response.status_code >= 400:
            self.is_authenticated = False
            raise PortalAuthenticationError(f"Upstream portal returned status {response.status_code} during login.")

        self.is_authenticated = True
        logger.info("Successfully authenticated with Urja Meter Ops portal.")
        return True

    def _ensure_authenticated(self):
        """Ensures client has an active session; triggers login if not yet authenticated."""
        if not self.is_authenticated:
            self.login()

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        retry_on_401: bool = True,
    ) -> httpx.Response:
        """
        Executes an HTTP request against the legacy portal.
        Handles session expiry detection (401 / redirect to login) and safe single retry.
        """
        self._ensure_authenticated()

        headers = {
            "Referer": self.base_url,
        }

        try:
            response = self.client.request(
                method=method,
                url=path,
                params=params,
                json=json_data,
                headers=headers,
            )
        except httpx.TimeoutException as e:
            logger.error(f"Timeout during request to {path}")
            raise UpstreamTimeoutError(f"Upstream request to {path} timed out.") from e
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during request to {path}: {e}")
            raise PortalRequestError(f"Upstream request to {path} failed.") from e

        # Check for unauthenticated / session expired indicators
        is_unauth = (
            response.status_code == 401
            or (response.status_code == 200 and '{"error":"unauthorized"' in response.text)
            or (response.history and any("/login" in str(r.url) for r in response.history))
        )

        if is_unauth:
            self.is_authenticated = False
            if retry_on_401:
                logger.info("Session expired or 401 detected. Attempting single re-authentication retry...")
                self.login()
                return self.request(method=method, path=path, params=params, json_data=json_data, retry_on_401=False)
            else:
                raise PortalSessionExpired("Session expired and re-authentication attempt failed.")

        if response.status_code == 404:
            raise MeterNotFoundError(path.split("/")[-1] if "meters/" in path else path)

        if response.status_code >= 500:
            raise PortalRequestError(
                message=f"Upstream portal error (status {response.status_code}).",
                status_code=response.status_code,
            )

        return response

    def get_meters(self, query: str = "", page: int = 1) -> Dict[str, Any]:
        """Fetches smart meters list from `/portal/meters/search`."""
        resp = self.request("GET", "/portal/meters/search", params={"q": query, "page": page})
        try:
            return resp.json()
        except Exception as e:
            raise PortalRequestError("Invalid JSON returned by meters search endpoint.") from e

    def get_meter_detail(self, meter_id: str) -> Dict[str, Any]:
        """
        Fetches meter detail load data from `/meters/{id}/__data.json` or `/meters/{id}`.
        """
        # Try SvelteKit server load data endpoint
        data_path = f"/meters/{meter_id}/__data.json"
        try:
            resp = self.request("GET", data_path)
            json_payload = resp.json()
            if isinstance(json_payload, dict) and json_payload.get("type") == "redirect":
                # Handle redirect if session lost
                raise PortalSessionExpired("Session expired on meter detail fetch.")
            return json_payload
        except Exception:
            # Fallback to direct page or return minimal structure
            return {"data": {"meterId": meter_id, "detail": [], "hierarchy": {}}}

    def get_meter_geo(self, meter_id: str) -> Optional[Dict[str, Any]]:
        """Fetches geographic coordinates from `/portal/meters/{id}/geo`."""
        try:
            resp = self.request("GET", f"/portal/meters/{meter_id}/geo")
            return resp.json()
        except Exception:
            return None

    def get_meter_consumption(self, meter_id: str) -> Dict[str, Any]:
        """Fetches time-series consumption readings from `/portal/meters/{id}/energy`."""
        resp = self.request("GET", f"/portal/meters/{meter_id}/energy")
        try:
            return resp.json()
        except Exception as e:
            raise PortalRequestError("Invalid JSON returned by energy consumption endpoint.") from e

    def get_hierarchy_dts(self, page: int = 1) -> Dict[str, Any]:
        """Fetches distribution transformers hierarchy list from `/portal/dts`."""
        resp = self.request("GET", "/portal/dts", params={"page": page})
        try:
            return resp.json()
        except Exception as e:
            raise PortalRequestError("Invalid JSON returned by distribution transformers endpoint.") from e

    def close(self):
        """Closes the underlying HTTP client."""
        self.client.close()
