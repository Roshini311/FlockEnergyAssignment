"""
Domain Exceptions and Exception Handlers.

Defines custom exception classes for upstream portal interactions
and maps them to clean HTTP status codes and sanitized REST error responses.
No credentials, cookies, or stack traces are leaked to API clients.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse


class PortalError(Exception):
    """Base exception for all portal integration errors."""
    def __init__(self, message: str = "An error occurred with the upstream portal."):
        self.message = message
        super().__init__(self.message)


class PortalAuthenticationError(PortalError):
    """Raised when authentication against the legacy portal fails."""
    def __init__(self, message: str = "Upstream portal authentication failed."):
        super().__init__(message)


class PortalSessionExpired(PortalError):
    """Raised when the portal session has expired or is invalid."""
    def __init__(self, message: str = "Upstream portal session expired."):
        super().__init__(message)


class PortalRequestError(PortalError):
    """Raised when an HTTP error occurs while communicating with the portal."""
    def __init__(self, message: str = "Upstream portal request failed.", status_code: int = 502):
        self.status_code = status_code
        super().__init__(message)


class UpstreamTimeoutError(PortalError):
    """Raised when a request to the upstream portal times out."""
    def __init__(self, message: str = "Upstream portal request timed out."):
        super().__init__(message)


class PortalParseError(PortalError):
    """Raised when legacy HTML or JSON payload parsing fails."""
    def __init__(self, message: str = "Failed to parse legacy portal response."):
        super().__init__(message)


class MeterNotFoundError(PortalError):
    """Raised when a requested meter ID is not found in the portal."""
    def __init__(self, meter_id: str):
        self.meter_id = meter_id
        super().__init__(f"Meter '{meter_id}' not found.")


# FastAPI Exception Handlers
def register_exception_handlers(app):
    @app.exception_handler(PortalAuthenticationError)
    async def auth_error_handler(request: Request, exc: PortalAuthenticationError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Upstream portal authentication failed. Check credentials."}
        )

    @app.exception_handler(PortalSessionExpired)
    async def session_expired_handler(request: Request, exc: PortalSessionExpired):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Portal session expired. Re-authentication required."}
        )

    @app.exception_handler(MeterNotFoundError)
    async def meter_not_found_handler(request: Request, exc: MeterNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"Meter '{exc.meter_id}' was not found on the upstream portal."}
        )

    @app.exception_handler(UpstreamTimeoutError)
    async def timeout_handler(request: Request, exc: UpstreamTimeoutError):
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": "Upstream portal request timed out."}
        )

    @app.exception_handler(PortalParseError)
    async def parse_error_handler(request: Request, exc: PortalParseError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Failed to parse data from the upstream portal."}
        )

    @app.exception_handler(PortalRequestError)
    async def request_error_handler(request: Request, exc: PortalRequestError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "Unable to retrieve information from the upstream portal."}
        )

    @app.exception_handler(PortalError)
    async def generic_portal_error_handler(request: Request, exc: PortalError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "An error occurred while communicating with the upstream portal."}
        )
