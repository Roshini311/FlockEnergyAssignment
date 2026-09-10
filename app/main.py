"""
FastAPI Main Application and REST API Router.

Exposes clean, documented, versioned REST endpoints wrapping the legacy Urja Meter Ops portal.
All scraping and session logic is decoupled via UrjaPortalClient and parser modules.
"""

from typing import Optional
from fastapi import Depends, FastAPI, Query, status
from app.client import UrjaPortalClient
from app.config import settings
from app.exceptions import register_exception_handlers
from app.models import (
    ConsumptionReading,
    ConsumptionResponse,
    HealthCheckResponse,
    HierarchyResponse,
    LoginRequest,
    LoginResponse,
    MeterDetailResponse,
    MeterListResponse,
)
from app.parser import (
    parse_consumption_json,
    parse_hierarchy_json,
    parse_meter_detail,
    parse_meter_list_json,
)

# Initialize FastAPI application
app = FastAPI(
    title="Flock Energy — Urja Meter Ops API",
    description=(
        "Production-grade REST API wrapper providing clean, normalized access "
        "to smart-meter information, time-series consumption readings, and network hierarchy "
        "from the legacy Urja Meter Ops distribution portal."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Register custom exception handlers
register_exception_handlers(app)

# Global or dependency-managed client instance
_portal_client: Optional[UrjaPortalClient] = None


def get_portal_client() -> UrjaPortalClient:
    """Dependency provider for UrjaPortalClient instance."""
    global _portal_client
    if _portal_client is None:
        _portal_client = UrjaPortalClient()
    return _portal_client


@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
def health_check():
    """Health check endpoint to verify service readiness."""
    return HealthCheckResponse(
        status="ok",
        upstream_portal=settings.URJA_BASE_URL
    )


@app.post(
    "/api/v1/auth/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Authenticate with legacy Urja Meter Ops portal"
)
def login(
    payload: Optional[LoginRequest] = None,
    client: UrjaPortalClient = Depends(get_portal_client)
):
    """
    Authenticates the API client against the legacy portal.
    If email and password are provided in payload, uses those credentials;
    otherwise defaults to environment configured credentials (`URJA_USERNAME` / `URJA_PASSWORD`).
    """
    username = payload.email if payload and payload.email else None
    password = payload.password if payload and payload.password else None

    client.login(username=username, password=password)
    return LoginResponse(
        authenticated=True,
        message="Successfully authenticated with Urja Meter Ops portal."
    )


@app.get(
    "/api/v1/meters",
    response_model=MeterListResponse,
    tags=["Meters"],
    summary="List smart meters with search and pagination"
)
def list_meters(
    q: str = Query("", description="Optional search query (meter number, serial number, etc.)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    client: UrjaPortalClient = Depends(get_portal_client)
):
    """
    Retrieves a paginated list of smart meters from the portal.
    Supports optional string search query `q`.
    """
    raw_response = client.get_meters(query=q, page=page)
    meters, pagination = parse_meter_list_json(raw_response, page=page, page_size=page_size)
    return MeterListResponse(data=meters, pagination=pagination)


@app.get(
    "/api/v1/meters/{meter_id}",
    response_model=MeterDetailResponse,
    tags=["Meters"],
    summary="Get smart meter details and metadata"
)
def get_meter_detail(
    meter_id: str,
    client: UrjaPortalClient = Depends(get_portal_client)
):
    """
    Retrieves detailed metadata, hierarchy location, nameplate specifications,
    and geographic coordinates for a specific smart meter.
    """
    page_data = client.get_meter_detail(meter_id=meter_id)
    geo_data = client.get_meter_geo(meter_id=meter_id)
    return parse_meter_detail(meter_id=meter_id, page_data=page_data, geo_data=geo_data)


@app.get(
    "/api/v1/meters/{meter_id}/consumption",
    response_model=ConsumptionResponse,
    tags=["Meters"],
    summary="Get meter energy consumption readings"
)
def get_meter_consumption(
    meter_id: str,
    client: UrjaPortalClient = Depends(get_portal_client)
):
    """
    Retrieves time-series energy consumption readings (kWh, kVAh, Voltage)
    for the specified smart meter.
    """
    raw_response = client.get_meter_consumption(meter_id=meter_id)
    readings = parse_consumption_json(meter_id=meter_id, payload=raw_response)
    return ConsumptionResponse(meter_id=meter_id, data=readings)


@app.get(
    "/api/v1/hierarchy",
    response_model=HierarchyResponse,
    tags=["Hierarchy"],
    summary="Get network distribution transformers hierarchy"
)
def get_hierarchy(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    client: UrjaPortalClient = Depends(get_portal_client)
):
    """
    Retrieves a paginated list of Distribution Transformers (DTs) representing
    the network hierarchy structure.
    """
    raw_response = client.get_hierarchy_dts(page=page)
    transformers, pagination = parse_hierarchy_json(raw_response, page=page, page_size=page_size)
    return HierarchyResponse(data=transformers, pagination=pagination)
