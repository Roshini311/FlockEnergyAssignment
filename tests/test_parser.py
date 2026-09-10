"""
Unit Tests for Data Normalization and Parsing (app/parser.py).
"""

import pytest
from app.exceptions import PortalParseError
from app.parser import (
    extract_nameplate_details,
    normalize_float,
    normalize_int,
    normalize_string,
    parse_consumption_json,
    parse_hierarchy_json,
    parse_meter_detail,
    parse_meter_list_json,
)


def test_normalize_string():
    assert normalize_string("  MTR-001  ") == "MTR-001"
    assert normalize_string("N/A") is None
    assert normalize_string("n/a") is None
    assert normalize_string("-") is None
    assert normalize_string("") is None
    assert normalize_string(None) is None
    assert normalize_string("null") is None
    assert normalize_string("Active") == "Active"


def test_normalize_float():
    assert normalize_float("124.50") == 124.5
    assert normalize_float("0") == 0.0
    assert normalize_float(45.2) == 45.2
    assert normalize_float("N/A") is None  # Crucial requirement: N/A must NOT become 0.0!
    assert normalize_float("-") is None
    assert normalize_float("invalid_number") is None
    assert normalize_float(None) is None


def test_normalize_int():
    assert normalize_int("20") == 20
    assert normalize_int("20.0") == 20
    assert normalize_int(100) == 100
    assert normalize_int("N/A") is None
    assert normalize_int("abc") is None


def test_parse_meter_list_json_valid():
    payload = {
        "data": [
            {
                "meterId": "MTR-1001",
                "serialNo": " SN-9988 ",
                "make": "Genus",
                "phaseType": "3-Phase",
                "installStatus": "Installed",
                "dtCode": "DT-501"
            },
            {
                "meterId": "MTR-1002",
                "serialNo": "N/A",
                "make": None,
                "phaseType": "-",
                "installStatus": "Active",
                "dtCode": "DT-501"
            }
        ],
        "total": 45
    }
    meters, pagination = parse_meter_list_json(payload, page=1, page_size=20)
    assert len(meters) == 2
    assert meters[0].meter_id == "MTR-1001"
    assert meters[0].serial_number == "SN-9988"
    assert meters[0].make == "Genus"

    # Verify N/A and missing values are correctly normalized to None
    assert meters[1].meter_id == "MTR-1002"
    assert meters[1].serial_number is None
    assert meters[1].make is None
    assert meters[1].phase_type is None

    # Verify pagination math
    assert pagination.page == 1
    assert pagination.page_size == 20
    assert pagination.total_records == 45
    assert pagination.total_pages == 3


def test_parse_meter_list_json_malformed():
    with pytest.raises(PortalParseError):
        parse_meter_list_json("invalid_payload", page=1)


def test_extract_nameplate_details():
    json_class_data = '{"installed_meter": {"CT Ratio": "100/5", "Accuracy Class": "0.5s", "Manufacture Year": "N/A"}}'
    items = extract_nameplate_details(json_class_data)
    assert len(items) == 2
    assert items[0].label == "CT Ratio"
    assert items[0].value == "100/5"
    assert items[1].label == "Accuracy Class"
    assert items[1].value == "0.5s"


def test_parse_meter_detail():
    page_data = {
        "data": {
            "meterId": "MTR-1001",
            "hierarchy": {
                "Zone": "North",
                "Circle": "Circle-A",
                "DT": "DT-501",
                "Feeder": "N/A"
            },
            "detail": [
                {"parameterName": "Voltage Rating", "parameterValue": "230V"},
                {"parameterName": "Current Rating", "parameterValue": "5-30A"}
            ]
        }
    }
    geo_data = {
        "data": {
            "latitude": "28.6139",
            "longitude": "77.2090"
        }
    }

    result = parse_meter_detail("MTR-1001", page_data, geo_data)
    assert result.meter_id == "MTR-1001"
    assert result.hierarchy["Zone"] == "North"
    assert result.hierarchy["Circle"] == "Circle-A"
    assert "Feeder" not in result.hierarchy  # "N/A" removed
    assert len(result.nameplate) == 2
    assert result.location is not None
    assert result.location.latitude == 28.6139
    assert result.location.longitude == 77.2090


def test_parse_consumption_json():
    payload = {
        "data": [
            {"timestamp": "2026-09-10T10:00:00Z", "kwh": "15.40", "kvah": "16.10", "voltR": "230.5"},
            {"timestamp": "2026-09-10T10:15:00Z", "kwh": "15.80", "kvah": "N/A", "voltR": "-"}
        ]
    }
    readings = parse_consumption_json("MTR-1001", payload)
    assert len(readings) == 2
    assert readings[0].kwh == 15.4
    assert readings[0].kvah == 16.1
    assert readings[0].volt_r == 230.5

    assert readings[1].kwh == 15.8
    assert readings[1].kvah is None
    assert readings[1].volt_r is None


def test_parse_hierarchy_json():
    payload = {
        "data": [
            {"code": "DT-101", "name": "DT Central Market", "feederCode": "F-01", "capacityKva": "250"},
            {"code": "DT-102", "name": "DT Residential Block A", "feederCode": "F-01", "capacityKva": "N/A"}
        ],
        "total": 2
    }
    transformers, pagination = parse_hierarchy_json(payload, page=1, page_size=20)
    assert len(transformers) == 2
    assert transformers[0].code == "DT-101"
    assert transformers[0].capacity_kva == 250.0
    assert transformers[1].capacity_kva is None
    assert pagination.total_records == 2
    assert pagination.total_pages == 1
