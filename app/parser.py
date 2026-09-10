"""
Parser and Normalization Module.

Contains pure helper functions for cleaning, normalizing, and transforming
legacy portal HTML/JSON payloads into standardized internal domain objects and Pydantic models.
Strictly decoupled from HTTP networking and BeautifulSoup logic.
"""

import json
from typing import Any, Dict, List, Optional, Tuple, Union
from bs4 import BeautifulSoup
from app.exceptions import PortalParseError
from app.models import (
    ConsumptionReading,
    MeterDetailResponse,
    MeterListItem,
    MeterLocation,
    MeterNameplateItem,
    PaginationMeta,
    TransformerItem,
)


def normalize_string(val: Optional[Any]) -> Optional[str]:
    """
    Strips whitespace and converts missing/ambiguous representations ("N/A", "-", "", "null") to None.
    Does not guess or mutate valid textual strings.
    """
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "N/A", "n/a", "N/a", "-", "null", "None", "undefined"):
        return None
    return s


def normalize_float(val: Optional[Any]) -> Optional[float]:
    """
    Converts valid numeric representations to float.
    Returns None for invalid, missing, or ambiguous non-numeric inputs like "N/A".
    """
    if val is None:
        return None
    cleaned = normalize_string(val)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def normalize_int(val: Optional[Any]) -> Optional[int]:
    """
    Converts valid integer representations to int.
    Returns None for invalid, missing, or non-numeric inputs.
    """
    if val is None:
        return None
    cleaned = normalize_string(val)
    if cleaned is None:
        return None
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


def parse_meter_list_json(payload: Dict[str, Any], page: int, page_size: int = 20) -> Tuple[List[MeterListItem], PaginationMeta]:
    """
    Parses the JSON payload returned by `/portal/meters/search`.
    Payload structure: `{"data": [...], "total": int}`
    """
    if not isinstance(payload, dict):
        raise PortalParseError("Expected dictionary payload from meter search endpoint.")

    raw_data = payload.get("data")
    if not isinstance(raw_data, list):
        raw_data = []

    total_records = normalize_int(payload.get("total")) or len(raw_data)
    total_pages = max(1, (total_records + page_size - 1) // page_size) if page_size > 0 else 1

    meters: List[MeterListItem] = []
    for item in raw_data:
        if not isinstance(item, dict):
            continue
        meter_id = normalize_string(item.get("meterId"))
        if not meter_id:
            continue
        meters.append(
            MeterListItem(
                meter_id=meter_id,
                serial_number=normalize_string(item.get("serialNo")),
                make=normalize_string(item.get("make")),
                phase_type=normalize_string(item.get("phaseType")),
                install_status=normalize_string(item.get("installStatus")),
                dt_code=normalize_string(item.get("dtCode")),
            )
        )

    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_records=total_records,
        total_pages=total_pages,
    )
    return meters, pagination


def extract_nameplate_details(detail_data: Any) -> List[MeterNameplateItem]:
    """
    Extracts nameplate parameters from legacy detail structure (either classData JSON string or list of param dicts).
    """
    items: List[MeterNameplateItem] = []
    if isinstance(detail_data, str):
        try:
            parsed = json.loads(detail_data)
            installed = parsed.get("installed_meter", {})
            if isinstance(installed, dict):
                for k, v in installed.items():
                    label = normalize_string(k)
                    val = normalize_string(v)
                    if label and val:
                        items.append(MeterNameplateItem(label=label, value=val))
        except (json.JSONDecodeError, TypeError):
            pass
    elif isinstance(detail_data, dict) and "classData" in detail_data:
        try:
            parsed = json.loads(detail_data["classData"])
            installed = parsed.get("installed_meter", {})
            if isinstance(installed, dict):
                for k, v in installed.items():
                    label = normalize_string(k)
                    val = normalize_string(v)
                    if label and val:
                        items.append(MeterNameplateItem(label=label, value=val))
        except (json.JSONDecodeError, TypeError):
            pass
    elif isinstance(detail_data, list):
        for entry in detail_data:
            if isinstance(entry, dict):
                label = normalize_string(entry.get("parameterName"))
                val = normalize_string(entry.get("parameterValue"))
                if label and val:
                    items.append(MeterNameplateItem(label=label, value=val))
    return items


def parse_meter_detail(
    meter_id: str,
    page_data: Dict[str, Any],
    geo_data: Optional[Dict[str, Any]] = None
) -> MeterDetailResponse:
    """
    Parses SvelteKit load data / detail payload along with optional geo JSON payload into MeterDetailResponse.
    """
    data = page_data.get("data", page_data) if isinstance(page_data, dict) else {}

    raw_hierarchy = data.get("hierarchy", {}) if isinstance(data, dict) else {}
    hierarchy: Dict[str, Optional[str]] = {}
    if isinstance(raw_hierarchy, dict):
        for key in ["Zone", "Circle", "Division", "Subdivision", "Sub Station", "Feeder", "DT"]:
            val = normalize_string(raw_hierarchy.get(key))
            if val:
                hierarchy[key] = val

    nameplate = extract_nameplate_details(data.get("detail"))

    location: Optional[MeterLocation] = None
    if geo_data and isinstance(geo_data, dict):
        g_data = geo_data.get("data", geo_data)
        if isinstance(g_data, dict):
            lat = normalize_float(g_data.get("latitude"))
            lng = normalize_float(g_data.get("longitude"))
            if lat is not None or lng is not None:
                location = MeterLocation(latitude=lat, longitude=lng)

    return MeterDetailResponse(
        meter_id=meter_id,
        hierarchy=hierarchy,
        nameplate=nameplate,
        location=location,
    )


def parse_consumption_json(meter_id: str, payload: Union[Dict[str, Any], List[Any]]) -> List[ConsumptionReading]:
    """
    Parses energy time-series array returned by `/portal/meters/{id}/energy`.
    Format: `[{"timestamp": "...", "kwh": ..., "kvah": ..., "voltR": ...}]` or `{"data": [...]}`
    """
    raw_list: List[Any] = []
    if isinstance(payload, dict):
        raw_list = payload.get("data", [])
    elif isinstance(payload, list):
        raw_list = payload

    readings: List[ConsumptionReading] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        ts = normalize_string(item.get("timestamp"))
        if not ts:
            continue
        readings.append(
            ConsumptionReading(
                timestamp=ts,
                kwh=normalize_float(item.get("kwh")),
                kvah=normalize_float(item.get("kvah")),
                volt_r=normalize_float(item.get("voltR")),
            )
        )
    return readings


def parse_hierarchy_json(payload: Dict[str, Any], page: int, page_size: int = 20) -> Tuple[List[TransformerItem], PaginationMeta]:
    """
    Parses distribution transformer list returned by `/portal/dts?page={page}`.
    Payload format: `{"data": [{"code": "...", "name": "...", "feederCode": "...", "capacityKva": ...}], "total": int}`
    """
    if not isinstance(payload, dict):
        raise PortalParseError("Expected dictionary payload from distribution transformers endpoint.")

    raw_data = payload.get("data")
    if not isinstance(raw_data, list):
        raw_data = []

    total_records = normalize_int(payload.get("total")) or len(raw_data)
    total_pages = max(1, (total_records + page_size - 1) // page_size) if page_size > 0 else 1

    transformers: List[TransformerItem] = []
    for item in raw_data:
        if not isinstance(item, dict):
            continue
        code = normalize_string(item.get("code"))
        name = normalize_string(item.get("name"))
        if not code or not name:
            continue
        transformers.append(
            TransformerItem(
                code=code,
                name=name,
                feeder_code=normalize_string(item.get("feederCode")),
                capacity_kva=normalize_float(item.get("capacityKva")),
            )
        )

    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_records=total_records,
        total_pages=total_pages,
    )
    return transformers, pagination
