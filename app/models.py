"""
Pydantic Request and Response Models.

Defines the clean, public REST API data contracts.
Hides legacy portal internal fields and normalizes naming to standard Python/snake_case.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Optional request payload to authenticate with explicit credentials."""
    email: Optional[str] = Field(None, description="Username or email for legacy portal")
    password: Optional[str] = Field(None, description="Password for legacy portal")


class LoginResponse(BaseModel):
    """Response returned upon successful authentication."""
    authenticated: bool = Field(True, description="Authentication status flag")
    message: str = Field("Successfully authenticated with Urja Meter Ops portal.", description="Status message")


class PaginationMeta(BaseModel):
    """Pagination metadata for collection endpoints."""
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, description="Number of records per page")
    total_records: int = Field(..., ge=0, description="Total matching records available upstream")
    total_pages: int = Field(..., ge=0, description="Total pages available")


class MeterListItem(BaseModel):
    """Normalized summary representation of a smart meter in listing endpoints."""
    meter_id: str = Field(..., description="Unique meter identifier")
    serial_number: Optional[str] = Field(None, description="Physical meter serial number")
    make: Optional[str] = Field(None, description="Manufacturer make")
    phase_type: Optional[str] = Field(None, description="Phase configuration (e.g., 1-Phase, 3-Phase)")
    install_status: Optional[str] = Field(None, description="Installation status (e.g., Active, Installed)")
    dt_code: Optional[str] = Field(None, description="Distribution Transformer code")

    model_config = ConfigDict(populate_by_name=True)


class MeterListResponse(BaseModel):
    """Response payload for meter search/listing endpoint."""
    data: List[MeterListItem] = Field(..., description="List of meters")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class MeterLocation(BaseModel):
    """Geographic coordinate representation for a meter location."""
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")


class MeterNameplateItem(BaseModel):
    """KeyValue pair representing nameplate parameters of a meter."""
    label: str = Field(..., description="Parameter label name")
    value: str = Field(..., description="Parameter value")


class MeterDetailResponse(BaseModel):
    """Comprehensive details response for a specific smart meter."""
    meter_id: str = Field(..., description="Unique meter identifier")
    hierarchy: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Network hierarchy breakdown (Zone, Circle, Division, Feeder, DT, etc.)"
    )
    nameplate: List[MeterNameplateItem] = Field(
        default_factory=list,
        description="Detailed nameplate parameters"
    )
    location: Optional[MeterLocation] = Field(None, description="Geographic location details if available")


class ConsumptionReading(BaseModel):
    """Time-series consumption reading for a smart meter."""
    timestamp: str = Field(..., description="Reading timestamp in ISO/portal format")
    kwh: Optional[float] = Field(None, description="Active energy reading in kWh")
    kvah: Optional[float] = Field(None, description="Apparent energy reading in kVAh")
    volt_r: Optional[float] = Field(None, description="R-Phase voltage reading in Volts")


class ConsumptionResponse(BaseModel):
    """Time-series energy consumption data response."""
    meter_id: str = Field(..., description="Meter identifier")
    data: List[ConsumptionReading] = Field(..., description="List of energy consumption readings")


class TransformerItem(BaseModel):
    """Distribution Transformer hierarchy item."""
    code: str = Field(..., description="Transformer code")
    name: str = Field(..., description="Transformer name")
    feeder_code: Optional[str] = Field(None, description="Associated Feeder Code")
    capacity_kva: Optional[float] = Field(None, description="Transformer capacity in kVA")


class HierarchyResponse(BaseModel):
    """Network hierarchy distribution transformers listing response."""
    data: List[TransformerItem] = Field(..., description="List of distribution transformers")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class HealthCheckResponse(BaseModel):
    """Health check endpoint response."""
    status: str = Field("ok", description="Service status")
    upstream_portal: str = Field(..., description="Target upstream portal URL")
